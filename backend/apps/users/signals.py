import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.common.models import ManagerRoutingRule

from .services.responsible_manager import RULE_STATE_FIELDS, affected_keys, reassign_clients_for_key
from .tasks import send_user_verified_email

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(pre_save, sender=User)
def store_previous_verification_status(sender, instance, **kwargs):
    """
    Сохраняем предыдущие статус верификации и активность перед сохранением модели.
    Это необходимо для определения их изменения в post_save: письмо о
    верификации и пересчёт клиентов при блокировке менеджера (стори 42.7).
    Старая запись читается одним запросом на оба признака.
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_verification_status = old_instance.verification_status
            instance._old_is_verified = old_instance.is_verified
            instance._old_is_active = old_instance.is_active
        except User.DoesNotExist:
            pass


@receiver(post_save, sender=User)
def check_verification_status_change(sender, instance, created, **kwargs):
    """
    Проверяем изменение статуса верификации и отправляем уведомление при необходимости.
    Срабатывает когда статус меняется на 'verified'.
    """
    if created:
        return

    # Получаем старые значения (если они были сохранены в pre_save)
    old_status = getattr(instance, "_old_verification_status", None)

    # Проверяем переход в статус verified
    # Триггером может быть изменение verification_status на 'verified'
    if old_status != "verified" and instance.verification_status == "verified":
        logger.info(f"User {instance.id} verification status changed to 'verified'. " "Sending email.")
        send_user_verified_email.delay(instance.id)


# --- Пересчёт ответственного менеджера при смене правила региона (стори 42.2) ---
# Синхронно, внутри транзакции сохранения правила: правила меняются редко,
# а пересчёт одного ключа — один UPDATE.


def _rule_state(rule: ManagerRoutingRule) -> dict:
    return {field: getattr(rule, field) for field in RULE_STATE_FIELDS}


def _reassign_affected(old: dict | None, new: dict | None) -> None:
    for key in affected_keys(old, new):
        reassign_clients_for_key(key)


@receiver(post_save, sender=User)
def reassign_clients_after_manager_activity_change(sender, instance, created, **kwargs):
    """
    Блокировка и разблокировка менеджера пересчитывают клиентов его правил (стори 42.7).

    Правило заблокированного менеджера ответственного не даёт: клиенты его
    ключей без ручного назначения уходят на резерв, после разблокировки —
    возвращаются. Пересчёт в той же транзакции, что и сохранение.

    Срабатывает только через ``save()`` — так блокируют все три пути: действие
    раздела руководителя, ``UserAdmin.block_users`` и флажок «Активен» в
    ``/admin/``. ``QuerySet.update(is_active=…)`` пересчёт обойдёт. Без смены
    ``is_active`` запросов нет: импорт 1С сохраняет тысячи ``User``.
    """
    if created:
        return
    old_is_active = getattr(instance, "_old_is_active", None)
    if old_is_active is None or old_is_active == instance.is_active:
        return
    rules = ManagerRoutingRule.objects.filter(manager=instance, is_active=True).values_list("match_type", "match_value")
    keys = {
        None if match_type == ManagerRoutingRule.MATCH_FALLBACK else (match_type, match_value)
        for match_type, match_value in rules
    }
    for key in keys:
        reassign_clients_for_key(key)


@receiver(pre_save, sender=ManagerRoutingRule)
def store_previous_routing_rule_state(sender, instance, **kwargs):
    """Запоминаем ключ, активность и менеджера правила до сохранения."""
    instance._previous_routing_state = (
        ManagerRoutingRule.objects.filter(pk=instance.pk).values(*RULE_STATE_FIELDS).first()
        if instance.pk is not None
        else None
    )


@receiver(post_save, sender=ManagerRoutingRule)
def reassign_clients_after_rule_save(sender, instance, **kwargs):
    _reassign_affected(getattr(instance, "_previous_routing_state", None), _rule_state(instance))


@receiver(post_delete, sender=ManagerRoutingRule)
def reassign_clients_after_rule_delete(sender, instance, **kwargs):
    _reassign_affected(_rule_state(instance), None)

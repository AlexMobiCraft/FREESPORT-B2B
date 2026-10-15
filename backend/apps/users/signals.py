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
    Сохраняем предыдущий статус верификации перед сохранением модели.
    Это необходимо для определения изменения статуса в post_save.
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            instance._old_verification_status = old_instance.verification_status
            instance._old_is_verified = old_instance.is_verified
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

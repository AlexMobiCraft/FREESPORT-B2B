import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

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

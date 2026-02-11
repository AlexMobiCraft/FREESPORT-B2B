"""
Сигналы для заказов FREESPORT
Отправка email-уведомлений при создании заказа (AC6)
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import Signal, receiver

from .models import Order

logger = logging.getLogger(__name__)

# Custom signal for bulk order updates (bypasses post_save)
# Provides: order_ids (list[int]), updated_count (int), field (str), timestamp (datetime)
orders_bulk_updated = Signal()


@receiver(post_save, sender=Order)
def send_order_confirmation_email(sender, instance, created, **kwargs):
    """
    Отправка email-уведомлений при создании нового заказа.

    Обе задачи (клиенту и администраторам) выполняются асинхронно через Celery,
    чтобы не блокировать post_save обработчик.

    Args:
        sender: Класс модели (Order)
        instance: Экземпляр заказа
        created: True если заказ только что создан
        **kwargs: Дополнительные аргументы сигнала
    """
    if not created:
        return

    # --- Отправка уведомления клиенту (async через Celery) ---
    try:
        from apps.orders.tasks import send_order_confirmation_to_customer

        send_order_confirmation_to_customer.delay(instance.id)
        logger.info(f"Задача отправки подтверждения клиенту для заказа " f"{instance.order_number} добавлена в очередь")
    except Exception as e:
        logger.error(f"Ошибка добавления задачи подтверждения клиенту для заказа " f"{instance.order_number}: {e}")

    # --- Отправка уведомления администраторам (async через Celery) ---
    try:
        from apps.orders.tasks import send_order_notification_email

        send_order_notification_email.delay(instance.id)
        logger.info(f"Задача уведомления администраторов о заказе {instance.order_number} " "добавлена в очередь")
    except Exception as e:
        logger.error(f"Ошибка добавления задачи уведомления для заказа {instance.order_number}: {e}")

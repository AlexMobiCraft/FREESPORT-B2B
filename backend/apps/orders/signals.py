"""
Сигналы для заказов OPTISPORT
Отправка email-уведомлений при создании заказа (AC6)
"""

import logging

from django.db import transaction
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

    Обе задачи (клиенту и получателям) ставятся в очередь Celery только после
    фиксации транзакции: до коммита воркер не находит заказ с субзаказами и
    позициями (`Order.DoesNotExist`, письмо теряется без повтора). На каждую
    задачу свой колбэк `on_commit(robust=True)`: сбой брокера не роняет
    оформление заказа, который уже зафиксирован, и не мешает второй задаче.
    Штатный лог `robust` номера заказа не содержит, поэтому ошибку ловим внутри
    колбэка и пишем номер в текст сообщения.

    Args:
        sender: Класс модели (Order)
        instance: Экземпляр заказа
        created: True если заказ только что создан
        **kwargs: Дополнительные аргументы сигнала
    """
    if not created:
        return

    if not instance.is_master:
        return

    order_id = instance.id
    order_number = instance.order_number

    def enqueue_customer_confirmation() -> None:
        # Импорт при срабатывании колбэка: tasks импортирует модели приложения.
        try:
            from apps.orders.tasks import send_order_confirmation_to_customer

            send_order_confirmation_to_customer.delay(order_id)
            logger.info(f"Задача отправки подтверждения клиенту для заказа {order_number} добавлена в очередь")
        except Exception as e:
            logger.error(f"Ошибка добавления задачи подтверждения клиенту для заказа {order_number}: {e}")

    def enqueue_recipients_notification() -> None:
        try:
            from apps.orders.tasks import send_order_notification_email

            send_order_notification_email.delay(order_id)
            logger.info(f"Задача уведомления о заказе {order_number} добавлена в очередь")
        except Exception as e:
            logger.error(f"Ошибка добавления задачи уведомления для заказа {order_number}: {e}")

    transaction.on_commit(enqueue_customer_confirmation, robust=True)
    transaction.on_commit(enqueue_recipients_notification, robust=True)

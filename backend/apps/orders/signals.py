"""
Сигналы для заказов OPTISPORT
Отправка email-уведомлений при создании заказа (AC6) и восстановление статуса
субзаказа после снятия отметки `export_skipped`.
"""

import logging

from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import Signal, receiver
from django.utils import timezone

from .models import Order

logger = logging.getLogger(__name__)

# Атрибут экземпляра: pre_save увидел в БД export_skipped=True, а сохраняется False.
_EXPORT_SKIPPED_CLEARED_ATTR = "_export_skipped_cleared"

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


@receiver(pre_save, sender=Order)
def remember_export_skipped_cleared(sender, instance, raw=False, update_fields=None, **kwargs):
    """Запомнить, что `save()` субзаказа снимает отметку `export_skipped`.

    Старое значение читается из БД: экземпляр мог быть загружен давно, а флаг
    выставляет выгрузка через `queryset.update`. Проверяются только уже
    существующие субзаказы и только сохранения, которые пишут `export_skipped`
    (`update_fields` пуст или содержит поле).
    """
    setattr(instance, _EXPORT_SKIPPED_CLEARED_ATTR, False)
    if raw or instance.is_master or instance._state.adding or instance.pk is None:
        return
    if update_fields is not None and "export_skipped" not in update_fields:
        return
    if instance.export_skipped:
        return
    was_skipped = Order.objects.filter(pk=instance.pk, export_skipped=True).exists()
    setattr(instance, _EXPORT_SKIPPED_CLEARED_ATTR, was_skipped)


@receiver(post_save, sender=Order)
def promote_sub_order_after_export_skipped_cleared(sender, instance, created, raw=False, **kwargs):
    """Вернуть субзаказу «В обработке», когда с него сняли `export_skipped`.

    Подтверждение выгрузки по кэшу ID помечает отправленным и субзаказ, который
    пропустили уже после формирования пачки, но в `processing` его не переводит
    (`promote_exported_sub_orders` исключает `export_skipped=True`). Повторно
    выгрузка такой субзаказ не выберет: `sent_to_1c=True`. Когда менеджер
    снимает флаг через `save()`, отправленный `pending`-субзаказ переводится
    `pending` → `processing`, мастер пересчитывается.

    Ограничение: `queryset.update()` и прямой SQL сигналов не вызывают — снятие
    флага ими статус не восстанавливает. Повторного входа нет: мастер
    сохраняется с `is_master=True`, а `pre_save` мастера флаг не взводит.
    """
    cleared = getattr(instance, _EXPORT_SKIPPED_CLEARED_ATTR, False)
    setattr(instance, _EXPORT_SKIPPED_CLEARED_ATTR, False)
    if raw or created or not cleared:
        return
    # Состояние читается из БД: экземпляр мог не знать о пометке sent_to_1c.
    if not Order.objects.filter(pk=instance.pk, is_master=False, sent_to_1c=True, status="pending").exists():
        return

    # Импорт при срабатывании: сервис импортирует модели приложения.
    from apps.orders.services.order_export_status import promote_exported_sub_orders

    promoted, _masters = promote_exported_sub_orders([instance.pk], timezone.now())
    if promoted:
        # Экземпляр не должен вернуть старый статус следующим полным save().
        instance.status = "processing"
        logger.info(f"Субзаказ {instance.order_number} переведён в processing после снятия export_skipped")

"""Статус заказа после выгрузки в 1С.

Когда обмен с 1С подтверждает выгрузку субзаказа (`sent_to_1c=True`), клиент
должен видеть заказ «В обработке», а не «Новый»: импорт статусов из 1С
приходит с задержкой или не приходит вовсе.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from datetime import datetime

from django.db import transaction

from apps.orders.models import Order
from apps.orders.services.order_status_import import OrderStatusImportService

logger = logging.getLogger(__name__)


def promote_exported_sub_orders(sub_ids: Iterable[int], now: datetime) -> tuple[int, list[int]]:
    """Перевести только что выгруженные субзаказы `pending` → `processing`.

    Принимает PK субзаказов, которые в этом обмене впервые получили
    `sent_to_1c=True`. Статус меняется только у `pending`: остальные статусы
    уже пришли из 1С или выставлены менеджером. Мастера этих субзаказов
    пересчитываются агрегацией `OrderStatusImportService`, поэтому мастер
    уходит в `processing`, только когда ни один его субзаказ не остался `pending`.

    Вызывается внутри транзакции, в которой субзаказы помечены отправленными.

    Returns:
        (число переведённых субзаказов, PK мастеров с изменённым статусом).
    """
    sub_ids = list(sub_ids)
    if not sub_ids:
        return 0, []

    with transaction.atomic():
        # Условие по статусу защищает от гонки с ручной сменой статуса менеджером.
        # export_skipped перепроверяется: подтверждение по кэшу ID флаг не смотрит,
        # а его могли выставить уже после формирования пачки.
        # Сначала блокируются субзаказы (порядок pk), затем мастера — тот же порядок,
        # что у отмены и импорта статусов.
        promoted_ids = list(
            Order.objects.select_for_update()
            .filter(pk__in=sub_ids, is_master=False, status="pending", export_skipped=False)
            .order_by("pk")
            .values_list("pk", flat=True)
        )
        if not promoted_ids:
            # Статус ни одного субзаказа не изменился — мастеров не трогаем.
            return 0, []
        promoted = Order.objects.filter(pk__in=promoted_ids).update(status="processing", updated_at=now)

        # Пересчитываются только мастера переведённых субзаказов.
        master_ids = set(
            Order.objects.filter(pk__in=promoted_ids, parent_order__isnull=False).values_list(
                "parent_order_id", flat=True
            )
        )
        if not master_ids:
            return promoted, []

        aggregator = OrderStatusImportService()
        changed_master_ids: list[int] = []
        masters = Order.objects.select_for_update().filter(pk__in=master_ids, is_master=True).order_by("pk")
        for master in masters:
            new_status, _regression_blocked = aggregator._aggregate_master_status(master)
            if new_status is None:
                continue
            master.status = new_status
            # update_fields: экземпляр мог быть загружен до queryset.update(sent_to_1c=True),
            # полный save() вернул бы мастеру sent_to_1c=False. post_save (бонусы) срабатывает.
            master.save(update_fields=["status", "updated_at"])
            changed_master_ids.append(master.pk)

    if promoted or changed_master_ids:
        logger.info(
            "[EXPORT STATUS] %s sub-orders pending → processing, masters re-aggregated: %s",
            promoted,
            changed_master_ids,
        )
    return promoted, changed_master_ids

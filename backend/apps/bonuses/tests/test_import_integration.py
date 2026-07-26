"""Unit-тесты продакшен-пути начисления: импорт статусов из 1С.

Остальные тесты дёргают `Order.save()` напрямую. Здесь проверяется реальная
цепочка, которая работает в проде:

`OrderStatusImportService.process()` → `transaction.atomic()` →
`_apply_master_aggregation` → `select_for_update` → `master.save()` →
`post_save` → savepoint → `BonusTransaction`.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.tests.utils import create_master_with_subs, create_user
from apps.orders.constants import ORDER_ID_PREFIX
from apps.orders.services.order_status_import import OrderStatusImportService


def _xml_for(order, status_1c: str) -> str:
    """Минимальный CommerceML 3.1 документ со статусом заказа."""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-07-25T12:00:00">
    <Контейнер>
        <Документ>
            <Ид>{ORDER_ID_PREFIX}{order.pk}</Ид>
            <Номер>{order.order_number}</Номер>
            <Дата>2026-07-25</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>{status_1c}</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""


@pytest.mark.unit
@pytest.mark.django_db
class TestAccrualThroughImport:
    """Начисление через настоящий сервис импорта статусов."""

    def test_closing_all_subs_accrues_bonus(self) -> None:
        """«Закрыт» по всем субзаказам → агрегация мастера → одно начисление."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["50000.00", "30000.00"])
        subs = list(master.sub_orders.all())

        for sub in subs:
            OrderStatusImportService().process(_xml_for(sub, "Закрыт"))

        master.refresh_from_db()
        assert master.status == "delivered"

        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.amount == Decimal("4000.00")
        assert bonus.base_amount == Decimal("80000.00")

    def test_partial_closure_accrues_nothing(self) -> None:
        """Пока закрыт не весь заказ — бонуса нет."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["50000.00", "30000.00"])
        first_sub = master.sub_orders.first()

        OrderStatusImportService().process(_xml_for(first_sub, "Закрыт"))

        master.refresh_from_db()
        assert master.status != "delivered"
        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_repeated_import_of_same_xml_is_idempotent(self) -> None:
        """Повторный прогон того же XML не меняет баланс и не рвёт импорт."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        sub = master.sub_orders.first()
        xml = _xml_for(sub, "Закрыт")

        first_result = OrderStatusImportService().process(xml)
        second_result = OrderStatusImportService().process(xml)

        assert first_result.updated == 1
        assert second_result.errors == []
        assert BonusTransaction.objects.filter(order=master).count() == 1
        assert BonusTransaction.objects.get(order=master).amount == Decimal("1000.00")

    def test_cancelled_sub_is_not_paid_for(self) -> None:
        """Отменённый в 1С субзаказ не попадает в базу начисления."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00", "100000.00"])
        subs = list(master.sub_orders.all())

        OrderStatusImportService().process(_xml_for(subs[0], "Закрыт"))
        OrderStatusImportService().process(_xml_for(subs[1], "Отменен"))

        master.refresh_from_db()
        # Мастер со смешанными статусами агрегируется в `delivered`
        # (у `cancelled` приоритет 0), поэтому начисление обязано произойти —
        # но только за закрытую половину заказа
        assert master.status == "delivered"
        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.base_amount == Decimal("100000.00")
        assert bonus.amount == Decimal("5000.00")

    def test_import_survives_when_accrual_is_impossible(self) -> None:
        """Сбой начисления не мешает импорту обновить статус заказа."""
        settings = BonusProgramSettings.load()
        settings.is_active = False
        settings.save()

        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        sub = master.sub_orders.first()

        result = OrderStatusImportService().process(_xml_for(sub, "Закрыт"))

        sub.refresh_from_db()
        assert result.updated == 1
        assert sub.status == "delivered"
        assert BonusTransaction.objects.count() == 0

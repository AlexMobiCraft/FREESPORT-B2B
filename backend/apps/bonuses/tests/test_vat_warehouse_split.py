"""Начисление бонуса по заказу, разбитому на субзаказы по НДС и складам.

Остальные тесты собирают мастер и субзаказы вручную. Здесь проходит полный
продакшен-путь для самого частого реального случая:

корзина со смешанными ставками НДС и складами →
`OrderCreateService.create()` → мастер + N субзаказов →
`OrderStatusImportService.process()` по каждому субзаказу →
агрегация мастера → `post_save` → `BonusTransaction`.

База начисления обязана равняться сумме товаров по всем субзаказам
независимо от количества групп разбивки, без доставки и без учёта
отменённых групп.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.bonuses.models import BonusTransaction
from apps.bonuses.tests.utils import create_user, ensure_program_started
from apps.cart.models import Cart, CartItem
from apps.orders.constants import ORDER_ID_PREFIX
from apps.orders.services.order_create import OrderCreateService
from apps.orders.services.order_status_import import OrderStatusImportService
from apps.products.factories import ProductVariantFactory

# Склады из ONEC_EXCHANGE.WAREHOUSE_RULES:
# «1 СДВ склад» — без vat_rate в правилах, ставка берётся с варианта;
# «Intex ОСНОВНОЙ» — vat_rate 22 из правил;
# «2 ТЛВ склад» — vat_rate 5 из правил (другое юрлицо).
SDV = "1 СДВ склад"
INTEX = "Intex ОСНОВНОЙ"
TLV = "2 ТЛВ склад"

ORDER_DATA = {
    "delivery_address": "г. Москва, ул. Тестовая, д. 1",
    "delivery_method": "courier",
    "payment_method": "card",
}


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


def _build_cart(user, specs: list[tuple[str | None, str | None, str, int]]) -> Cart:
    """Корзина из позиций вида (склад, ставка НДС варианта, цена, количество).

    Цена фиксируется снимком, чтобы база начисления не зависела
    от ролевого прайса тренера.
    """
    cart = Cart.objects.create(user=user)
    for warehouse_name, vat_rate, price, quantity in specs:
        variant = ProductVariantFactory(
            warehouse_name=warehouse_name,
            vat_rate=Decimal(vat_rate) if vat_rate is not None else None,
            stock_quantity=quantity + 100,
            reserved_quantity=0,
        )
        CartItem.objects.create(
            cart=cart,
            variant=variant,
            quantity=quantity,
            price_snapshot=Decimal(price),
        )
    return cart


def _create_order(user, specs, delivery_cost: str = "0"):
    """Создаёт заказ через продакшен-сервис разбивки по VAT-группам."""
    ensure_program_started()
    cart = _build_cart(user, specs)
    return OrderCreateService(
        cart=cart,
        user=user,
        validated_data=dict(ORDER_DATA),
        delivery_cost=Decimal(delivery_cost),
    ).create()


def _close(order, status_1c: str = "Закрыт") -> None:
    """Прогоняет заказ через импорт статусов из 1С."""
    OrderStatusImportService().process(_xml_for(order, status_1c))


@pytest.mark.unit
@pytest.mark.django_db
class TestSplitByVatAndWarehouse:
    """Разбивка корзины на субзаказы по паре (ставка НДС, склад)."""

    def test_different_vat_rates_are_split(self) -> None:
        """Разные ставки НДС → разные субзаказы."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "10000.00", 1),  # 22% из правил склада
                (TLV, None, "20000.00", 1),  # 5% из правил склада
            ],
        )

        subs = list(master.sub_orders.order_by("suborder_sequence"))
        assert len(subs) == 2
        assert {sub.vat_group for sub in subs} == {Decimal("22"), Decimal("5")}

    def test_same_vat_different_warehouses_are_split(self) -> None:
        """Одна ставка НДС, но разные склады → всё равно разные субзаказы.

        1С требует отдельный документ на каждое юрлицо/склад, поэтому
        группировка идёт по паре (ставка, склад), а не по одной ставке.
        """
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (SDV, "22.00", "10000.00", 1),  # ставка с варианта: у склада правил нет
                (INTEX, None, "15000.00", 1),  # 22% из правил склада
            ],
        )

        subs = list(master.sub_orders.all())
        assert len(subs) == 2, "Одинаковая ставка НДС на разных складах слиплась в один субзаказ"
        assert {sub.vat_group for sub in subs} == {Decimal("22")}

    def test_same_vat_same_warehouse_stay_together(self) -> None:
        """Одинаковые ставка и склад → один субзаказ на обе позиции."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (TLV, None, "1000.00", 2),
                (TLV, None, "500.00", 3),
            ],
        )

        subs = list(master.sub_orders.all())
        assert len(subs) == 1
        assert subs[0].items.count() == 2
        assert subs[0].total_amount == Decimal("3500.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestAccrualOverSplitOrder:
    """База начисления по разбитому заказу."""

    def test_base_covers_all_vat_groups(self) -> None:
        """Бонус один на мастер и считается от суммы всех субзаказов.

        Три группы: два склада с 22% и один с 5%. Товаров на 80 000 ₽,
        при 5% программы бонус — 4 000 ₽.
        """
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (SDV, "22.00", "30000.00", 1),
                (INTEX, None, "20000.00", 1),
                (TLV, None, "15000.00", 2),
            ],
        )
        subs = list(master.sub_orders.all())
        assert len(subs) == 3

        for sub in subs:
            _close(sub)

        master.refresh_from_db()
        assert master.status == "delivered"

        bonuses = BonusTransaction.objects.filter(order=master)
        assert bonuses.count() == 1, "Разбивка на субзаказы не должна множить начисления"
        bonus = bonuses.get()
        assert bonus.base_amount == Decimal("80000.00")
        assert bonus.percent_applied == Decimal("5.00")
        assert bonus.amount == Decimal("4000.00")

    def test_delivery_cost_is_excluded_from_base(self) -> None:
        """Доставка лежит на мастере и в базу начисления не входит."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "50000.00", 1),
                (TLV, None, "30000.00", 1),
            ],
            delivery_cost="1500.00",
        )

        for sub in master.sub_orders.all():
            _close(sub)

        master.refresh_from_db()
        assert master.total_amount == Decimal("81500.00"), "Доставка должна попадать в сумму заказа"

        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.base_amount == Decimal("80000.00"), "Доставка просочилась в базу начисления"
        assert bonus.amount == Decimal("4000.00")

    def test_partial_closure_of_split_order_gives_nothing(self) -> None:
        """Закрыты не все группы → бонуса нет, деньги ещё в работе."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (SDV, "22.00", "30000.00", 1),
                (INTEX, None, "20000.00", 1),
                (TLV, None, "15000.00", 1),
            ],
        )
        subs = list(master.sub_orders.all())

        _close(subs[0])
        _close(subs[1])

        master.refresh_from_db()
        assert master.status != "delivered"
        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_cancelled_vat_group_is_not_paid_for(self) -> None:
        """Отменённая группа исключается из базы, остальные оплачиваются.

        Мастер со смешанными статусами агрегируется в `delivered`
        (у `cancelled` приоритет 0), поэтому без фильтра по статусу
        субзаказов бонус начислился бы и за отменённый товар.
        """
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "100000.00", 1),
                (TLV, None, "100000.00", 1),
            ],
        )
        subs = list(master.sub_orders.order_by("suborder_sequence"))

        _close(subs[0], "Закрыт")
        _close(subs[1], "Отменен")

        master.refresh_from_db()
        assert master.status == "delivered"

        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.base_amount == Decimal("100000.00"), "Бонус начислен за отменённую группу"
        assert bonus.amount == Decimal("5000.00")

    def test_fully_cancelled_split_order_gives_nothing(self) -> None:
        """Все группы отменены → начислять не за что."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "40000.00", 1),
                (TLV, None, "60000.00", 1),
            ],
        )

        for sub in master.sub_orders.all():
            _close(sub, "Отменен")

        master.refresh_from_db()
        assert master.status == "cancelled"
        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_repeated_import_over_split_order_is_idempotent(self) -> None:
        """Повторный прогон того же XML по всем группам не удваивает бонус."""
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "12345.67", 1),
                (TLV, None, "7654.33", 1),
            ],
        )
        subs = list(master.sub_orders.all())

        for _ in range(2):
            for sub in subs:
                _close(sub)

        bonuses = BonusTransaction.objects.filter(order=master)
        assert bonuses.count() == 1
        bonus = bonuses.get()
        assert bonus.base_amount == Decimal("20000.00")
        assert bonus.amount == Decimal("1000.00")

    def test_rounding_over_split_groups_is_half_up(self) -> None:
        """База с копейками округляется до копейки по ROUND_HALF_UP.

        5% от 1 234,50 ₽ = 61,725 ₽ → 61,73 ₽.
        """
        trainer = create_user()
        master = _create_order(
            trainer,
            [
                (INTEX, None, "1000.20", 1),
                (TLV, None, "234.30", 1),
            ],
        )

        for sub in master.sub_orders.all():
            _close(sub)

        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.base_amount == Decimal("1234.50")
        assert bonus.amount == Decimal("61.73")

    def test_non_trainer_split_order_accrues_nothing(self) -> None:
        """Разбивка заказа не делает бонусы доступными не-тренеру."""
        buyer = create_user(role="retail")
        master = _create_order(
            buyer,
            [
                (INTEX, None, "50000.00", 1),
                (TLV, None, "50000.00", 1),
            ],
        )

        for sub in master.sub_orders.all():
            _close(sub)

        master.refresh_from_db()
        assert master.status == "delivered"
        assert BonusTransaction.objects.count() == 0

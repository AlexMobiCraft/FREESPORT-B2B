"""
Shared helper functions for test fixtures (Story 34-5).

Provides reusable helpers for creating master+sub order structures
used across Epic 4 and Epic 5 tests.
"""

from collections import defaultdict
from decimal import Decimal
from typing import TYPE_CHECKING

from apps.orders.models import Order, OrderItem

if TYPE_CHECKING:
    from apps.products.models import ProductVariant
    from apps.users.models import User


def create_master_with_subs(
    user: "User | None" = None,
    variants_with_vat: "list[tuple[ProductVariant, Decimal | None]] | None" = None,
    *,
    sent_to_1c: bool = False,
    delivery_address: str = "ул. Тестовая, 1",
    delivery_method: str = "courier",
    payment_method: str = "card",
    customer_name: str = "",
    customer_email: str = "",
    customer_phone: str = "",
    status: str = "pending",
) -> "tuple[Order, list[Order]]":
    """Создаёт master + N sub-orders по VAT-группам.

    Args:
        user: владелец заказа (None для гостевого).
        variants_with_vat: [(variant, vat_rate), ...]. Группировка по vat_rate.
        sent_to_1c: флаг отправки в 1С.
        delivery_address: адрес доставки.
        delivery_method: способ доставки.
        payment_method: способ оплаты.
        customer_name: имя клиента (гостевой заказ).
        customer_email: email клиента (гостевой заказ).
        customer_phone: телефон клиента (гостевой заказ).
        status: начальный статус.

    Returns:
        (master, [sub1, sub2, ...]) — master.is_master=True, sub.is_master=False.
    """
    common = dict(
        user=user,
        delivery_address=delivery_address,
        delivery_method=delivery_method,
        payment_method=payment_method,
        customer_name=customer_name,
        customer_email=customer_email,
        customer_phone=customer_phone,
        sent_to_1c=sent_to_1c,
        status=status,
    )

    if variants_with_vat is None:
        variants_with_vat = []

    if not variants_with_vat:
        raise ValueError("variants_with_vat не может быть пустым — нужен хотя бы один (variant, vat_rate)")

    # Проверка на дублирование variant в одной VAT-группе (по pk, не по id() объекта)
    seen: set[tuple] = set()
    for variant, vat_rate in variants_with_vat:
        key = (variant.pk, vat_rate)
        if key in seen:
            raise ValueError(
                f"Variant pk={variant.pk} дублируется для vat_rate={vat_rate} — нарушает OrderItem unique constraint"
            )
        seen.add(key)

    groups: "dict[Decimal | None, list[ProductVariant]]" = defaultdict(list)
    total = Decimal("0")
    for variant, vat_rate in variants_with_vat:
        groups[vat_rate].append(variant)
        total += variant.retail_price

    master = Order.objects.create(
        **common,
        is_master=True,
        total_amount=total if total > 0 else Decimal("0.00"),
    )

    subs = []
    for vat_rate, variants in groups.items():
        sub_total = sum(v.retail_price for v in variants)
        sub = Order.objects.create(
            **common,
            is_master=False,
            parent_order=master,
            vat_group=vat_rate,
            total_amount=sub_total,
        )
        for variant in variants:
            OrderItem.objects.create(
                order=sub,
                product=variant.product,
                variant=variant,
                quantity=1,
                unit_price=variant.retail_price,
                total_price=variant.retail_price,
                product_name=variant.product.name,
                product_sku=variant.sku,
                vat_rate=vat_rate,
            )
        subs.append(sub)

    return master, subs


def create_single_sub_order(
    user: "User | None" = None,
    variant: "ProductVariant | None" = None,
    vat_rate: "Decimal | None" = None,
    **order_kwargs,
) -> "tuple[Order, Order]":
    """Shortcut: 1 master + 1 sub с одним OrderItem.

    Returns:
        (master, sub) — оба как отдельные объекты Order.
    """
    if variant is None:
        from tests.conftest import ProductVariantFactory
        variant = ProductVariantFactory.create()
    assert variant is not None

    master, subs = create_master_with_subs(
        user=user,
        variants_with_vat=[(variant, vat_rate)],
        **order_kwargs,
    )
    return master, subs[0]


def build_test_xml_for_sub(
    sub_order: Order,
    status_1c: str = "Отгружен",
    paid_date: "str | None" = None,
    shipped_date: "str | None" = None,
) -> str:
    """Генерирует XML с <Ід>order-{sub.id}</Ід> для субзаказа.

    Args:
        sub_order: субзаказ (is_master=False).
        status_1c: статус в формате 1С (русскими словами).
        paid_date: дата оплаты (YYYY-MM-DD или None).
        shipped_date: дата отгрузки (YYYY-MM-DD или None).

    Returns:
        XML-строка в формате CommerceML 3.1.
    """
    requisites = f"""
        <ЗначениеРеквизита>
            <Наименование>СтатусЗаказа</Наименование>
            <Значение>{status_1c}</Значение>
        </ЗначениеРеквизита>
    """
    if paid_date:
        requisites += f"""
        <ЗначениеРеквизита>
            <Наименование>ДатаОплаты</Наименование>
            <Значение>{paid_date}</Значение>
        </ЗначениеРеквизита>
        """
    if shipped_date:
        requisites += f"""
        <ЗначениеРеквизита>
            <Наименование>ДатаОтгрузки</Наименование>
            <Значение>{shipped_date}</Значение>
        </ЗначениеРеквизита>
        """

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-02T12:00:00">
    <Контейнер>
        <Документ>
            <Ид>order-{sub_order.pk}</Ид>
            <Номер>{sub_order.order_number}</Номер>
            <Дата>2026-02-02</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                {requisites}
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""

"""
Story 5.3: Интеграционные тесты полного цикла импорта статусов.

Тесты покрывают полный E2E цикл 1С:
checkauth -> query -> success -> file (orders.xml).

Updated for Story 34-3: handle_query exports only sub-orders
(is_master=False, parent_order__isnull=False). _create_order_with_item
now creates master + sub-order structure.
"""

from __future__ import annotations

from datetime import date
from typing import cast

import pytest
from django.utils import timezone
from rest_framework.response import Response
from rest_framework.test import APIClient

from apps.orders.models import Order
from tests.conftest import OrderFactory, OrderItemFactory, ProductVariantFactory, UserFactory
from tests.helpers import create_master_with_subs
from tests.utils import EXCHANGE_URL, ONEC_PASSWORD
from tests.utils import build_orders_xml as _build_orders_xml
from tests.utils import parse_commerceml_response, perform_1c_checkauth

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


@pytest.fixture
def log_dir(tmp_path, settings):
    """Override EXCHANGE_LOG_DIR -> tmp_path to isolate logs."""
    private_log = tmp_path / "var" / "1c_exchange" / "logs"
    settings.EXCHANGE_LOG_DIR = str(private_log)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return private_log


@pytest.fixture
def onec_user(db):
    """Staff user for 1C exchange."""
    return UserFactory.create(is_staff=True, password=ONEC_PASSWORD)


@pytest.fixture
def auth_client(onec_user) -> APIClient:
    """Authenticated APIClient after checkauth."""
    client = APIClient()
    return perform_1c_checkauth(client, onec_user.email, ONEC_PASSWORD)


def _post_orders_xml(auth_client: APIClient, xml_data: bytes) -> Response:
    return cast(
        Response,
        auth_client.post(
            f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
            data=xml_data,
            content_type="application/xml",
            CONTENT_LENGTH=str(len(xml_data)),
        ),
    )


def _get_exchange(auth_client: APIClient, mode: str) -> Response:
    return cast(Response, auth_client.get(EXCHANGE_URL, data={"mode": mode}))


def _create_order_with_item(
    *,
    status: str = "pending",
    sent_to_1c: bool = False,
) -> Order:
    """Create master + sub-order + OrderItem for E2E import tests.

    Returns the sub-order (is_master=False), which is the one exported to 1C
    and the one that receives status updates from 1C.
    """
    variant = ProductVariantFactory.create()
    master = Order.objects.create(
        status=status,
        sent_to_1c=False,
        is_master=True,
        total_amount=variant.retail_price,
        delivery_address="ул. Тестовая, 1",
        delivery_method="courier",
        payment_method="card",
    )
    sub = Order.objects.create(
        status=status,
        sent_to_1c=sent_to_1c,
        is_master=False,
        parent_order=master,
        total_amount=variant.retail_price,
        delivery_address="ул. Тестовая, 1",
        delivery_method="courier",
        payment_method="card",
    )
    sub.order_number = f"order-{sub.pk}"
    sub.save(update_fields=["order_number"])
    OrderItemFactory.create(
        order=sub,
        product=variant.product,
        variant=variant,
        product_name=variant.product.name,
        unit_price=variant.retail_price,
        quantity=1,
        total_price=variant.retail_price,
    )
    return sub


def test_full_cycle_export_then_import_updates_status(auth_client, log_dir, db):
    """AC1: export -> success -> import updates shipped status on sub-order."""
    # ARRANGE
    sub = _create_order_with_item()

    # ACT — export query
    resp_query = _get_exchange(auth_client, "query")
    assert resp_query.status_code == 200
    root = parse_commerceml_response(resp_query)
    documents = root.findall(".//Документ")
    assert any(
        doc.findtext("Номер") == sub.order_number for doc in documents
    ), "Exported XML must include the target sub-order"

    # ACT — export success
    resp_success = _get_exchange(auth_client, "success")
    assert resp_success.status_code == 200

    sub.refresh_from_db()
    assert sub.sent_to_1c is True

    xml_data = _build_orders_xml(
        order_id=f"order-{sub.pk}",
        order_number=f"order-{sub.pk}",
        status_1c="Отгружен",
    )

    # ACT — import orders.xml
    resp_file = _post_orders_xml(auth_client, xml_data)
    assert resp_file.status_code == 200
    assert resp_file.content.decode("utf-8").startswith("success")

    # ASSERT
    sub.refresh_from_db()
    assert sub.status == "shipped"
    assert sub.status_1c == "Отгружен"
    assert sub.sent_to_1c is True


@pytest.mark.parametrize(
    "status_1c, expected_status",
    [
        ("ОжидаетОбработки", "processing"),
        ("Отгружен", "shipped"),
        ("Доставлен", "delivered"),
        ("Отменен", "cancelled"),
    ],
)
def test_status_mapping_from_1c(auth_client, log_dir, db, status_1c, expected_status):
    """AC2: 1C status mapping for processing/shipped/delivered/cancelled."""
    # ARRANGE
    sub = _create_order_with_item()
    xml_data = _build_orders_xml(
        order_id=f"order-{sub.pk}",
        order_number=f"order-{sub.pk}",
        status_1c=status_1c,
    )

    # ACT
    response = _post_orders_xml(auth_client, xml_data)
    assert response.status_code == 200
    assert response.content.decode("utf-8").startswith("success")

    # ASSERT
    sub.refresh_from_db()
    assert sub.status == expected_status
    assert sub.status_1c == status_1c


def test_dates_extracted_from_requisites(auth_client, log_dir, db):
    """AC3: paid_at/shipped_at extracted from requisites."""
    # ARRANGE
    sub = _create_order_with_item()
    xml_data = _build_orders_xml(
        order_id=f"order-{sub.pk}",
        order_number=f"order-{sub.pk}",
        status_1c="Отгружен",
        paid_date="2026-02-01",
        shipped_date="2026-02-02",
    )

    # ACT
    response = _post_orders_xml(auth_client, xml_data)
    assert response.status_code == 200
    assert response.content.decode("utf-8").startswith("success")

    # ASSERT
    sub.refresh_from_db()
    assert sub.paid_at is not None
    assert timezone.localdate(sub.paid_at) == date(2026, 2, 1)
    assert sub.shipped_at is not None
    assert timezone.localdate(sub.shipped_at) == date(2026, 2, 2)


def test_invalid_xml_returns_failure(auth_client, log_dir, db):
    """AC4: invalid XML returns failure."""
    # ARRANGE
    xml_data = b"<not valid xml!!!"

    # ACT
    response = _post_orders_xml(auth_client, xml_data)

    # ASSERT
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert content.startswith("failure")
    assert "Malformed XML" in content


def test_unknown_order_returns_failure(auth_client, log_dir, db):
    """AC4: unknown order returns failure and no updates."""
    # ARRANGE
    existing_sub = _create_order_with_item()
    missing_id = existing_sub.pk + 9999
    xml_data = _build_orders_xml(
        order_id=f"order-{missing_id}",
        order_number=f"order-{missing_id}",
        status_1c="Отгружен",
    )

    # ACT
    response = _post_orders_xml(auth_client, xml_data)

    # ASSERT
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert content.startswith("failure")
    existing_sub.refresh_from_db()
    assert existing_sub.status == "pending"
    assert existing_sub.sent_to_1c is False


# =============================================================================
# Story 34-5: Cross-epic E2E тест полного VAT-split цикла экспорт→импорт
# =============================================================================


def _build_multi_orders_xml(subs_data: list[dict]) -> bytes:
    """Строит XML с несколькими документами для batch-импорта."""
    from django.utils import timezone as tz

    now_str = tz.now().strftime("%Y-%m-%dT%H:%M:%S")
    containers = []
    for sd in subs_data:
        containers.append(
            f"""
    <Контейнер>
        <Документ>
            <Ид>{sd['order_id']}</Ид>
            <Номер>{sd['order_number']}</Номер>
            <Дата>{now_str[:10]}</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>{sd['status_1c']}</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>"""
        )
    xml_str = f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="{now_str}">
    {''.join(containers)}
</КоммерческаяИнформация>
"""
    return xml_str.encode("utf-8")


def test_full_vat_split_export_import_cycle(auth_client, log_dir, db, settings):
    """Cross-epic E2E: VAT-split master+subs полный цикл (Story 34-5, AC5).

    Покрывает:
    - Экспорт двух sub-orders с разными vat_group (5 и 22)
    - mode=query → XML содержит ровно 2 документа с разными организациями
    - mode=success → оба субзаказа и master помечены sent_to_1c=True
    - POST orders.xml с разными статусами для каждого субзаказа
    - sub1.status='shipped', sub2.status='confirmed'
    - master.status агрегирован по правилу min-priority → 'confirmed'
    """
    from decimal import Decimal

    settings.ONEC_EXCHANGE = {
        **getattr(settings, "ONEC_EXCHANGE", {}),
        "ORGANIZATION_BY_VAT": {
            22: {"name": "ИП Семерюк Д.В.", "warehouse": "1 СДВ склад"},
            5: {"name": "ИП Терещенко Л.В.", "warehouse": "2 ТЛВ склад"},
        },
    }

    # ARRANGE — master + 2 subs с разными VAT-группами (через shared helper AC6)
    variant1 = ProductVariantFactory.create(retail_price=Decimal("1000.00"))
    variant2 = ProductVariantFactory.create(retail_price=Decimal("2000.00"))

    master, subs = create_master_with_subs(
        variants_with_vat=[
            (variant1, Decimal("5.00")),
            (variant2, Decimal("22.00")),
        ],
        status="pending",
        sent_to_1c=False,
    )
    sub1, sub2 = subs

    # Устанавливаем order_number для XML-ссылок
    sub1.order_number = f"order-{sub1.pk}"
    sub1.save(update_fields=["order_number"])
    sub2.order_number = f"order-{sub2.pk}"
    sub2.save(update_fields=["order_number"])

    # ACT 1 — экспорт: mode=query
    resp_query = _get_exchange(auth_client, "query")
    assert resp_query.status_code == 200
    root = parse_commerceml_response(resp_query)
    documents = root.findall(".//Документ")
    assert len(documents) == 2, f"Ожидали ровно 2 документа, получили {len(documents)}"
    exported_numbers = {doc.findtext("Номер") for doc in documents}
    assert sub1.order_number in exported_numbers, "sub1 должен быть в экспорте"
    assert sub2.order_number in exported_numbers, "sub2 должен быть в экспорте"

    # Проверяем организации по vat_group (AC5: разные org для vat=5 и vat=22)
    org_by_number = {doc.findtext("Номер"): doc.findtext("Организация") for doc in documents}
    assert org_by_number[sub1.order_number] == "ИП Терещенко Л.В.", (
        f"sub1 (vat_group=5): ожидали 'ИП Терещенко Л.В.', получили {org_by_number[sub1.order_number]!r}"
    )
    assert org_by_number[sub2.order_number] == "ИП Семерюк Д.В.", (
        f"sub2 (vat_group=22): ожидали 'ИП Семерюк Д.В.', получили {org_by_number[sub2.order_number]!r}"
    )

    # Проверяем склады по vat_group (AC5: ORGANIZATION_BY_VAT задаёт и Склад)
    warehouse_by_number = {doc.findtext("Номер"): doc.findtext("Склад") for doc in documents}
    assert warehouse_by_number[sub1.order_number] == "2 ТЛВ склад", (
        f"sub1 (vat_group=5): ожидали '2 ТЛВ склад', получили {warehouse_by_number[sub1.order_number]!r}"
    )
    assert warehouse_by_number[sub2.order_number] == "1 СДВ склад", (
        f"sub2 (vat_group=22): ожидали '1 СДВ склад', получили {warehouse_by_number[sub2.order_number]!r}"
    )

    # ACT 2 — mode=success: помечаем как отправленные
    resp_success = _get_exchange(auth_client, "success")
    assert resp_success.status_code == 200

    sub1.refresh_from_db()
    sub2.refresh_from_db()
    master.refresh_from_db()
    assert sub1.sent_to_1c is True
    assert sub2.sent_to_1c is True
    assert master.sent_to_1c is True, "master должен быть помечен sent_to_1c=True после того, как все sub отправлены"
    assert master.sent_to_1c_at is not None, "master.sent_to_1c_at должен быть заполнен"

    # ACT 3 — импорт: POST orders.xml с разными статусами
    xml_data = _build_multi_orders_xml([
        {
            "order_id": f"order-{sub1.pk}",
            "order_number": sub1.order_number,
            "status_1c": "Отгружен",
        },
        {
            "order_id": f"order-{sub2.pk}",
            "order_number": sub2.order_number,
            "status_1c": "Подтвержден",
        },
    ])
    resp_import = _post_orders_xml(auth_client, xml_data)
    assert resp_import.status_code == 200
    assert resp_import.content.decode("utf-8").startswith("success")

    # ASSERT — субзаказы обновлены
    sub1.refresh_from_db()
    sub2.refresh_from_db()
    assert sub1.status == "shipped", f"sub1.status={sub1.status!r}, ожидали 'shipped'"
    assert sub2.status == "confirmed", f"sub2.status={sub2.status!r}, ожидали 'confirmed'"

    # ASSERT — мастер агрегирован (min-priority: confirmed(2) < shipped(4))
    master.refresh_from_db()
    assert master.status == "confirmed", (
        f"master.status={master.status!r}, ожидали 'confirmed' (min-priority агрегация)"
    )

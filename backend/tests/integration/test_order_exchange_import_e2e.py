"""
Story 5.3: Интеграционные тесты полного цикла импорта статусов.

Тесты покрывают полный E2E цикл 1С:
checkauth -> query -> success -> file (orders.xml).
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


def _align_order_number_with_id(order: Order) -> Order:
    order.order_number = f"order-{order.pk}"
    order.save(update_fields=["order_number"])
    return order


def _create_order_with_item(
    *,
    status: str = "pending",
    sent_to_1c: bool = False,
) -> Order:
    variant = ProductVariantFactory.create()
    order = OrderFactory.create(
        status=status,
        sent_to_1c=sent_to_1c,
    )
    order = _align_order_number_with_id(order)
    OrderItemFactory.create(
        order=order,
        product=variant.product,
        variant=variant,
        product_name=variant.product.name,
        unit_price=variant.retail_price,
        quantity=1,
        total_price=variant.retail_price,
    )
    return order


def test_full_cycle_export_then_import_updates_status(auth_client, log_dir, db):
    """AC1: export -> success -> import updates shipped status."""
    # ARRANGE
    order = _create_order_with_item()

    # ACT — export query
    resp_query = _get_exchange(auth_client, "query")
    assert resp_query.status_code == 200
    root = parse_commerceml_response(resp_query)
    documents = root.findall(".//Документ")
    assert any(
        doc.findtext("Номер") == order.order_number for doc in documents
    ), "Exported XML must include the target order"

    # ACT — export success
    resp_success = _get_exchange(auth_client, "success")
    assert resp_success.status_code == 200

    order.refresh_from_db()
    assert order.sent_to_1c is True

    xml_data = _build_orders_xml(
        order_id=f"order-{order.pk}",
        order_number=f"order-{order.pk}",
        status_1c="Отгружен",
    )

    # ACT — import orders.xml
    resp_file = _post_orders_xml(auth_client, xml_data)
    assert resp_file.status_code == 200
    assert resp_file.content.decode("utf-8").startswith("success")

    # ASSERT
    order.refresh_from_db()
    assert order.status == "shipped"
    assert order.status_1c == "Отгружен"
    assert order.sent_to_1c is True


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
    order = _create_order_with_item()
    xml_data = _build_orders_xml(
        order_id=f"order-{order.pk}",
        order_number=f"order-{order.pk}",
        status_1c=status_1c,
    )

    # ACT
    response = _post_orders_xml(auth_client, xml_data)
    assert response.status_code == 200
    assert response.content.decode("utf-8").startswith("success")

    # ASSERT
    order.refresh_from_db()
    assert order.status == expected_status
    assert order.status_1c == status_1c
    assert order.sent_to_1c is True


def test_dates_extracted_from_requisites(auth_client, log_dir, db):
    """AC3: paid_at/shipped_at extracted from requisites."""
    # ARRANGE
    order = _create_order_with_item()
    xml_data = _build_orders_xml(
        order_id=f"order-{order.pk}",
        order_number=f"order-{order.pk}",
        status_1c="Отгружен",
        paid_date="2026-02-01",
        shipped_date="2026-02-02",
    )

    # ACT
    response = _post_orders_xml(auth_client, xml_data)
    assert response.status_code == 200
    assert response.content.decode("utf-8").startswith("success")

    # ASSERT
    order.refresh_from_db()
    assert order.paid_at is not None
    assert timezone.localdate(order.paid_at) == date(2026, 2, 1)
    assert order.shipped_at is not None
    assert timezone.localdate(order.shipped_at) == date(2026, 2, 2)


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
    existing_order = _create_order_with_item()
    missing_id = existing_order.pk + 9999
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
    existing_order.refresh_from_db()
    assert existing_order.status == "pending"
    assert existing_order.sent_to_1c is False

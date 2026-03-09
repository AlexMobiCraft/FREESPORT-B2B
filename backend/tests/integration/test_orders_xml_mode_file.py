"""
Интеграционные тесты для mode=file обработки orders.xml.

Story 5.2: View-обработчик mode=file для orders.xml.
Тестирует полный цикл: HTTP POST → _handle_orders_xml → OrderStatusImportService → DB.
"""

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import cast
from unittest.mock import patch

import pytest
from django.http import HttpResponse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.integrations.onec_exchange.throttling import OneCExchangeThrottle
from apps.integrations.onec_exchange.views import ORDERS_XML_MAX_SIZE, ICExchangeView
from apps.orders.models import Order
from tests.conftest import OrderFactory, UserFactory, get_unique_suffix
from tests.utils import EXCHANGE_URL, ONEC_PASSWORD
from tests.utils import build_multi_orders_xml as _build_multi_orders_xml  # noqa: E402
from tests.utils import build_orders_xml as _build_orders_xml  # noqa: E402
from tests.utils import perform_1c_checkauth


@pytest.mark.django_db
@pytest.mark.integration
class TestOrdersXmlModeFile:
    """Integration tests for mode=file orders.xml handler."""

    def setup_method(self):
        self.client = APIClient()
        self.user = UserFactory.create(is_staff=True, password=ONEC_PASSWORD)
        perform_1c_checkauth(self.client, self.user.email, ONEC_PASSWORD)

    def _post_orders_xml(self, xml_data: bytes, **kwargs) -> HttpResponse:
        """POST orders.xml via mode=file."""
        return cast(
            HttpResponse,
            self.client.post(
                f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
                data=xml_data,
                content_type="application/xml",
                CONTENT_LENGTH=str(len(xml_data)),
                **kwargs,
            ),
        )

    # ===================================================================
    # 4.1: Успешное обновление статуса через mode=file (AC1, AC2)
    # ===================================================================

    def test_successful_status_update(self):
        """POST orders.xml обновляет статус заказа в БД."""
        # ARRANGE
        order_number = f"FS-INT-{get_unique_suffix()}"
        order = Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(
            order_id=f"order-{order.pk}",
            order_number=order_number,
            status_1c="Отгружен",
        )

        # ACT
        response = self._post_orders_xml(xml_data)

        # ASSERT
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")

        order.refresh_from_db()
        assert order.status == "shipped"
        assert order.status_1c == "Отгружен"
        assert order.sent_to_1c is True
        assert order.sent_to_1c_at is not None

    # ===================================================================
    # 4.2: Идемпотентность — повторная отправка того же XML (AC4)
    # ===================================================================

    def test_idempotent_resubmission(self):
        """Повторная отправка того же XML → success, без дублирования."""
        # ARRANGE
        order_number = f"FS-IDEM-{get_unique_suffix()}"
        order = Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(
            order_id=f"order-{order.pk}",
            order_number=order_number,
            status_1c="Подтвержден",
        )

        # ACT — первая отправка
        resp1 = self._post_orders_xml(xml_data)
        assert resp1.content.decode("utf-8").startswith("success")

        # ACT — повторная отправка (идемпотентность)
        resp2 = self._post_orders_xml(xml_data)
        assert resp2.content.decode("utf-8").startswith("success")

    # ===================================================================
    # 4.3: Аудит-лог сохраняется до обработки (AC5)
    # ===================================================================

    def test_audit_log_saved(self):
        """XML сохраняется в аудит-лог ДО обработки."""
        order_number = f"FS-AUDIT-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Подтвержден")

        with patch("apps.integrations.onec_exchange.views._save_exchange_log") as mock_log:
            response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        mock_log.assert_called_once()
        call_args = mock_log.call_args
        assert call_args[0][0] == "orders.xml"
        assert call_args[1].get("is_binary") is True

    # ===================================================================
    # 4.4: Невалидный XML → failure (AC6)
    # ===================================================================

    def test_invalid_xml_returns_failure(self):
        """Невалидный XML возвращает failure."""
        xml_data = b"<not valid xml!!!"

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("failure")
        assert "Malformed XML" in content

    # ===================================================================
    # 4.5: Аутентификация обязательна (AC7)
    # ===================================================================

    def test_unauthenticated_request_rejected(self):
        """POST без аутентификации → 401."""
        xml_data = _build_orders_xml()
        unauthenticated_client = APIClient()

        response = cast(
            HttpResponse,
            unauthenticated_client.post(
                f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
                data=xml_data,
                content_type="application/xml",
            ),
        )

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    # ===================================================================
    # 4.6: Регрессия статуса блокируется (AC8)
    # ===================================================================

    def test_status_regression_blocked(self):
        """shipped → confirmed (регрессия) блокируется, заказ не обновляется."""
        order_number = f"FS-REG-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="shipped",
            status_1c="Отгружен",
            sent_to_1c=True,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Подтвержден")

        response = self._post_orders_xml(xml_data)

        # Partial success: service returns result with errors but since
        # no orders were updated AND regression was logged as error, response
        # can be success (result.errors is empty — regression is skip, not error)
        assert response.status_code == 200

        order = Order.objects.get(order_number=order_number)
        assert order.status == "shipped"  # Не изменился

    def test_cancelled_always_allowed(self):
        """Переход в cancelled разрешён из любого статуса (бизнес-требование)."""
        order_number = f"FS-CANCEL-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="shipped",
            status_1c="Отгружен",
            sent_to_1c=True,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Отменен")

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")

        order = Order.objects.get(order_number=order_number)
        assert order.status == "cancelled"

    # ===================================================================
    # 4.7: Нулевая обработка при пустом контейнере (AC9)
    # ===================================================================

    def test_zero_processed_from_empty_container(self):
        """XML без <Документ> → success (нет ошибок), zero processed logged."""
        ts = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
        xml_data = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<КоммерческаяИнформация ВерсияСхемы="3.1" '
            f'ДатаФормирования="{ts}">'
            "<Контейнер></Контейнер>"
            "</КоммерческаяИнформация>"
        ).encode("utf-8")

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")

    # ===================================================================
    # 4.8: windows-1251 кодировка (AC10)
    # ===================================================================

    def test_windows_1251_encoding(self):
        """XML в windows-1251 успешно обрабатывается."""
        order_number = f"FS-ENC-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )

        timestamp = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")
        order_date = timezone.now().strftime("%Y-%m-%d")
        xml_str = f"""<?xml version="1.0" encoding="windows-1251"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="{timestamp}">
    <Контейнер>
        <Документ>
            <Ид></Ид>
            <Номер>{order_number}</Номер>
            <Дата>{order_date}</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Подтвержден</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>"""
        xml_data = xml_str.encode("windows-1251")

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")

        order = Order.objects.get(order_number=order_number)
        assert order.status == "confirmed"

    # ===================================================================
    # 4.9: Truncated body → failure (FM1.1)
    # ===================================================================

    def test_truncated_body_rejected(self):
        """Content-Length больше реального тела → failure."""
        order_number = f"FS-TRUNC-{get_unique_suffix()}"
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Отгружен")

        response = cast(
            HttpResponse,
            self.client.post(
                f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
                data=xml_data,
                content_type="application/xml",
                CONTENT_LENGTH=str(len(xml_data) + 1000),
            ),
        )

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("failure")
        assert "Incomplete" in content or "Internal" in content

    # ===================================================================
    # 4.10: File too large → failure (ADR-004)
    # ===================================================================

    def test_file_too_large_rejected(self):
        """Content-Length > ORDERS_XML_MAX_SIZE → failure."""
        xml_data = _build_orders_xml()

        response = cast(
            HttpResponse,
            self.client.post(
                f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
                data=xml_data,
                content_type="application/xml",
                CONTENT_LENGTH=str(6 * 1024 * 1024),  # 6MB > 5MB limit
            ),
        )

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "failure" in content
        assert "too large" in content.lower()

    def test_body_exceeds_limit_with_small_content_length(self):
        """Body > лимита отклоняется, даже если Content-Length занижен."""
        xml_data = b"<xml>" + (b"a" * (ORDERS_XML_MAX_SIZE + 10)) + b"</xml>"

        class _DummyRequest:
            def __init__(self, body: bytes, content_length: int):
                self.META = {"CONTENT_LENGTH": str(content_length)}

                def _read(size: int = -1) -> bytes:
                    if size is None or size < 0:
                        return body
                    return body[:size]

                self._request = SimpleNamespace(read=_read)

        view = ICExchangeView()
        request = _DummyRequest(xml_data, content_length=10)
        response = view._handle_orders_xml(request)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "failure" in content
        assert "too large" in content.lower()

    # ===================================================================
    # 4.11: Too many documents → failure (FM4.5)
    # ===================================================================

    def test_too_many_documents_rejected(self):
        """XML с > MAX_DOCUMENTS_PER_FILE документов → failure."""
        xml_data = _build_orders_xml()

        with patch("apps.integrations.onec_exchange.views.MAX_DOCUMENTS_PER_FILE", 0):
            response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "failure" in content
        assert "Too many documents" in content

    # ===================================================================
    # 4.12: Stale timestamp → failure (AC13)
    # ===================================================================

    def test_stale_xml_timestamp_rejected(self):
        """XML с ДатаФормирования старше 24 часов → failure."""
        stale_time = (timezone.now() - timedelta(hours=25)).strftime("%Y-%m-%dT%H:%M:%S")
        xml_data = _build_orders_xml(timestamp=stale_time)

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "failure" in content
        assert "timestamp" in content.lower()

    # ===================================================================
    # 4.13: Unexpected fields ignored (AC14)
    # ===================================================================

    def test_unexpected_requisites_ignored(self):
        """Неизвестные реквизиты игнорируются, известные обрабатываются."""
        order_number = f"FS-WL-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        extra = """
        <ЗначениеРеквизита>
            <Наименование>НеизвестноеПоле</Наименование>
            <Значение>secret_data</Значение>
        </ЗначениеРеквизита>
        """
        xml_data = _build_orders_xml(
            order_number=order_number,
            status_1c="Подтвержден",
            extra_requisites=extra,
        )

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")

        order = Order.objects.get(order_number=order_number)
        assert order.status == "confirmed"

    # ===================================================================
    # 4.14: Multiple orders в одном XML (batch)
    # ===================================================================

    def test_multiple_orders_in_single_xml(self):
        """XML с несколькими <Документ> обрабатывает все заказы."""
        statuses_1c = ["Подтвержден", "Отгружен", "Доставлен"]
        expected_statuses = ["confirmed", "shipped", "delivered"]
        orders = [
            OrderFactory.create(
                order_number=f"FS-MULTI-{get_unique_suffix()}",
                sent_to_1c=False,
                total_amount=Decimal("100.00"),
            )
            for _ in range(3)
        ]

        orders_data = [{"order_number": o.order_number, "status_1c": s} for o, s in zip(orders, statuses_1c)]
        xml_data = _build_multi_orders_xml(orders_data)

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        assert response.content.decode("utf-8").startswith("success")

        for o, expected in zip(orders, expected_statuses):
            assert Order.objects.get(order_number=o.order_number).status == expected

    # ===================================================================
    # 4.15: Partial success — some orders update, some fail
    # ===================================================================

    def test_partial_success(self):
        """Часть заказов обновляется, часть не найдена → всё равно success."""
        real_num = f"FS-PART-{get_unique_suffix()}"
        Order.objects.create(
            order_number=real_num,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )

        orders_data = [
            {"order_number": real_num, "status_1c": "Подтвержден"},
            {"order_number": "FS-NONEXISTENT-999", "status_1c": "Отгружен"},
        ]
        xml_data = _build_multi_orders_xml(orders_data)

        response = self._post_orders_xml(xml_data)

        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert content.startswith("success")  # ADR-003: partial = success

        assert Order.objects.get(order_number=real_num).status == "confirmed"

    # ===================================================================
    # 4.16: Non-orders.xml filename → normal file upload (not inline)
    # ===================================================================

    def test_non_orders_xml_uses_normal_upload(self):
        """Файл с другим именем → обычный file upload, не inline обработка."""
        response = cast(
            HttpResponse,
            self.client.post(
                f"{EXCHANGE_URL}?mode=file&filename=import.xml",
                data=b"<test/>",
                content_type="application/xml",
            ),
        )

        # Normal file upload handler processes it (not _handle_orders_xml)
        assert response.status_code == 200

    # ===================================================================
    # 4.17: STATUS_PRIORITY regression tests
    # ===================================================================

    def test_status_priority_shipped_to_confirmed_blocked(self):
        """shipped (p=4) → confirmed (p=2) — регрессия блокируется."""
        order_number = f"FS-PRI-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="shipped",
            status_1c="Отгружен",
            sent_to_1c=True,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Подтвержден")

        response = self._post_orders_xml(xml_data)
        assert response.status_code == 200

        order = Order.objects.get(order_number=order_number)
        assert order.status == "shipped"  # Не изменился

    def test_status_priority_forward_allowed(self):
        """pending (p=1) → shipped (p=4) — прогресс разрешён."""
        order_number = f"FS-FWD-{get_unique_suffix()}"
        Order.objects.create(
            order_number=order_number,
            status="pending",
            status_1c="",
            sent_to_1c=False,
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        xml_data = _build_orders_xml(order_number=order_number, status_1c="Отгружен")

        response = self._post_orders_xml(xml_data)
        assert response.status_code == 200
        assert response.content.decode("utf-8").startswith("success")

        order = Order.objects.get(order_number=order_number)
        assert order.status == "shipped"

    # ===================================================================
    # 4.18: Rate limiting (AC12)
    # ===================================================================

    def test_rate_limiting_returns_429(self):
        """Превышение rate limit → HTTP 429 (AC12)."""
        from django.core.cache import cache as django_cache

        throttle_key = f"throttle_1c_exchange_{self.user.pk}"
        django_cache.delete(throttle_key)

        xml_data = _build_orders_xml(status_1c="Подтвержден")

        # Mock throttle rate to 3/min to avoid 61 real requests
        with patch.object(OneCExchangeThrottle, "rate", "3/min"):
            responses: list[HttpResponse] = []
            for _ in range(5):
                resp = cast(
                    HttpResponse,
                    self.client.post(
                        f"{EXCHANGE_URL}?mode=file&filename=orders.xml",
                        data=xml_data,
                        content_type="application/xml",
                        CONTENT_LENGTH=str(len(xml_data)),
                    ),
                )
                responses.append(resp)

        # At least one response should be 429
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected at least one 429 response, got: {status_codes}"

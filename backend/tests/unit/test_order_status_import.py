"""
Unit-тесты для OrderStatusImportService.

Тесты для Story 5.1: Сервис импорта статусов (OrderStatusImportService)
Покрывают AC1-AC9.
"""

import logging
from datetime import date, timedelta
from typing import cast
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from defusedxml import ElementTree as ET
from defusedxml.common import DefusedXmlException
from django.db import OperationalError
from django.test.utils import override_settings
from django.utils import timezone

from apps.orders.constants import MAX_ERRORS, ORDER_ID_PREFIX, STATUS_MAPPING, STATUS_MAPPING_LOWER, ProcessingStatus
from apps.orders.models import Order
from apps.orders.services.order_status_import import ImportResult, OrderStatusImportService, OrderUpdateData
from tests.conftest import get_unique_suffix

pytestmark = pytest.mark.django_db


# =============================================================================
# Helper Functions
# =============================================================================


def build_test_xml(
    order_id: str = "order-123",
    order_number: str = "FS-TEST-001",
    status: str = "Отгружен",
    paid_date: str | None = None,
    shipped_date: str | None = None,
) -> str:
    """Генерирует тестовый XML в формате CommerceML 3.1."""
    requisites = f"""
        <ЗначениеРеквизита>
            <Наименование>СтатусЗаказа</Наименование>
            <Значение>{status}</Значение>
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
            <Ид>{order_id}</Ид>
            <Номер>{order_number}</Номер>
            <Дата>2026-02-02</Дата>
            <ХозОперация>Заказ товара</ХозОперация>
            <ЗначенияРеквизитов>
                {requisites}
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""


def build_multi_order_xml(orders: list[dict]) -> str:
    """Генерирует XML с несколькими заказами."""
    containers = []
    for order in orders:
        order_id = order.get("order_id", "order-1")
        order_number = order.get("order_number", "FS-TEST")
        status = order.get("status", "Отгружен")

        containers.append(
            f"""
        <Контейнер>
            <Документ>
                <Ид>{order_id}</Ид>
                <Номер>{order_number}</Номер>
                <Дата>2026-02-02</Дата>
                <ХозОперация>Заказ товара</ХозОперация>
                <ЗначенияРеквизитов>
                    <ЗначениеРеквизита>
                        <Наименование>СтатусЗаказа</Наименование>
                        <Значение>{status}</Значение>
                    </ЗначениеРеквизита>
                </ЗначенияРеквизитов>
            </Документ>
        </Контейнер>
        """
        )

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-02T12:00:00">
    {''.join(containers)}
</КоммерческаяИнформация>
"""


# =============================================================================
# Test Classes
# =============================================================================


@pytest.mark.unit
class TestStatusMapping:
    """Тесты маппинга статусов 1С → FREESPORT (AC3)."""

    def test_status_mapping_all_statuses(self):
        """AC9 4.3: Проверка всех 6 статусов маппинга."""
        # ARRANGE / ACT / ASSERT
        expected_mappings = {
            "ОжидаетОбработки": "processing",
            "Подтвержден": "confirmed",
            "Отгружен": "shipped",
            "Доставлен": "delivered",
            "Отменен": "cancelled",
            "Возвращен": "refunded",
        }

        for status_1c, status_freesport in expected_mappings.items():
            assert (
                STATUS_MAPPING.get(status_1c) == status_freesport
            ), f"Mapping mismatch: {status_1c} should map to {status_freesport}"

    def test_status_mapping_count(self):
        """Проверка количества статусов в маппинге."""
        assert len(STATUS_MAPPING) == 6


@pytest.mark.unit
class TestOrderUpdateData:
    """Тесты dataclass OrderUpdateData."""

    def test_order_update_data_creation(self):
        """Проверка создания OrderUpdateData."""
        # ARRANGE
        data = OrderUpdateData(
            order_id="order-123",
            order_number="FS-TEST-001",
            status_1c="Отгружен",
            paid_at=None,
            shipped_at=None,
        )

        # ASSERT
        assert data.order_id == "order-123"
        assert data.order_number == "FS-TEST-001"
        assert data.status_1c == "Отгружен"
        assert data.paid_at is None
        assert data.shipped_at is None


@pytest.mark.unit
class TestImportResult:
    """Тесты dataclass ImportResult."""

    def test_import_result_defaults(self):
        """Проверка дефолтных значений ImportResult."""
        # ARRANGE / ACT
        result = ImportResult()

        # ASSERT
        assert result.processed == 0
        assert result.updated == 0
        assert result.skipped_up_to_date == 0
        assert result.skipped_unknown_status == 0
        assert result.skipped_data_conflict == 0
        assert result.skipped_status_regression == 0
        assert result.skipped_invalid == 0
        assert result.not_found == 0
        assert result.errors == []


@pytest.mark.unit
class TestXMLParsing:
    """Тесты парсинга XML (AC1)."""

    def test_parse_valid_xml_extracts_order_data(self):
        """AC9 4.2: Парсинг валидного XML."""
        # ARRANGE
        order_number = f"FS-{get_unique_suffix()}"
        xml_data = build_test_xml(
            order_id="order-999",
            order_number=order_number,
            status="Доставлен",
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, total_docs, parse_errors = service._parse_orders_xml(xml_data)

        # ASSERT
        assert len(order_updates) == 1
        assert total_docs == 1
        assert parse_errors == []
        assert order_updates[0].order_id == "order-999"
        assert order_updates[0].order_number == order_number
        assert order_updates[0].status_1c == "Доставлен"

    def test_parse_xml_with_bytes(self):
        """Парсинг XML из bytes."""
        # ARRANGE
        xml_data = build_test_xml().encode("utf-8")
        service = OrderStatusImportService()

        # ACT
        order_updates, total_docs, parse_errors = service._parse_orders_xml(xml_data)

        # ASSERT
        assert len(order_updates) == 1
        assert total_docs == 1
        assert parse_errors == []

    def test_parse_xml_with_multiple_orders(self):
        """Парсинг XML с несколькими заказами."""
        # ARRANGE
        xml_data = build_multi_order_xml(
            [
                {"order_id": "order-1", "order_number": "FS-1", "status": "Отгружен"},
                {"order_id": "order-2", "order_number": "FS-2", "status": "Доставлен"},
                {
                    "order_id": "order-3",
                    "order_number": "FS-3",
                    "status": "Подтвержден",
                },
            ]
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, total_docs, parse_errors = service._parse_orders_xml(xml_data)

        # ASSERT
        assert len(order_updates) == 3
        assert total_docs == 3
        assert parse_errors == []
        statuses = [u.status_1c for u in order_updates]
        assert "Отгружен" in statuses
        assert "Доставлен" in statuses
        assert "Подтвержден" in statuses

    def test_parse_xml_invalid_raises_error(self):
        """Невалидный XML вызывает ParseError."""
        # ARRANGE
        invalid_xml = "<invalid><not-closed>"
        service = OrderStatusImportService()

        # ACT / ASSERT
        with pytest.raises(ET.ParseError):
            service._parse_orders_xml(invalid_xml)


@pytest.mark.unit
class TestDateExtraction:
    """Тесты извлечения дат из реквизитов (AC5)."""

    def test_process_extracts_payment_and_shipment_dates(self):
        """AC9 4.5: Извлечение дат оплаты и отгрузки."""
        # ARRANGE
        xml_data = build_test_xml(
            status="Отгружен",
            paid_date="2026-02-01",
            shipped_date="2026-02-02",
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, total_docs, parse_errors = service._parse_orders_xml(xml_data)

        # ASSERT
        assert len(order_updates) == 1
        assert total_docs == 1
        assert parse_errors == []
        update = order_updates[0]

        # Проверяем что даты распарсены
        assert update.paid_at is not None
        assert update.shipped_at is not None

        # Проверяем значения дат
        assert update.paid_at.date() == date(2026, 2, 1)
        assert update.shipped_at.date() == date(2026, 2, 2)

    def test_parse_date_missing_returns_none(self):
        """Отсутствующая дата возвращает None."""
        # ARRANGE
        xml_data = build_test_xml(
            status="Отгружен",
            paid_date=None,
            shipped_date=None,
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, _, _ = service._parse_orders_xml(xml_data)

        # ASSERT
        assert order_updates[0].paid_at is None
        assert order_updates[0].shipped_at is None

    def test_invalid_date_does_not_mark_present(self):
        # [AI-Review][High] Некорректная дата не должна помечаться как present.
        # ARRANGE
        xml_data = build_test_xml(
            status="Отгружен",
            paid_date="2026-02-30",
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, _, _ = service._parse_orders_xml(xml_data)

        # ASSERT
        update = order_updates[0]
        assert update.paid_at is None
        assert update.paid_at_present is False

    def test_parse_datetime_with_time_preserves_time(self):
        # [AI-Review][Low] Парсинг datetime с временем сохраняет время.
        # ARRANGE
        xml_data = build_test_xml(
            status="Отгружен",
            paid_date="2026-02-01T14:30:00",
            shipped_date="2026-02-02T09:15:30",
        )
        service = OrderStatusImportService()

        # ACT
        order_updates, _, _ = service._parse_orders_xml(xml_data)

        # ASSERT
        update = order_updates[0]
        assert update.paid_at is not None
        assert update.shipped_at is not None

        # Проверяем время (не только дату)
        assert update.paid_at.hour == 14
        assert update.paid_at.minute == 30
        assert update.shipped_at.hour == 9
        assert update.shipped_at.minute == 15
        assert update.shipped_at.second == 30

    def test_parse_date_value_uses_source_timezone(self):
        # [AI-Review][Medium] _parse_date_value учитывает SOURCE_TIME_ZONE.
        # ARRANGE
        service = OrderStatusImportService()

        # ACT
        with override_settings(ONEC_EXCHANGE={"SOURCE_TIME_ZONE": "UTC"}):
            parsed = service._parse_date_value("2026-02-01T10:30:00")

        # ASSERT
        assert parsed is not None
        assert parsed.tzinfo is not None
        assert parsed.tzinfo == ZoneInfo("UTC")


@pytest.mark.unit
class TestOrderProcessing:
    """Тесты обработки заказов с моками (AC2, AC3, AC4, AC6, AC7, AC8)."""

    def test_process_updates_order_status_and_status_1c(self):
        """AC9 4.4: Обновление статуса + status_1c."""
        # ARRANGE
        order_number = f"FS-{get_unique_suffix()}"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
        )

        # Мокаем Order
        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = None
        mock_order.shipped_at = None

        service = OrderStatusImportService()

        # Мокаем bulk_fetch чтобы вернуть кэш с order
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.updated == 1
            assert mock_order.status == "shipped"  # Mapped from "Отгружен"
            assert mock_order.status_1c == "Отгружен"  # Original 1C status (AC4)
            mock_order.save.assert_called_once()

    def test_unknown_status_logs_warning_and_skips(self):
        """AC9 4.6: Неизвестный статус — пропуск заказа (AC6)."""
        # ARRANGE
        order_number = "FS-TEST-001"
        xml_data = build_test_xml(order_number=order_number, status="НеизвестныйСтатус")

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.skipped_unknown_status == 1
            assert result.skipped_up_to_date == 0
            assert result.updated == 0
            mock_order.save.assert_not_called()

    def test_idempotent_updates_sent_to_1c_when_status_unchanged(self):
        # [AI-Review][High] sent_to_1c обновляется даже без изменений статуса.
        # ARRANGE
        order_number = "FS-SENT-IDEM-001"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"
        mock_order.status_1c = "Отгружен"
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False
        mock_order.sent_to_1c_at = None

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — sent_to_1c должен обновиться
            assert result.updated == 1
            assert result.skipped_up_to_date == 0
            assert mock_order.sent_to_1c is True
            assert mock_order.sent_to_1c_at is not None
            mock_order.save.assert_called_once()

    def test_missing_order_logs_error_and_continues(self):
        """AC9 4.7: Отсутствующий заказ — продолжение обработки (AC7)."""
        # ARRANGE
        xml_data = build_multi_order_xml(
            [
                {
                    "order_id": "order-1",
                    "order_number": "MISSING-1",
                    "status": "Отгружен",
                },
                {
                    "order_id": "order-2",
                    "order_number": "EXISTS-1",
                    "status": "Доставлен",
                },
            ]
        )

        mock_existing_order = MagicMock()
        mock_existing_order.order_number = "EXISTS-1"
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-2
        mock_existing_order.pk = 2
        mock_existing_order.status = "pending"
        mock_existing_order.status_1c = ""
        mock_existing_order.paid_at = None
        mock_existing_order.shipped_at = None

        service = OrderStatusImportService()

        # Кэш содержит только EXISTS-1, MISSING-1 отсутствует
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {"num:EXISTS-1": mock_existing_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.processed == 2
            assert result.updated == 1  # EXISTS-1 updated
            assert result.not_found == 1  # MISSING-1 not found
            mock_existing_order.save.assert_called_once()

    def test_idempotent_processing_no_duplicate_updates(self):
        """AC9 4.8: Идемпотентность — повторная обработка не дублирует (AC8)."""
        # ARRANGE
        order_number = "FS-IDEM-001"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
        )

        # Заказ уже имеет такой же статус
        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"  # Already shipped
        mock_order.status_1c = "Отгружен"  # Same 1C status
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = True
        previous_sent_to_1c_at = timezone.now() - timedelta(days=1)
        mock_order.sent_to_1c_at = previous_sent_to_1c_at

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

        # ASSERT — sent_to_1c_at должен обновиться
        assert result.skipped_up_to_date == 1
        assert result.skipped_unknown_status == 0
        assert result.updated == 0
        assert mock_order.sent_to_1c_at != previous_sent_to_1c_at
        mock_order.save.assert_called_once()

    def test_idempotent_updates_dates_even_if_status_unchanged(self):
        """
        [AI-Review][High] Обновление дат даже если статус не изменился.
        """
        # ARRANGE
        order_number = "FS-DATES-001"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
            paid_date="2026-02-01",
            shipped_date="2026-02-02",
        )

        # Заказ уже имеет такой же статус, но даты отсутствуют
        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"  # Already shipped
        mock_order.status_1c = "Отгружен"  # Same 1C status
        mock_order.paid_at = None  # Date not set
        mock_order.shipped_at = None  # Date not set

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

        # ASSERT — даты должны обновиться несмотря на совпадение статуса
        assert result.updated == 1
        assert result.skipped_up_to_date == 0
        assert result.skipped_unknown_status == 0
        assert mock_order.paid_at is not None
        assert mock_order.shipped_at is not None
        mock_order.save.assert_called_once()

    def test_process_sets_payment_status_paid_when_paid_at_present(self):
        # [AI-Review][Medium] paid_at из 1С выставляет payment_status='paid'.
        # ARRANGE
        order_number = "FS-PAID-001"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
            paid_date="2026-02-01",
        )

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"
        mock_order.status_1c = "Отгружен"
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.payment_status = "pending"
        mock_order.sent_to_1c = True
        mock_order.sent_to_1c_at = timezone.now()

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

        # ASSERT
        assert result.updated == 1
        assert mock_order.payment_status == "paid"
        mock_order.save.assert_called_once()

    def test_payment_status_refunded_not_regressed_by_paid_at(self):
        # [AI-Review][Medium] refunded payment_status не регрессирует в paid.
        # ARRANGE
        order_number = "FS-REFUND-001"
        xml_data = build_test_xml(
            order_number=order_number,
            status="Отгружен",
            paid_date="2026-02-01",
        )

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"
        mock_order.status_1c = "Отгружен"
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.payment_status = "refunded"
        mock_order.sent_to_1c = True
        mock_order.sent_to_1c_at = timezone.now()

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

        # ASSERT
        assert result.updated == 1
        assert mock_order.payment_status == "refunded"
        mock_order.save.assert_called_once()

    def test_process_uses_batch_size_from_settings(self):
        # [AI-Review][Medium] process() обрабатывает заказы батчами.
        # ARRANGE
        xml_data = build_multi_order_xml(
            [
                {
                    "order_id": "order-1",
                    "order_number": "FS-BATCH-1",
                    "status": "Отгружен",
                },
                {
                    "order_id": "order-2",
                    "order_number": "FS-BATCH-2",
                    "status": "Отгружен",
                },
                {
                    "order_id": "order-3",
                    "order_number": "FS-BATCH-3",
                    "status": "Отгружен",
                },
            ]
        )
        service = OrderStatusImportService()

        with override_settings(ONEC_EXCHANGE={"ORDER_STATUS_IMPORT_BATCH_SIZE": 2}):
            with patch.object(service, "_bulk_fetch_orders", return_value={}) as bulk_fetch:
                with patch.object(
                    service,
                    "_process_order_update",
                    return_value=(ProcessingStatus.SKIPPED_UP_TO_DATE, None),
                ):
                    # ACT
                    result = service.process(xml_data)

        # ASSERT
        assert result.processed == 3
        assert result.skipped_up_to_date == 3
        assert bulk_fetch.call_count == 2
        first_batch = bulk_fetch.call_args_list[0].args[0]
        second_batch = bulk_fetch.call_args_list[1].args[0]
        assert len(first_batch) == 2
        assert len(second_batch) == 1

    def test_status_1c_truncated_to_255_chars(self):
        # [AI-Review][Low] status_1c обрезается до 255 символов для защиты от DB error.
        # ARRANGE
        order_number = f"FS-LONG-{get_unique_suffix()}"
        long_status = "А" * 300  # 300 символов кириллицы
        xml_data = build_test_xml(order_number=order_number, status=long_status)

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False
        mock_order.sent_to_1c_at = None
        mock_order.payment_status = "pending"

        # status_1c не в STATUS_MAPPING — будет skipped_unknown_status
        # Но логика truncate срабатывает в _process_order_update перед save
        # Чтобы протестировать truncate, добавим статус в mapping временно
        with patch.dict(STATUS_MAPPING, {long_status: "confirmed"}), patch.dict(
            STATUS_MAPPING_LOWER, {long_status.lower(): "confirmed"}
        ):
            service = OrderStatusImportService()
            mock_cache = {f"num:{order_number}": mock_order}

            with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
                # ACT
                result = service.process(xml_data)

                # ASSERT
                assert result.updated == 1
                # status_1c должен быть обрезан до 255 символов
                assert len(mock_order.status_1c) == 255
                assert mock_order.status_1c == long_status[:255]
                mock_order.save.assert_called_once()


@pytest.mark.unit
class TestFindOrder:
    """Тесты поиска заказа (AC2)."""

    def test_find_order_by_order_number_priority(self):
        """Поиск сначала по order_number."""
        # ARRANGE
        from apps.orders.models import Order

        order_data = OrderUpdateData(
            order_id="order-999",
            order_number="FS-FIND-001",
            status_1c="Отгружен",
        )

        mock_order = MagicMock()
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-999
        mock_order.pk = 999
        mock_queryset = MagicMock()
        mock_queryset.first.return_value = mock_order

        # [AI-Review][Medium] Мокаем цепочку select_for_update().filter().first()
        mock_select_for_update = MagicMock()
        mock_select_for_update.filter.return_value = mock_queryset

        service = OrderStatusImportService()

        with patch.object(Order.objects, "select_for_update", return_value=mock_select_for_update):
            # ACT
            result, conflict_msg = service._find_order(order_data)

            # ASSERT
            assert conflict_msg is None
            assert result == mock_order
            mock_select_for_update.filter.assert_called_with(order_number="FS-FIND-001")

    def test_find_order_by_id_fallback(self):
        """Fallback поиск по order-{id} когда order_number не найден."""
        # ARRANGE
        from apps.orders.models import Order

        order_data = OrderUpdateData(
            order_id="order-42",
            order_number="",  # Empty - will use order_id
            status_1c="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.pk = 42
        service = OrderStatusImportService()

        # Тестируем _find_order с кэшем по pk
        cache: dict[str, Order] = {"pk:42": cast(Order, mock_order)}

        # ACT
        result, conflict_msg = service._find_order(order_data, cache)

        # ASSERT
        assert conflict_msg is None
        assert result == mock_order

    def test_find_order_fallback_to_db_when_no_cache(self):
        """Fallback на БД когда кэш не передан — проверка через process."""
        # ARRANGE
        xml_data = build_test_xml(order_id="order-42", order_number="")

        mock_order = MagicMock()
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.order_number = "FOUND-BY-ID"
        mock_order.paid_at = None
        mock_order.shipped_at = None

        service = OrderStatusImportService()

        # Кэш содержит order по pk
        mock_cache = {"pk:42": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.updated == 1


@pytest.mark.unit
class TestProcessIntegration:
    """Интеграционные unit-тесты для process()."""

    def test_process_returns_correct_result_structure(self):
        """Проверка структуры ImportResult."""
        # ARRANGE
        xml_data = build_test_xml()
        service = OrderStatusImportService()

        # Пустой кэш — заказ не найден
        with patch.object(service, "_bulk_fetch_orders", return_value={}):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert isinstance(result, ImportResult)
            assert hasattr(result, "processed")
            assert hasattr(result, "updated")
            assert hasattr(result, "skipped_up_to_date")
            assert hasattr(result, "skipped_unknown_status")
            assert hasattr(result, "skipped_data_conflict")
            assert hasattr(result, "skipped_status_regression")
            assert hasattr(result, "skipped_invalid")
            assert hasattr(result, "not_found")
            assert hasattr(result, "errors")

    def test_process_handles_xml_parse_error(self):
        """Обработка ошибки парсинга XML."""
        # ARRANGE
        invalid_xml = "<not valid xml>"
        service = OrderStatusImportService()

        # ACT
        result = service.process(invalid_xml)

        # ASSERT
        assert len(result.errors) > 0
        assert result.processed == 0

    def test_process_handles_defusedxml_exception(self):
        """[Review][Medium] DefusedXmlException фиксируется в errors."""
        # ARRANGE
        service = OrderStatusImportService()

        with patch.object(
            service,
            "_parse_orders_xml",
            side_effect=DefusedXmlException("entity expansion"),
        ):
            # ACT
            result = service.process("<xml></xml>")

        # ASSERT
        assert result.processed == 0
        assert len(result.errors) == 1
        assert "security" in result.errors[0].lower()

    def test_process_handles_operational_error_in_bulk_fetch(self):
        # [AI-Review][Medium] OperationalError в bulk fetch записывается в errors.
        # ARRANGE
        xml_data = build_test_xml(order_number="FS-DB-ERR-001", status="Отгружен")
        service = OrderStatusImportService()

        with patch.object(
            service,
            "_bulk_fetch_orders",
            side_effect=OperationalError("transient db error"),
        ):
            # ACT
            result = service.process(xml_data)

        # ASSERT
        assert result.processed == 1
        assert result.updated == 0
        assert result.not_found == 0
        assert len(result.errors) == 1
        assert "Database error during bulk fetch" in result.errors[0]


# =============================================================================
# Review Follow-up Tests
# =============================================================================


@pytest.mark.unit
class TestReviewFollowups:
    """Тесты для исправлений по результатам код-ревью."""

    def test_flexible_document_search_without_container(self):
        # [AI-Review][High] Гибкий поиск <Документ> без <Контейнер>.
        # ARRANGE — XML без <Контейнер>, <Документ> напрямую в root
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    <Документ>
        <Ид>order-100</Ид>
        <Номер>FS-FLEX-001</Номер>
        <ЗначенияРеквизитов>
            <ЗначениеРеквизита>
                <Наименование>СтатусЗаказа</Наименование>
                <Значение>Доставлен</Значение>
            </ЗначениеРеквизита>
        </ЗначенияРеквизитов>
    </Документ>
</КоммерческаяИнформация>
"""
        service = OrderStatusImportService()

        # ACT
        order_updates, total_docs, parse_errors = service._parse_orders_xml(xml_data)

        # ASSERT — документ должен быть найден
        assert len(order_updates) == 1
        assert total_docs == 1
        assert parse_errors == []
        assert order_updates[0].order_id == "order-100"
        assert order_updates[0].status_1c == "Доставлен"

    def test_requisite_name_with_spaces(self):
        """[AI-Review][High] Имена реквизитов с пробелами: 'Статус Заказа'."""
        # ARRANGE — XML с пробелами в имени реквизита
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    <Контейнер>
        <Документ>
            <Ид>order-200</Ид>
            <Номер>FS-SPACE-001</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>Статус Заказа</Наименование>
                    <Значение>Отгружен</Значение>
                </ЗначениеРеквизита>
                <ЗначениеРеквизита>
                    <Наименование>Дата Оплаты</Наименование>
                    <Значение>2026-02-01</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""
        service = OrderStatusImportService()

        # ACT
        order_updates, _, _ = service._parse_orders_xml(xml_data)

        # ASSERT — статус и дата должны быть извлечены
        assert len(order_updates) == 1
        assert order_updates[0].status_1c == "Отгружен"
        assert order_updates[0].paid_at is not None

    def test_case_insensitive_status_mapping(self):
        """[AI-Review][Medium] Регистронезависимый маппинг статусов."""
        # ARRANGE — статус в разном регистре
        order_number = "FS-CASE-001"

        for status_variant in ["ОТГРУЖЕН", "отгружен", "Отгружен", "оТгРуЖеН"]:
            xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    <Контейнер>
        <Документ>
            <Ид>order-300</Ид>
            <Номер>{order_number}</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>{status_variant}</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""
            mock_order = MagicMock()
            mock_order.order_number = order_number
            mock_order.status = "pending"
            mock_order.status_1c = ""
            mock_order.paid_at = None
            mock_order.paid_at = None
            mock_order.shipped_at = None
            mock_order.pk = 300

            service = OrderStatusImportService()
            # [AI-Review][High] Используем num: префикс для избежания коллизий
            mock_cache = {f"num:{order_number}": mock_order}

            with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
                # ACT
                result = service.process(xml_data)

                # ASSERT — статус должен быть смаплен на "shipped"
                assert result.updated == 1, f"Failed for status variant: {status_variant}"
                assert mock_order.status == "shipped", f"Failed for status variant: {status_variant}"

    def test_error_isolation_continues_processing(self):
        """[AI-Review][High] Изоляция ошибок — одна ошибка не останавливает обработку."""
        # ARRANGE — 3 заказа: 1й вызывает исключение при save, 2й и 3й нормальные
        xml_data = build_multi_order_xml(
            [
                {
                    "order_id": "order-1",
                    "order_number": "ERROR-ORDER",
                    "status": "Отгружен",
                },
                {
                    "order_id": "order-2",
                    "order_number": "GOOD-ORDER-1",
                    "status": "Доставлен",
                },
                {
                    "order_id": "order-3",
                    "order_number": "GOOD-ORDER-2",
                    "status": "Подтвержден",
                },
            ]
        )

        # Mock orders
        error_order = MagicMock()
        error_order.order_number = "ERROR-ORDER"
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-1
        error_order.pk = 1
        error_order.status = "pending"
        error_order.status_1c = ""
        error_order.paid_at = None
        error_order.shipped_at = None
        error_order.save.side_effect = Exception("Database error!")

        good_order_1 = MagicMock()
        good_order_1.order_number = "GOOD-ORDER-1"
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-2
        good_order_1.pk = 2
        good_order_1.status = "pending"
        good_order_1.status_1c = ""
        good_order_1.paid_at = None
        good_order_1.shipped_at = None

        good_order_2 = MagicMock()
        good_order_2.order_number = "GOOD-ORDER-2"
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-3
        good_order_2.pk = 3
        good_order_2.status = "pending"
        good_order_2.status_1c = ""
        good_order_2.paid_at = None
        good_order_2.shipped_at = None

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {
            "num:ERROR-ORDER": error_order,
            "num:GOOD-ORDER-1": good_order_1,
            "num:GOOD-ORDER-2": good_order_2,
        }

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — обработка продолжилась, ошибка зафиксирована
            assert result.processed == 3
            assert result.updated == 2  # GOOD-ORDER-1 и GOOD-ORDER-2
            assert len(result.errors) == 1  # ERROR-ORDER
            assert "Database error" in result.errors[0]
            good_order_1.save.assert_called_once()
            good_order_2.save.assert_called_once()

    def test_errors_collected_in_import_result(self):
        """[AI-Review][Medium] Ошибки собираются в ImportResult.errors."""
        # ARRANGE — заказ не найден
        xml_data = build_test_xml(order_number="NOT-EXISTS", order_id="order-999")
        service = OrderStatusImportService()

        with patch.object(service, "_bulk_fetch_orders", return_value={}):
            # ACT
            result = service.process(xml_data)

            # ASSERT — ошибка "not found" добавлена в errors
            assert result.not_found == 1
            assert len(result.errors) == 1
            assert "not found" in result.errors[0].lower()

    def test_extract_all_requisites_optimization(self):
        """[AI-Review][Low] Оптимизация: все реквизиты собираются в один dict."""
        # ARRANGE
        import defusedxml.ElementTree as ET

        xml_doc = """
        <Документ>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Отгружен</Значение>
                </ЗначениеРеквизита>
                <ЗначениеРеквизита>
                    <Наименование>ДатаОплаты</Наименование>
                    <Значение>2026-02-01</Значение>
                </ЗначениеРеквизита>
                <ЗначениеРеквизита>
                    <Наименование>Дата Отгрузки</Наименование>
                    <Значение>2026-02-02</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
        """
        document = ET.fromstring(xml_doc)
        service = OrderStatusImportService()

        # ACT
        requisites = service._extract_all_requisites(document)

        # ASSERT — все реквизиты собраны, с нормализацией
        assert "статусзаказа" in requisites
        assert requisites["статусзаказа"] == "Отгружен"
        assert "датаоплаты" in requisites
        assert requisites["датаоплаты"] == "2026-02-01"
        # Нормализация удаляет все whitespace
        assert "датаотгрузки" in requisites

    def test_sent_to_1c_set_true_on_status_import(self):
        """[AI-Review][Medium] sent_to_1c=True при получении статуса из 1С."""
        # ARRANGE
        order_number = "FS-SENT-001"
        xml_data = build_test_xml(order_number=order_number, status="Отгружен")

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False  # Not yet synced

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — sent_to_1c должен быть установлен в True
            assert result.updated == 1
            assert mock_order.sent_to_1c is True
            mock_order.save.assert_called_once()

    def test_processed_count_includes_invalid_documents(self):
        """[AI-Review][Low] result.processed включает все <Документ>, включая некорректные."""
        # ARRANGE — 2 документа: 1 валидный, 1 без статуса (некорректный)
        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация ВерсияСхемы="3.1">
    <Контейнер>
        <Документ>
            <Ид>order-1</Ид>
            <Номер>VALID-001</Номер>
            <ЗначенияРеквизитов>
                <ЗначениеРеквизита>
                    <Наименование>СтатусЗаказа</Наименование>
                    <Значение>Отгружен</Значение>
                </ЗначениеРеквизита>
            </ЗначенияРеквизитов>
        </Документ>
        <Документ>
            <Ид>order-2</Ид>
            <Номер>INVALID-001</Номер>
            <!-- Нет СтатусЗаказа — некорректный документ -->
        </Документ>
    </Контейнер>
</КоммерческаяИнформация>
"""
        service = OrderStatusImportService()

        with patch.object(service, "_bulk_fetch_orders", return_value={}):
            # ACT
            result = service.process(xml_data)

            # ASSERT — processed = 2 (оба документа), но только 1 обработан
            assert result.processed == 2  # Все найденные <Документ>
            assert result.skipped_invalid == 1  # Некорректный документ учтён отдельно
            assert result.not_found == 1  # Только валидный документ дошёл до поиска
            assert len(result.errors) == 2


# =============================================================================
# Round 3 Review Follow-up Tests
# =============================================================================


@pytest.mark.unit
class TestRound3ReviewFollowups:
    """Тесты для исправлений Round 3 код-ревью."""

    def test_sent_to_1c_at_set_when_sent_to_1c_becomes_true(self):
        """[AI-Review][Medium] Data Integrity: sent_to_1c_at устанавливается при sent_to_1c=True."""
        # ARRANGE
        order_number = "FS-SENT-AT-001"
        xml_data = build_test_xml(order_number=order_number, status="Отгружен")

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False  # Ещё не синхронизирован
        mock_order.sent_to_1c_at = None

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        before_process = timezone.now()

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.updated == 1
            assert mock_order.sent_to_1c is True
            assert mock_order.sent_to_1c_at is not None
            # Проверяем что sent_to_1c_at установлен примерно в текущее время
            assert mock_order.sent_to_1c_at >= before_process

    def test_sent_to_1c_at_updated_if_already_synced(self):
        """sent_to_1c_at обновляется при повторной синхронизации."""
        # ARRANGE
        order_number = "FS-ALREADY-SYNCED"
        xml_data = build_test_xml(order_number=order_number, status="Доставлен")

        original_sync_time = timezone.now() - timedelta(days=1)

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "shipped"  # Другой статус — будет обновление
        mock_order.status_1c = "Отгружен"
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = True  # Уже синхронизирован
        mock_order.sent_to_1c_at = original_sync_time

        service = OrderStatusImportService()
        # [AI-Review][High] Используем num: префикс для избежания коллизий
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — статус обновлён и sent_to_1c_at обновлён
            assert result.updated == 1
            assert mock_order.sent_to_1c is True
            assert mock_order.sent_to_1c_at != original_sync_time

    def test_order_id_prefix_constant_used(self):
        """[AI-Review][Low] Flexibility: ORDER_ID_PREFIX используется для парсинга."""
        # ARRANGE
        service = OrderStatusImportService()

        # ACT / ASSERT — проверяем что константа имеет ожидаемое значение
        assert ORDER_ID_PREFIX == "order-"

        # Проверяем парсинг с использованием константы
        pk = service._parse_order_id_to_pk(f"{ORDER_ID_PREFIX}42")
        assert pk == 42

        # Некорректный формат
        pk_invalid = service._parse_order_id_to_pk("invalid-42")
        assert pk_invalid is None

    def test_max_errors_constant_defined(self):
        """[AI-Review][Low] Reliability: MAX_ERRORS константа определена."""
        assert MAX_ERRORS == 100

    def test_errors_list_truncated_at_max_errors(self):
        """[AI-Review][Low] Reliability: список ошибок ограничен MAX_ERRORS."""
        # ARRANGE — создаём много несуществующих заказов
        orders = []
        for i in range(150):
            orders.append(
                {
                    "order_id": f"order-{i}",
                    "order_number": f"NOT-EXISTS-{i}",
                    "status": "Отгружен",
                }
            )

        xml_data = build_multi_order_xml(orders)
        service = OrderStatusImportService()

        # Пустой кэш — все заказы не найдены
        with patch.object(service, "_bulk_fetch_orders", return_value={}):
            # ACT
            result = service.process(xml_data)

            # ASSERT
            assert result.processed == 150
            assert result.not_found == 150
            # Ошибки ограничены MAX_ERRORS
            assert len(result.errors) == MAX_ERRORS


# =============================================================================
# Round 6 Review Follow-up Tests (Cache Key Collision & Race Condition)
# =============================================================================


@pytest.mark.unit
class TestRound6ReviewFollowups:
    """Тесты для исправлений Round 6 код-ревью."""

    def test_cache_key_collision_prevented_with_num_prefix(self):
        """[AI-Review][High] Cache Key Collision Risk: num: префикс предотвращает коллизии."""
        # ARRANGE — order_number может выглядеть как pk:123
        order_number = "pk:999"  # Edge case: order_number looks like pk key
        order_pk = 999

        xml_data = build_test_xml(
            order_id=f"order-{order_pk}",
            order_number=order_number,
            status="Отгружен",
        )

        mock_order_by_number = MagicMock()
        mock_order_by_number.order_number = order_number
        # [AI-Review][Medium] Data Integrity: pk должен соответствовать order_id
        mock_order_by_number.pk = order_pk
        mock_order_by_number.status = "pending"
        mock_order_by_number.status_1c = ""
        mock_order_by_number.paid_at = None
        mock_order_by_number.shipped_at = None
        mock_order_by_number.sent_to_1c = False

        # [AI-Review][Medium] Data Integrity: второй заказ с тем же pk создаст конфликт
        # Тест проверяет, что num: и pk: ключи не путаются, поэтому используем один заказ
        mock_order_by_pk = MagicMock()
        mock_order_by_pk.order_number = "DIFFERENT"
        mock_order_by_pk.pk = 1000  # Другой pk, не связанный с текущим XML
        mock_order_by_pk.status = "pending"
        mock_order_by_pk.status_1c = ""
        mock_order_by_pk.paid_at = None
        mock_order_by_pk.shipped_at = None
        mock_order_by_pk.sent_to_1c = False

        service = OrderStatusImportService()

        # [AI-Review][High] Кэш с обоими типами ключей — они НЕ должны конфликтовать
        # num:pk:999 указывает на заказ с pk=999
        # pk:1000 указывает на другой заказ (не связан с текущим XML)
        mock_cache = {
            f"num:{order_number}": mock_order_by_number,  # num:pk:999 -> pk=999
            "pk:1000": mock_order_by_pk,  # pk:1000 -> другой заказ
        }

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — должен быть найден по order_number (приоритет)
            assert result.updated == 1
            mock_order_by_number.save.assert_called_once()
            mock_order_by_pk.save.assert_not_called()

    def test_bulk_fetch_creates_correct_cache_keys(self):
        """
        [AI-Review][High] _bulk_fetch_orders создаёт ключи
        с правильными префиксами.
        """
        # ARRANGE
        from unittest.mock import MagicMock
        from unittest.mock import patch as mock_patch

        order_updates = [
            OrderUpdateData(
                order_id="order-42",
                order_number="FS-TEST-001",
                status_1c="Отгружен",
            ),
            OrderUpdateData(
                order_id="order-100",
                order_number="FS-TEST-002",
                status_1c="Доставлен",
            ),
        ]

        mock_order_1 = MagicMock()
        mock_order_1.order_number = "FS-TEST-001"
        mock_order_1.pk = 42

        mock_order_2 = MagicMock()
        mock_order_2.order_number = "FS-TEST-002"
        mock_order_2.pk = 100

        service = OrderStatusImportService()

        with mock_patch("apps.orders.models.Order.objects") as mock_objects:
            # [AI-Review][High] Мокаем цепочку
            # select_for_update().filter().order_by().only()
            mock_select_for_update = MagicMock()
            mock_filter = MagicMock()
            mock_order_by = MagicMock()
            mock_order_by.only.return_value = [mock_order_1, mock_order_2]
            mock_filter.order_by.return_value = mock_order_by
            mock_select_for_update.filter.return_value = mock_filter
            mock_objects.select_for_update.return_value = mock_select_for_update

            # ACT
            cache = service._bulk_fetch_orders(order_updates)

            # ASSERT — ключи должны быть с правильными префиксами
            assert "num:FS-TEST-001" in cache
            assert "num:FS-TEST-002" in cache
            assert "pk:42" in cache
            assert "pk:100" in cache

            # Старый формат БЕЗ префикса НЕ должен присутствовать
            assert "FS-TEST-001" not in cache
            assert "FS-TEST-002" not in cache

            # select_for_update должен быть вызван
            mock_objects.select_for_update.assert_called_once()
            mock_select_for_update.filter.assert_called_once()
            mock_filter.order_by.assert_called_once_with("pk")
            mock_order_by.only.assert_called_once()

    def test_find_order_uses_num_prefix_for_cache_lookup(self):
        """[AI-Review][High] _find_order ищет по num:{order_number} в кэше."""
        # ARRANGE
        order_number = "FS-CACHE-001"
        order_data = OrderUpdateData(
            order_id="order-50",
            order_number=order_number,
            status_1c="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.order_number = order_number
        mock_order.pk = 50

        service = OrderStatusImportService()

        # Кэш с правильным num: префиксом
        cache: dict[str, Order] = {f"num:{order_number}": cast(Order, mock_order)}

        # ACT
        found_order, conflict_msg = service._find_order(order_data, cache)

        # ASSERT
        assert conflict_msg is None
        assert found_order == mock_order

    def test_find_order_fallback_uses_select_for_update(self):
        # [AI-Review][Medium] Race Condition Risk: select_for_update()
        # в fallback запросе.
        # ARRANGE
        from unittest.mock import MagicMock
        from unittest.mock import patch as mock_patch

        order_data = OrderUpdateData(
            order_id="order-77",
            order_number="FS-LOCK-001",
            status_1c="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.order_number = "FS-LOCK-001"
        mock_order.pk = 77

        service = OrderStatusImportService()

        with mock_patch("apps.orders.models.Order.objects") as mock_objects:
            # Настраиваем цепочку вызовов: select_for_update().filter().first()
            mock_select_for_update = MagicMock()
            mock_filter = MagicMock()
            mock_filter.first.return_value = mock_order
            mock_select_for_update.filter.return_value = mock_filter
            mock_objects.select_for_update.return_value = mock_select_for_update

            # ACT — вызываем без кэша (None), чтобы сработал fallback
            found_order, conflict_msg = service._find_order(order_data, orders_cache=None)

            # ASSERT — select_for_update() должен быть вызван
            mock_objects.select_for_update.assert_called_once()
            mock_select_for_update.filter.assert_called_once_with(order_number="FS-LOCK-001")
            assert conflict_msg is None
            assert found_order == mock_order

    def test_find_order_fallback_pk_uses_select_for_update(self):
        # [AI-Review][Medium] select_for_update() используется при поиске по pk.
        # ARRANGE
        from unittest.mock import MagicMock
        from unittest.mock import patch as mock_patch

        order_data = OrderUpdateData(
            order_id="order-88",
            order_number="",  # Пустой номер — сразу идёт поиск по pk
            status_1c="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.pk = 88

        service = OrderStatusImportService()

        with mock_patch("apps.orders.models.Order.objects") as mock_objects:
            # Поиск по pk напрямую (order_number пустой, поэтому первый if пропускается)
            mock_select_for_update = MagicMock()
            mock_filter_pk = MagicMock()
            mock_filter_pk.first.return_value = mock_order  # Найден по pk

            mock_select_for_update.filter.return_value = mock_filter_pk
            mock_objects.select_for_update.return_value = mock_select_for_update

            # ACT
            found_order, conflict_msg = service._find_order(order_data, orders_cache=None)

            # ASSERT
            assert conflict_msg is None
            assert found_order == mock_order
            # select_for_update() вызван один раз для поиска по pk
            mock_objects.select_for_update.assert_called_once()
            mock_select_for_update.filter.assert_called_once_with(pk=88)


@pytest.mark.unit
class TestRound7ReviewFollowups:
    """Тесты для исправлений Round 7 код-ревью (сброс дат, маппинг, .only())."""

    def test_date_reset_when_tag_present_but_empty(self):
        # [AI-Review][Medium] Logic/Data Consistency: дата сбрасывается при пустом теге.
        # ARRANGE
        order_number = "FS-DATE-RESET-001"
        # XML с пустым тегом <ДатаОплаты></ДатаОплаты>
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-04T12:00:00">
            <Контейнер>
                <Документ>
                    <Ид>order-123</Ид>
                    <Номер>{order_number}</Номер>
                    <ЗначенияРеквизитов>
                        <ЗначениеРеквизита>
                            <Наименование>СтатусЗаказа</Наименование>
                            <Значение>Отгружен</Значение>
                        </ЗначениеРеквизита>
                        <ЗначениеРеквизита>
                            <Наименование>ДатаОплаты</Наименование>
                            <Значение></Значение>
                        </ЗначениеРеквизита>
                    </ЗначенияРеквизитов>
                </Документ>
            </Контейнер>
        </КоммерческаяИнформация>"""

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = timezone.now()  # Была установлена дата
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False
        mock_order.sent_to_1c_at = None

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — дата должна быть сброшена (None)
            assert result.updated == 1
            assert mock_order.paid_at is None

    def test_date_not_changed_when_tag_absent(self):
        # [AI-Review][Medium] Logic/Data Consistency: дата НЕ меняется если тега нет.
        # ARRANGE
        order_number = "FS-DATE-KEEP-001"
        original_paid_at = timezone.now()
        # XML БЕЗ тега <ДатаОплаты>
        xml_data = f"""<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация ВерсияСхемы="3.1" ДатаФормирования="2026-02-04T12:00:00">
            <Контейнер>
                <Документ>
                    <Ид>order-124</Ид>
                    <Номер>{order_number}</Номер>
                    <ЗначенияРеквизитов>
                        <ЗначениеРеквизита>
                            <Наименование>СтатусЗаказа</Наименование>
                            <Значение>Доставлен</Значение>
                        </ЗначениеРеквизита>
                    </ЗначенияРеквизитов>
                </Документ>
            </Контейнер>
        </КоммерческаяИнформация>"""

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-124
        mock_order.pk = 124
        mock_order.status = "shipped"
        mock_order.status_1c = "Отгружен"
        mock_order.paid_at = original_paid_at  # Была установлена дата
        mock_order.shipped_at = None
        mock_order.sent_to_1c = True
        mock_order.sent_to_1c_at = timezone.now()

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — дата НЕ должна измениться (тега не было)
            assert result.updated == 1
            assert mock_order.paid_at == original_paid_at

    def test_status_mapping_lower_precomputed(self):
        # [AI-Review][Low] Code Style: STATUS_MAPPING_LOWER существует и корректен.
        # ASSERT — все ключи должны быть в lowercase
        for key in STATUS_MAPPING_LOWER:
            assert key == key.lower()

        # ASSERT — все значения из STATUS_MAPPING должны быть в STATUS_MAPPING_LOWER
        for original_key, value in STATUS_MAPPING.items():
            assert STATUS_MAPPING_LOWER[original_key.lower()] == value

    def test_order_update_data_has_present_flags(self):
        # [AI-Review][Medium] Logic/Data Consistency: OrderUpdateData имеет флаги *_present.
        # ARRANGE
        data = OrderUpdateData(
            order_id="order-1",
            order_number="TEST-001",
            status_1c="Отгружен",
            paid_at=None,
            shipped_at=None,
            paid_at_present=True,
            shipped_at_present=False,
        )

        # ASSERT
        assert data.paid_at_present is True
        assert data.shipped_at_present is False

    @pytest.mark.parametrize(
        ("current_status", "status_1c"),
        [
            ("delivered", "Доставлен"),
            ("cancelled", "Отменен"),
            ("refunded", "Возвращен"),
        ],
    )
    def test_final_status_regression_is_skipped(self, current_status, status_1c):
        # [AI-Review][Medium] Финальные статусы не регрессируют в активные.
        # ARRANGE
        order_number = "FS-FINAL-001"
        xml_data = build_test_xml(order_number=order_number, status="Отгружен")

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = current_status  # финальный статус
        mock_order.status_1c = status_1c
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = True
        mock_order.sent_to_1c_at = timezone.now()

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — обновление должно быть пропущено
            assert result.updated == 0
            assert result.skipped_status_regression == 1
            assert result.skipped_unknown_status == 0
            mock_order.save.assert_not_called()
            assert mock_order.status == current_status

    @pytest.mark.parametrize(
        ("current_status", "current_1c", "new_1c_status", "target_status"),
        [
            # cancelled → delivered (blocked)
            ("cancelled", "Отменен", "Доставлен", "delivered"),
            # cancelled → refunded (blocked)
            ("cancelled", "Отменен", "Возвращен", "refunded"),
            # delivered → cancelled (blocked)
            ("delivered", "Доставлен", "Отменен", "cancelled"),
            # delivered → refunded (blocked)
            ("delivered", "Доставлен", "Возвращен", "refunded"),
            # refunded → cancelled (blocked)
            ("refunded", "Возвращен", "Отменен", "cancelled"),
            # refunded → delivered (blocked)
            ("refunded", "Возвращен", "Доставлен", "delivered"),
        ],
    )
    def test_transition_between_final_statuses_is_blocked(
        self, current_status, current_1c, new_1c_status, target_status
    ):
        # [AI-Review][Medium] Переходы между финальными статусами блокируются.
        # ARRANGE
        order_number = f"FS-FINAL-TRANS-{get_unique_suffix()}"
        xml_data = build_test_xml(order_number=order_number, status=new_1c_status)

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = current_status
        mock_order.status_1c = current_1c
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = True
        mock_order.sent_to_1c_at = timezone.now()
        mock_order.payment_status = "paid"

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — переход между финальными статусами блокируется
            assert result.updated == 0
            assert result.skipped_status_regression == 1
            mock_order.save.assert_not_called()
            # Статус не изменился
            assert mock_order.status == current_status

    def test_status_update_logged_at_debug(self, caplog):
        # [AI-Review][Medium] Обновление статуса логируется на DEBUG, не INFO.
        # ARRANGE
        order_number = "FS-LOG-DEBUG-001"
        xml_data = build_test_xml(order_number=order_number, status="Отгружен")

        mock_order = MagicMock()
        mock_order.order_number = order_number
        # [AI-Review][Medium] Data Integrity:
        # pk должен соответствовать order_id=order-123
        mock_order.pk = 123
        mock_order.status = "pending"
        mock_order.status_1c = ""
        mock_order.paid_at = None
        mock_order.shipped_at = None
        mock_order.sent_to_1c = False
        mock_order.sent_to_1c_at = None

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            caplog.set_level(logging.DEBUG, logger="apps.orders.services.order_status_import")
            result = service.process(xml_data)

        # ASSERT
        assert result.updated == 1
        update_logs = [record for record in caplog.records if "status updated to" in record.message]
        assert update_logs, "Ожидали debug-лог обновления статуса"
        assert all(record.levelno == logging.DEBUG for record in update_logs)

    def test_parse_document_sets_present_flags(self):
        # [AI-Review][Medium] Logic/Data Consistency: _parse_document устанавливает флаги.
        # ARRANGE
        xml_str = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Документ>"
            "    <Ид>order-200</Ид>"
            "    <Номер>FS-FLAGS-1</Номер>"
            "    <ЗначенияРеквизитов>"
            "        <ЗначениеРеквизита>"
            "            <Наименование>СтатусЗаказа</Наименование>"
            "            <Значение>Отгружен</Значение>"
            "        </ЗначениеРеквизита>"
            "        <ЗначениеРеквизита>"
            "            <Наименование>ДатаОплаты</Наименование>"
            "            <Значение>2026-02-01</Значение>"
            "        </ЗначениеРеквизита>"
            "    </ЗначенияРеквизитов>"
            "</Документ>"
        )

        import defusedxml.ElementTree as ET

        document = ET.fromstring(xml_str)

        service = OrderStatusImportService()

        # ACT
        result = service._parse_document(document)

        # ASSERT — paid_at_present=True (тег есть), shipped_at_present=False (тега нет)
        assert result.paid_at_present is True
        assert result.shipped_at_present is False
        assert result.paid_at is not None


# =============================================================================
# Round 13 Review Follow-up Tests
# =============================================================================


@pytest.mark.unit
class TestRound13ReviewFollowups:
    # Тесты для исправлений Round 13 код-ревью.

    def test_import_result_skipped_property(self):
        # [AI-Review][Low] AC Deviation: ImportResult.skipped суммирует все skipped_*.
        # ARRANGE
        result = ImportResult(
            processed=10,
            updated=2,
            skipped_up_to_date=3,
            skipped_unknown_status=1,
            skipped_data_conflict=1,
            skipped_status_regression=2,
            skipped_invalid=1,
            not_found=0,
        )

        # ACT
        total_skipped = result.skipped

        # ASSERT
        assert total_skipped == 8  # 3 + 1 + 1 + 2 + 1

    def test_import_result_skipped_defaults_to_zero(self):
        # [AI-Review][Low] ImportResult.skipped возвращает 0 по умолчанию.
        # ARRANGE
        result = ImportResult()

        # ACT / ASSERT
        assert result.skipped == 0

    def test_order_update_data_has_parse_warnings_field(self):
        # [AI-Review][Medium] Observability: OrderUpdateData имеет поле parse_warnings.
        # ARRANGE
        data = OrderUpdateData(
            order_id="order-1",
            order_number="TEST-001",
            status_1c="Отгружен",
            parse_warnings=["Invalid date format: '2026-02-30'"],
        )

        # ASSERT
        assert data.parse_warnings == ["Invalid date format: '2026-02-30'"]

    def test_order_update_data_parse_warnings_defaults_to_empty(self):
        # [AI-Review][Medium] OrderUpdateData.parse_warnings по умолчанию пустой.
        # ARRANGE
        data = OrderUpdateData(
            order_id="order-1",
            order_number="TEST-001",
            status_1c="Отгружен",
        )

        # ASSERT
        assert data.parse_warnings == []

    def test_invalid_date_error_captured_in_import_result(self):
        # [AI-Review][Medium] Observability: ошибки парсинга дат попадают в ImportResult.errors.
        # ARRANGE — XML с некорректной датой
        xml_data = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<КоммерческаяИнформация ВерсияСхемы="3.1">'
            "    <Контейнер>"
            "        <Документ>"
            "            <Ид>order-1</Ид>"
            "            <Номер>FS-DATE-ERR-001</Номер>"
            "            <ЗначенияРеквизитов>"
            "                <ЗначениеРеквизита>"
            "                    <Наименование>СтатусЗаказа</Наименование>"
            "                    <Значение>Отгружен</Значение>"
            "                </ЗначениеРеквизита>"
            "                <ЗначениеРеквизита>"
            "                    <Наименование>ДатаОплаты</Наименование>"
            "                    <Значение>2026-02-30</Значение>"
            "                </ЗначениеРеквизита>"
            "            </ЗначенияРеквизитов>"
            "        </Документ>"
            "    </Контейнер>"
            "</КоммерческаяИнформация>"
        )

        service = OrderStatusImportService()

        with patch.object(service, "_bulk_fetch_orders", return_value=dict()):
            # ACT
            result = service.process(xml_data)

            # ASSERT — ошибка парсинга даты должна быть в errors
            assert result.processed == 1
            date_errors = [e for e in result.errors if "invalid paid_at date" in e.lower()]
            assert len(date_errors) == 1
            assert "2026-02-30" in date_errors[0]

    def test_parse_document_collects_date_warnings(self):
        # [AI-Review][Medium] _parse_document собирает предупреждения о датах.
        # ARRANGE
        xml_str = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Документ>"
            "    <Ид>order-100</Ид>"
            "    <Номер>FS-WARN-001</Номер>"
            "    <ЗначенияРеквизитов>"
            "        <ЗначениеРеквизита>"
            "            <Наименование>СтатусЗаказа</Наименование>"
            "            <Значение>Отгружен</Значение>"
            "        </ЗначениеРеквизита>"
            "        <ЗначениеРеквизита>"
            "            <Наименование>ДатаОплаты</Наименование>"
            "            <Значение>not-a-date</Значение>"
            "        </ЗначениеРеквизита>"
            "        <ЗначениеРеквизита>"
            "            <Наименование>ДатаОтгрузки</Наименование>"
            "            <Значение>also-invalid</Значение>"
            "        </ЗначениеРеквизита>"
            "    </ЗначенияРеквизитов>"
            "</Документ>"
        )

        import defusedxml.ElementTree as ET

        document = ET.fromstring(xml_str)

        service = OrderStatusImportService()

        # ACT
        result = service._parse_document(document)

        # ASSERT — обе ошибки парсинга дат должны быть собраны
        assert len(result.parse_warnings) == 2
        assert any("paid_at" in w for w in result.parse_warnings)
        assert any("shipped_at" in w for w in result.parse_warnings)

    def test_final_statuses_derived_from_order_statuses(self):
        # [AI-Review][Low] DRY: FINAL_STATUSES производное от ORDER_STATUSES.
        from apps.orders.constants import ALL_ORDER_STATUSES, FINAL_STATUSES, ORDER_STATUSES

        # ASSERT — все финальные статусы должны быть в ORDER_STATUSES
        order_status_codes = {status for status, _ in ORDER_STATUSES}
        for final_status in FINAL_STATUSES:
            assert final_status in order_status_codes, f"{final_status} not in ORDER_STATUSES"
            assert final_status in ALL_ORDER_STATUSES

    def test_active_statuses_derived_from_order_statuses(self):
        # [AI-Review][Low] DRY: ACTIVE_STATUSES производное от ORDER_STATUSES.
        from apps.orders.constants import ACTIVE_STATUSES, ALL_ORDER_STATUSES, ORDER_STATUSES

        # ASSERT — все активные статусы должны быть в ORDER_STATUSES
        order_status_codes = {status for status, _ in ORDER_STATUSES}
        for active_status in ACTIVE_STATUSES:
            assert active_status in order_status_codes, f"{active_status} not in ORDER_STATUSES"
            assert active_status in ALL_ORDER_STATUSES

    def test_all_order_statuses_covers_final_and_active(self):
        # [AI-Review][Low] DRY: ALL_ORDER_STATUSES = FINAL_STATUSES U ACTIVE_STATUSES.
        from apps.orders.constants import ACTIVE_STATUSES, ALL_ORDER_STATUSES, FINAL_STATUSES

        # ASSERT — объединение должно равняться ALL_ORDER_STATUSES
        combined = FINAL_STATUSES | ACTIVE_STATUSES
        assert combined == ALL_ORDER_STATUSES

    def test_data_integrity_order_id_pk_mismatch_detected(self):
        # [AI-Review][Medium] Data Integrity: Conflict order_id and pk detected.
        # ARRANGE — XML с order_id=order-999, но в БД заказ с order_number имеет pk=1
        order_number = "FS-CONFLICT-001"
        xml_data = build_test_xml(
            order_id="order-999",
            order_number=order_number,
            status="Отгружен",
        )

        mock_order = MagicMock()
        mock_order.order_number = order_number
        mock_order.pk = 1  # Не совпадает с order-999

        service = OrderStatusImportService()
        mock_cache = {f"num:{order_number}": mock_order}

        with patch.object(service, "_bulk_fetch_orders", return_value=mock_cache):
            # ACT
            result = service.process(xml_data)

            # ASSERT — должен быть обнаружен конфликт данных
            assert result.skipped_data_conflict == 1
            assert result.updated == 0
            conflict_errors = [e for e in result.errors if "conflict" in e.lower()]
            assert len(conflict_errors) == 1

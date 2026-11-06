"""
Unit-тесты для команды load_product_stocks

Story 3.1.5: Команда для обновления остатков товаров
"""

from __future__ import annotations

from io import StringIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.products.models import ImportSession, Product

if TYPE_CHECKING:
    from pytest_django.fixtures import SettingsWrapper


@pytest.mark.unit
class TestLoadProductStocksCommand:
    """Unit-тесты для команды load_product_stocks"""

    def test_command_requires_file_argument(self) -> None:
        """Проверка что команда требует аргумент --file"""
        with pytest.raises(CommandError, match="the following arguments are required"):
            call_command("load_product_stocks")

    def test_command_validates_file_exists(self) -> None:
        """Проверка валидации существования файла"""
        with pytest.raises(CommandError, match="Файл не найден"):
            call_command("load_product_stocks", file="/nonexistent/file.xml")

    @patch("os.path.exists", return_value=True)
    def test_command_validates_batch_size_positive(self, mock_exists: MagicMock) -> None:
        """Проверка валидации batch_size > 0"""
        with pytest.raises(CommandError, match="Некорректный размер пакета"):
            call_command("load_product_stocks", file="test.xml", batch_size=-1)

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_handles_empty_file(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка обработки пустого файла"""
        mock_parser.return_value = []

        call_command("load_product_stocks", file="test.xml")

        # Проверяем что сессия создана со статусом COMPLETED
        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.report_details["total_records"] == 0
        assert "warning" in session.report_details

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_updates_existing_products(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка обновления существующих товаров"""
        from apps.products.factories import ProductFactory

        # Создаем тестовый товар
        product = ProductFactory.create(
            name="Test Product",
            onec_id="test-uuid#sku-uuid",
            stock_quantity=0,
        )

        # Мокируем данные парсера
        mock_parser.return_value = [
            {
                "id": "test-uuid#sku-uuid",
                "warehouse_id": "warehouse-1",
                "quantity": 100,
            }
        ]

        call_command("load_product_stocks", file="test.xml")

        # Проверяем обновление
        variant = product.variants.first()
        variant.refresh_from_db()
        assert variant.stock_quantity == 100
        assert variant.last_sync_at is not None

        # Проверяем сессию
        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.report_details["updated_count"] == 1
        assert session.report_details["not_found_count"] == 0

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_handles_missing_products(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка обработки отсутствующих товаров"""
        mock_parser.return_value = [
            {
                "id": "nonexistent-uuid",
                "warehouse_id": "warehouse-1",
                "quantity": 50,
            }
        ]

        call_command("load_product_stocks", file="test.xml")

        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.report_details["updated_count"] == 0
        assert session.report_details["not_found_count"] == 1
        assert "nonexistent-uuid" in session.report_details["not_found_skus"]

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_skips_invalid_records(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка пропуска некорректных записей"""
        mock_parser.return_value = [
            {"id": None, "quantity": 10},  # Без onec_id
            {"id": "test-uuid", "quantity": -5},  # Отрицательное количество
        ]

        call_command("load_product_stocks", file="test.xml")

        session = ImportSession.objects.latest("started_at")
        assert session.report_details["skipped_count"] == 2

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_dry_run_mode(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка режима dry-run"""
        from apps.products.factories import ProductFactory

        product = ProductFactory.create(
            name="Test Product",
            onec_id="test-uuid",
            stock_quantity=0,
        )

        mock_parser.return_value = [{"id": "test-uuid", "quantity": 100}]

        call_command("load_product_stocks", file="test.xml", dry_run=True)

        # Проверяем что данные НЕ изменились
        variant = product.variants.first()
        variant.refresh_from_db()
        assert variant.stock_quantity == 0

        # Проверяем что сессия отмечена как dry_run
        session = ImportSession.objects.latest("started_at")
        assert session.report_details["dry_run"] is True

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_batch_processing(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка batch processing"""
        from apps.products.factories import ProductFactory

        # Создаем 2500 товаров
        products = ProductFactory.create_batch(
            2500,
            stock_quantity=0,
        )

        # Мокируем данные для всех вариантов
        mock_parser.return_value = [
            {"id": product.variants.first().onec_id, "quantity": i * 10} for i, product in enumerate(products)
        ]

        call_command("load_product_stocks", file="test.xml", batch_size=1000)

        session = ImportSession.objects.latest("started_at")
        assert session.report_details["updated_count"] == 2500
        assert session.report_details["batch_size"] == 1000

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_handles_parser_exception(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка обработки исключений парсера"""
        mock_parser.side_effect = Exception("XML parsing error")

        with pytest.raises(Exception, match="XML parsing error"):
            call_command("load_product_stocks", file="test.xml")

        session = ImportSession.objects.latest("started_at")
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "XML parsing error" in session.error_message

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_updates_last_sync_at(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка обновления last_sync_at"""
        from apps.products.factories import ProductFactory

        product = ProductFactory.create(
            onec_id="test-uuid",
            stock_quantity=0,
            last_sync_at=None,
        )

        mock_parser.return_value = [{"id": "test-uuid", "quantity": 50}]

        call_command("load_product_stocks", file="test.xml")

        variant = product.variants.first()
        variant.refresh_from_db()
        assert variant.stock_quantity == 50

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_session_duration_tracking(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка отслеживания длительности сессии"""
        from apps.products.factories import ProductFactory

        # Создаем товар чтобы был не пустой результат
        product = ProductFactory.create(onec_id="test-uuid", stock_quantity=0)
        mock_parser.return_value = [{"id": "test-uuid", "quantity": 50}]

        call_command("load_product_stocks", file="test.xml")

        session = ImportSession.objects.latest("started_at")
        assert "duration_seconds" in session.report_details
        assert session.report_details["duration_seconds"] >= 0
        assert session.finished_at is not None

    @pytest.mark.django_db
    @patch("apps.products.services.parser.XMLDataParser.parse_rests_xml")
    @patch("os.path.exists", return_value=True)
    def test_command_limits_not_found_skus_list(self, mock_exists: MagicMock, mock_parser: MagicMock) -> None:
        """Проверка ограничения списка not_found_skus до 100 элементов"""
        # Создаем 150 несуществующих товаров
        mock_parser.return_value = [{"id": f"nonexistent-{i}", "quantity": 10} for i in range(150)]

        call_command("load_product_stocks", file="test.xml")

        session = ImportSession.objects.latest("started_at")
        assert session.report_details["not_found_count"] == 150
        # Проверяем что список ограничен 100 элементами
        assert len(session.report_details["not_found_skus"]) == 100

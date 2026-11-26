"""
Тесты модели ImportSession.

Story 3.1: Оркестрация Асинхронного Импорта
"""

import pytest
from django.test import TestCase

from apps.products.models import ImportSession


@pytest.mark.unit
class TestImportSessionModel(TestCase):
    """Unit-тесты модели ImportSession."""

    def test_create_session_defaults(self) -> None:
        """Проверка дефолтных значений при создании сессии."""
        session = ImportSession.objects.create()

        assert session.status == ImportSession.ImportStatus.PENDING
        assert session.import_type == ImportSession.ImportType.CATALOG
        assert session.created_at is not None
        assert session.report == ""
        assert session.error_message == ""

    def test_create_session_with_custom_values(self) -> None:
        """Тест создания сессии с кастомными значениями."""
        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.IMAGES,
            status=ImportSession.ImportStatus.STARTED,
            celery_task_id="abc-123",
        )

        assert session.import_type == "images"
        assert session.get_import_type_display() == "Изображения товаров"
        assert session.status == "started"
        assert session.get_status_display() == "Начато"
        assert session.celery_task_id == "abc-123"

    def test_all_import_types_present(self) -> None:
        """Проверка наличия всех ожидаемых типов импорта."""
        expected_types = [
            "catalog",
            "variants",
            "attributes",
            "images",
            "stocks",
            "prices",
            "customers",
        ]
        choices_values = [choice[0] for choice in ImportSession.ImportType.choices]

        for expected_type in expected_types:
            assert expected_type in choices_values, f"Тип '{expected_type}' отсутствует в choices"

    def test_all_import_statuses_present(self) -> None:
        """Проверка наличия всех ожидаемых статусов."""
        expected_statuses = ["pending", "started", "in_progress", "completed", "failed"]
        choices_values = [choice[0] for choice in ImportSession.ImportStatus.choices]

        for expected_status in expected_statuses:
            assert expected_status in choices_values

    def test_str_representation(self) -> None:
        """Проверка строкового представления."""
        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.PENDING,
        )
        # Пример: "Каталог товаров - В очереди (2025-01-01...)"
        str_val = str(session)
        assert "Каталог товаров" in str_val
        assert "В очереди" in str_val

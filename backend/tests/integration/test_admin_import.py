"""
Integration тесты для admin display methods импорта.
"""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite

from apps.integrations.admin import ImportSessionAdmin
from apps.integrations.models import Session as ImportSession


@pytest.mark.integration
@pytest.mark.django_db
class TestImportSessionDisplayMethods:
    """Тесты для display methods в ImportSessionAdmin"""

    def setup_method(self) -> None:
        """Настройка перед каждым тестом"""
        self.admin = ImportSessionAdmin(ImportSession, AdminSite())

    def test_colored_status_display_completed(self) -> None:
        """Тест отображения статуса 'completed' с зеленым цветом"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
        )

        result = self.admin.colored_status(import_session)

        assert "green" in result
        assert "✅" in result
        assert "Завершено" in result

    def test_colored_status_display_in_progress(self) -> None:
        """Тест отображения статуса 'in_progress' с оранжевым цветом"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
        )

        result = self.admin.colored_status(import_session)

        assert "orange" in result
        assert "⏳" in result

    def test_colored_status_display_failed(self) -> None:
        """Тест отображения статуса 'failed' с красным цветом"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.FAILED,
        )

        result = self.admin.colored_status(import_session)

        assert "red" in result
        assert "❌" in result

    def test_duration_display_not_finished(self) -> None:
        """Тест отображения длительности для незавершенного импорта"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
        )

        result = self.admin.duration(import_session)

        assert result == "В процессе..."

    def test_progress_display_with_data(self) -> None:
        """Тест отображения прогресса с реальными данными"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report_details={"total_items": 100, "processed_items": 50},
        )

        result = self.admin.progress_display(import_session)

        assert "<progress" in result
        assert "50%" in result or "50.0%" in result
        assert "50/100" in result

    def test_progress_display_no_data(self) -> None:
        """Тест отображения прогресса без данных"""
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
        )

        result = self.admin.progress_display(import_session)

        assert result == "-"

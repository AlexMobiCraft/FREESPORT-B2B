"""
Unit тесты для admin actions в products app

Проверяет отдельные методы ImportSessionAdmin в изоляции:
- duration calculation
- progress_display rendering
- colored_status rendering
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

import pytest
from django.contrib.admin.sites import AdminSite
from django.utils import timezone

from apps.integrations.admin import ImportSessionAdmin
from apps.integrations.models import Session as ImportSession

if TYPE_CHECKING:
    pass


@pytest.mark.unit
@pytest.mark.django_db
class TestImportSessionAdminDuration:
    """Unit тесты для метода duration"""

    def setup_method(self) -> None:
        """Настройка перед каждым тестом"""
        self.admin = ImportSessionAdmin(ImportSession, AdminSite())

    def test_duration_completed_import_minutes(self) -> None:
        """
        Тест расчета длительности для завершенного импорта (минуты).

        Проверяет что длительность корректно вычисляется
        для импорта длительностью 5 минут.
        """
        # Arrange
        started = timezone.now()
        finished = started + timedelta(minutes=5)

        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
            started_at=started,
            finished_at=finished,
        )

        # Act
        result = self.admin.duration(import_session)

        # Assert
        assert "5.0 мин" in result

    def test_duration_completed_import_seconds(self) -> None:
        """
        Тест расчета длительности для быстрого импорта (секунды).

        Проверяет что для импорта длительностью < 1 минуты
        показывается время в секундах.
        """
        # Arrange
        started = timezone.now()
        finished = started + timedelta(seconds=30)

        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
            started_at=started,
            finished_at=finished,
        )

        # Act
        result = self.admin.duration(import_session)

        # Assert
        assert "30 сек" in result or "30.0 сек" in result

    def test_duration_in_progress(self) -> None:
        """
        Тест отображения длительности для импорта в процессе.

        Проверяет что для незавершенного импорта
        показывается "В процессе...".
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            started_at=timezone.now(),
            finished_at=None,
        )

        # Act
        result = self.admin.duration(import_session)

        # Assert
        assert result == "В процессе..."

    def test_duration_not_started(self) -> None:
        """
        Тест отображения длительности для импорта со статусом STARTED.

        Проверяет что для импорта со статусом STARTED
        (который технически уже начат, т.к. started_at установлен auto_now_add)
        показывается "В процессе...".

        Note: started_at устанавливается автоматически Django при создании,
        поэтому технически невозможно создать ImportSession без started_at.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
            finished_at=None,
        )

        # Act
        result = self.admin.duration(import_session)

        # Assert
        assert result == "В процессе..."


@pytest.mark.unit
@pytest.mark.django_db
class TestImportSessionAdminProgressDisplay:
    """Unit тесты для метода progress_display"""

    def setup_method(self) -> None:
        """Настройка перед каждым тестом"""
        self.admin = ImportSessionAdmin(ImportSession, AdminSite())

    def test_progress_display_50_percent(self) -> None:
        """
        Тест отображения прогресса 50%.

        Проверяет корректное отображение progress bar
        для импорта с 50% прогрессом.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report_details={"total_items": 100, "processed_items": 50},
        )

        # Act
        result = self.admin.progress_display(import_session)

        # Assert
        assert "<progress" in result
        assert 'value="50.0"' in result or 'value="50"' in result
        assert "50%" in result
        assert "50/100" in result

    def test_progress_display_100_percent(self) -> None:
        """
        Тест отображения прогресса 100%.

        Проверяет отображение для полностью завершенного импорта.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report_details={"total_items": 200, "processed_items": 200},
        )

        # Act
        result = self.admin.progress_display(import_session)

        # Assert
        assert "<progress" in result
        assert "100%" in result
        assert "200/200" in result

    def test_progress_display_zero_total(self) -> None:
        """
        Тест отображения прогресса с нулевым total_items.

        Проверяет что не происходит division by zero
        и показывается "-".
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report_details={"total_items": 0, "processed_items": 0},
        )

        # Act
        result = self.admin.progress_display(import_session)

        # Assert
        assert result == "-"

    def test_progress_display_no_report_details(self) -> None:
        """
        Тест отображения прогресса без report_details.

        Проверяет что показывается "-" если нет данных о прогрессе.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report_details={},
        )

        # Act
        result = self.admin.progress_display(import_session)

        # Assert
        assert result == "-"

    def test_progress_display_completed_status(self) -> None:
        """
        Тест отображения прогресса для завершенного импорта.

        Проверяет что для статуса 'completed' не показывается
        progress bar (только для 'in_progress').
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
            report_details={"total_items": 100, "processed_items": 100},
        )

        # Act
        result = self.admin.progress_display(import_session)

        # Assert
        assert result == "-"


@pytest.mark.unit
@pytest.mark.django_db
class TestImportSessionAdminColoredStatus:
    """Unit тесты для метода colored_status"""

    def setup_method(self) -> None:
        """Настройка перед каждым тестом"""
        self.admin = ImportSessionAdmin(ImportSession, AdminSite())

    def test_colored_status_completed(self) -> None:
        """
        Тест отображения статуса 'completed'.

        Проверяет зеленый цвет и иконку ✅.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
        )

        # Act
        result = self.admin.colored_status(import_session)

        # Assert
        assert "green" in result
        assert "✅" in result
        assert "Завершено" in result or "completed" in result.lower()

    def test_colored_status_in_progress(self) -> None:
        """
        Тест отображения статуса 'in_progress'.

        Проверяет оранжевый цвет и иконку ⏳.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
        )

        # Act
        result = self.admin.colored_status(import_session)

        # Assert
        assert "orange" in result
        assert "⏳" in result

    def test_colored_status_failed(self) -> None:
        """
        Тест отображения статуса 'failed'.

        Проверяет красный цвет и иконку ❌.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.FAILED,
        )

        # Act
        result = self.admin.colored_status(import_session)

        # Assert
        assert "red" in result
        assert "❌" in result

    def test_colored_status_started(self) -> None:
        """
        Тест отображения статуса 'started'.

        Проверяет серый цвет и иконку ⏸️.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
        )

        # Act
        result = self.admin.colored_status(import_session)

        # Assert
        assert "gray" in result
        assert "⏸️" in result

    def test_colored_status_html_format(self) -> None:
        """
        Тест что результат является валидным HTML.

        Проверяет наличие тега span со стилями.
        """
        # Arrange
        import_session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.COMPLETED,
        )

        # Act
        result = self.admin.colored_status(import_session)

        # Assert
        assert "<span" in result
        assert "style=" in result
        assert "color:" in result
        assert "</span>" in result


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeAdminMergeAttributes:
    """Integration тесты для merge_attributes admin action"""

    def setup_method(self) -> None:
        """Настройка перед каждым тестом"""
        from django.contrib.admin.sites import AdminSite

        from apps.products.admin import AttributeAdmin
        from apps.products.models import Attribute

        self.admin = AttributeAdmin(Attribute, AdminSite())

    def test_merge_requires_minimum_two_attributes(self) -> None:
        """
        Тест что объединение требует минимум 2 атрибута.

        Проверяет что при выборе одного атрибута показывается предупреждение.
        """
        from unittest.mock import MagicMock

        from apps.products.models import Attribute

        # Arrange
        attr = Attribute.objects.create(name="TestAttr-Single", type="Справочник")
        queryset = Attribute.objects.filter(pk=attr.pk)
        request = MagicMock()
        request.POST = {}

        # Act
        result = self.admin.merge_attributes(request, queryset)

        # Assert
        assert result is None
        request.assert_not_called  # Не должно быть вызовов render

    def test_merge_transfers_mappings(self) -> None:
        """
        Тест переноса маппингов 1С при объединении атрибутов.
        """
        import time
        import uuid
        from unittest.mock import MagicMock

        from django.contrib.admin.models import LogEntry
        from django.contrib.auth import get_user_model

        from apps.products.models import Attribute, Attribute1CMapping

        User = get_user_model()

        # Arrange - уникальные имена для теста
        suffix = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

        target_attr = Attribute.objects.create(name=f"TargetAttr-{suffix}", type="Справочник")
        source_attr = Attribute.objects.create(name=f"SourceAttr-{suffix}", type="Справочник")

        Attribute1CMapping.objects.create(
            attribute=source_attr,
            onec_id=f"source-mapping-{suffix}",
            onec_name="Source Mapping",
            source="goods",
        )

        queryset = Attribute.objects.filter(pk__in=[target_attr.pk, source_attr.pk])

        # Mock request с user для LogEntry
        user = User.objects.create_user(
            email=f"test-merge-{suffix}@example.com",
            password="testpass123",
            phone=f"+70000{suffix[:6]}",
        )
        request = MagicMock()
        request.POST = {"apply": "1", "target_attribute": str(target_attr.pk)}
        request.user = user
        request.get_full_path.return_value = "/admin/products/attribute/"

        # Act
        from apps.products.forms import MergeAttributesActionForm

        form = MergeAttributesActionForm(request.POST)
        assert form.is_valid(), f"Form errors: {form.errors}"

        self.admin.merge_attributes(request, queryset)

        # Assert
        # Маппинг должен быть перенесен на target
        assert Attribute1CMapping.objects.filter(attribute=target_attr, onec_id=f"source-mapping-{suffix}").exists()

        # Source атрибут должен быть удален
        assert not Attribute.objects.filter(pk=source_attr.pk).exists()

        # LogEntry должен быть создан
        log_entries = LogEntry.objects.filter(object_id=str(target_attr.pk))
        assert log_entries.exists()

    def test_merge_deduplicates_values(self) -> None:
        """
        Тест дедупликации значений при объединении атрибутов.
        """
        import time
        import uuid
        from unittest.mock import MagicMock

        from django.contrib.auth import get_user_model

        from apps.products.models import Attribute, AttributeValue, AttributeValue1CMapping

        User = get_user_model()

        # Arrange
        suffix = f"{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"

        target_attr = Attribute.objects.create(name=f"Target-{suffix}", type="Справочник")
        source_attr = Attribute.objects.create(name=f"Source-{suffix}", type="Справочник")

        # Одинаковые значения в обоих атрибутах
        target_value = AttributeValue.objects.create(attribute=target_attr, value=f"Red-{suffix}")
        source_value = AttributeValue.objects.create(
            attribute=source_attr, value=f"red-{suffix}"  # Same normalized_value
        )

        # Маппинг для source value
        AttributeValue1CMapping.objects.create(
            attribute_value=source_value,
            onec_id=f"value-mapping-{suffix}",
            onec_value="red",
            source="goods",
        )

        queryset = Attribute.objects.filter(pk__in=[target_attr.pk, source_attr.pk])

        user = User.objects.create_user(
            email=f"test-dedup-{suffix}@example.com",
            password="testpass123",
            phone=f"+70001{suffix[:6]}",
        )
        request = MagicMock()
        request.POST = {"apply": "1", "target_attribute": str(target_attr.pk)}
        request.user = user
        request.get_full_path.return_value = "/admin/products/attribute/"

        # Act
        self.admin.merge_attributes(request, queryset)

        # Assert
        # Должно остаться только одно значение у target
        assert target_attr.values.count() == 1

        # Маппинг source value должен быть перенесен на target value
        assert AttributeValue1CMapping.objects.filter(
            attribute_value=target_value, onec_id=f"value-mapping-{suffix}"
        ).exists()

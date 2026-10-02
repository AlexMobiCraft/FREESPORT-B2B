"""
Unit-тесты для admin интерфейса приложения integrations
"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.http import HttpRequest
from django.test import RequestFactory

from apps.integrations.admin import ImportSessionAdmin
from apps.integrations.models import Session

User = get_user_model()


@pytest.mark.django_db
class TestImportSessionAdmin:
    """Тесты для ImportSessionAdmin"""

    @pytest.fixture
    def admin_site(self):
        """Создание экземпляра AdminSite"""
        return AdminSite()

    @pytest.fixture
    def import_session_admin(self, admin_site):
        """Создание экземпляра ImportSessionAdmin"""
        return ImportSessionAdmin(Session, admin_site)

    @pytest.fixture
    def superuser(self):
        """Создание суперпользователя для тестов"""
        return User.objects.create_superuser(email="admin@test.com", password="testpass123")

    @pytest.fixture
    def request_factory(self):
        """Фабрика для создания HTTP запросов"""
        return RequestFactory()

    @pytest.fixture
    def mock_request(self, request_factory, superuser):
        """Создание mock HTTP запроса с аутентифицированным пользователем"""
        request = request_factory.get("/admin/integrations/session/")
        request.user = superuser
        return request

    @pytest.fixture
    def import_session(self):
        """Создание тестовой сессии импорта"""
        return Session.objects.create(import_type="catalog", status="completed")

    def test_colored_status_display(self, import_session_admin, import_session):
        """
        Тест: отображение цветного статуса

        Проверяет корректность форматирования статуса с иконками.
        """
        # Act
        result = import_session_admin.colored_status(import_session)

        # Assert
        assert "✅" in result  # Иконка для completed
        assert "green" in result  # Цвет для completed
        assert "Завершено" in result  # Текст статуса

    def test_duration_calculation_completed(self, import_session_admin):
        """
        Тест: расчет длительности для завершенного импорта

        Проверяет корректность расчета времени выполнения.
        """
        # Arrange
        from datetime import timedelta

        from django.utils import timezone

        session = Session.objects.create(import_type="catalog", status="completed")
        session.started_at = timezone.now() - timedelta(minutes=5)
        session.finished_at = timezone.now()
        session.save()

        # Act
        result = import_session_admin.duration(session)

        # Assert
        assert "мин" in result
        assert "5" in result

    def test_duration_calculation_in_progress(self, import_session_admin):
        """
        Тест: отображение длительности для импорта в процессе
        """
        # Arrange
        session = Session.objects.create(import_type="catalog", status="in_progress")

        # Act
        result = import_session_admin.duration(session)

        # Assert
        assert "В процессе..." in result

    def test_progress_display_with_data(self, import_session_admin):
        """
        Тест: отображение прогресс-бара с данными
        """
        # Arrange
        session = Session.objects.create(
            import_type="catalog",
            status="in_progress",
            report_details={"total_items": 100, "processed_items": 50},
        )

        # Act
        result = import_session_admin.progress_display(session)

        # Assert
        assert "progress" in result.lower()
        assert "50%" in result
        assert "50/100" in result

    def test_progress_display_without_data(self, import_session_admin):
        """
        Тест: отображение прогресса без данных
        """
        # Arrange
        session = Session.objects.create(import_type="catalog", status="completed")

        # Act
        result = import_session_admin.progress_display(session)

        # Assert
        assert result == "-"

    # ========================================================================
    # Тесты для read-only режима (Story 9.7)
    # ========================================================================

    def test_has_add_permission_returns_false(self, import_session_admin, mock_request):
        """
        Тест: has_add_permission возвращает False

        Story 9.7: Страница сессий импорта должна быть read-only.
        Создание новых сессий через admin запрещено.
        """
        # Act
        result = import_session_admin.has_add_permission(mock_request)

        # Assert
        assert result is False, (
            "Создание новых сессий импорта через admin должно быть запрещено. "
            "Сессии создаются автоматически через /admin/integrations/import_1c/"
        )

    def test_has_change_permission_returns_false(self, import_session_admin, mock_request, import_session):
        """
        Тест: has_change_permission возвращает False

        Story 9.7: Редактирование сессий импорта запрещено для
        сохранения целостности данных аудита.
        """
        # Act - без объекта
        result_without_obj = import_session_admin.has_change_permission(mock_request)

        # Act - с объектом
        result_with_obj = import_session_admin.has_change_permission(mock_request, import_session)

        # Assert
        assert result_without_obj is False, "Редактирование сессий импорта должно быть запрещено (без объекта)"
        assert result_with_obj is False, "Редактирование сессий импорта должно быть запрещено (с объектом)"

    def test_has_delete_permission_returns_true(self, import_session_admin, mock_request, import_session):
        """
        Тест: has_delete_permission возвращает True

        Story 9.7: Удаление разрешено для периодического cleanup:
        - Удаление тестовых/ошибочных сессий
        - Периодический cleanup старых данных (>6 месяцев)
        - Предотвращение бесконечного роста БД
        """
        # Act - без объекта
        result_without_obj = import_session_admin.has_delete_permission(mock_request)

        # Act - с объектом
        result_with_obj = import_session_admin.has_delete_permission(mock_request, import_session)

        # Assert
        assert result_without_obj is True, "Удаление сессий должно быть разрешено для cleanup (без объекта)"
        assert result_with_obj is True, "Удаление сессий должно быть разрешено для cleanup (с объектом)"

    def test_actions_list_is_empty(self, import_session_admin):
        """
        Тест: actions список пустой

        Story 9.7: Admin action "trigger_selective_import" удален.
        Страница только для просмотра, без возможности запуска импорта.
        """
        # Act
        actions = import_session_admin.actions

        # Assert
        assert actions == [], (
            "Admin actions должны быть пустыми. " "Запуск импорта выполняется через /admin/integrations/import_1c/"
        )

    def test_celery_task_status_method_exists(self, import_session_admin):
        """
        Тест: метод celery_task_status существует и работает

        Story 9.7: Функционал мониторинга Celery задач должен быть сохранен.
        """
        # Arrange
        session = Session.objects.create(
            import_type="catalog",
            status="in_progress",
            celery_task_id="test-task-id-123",
        )

        # Act - AsyncResult импортируется внутри метода
        with patch("celery.result.AsyncResult") as mock_async_result:
            mock_result = Mock()
            mock_result.state = "STARTED"
            mock_async_result.return_value = mock_result

            result = import_session_admin.celery_task_status(session)

        # Assert
        assert result is not None
        assert "▶️" in result  # Иконка для STARTED
        assert "blue" in result  # Цвет для STARTED
        assert "Выполняется" in result

    def test_celery_task_status_without_task_id(self, import_session_admin, import_session):
        """
        Тест: celery_task_status без task_id возвращает "-"
        """
        # Arrange
        import_session.celery_task_id = ""
        import_session.save()

        # Act
        result = import_session_admin.celery_task_status(import_session)

        # Assert
        assert "-" in result
        assert "gray" in result

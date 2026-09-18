"""
Unit тесты для views страницы импорта из 1С.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import RequestFactory
from django.urls import reverse

from apps.integrations.views import (
    _create_and_run_import,
    _handle_import_request,
    _validate_dependencies,
    import_from_1c_view,
)
from apps.products.models import ImportSession, Product

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestValidateDependencies:
    """Тесты для функции валидации зависимостей."""

    def test_validate_catalog_no_requirements(self):
        """Тест: каталог не требует зависимостей."""
        is_valid, error_message = _validate_dependencies(["catalog"])
        assert is_valid is True
        assert error_message == ""

    def test_validate_customers_no_requirements(self):
        """Тест: клиенты не требуют зависимостей."""
        is_valid, error_message = _validate_dependencies(["customers"])
        assert is_valid is True
        assert error_message == ""

    def test_validate_stocks_requires_products(self, db):
        """Тест: остатки требуют наличия товаров в БД."""
        # БД пуста
        is_valid, error_message = _validate_dependencies(["stocks"])
        assert is_valid is False
        assert "каталог товаров пуст" in error_message

    def test_validate_prices_requires_products(self, db):
        """Тест: цены требуют наличия товаров в БД."""
        # БД пуста
        is_valid, error_message = _validate_dependencies(["prices"])
        assert is_valid is False
        assert "каталог товаров пуст" in error_message

    def test_validate_stocks_with_existing_products(self, product_factory):
        """Тест: остатки проходят валидацию если товары есть."""
        # Создаем товар
        product_factory()
        is_valid, error_message = _validate_dependencies(["stocks"])
        assert is_valid is True
        assert error_message == ""

    def test_validate_prices_with_existing_products(self, product_factory):
        """Тест: цены проходят валидацию если товары есть."""
        # Создаем товар
        product_factory()
        is_valid, error_message = _validate_dependencies(["prices"])
        assert is_valid is True
        assert error_message == ""


@pytest.mark.unit
@pytest.mark.django_db
class TestCreateAndRunImport:
    """Тесты для функции создания и запуска импорта."""

    @patch("apps.integrations.views.Path")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.settings")
    def test_create_catalog_import_session(self, mock_settings, mock_task, mock_path):
        """Тест: создание сессии импорта каталога."""
        # Setup
        mock_settings.ONEC_DATA_DIR = "/path/to/data"
        mock_task.delay.return_value = MagicMock(id="test-task-id")
        # Mock Path to always return exists=True
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, x: mock_path_instance
        mock_path.return_value = mock_path_instance

        # Execute
        session = _create_and_run_import("catalog")

        # Assert
        assert session.import_type == ImportSession.ImportType.CATALOG
        assert session.status == ImportSession.ImportStatus.STARTED
        assert session.celery_task_id == "test-task-id"
        mock_task.delay.assert_called_once_with(["catalog"])

    @patch("apps.integrations.views.Path")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.settings")
    def test_create_stocks_import_session(self, mock_settings, mock_task, mock_path):
        """Тест: создание сессии импорта остатков."""
        # Setup
        mock_settings.ONEC_DATA_DIR = "/path/to/data"
        mock_task.delay.return_value = MagicMock(id="test-task-id-2")
        # Mock Path to always return exists=True
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, x: mock_path_instance
        mock_path.return_value = mock_path_instance

        # Execute
        session = _create_and_run_import("stocks")

        # Assert
        assert session.import_type == ImportSession.ImportType.STOCKS
        assert session.celery_task_id == "test-task-id-2"
        mock_task.delay.assert_called_once_with(["stocks"])

    @patch("apps.integrations.views.Path")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.settings")
    def test_create_prices_import_session(self, mock_settings, mock_task, mock_path):
        """Тест: создание сессии импорта цен."""
        mock_settings.ONEC_DATA_DIR = "/path/to/data"
        mock_task.delay.return_value = MagicMock(id="test-task-id-3")
        # Mock Path to always return exists=True
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, x: mock_path_instance
        mock_path.return_value = mock_path_instance

        session = _create_and_run_import("prices")

        assert session.import_type == ImportSession.ImportType.PRICES
        mock_task.delay.assert_called_once_with(["prices"])

    @patch("apps.integrations.views.Path")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.settings")
    def test_create_customers_import_session(self, mock_settings, mock_task, mock_path):
        """Тест: создание сессии импорта клиентов."""
        mock_settings.ONEC_DATA_DIR = "/path/to/data"
        mock_task.delay.return_value = MagicMock(id="test-task-id-4")
        # Mock Path to always return exists=True
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = True
        mock_path_instance.__truediv__ = lambda self, x: mock_path_instance
        mock_path.return_value = mock_path_instance

        session = _create_and_run_import("customers")

        assert session.import_type == ImportSession.ImportType.CUSTOMERS
        mock_task.delay.assert_called_once_with(["customers"])

    @patch("apps.integrations.views.settings")
    def test_create_import_raises_without_onec_data_dir(self, mock_settings):
        """Тест: исключение если ONEC_DATA_DIR не настроен."""
        mock_settings.ONEC_DATA_DIR = None

        with pytest.raises(ValueError, match="ONEC_DATA_DIR не найдена"):
            _create_and_run_import("catalog")


@pytest.mark.unit
@pytest.mark.django_db
class TestImportFrom1CView:
    """Тесты для главного view страницы импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def request_factory(self):
        """RequestFactory для создания mock запросов."""
        return RequestFactory()

    def test_get_request_displays_form(self, admin_user, request_factory):
        """Тест: GET запрос отображает форму выбора типа импорта."""
        # Setup
        request = request_factory.get("/admin/integrations/import_1c/")
        request.user = admin_user

        # Execute
        response = import_from_1c_view(request)

        # Assert
        assert response.status_code == 200
        assert "import_types" in response.context_data
        assert len(response.context_data["import_types"]) == 7

        # Проверяем структуру типов импорта
        import_types = response.context_data["import_types"]
        assert any(t["value"] == "catalog" for t in import_types)
        assert any(t["value"] == "stocks" for t in import_types)
        assert any(t["value"] == "prices" for t in import_types)
        assert any(t["value"] == "customers" for t in import_types)

    def test_get_request_includes_admin_context(self, admin_user, request_factory):
        """Тест: GET запрос включает контекст Django Admin."""
        request = request_factory.get("/admin/integrations/import_1c/")
        request.user = admin_user

        response = import_from_1c_view(request)

        assert "site_header" in response.context_data
        assert "site_title" in response.context_data
        assert response.context_data["title"] == "Импорт данных из 1С"


@pytest.mark.unit
@pytest.mark.django_db
class TestHandleImportRequest:
    """Тесты для обработки POST запроса импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def request_factory(self):
        """RequestFactory для создания mock запросов."""
        return RequestFactory()

    def test_post_without_import_type_shows_warning(self, admin_user, request_factory):
        """Тест: POST без типа импорта показывает предупреждение."""
        # Setup
        request = request_factory.post("/admin/integrations/import_1c/")
        request.user = admin_user
        request._messages = MagicMock()

        # Execute
        response = _handle_import_request(request)

        # Assert
        assert response.status_code == 302  # Redirect
        assert "/admin/integrations/import_1c/" in response.url

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views._create_and_run_import")
    @patch("apps.integrations.views._validate_dependencies")
    def test_post_with_valid_catalog_launches_import(
        self,
        mock_validate,
        mock_create_import,
        mock_redis,
        admin_user,
        request_factory,
    ):
        """Тест: POST с валидным типом запускает импорт."""
        # Setup
        mock_validate.return_value = (True, "")
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        mock_session = MagicMock()
        mock_session.pk = 123
        mock_session.celery_task_id = "task-123"
        mock_create_import.return_value = mock_session

        request = request_factory.post("/admin/integrations/import_1c/", {"import_type": "catalog"})
        request.user = admin_user
        request._messages = MagicMock()

        # Execute
        response = _handle_import_request(request)

        # Assert
        assert response.status_code == 302
        assert "/admin/integrations/session/" in response.url
        mock_validate.assert_called_once_with(["catalog"])
        mock_create_import.assert_called_once_with("catalog")
        mock_lock.release.assert_called_once()

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views._validate_dependencies")
    def test_post_with_active_lock_shows_warning(self, mock_validate, mock_redis, admin_user, request_factory):
        """Тест: POST при активном lock показывает предупреждение."""
        # Setup
        mock_validate.return_value = (True, "")
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False  # Lock занят
        mock_redis.return_value.lock.return_value = mock_lock

        request = request_factory.post("/admin/integrations/import_1c/", {"import_type": "catalog"})
        request.user = admin_user
        request._messages = MagicMock()

        # Execute
        response = _handle_import_request(request)

        # Assert
        assert response.status_code == 302
        assert "/admin/integrations/import_1c/" in response.url

    @patch("apps.integrations.views._validate_dependencies")
    def test_post_with_invalid_dependencies_shows_error(self, mock_validate, admin_user, request_factory):
        """Тест: POST с невалидными зависимостями показывает ошибку."""
        # Setup
        mock_validate.return_value = (False, "Каталог товаров пуст")

        request = request_factory.post("/admin/integrations/import_1c/", {"import_type": "stocks"})
        request.user = admin_user
        request._messages = MagicMock()

        # Execute
        response = _handle_import_request(request)

        # Assert
        assert response.status_code == 302
        assert "/admin/integrations/import_1c/" in response.url
        mock_validate.assert_called_once_with(["stocks"])

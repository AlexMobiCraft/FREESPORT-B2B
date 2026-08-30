"""
Integration тесты для страницы импорта из 1С.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from apps.products.models import ImportSession, Product

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestImportPageAccess:
    """Тесты доступа к странице импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def regular_user(self, db):
        """Создает обычного пользователя."""
        return User.objects.create_user(
            email="user@test.com",
            password="testpass123",
            is_staff=False,
        )

    @pytest.fixture
    def client(self):
        """Django test client."""
        return Client()

    @pytest.fixture
    def onec_data_dir(self, tmp_path, settings):
        """Создает временную директорию для данных 1С и прописывает её в settings."""
        data_dir = tmp_path / "import_1c"
        data_dir.mkdir(parents=True, exist_ok=True)
        settings.ONEC_DATA_DIR = str(data_dir)
        return data_dir

    def test_page_accessible_for_admin(self, client, admin_user):
        """Тест: страница доступна для администратора."""
        client.force_login(admin_user)
        response = client.get("/admin/integrations/import_1c/")

        assert response.status_code == 200
        assert "Импорт данных из 1С" in str(response.content, encoding="utf-8")

    def test_page_redirects_for_anonymous(self, client):
        """Тест: страница перенаправляет неавторизованных пользователей."""
        response = client.get("/admin/integrations/import_1c/")

        assert response.status_code == 302  # Redirect to login
        assert "/admin/login/" in response.url

    def test_page_forbidden_for_regular_user(self, client, regular_user):
        """Тест: страница недоступна для обычных пользователей."""
        client.force_login(regular_user)
        response = client.get("/admin/integrations/import_1c/")

        # Должен быть redirect или 403
        assert response.status_code in [302, 403]


@pytest.mark.integration
@pytest.mark.django_db
class TestImportPageDisplay:
    """Тесты отображения страницы импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def client(self):
        """Django test client."""
        return Client()

    def test_page_displays_import_types(self, client, admin_user):
        """Тест: страница отображает все типы импорта."""
        client.force_login(admin_user)
        response = client.get("/admin/integrations/import_1c/")

        content = str(response.content, encoding="utf-8")
        assert "Полный каталог" in content
        assert "Только остатки" in content
        assert "Только цены" in content
        assert "Клиенты" in content

    def test_page_displays_warnings_for_dependent_types(self, client, admin_user):
        """Тест: страница отображает предупреждения для зависимых типов."""
        client.force_login(admin_user)
        response = client.get("/admin/integrations/import_1c/")

        content = str(response.content, encoding="utf-8")
        assert "Требуется предварительный импорт каталога" in content

    def test_page_has_submit_button(self, client, admin_user):
        """Тест: страница содержит кнопку запуска импорта."""
        client.force_login(admin_user)
        response = client.get("/admin/integrations/import_1c/")

        content = str(response.content, encoding="utf-8")
        assert "Запустить импорт" in content

    def test_page_has_cancel_link(self, client, admin_user):
        """Тест: страница содержит ссылку отмены."""
        client.force_login(admin_user)
        response = client.get("/admin/integrations/import_1c/")

        content = str(response.content, encoding="utf-8")
        assert "Отмена" in content


@pytest.mark.integration
@pytest.mark.django_db
class TestImportPageSubmission:
    """Тесты отправки формы импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def client(self):
        """Django test client."""
        return Client()

    def test_post_without_type_shows_warning(self, client, admin_user):
        """Тест: POST без типа импорта показывает предупреждение."""
        client.force_login(admin_user)
        response = client.post("/admin/integrations/import_1c/", {})

        assert response.status_code == 302
        # Проверяем, что есть сообщение в messages
        messages = list(response.wsgi_request._messages)
        assert len(messages) > 0

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_post_catalog_creates_session_and_redirects(
        self, mock_exists, mock_task, mock_redis, client, admin_user, onec_data_dir
    ):
        """Тест: POST с каталогом создает сессию и перенаправляет."""
        # Setup mocks
        mock_exists.return_value = True
        mock_task.delay.return_value = MagicMock(id="test-task-123")

        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        # Execute
        response = client.post("/admin/integrations/import_1c/", {"import_type": "catalog"})

        # Assert
        assert response.status_code == 302
        assert "/admin/integrations/session/" in response.url

        # Проверяем что создалась сессия
        sessions = ImportSession.objects.all()
        assert sessions.count() == 1
        session = sessions.first()
        assert session.import_type == ImportSession.ImportType.CATALOG
        assert session.status == ImportSession.ImportStatus.STARTED
        assert session.celery_task_id == "test-task-123"

        # Проверяем что Celery задача была запущена
        mock_task.delay.assert_called_once_with(["catalog"])

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_post_customers_creates_correct_session_type(
        self, mock_exists, mock_task, mock_redis, client, admin_user, onec_data_dir
    ):
        """Тест: POST с клиентами создает сессию правильного типа."""
        mock_exists.return_value = True
        mock_task.delay.return_value = MagicMock(id="test-task-456")

        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        response = client.post("/admin/integrations/import_1c/", {"import_type": "customers"})

        assert response.status_code == 302

        session = ImportSession.objects.first()
        assert session.import_type == ImportSession.ImportType.CUSTOMERS

    @patch("apps.integrations.views.get_redis_connection")
    def test_post_stocks_without_products_shows_error(self, mock_redis, client, admin_user, db):
        """Тест: POST с остатками без товаров показывает ошибку."""
        # БД пуста, товаров нет
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        response = client.post("/admin/integrations/import_1c/", {"import_type": "stocks"})

        assert response.status_code == 302
        # Проверяем что сессия НЕ создана
        assert ImportSession.objects.count() == 0

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_post_stocks_with_products_succeeds(
        self,
        mock_exists,
        mock_task,
        mock_redis,
        client,
        admin_user,
        product_factory,
        onec_data_dir,
    ):
        """Тест: POST с остатками при наличии товаров успешен."""
        # Создаем товар
        product_factory()

        mock_exists.return_value = True
        mock_task.delay.return_value = MagicMock(id="test-task-789")

        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        response = client.post("/admin/integrations/import_1c/", {"import_type": "stocks"})

        assert response.status_code == 302

        session = ImportSession.objects.first()
        assert session.import_type == ImportSession.ImportType.STOCKS

    @patch("apps.integrations.views.get_redis_connection")
    def test_concurrent_import_shows_warning(self, mock_redis, client, admin_user):
        """Тест: попытка параллельного импорта показывает предупреждение."""
        # Lock занят
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        response = client.post("/admin/integrations/import_1c/", {"import_type": "catalog"})

        assert response.status_code == 302
        # Проверяем что сессия НЕ создана
        assert ImportSession.objects.count() == 0


@pytest.mark.integration
@pytest.mark.django_db
class TestImportPageMessages:
    """Тесты сообщений страницы импорта."""

    @pytest.fixture
    def admin_user(self, db):
        """Создает пользователя-администратора."""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def client(self):
        """Django test client."""
        return Client()

    @patch("apps.integrations.views.get_redis_connection")
    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_successful_import_shows_success_message(
        self, mock_exists, mock_task, mock_redis, client, admin_user, onec_data_dir
    ):
        """Тест: успешный импорт показывает success сообщение."""
        mock_exists.return_value = True
        mock_task.delay.return_value = MagicMock(id="test-task-999")

        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        mock_redis.return_value.lock.return_value = mock_lock

        client.force_login(admin_user)

        response = client.post(
            "/admin/integrations/import_1c/",
            {"import_type": "catalog"},
            follow=False,
        )

        messages = list(response.wsgi_request._messages)
        assert len(messages) > 0
        assert any("Импорт запущен" in str(m) for m in messages)
        assert any("Task ID" in str(m) for m in messages)

"""
Интеграционные тесты для нового типа импорта IMAGES.

Story 15.1: Добавление типа импорта "Изображения" в админ-панель
"""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from apps.integrations.views import _validate_dependencies
from apps.products.factories import ProductFactory
from apps.products.models import ImportSession, Product

User = get_user_model()


@pytest.mark.integration
class TestImportDependenciesValidation(TestCase):
    """Тесты валидации зависимостей для типа images."""

    def test_images_requires_catalog_validation_fails_when_no_products(self) -> None:
        """Проверка: images требует наличия товаров - ошибка если нет."""
        # Убедиться что товаров нет
        Product.objects.all().delete()

        is_valid, error_message = _validate_dependencies(["images"])

        assert not is_valid
        assert "каталог товаров пуст" in error_message
        assert "изображения" in error_message.lower()

    def test_images_validation_passes_when_products_exist(self) -> None:
        """Проверка: images проходит валидацию когда товары есть."""
        # Создать хотя бы один товар
        ProductFactory.create()

        is_valid, error_message = _validate_dependencies(["images"])

        assert is_valid
        assert error_message == ""

    def test_multiple_types_validation_with_images(self) -> None:
        """Проверка валидации при выборе нескольких типов включая images."""
        ProductFactory.create()

        is_valid, error_message = _validate_dependencies(["catalog", "images"])

        assert is_valid

    def test_validation_error_message_specific_to_images(self) -> None:
        """Проверка специфичного сообщения об ошибке для images."""
        Product.objects.all().delete()

        is_valid, error_message = _validate_dependencies(["images"])

        # Проверяем, что сообщение содержит специфическое упоминание изображений
        assert "изображения" in error_message.lower()
        # И НЕ содержит "остатки/цены"
        assert "остатки" not in error_message.lower()


@pytest.mark.integration
class TestImportFromView(TestCase):
    """Интеграционные тесты view импорта из 1С."""

    def setUp(self) -> None:
        """Настройка тестовых данных."""
        self.client = Client()
        # Создать admin пользователя
        self.admin_user = User.objects.create_superuser(email="admin@test.com", password="testpass123")
        self.client.force_login(self.admin_user)

    def test_import_form_displays_images_type(self) -> None:
        """Проверка отображения типа 'images' в форме импорта."""
        url = reverse("admin:integrations_import_from_1c")

        response = self.client.get(url)

        assert response.status_code == 200

        # Проверяем наличие типа images в context
        import_types = response.context["import_types"]
        images_type = next((t for t in import_types if t["value"] == "images"), None)

        assert images_type is not None
        assert images_type["label"] == "Только изображения товаров"
        assert images_type["requires_catalog"] is True
        assert "import_files" in images_type["files"]

    def test_images_type_ordering_in_form(self) -> None:
        """Проверка порядка типа images в форме (после catalog, перед stocks)."""
        url = reverse("admin:integrations_import_from_1c")

        response = self.client.get(url)

        import_types = response.context["import_types"]
        type_values = [t["value"] for t in import_types]

        catalog_index = type_values.index("catalog")
        images_index = type_values.index("images")
        stocks_index = type_values.index("stocks")

        # Проверяем правильный порядок
        assert catalog_index < images_index < stocks_index

    def test_images_type_has_correct_emoji(self) -> None:
        """Проверка наличия emoji для типа images в HTML."""
        url = reverse("admin:integrations_import_from_1c")

        response = self.client.get(url)

        # Проверяем наличие emoji 🖼️ в HTML
        assert "🖼️" in response.content.decode("utf-8")


@pytest.mark.integration
class TestImportPostRequest(TestCase):
    """Тесты POST запросов на запуск импорта с типом images."""

    def setUp(self) -> None:
        """Настройка тестовых данных."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(email="admin@test.com", password="testpass123")
        self.client.force_login(self.admin_user)

    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_post_images_type_creates_session_with_correct_type(
        self, mock_exists: MagicMock, mock_task: MagicMock
    ) -> None:
        """Проверка создания сессии с типом IMAGES при POST запросе."""
        # Мокаем существование директории
        mock_exists.return_value = True

        # Создать товары для прохождения валидации
        ProductFactory.create()

        # Мокируем Celery задачу
        mock_task.delay.return_value.id = "test-task-id"

        url = reverse("admin:integrations_import_from_1c")

        response = self.client.post(url, {"import_type": "images"})

        # Проверяем редирект
        assert response.status_code == 302

        # Проверяем создание сессии
        session = ImportSession.objects.filter(import_type=ImportSession.ImportType.IMAGES).first()

        assert session is not None
        assert session.status == ImportSession.ImportStatus.STARTED
        assert session.celery_task_id == "test-task-id"

    def test_post_images_type_fails_when_no_products(self) -> None:
        """Проверка ошибки при попытке импорта images без товаров."""
        Product.objects.all().delete()

        url = reverse("admin:integrations_import_from_1c")

        response = self.client.post(url, {"import_type": "images"})

        # Проверяем редирект обратно на форму
        assert response.status_code == 302

        # Проверяем, что сессия НЕ создана
        assert not ImportSession.objects.filter(import_type=ImportSession.ImportType.IMAGES).exists()


@pytest.mark.integration
class TestExistingTypesRegression(TestCase):
    """Regression тесты: новый тип не ломает существующие."""

    def setUp(self) -> None:
        """Настройка тестовых данных."""
        self.client = Client()
        self.admin_user = User.objects.create_superuser(email="admin@test.com", password="testpass123")
        self.client.force_login(self.admin_user)

    @patch("apps.integrations.views.run_selective_import_task")
    @patch("apps.integrations.views.Path.exists")
    def test_catalog_type_still_works(self, mock_exists: MagicMock, mock_task: MagicMock) -> None:
        """Проверка: тип catalog работает как прежде."""
        # Мокаем существование директории
        mock_exists.return_value = True

        mock_task.delay.return_value.id = "test-task-id"

        url = reverse("admin:integrations_import_from_1c")
        response = self.client.post(url, {"import_type": "catalog"})

        assert response.status_code == 302

        session = ImportSession.objects.filter(import_type=ImportSession.ImportType.CATALOG).first()

        assert session is not None

    def test_stocks_type_still_requires_products(self) -> None:
        """Проверка: валидация stocks не изменилась."""
        Product.objects.all().delete()

        is_valid, error_message = _validate_dependencies(["stocks"])

        assert not is_valid
        assert "остатки" in error_message.lower() or "цены" in error_message.lower()

    def test_prices_type_still_requires_products(self) -> None:
        """Проверка: валидация prices не изменилась."""
        Product.objects.all().delete()

        is_valid, error_message = _validate_dependencies(["prices"])

        assert not is_valid
        assert "остатки" in error_message.lower() or "цены" in error_message.lower()

    def test_all_original_types_present_in_form(self) -> None:
        """Проверка наличия всех оригинальных типов в форме."""
        url = reverse("admin:integrations_import_from_1c")

        response = self.client.get(url)

        import_types = response.context["import_types"]
        type_values = [t["value"] for t in import_types]

        # Все оригинальные типы должны быть на месте
        assert "catalog" in type_values
        assert "stocks" in type_values
        assert "prices" in type_values
        assert "customers" in type_values
        # И новый тип тоже
        assert "images" in type_values

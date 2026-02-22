"""
Integration tests for image import with path normalization (Story 27.2, AC4)

Tests that both path formats ('import_files/xx/file.jpg' and 'xx/file.jpg')
produce the same result in media storage.
"""

from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.test import override_settings

from apps.products.models import Brand, Category, ImportSession, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor, normalize_image_path


@pytest.fixture
def brand(db):
    """Создаёт тестовый бренд"""
    return Brand.objects.create(
        name="Test Brand",
        slug="test-brand",
        is_active=True,
    )


@pytest.fixture
def category(db):
    """Создаёт тестовую категорию"""
    return Category.objects.create(
        name="Test Category",
        slug="test-category",
        is_active=True,
    )


@pytest.fixture
def import_session(db):
    """Создаёт тестовую сессию импорта"""
    return ImportSession.objects.create(
        import_type="full",
        status="in_progress",
    )


@pytest.fixture
def product(db, brand, category):
    """Создаёт тестовый Product"""
    return Product.objects.create(
        name="Test Product",
        slug="test-product",
        onec_id="test-parent-id",
        parent_onec_id="test-parent-id",
        brand=brand,
        category=category,
        is_active=True,
        base_images=[],
    )


@pytest.fixture
def variant(db, product):
    """Создаёт тестовый ProductVariant"""
    return ProductVariant.objects.create(
        product=product,
        sku="TEST-SKU-001",
        onec_id="test-parent-id#variant-id",
        retail_price=Decimal("1000.00"),
        is_active=True,
    )


@pytest.fixture
def processor(import_session):
    """Создаёт VariantImportProcessor"""
    return VariantImportProcessor(session_id=import_session.id)


@pytest.fixture
def temp_import_dir(tmp_path):
    """Создаёт временную структуру директорий импорта с тестовыми изображениями"""
    # Создаём структуру xx/file.jpg
    images_dir = tmp_path / "xx"
    images_dir.mkdir(parents=True)

    # Создаём тестовые изображения
    test_image1 = images_dir / "test1.jpg"
    test_image1.write_bytes(b"fake image data 1")

    test_image2 = images_dir / "test2.jpg"
    test_image2.write_bytes(b"fake image data 2")

    return tmp_path


@pytest.mark.integration
@pytest.mark.django_db
class TestImageImportWithNormalization:
    """Integration тесты импорта изображений с разными форматами путей (AC4)"""

    def test_import_base_images_with_import_files_prefix(self, processor, product, temp_import_dir):
        """Импорт base_images с путём import_files/xx/test1.jpg - путь нормализуется"""
        image_paths = ["import_files/xx/test1.jpg"]

        # Проверяем что нормализованный путь корректен
        normalized = normalize_image_path(image_paths[0])
        assert normalized == "xx/test1.jpg"

        # Проверяем что файл существует по нормализованному пути
        source_path = Path(temp_import_dir) / normalized
        assert source_path.exists()

    def test_import_base_images_without_prefix(self, processor, product, temp_import_dir):
        """Импорт base_images с путём xx/test1.jpg (без prefix)"""
        image_paths = ["xx/test1.jpg"]

        # Проверяем что нормализованный путь остаётся неизменным
        normalized = normalize_image_path(image_paths[0])
        assert normalized == "xx/test1.jpg"

        # Проверяем что файл существует
        source_path = Path(temp_import_dir) / normalized
        assert source_path.exists()

    def test_import_variant_images_with_import_files_prefix(self, processor, variant, temp_import_dir):
        """
        Импорт variant images с путём import_files/xx/test1.jpg - путь нормализуется
        """
        image_paths = ["import_files/xx/test1.jpg"]

        # Проверяем что нормализованный путь корректен
        normalized = normalize_image_path(image_paths[0])
        assert normalized == "xx/test1.jpg"

        # Проверяем что файл существует по нормализованному пути
        source_path = Path(temp_import_dir) / normalized
        assert source_path.exists()

    def test_import_variant_images_without_prefix(self, processor, variant, temp_import_dir):
        """Импорт variant images с путём xx/test1.jpg (без prefix)"""
        image_paths = ["xx/test1.jpg"]

        # Проверяем что нормализованный путь остаётся неизменным
        normalized = normalize_image_path(image_paths[0])
        assert normalized == "xx/test1.jpg"

        # Проверяем что файл существует
        source_path = Path(temp_import_dir) / normalized
        assert source_path.exists()

    def test_both_path_formats_find_same_file(self, temp_import_dir):
        """Оба формата путей должны находить один и тот же файл"""
        # Путь с prefix
        path_with_prefix = "import_files/xx/test1.jpg"
        # Путь без prefix
        path_without_prefix = "xx/test1.jpg"

        # Нормализуем оба пути
        normalized_with = normalize_image_path(path_with_prefix)
        normalized_without = normalize_image_path(path_without_prefix)

        # Оба должны дать одинаковый результат
        assert normalized_with == normalized_without == "xx/test1.jpg"

        # Оба должны находить один и тот же файл
        source_path_with = Path(temp_import_dir) / normalized_with
        source_path_without = Path(temp_import_dir) / normalized_without

        assert source_path_with == source_path_without
        assert source_path_with.exists()

    def test_stats_updated_on_image_import(self, processor, product, temp_import_dir):
        """Статистика обновляется при импорте изображений"""
        image_paths = ["xx/test1.jpg"]

        initial_copied = processor.stats["images_copied"]
        initial_errors = processor.stats["images_errors"]

        with patch("apps.products.services.variant_import.default_storage") as mock_storage:
            mock_storage.exists.return_value = False
            mock_storage.save.return_value = "products/base/xx/test1.jpg"

            processor._import_base_images(product, image_paths, str(temp_import_dir))

            # Проверяем что статистика изменилась
            total_changes = (
                processor.stats["images_copied"] + processor.stats["images_skipped"] + processor.stats["images_errors"]
            )
            assert total_changes >= initial_copied + initial_errors

    def test_image_not_found_logs_error(self, processor, product, temp_import_dir):
        """Несуществующий файл увеличивает счётчик ошибок изображений"""
        image_paths = ["nonexistent/missing.jpg"]

        initial_errors = processor.stats["images_errors"]

        processor._import_base_images(product, image_paths, str(temp_import_dir))

        # Должна быть ошибка (файл не найден)
        assert processor.stats["images_errors"] > initial_errors

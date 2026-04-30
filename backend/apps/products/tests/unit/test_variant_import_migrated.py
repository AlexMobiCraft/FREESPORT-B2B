"""
Тесты для перенесённых методов VariantImportProcessor (Story 27.1)

Тестирует:
- process_categories() - создание/обновление категорий с иерархией
- _has_circular_reference() - обнаружение циклических ссылок
- process_brands() - создание/обновление брендов с дедупликацией
- process_price_types() - создание/обновление типов цен
"""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.test import override_settings

from apps.products.models import Brand, Brand1CMapping, Category, ImportSession, PriceType
from apps.products.services.variant_import import BrandData, CategoryData, PriceTypeData, VariantImportProcessor

# Маркировка для всего модуля
pytestmark = [pytest.mark.django_db, pytest.mark.unit]

# Глобальный счетчик для обеспечения уникальности
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс для тестов"""
    global _unique_counter
    _unique_counter += 1
    import uuid

    return f"{_unique_counter}_{uuid.uuid4().hex[:6]}"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def import_session():
    """Создаёт ImportSession для тестирования"""
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.IN_PROGRESS,
    )
    return session


@pytest.fixture
def processor(import_session):
    """Создаёт VariantImportProcessor для тестирования"""
    return VariantImportProcessor(session_id=import_session.id)


# ============================================================================
# TestProcessPriceTypes
# ============================================================================


class TestProcessPriceTypes:
    """Тесты для process_price_types()"""

    def test_create_price_type(self, processor):
        """Создание нового PriceType"""
        # Arrange
        suffix = get_unique_suffix()
        price_types_data: list[PriceTypeData] = [
            {
                "onec_id": f"pt_{suffix}_1",
                "onec_name": "Розничная цена",
                "product_field": "retail_price",
            }
        ]

        # Act
        count = processor.process_price_types(price_types_data)

        # Assert
        assert count == 1
        pt = PriceType.objects.get(onec_id=f"pt_{suffix}_1")
        assert pt.onec_name == "Розничная цена"
        assert pt.product_field == "retail_price"
        assert pt.is_active is True

    def test_update_existing_price_type(self, processor):
        """Обновление существующего PriceType"""
        # Arrange
        suffix = get_unique_suffix()
        onec_id = f"pt_{suffix}_update"

        # Создаём существующий PriceType
        PriceType.objects.create(
            onec_id=onec_id,
            onec_name="Old Name",
            product_field="opt1_price",
            is_active=False,
        )

        price_types_data: list[PriceTypeData] = [
            {
                "onec_id": onec_id,
                "onec_name": "New Name",
                "product_field": "opt1_price",
            }
        ]

        # Act
        count = processor.process_price_types(price_types_data)

        # Assert
        assert count == 1
        pt = PriceType.objects.get(onec_id=onec_id)
        assert pt.onec_name == "New Name"
        assert pt.is_active is True  # Обновлено на True

    def test_process_multiple_price_types(self, processor):
        """Обработка нескольких типов цен за раз"""
        # Arrange
        suffix = get_unique_suffix()
        price_types_data: list[PriceTypeData] = [
            {
                "onec_id": f"pt_{suffix}_a",
                "onec_name": "Оптовая 1",
                "product_field": "opt1_price",
            },
            {
                "onec_id": f"pt_{suffix}_b",
                "onec_name": "Оптовая 2",
                "product_field": "opt2_price",
            },
            {
                "onec_id": f"pt_{suffix}_c",
                "onec_name": "Оптовая 3",
                "product_field": "opt3_price",
            },
        ]

        # Act
        count = processor.process_price_types(price_types_data)

        # Assert
        assert count == 3
        assert PriceType.objects.filter(onec_id__startswith=f"pt_{suffix}").count() == 3


# ============================================================================
# TestProcessCategories
# ============================================================================


class TestProcessCategories:
    """Тесты для process_categories()"""

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_create_root_categories(self, processor):
        """Создание корневых категорий без parent"""
        # Arrange
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {
                "id": f"cat_{suffix}_1",
                "name": f"Спортивная одежда {suffix}",
                "description": "Описание категории",
            },
            {
                "id": f"cat_{suffix}_2",
                "name": f"Спортивная обувь {suffix}",
            },
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 2
        assert result["updated"] == 0
        assert result["errors"] == 0

        cat1 = Category.objects.get(onec_id=f"cat_{suffix}_1")
        assert cat1.name == f"Спортивная одежда {suffix}"
        assert cat1.description == "Описание категории"
        assert cat1.parent is None

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_create_child_categories(self, processor):
        """Создание дочерних категорий с parent"""
        # Arrange
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {
                "id": f"cat_{suffix}_parent",
                "name": f"Родительская {suffix}",
            },
            {
                "id": f"cat_{suffix}_child",
                "name": f"Дочерняя {suffix}",
                "parent_id": f"cat_{suffix}_parent",
            },
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 2
        assert result["cycles_detected"] == 0

        child = Category.objects.get(onec_id=f"cat_{suffix}_child")
        parent = Category.objects.get(onec_id=f"cat_{suffix}_parent")
        assert child.parent == parent

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_update_existing_category(self, processor):
        """Обновление существующей категории"""
        # Arrange
        suffix = get_unique_suffix()
        onec_id = f"cat_{suffix}_update"

        # Создаём существующую категорию
        Category.objects.create(
            onec_id=onec_id,
            name="Old Name",
            slug=f"old-slug-{suffix}",
            is_active=False,
        )

        categories_data: list[CategoryData] = [
            {
                "id": onec_id,
                "name": "New Name",
                "description": "New description",
            }
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 0
        assert result["updated"] == 1

        cat = Category.objects.get(onec_id=onec_id)
        assert cat.name == "New Name"
        assert cat.description == "New description"
        assert cat.is_active is True

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_detect_circular_reference(self, processor):
        """Обнаружение циклических ссылок"""
        # Arrange
        suffix = get_unique_suffix()

        # Создаём категории с предполагаемым циклом:
        # cat_a -> cat_b -> cat_a (цикл)
        categories_data: list[CategoryData] = [
            {
                "id": f"cat_{suffix}_a",
                "name": f"Category A {suffix}",
                "parent_id": f"cat_{suffix}_b",  # A хочет parent B
            },
            {
                "id": f"cat_{suffix}_b",
                "name": f"Category B {suffix}",
                "parent_id": f"cat_{suffix}_a",  # B хочет parent A - ЦИКЛ!
            },
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 2
        # Должен обнаружить хотя бы один цикл
        assert result["cycles_detected"] >= 1

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_skip_category_with_missing_id(self, processor):
        """Пропуск категории без id"""
        # Arrange
        categories_data: list[CategoryData] = [
            {
                "name": "No ID Category",
            },
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 0
        assert result["errors"] == 1

    @override_settings(ROOT_CATEGORY_NAME=None)
    def test_skip_category_with_missing_name(self, processor):
        """Пропуск категории без name"""
        # Arrange
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {
                "id": f"cat_{suffix}_no_name",
            },
        ]

        # Act
        result = processor.process_categories(categories_data)

        # Assert
        assert result["created"] == 0
        assert result["errors"] == 1


# ============================================================================
# TestProcessCategoriesFiltering
# ============================================================================


class TestProcessCategoriesFiltering:
    """Тесты для фильтрации корневых категорий в process_categories()"""

    def test_process_categories_skips_root_categories(self, processor):
        """Корневые категории не создаются в БД при активной фильтрации."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"tech_{suffix}", "name": "БЫТОВАЯ ТЕХНИКА"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        # Корневые не создаются
        assert not Category.objects.filter(onec_id=f"sport_{suffix}").exists()
        assert not Category.objects.filter(onec_id=f"tech_{suffix}").exists()
        # Дочерняя СПОРТ создаётся
        assert Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert result["created"] == 1

    def test_process_categories_imports_sport_children_as_root(self, processor):
        """Дочерние СПОРТ → parent=None (корневые на сайте)."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
            {"id": f"shoes_{suffix}", "name": f"Обувь {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        clothes = Category.objects.get(onec_id=f"clothes_{suffix}")
        shoes = Category.objects.get(onec_id=f"shoes_{suffix}")
        assert clothes.parent is None
        assert shoes.parent is None
        assert result["created"] == 2

    def test_process_categories_imports_deep_descendants(self, processor):
        """[F4] Глубокие потомки (внуки, правнуки) якорной тоже импортируются."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
            {"id": f"tshirts_{suffix}", "name": f"Футболки {suffix}", "parent_id": f"clothes_{suffix}"},
            {"id": f"polo_{suffix}", "name": f"Поло {suffix}", "parent_id": f"tshirts_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        # Все потомки должны быть созданы
        assert Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert Category.objects.filter(onec_id=f"tshirts_{suffix}").exists()
        assert Category.objects.filter(onec_id=f"polo_{suffix}").exists()
        assert result["created"] == 3

        # Иерархия сохранена (кроме прямых child якорной)
        tshirts = Category.objects.get(onec_id=f"tshirts_{suffix}")
        clothes = Category.objects.get(onec_id=f"clothes_{suffix}")
        polo = Category.objects.get(onec_id=f"polo_{suffix}")
        assert tshirts.parent == clothes
        assert polo.parent == tshirts
        assert clothes.parent is None  # Прямой child якорной → root

    def test_process_categories_ignores_non_sport_root_descendants(self, processor):
        """Потомки НЕ-СПОРТ корневых не импортируются."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"tech_{suffix}", "name": "БЫТОВАЯ ТЕХНИКА"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
            {"id": f"fridges_{suffix}", "name": f"Холодильники {suffix}", "parent_id": f"tech_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        assert Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert not Category.objects.filter(onec_id=f"fridges_{suffix}").exists()
        assert result["created"] == 1

    def test_get_or_create_category_returns_none_for_filtered(self, processor):
        """_get_or_create_category возвращает None для категорий вне allowed_ids."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"junk_{suffix}", "name": "Номенклатура к удалению"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            processor.process_categories(categories_data)

        # allowed: только clothes (дочерняя СПОРТ)
        assert processor._category_filtering_active is True
        assert f"clothes_{suffix}" in processor._allowed_category_ids
        assert f"junk_{suffix}" not in processor._allowed_category_ids

        # Товар с категорией из allowed — возвращает категорию
        result_allowed = processor._get_or_create_category({"category_id": f"clothes_{suffix}"})
        assert result_allowed is not None

        # Товар с категорией вне allowed — возвращает None
        result_filtered = processor._get_or_create_category({"category_id": f"junk_{suffix}"})
        assert result_filtered is None
        # Категория НЕ создана в БД
        assert not Category.objects.filter(onec_id=f"junk_{suffix}").exists()

    def test_process_categories_fallback_without_root_name(self, processor):
        """Если ROOT_CATEGORY_NAME=None, импортирует всё (тихо)."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"tech_{suffix}", "name": "БЫТОВАЯ ТЕХНИКА"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME=None):
            result = processor.process_categories(categories_data)

        # Все категории должны быть созданы (обратная совместимость)
        assert Category.objects.filter(onec_id=f"sport_{suffix}").exists()
        assert Category.objects.filter(onec_id=f"tech_{suffix}").exists()
        assert Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert result["created"] == 3
        assert "root_not_found" not in result

    def test_process_categories_error_log_when_root_not_found(self, processor, caplog):
        """[F8] Если ROOT_CATEGORY_NAME задан но не найден → error лог и отмена импорта файла (return empty result)."""
        import logging

        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="НЕСУЩЕСТВУЮЩАЯ"):
            with caplog.at_level(logging.ERROR, logger="apps.products.services.variant_import"):
                result = processor.process_categories(categories_data)

        # Cancel the import: 0 categories imported
        assert not Category.objects.filter(onec_id=f"sport_{suffix}").exists()
        assert not Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert result["created"] == 0
        assert result["updated"] == 0
        assert result.get("root_not_found") is True

        # Проверяем error лог
        assert any("НЕСУЩЕСТВУЮЩАЯ" in record.message for record in caplog.records)


# ============================================================================
# TestHasCircularReference
# ============================================================================


class TestHasCircularReference:
    """Тесты для _has_circular_reference()"""

    def test_no_circular_reference(self, processor):
        """Нет циклической ссылки - нормальная иерархия"""
        # Arrange
        suffix = get_unique_suffix()

        parent = Category.objects.create(
            onec_id=f"cat_{suffix}_parent",
            name=f"Parent {suffix}",
            slug=f"parent-{suffix}",
        )
        child = Category.objects.create(
            onec_id=f"cat_{suffix}_child",
            name=f"Child {suffix}",
            slug=f"child-{suffix}",
        )

        category_map = {
            f"cat_{suffix}_parent": parent,
            f"cat_{suffix}_child": child,
        }

        # Act: child хочет parent = parent - это валидно
        result = processor._has_circular_reference(child, parent, category_map)

        # Assert
        assert result is False

    def test_direct_circular_reference(self, processor):
        """Прямая циклическая ссылка: A -> B -> A"""
        # Arrange
        suffix = get_unique_suffix()

        cat_a = Category.objects.create(
            onec_id=f"cat_{suffix}_a",
            name=f"Cat A {suffix}",
            slug=f"cat-a-{suffix}",
        )
        cat_b = Category.objects.create(
            onec_id=f"cat_{suffix}_b",
            name=f"Cat B {suffix}",
            slug=f"cat-b-{suffix}",
            parent=cat_a,  # B.parent = A
        )

        category_map = {
            f"cat_{suffix}_a": cat_a,
            f"cat_{suffix}_b": cat_b,
        }

        # Act: A хочет parent = B, но B.parent = A - это цикл!
        result = processor._has_circular_reference(cat_a, cat_b, category_map)

        # Assert
        assert result is True

    def test_self_reference(self, processor):
        """Самоссылка: A -> A"""
        # Arrange
        suffix = get_unique_suffix()

        cat = Category.objects.create(
            onec_id=f"cat_{suffix}_self",
            name=f"Self Ref {suffix}",
            slug=f"self-ref-{suffix}",
        )

        category_map = {f"cat_{suffix}_self": cat}

        # Act: cat хочет parent = cat - это цикл!
        result = processor._has_circular_reference(cat, cat, category_map)

        # Assert
        assert result is True


# ============================================================================
# TestProcessBrands
# ============================================================================


class TestProcessBrands:
    """Тесты для process_brands()"""

    def test_create_new_brand_with_mapping(self, processor):
        """Создание нового бренда с маппингом"""
        # Arrange
        suffix = get_unique_suffix()
        brands_data: list[BrandData] = [
            {
                "id": f"brand_{suffix}_1",
                "name": f"Nike Test {suffix}",
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 1
        assert result["mappings_created"] == 1
        assert result["mappings_updated"] == 0

        brand = Brand.objects.get(name=f"Nike Test {suffix}")
        assert brand.is_active is True

        mapping = Brand1CMapping.objects.get(onec_id=f"brand_{suffix}_1")
        assert mapping.brand == brand
        assert mapping.onec_name == f"Nike Test {suffix}"

    def test_merge_duplicate_by_normalized_name(self, processor):
        """Объединение дубликатов по normalized_name"""
        # Arrange
        suffix = get_unique_suffix()

        # Создаём бренд вручную
        existing_brand = Brand.objects.create(
            name=f"Adidas {suffix}",
            slug=f"adidas-{suffix}",
            is_active=True,
        )
        # normalized_name устанавливается автоматически в save()

        # Пытаемся импортировать бренд с таким же нормализованным именем
        brands_data: list[BrandData] = [
            {
                "id": f"brand_{suffix}_adidas",
                "name": f"ADIDAS {suffix}",  # Другой регистр, но тот же бренд
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 0  # Бренд НЕ создан
        assert result["mappings_created"] == 1  # Маппинг создан

        # Проверяем что маппинг ведёт к существующему бренду
        mapping = Brand1CMapping.objects.get(onec_id=f"brand_{suffix}_adidas")
        assert mapping.brand == existing_brand

    def test_update_existing_mapping(self, processor):
        """Обновление существующего маппинга"""
        # Arrange
        suffix = get_unique_suffix()

        # Создаём бренд и маппинг
        brand = Brand.objects.create(
            name=f"Puma {suffix}",
            slug=f"puma-{suffix}",
            is_active=True,
        )
        Brand1CMapping.objects.create(
            brand=brand,
            onec_id=f"brand_{suffix}_puma",
            onec_name="Old Puma Name",
        )

        # Пытаемся импортировать с новым именем
        brands_data: list[BrandData] = [
            {
                "id": f"brand_{suffix}_puma",
                "name": f"New Puma Name {suffix}",
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 0
        assert result["mappings_created"] == 0
        assert result["mappings_updated"] == 1

        mapping = Brand1CMapping.objects.get(onec_id=f"brand_{suffix}_puma")
        assert mapping.onec_name == f"New Puma Name {suffix}"

    def test_generate_unique_slug(self, processor):
        """Генерация уникального slug при коллизии"""
        # Arrange
        suffix = get_unique_suffix()

        # Создаём бренд с определённым slug
        Brand.objects.create(
            name=f"Reebok Original {suffix}",
            slug=f"reebok-{suffix}",
            is_active=True,
        )

        # Пытаемся создать бренд который получит такой же slug
        brands_data: list[BrandData] = [
            {
                "id": f"brand_{suffix}_reebok2",
                "name": f"Reebok {suffix}",  # Тот же slug после транслитерации
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 1

        # Новый бренд должен получить уникальный slug (с суффиксом)
        new_brand = Brand.objects.filter(name=f"Reebok {suffix}").first()
        assert new_brand is not None
        # Slug должен отличаться от существующего
        assert new_brand.slug != f"reebok-{suffix}"

    def test_skip_brand_with_missing_id(self, processor):
        """Пропуск бренда без id"""
        # Arrange
        brands_data: list[BrandData] = [
            {
                "name": "No ID Brand",  # type: ignore
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 0
        assert result["mappings_created"] == 0

    def test_skip_brand_with_missing_name(self, processor):
        """Пропуск бренда без name"""
        # Arrange
        suffix = get_unique_suffix()
        brands_data: list[BrandData] = [
            {
                "id": f"brand_{suffix}_no_name",  # type: ignore
            }
        ]

        # Act
        result = processor.process_brands(brands_data)

        # Assert
        assert result["brands_created"] == 0
        assert result["mappings_created"] == 0

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
        """Создаёт якорь СПОРТ и пропускает посторонние root-ветки."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"tech_{suffix}", "name": "БЫТОВАЯ ТЕХНИКА"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        sport = Category.objects.get(onec_id=f"sport_{suffix}")
        assert sport.parent is None
        assert not Category.objects.filter(onec_id=f"tech_{suffix}").exists()
        clothes = Category.objects.get(onec_id=f"clothes_{suffix}")
        assert clothes.parent == sport
        assert result["created"] == 2

    def test_process_categories_imports_sport_children_as_root(self, processor):
        """Дочерние СПОРТ сохраняются под якорем, а не становятся root."""
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
        sport = Category.objects.get(onec_id=f"sport_{suffix}")
        assert sport.parent is None
        assert clothes.parent == sport
        assert shoes.parent == sport
        assert result["created"] == 3

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
        assert result["created"] == 4

        # Иерархия сохранена полностью, включая якорь СПОРТ
        sport = Category.objects.get(onec_id=f"sport_{suffix}")
        tshirts = Category.objects.get(onec_id=f"tshirts_{suffix}")
        clothes = Category.objects.get(onec_id=f"clothes_{suffix}")
        polo = Category.objects.get(onec_id=f"polo_{suffix}")
        assert tshirts.parent == clothes
        assert polo.parent == tshirts
        assert clothes.parent == sport

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

        assert Category.objects.filter(onec_id=f"sport_{suffix}").exists()
        assert Category.objects.filter(onec_id=f"clothes_{suffix}").exists()
        assert not Category.objects.filter(onec_id=f"tech_{suffix}").exists()
        assert not Category.objects.filter(onec_id=f"fridges_{suffix}").exists()
        assert result["created"] == 2

    def test_get_or_create_category_returns_none_for_filtered(self, processor):
        """_get_or_create_category изолирует категории вне allowed_ids в скрытый fallback."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"junk_{suffix}", "name": "Номенклатура к удалению"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            processor.process_categories(categories_data)

        # allowed: anchor + его потомки
        assert processor._category_filtering_active is True
        assert f"sport_{suffix}" in processor._allowed_category_ids
        assert f"clothes_{suffix}" in processor._allowed_category_ids
        assert f"junk_{suffix}" not in processor._allowed_category_ids

        # Товар с категорией из allowed — возвращает категорию
        result_allowed = processor._get_or_create_category({"category_id": f"clothes_{suffix}"})
        assert result_allowed is not None

        # Товар с категорией вне allowed — уходит в скрытую техническую категорию
        result_filtered = processor._get_or_create_category({"category_id": f"junk_{suffix}"})
        assert result_filtered is not None
        assert result_filtered.slug == "onec-unresolved-category"
        assert result_filtered.is_active is False
        # Публичная placeholder-категория НЕ создана в БД
        assert not Category.objects.filter(onec_id=f"junk_{suffix}").exists()

    def test_get_or_create_category_routes_existing_outside_subtree_to_fallback(self, processor):
        """CR-4 Fix 1: категория существует в DB, но вне allowed subtree — товар уходит в техкатегорию."""
        suffix = get_unique_suffix()
        categories_data: list[CategoryData] = [
            {"id": f"sport_{suffix}", "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": f"sport_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            processor.process_categories(categories_data)

        # Создаём категорию в DB с onec_id вне разрешённого поддерева (она уже есть в _allowed_category_ids? нет)
        outside_cat = Category.objects.create(
            name=f"Вне поддерева {suffix}",
            slug=f"outside-subtree-{suffix}",
            onec_id=f"outside_{suffix}",
            is_active=True,
        )

        assert processor._category_filtering_active is True
        assert outside_cat.onec_id not in processor._allowed_category_ids

        # Вызов _get_or_create_category: категория найдена в DB, но вне subtree
        result = processor._get_or_create_category({"category_id": f"outside_{suffix}", "id": f"prod_{suffix}"})

        assert result is not None
        assert result.slug == "onec-unresolved-category", (
            "Категория вне allowed subtree должна направляться в техническую fallback-категорию"
        )
        assert result.is_active is False
        assert processor.stats["category_fallbacks"] >= 1

    def test_incremental_import_reactivates_inactive_anchor(self, processor):
        """CR-4 Fix 3: инкрементальный импорт (без СПОРТ в XML) реактивирует неактивный якорь."""
        suffix = get_unique_suffix()

        # Pre-condition: якорь СПОРТ в БД, но неактивный
        inactive_sport = Category.objects.create(
            name="СПОРТ",
            slug=f"sport-inactive-incr-{suffix}",
            onec_id=f"sport_inactive_{suffix}",
            is_active=False,
            parent=None,
        )

        # Инкрементальный импорт: XML содержит только потомков, якоря нет
        categories_data: list[CategoryData] = [
            {"id": f"football_{suffix}", "name": f"Футбол {suffix}", "parent_id": f"sport_inactive_{suffix}"},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            processor.process_categories(categories_data)

        inactive_sport.refresh_from_db()
        assert inactive_sport.is_active is True, (
            "Инкрементальный импорт должен реактивировать неактивный якорь СПОРТ"
        )
        assert processor._category_filtering_active is True

    def test_get_or_create_category_does_not_create_public_placeholder_for_unknown_id(self, processor):
        """Не создаёт публичную `Категория <uuid>` при неизвестном category_id из goods.xml."""
        suffix = get_unique_suffix()
        unknown_id = f"unknown_{suffix}"

        category = processor._get_or_create_category(
            {
                "category_id": unknown_id,
                "category_name": f"Категория {unknown_id}",
            }
        )

        assert category is not None
        assert category.slug == "onec-unresolved-category"
        assert category.is_active is False
        assert processor.stats["category_fallbacks"] == 1
        assert not Category.objects.filter(onec_id=unknown_id).exists()
        assert not Category.objects.filter(name=f"Категория {unknown_id}").exists()

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

    def test_full_reimport_does_not_produce_placeholder_roots(self, processor):
        """AC8: повторная полная перезаливка в пустую БД — UUID-placeholder roots не появляются.

        Симулирует два подряд полных импорта groups.xml и проверяет, что на выходе:
        - СПОРТ является единственным root
        - потомки сохраняют parent chain
        - нет категорий с UUID-суффиксом в parent=None
        """
        from apps.products.category_utils import is_placeholder_category_name

        suffix = get_unique_suffix()
        sport_id = f"sport_full_{suffix}"
        football_id = f"football_full_{suffix}"
        balls_id = f"balls_full_{suffix}"

        categories_data: list[CategoryData] = [
            {"id": sport_id, "name": "СПОРТ"},
            {"id": football_id, "name": f"Футбол {suffix}", "parent_id": sport_id},
            {"id": balls_id, "name": f"Мячи {suffix}", "parent_id": football_id},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            # Первая полная заливка
            processor.process_categories(categories_data)
            # Вторая полная заливка — imitate full re-import
            result = processor.process_categories(categories_data)

        # Ровно один root — СПОРТ
        roots = list(Category.objects.filter(parent__isnull=True, is_active=True))
        root_names = [c.name for c in roots]
        assert len([r for r in roots if r.name == "СПОРТ"]) == 1, (
            f"Должен быть ровно один активный root СПОРТ, found: {root_names}"
        )

        # Нет UUID-placeholder в root
        for cat in roots:
            assert not is_placeholder_category_name(cat.name), (
                f"Найден UUID-placeholder root: {cat.name!r}"
            )

        # Иерархия корректна
        football = Category.objects.get(onec_id=football_id)
        sport = Category.objects.get(onec_id=sport_id)
        balls = Category.objects.get(onec_id=balls_id)
        assert football.parent == sport
        assert balls.parent == football

        # Нет "ложного" дубля СПОРТ
        assert Category.objects.filter(name="СПОРТ", parent__isnull=True).count() == 1
        assert result.get("root_not_found") is not True

    def test_process_categories_picks_repair_anchor_when_stale_duplicate_root_exists(self, processor):
        """CR-5 #2: при наличии stale-дубля root СПОРТ с чужим onec_id и repair-якоря с sentinel
        импорт должен обновить именно repair-якорь, а не stale-дубль и не создать третий root."""
        from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID

        suffix = get_unique_suffix()
        real_sport_id = f"sport_real_{suffix}"
        stale_sport_id = f"sport_stale_{suffix}"

        # Stale-дубль root СПОРТ с чужим (не sentinel) onec_id
        stale_root = Category.objects.create(
            name="СПОРТ",
            slug=f"sport-stale-{suffix}",
            is_active=True,
            onec_id=stale_sport_id,
            parent=None,
        )
        # Repair-якорь с sentinel — должен быть выбран для merge
        repair_anchor = Category.objects.create(
            name="СПОРТ",
            slug=f"sport-repair-{suffix}",
            is_active=True,
            onec_id=REPAIR_ANCHOR_ONEC_ID,
            parent=None,
        )

        categories_data: list[CategoryData] = [
            {"id": real_sport_id, "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": real_sport_id},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            processor.process_categories(categories_data)

        repair_anchor.refresh_from_db()
        stale_root.refresh_from_db()

        assert repair_anchor.onec_id == real_sport_id, (
            "Импорт должен слить именно repair-якорь с реальным onec_id, а не stale-дубль"
        )
        assert stale_root.onec_id == stale_sport_id, "Stale-дубль не должен быть затронут merge-логикой"
        # Suммарно остаются repair-якорь (теперь real) + stale, но новый root не создаётся
        sport_roots_count = Category.objects.filter(name="СПОРТ", parent__isnull=True).count()
        assert sport_roots_count == 2, "Не должно появиться третьего root СПОРТ"

    def test_process_categories_merges_repair_anchor_with_real_onec_id(self, processor):
        """CR-3: если repair-якорь СПОРТ существует с sentinel onec_id, импорт обновляет его реальным ID,
        а не создаёт второй root СПОРТ."""
        from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID

        suffix = get_unique_suffix()
        real_sport_id = f"sport_real_{suffix}"

        # Симуляция repair-команды: якорь существует с sentinel onec_id
        repair_anchor = Category.objects.create(
            name="СПОРТ",
            slug=f"sport-repair-{suffix}",
            is_active=True,
            onec_id=REPAIR_ANCHOR_ONEC_ID,
            parent=None,
        )

        categories_data: list[CategoryData] = [
            {"id": real_sport_id, "name": "СПОРТ"},
            {"id": f"clothes_{suffix}", "name": f"Одежда {suffix}", "parent_id": real_sport_id},
        ]

        with override_settings(ROOT_CATEGORY_NAME="СПОРТ"):
            result = processor.process_categories(categories_data)

        # Должен остаться ровно один root СПОРТ — repair-якорь, обновлённый реальным onec_id
        sport_roots = list(Category.objects.filter(name="СПОРТ", parent__isnull=True))
        assert len(sport_roots) == 1, "Должен остаться ровно один корневой СПОРТ после слияния"
        merged = sport_roots[0]
        assert merged.pk == repair_anchor.pk, "Repair-якорь должен быть обновлён, не удалён"
        assert merged.onec_id == real_sport_id, "Sentinel onec_id должен быть заменён реальным"
        assert result["updated"] >= 1


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

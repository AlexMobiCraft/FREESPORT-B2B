"""
Тесты для management command cleanup_root_categories.

Тестирует:
- dry-run режим (по умолчанию)
- execute: reparent дочерних СПОРТ, удаление якорной, удаление посторонних корневых
- CASCADE удаление товаров
- HomepageCategory совместимость
- Пользовательский --root-name
- Отсутствие якорной категории
"""

from __future__ import annotations

import uuid

import pytest
from django.core.management import call_command

from apps.products.models import Category, HomepageCategory, Product

# Маркировка для всего модуля
pytestmark = [pytest.mark.django_db, pytest.mark.unit]

# Глобальный счетчик
_counter = 0


def _suffix() -> str:
    global _counter
    _counter += 1
    return f"{_counter}_{uuid.uuid4().hex[:6]}"


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def brand():
    """Создаёт бренд для товаров."""
    from apps.products.models import Brand

    suffix = _suffix()
    return Brand.objects.create(
        name=f"TestBrand {suffix}",
        slug=f"test-brand-{suffix}",
        is_active=True,
    )


@pytest.fixture
def sport_tree(brand):
    """
    Создаёт дерево категорий:
    - СПОРТ (root)            ← якорная
      - Одежда                ← child1
        - Футболки            ← grandchild
      - Обувь                 ← child2
    - БЫТОВАЯ ТЕХНИКА (root)  ← посторонняя
      - Холодильники          ← child посторонней
    """
    suffix = _suffix()

    sport = Category.objects.create(
        name="СПОРТ",
        slug=f"sport-{suffix}",
        onec_id=f"sport-{suffix}",
    )
    clothes = Category.objects.create(
        name=f"Одежда {suffix}",
        slug=f"clothes-{suffix}",
        onec_id=f"clothes-{suffix}",
        parent=sport,
    )
    tshirts = Category.objects.create(
        name=f"Футболки {suffix}",
        slug=f"tshirts-{suffix}",
        onec_id=f"tshirts-{suffix}",
        parent=clothes,
    )
    shoes = Category.objects.create(
        name=f"Обувь {suffix}",
        slug=f"shoes-{suffix}",
        onec_id=f"shoes-{suffix}",
        parent=sport,
    )

    tech = Category.objects.create(
        name=f"БЫТОВАЯ ТЕХНИКА {suffix}",
        slug=f"tech-{suffix}",
        onec_id=f"tech-{suffix}",
    )
    fridges = Category.objects.create(
        name=f"Холодильники {suffix}",
        slug=f"fridges-{suffix}",
        onec_id=f"fridges-{suffix}",
        parent=tech,
    )

    # Товары
    product_clothes = Product.objects.create(
        name=f"Куртка {suffix}",
        slug=f"jacket-{suffix}",
        brand=brand,
        category=clothes,
        description="Тестовая куртка",
    )
    product_tshirt = Product.objects.create(
        name=f"Футболка {suffix}",
        slug=f"tshirt-product-{suffix}",
        brand=brand,
        category=tshirts,
        description="Тестовая футболка",
    )
    product_shoes = Product.objects.create(
        name=f"Кроссовки {suffix}",
        slug=f"sneakers-{suffix}",
        brand=brand,
        category=shoes,
        description="Тестовые кроссовки",
    )
    product_fridge = Product.objects.create(
        name=f"Холодильник {suffix}",
        slug=f"fridge-product-{suffix}",
        brand=brand,
        category=fridges,
        description="Посторонний товар",
    )

    return {
        "sport": sport,
        "clothes": clothes,
        "tshirts": tshirts,
        "shoes": shoes,
        "tech": tech,
        "fridges": fridges,
        "product_clothes": product_clothes,
        "product_tshirt": product_tshirt,
        "product_shoes": product_shoes,
        "product_fridge": product_fridge,
    }


# ============================================================================
# Tests
# ============================================================================


class TestCleanupRootCategories:
    """Тесты для cleanup_root_categories management command."""

    def test_dry_run_shows_info_without_changes(self, sport_tree):
        """dry-run не меняет данные."""
        sport_pk = sport_tree["sport"].pk
        tech_pk = sport_tree["tech"].pk

        call_command("cleanup_root_categories")

        # Всё должно остаться на месте
        assert Category.objects.filter(pk=sport_pk).exists()
        assert Category.objects.filter(pk=tech_pk).exists()
        assert sport_tree["clothes"].parent_id == sport_pk

    def test_execute_reparents_sport_children(self, sport_tree):
        """Дочерние СПОРТ получают parent=None."""
        clothes_pk = sport_tree["clothes"].pk
        shoes_pk = sport_tree["shoes"].pk

        call_command("cleanup_root_categories", execute=True)

        # Refresh
        clothes = Category.objects.get(pk=clothes_pk)
        shoes = Category.objects.get(pk=shoes_pk)

        assert clothes.parent is None
        assert shoes.parent is None

    def test_execute_deletes_sport_category(self, sport_tree):
        """СПОРТ удалена."""
        sport_pk = sport_tree["sport"].pk

        call_command("cleanup_root_categories", execute=True)

        assert not Category.objects.filter(pk=sport_pk).exists()

    def test_execute_deletes_other_root_categories(self, sport_tree):
        """Другие корневые удалены вместе с потомками (CASCADE)."""
        tech_pk = sport_tree["tech"].pk
        fridges_pk = sport_tree["fridges"].pk

        call_command("cleanup_root_categories", execute=True)

        assert not Category.objects.filter(pk=tech_pk).exists()
        assert not Category.objects.filter(pk=fridges_pk).exists()

    def test_products_under_sport_children_preserved(self, sport_tree):
        """Товары в подкатегориях СПОРТ сохранены."""
        product_clothes_pk = sport_tree["product_clothes"].pk
        product_tshirt_pk = sport_tree["product_tshirt"].pk
        product_shoes_pk = sport_tree["product_shoes"].pk

        call_command("cleanup_root_categories", execute=True)

        assert Product.objects.filter(pk=product_clothes_pk).exists()
        assert Product.objects.filter(pk=product_tshirt_pk).exists()
        assert Product.objects.filter(pk=product_shoes_pk).exists()

    def test_products_under_anchor_deleted(self, sport_tree, brand):
        """[F5] Товары привязанные напрямую к СПОРТ удаляются каскадно."""
        suffix = _suffix()
        product_on_sport = Product.objects.create(
            name=f"Товар на СПОРТ {suffix}",
            slug=f"product-on-sport-{suffix}",
            brand=brand,
            category=sport_tree["sport"],
            description="Привязан к СПОРТ напрямую",
        )
        product_pk = product_on_sport.pk

        call_command("cleanup_root_categories", execute=True)

        assert not Product.objects.filter(pk=product_pk).exists()

    def test_custom_root_name_argument(self, sport_tree):
        """Работает с --root-name."""
        tech_name = sport_tree["tech"].name
        sport_pk = sport_tree["sport"].pk

        # Используем технику в качестве якорной
        call_command(
            "cleanup_root_categories",
            execute=True,
            root_name=tech_name,
        )

        # СПОРТ должна быть удалена (как посторонняя корневая)
        assert not Category.objects.filter(pk=sport_pk).exists()
        # Холодильники должны стать root
        fridges = Category.objects.get(pk=sport_tree["fridges"].pk)
        assert fridges.parent is None

    def test_missing_root_category_warning(self, brand):
        """Предупреждение если якорная не найдена."""
        suffix = _suffix()
        Category.objects.create(
            name=f"Другая {suffix}",
            slug=f"other-{suffix}",
            onec_id=f"other-{suffix}",
        )

        # Не должно упасть, просто предупреждение
        call_command(
            "cleanup_root_categories",
            execute=True,
            root_name="НЕСУЩЕСТВУЮЩАЯ",
        )

    def test_homepage_categories_not_broken(self, sport_tree):
        """[F9] HomepageCategory записи, привязанные к сохранённым категориям, работают."""
        clothes_pk = sport_tree["clothes"].pk

        # HomepageCategory — proxy, записи в той же таблице
        # Проверяем что запись доступна после cleanup
        call_command("cleanup_root_categories", execute=True)

        # Категория всё ещё существует и доступна через proxy
        assert HomepageCategory.objects.filter(pk=clothes_pk).exists()
        hp_cat = HomepageCategory.objects.get(pk=clothes_pk)
        assert hp_cat.parent is None  # reparented

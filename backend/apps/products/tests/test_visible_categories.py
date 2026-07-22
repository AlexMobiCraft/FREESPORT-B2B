"""
Тесты для ProductViewSet.visible_categories action и аннотации in_stock_count
в CategoryTreeViewSet (bugfix: сортировка и скрытие пустых категорий в каталоге).
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.factories import CategoryFactory, ProductFactory, ProductVariantFactory
from apps.products.models import Brand, Category


@pytest.mark.django_db
class TestVisibleCategoriesAction:
    """GET /products/visible-categories/"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("products:product-visible-categories")

    @pytest.fixture
    def brand_nike(self):
        return Brand.objects.create(name="Nike", slug="nike")

    @pytest.fixture
    def brand_adidas(self):
        return Brand.objects.create(name="Adidas", slug="adidas")

    @pytest.fixture
    def cat_shoes(self):
        return CategoryFactory(name="Обувь", slug="shoes")

    @pytest.fixture
    def cat_clothing(self):
        return CategoryFactory(name="Одежда", slug="clothing")

    @pytest.fixture
    def cat_uncategorized(self):
        return CategoryFactory(name="Без категории", slug="uncategorized")

    def test_returns_category_ids_for_in_stock_products(self, client, url, cat_shoes, cat_clothing):
        """Возвращает категории с товарами в наличии."""
        p = ProductFactory(category=cat_shoes, create_variant=False)
        ProductVariantFactory(product=p, stock_quantity=5, retail_price=Decimal("1000"))
        # Товар без остатка
        p2 = ProductFactory(category=cat_clothing, create_variant=False)
        ProductVariantFactory(product=p2, stock_quantity=0, retail_price=Decimal("500"))

        resp = client.get(url, {"in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        ids = set(resp.data["category_ids"])
        assert cat_shoes.id in ids
        assert cat_clothing.id not in ids

    def test_ignores_category_id_param(self, client, url, cat_shoes, cat_clothing):
        """category_id не должен сужать результат."""
        p1 = ProductFactory(category=cat_shoes, create_variant=False)
        ProductVariantFactory(product=p1, stock_quantity=3, retail_price=Decimal("1000"))
        p2 = ProductFactory(category=cat_clothing, create_variant=False)
        ProductVariantFactory(product=p2, stock_quantity=2, retail_price=Decimal("800"))

        # Передаём category_id=cat_shoes.id — он должен быть проигнорирован
        resp = client.get(url, {"category_id": cat_shoes.id})

        assert resp.status_code == status.HTTP_200_OK
        ids = set(resp.data["category_ids"])
        # Обе категории должны быть видны несмотря на category_id
        assert cat_shoes.id in ids
        assert cat_clothing.id in ids

    def test_filter_by_brand(self, client, url, cat_shoes, cat_clothing, brand_nike, brand_adidas):
        """Фильтрация по бренду возвращает только нужные категории."""
        p_nike = ProductFactory(category=cat_shoes, brand=brand_nike, create_variant=False)
        ProductVariantFactory(product=p_nike, stock_quantity=1, retail_price=Decimal("2000"))
        p_adidas = ProductFactory(category=cat_clothing, brand=brand_adidas, create_variant=False)
        ProductVariantFactory(product=p_adidas, stock_quantity=1, retail_price=Decimal("1500"))

        resp = client.get(url, {"brand": str(brand_nike.id)})

        assert resp.status_code == status.HTTP_200_OK
        ids = set(resp.data["category_ids"])
        assert cat_shoes.id in ids
        assert cat_clothing.id not in ids

    def test_includes_ancestor_ids(self, client, url):
        """Возвращает ID предков категорий с товарами."""
        parent = CategoryFactory(name="Спорт", slug="sport", parent=None)
        child = CategoryFactory(name="Лыжи", slug="skiing", parent=parent)

        p = ProductFactory(category=child, create_variant=False)
        ProductVariantFactory(product=p, stock_quantity=2, retail_price=Decimal("5000"))

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        ids = set(resp.data["category_ids"])
        assert child.id in ids
        assert parent.id in ids  # предок должен быть включён

    def test_empty_result_when_no_matching_products(self, client, url, cat_uncategorized):
        """Возвращает пустой список если нет товаров по фильтру."""
        p = ProductFactory(category=cat_uncategorized, create_variant=False)
        ProductVariantFactory(product=p, stock_quantity=0, retail_price=Decimal("100"))

        resp = client.get(url, {"in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["category_ids"] == []

    def test_filter_by_price_range(self, client, url, cat_shoes, cat_clothing):
        """Фильтрация по диапазону цен."""
        p_cheap = ProductFactory(category=cat_shoes, create_variant=False)
        ProductVariantFactory(product=p_cheap, stock_quantity=1, retail_price=Decimal("500"))
        p_expensive = ProductFactory(category=cat_clothing, create_variant=False)
        ProductVariantFactory(product=p_expensive, stock_quantity=1, retail_price=Decimal("10000"))

        resp = client.get(url, {"min_price": "1000", "max_price": "15000"})

        assert resp.status_code == status.HTTP_200_OK
        ids = set(resp.data["category_ids"])
        assert cat_clothing.id in ids
        assert cat_shoes.id not in ids


@pytest.mark.django_db
class TestCategoryTreeInStockCount:
    """in_stock_count в CategoryTreeViewSet"""

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("products:category-tree-list")

    def test_in_stock_count_field_present(self, client, url):
        """Поле in_stock_count присутствует в ответе."""
        sport = CategoryFactory(name="СПОРТ", slug="sport-root", onec_id="sport-root", parent=None)
        cat = CategoryFactory(name="Тест", parent=sport)
        p = ProductFactory(category=cat, create_variant=False)
        ProductVariantFactory(product=p, stock_quantity=3, retail_price=Decimal("1000"))

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        category_data = next((c for c in results if c["id"] == cat.id), None)
        assert category_data is not None
        assert "in_stock_count" in category_data

    def test_in_stock_count_excludes_zero_stock(self, client, url):
        """in_stock_count не считает товары с нулевым остатком."""
        sport = CategoryFactory(name="СПОРТ", slug="sport-root", onec_id="sport-root", parent=None)
        cat = CategoryFactory(name="Склад", parent=sport)
        p_in = ProductFactory(category=cat, create_variant=False)
        ProductVariantFactory(product=p_in, stock_quantity=2, retail_price=Decimal("1000"))
        p_out = ProductFactory(category=cat, create_variant=False)
        ProductVariantFactory(product=p_out, stock_quantity=0, retail_price=Decimal("900"))

        resp = client.get(url)

        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        category_data = next((c for c in results if c["id"] == cat.id), None)
        assert category_data is not None
        assert category_data["in_stock_count"] == 1
        assert category_data["products_count"] == 2

    @pytest.mark.integration
    def test_public_tree_returns_sport_children_only(self, client, url):
        """Публичное дерево отдаёт детей СПОРТ и скрывает тех/fallback категории."""
        sport = CategoryFactory(name="СПОРТ", slug="sport-root", onec_id="sport-root", parent=None)
        football = CategoryFactory(name="Футбол", slug="football-public", parent=sport)
        balls = CategoryFactory(name="Мячи", slug="balls-public", parent=football)
        CategoryFactory(name="Категория unknown-uuid", slug="category-unknown-uuid", parent=None, is_active=True)
        CategoryFactory(name="Без категории", slug="uncategorized", parent=sport, is_active=True)
        CategoryFactory(
            name="Техническая категория: неразрешенные ссылки 1С",
            slug="onec-unresolved-category",
            parent=sport,
            is_active=False,
        )

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        names = [item["name"] for item in results]
        assert names == ["Футбол"]
        assert results[0]["id"] == football.id
        assert results[0]["children"][0]["id"] == balls.id

    @pytest.mark.integration
    def test_public_tree_shows_legitimate_category_with_kategoriya_prefix(self, client, url):
        """Регрессия: 'Категория сезона' (легитимная) не скрывается фильтром placeholder."""
        sport = CategoryFactory(name="СПОРТ", slug="sport-legit-test", onec_id="sport-legit-test", parent=None)
        legit = CategoryFactory(name="Категория сезона", slug="kategoriya-sezona", parent=sport)
        placeholder = CategoryFactory(
            name="Категория 123e4567-e89b-12d3-a456-426614174000",
            slug="category-placeholder-uuid",
            parent=sport,
            is_active=True,
        )

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        ids = {item["id"] for item in results}
        assert legit.id in ids, "Легитимная категория 'Категория сезона' должна быть видна в публичном дереве"
        assert placeholder.id not in ids, "UUID-placeholder категория не должна появляться в публичном дереве"

    @pytest.mark.integration
    def test_public_tree_returns_union_when_multiple_active_anchors(self, client, url):
        """CR-5 #3: при нескольких активных якорях СПОРТ публичное дерево возвращает union детей.

        Защищает от ситуации, когда из-за дублирования root СПОРТ витрина теряет половину каталога.
        """
        sport_a = CategoryFactory(name="СПОРТ", slug="sport-anchor-a", onec_id="sport-anchor-a", parent=None)
        sport_b = CategoryFactory(name="СПОРТ", slug="sport-anchor-b", onec_id="sport-anchor-b", parent=None)
        football = CategoryFactory(name="Футбол", slug="football-anchor-a", parent=sport_a)
        tennis = CategoryFactory(name="Теннис", slug="tennis-anchor-b", parent=sport_b)

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        ids = {item["id"] for item in results}
        assert football.id in ids, "Дети первого якоря СПОРТ должны быть в публичном дереве"
        assert tennis.id in ids, "Дети второго якоря СПОРТ также должны быть в публичном дереве (union)"

    @pytest.mark.integration
    def test_placeholder_nested_under_legitimate_category_is_excluded(self, client, url):
        """Регрессия: рекурсивная фильтрация — placeholder вложен под легитимную категорию."""
        sport = CategoryFactory(name="СПОРТ", slug="sport-nested-ph-test", onec_id="sport-nested-ph", parent=None)
        football = CategoryFactory(name="Футбол", slug="football-nested-ph-test", parent=sport)
        nested_placeholder = CategoryFactory(
            name="Категория 123e4567-e89b-12d3-a456-426614174001",
            slug="category-nested-placeholder-uuid",
            parent=football,
            is_active=True,
        )

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        results = resp.data if isinstance(resp.data, list) else resp.data.get("results", [])
        football_data = next((c for c in results if c["id"] == football.id), None)
        assert football_data is not None, "Легитимная категория Футбол должна присутствовать в дереве"
        child_ids = {child["id"] for child in football_data.get("children", [])}
        assert nested_placeholder.id not in child_ids, (
            "Вложенная UUID-placeholder категория не должна появляться в дочерних элементах"
        )

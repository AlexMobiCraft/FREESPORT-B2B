"""
Режим `ordering=category_tree`: товары каталога в порядке дерева категорий сайдбара.

Покрывает строки матрицы спеки `spec-catalog-products-category-tree-order` (кроме двух
фронтовых): обход в глубину, нулевой `sort_order`, исключённые сайдбаром категории,
товары вне дерева якоря, два якоря, одинаковые имена, фильтр категории, пустое дерево,
цикл parent. DFS-helper `order_category_tree` проверяется отдельно на голых строках,
а `catalog_category_order()` сверяется с реальным ответом `/categories-tree/`.

Имя якоря в каждом тесте своё (`settings.ROOT_CATEGORY_NAME`): чужие категории в
тестовой БД не становятся корнями обхода, а выдача сверяется только по своим товарам.
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.products.category_utils import catalog_category_order, order_category_tree
from apps.products.factories import ProductFactory, get_unique_suffix
from apps.products.models import Category, Product

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PRODUCTS_URL = "/api/v1/products/"
CATEGORIES_TREE_URL = "/api/v1/categories-tree/"


@pytest.fixture
def root_name(settings: Any) -> str:
    """Уникальное имя якоря для теста"""
    name = f"ROOT-{get_unique_suffix()}"
    settings.ROOT_CATEGORY_NAME = name
    return name


@pytest.fixture(autouse=True)
def _clear_cache():
    """filter_category_id кэширует поддерево — не даём кэшу пережить тест"""
    cache.clear()
    yield
    cache.clear()


def _category(
    name: str,
    parent: Category | None = None,
    sort_order: int = 0,
    is_active: bool = True,
) -> Category:
    """Категория с уникальным slug: имена в тестах повторяются"""
    return Category.objects.create(
        name=name,
        slug=f"cat-{get_unique_suffix()}",
        parent=parent,
        sort_order=sort_order,
        is_active=is_active,
    )


def _product(category: Category | None, name: str | None = None, **kwargs: Any) -> Product:
    """Товар с вариантом; slug уникален даже при одинаковых именах"""
    return ProductFactory(
        category=category,
        name=name or f"Product-{get_unique_suffix()}",
        slug=f"product-{get_unique_suffix()}",
        **kwargs,
    )


def _ordered_ids(products: list[Product], **params: Any) -> list[int]:
    """id своих товаров в порядке выдачи API (чужие товары БД отбрасываются)"""
    mine = {p.id for p in products}
    response = APIClient().get(PRODUCTS_URL, {"ordering": "category_tree", "page_size": 100, **params})
    assert response.status_code == 200, response.content
    return [item["id"] for item in response.data["results"] if item["id"] in mine]


def _ids(*products: Product) -> list[int]:
    return [p.id for p in products]


class TestOrderCategoryTreeHelper:
    """DFS-helper на голых строках `(id, parent_id, sort_order)` в порядке БД."""

    def test_depth_first_parent_before_children(self):
        rows = [(10, 1, 1), (11, 10, 0), (12, 10, 0), (20, 1, 2)]
        assert order_category_tree(rows, [1]) == [10, 11, 12, 20]

    def test_zero_sort_order_goes_after_positive(self):
        # Порядок БД (sort_order, name): ноль первым, ранг переносит его в конец
        rows = [(30, 1, 0), (20, 1, 2)]
        assert order_category_tree(rows, [1]) == [20, 30]

    def test_rank_is_applied_on_every_level(self):
        rows = [(10, 1, 1), (12, 10, 0), (11, 10, 3)]
        assert order_category_tree(rows, [1]) == [10, 11, 12]

    def test_children_of_several_anchors_are_one_sibling_list(self):
        # Y (якорь 2, sort 1) раньше X (якорь 1, sort 2): ранжируются вместе
        rows = [(21, 2, 1), (11, 1, 2), (12, 1, 0)]
        assert order_category_tree(rows, [1, 2]) == [21, 11, 12]

    def test_cycle_does_not_hang_and_is_left_out(self):
        rows = [(10, 1, 1), (40, 41, 0), (41, 40, 0)]
        assert order_category_tree(rows, [1]) == [10]

    def test_cycle_through_reachable_node_is_visited_once(self):
        # Битые данные: узел 10 одновременно ребёнок якоря и потомок своего ребёнка
        rows = [(10, 1, 1), (11, 10, 0), (10, 11, 0)]
        assert order_category_tree(rows, [1]) == [10, 11]

    def test_empty_tree(self):
        assert order_category_tree([], [1]) == []
        assert order_category_tree([(10, None, 1)], []) == []


class TestCatalogCategoryOrderMatchesSidebar:
    """`catalog_category_order()` против реального ответа сайдбара `/categories-tree/`.

    Правила обхода в helper'е переписаны вручную; этот тест ловит расхождение, если
    кто-то поменяет фильтр или `order_by` дерева, а обход — нет.
    """

    def test_catalog_category_order_without_anchor_is_empty(self, root_name):
        _category("Orphan", sort_order=1)
        assert catalog_category_order() == []

    def test_order_equals_flattened_sidebar_tree(self, root_name):
        anchor = _category(root_name)
        a = _category("Единоборства", anchor, sort_order=1)
        _category("Капы", a, sort_order=0)
        _category("Бинты", a, sort_order=0)
        _category("Защита корпуса", a, sort_order=2)
        shoes = _category("Обувь", a, sort_order=1)
        _category("Обувь для бокса", shoes, sort_order=0)
        _category("Аксессуары", anchor, sort_order=0)
        _category("Ворота", anchor, sort_order=3)
        _category(f"Категория {uuid.uuid4()}", a, sort_order=1)

        response = APIClient().get(CATEGORIES_TREE_URL)
        assert response.status_code == 200, response.content

        def flatten(nodes: list[dict[str, Any]]) -> list[int]:
            # Как sortCategoryTree фронта: стабильно по рангу поверх порядка API
            ranked = sorted(
                nodes, key=lambda n: 2 if n["slug"] == "uncategorized" else (0 if n["sort_order"] > 0 else 1)
            )
            result: list[int] = []
            for node in ranked:
                result += [node["id"], *flatten(node["children"])]
            return result

        assert catalog_category_order() == flatten(response.data)


class TestCategoryTreeOrderingApi:
    """`GET /api/v1/products/?ordering=category_tree` — строки матрицы спеки."""

    def test_depth_first_and_parent_before_children(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        a1 = _category("A1-branch", a, sort_order=1)
        a2 = _category("A2-branch", a, sort_order=2)
        b = _category("B-branch", anchor, sort_order=2)
        # Имена товаров против порядка дерева: сортировка по названию дала бы обратное
        pb = _product(b, "a-product")
        pa2 = _product(a2, "b-product")
        pa1 = _product(a1, "c-product")
        pa = _product(a, "d-product")

        assert _ordered_ids([pa, pa1, pa2, pb]) == _ids(pa, pa1, pa2, pb)

    def test_zero_sort_order_after_positive(self, root_name):
        anchor = _category(root_name)
        v = _category("V-zero", anchor, sort_order=0)
        b = _category("B-two", anchor, sort_order=2)
        pv = _product(v, "a-product")
        pb = _product(b, "b-product")

        assert _ordered_ids([pv, pb]) == _ids(pb, pv)

    def test_zero_sort_order_siblings_by_name(self, root_name):
        anchor = _category(root_name)
        kapy = _category("Капы", anchor, sort_order=0)
        binty = _category("Бинты", anchor, sort_order=0)
        pk = _product(kapy, "a-product")
        pb = _product(binty, "b-product")

        assert _ordered_ids([pk, pb]) == _ids(pb, pk)

    def test_excluded_categories_go_to_the_end(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        b = _category("B-branch", anchor, sort_order=2)
        # update_or_create: служебная категория могла остаться в БД от интеграционных тестов
        uncategorized, _ = Category.objects.update_or_create(
            slug="uncategorized",
            defaults={"name": "Uncategorized", "parent": a, "sort_order": 1, "is_active": True},
        )
        placeholder = _category(f"Категория {uuid.uuid4()}", a, sort_order=1)
        placeholder_child = _category("Child-of-placeholder", placeholder, sort_order=1)
        no_category = _category("Без категории", a, sort_order=1)
        pa = _product(a, "x-product")
        pb = _product(b, "y-product")
        # Имена раньше по алфавиту: в конце они оказываются только из-за исключения
        tail = [
            _product(uncategorized, "a-tail"),
            _product(placeholder, "b-tail"),
            _product(placeholder_child, "c-tail"),
            _product(no_category, "d-tail"),
        ]

        assert _ordered_ids([pa, pb, *tail]) == _ids(pa, pb, *tail)

    def test_category_outside_anchor_tree_goes_to_the_end(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        foreign_root = _category("Foreign-root", sort_order=1)
        foreign_child = _category("Foreign-child", foreign_root, sort_order=1)
        p_foreign = _product(foreign_root, "a-foreign")
        p_foreign_child = _product(foreign_child, "b-foreign")
        pa = _product(a, "z-product")

        assert _ordered_ids([p_foreign, p_foreign_child, pa]) == _ids(pa, p_foreign, p_foreign_child)

    def test_two_anchors_rank_children_together(self, root_name):
        anchor_1 = _category(root_name)
        anchor_2 = _category(root_name)
        x = _category("X-branch", anchor_1, sort_order=2)
        y = _category("Y-branch", anchor_2, sort_order=1)
        z = _category("Z-branch", anchor_1, sort_order=3)
        px = _product(x, "a-product")
        pz = _product(z, "b-product")
        py = _product(y, "c-product")

        assert _ordered_ids([px, py, pz]) == _ids(py, px, pz)

    def test_same_names_ordered_by_id(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        first = _product(a, "Same name")
        second = _product(a, "Same name")
        other = _product(a, "Another name")

        assert _ordered_ids([first, second, other]) == _ids(other, first, second)

    def test_category_filter_keeps_subtree_order(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        a1 = _category("A1-branch", a, sort_order=1)
        a2 = _category("A2-branch", a, sort_order=2)
        b = _category("B-branch", anchor, sort_order=2)
        pa2 = _product(a2, "a-product")
        pa1 = _product(a1, "b-product")
        pa = _product(a, "c-product")
        pb = _product(b, "d-product")

        result = _ordered_ids([pa, pa1, pa2, pb], category_id=a.id)

        assert result == _ids(pa, pa1, pa2)

    def test_empty_tree_falls_back_to_name_then_id(self, root_name):
        # Якоря с именем root_name нет — обход пуст
        c = _category("Lonely", sort_order=1)
        second_same = _product(c, "b-product")
        third = _product(c, "c-product")
        first = _product(c, "a-product")
        same = _product(c, "b-product")

        assert _ordered_ids([first, second_same, same, third]) == _ids(first, second_same, same, third)

    def test_parent_cycle_is_left_out_of_traversal(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        b = _category("B-branch", anchor, sort_order=2)
        c1 = _category("Cycle-1", sort_order=1)
        c2 = _category("Cycle-2", c1, sort_order=1)
        # Цикл parent собирается в обход save(): модель такого не допустила бы
        Category.objects.filter(pk=c1.pk).update(parent=c2)
        # Товары в самих узлах цикла не создаются: Category.full_name рекурсирует по
        # parent без защиты, и сериализация такого товара падает в любом ordering —
        # дефект вне этой задачи. Здесь проверяется, что цикл не вешает обход.
        pb = _product(b, "a-product")
        pa = _product(a, "z-product")

        order = catalog_category_order()

        assert c1.id not in order and c2.id not in order
        assert order.index(a.id) < order.index(b.id)
        assert _ordered_ids([pa, pb]) == _ids(pa, pb)

    def test_pages_do_not_overlap(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        b = _category("B-branch", anchor, sort_order=2)
        products = [_product(a, "Same") for _ in range(3)] + [_product(b, "Same") for _ in range(2)]
        mine = {p.id for p in products}

        seen: list[int] = []
        client = APIClient()
        for page in (1, 2, 3):
            query: dict[str, Any] = {"ordering": "category_tree", "page_size": 2, "page": page}
            response = client.get(PRODUCTS_URL, query)
            assert response.status_code == 200
            seen += [item["id"] for item in response.data["results"] if item["id"] in mine]

        assert seen == _ids(*products)

    def test_search_with_category_tree(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        b = _category("B-branch", anchor, sort_order=2)
        token = f"TREESKU{get_unique_suffix()}".upper()
        pb = _product(b, "a-product", sku=f"{token}-B")
        pa = _product(a, "b-product", sku=f"{token}-A")

        assert _ordered_ids([pa, pb], search=token) == _ids(pa, pb)

    def test_other_orderings_unchanged(self, root_name):
        anchor = _category(root_name)
        a = _category("A-branch", anchor, sort_order=1)
        b = _category("B-branch", anchor, sort_order=2)
        pb = _product(b, "a-product")
        pa = _product(a, "b-product")
        mine = {pa.id, pb.id}

        query: dict[str, Any] = {"ordering": "name", "page_size": 100}
        response = APIClient().get(PRODUCTS_URL, query)
        assert response.status_code == 200
        assert [i["id"] for i in response.data["results"] if i["id"] in mine] == _ids(pb, pa)

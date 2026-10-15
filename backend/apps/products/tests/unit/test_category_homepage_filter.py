"""
Фильтр is_homepage у CategoryFilter: на главную попадают только корни витрины
(прямые дети якоря ROOT_CATEGORY_NAME) с sort_order > 0. Подкатегориям sort_order
задаёт лишь порядок в каталоге.
"""

from __future__ import annotations

from typing import cast

import pytest
from django.contrib import admin
from django.test import RequestFactory

from apps.products.admin import CategoryAdmin, IsOnHomepageFilter
from apps.products.factories import CategoryFactory
from apps.products.filters import CategoryFilter
from apps.products.models import Category

# Своё имя якоря: в тестовой БД могут лежать категории из data-миграций
ANCHOR_NAME = "ЯКОРЬ-ТЕСТ-ГЛАВНОЙ"


def homepage_ids() -> set[int]:
    qs = CategoryFilter({"is_homepage": "true"}, queryset=Category.objects.all()).qs
    return set(qs.values_list("id", flat=True))


@pytest.mark.django_db
class TestHomepageCategoryFilter:
    @pytest.fixture(autouse=True)
    def anchor_name(self, settings):
        settings.ROOT_CATEGORY_NAME = ANCHOR_NAME

    @pytest.fixture
    def anchor(self):
        return CategoryFactory(name=ANCHOR_NAME, parent=None)

    def test_showcase_root_with_sort_order_included(self, anchor):
        root = CategoryFactory(parent=anchor, sort_order=1)

        assert root.id in homepage_ids()

    def test_subcategory_with_sort_order_excluded(self, anchor):
        root = CategoryFactory(parent=anchor, sort_order=2)
        child = CategoryFactory(parent=root, sort_order=3)

        ids = homepage_ids()

        assert root.id in ids
        assert child.id not in ids

    def test_showcase_root_without_sort_order_excluded(self, anchor):
        root = CategoryFactory(parent=anchor, sort_order=0)

        assert root.id not in homepage_ids()

    def test_children_of_inactive_anchor_excluded(self, anchor):
        # Свой slug: тот же name транслитерируется в slug первого якоря
        inactive_anchor = CategoryFactory(name=ANCHOR_NAME, slug="yakor-test-neaktivnyj", parent=None, is_active=False)
        active_root = CategoryFactory(parent=anchor, sort_order=1)
        stale_root = CategoryFactory(parent=inactive_anchor, sort_order=1)

        ids = homepage_ids()

        assert active_root.id in ids
        assert stale_root.id not in ids

    def test_without_flag_returns_all(self, anchor):
        child = CategoryFactory(parent=CategoryFactory(parent=anchor), sort_order=0)

        qs = CategoryFilter({}, queryset=Category.objects.all()).qs

        assert qs.filter(id=child.id).exists()


@pytest.mark.django_db
class TestAdminIsOnHomepageFilter:
    """Фильтр админки «На главной» совпадает с API главной."""

    @pytest.fixture(autouse=True)
    def anchor_name(self, settings):
        settings.ROOT_CATEGORY_NAME = ANCHOR_NAME

    def admin_ids(self, value: str) -> set[int]:
        request = RequestFactory().get("/")
        # Django 5 передаёт значения параметров списком, стабы ждут строку
        params = cast(dict[str, str], {"is_homepage": [value]})
        model_admin = CategoryAdmin(Category, admin.site)
        flt = IsOnHomepageFilter(request, params, Category, model_admin)
        qs = flt.queryset(request, Category.objects.all())
        assert qs is not None
        return set(qs.values_list("id", flat=True))

    def test_yes_and_no_split_by_homepage_rule(self):
        anchor = CategoryFactory(name=ANCHOR_NAME, parent=None)
        root = CategoryFactory(parent=anchor, sort_order=1)
        child = CategoryFactory(parent=root, sort_order=2)
        orphan = CategoryFactory(parent=None, sort_order=3)

        yes, no = self.admin_ids("yes"), self.admin_ids("no")

        assert root.id in yes and root.id not in no
        for category in (child, orphan, anchor):
            assert category.id in no and category.id not in yes

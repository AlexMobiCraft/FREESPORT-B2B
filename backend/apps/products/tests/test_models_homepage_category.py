"""
Тесты для HomepageCategory proxy модели.
Story: home-categories-refactor, Task 1.
"""

import pytest

from apps.products.models import Category, HomepageCategory


class TestHomepageCategoryMeta:
    """Тесты Meta proxy модели HomepageCategory (без БД)."""

    def test_is_proxy_model(self):
        assert HomepageCategory._meta.proxy is True

    def test_shares_db_table_with_category(self):
        assert HomepageCategory._meta.db_table == Category._meta.db_table

    def test_verbose_name(self):
        assert HomepageCategory._meta.verbose_name == "Категория для главной"

    def test_verbose_name_plural(self):
        assert HomepageCategory._meta.verbose_name_plural == "Категории для главной"

    def test_default_ordering(self):
        assert list(HomepageCategory._meta.ordering or []) == ["sort_order", "id"]

    def test_str_method_inherited(self):
        cat = HomepageCategory(name="Бег", slug="beg")
        assert str(cat) == "Бег"


@pytest.mark.django_db
class TestHomepageCategoryDB:
    """Тесты proxy модели с доступом к БД."""

    def test_proxy_queryset_returns_categories(self):
        cat = Category.objects.create(
            name="Тестовая",
            slug="test-proxy-qs",
            sort_order=1,
        )
        assert HomepageCategory.objects.filter(pk=cat.pk).exists()

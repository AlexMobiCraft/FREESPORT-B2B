"""
Unit-тесты раздела маркетинга `/marketing/` (стори 42.6): доступ к сайту, кэш
членства на запросе, состав регистрации, плашка подписчиков и белые списки
полей товара и бренда.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group
from django.db import connection
from django.test import RequestFactory

from apps.banners.admin import BannerAdmin
from apps.banners.models import Banner
from apps.common.admin import BlogPostAdmin, ContentCategoryAdmin, NewsAdmin
from apps.common.marketing_admin import newsletter_stats
from apps.common.models import BlogPost, Category, News
from apps.products.admin import BrandAdmin, HomepageCategoryAdmin, ProductAdmin
from apps.products.factories import ProductFactory
from apps.products.models import Brand, HomepageCategory, Product
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import manager_site, marketing_site
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")

# Скрытые поля товара и бренда: ни правкой, ни чтением в разделе их нет.
PRODUCT_HIDDEN_FIELDS = {
    "slug",
    "description",
    "short_description",
    "specifications",
    "base_images",
    "seo_title",
    "seo_description",
    "is_featured",
    "min_order_quantity",
    "onec_id",
    "parent_onec_id",
    "onec_brand_id",
    "sync_status",
    "last_sync_at",
    "error_message",
    "onec_deleted",
    "vat_rate",
    "is_active",
    "created_at",
    "updated_at",
}
BRAND_HIDDEN_FIELDS = {"slug", "normalized_name", "website", "created_at", "updated_at"}
LABEL_ACTIONS = (
    "mark_as_hit",
    "unmark_as_hit",
    "mark_as_new",
    "unmark_as_new",
    "mark_as_sale",
    "unmark_as_sale",
    "mark_as_promo",
    "unmark_as_promo",
    "mark_as_premium",
    "unmark_as_premium",
)


@pytest.fixture(autouse=True)
def role_groups():
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


def make_user(group_name: str | None = None, **extra) -> User:
    user = User.objects.create_user(email=f"u_{get_unique_suffix()}@example.com", password=PASSWORD, **extra)
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    return User.objects.get(pk=user.pk)


def request_for(user, path: str = "/marketing/"):
    request = RequestFactory().get(path)
    request.user = user
    return request


def fields_of(fieldsets) -> set[str]:
    return {name for _, options in fieldsets for name in options["fields"]}


class TestHasPermission:
    @pytest.mark.parametrize(
        "group_name, extra, expected",
        [
            (MARKETING_GROUP, {"is_staff": True}, True),
            (SUPERVISORS_GROUP, {"is_staff": True}, True),
            (MANAGERS_GROUP, {"is_staff": True}, False),
            (None, {"is_staff": True}, False),
            (MARKETING_GROUP, {"is_staff": False}, False),
            (MARKETING_GROUP, {"is_staff": True, "is_active": False}, False),
            (MARKETING_GROUP, {"is_staff": True, "is_superuser": True}, False),
            (None, {"is_staff": True, "is_superuser": True}, False),
        ],
    )
    def test_matrix(self, group_name, extra, expected):
        user = make_user(group_name, **extra)
        assert marketing_site.has_permission(request_for(user)) is expected

    def test_anonymous(self):
        assert marketing_site.has_permission(request_for(AnonymousUser())) is False

    def test_membership_is_read_once_per_request(self, django_assert_num_queries):
        user = make_user(MARKETING_GROUP, is_staff=True)
        request = request_for(user)

        with django_assert_num_queries(1):
            assert marketing_site.has_permission(request)
            assert marketing_site.has_permission(request)

    @pytest.mark.parametrize("order", ["manager-first", "marketing-first"])
    def test_one_request_on_two_sites(self, order):
        """Кэш членства — по имени сайта: ответ одного раздела не достаётся другому."""
        manager = make_user(MANAGERS_GROUP, is_staff=True)
        request = request_for(manager)
        sites = [manager_site, marketing_site] if order == "manager-first" else [marketing_site, manager_site]

        results = {site.name: site.has_permission(request) for site in sites}
        # Повторный вызов — из кэша, тот же ответ.
        results_again = {site.name: site.has_permission(request) for site in sites}

        assert results == {"manager": True, "marketing": False}
        assert results_again == results

    def test_supervisor_on_both_sites(self):
        supervisor = make_user(SUPERVISORS_GROUP, is_staff=True)
        request = request_for(supervisor)

        assert manager_site.has_permission(request) is True
        assert marketing_site.has_permission(request) is True


class TestRegistry:
    def test_marketing_site_has_exactly_seven_models(self):
        assert {model._meta.label for model in marketing_site._registry} == {
            "banners.Banner",
            "common.News",
            "common.BlogPost",
            "common.Category",
            "products.Product",
            "products.Brand",
            "products.HomepageCategory",
        }

    def test_main_admin_keeps_parent_classes(self):
        assert type(admin.site._registry[Product]) is ProductAdmin
        assert type(admin.site._registry[Brand]) is BrandAdmin
        assert type(admin.site._registry[HomepageCategory]) is HomepageCategoryAdmin
        assert type(admin.site._registry[Banner]) is BannerAdmin
        assert type(admin.site._registry[News]) is NewsAdmin
        assert type(admin.site._registry[BlogPost]) is BlogPostAdmin
        assert type(admin.site._registry[Category]) is ContentCategoryAdmin

    def test_no_view_on_site_in_section(self):
        for model, model_admin in marketing_site._registry.items():
            assert model_admin.view_on_site is False, model

    def test_titles(self):
        assert marketing_site.site_header == "OPTISPORT — Маркетинг"
        assert marketing_site.site_title == "OPTISPORT — Маркетинг"
        assert marketing_site.index_title == "Раздел маркетинга"


class TestNewsletterStats:
    def test_empty(self):
        assert newsletter_stats() == {"total": 0, "recent": 0, "text": "Подписчиков: 0 (+0 за 30 дней)"}


class TestWhitelists:
    def test_product_card(self):
        model_admin = marketing_site._registry[Product]
        request = request_for(make_user(MARKETING_GROUP, is_staff=True))
        product = ProductFactory()

        fields = fields_of(model_admin.get_fieldsets(request, product))
        readonly = set(model_admin.get_readonly_fields(request, product))

        assert fields == {
            "name",
            "brand_link",
            "category_name",
            "discount_percent",
            "is_hit",
            "is_new",
            "is_sale",
            "is_promo",
            "is_premium",
        }
        assert readonly == {"name", "brand_link", "category_name", "discount_percent"}
        assert not (fields | readonly) & PRODUCT_HIDDEN_FIELDS
        assert model_admin.get_inline_instances(request, product) == []

    def test_brand_card(self):
        model_admin = marketing_site._registry[Brand]
        request = request_for(make_user(MARKETING_GROUP, is_staff=True))

        fields = fields_of(model_admin.get_fieldsets(request))
        readonly = set(model_admin.get_readonly_fields(request))

        assert fields == {"name", "is_active", "image", "is_featured", "description"}
        assert readonly == {"name", "is_active"}
        assert not (fields | readonly) & BRAND_HIDDEN_FIELDS
        assert model_admin.get_inline_instances(request) == []

    def test_label_actions_require_change(self):
        """Решение 9: действия меток — только с правом change, в /admin/ и в разделе."""
        for name in LABEL_ACTIONS:
            action = getattr(ProductAdmin, name)
            assert tuple(action.allowed_permissions) == ("change",), name

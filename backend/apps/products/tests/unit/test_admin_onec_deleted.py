"""
Админка: флаг «Скрыт импортом 1С» и реестр исключённых Ид.

Флаг ставит и снимает только импорт — руками он не правится; реестр доступен
только на чтение.
"""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from django.urls import reverse

from apps.products.admin import OnecExcludedItemAdmin, ProductAdmin, ProductVariantAdmin
from apps.products.models import OnecExcludedItem, Product, ProductVariant

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


@pytest.fixture
def superuser():
    return get_user_model().objects.create_superuser(email="onec-admin@freesport.test", password="pass12345")


@pytest.fixture
def request_as_superuser(superuser):
    request = RequestFactory().get("/admin/")
    request.user = superuser
    return request


@pytest.mark.parametrize(("admin_class", "model"), [(ProductAdmin, Product), (ProductVariantAdmin, ProductVariant)])
def test_onec_deleted_is_column_filter_and_readonly(admin_class, model):
    model_admin = admin_class(model, AdminSite())

    assert "onec_deleted" in model_admin.list_display
    assert "onec_deleted" in model_admin.list_filter
    assert "onec_deleted" in model_admin.readonly_fields
    fieldset_fields = [field for _, options in model_admin.fieldsets for field in options["fields"]]
    assert "onec_deleted" in fieldset_fields


def test_registry_admin_is_read_only(request_as_superuser):
    item = OnecExcludedItem.objects.create(onec_id="admin-excluded", kind="product", reason="вне дерева")
    model_admin = OnecExcludedItemAdmin(OnecExcludedItem, AdminSite())

    assert model_admin.has_add_permission(request_as_superuser) is False
    assert model_admin.has_change_permission(request_as_superuser, item) is False
    assert model_admin.has_delete_permission(request_as_superuser, item) is False
    assert model_admin.has_view_permission(request_as_superuser, item) is True
    assert set(model_admin.readonly_fields) == {"onec_id", "kind", "reason", "updated_at"}


def test_registry_changelist_is_available(client, superuser):
    OnecExcludedItem.objects.create(onec_id="admin-listed", kind="offer", reason="пометка предложения")
    client.force_login(superuser)

    response = client.get(reverse("admin:products_onecexcludeditem_changelist"))

    assert response.status_code == 200
    assert "admin-listed" in response.content.decode()


def test_product_changelist_filters_by_onec_deleted(client, superuser):
    client.force_login(superuser)

    response = client.get(reverse("admin:products_product_changelist"), {"onec_deleted__exact": "1"})

    assert response.status_code == 200

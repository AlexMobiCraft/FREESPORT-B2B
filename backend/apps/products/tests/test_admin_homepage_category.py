"""
Тесты для HomepageCategoryAdmin.
Story: home-categories-refactor, Task 2.
"""

from django.contrib import admin
from django.test import RequestFactory

from apps.products.admin import HomepageCategoryAdmin
from apps.products.models import HomepageCategory


class TestHomepageCategoryAdminRegistration:
    """Тесты регистрации и конфигурации HomepageCategoryAdmin (без БД)."""

    def setup_method(self):
        self.admin_class = HomepageCategoryAdmin

    def test_model_is_registered(self):
        """HomepageCategory зарегистрирована в admin."""
        assert HomepageCategory in admin.site._registry

    def test_admin_class_is_correct(self):
        """Используется именно HomepageCategoryAdmin."""
        registered = admin.site._registry[HomepageCategory]
        assert isinstance(registered, HomepageCategoryAdmin)

    def test_list_display_contains_required_fields(self):
        """list_display содержит image_preview, name, sort_order, is_active."""
        required = {"image_preview", "name", "sort_order", "is_active"}
        assert required.issubset(set(self.admin_class.list_display))

    def test_list_editable_contains_sort_order_and_is_active(self):
        """list_editable содержит sort_order и is_active."""
        assert "sort_order" in self.admin_class.list_editable
        assert "is_active" in self.admin_class.list_editable

    def test_has_delete_permission_returns_false(self):
        """has_delete_permission всегда False (защита от удаления)."""
        instance = admin.site._registry[HomepageCategory]
        request = RequestFactory().get("/")
        assert instance.has_delete_permission(request=request) is False

    def test_ordering(self):
        """Сортировка по sort_order."""
        assert self.admin_class.ordering == ("sort_order",)

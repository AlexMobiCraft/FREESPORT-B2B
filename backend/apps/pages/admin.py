"""
Django Admin для статических страниц
"""

from django.contrib import admin

from .models import Page


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    """Админ интерфейс для статических страниц"""

    list_display = ["title", "slug", "is_published", "updated_at"]
    list_filter = ["is_published", "created_at"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        ("Основное", {"fields": ("title", "slug", "content", "is_published")}),
        ("SEO", {"fields": ("seo_title", "seo_description"), "classes": ("collapse",)}),
    )

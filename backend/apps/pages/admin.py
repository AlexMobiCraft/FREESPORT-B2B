"""
Django Admin для статических страниц
"""

from django.contrib import admin

from apps.common.rich_editor import RichContentAdminMixin

from .models import Page


@admin.register(Page)
class PageAdmin(RichContentAdminMixin, admin.ModelAdmin):
    """Админ интерфейс для статических страниц"""

    # Текст страницы лежит в `container` внутри `Card` (px-4, p-10): 1280 - 32 - 80 на
    # ширине xl. На другой ширине экрана колонка другая, редактор показывает типичную.
    rich_editor_column_width = 1168

    list_display = ["title", "slug", "is_published", "updated_at"]
    list_filter = ["is_published", "created_at"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ("title",)}

    fieldsets = (
        ("Основное", {"fields": ("title", "slug", "content", "is_published")}),
        ("SEO", {"fields": ("seo_title", "seo_description"), "classes": ("collapse",)}),
    )

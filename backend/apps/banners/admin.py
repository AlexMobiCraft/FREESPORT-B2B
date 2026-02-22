"""
Django Admin для приложения banners
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import Banner


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """Admin для модели Banner"""

    list_display = (
        "title",
        "type",
        "image_preview",
        "get_is_active_display",
        "priority",
        "target_groups_display",
        "start_date",
        "end_date",
    )
    list_filter = (
        "type",
        "is_active",
        "show_to_guests",
        "show_to_authenticated",
        "show_to_trainers",
        "show_to_wholesale",
        "show_to_federation",
    )
    search_fields = ("title", "subtitle")
    readonly_fields = ("created_at", "updated_at", "image_preview")

    fieldsets = (
        (
            "Контент",
            {
                "fields": (
                    "type",
                    "title",
                    "subtitle",
                    "image",
                    "image_preview",
                    "image_alt",
                    "cta_text",
                    "cta_link",
                ),
            },
        ),
        (
            "Таргетинг",
            {
                "fields": (
                    "show_to_guests",
                    "show_to_authenticated",
                    "show_to_trainers",
                    "show_to_wholesale",
                    "show_to_federation",
                ),
                "description": ("Выберите целевые группы пользователей для показа баннера"),
            },
        ),
        (
            "Управление",
            {
                "fields": (
                    "is_active",
                    "priority",
                    "start_date",
                    "end_date",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Превью")
    def image_preview(self, obj: Banner) -> SafeString:
        """Отображает превью изображения в списке и детальном просмотре"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 100px;" />',
                obj.image.url,
            )
        return format_html('<span style="color: #999;">{}</span>', "Нет изображения")

    @admin.display(description="Целевые группы")
    def target_groups_display(self, obj: Banner) -> str:
        """Отображает список целевых групп пользователей"""
        groups = []
        if obj.show_to_guests:
            groups.append("Гости")
        if obj.show_to_authenticated:
            groups.append("Авторизованные")
        if obj.show_to_trainers:
            groups.append("Тренеры")
        if obj.show_to_wholesale:
            groups.append("Оптовики")
        if obj.show_to_federation:
            groups.append("Федерации")

        return ", ".join(groups) if groups else "Не настроено"

    @admin.display(description="Статус (с учетом дат)", boolean=True)
    def get_is_active_display(self, obj: Banner) -> bool:
        """Отображает реальный статус активности с учетом расписания"""
        return obj.is_scheduled_active

"""
Django Admin конфигурация для управления способами доставки.
"""

from django.contrib import admin

from .models import DeliveryMethod


@admin.register(DeliveryMethod)
class DeliveryMethodAdmin(admin.ModelAdmin):
    """Админ-панель для управления способами доставки."""

    list_display = ["id", "name", "icon", "is_available", "sort_order"]
    list_editable = ["is_available", "sort_order"]
    list_filter = ["is_available"]
    search_fields = ["name", "description"]
    ordering = ["sort_order"]
    fieldsets = (
        (
            None,
            {
                "fields": ("id", "name", "description", "icon"),
            },
        ),
        (
            "Настройки",
            {
                "fields": ("is_available", "sort_order"),
            },
        ),
    )

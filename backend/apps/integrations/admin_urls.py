"""
Регистрация custom URLs для Django Admin в приложении integrations.

Этот модуль выполняет monkey-patching Django admin site для добавления
custom URL страницы "Импорт из 1С".
"""

from django.contrib import admin
from django.urls import path

from apps.integrations.views import import_from_1c_view

# Сохраняем оригинальный метод get_urls
_original_get_urls = admin.site.get_urls


def _custom_get_urls() -> list:
    """
    Добавляет custom URL для страницы импорта к стандартным admin URLs.

    Returns:
        List URL patterns включая custom URL для импорта из 1С
    """
    custom_urls = [
        path(
            "integrations/import_1c/",
            admin.site.admin_view(import_from_1c_view),
            name="integrations_import_from_1c",
        ),
    ]
    return custom_urls + _original_get_urls()


# Применяем monkey-patch к admin site
admin.site.get_urls = _custom_get_urls  # type: ignore[method-assign]

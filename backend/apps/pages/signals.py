"""
Signals для автоматической инвалидации кэша страниц
"""

from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Page


@receiver([post_save, post_delete], sender=Page)
def invalidate_page_cache(sender, instance, **kwargs):
    """Инвалидация кэша при изменении страницы"""
    # Инвалидация кэша списка страниц
    cache.delete("pages_list")

    # Инвалидация кэша конкретной страницы
    cache.delete(f"page_detail_{instance.slug}")

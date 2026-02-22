"""
Signals для инвалидации кэша featured brands при изменении Brand.

LIMITATION: QuerySet.update() и bulk_create/bulk_update обходят Django signals,
поэтому кэш НЕ инвалидируется при массовых операциях. Для таких случаев
необходимо вручную вызывать cache.delete(FEATURED_BRANDS_CACHE_KEY).
"""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .constants import FEATURED_BRANDS_CACHE_KEY
from .models import Brand

# Поля Brand, влияющие на featured endpoint payload.
_FEATURED_RELEVANT_FIELDS = frozenset({"is_featured", "is_active", "name", "slug", "image", "website"})


@receiver(pre_save, sender=Brand)
def track_brand_previous_state(sender, instance, **kwargs):
    """Сохраняет предыдущее состояние полей Brand перед save для сравнения в post_save."""
    if instance.pk:
        try:
            old = Brand.objects.filter(pk=instance.pk).values(*_FEATURED_RELEVANT_FIELDS).first()
            instance._pre_save_state = old
        except Exception:
            instance._pre_save_state = None
    else:
        # Новый объект — всегда инвалидируем если is_featured=True
        instance._pre_save_state = None


@receiver(post_save, sender=Brand)
def invalidate_featured_brands_cache_on_save(sender, instance, created, **kwargs):
    """Очищает кэш featured brands только если изменились релевантные поля.

    Оптимизация: если обновлено только поле вроде description, инвалидация
    не происходит, предотвращая cache thrashing.

    Использует transaction.on_commit чтобы кэш очищался только после
    успешного коммита транзакции, предотвращая race condition.
    """
    if created:
        if instance.is_featured and instance.is_active:
            transaction.on_commit(lambda: cache.delete(FEATURED_BRANDS_CACHE_KEY))
        return

    old = getattr(instance, "_pre_save_state", None)
    if old is None:
        # Не удалось загрузить предыдущее состояние — безопасная инвалидация
        transaction.on_commit(lambda: cache.delete(FEATURED_BRANDS_CACHE_KEY))
        return

    # Проверяем, изменились ли релевантные поля
    for field in _FEATURED_RELEVANT_FIELDS:
        old_value = old.get(field)
        new_value = getattr(instance, field)
        # ImageField хранится как строка пути
        if hasattr(new_value, "name"):
            new_value = new_value.name
        if str(old_value) != str(new_value):
            transaction.on_commit(lambda: cache.delete(FEATURED_BRANDS_CACHE_KEY))
            return


@receiver(post_delete, sender=Brand)
def invalidate_featured_brands_cache_on_delete(sender, instance, **kwargs):
    """Очищает кэш featured brands при удалении Brand.

    Инвалидирует только если удалённый бренд мог быть в featured выдаче.
    """
    if instance.is_featured and instance.is_active:
        transaction.on_commit(lambda: cache.delete(FEATURED_BRANDS_CACHE_KEY))

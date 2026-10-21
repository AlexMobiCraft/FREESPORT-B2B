"""
Signals для инвалидации кэша featured brands при изменении Brand.

Сохранение бренда, который был или стал избранным, после commit сбрасывает и
ISR-кэш главной Next (`/home`): она рендерит избранные бренды на сервере и без
сброса показала бы правку только через час (стори 42.6).

LIMITATION: QuerySet.update() и bulk_create/bulk_update обходят Django signals,
поэтому кэш НЕ инвалидируется при массовых операциях. Для таких случаев
необходимо вручную вызывать cache.delete(FEATURED_BRANDS_CACHE_KEY).
"""

from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from apps.common.services.nextjs_revalidate import HOME_PAGE_PATH, revalidate_nextjs_path_in_background

from .constants import FEATURED_BRANDS_CACHE_KEY
from .models import Brand

# Поля Brand, влияющие на featured endpoint payload.
_FEATURED_RELEVANT_FIELDS = frozenset({"is_featured", "is_active", "name", "slug", "image", "website"})


def _on_featured_change(*, reset_api_cache: bool, was_featured: bool, is_featured: bool) -> None:
    """После commit сбрасывает кэш featured endpoint и, для избранного бренда, ISR главной.

    Неизбранный бренд на главной не виден, а импорт 1С правит name/is_active у
    многих брендов: без условия каждый прогон слал бы запрос в Next на каждый.
    """
    refresh_home = was_featured or is_featured
    if not (reset_api_cache or refresh_home):
        return

    def _after_commit() -> None:
        # Сначала кэш API: пересборка главной читает featured endpoint.
        if reset_api_cache:
            cache.delete(FEATURED_BRANDS_CACHE_KEY)
        if refresh_home:
            revalidate_nextjs_path_in_background(HOME_PAGE_PATH)

    transaction.on_commit(_after_commit)


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
        _on_featured_change(
            reset_api_cache=instance.is_featured and instance.is_active,
            was_featured=False,
            is_featured=instance.is_featured,
        )
        return

    old = getattr(instance, "_pre_save_state", None)
    if old is None:
        # Не удалось загрузить предыдущее состояние — безопасная инвалидация
        _on_featured_change(reset_api_cache=True, was_featured=True, is_featured=instance.is_featured)
        return

    # Проверяем, изменились ли релевантные поля
    changed = False
    for field in _FEATURED_RELEVANT_FIELDS:
        old_value = old.get(field)
        new_value = getattr(instance, field)
        # ImageField хранится как строка пути
        if hasattr(new_value, "name"):
            new_value = new_value.name
        if str(old_value) != str(new_value):
            changed = True
            break

    _on_featured_change(
        reset_api_cache=changed,
        was_featured=bool(old.get("is_featured")),
        is_featured=instance.is_featured,
    )


@receiver(post_delete, sender=Brand)
def invalidate_featured_brands_cache_on_delete(sender, instance, **kwargs):
    """Очищает кэш featured brands при удалении Brand.

    Инвалидирует только если удалённый бренд мог быть в featured выдаче.
    """
    _on_featured_change(
        reset_api_cache=instance.is_featured and instance.is_active,
        was_featured=instance.is_featured,
        is_featured=instance.is_featured,
    )

"""
Сигналы для приложения banners — кэш-инвалидация

Story 32.1 AC3: Saving/deleting a banner invalidates the API cache
for that specific banner type (key pattern: banners:list:{type}:{role})

Story 32.4 CR-8: При смене type у существующего баннера инвалидируются
оба типа (старый + новый) через pre_save tracking.

Сохранение существующего баннера переписывает его снимок (название, реквизиты
рекламодателя) в строках дневной статистики — см. `sync_daily_stat_snapshots`.
"""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from .models import Banner
from .services import invalidate_banner_cache, sync_daily_stat_snapshots


@receiver(pre_save, sender=Banner)
def track_old_banner_type(sender: type[Banner], instance: Banner, **kwargs: Any) -> None:
    """
    Сохраняет старый type баннера перед save для инвалидации кеша обоих типов.

    CR-8: При смене hero→marketing нужно инвалидировать кеш и hero, и marketing.
    """
    if instance.pk:
        try:
            old_instance = Banner.objects.only("type").get(pk=instance.pk)
            instance._old_type = old_instance.type  # type: ignore[attr-defined]
        except Banner.DoesNotExist:
            instance._old_type = None  # type: ignore[attr-defined]
    else:
        instance._old_type = None  # type: ignore[attr-defined]


@receiver(post_save, sender=Banner)
def invalidate_banner_cache_on_save(sender: type[Banner], instance: Banner, **kwargs: Any) -> None:
    """
    Инвалидирует кэш при сохранении баннера.

    AC3: cache key pattern banners:list:{type}:{role}
    CR-8: При смене type инвалидирует кеш обоих типов (старый + новый).
    """
    invalidate_banner_cache(instance.type)

    old_type = getattr(instance, "_old_type", None)
    if old_type and old_type != instance.type:
        invalidate_banner_cache(old_type)


@receiver(post_save, sender=Banner)
def sync_daily_stats_on_save(
    sender: type[Banner], instance: Banner, created: bool = False, raw: bool = False, **kwargs: Any
) -> None:
    """
    Переписывает снимок баннера в его строках статистики.

    У нового баннера строк ещё нет; при `raw` (loaddata) данные фикстуры
    загружаются как есть.
    """
    if created or raw:
        return
    sync_daily_stat_snapshots(instance)


@receiver(post_delete, sender=Banner)
def invalidate_banner_cache_on_delete(sender: type[Banner], instance: Banner, **kwargs: Any) -> None:
    """
    Инвалидирует кэш при удалении баннера.

    AC3: cache key pattern banners:list:{type}:{role}
    """
    invalidate_banner_cache(instance.type)

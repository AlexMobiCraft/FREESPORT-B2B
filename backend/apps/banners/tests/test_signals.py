"""
Тесты кэш-инвалидации баннеров — Story 32.1

Покрытие:
- AC3: Saving/deleting banner invalidates cache banners:list:{type}:{role}
- 7-1: Инвалидация очищает ключи по всем ролям
"""

import pytest
from django.core.cache import cache

from apps.banners.factories import BannerFactory
from apps.banners.models import Banner
from apps.banners.services import _ALL_ROLE_KEYS


@pytest.mark.django_db
class TestBannerCacheInvalidation:
    """AC3: Cache invalidation on save/delete с учётом ролей."""

    def test_save_hero_banner_invalidates_hero_cache_all_roles(self):
        """Сохранение Hero баннера инвалидирует banners:list:hero:{role} для всех ролей."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:hero:{role}", "cached_data")
        BannerFactory(type=Banner.BannerType.HERO)
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:hero:{role}") is None

    def test_save_marketing_banner_invalidates_marketing_cache(self):
        """Сохранение Marketing баннера инвалидирует banners:list:marketing:{role}."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:marketing:{role}", "cached_data")
        BannerFactory(type=Banner.BannerType.MARKETING)
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:marketing:{role}") is None

    def test_save_hero_does_not_invalidate_marketing_cache(self):
        """Сохранение Hero баннера НЕ инвалидирует marketing кэш."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:marketing:{role}", "cached_data")
        BannerFactory(type=Banner.BannerType.HERO)
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:marketing:{role}") == "cached_data"

    def test_save_marketing_does_not_invalidate_hero_cache(self):
        """Сохранение Marketing баннера НЕ инвалидирует hero кэш."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:hero:{role}", "cached_data")
        BannerFactory(type=Banner.BannerType.MARKETING)
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:hero:{role}") == "cached_data"

    def test_delete_hero_banner_invalidates_hero_cache(self):
        """Удаление Hero баннера инвалидирует banners:list:hero:{role}."""
        banner = BannerFactory(type=Banner.BannerType.HERO)
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:hero:{role}", "cached_data")
        banner.delete()
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:hero:{role}") is None

    def test_delete_marketing_banner_invalidates_marketing_cache(self):
        """Удаление Marketing баннера инвалидирует banners:list:marketing:{role}."""
        banner = BannerFactory(type=Banner.BannerType.MARKETING)
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:marketing:{role}", "cached_data")
        banner.delete()
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:marketing:{role}") is None

    def test_update_banner_invalidates_cache(self):
        """Обновление баннера инвалидирует кэш его типа по всем ролям."""
        banner = BannerFactory(type=Banner.BannerType.HERO)
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:hero:{role}", "cached_data")
        banner.title = "Updated Title"
        banner.save()
        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:hero:{role}") is None

"""
Тесты ActiveBannersView — Story 32.1 Review Follow-ups

Покрытие:
- 5-2: Caching and filtering by type in ActiveBannersView
- 5-3: Query param ?type=hero|marketing
- 7-1: Cache key collision fix — роли изолированы в кеше
"""

import pytest
from typing import Any, cast
from django.contrib.auth import get_user_model
from django.core.cache import cache
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from apps.banners.factories import BannerFactory
from apps.banners.models import Banner

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestActiveBannersViewTypeFilter:
    """5-3: ?type=hero|marketing query param filtering."""

    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_list_without_type_returns_hero_only(self):
        """Без ?type возвращаются только hero баннеры (AC1, FR6)."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)
        response = self.client.get("/api/v1/banners/")
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["type"] == "hero"

    def test_filter_by_type_hero(self):
        """?type=hero возвращает только Hero баннеры."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)
        response = self.client.get("/api/v1/banners/", {"type": "hero"})
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["type"] == "hero"

    def test_filter_by_type_marketing(self):
        """?type=marketing возвращает только Marketing баннеры."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)
        response = self.client.get("/api/v1/banners/", {"type": "marketing"})
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["type"] == "marketing"

    def test_filter_by_invalid_type_defaults_to_hero(self):
        """?type=invalid — невалидный type → default hero (AC1)."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)
        response = self.client.get("/api/v1/banners/", {"type": "invalid"})
        assert response.status_code == 200
        assert len(response.data) == 1
        assert response.data[0]["type"] == "hero"

    def test_invalid_type_does_not_create_cache_key(self):
        """?type=invalid НЕ создаёт отдельный ключ кеша (cache flooding prevention)."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        self.client.get("/api/v1/banners/", {"type": "random_attack_value"})
        assert cache.get("banners:list:random_attack_value:guest") is None
        assert cache.get("banners:list:hero:guest") is not None


@pytest.mark.integration
@pytest.mark.django_db
class TestActiveBannersViewCaching:
    """5-2: Caching by type in ActiveBannersView."""

    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_response_is_cached_for_type(self):
        """Ответ кешируется под ключом banners:list:{type}:{role}."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        self.client.get("/api/v1/banners/", {"type": "hero"})
        cached = cache.get("banners:list:hero:guest")
        assert cached is not None

    def test_response_cached_for_hero_when_no_type(self):
        """Без ?type ответ кешируется под ключом banners:list:hero:{role} (AC1)."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        self.client.get("/api/v1/banners/")
        cached = cache.get("banners:list:hero:guest")
        assert cached is not None

    def test_cached_response_returned_on_second_call(self):
        """Второй вызов возвращает кешированные данные."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        response1 = self.client.get("/api/v1/banners/", {"type": "hero"})
        response2 = self.client.get("/api/v1/banners/", {"type": "hero"})
        assert response1.data == response2.data

    def test_different_types_cached_separately(self):
        """hero и marketing кешируются под разными ключами."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)
        self.client.get("/api/v1/banners/", {"type": "hero"})
        self.client.get("/api/v1/banners/", {"type": "marketing"})
        assert cache.get("banners:list:hero:guest") is not None
        assert cache.get("banners:list:marketing:guest") is not None

    def test_signal_invalidates_cache_after_save(self):
        """Сохранение нового баннера инвалидирует кеш (через signal)."""
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        self.client.get("/api/v1/banners/", {"type": "hero"})
        assert cache.get("banners:list:hero:guest") is not None
        # Создаём новый баннер — signal должен очистить кеш
        BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        assert cache.get("banners:list:hero:guest") is None

    def test_signal_invalidates_both_caches_on_type_change(self):
        """CR-8: Смена type у баннера инвалидирует кеш обоих типов (старый + новый)."""
        banner = BannerFactory(type=Banner.BannerType.HERO, show_to_guests=True)
        BannerFactory(type=Banner.BannerType.MARKETING, show_to_guests=True)

        # Заполняем кеш для обоих типов
        self.client.get("/api/v1/banners/", {"type": "hero"})
        self.client.get("/api/v1/banners/", {"type": "marketing"})
        assert cache.get("banners:list:hero:guest") is not None
        assert cache.get("banners:list:marketing:guest") is not None

        # Меняем type существующего баннера hero→marketing
        banner.type = Banner.BannerType.MARKETING
        banner.save()

        # Оба кеша должны быть инвалидированы
        assert cache.get("banners:list:hero:guest") is None
        assert cache.get("banners:list:marketing:guest") is None

    def test_signal_invalidates_role_specific_caches_on_type_change(self):
        """CR-9: Смена type инвалидирует кеш всех ролей, не только guest."""
        banner = BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=True,
            show_to_authenticated=True,
        )
        BannerFactory(
            type=Banner.BannerType.MARKETING,
            show_to_guests=True,
            show_to_authenticated=True,
        )

        # Заполняем кеш guest + retail для обоих типов
        self.client.get("/api/v1/banners/", {"type": "hero"})
        self.client.get("/api/v1/banners/", {"type": "marketing"})

        retail_user = User.objects.create_user(
            email="retail_cache_inv@test.local", password="testpass123", role="retail"
        )
        retail_client = APIClient()
        refresh = RefreshToken.for_user(retail_user)
        retail_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(cast(RefreshToken, refresh).access_token)}")
        retail_client.get("/api/v1/banners/", {"type": "hero"})
        retail_client.get("/api/v1/banners/", {"type": "marketing"})

        assert cache.get("banners:list:hero:guest") is not None
        assert cache.get("banners:list:hero:retail") is not None
        assert cache.get("banners:list:marketing:guest") is not None
        assert cache.get("banners:list:marketing:retail") is not None

        # Меняем type hero→marketing
        banner.type = Banner.BannerType.MARKETING
        banner.save()

        # Все кеши обоих типов по всем ролям должны быть инвалидированы
        assert cache.get("banners:list:hero:guest") is None
        assert cache.get("banners:list:hero:retail") is None
        assert cache.get("banners:list:marketing:guest") is None
        assert cache.get("banners:list:marketing:retail") is None


@pytest.mark.integration
@pytest.mark.django_db
class TestActiveBannersViewRoleIsolation:
    """7-1: Разные роли получают разные кеши — гость не видит оптовые баннеры."""

    def setup_method(self):
        cache.clear()

    def _make_authenticated_client(self, user):
        """Создаёт APIClient с JWT для данного пользователя."""
        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(cast(RefreshToken, refresh).access_token)}")
        return client

    def test_guest_does_not_see_wholesale_banners(self):
        """Гость не видит баннеры для оптовиков."""
        BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=False,
            show_to_wholesale=True,
        )
        guest_client = APIClient()
        response = guest_client.get("/api/v1/banners/")
        assert response.status_code == 200
        assert len(response.data) == 0

    def test_wholesale_user_sees_wholesale_banners(self):
        """Оптовик видит баннеры для оптовиков."""
        BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=False,
            show_to_wholesale=True,
        )
        wholesale_user = User.objects.create_user(
            email="wholesale@test.local", password="testpass123", role="wholesale_level1"
        )
        client = self._make_authenticated_client(wholesale_user)
        response = client.get("/api/v1/banners/")
        assert response.status_code == 200
        assert len(response.data) == 1

    def test_guest_cache_does_not_leak_to_wholesale(self):
        """Кеш гостя не утекает к оптовику (и наоборот)."""
        # Hero баннер только для гостей
        guest_banner = BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=True,
            show_to_wholesale=False,
            priority=10,
        )
        # Hero баннер только для оптовиков
        wholesale_banner = BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=False,
            show_to_wholesale=True,
            priority=5,
        )

        guest_client = APIClient()
        wholesale_user = User.objects.create_user(
            email="wholesale_leak@test.local", password="testpass123", role="wholesale_level1"
        )
        wholesale_client = self._make_authenticated_client(wholesale_user)

        # Гость запрашивает баннеры — кешируется под guest
        guest_response = guest_client.get("/api/v1/banners/")
        assert len(guest_response.data) == 1
        assert guest_response.data[0]["id"] == guest_banner.id

        # Оптовик запрашивает баннеры — свой кеш, не из guest
        wholesale_response = wholesale_client.get("/api/v1/banners/")
        assert len(wholesale_response.data) == 1
        assert wholesale_response.data[0]["id"] == wholesale_banner.id

    def test_different_roles_cached_independently(self):
        """Каждая роль получает свой ключ кеша."""
        BannerFactory(
            type=Banner.BannerType.HERO,
            show_to_guests=True,
            show_to_authenticated=True,
        )

        guest_client = APIClient()
        retail_user = User.objects.create_user(email="retail_cache@test.local", password="testpass123", role="retail")
        retail_client = self._make_authenticated_client(retail_user)

        guest_client.get("/api/v1/banners/")
        retail_client.get("/api/v1/banners/")

        assert cache.get("banners:list:hero:guest") is not None
        assert cache.get("banners:list:hero:retail") is not None


@pytest.mark.integration
@pytest.mark.django_db
class TestActiveBannersViewMarketingLimit:
    """AC2: ?type=marketing лимит 5 баннеров (FR12)."""

    def setup_method(self):
        self.client = APIClient()
        cache.clear()

    def test_marketing_returns_max_5_banners(self):
        """Создаём 6 marketing баннеров — API возвращает не более 5 (FR12)."""
        for i in range(6):
            BannerFactory(
                type=Banner.BannerType.MARKETING,
                show_to_guests=True,
                priority=i,
            )
        response = self.client.get("/api/v1/banners/", {"type": "marketing"})
        assert response.status_code == 200
        assert len(response.data) == 5

    def test_marketing_limit_configurable_via_settings(self):
        """MARKETING_BANNER_LIMIT из settings управляет лимитом (override_settings)."""
        from django.test import override_settings

        for i in range(6):
            BannerFactory(
                type=Banner.BannerType.MARKETING,
                show_to_guests=True,
                priority=i,
            )

        with override_settings(MARKETING_BANNER_LIMIT=3):
            cache.clear()
            response = self.client.get("/api/v1/banners/", {"type": "marketing"})
            assert response.status_code == 200
            assert len(response.data) == 3

    def test_hero_limited_to_10_by_default(self):
        """Hero баннеры ограничены лимитом 10 по умолчанию (Performance safety)."""
        for i in range(12):
            BannerFactory(
                type=Banner.BannerType.HERO,
                show_to_guests=True,
                priority=i,
            )
        response = self.client.get("/api/v1/banners/", {"type": "hero"})
        assert response.status_code == 200
        assert len(response.data) == 10

    def test_hero_limit_configurable_via_settings(self):
        """HERO_BANNER_LIMIT из settings управляет лимитом hero баннеров."""
        from django.test import override_settings

        for i in range(12):
            BannerFactory(
                type=Banner.BannerType.HERO,
                show_to_guests=True,
                priority=i,
            )

        with override_settings(HERO_BANNER_LIMIT=4):
            cache.clear()
            response = self.client.get("/api/v1/banners/", {"type": "hero"})
            assert response.status_code == 200
            assert len(response.data) == 4

    def test_marketing_fewer_than_limit_returns_all(self):
        """Если marketing баннеров меньше 5, возвращаются все."""
        for i in range(3):
            BannerFactory(
                type=Banner.BannerType.MARKETING,
                show_to_guests=True,
                priority=i,
            )
        response = self.client.get("/api/v1/banners/", {"type": "marketing"})
        assert response.status_code == 200
        assert len(response.data) == 3

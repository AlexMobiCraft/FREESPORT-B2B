"""
Тесты сервисного слоя баннеров — Story 32.1

Покрытие:
- 7-1: Cache key включает роль пользователя (предотвращение утечки)
- 7-2: Service layer functions (validate, build_cache_key, get_role_key, invalidate)
- 9-1: Dynamic TTL — compute_cache_ttl учитывает start_date/end_date
"""

from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.core.cache import cache
from django.db.models import Q
from django.utils import timezone

from apps.banners.factories import BannerFactory
from apps.banners.models import Banner
from apps.banners.services import (
    _ALL_ROLE_KEYS,
    BANNER_CACHE_TTL,
    CACHE_KEY_PATTERN,
    MIN_CACHE_TTL,
    _get_role_filter,
    build_cache_key,
    cache_banner_response,
    compute_cache_ttl,
    get_cached_banners,
    get_role_key,
    invalidate_banner_cache,
    validate_banner_type,
)
from apps.users.models import User


@pytest.mark.unit
class TestGetRoleKey:
    """7-1: get_role_key возвращает корректный ключ роли."""

    def test_none_user_returns_guest(self):
        assert get_role_key(None) == "guest"

    def test_anonymous_user_returns_guest(self):
        user = MagicMock()
        user.is_authenticated = False
        assert get_role_key(user) == "guest"

    def test_retail_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.role = "retail"
        assert get_role_key(user) == "retail"

    def test_wholesale_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.role = "wholesale_level1"
        assert get_role_key(user) == "wholesale_level1"

    def test_trainer_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.role = "trainer"
        assert get_role_key(user) == "trainer"

    def test_federation_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.role = "federation_rep"
        assert get_role_key(user) == "federation_rep"

    def test_admin_user(self):
        user = MagicMock()
        user.is_authenticated = True
        user.role = "admin"
        assert get_role_key(user) == "admin"

    def test_user_without_role_attr_defaults_to_retail(self):
        user = MagicMock(spec=["is_authenticated"])
        user.is_authenticated = True
        assert get_role_key(user) == "retail"


@pytest.mark.unit
class TestValidateBannerType:
    """7-2: validate_banner_type корректно фильтрует типы. Default='hero' (AC1)."""

    def test_valid_hero(self):
        assert validate_banner_type("hero") == "hero"

    def test_valid_marketing(self):
        assert validate_banner_type("marketing") == "marketing"

    def test_invalid_type_returns_hero(self):
        assert validate_banner_type("invalid") == "hero"

    def test_none_returns_hero(self):
        assert validate_banner_type(None) == "hero"

    def test_empty_string_returns_hero(self):
        assert validate_banner_type("") == "hero"


@pytest.mark.unit
class TestBuildCacheKey:
    """7-1: Ключ кеша включает тип и роль."""

    def test_hero_guest(self):
        assert build_cache_key("hero", "guest") == "banners:list:hero:guest"

    def test_marketing_wholesale(self):
        assert build_cache_key("marketing", "wholesale_level1") == "banners:list:marketing:wholesale_level1"

    def test_hero_retail(self):
        assert build_cache_key("hero", "retail") == "banners:list:hero:retail"

    def test_marketing_guest(self):
        assert build_cache_key("marketing", "guest") == "banners:list:marketing:guest"

    def test_different_roles_produce_different_keys(self):
        """Разные роли дают разные ключи — критично для изоляции."""
        key_guest = build_cache_key("hero", "guest")
        key_wholesale = build_cache_key("hero", "wholesale_level1")
        assert key_guest != key_wholesale


@pytest.mark.integration
class TestCacheFunctions:
    """7-2: Cache get/set через сервисные функции."""

    def setup_method(self):
        cache.clear()

    def test_get_cached_banners_miss(self):
        assert get_cached_banners("banners:list:hero:guest") is None

    def test_cache_and_retrieve(self):
        data = [{"id": 1, "title": "Test"}]
        cache_banner_response("banners:list:hero:guest", data)
        assert get_cached_banners("banners:list:hero:guest") == data

    def test_cache_banner_response_with_custom_ttl(self):
        """cache_banner_response принимает кастомный TTL."""
        data = [{"id": 1}]
        cache_banner_response("banners:list:hero:guest", data, ttl=60)
        assert get_cached_banners("banners:list:hero:guest") == data

    def test_cache_banner_response_none_ttl_uses_default(self):
        """ttl=None использует BANNER_CACHE_TTL по умолчанию."""
        data = [{"id": 1}]
        with patch("apps.banners.services.cache") as mock_cache:
            cache_banner_response("test_key", data, ttl=None)
            mock_cache.set.assert_called_once_with("test_key", data, BANNER_CACHE_TTL)


@pytest.mark.integration
@pytest.mark.django_db
class TestInvalidateBannerCache:
    """7-1/7-2: Инвалидация очищает ключи по всем ролям."""

    def setup_method(self):
        cache.clear()

    def test_invalidate_clears_typed_keys_for_all_roles(self):
        """Инвалидация hero очищает banners:list:hero:{role} для всех ролей."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:hero:{role}", "data")

        invalidate_banner_cache("hero")

        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:hero:{role}") is None

    def test_invalidate_hero_does_not_clear_marketing(self):
        """Инвалидация hero НЕ затрагивает marketing ключи."""
        for role in _ALL_ROLE_KEYS:
            cache.set(f"banners:list:marketing:{role}", "data")

        invalidate_banner_cache("hero")

        for role in _ALL_ROLE_KEYS:
            assert cache.get(f"banners:list:marketing:{role}") == "data"


@pytest.mark.unit
class TestAllRoleKeysDerivedFromUserModel:
    """8-1: _ALL_ROLE_KEYS импортируется из User.ROLE_CHOICES, не хардкодится."""

    def test_all_role_choices_present(self):
        """Каждая роль из User.ROLE_CHOICES присутствует в _ALL_ROLE_KEYS."""
        for role_value, _ in User.ROLE_CHOICES:
            assert role_value in _ALL_ROLE_KEYS, f"Role '{role_value}' missing from _ALL_ROLE_KEYS"

    def test_guest_role_present(self):
        """'guest' присутствует в _ALL_ROLE_KEYS (не входит в ROLE_CHOICES)."""
        assert "guest" in _ALL_ROLE_KEYS

    def test_no_extra_roles(self):
        """_ALL_ROLE_KEYS содержит ровно ROLE_CHOICES + guest, без лишних."""
        expected = {role for role, _ in User.ROLE_CHOICES} | {"guest"}
        assert set(_ALL_ROLE_KEYS) == expected

    def test_stays_in_sync_with_user_model(self):
        """При добавлении роли в User.ROLE_CHOICES она автоматически появляется в _ALL_ROLE_KEYS."""
        role_choice_values = {role for role, _ in User.ROLE_CHOICES}
        all_role_set = set(_ALL_ROLE_KEYS) - {"guest"}
        assert all_role_set == role_choice_values


@pytest.mark.unit
class TestCacheKeyPattern:
    """8-2: CACHE_KEY_PATTERN — константа для формирования ключей кеша."""

    def test_pattern_is_string(self):
        assert isinstance(CACHE_KEY_PATTERN, str)

    def test_pattern_contains_type_placeholder(self):
        assert "{type}" in CACHE_KEY_PATTERN

    def test_pattern_contains_role_placeholder(self):
        assert "{role}" in CACHE_KEY_PATTERN

    def test_build_cache_key_uses_pattern(self):
        """build_cache_key формирует ключ по CACHE_KEY_PATTERN."""
        key = build_cache_key("hero", "guest")
        expected = CACHE_KEY_PATTERN.format(type="hero", role="guest")
        assert key == expected

    def test_build_cache_key_marketing_type(self):
        """build_cache_key формирует ключ для marketing."""
        key = build_cache_key("marketing", "retail")
        expected = CACHE_KEY_PATTERN.format(type="marketing", role="retail")
        assert key == expected


@pytest.mark.integration
@pytest.mark.django_db
class TestComputeCacheTTL:
    """9-1: Dynamic TTL учитывает ближайшие start_date/end_date баннеров."""

    def test_no_banners_returns_default_ttl(self):
        """Без баннеров возвращается BANNER_CACHE_TTL."""
        assert compute_cache_ttl() == BANNER_CACHE_TTL

    def test_no_temporal_boundaries_returns_default_ttl(self):
        """Баннеры без start_date/end_date — TTL = BANNER_CACHE_TTL."""
        BannerFactory(
            start_date=None,
            end_date=None,
            show_to_guests=True,
        )
        assert compute_cache_ttl() == BANNER_CACHE_TTL

    def test_end_date_sooner_than_default_ttl(self):
        """Баннер с end_date через 5 мин — TTL = 300 секунд."""
        now = timezone.now()
        BannerFactory(
            end_date=now + timedelta(minutes=5),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl()
        # TTL должен быть ~300с (±2с на выполнение)
        assert MIN_CACHE_TTL <= ttl <= 302

    def test_start_date_sooner_than_default_ttl(self):
        """Будущий баннер с start_date через 3 мин — TTL = ~180 секунд."""
        now = timezone.now()
        BannerFactory(
            start_date=now + timedelta(minutes=3),
            end_date=now + timedelta(days=7),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl()
        assert MIN_CACHE_TTL <= ttl <= 182

    def test_end_date_far_away_returns_default_ttl(self):
        """Баннер с end_date через 1 час — TTL = BANNER_CACHE_TTL (15 мин)."""
        now = timezone.now()
        BannerFactory(
            end_date=now + timedelta(hours=1),
            show_to_guests=True,
        )
        assert compute_cache_ttl() == BANNER_CACHE_TTL

    def test_minimum_ttl_floor(self):
        """TTL не опускается ниже MIN_CACHE_TTL."""
        now = timezone.now()
        BannerFactory(
            end_date=now + timedelta(seconds=2),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl()
        assert ttl >= MIN_CACHE_TTL

    def test_type_filter_hero(self):
        """compute_cache_ttl(hero) учитывает только hero баннеры."""
        now = timezone.now()
        # Hero с close end_date
        BannerFactory(
            type=Banner.BannerType.HERO,
            end_date=now + timedelta(minutes=2),
            show_to_guests=True,
        )
        # Marketing с далёким end_date
        BannerFactory(
            type=Banner.BannerType.MARKETING,
            end_date=now + timedelta(hours=2),
            show_to_guests=True,
        )
        ttl_hero = compute_cache_ttl("hero")
        ttl_marketing = compute_cache_ttl("marketing")
        assert ttl_hero < BANNER_CACHE_TTL  # Hero: ~120с
        assert ttl_marketing == BANNER_CACHE_TTL  # Marketing: 2 часа > 15 мин

    def test_default_type_is_hero(self):
        """compute_cache_ttl() без аргумента использует hero."""
        now = timezone.now()
        BannerFactory(
            type=Banner.BannerType.HERO,
            end_date=now + timedelta(minutes=2),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl()
        assert ttl < BANNER_CACHE_TTL

    def test_nearest_boundary_wins(self):
        """Из end_date и start_date выбирается ближайший."""
        now = timezone.now()
        # Активный с end_date через 10 мин
        BannerFactory(
            end_date=now + timedelta(minutes=10),
            show_to_guests=True,
        )
        # Будущий с start_date через 3 мин
        BannerFactory(
            start_date=now + timedelta(minutes=3),
            end_date=now + timedelta(days=7),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl()
        # start_date через 3 мин ближе, чем end_date через 10 мин
        assert ttl <= 182

    def test_role_key_guest_filters_by_show_to_guests(self):
        """TTL для guest учитывает только баннеры с show_to_guests=True."""
        now = timezone.now()
        # Баннер виден только retail (не guest) — с close end_date
        BannerFactory(
            end_date=now + timedelta(minutes=2),
            show_to_guests=False,
            show_to_authenticated=True,
        )
        # Guest не видит этот баннер — TTL остаётся default
        ttl = compute_cache_ttl("hero", role_key="guest")
        assert ttl == BANNER_CACHE_TTL

    def test_role_key_retail_sees_authenticated_banners(self):
        """TTL для retail учитывает баннеры с show_to_authenticated=True."""
        now = timezone.now()
        BannerFactory(
            end_date=now + timedelta(minutes=2),
            show_to_guests=False,
            show_to_authenticated=True,
        )
        ttl = compute_cache_ttl("hero", role_key="retail")
        assert ttl < BANNER_CACHE_TTL  # ~120с

    def test_role_key_trainer_sees_authenticated_and_trainer_banners(self):
        """TTL для trainer учитывает show_to_authenticated OR show_to_trainers."""
        now = timezone.now()
        # Баннер только для authenticated (не trainers-specific)
        BannerFactory(
            end_date=now + timedelta(minutes=2),
            show_to_guests=False,
            show_to_authenticated=True,
            show_to_trainers=False,
        )
        ttl = compute_cache_ttl("hero", role_key="trainer")
        # Trainer видит show_to_authenticated баннеры тоже
        assert ttl < BANNER_CACHE_TTL

    def test_role_key_trainer_sees_trainer_specific_banners(self):
        """TTL для trainer учитывает show_to_trainers=True баннеры."""
        now = timezone.now()
        BannerFactory(
            end_date=now + timedelta(minutes=2),
            show_to_guests=False,
            show_to_authenticated=False,
            show_to_trainers=True,
        )
        ttl = compute_cache_ttl("hero", role_key="trainer")
        assert ttl < BANNER_CACHE_TTL

    def test_future_start_date_affects_ttl(self):
        """Будущий баннер (start_date > now) корректно уменьшает TTL."""
        now = timezone.now()
        BannerFactory(
            start_date=now + timedelta(minutes=4),
            end_date=now + timedelta(days=7),
            show_to_guests=True,
        )
        ttl = compute_cache_ttl("hero", role_key="guest")
        # Будущий баннер через 4 мин — TTL ~240с
        assert MIN_CACHE_TTL <= ttl <= 242


@pytest.mark.unit
class TestGetRoleFilterReturnsQ:
    """CR-10: _get_role_filter возвращает Q-объекты, синхронизированные с Banner.get_for_user."""

    def test_guest_returns_show_to_guests(self):
        q = _get_role_filter("guest")
        assert isinstance(q, Q)

    def test_retail_returns_show_to_authenticated(self):
        q = _get_role_filter("retail")
        assert isinstance(q, Q)

    def test_trainer_includes_authenticated_base(self):
        q = _get_role_filter("trainer")
        assert isinstance(q, Q)
        # Q object should be an OR of show_to_authenticated and show_to_trainers
        q_str = str(q)
        assert "show_to_authenticated" in q_str
        assert "show_to_trainers" in q_str

    def test_wholesale_includes_authenticated_base(self):
        q = _get_role_filter("wholesale_level1")
        q_str = str(q)
        assert "show_to_authenticated" in q_str
        assert "show_to_wholesale" in q_str

    def test_federation_includes_authenticated_base(self):
        q = _get_role_filter("federation_rep")
        q_str = str(q)
        assert "show_to_authenticated" in q_str
        assert "show_to_federation" in q_str

    def test_unknown_role_falls_back_to_guest(self):
        q = _get_role_filter("unknown_role")
        assert isinstance(q, Q)
        assert "show_to_guests" in str(q)

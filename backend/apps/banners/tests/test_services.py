"""
Тесты сервисного слоя баннеров — Story 32.1

Покрытие:
- 7-1: Cache key включает роль пользователя (предотвращение утечки)
- 7-2: Service layer functions (validate, build_cache_key, get_role_key, invalidate)
- 9-1: Dynamic TTL — compute_cache_ttl учитывает start_date/end_date
- Снимок баннера в строках статистики: sync_daily_stat_snapshots, сигнал, миграция 0010
- Миграция 0011: удаление статистики баннеров шапки (hero)
"""

import importlib
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.apps import apps as django_apps
from django.core.cache import cache
from django.db import connection
from django.db.models import Q
from django.db.models.signals import post_save
from django.utils import timezone

from apps.banners.factories import AdvertisementBannerFactory, BannerFactory
from apps.banners.models import Banner, BannerDailyStat
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
    sync_daily_stat_snapshots,
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


@pytest.mark.unit
class TestWholesaleLevel4RoleFilter:
    """
    Стори 39.3, AC8: роль уровня 4 относится к оптовым.

    Без правки роль проваливалась в else-ветку `_get_role_filter` и получала
    гостевой фильтр — авторизованный оптовик видел баннеры для анонимов.
    """

    def test_level4_gets_wholesale_filter(self):
        """Фильтр — базовый authenticated ИЛИ оптовый флаг, как у уровней 1-3"""
        q = _get_role_filter("wholesale_level4")
        q_str = str(q)
        assert "show_to_authenticated" in q_str
        assert "show_to_wholesale" in q_str

    def test_level4_is_not_treated_as_guest(self):
        """Гостевой fallback для этой роли не применяется"""
        assert "show_to_guests" not in str(_get_role_filter("wholesale_level4"))

    def test_level4_filter_matches_level3(self):
        """Фильтр совпадает с фильтром третьего уровня — уровни равноправны"""
        assert _get_role_filter("wholesale_level4") == _get_role_filter("wholesale_level3")


@pytest.mark.unit
class TestVipAndSpecialPriceRoleFilter:
    """
    Роли «VIP» и «Спец цена» — оптовики для баннеров (`show_to_wholesale`).

    Имя роли не начинается с «wholesale», а неизвестная роль падает на гостевой
    фильтр: без правки авторизованный VIP видел бы баннеры для анонимов.
    """

    @pytest.mark.parametrize("role", ["vip", "special_price", "dealer"])
    def test_role_gets_wholesale_filter(self, role):
        q_str = str(_get_role_filter(role))
        assert "show_to_authenticated" in q_str
        assert "show_to_wholesale" in q_str

    @pytest.mark.parametrize("role", ["vip", "special_price", "dealer"])
    def test_role_is_not_treated_as_guest(self, role):
        assert "show_to_guests" not in str(_get_role_filter(role))

    @pytest.mark.parametrize("role", ["vip", "special_price", "dealer"])
    def test_role_filter_matches_wholesale(self, role):
        assert _get_role_filter(role) == _get_role_filter("wholesale_level1")

    @pytest.mark.django_db
    @pytest.mark.parametrize("role", ["vip", "special_price", "dealer"])
    def test_get_for_user_shows_wholesale_banner(self, role):
        """Модельный путь `Banner.get_for_user` согласован с сервисным фильтром."""
        user = User.objects.create_user(email=f"{role}-banner@example.com", password="testpass123", role=role)
        wholesale = BannerFactory(show_to_guests=False, show_to_authenticated=False, show_to_wholesale=True)
        guests_only = BannerFactory(show_to_guests=True, show_to_authenticated=False, show_to_wholesale=False)

        banner_ids = set(Banner.get_for_user(user).values_list("id", flat=True))

        assert wholesale.id in banner_ids
        assert guests_only.id not in banner_ids


# ---------------------------------------------------------------------------
# Снимок баннера в строках дневной статистики
# ---------------------------------------------------------------------------

_snapshot_migration = importlib.import_module("apps.banners.migrations.0010_sync_banner_daily_stat_snapshots")
_hero_stats_migration = importlib.import_module("apps.banners.migrations.0011_delete_hero_banner_daily_stats")


def _stat(banner: Banner | None, **fields: Any) -> BannerDailyStat:
    """Строка статистики со снимком баннера; без баннера — как у удалённого."""
    values: dict[str, Any] = {"date": date(2026, 11, 3), "views": 1, "clicks": 0}
    if banner is not None:
        values.update(
            banner=banner,
            banner_ref_id=banner.pk,
            banner_title=banner.title,
            erid=banner.erid if banner.is_advertisement else "",
            advertiser_name=banner.advertiser_name if banner.is_advertisement else "",
            advertiser_inn=banner.advertiser_inn if banner.is_advertisement else "",
        )
    values.update(fields)
    return BannerDailyStat.objects.create(**values)


def _snapshots(banner_ref_id: int) -> set[tuple[str, str, str, str]]:
    rows = BannerDailyStat.objects.filter(banner_ref_id=banner_ref_id)
    return set(rows.values_list("banner_title", "erid", "advertiser_name", "advertiser_inn"))


@pytest.mark.django_db
class TestSyncDailyStatSnapshots:
    def test_rename_rewrites_all_rows_with_any_erid(self):
        banner = AdvertisementBannerFactory(title="Старое", erid="2VfnxNEW")
        for day in (3, 4, 5):
            _stat(banner, date=date(2026, 11, day))
            _stat(banner, date=date(2026, 11, day), erid="2VfnxOLD")

        banner.title = "Новое"
        banner.save()

        titles = list(BannerDailyStat.objects.filter(banner=banner).values_list("banner_title", flat=True))
        assert titles == ["Новое"] * 6

    def test_advertiser_change_rewrites_ad_rows_only(self):
        banner = AdvertisementBannerFactory(erid="2VfnxAD")
        ad_row = _stat(banner, date=date(2026, 11, 3))
        # Рекламная строка без ERID: ERID у рекламы необязателен.
        ad_without_erid = _stat(banner, date=date(2026, 11, 4), erid="")
        # Строка тех дней, когда баннер не был рекламой.
        plain_row = _stat(banner, date=date(2026, 11, 5), erid="", advertiser_name="", advertiser_inn="")

        banner.advertiser_name = "ООО Новый"
        banner.advertiser_inn = "500100732259"
        banner.save()

        for row in (ad_row, ad_without_erid):
            row.refresh_from_db()
            assert (row.advertiser_name, row.advertiser_inn) == ("ООО Новый", "500100732259")
        plain_row.refresh_from_db()
        assert (plain_row.advertiser_name, plain_row.advertiser_inn, plain_row.erid) == ("", "", "")

    def test_unmarked_banner_keeps_requisites_and_erid(self):
        banner = AdvertisementBannerFactory(title="Старое", erid="2VfnxAD")
        _stat(banner)

        banner.is_advertisement = False
        banner.title = "Новое"
        banner.advertiser_name = "ООО Другой"
        banner.save()

        assert _snapshots(banner.pk) == {("Новое", "2VfnxAD", 'ООО "Прайм Спорт Рус"', "7718933790")}

    def test_deleted_banner_rows_untouched(self):
        banner = AdvertisementBannerFactory(title="Живой", erid="2VfnxAD")
        live_row = _stat(banner, banner_title="Старое")
        # Сирота с тем же banner_ref_id: фильтр — по banner_id, а не по banner_ref_id.
        orphan = _stat(None, banner_ref_id=banner.pk, date=date(2026, 11, 4), banner_title="Удалённый")

        sync_daily_stat_snapshots(banner)

        live_row.refresh_from_db()
        orphan.refresh_from_db()
        assert live_row.banner_title == "Живой"
        assert (orphan.banner_id, orphan.banner_title) == (None, "Удалённый")

    def test_updates_only_differing_rows(self):
        banner = AdvertisementBannerFactory(title="Название", erid="2VfnxAD")
        _stat(banner, date=date(2026, 11, 3))
        _stat(banner, date=date(2026, 11, 4), banner_title="Старое")
        _stat(banner, date=date(2026, 11, 5), advertiser_inn="0123456789")

        assert sync_daily_stat_snapshots(banner) == 2
        assert sync_daily_stat_snapshots(banner) == 0

    def test_raw_and_created_saves_skip_sync(self):
        banner = AdvertisementBannerFactory(title="Старое")
        row = _stat(banner)
        banner.title = "Новое"

        post_save.send(sender=Banner, instance=banner, created=False, raw=True)
        post_save.send(sender=Banner, instance=banner, created=True, raw=False)

        row.refresh_from_db()
        assert row.banner_title == "Старое"

    def test_migration_aligns_accumulated_rows(self):
        banner = AdvertisementBannerFactory(title="Текущее", erid="2VfnxAD")
        _stat(banner, date=date(2026, 11, 3), banner_title="Первое", advertiser_name="ООО Старое")
        _stat(banner, date=date(2026, 11, 4), erid="2VfnxOLD", banner_title="Второе")
        plain = BannerFactory(title="Обычный")
        plain_row = _stat(plain, banner_title="Прежний")
        orphan = _stat(None, banner_ref_id=10**9, banner_title="Удалённый", erid="2VfnxGONE")

        _snapshot_migration.sync_banner_daily_stat_snapshots(django_apps, SimpleNamespace(connection=connection))

        assert {row[0] for row in _snapshots(banner.pk)} == {"Текущее"}
        assert {row[2] for row in _snapshots(banner.pk)} == {'ООО "Прайм Спорт Рус"'}
        plain_row.refresh_from_db()
        orphan.refresh_from_db()
        assert (plain_row.banner_title, plain_row.advertiser_name) == ("Обычный", "")
        assert orphan.banner_title == "Удалённый"


@pytest.mark.django_db
class TestDeleteHeroBannerDailyStatsMigration:
    def test_deletes_hero_rows_and_keeps_marketing_and_orphan(self):
        hero = BannerFactory(type=Banner.BannerType.HERO)
        _stat(hero, date=date(2026, 11, 19), views=12, clicks=1)
        _stat(hero, date=date(2026, 11, 20), views=8, clicks=1)
        marketing = AdvertisementBannerFactory(erid="2VfnxAD")
        marketing_row = _stat(marketing, views=7, clicks=2)
        orphan = _stat(None, banner_ref_id=10**9, banner_title="Удалённый", views=3)
        # Баннер был рекламным маркетинговым, потом его перевели в шапку: строки рекламы для ОРД остаются.
        former_ad = BannerFactory(type=Banner.BannerType.HERO)
        former_ad_row = _stat(
            former_ad,
            erid="2VfnxFORMER",
            advertiser_name='ООО "Прайм Спорт Рус"',
            advertiser_inn="7718933790",
            views=5,
            clicks=1,
        )
        _stat(former_ad, date=date(2026, 11, 20), views=4)

        _hero_stats_migration.delete_hero_banner_daily_stats(django_apps, SimpleNamespace(connection=connection))

        assert not BannerDailyStat.objects.filter(banner_ref_id=hero.pk).exists()
        assert set(BannerDailyStat.objects.values_list("pk", "views", "clicks")) == {
            (marketing_row.pk, 7, 2),
            (orphan.pk, 3, 0),
            (former_ad_row.pk, 5, 1),
        }

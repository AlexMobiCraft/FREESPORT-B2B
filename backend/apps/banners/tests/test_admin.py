"""
Тесты Admin-интерфейса Banner — Story 32.1

Покрытие:
- AC2: BannerAdmin list_filter по type
- AC2: Image обязательна для Marketing type
- AC2: target_url (cta_link) доступен в форме
"""

import csv
import importlib
import io
from datetime import date, timedelta
from types import SimpleNamespace
from typing import Any, cast

import pytest
from django.apps import apps as django_apps
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.test import Client, RequestFactory
from django.utils import timezone

from apps.banners.admin import (
    BannerAdmin,
    BannerDailyStatAdmin,
    StatPeriod,
    day_options,
    month_options,
    ord_csv_response,
    parse_period,
    year_options,
)
from apps.banners.factories import (
    AdvertisementBannerFactory,
    BannerFactory,
    MarketingBannerFactory,
    generate_test_image,
)
from apps.banners.models import Banner, BannerDailyStat
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import marketing_site
from tests.conftest import get_unique_suffix

_roles_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")
_stat_migration = importlib.import_module("apps.banners.migrations.0009_banner_daily_stat_permissions")

STATS_URL = "/marketing/banners/bannerdailystat/"
EXPORT_URL = f"{STATS_URL}export-ord/"
BANNERS_URL = "/marketing/banners/banner/"


@pytest.mark.django_db
class TestBannerAdminListFilter:
    """AC2: Sidebar filter by 'Type' is available."""

    def test_type_in_list_filter(self):
        """type присутствует в list_filter."""
        admin = BannerAdmin(Banner, AdminSite())
        assert "type" in admin.list_filter

    def test_type_in_list_display(self):
        """type отображается в list_display."""
        admin = BannerAdmin(Banner, AdminSite())
        assert "type" in admin.list_display


@pytest.mark.django_db
class TestBannerAdminFormValidation:
    """AC2: Image mandatory for Marketing type."""

    def test_marketing_banner_without_image_raises_error(self):
        """Создание Marketing баннера без image должно вызвать ValidationError."""
        banner = Banner(
            title="Test Marketing",
            subtitle="Test",
            cta_link="/test",
            type=Banner.BannerType.MARKETING,
            # image не указан
        )
        with pytest.raises(ValidationError) as exc_info:
            banner.full_clean()
        assert "image" in exc_info.value.message_dict

    def test_marketing_banner_with_image_passes(self):
        """Marketing баннер с image проходит валидацию."""
        banner = BannerFactory.build(type=Banner.BannerType.MARKETING)
        # build() не сохраняет, но image генерируется через factory
        # full_clean не должен бросить исключение
        banner.full_clean()

    def test_hero_banner_without_image_is_valid(self):
        """Hero баннер без image теперь валиден (image blank=True)."""
        banner = Banner(
            title="Test Hero",
            subtitle="Test",
            cta_link="/test",
            type=Banner.BannerType.HERO,
        )
        # full_clean не должен бросать ошибку, т.к. image теперь blank=True
        banner.full_clean()


@pytest.mark.django_db
class TestBannerAdminFieldsets:
    """AC2: target_url (cta_link) доступен для Marketing баннеров."""

    def test_cta_link_in_fieldsets(self):
        """cta_link (target_url) присутствует в fieldsets."""
        admin = BannerAdmin(Banner, AdminSite())
        all_fields: list[str] = []
        for _, options in admin.fieldsets:
            all_fields.extend(cast(Any, options["fields"]))
        assert "cta_link" in all_fields

    def test_type_in_fieldsets(self):
        """type присутствует в fieldsets."""
        admin = BannerAdmin(Banner, AdminSite())
        all_fields: list[str] = []
        for _, options in admin.fieldsets:
            all_fields.extend(cast(Any, options["fields"]))
        assert "type" in all_fields


@pytest.mark.unit
class TestBannerAdminAdvertisementFields:
    """Fieldset «Маркировка рекламы» и видимость флага в списке."""

    def _all_fields(self) -> list[str]:
        admin = BannerAdmin(Banner, AdminSite())
        fields: list[str] = []
        for _, options in admin.fieldsets:
            fields.extend(cast(Any, options["fields"]))
        return fields

    @pytest.mark.parametrize("field", ["is_advertisement", "advertiser_name", "advertiser_inn", "erid"])
    def test_advertisement_field_in_fieldsets(self, field):
        """Все четыре поля маркировки доступны в форме админки."""
        assert field in self._all_fields()

    def test_advertisement_fieldset_present(self):
        """Отдельная секция «Маркировка рекламы» существует."""
        admin = BannerAdmin(Banner, AdminSite())
        titles = [title for title, _ in admin.fieldsets]
        assert "Маркировка рекламы" in titles

    def test_is_advertisement_visible_in_list(self):
        """Флаг с юридическими последствиями виден в списке, а не только в фильтре."""
        admin = BannerAdmin(Banner, AdminSite())
        assert "is_advertisement" in admin.list_display
        assert "is_advertisement" in admin.list_filter

    def test_advertiser_name_searchable(self):
        """По рекламодателю можно искать — иначе не найти его баннеры при проверке."""
        admin = BannerAdmin(Banner, AdminSite())
        assert "advertiser_name" in admin.search_fields


# ---------------------------------------------------------------------------
# Статистика показов и кликов для ОРД
# ---------------------------------------------------------------------------


def make_stat(banner: Banner | None = None, **fields: Any) -> BannerDailyStat:
    """Строка статистики; без баннера — как у удалённого (banner=NULL, снимок остаётся)."""
    defaults: dict[str, Any] = {
        "date": timezone.localdate(),
        "views": 0,
        "clicks": 0,
    }
    if banner is not None:
        defaults.update(
            banner=banner,
            banner_ref_id=banner.pk,
            banner_title=banner.title,
            erid=banner.erid if banner.is_advertisement else "",
            advertiser_name=banner.advertiser_name if banner.is_advertisement else "",
            advertiser_inn=banner.advertiser_inn if banner.is_advertisement else "",
        )
    defaults.update(fields)
    return BannerDailyStat.objects.create(**defaults)


def stat_admin() -> BannerDailyStatAdmin:
    return BannerDailyStatAdmin(BannerDailyStat, AdminSite())


def export_rows(queryset: Any) -> list[list[str]]:
    response = ord_csv_response(queryset)
    content = response.content.decode("utf-8")
    assert content.startswith("﻿")
    return list(csv.reader(io.StringIO(content[1:]), delimiter=";"))


@pytest.mark.django_db
class TestBannerAdminStatColumns:
    def _row(self, banner: Banner) -> Banner:
        request = RequestFactory().get("/")
        return BannerAdmin(Banner, AdminSite()).get_queryset(request).get(pk=banner.pk)

    def test_columns_in_list_display(self):
        admin = BannerAdmin(Banner, AdminSite())
        assert {"views_30d", "clicks_30d", "ctr_30d"} <= set(admin.list_display)

    def test_sums_last_thirty_days_only(self):
        banner = AdvertisementBannerFactory()
        today = timezone.localdate()
        make_stat(banner, date=today, views=10, clicks=1)
        make_stat(banner, date=today - timedelta(days=29), views=5, clicks=2)
        make_stat(banner, date=today - timedelta(days=30), views=1000, clicks=500)
        # Смена ERID — вторая строка того же дня, тоже в сумме.
        make_stat(banner, date=today, erid="2VfnxOTHER", views=5, clicks=0)

        row = self._row(banner)
        admin = BannerAdmin(Banner, AdminSite())

        assert (admin.views_30d(row), admin.clicks_30d(row)) == (20, 3)
        assert admin.ctr_30d(row) == "15,00 %"

    def test_ctr_without_views_is_dash(self):
        banner = MarketingBannerFactory()
        make_stat(banner, views=0, clicks=2)
        admin = BannerAdmin(Banner, AdminSite())

        row = self._row(banner)

        assert (admin.views_30d(row), admin.clicks_30d(row), admin.ctr_30d(row)) == (0, 2, "—")

    def test_banner_without_stats_has_zeros(self):
        banner = MarketingBannerFactory()
        admin = BannerAdmin(Banner, AdminSite())

        row = self._row(banner)

        assert (admin.views_30d(row), admin.clicks_30d(row), admin.ctr_30d(row)) == (0, 0, "—")

    def test_hero_banner_columns_are_dashes(self):
        # Статистика шапки не ведётся; строки времён, когда баннер был маркетинговым, не показываются.
        banner = BannerFactory(type=Banner.BannerType.HERO)
        make_stat(banner, views=10, clicks=1)
        admin = BannerAdmin(Banner, AdminSite())

        row = self._row(banner)

        assert (admin.views_30d(row), admin.clicks_30d(row), admin.ctr_30d(row)) == ("—", "—", "—")

    def test_list_has_one_row_per_banner(self):
        banner = MarketingBannerFactory()
        for days in range(5):
            make_stat(banner, date=timezone.localdate() - timedelta(days=days), views=1)

        queryset = BannerAdmin(Banner, AdminSite()).get_queryset(RequestFactory().get("/"))

        assert queryset.filter(pk=banner.pk).count() == 1


@pytest.mark.django_db
class TestBannerDailyStatAdminReadOnly:
    def test_no_add_change_delete(self):
        admin = stat_admin()
        request = RequestFactory().get("/")
        stat = make_stat(BannerFactory(), views=1)

        assert admin.has_add_permission(request) is False
        assert admin.has_change_permission(request, stat) is False
        assert admin.has_delete_permission(request, stat) is False

    def test_no_changelist_filters_or_actions(self):
        # Список Django заменён сводкой: фильтры и действия ему больше не нужны.
        admin = stat_admin()

        assert admin.date_hierarchy is None
        assert not admin.list_filter
        assert not admin.search_fields


@pytest.mark.django_db
class TestOrdCsvExport:
    def test_header_bom_and_delimiter(self):
        rows = export_rows(BannerDailyStat.objects.none())

        assert rows == [
            [
                "ERID",
                "Рекламодатель",
                "ИНН рекламодателя",
                "Баннер",
                "Начало периода",
                "Конец периода",
                "Показы",
                "Клики",
            ]
        ]

    def test_only_rows_with_erid(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        plain = BannerFactory(type=Banner.BannerType.HERO)
        make_stat(ad, date=date(2026, 11, 3), views=7, clicks=1)
        make_stat(plain, date=date(2026, 11, 3), views=100, clicks=10)

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert len(rows) == 1
        assert rows[0][0] == '="2VfnxAD"'

    def test_one_row_per_erid_and_banner_within_month(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD", title="Баннер А", advertiser_inn="7718933790")
        make_stat(ad, date=date(2026, 11, 2), views=0, clicks=1)
        make_stat(ad, date=date(2026, 11, 3), views=10, clicks=2)
        make_stat(ad, date=date(2026, 11, 20), views=5, clicks=0)
        make_stat(ad, date=date(2026, 11, 25), views=0, clicks=1)

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert rows == [
            [
                '="2VfnxAD"',
                'ООО "Прайм Спорт Рус"',
                '="7718933790"',
                "Баннер А",
                # Период — первая и последняя дата с показами, не с кликами.
                "03.11.2026",
                "20.11.2026",
                "15",
                "4",
            ]
        ]

    def test_selection_across_month_boundary_gives_row_per_month(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        make_stat(ad, date=date(2026, 10, 30), views=3, clicks=0)
        make_stat(ad, date=date(2026, 10, 31), views=4, clicks=1)
        make_stat(ad, date=date(2026, 11, 1), views=5, clicks=2)

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert [(row[4], row[5], row[6], row[7]) for row in rows] == [
            ("30.10.2026", "31.10.2026", "7", "1"),
            ("01.11.2026", "01.11.2026", "5", "2"),
        ]

    def test_same_erid_on_two_banners_gives_two_rows(self):
        first = AdvertisementBannerFactory(erid="2VfnxSAME", title="Первый")
        second = AdvertisementBannerFactory(erid="2VfnxSAME", title="Второй")
        make_stat(first, date=date(2026, 11, 3), views=1)
        make_stat(second, date=date(2026, 11, 3), views=2)

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert sorted((row[3], row[6]) for row in rows) == [("Второй", "2"), ("Первый", "1")]

    def test_requisites_from_latest_row_and_title_change_does_not_split(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        make_stat(ad, date=date(2026, 11, 3), views=1, banner_title="Старое", advertiser_name="ООО Старое")
        make_stat(ad, date=date(2026, 11, 4), views=1, banner_title="Новое", advertiser_name="ООО Новое")

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert len(rows) == 1
        assert (rows[0][1], rows[0][3], rows[0][6]) == ("ООО Новое", "Новое", "2")

    def test_inn_with_leading_zero_is_text(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD", advertiser_inn="0123456789")
        make_stat(ad, date=date(2026, 11, 3), views=1)

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert rows[0][2] == '="0123456789"'

    def test_formula_cells_are_escaped(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        make_stat(
            ad,
            date=date(2026, 11, 3),
            views=1,
            banner_title='=HYPERLINK("http://evil","x")',
            advertiser_name="@SUM(1+1)",
        )

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert rows[0][3] == '\'=HYPERLINK("http://evil","x")'
        assert rows[0][1] == "'@SUM(1+1)"

    def test_quote_in_erid_does_not_break_text_cell(self):
        make_stat(None, banner_ref_id=1, date=date(2026, 11, 3), views=1, erid='ab"c', banner_title="Б")

        rows = export_rows(BannerDailyStat.objects.all())[1:]

        assert rows[0][0] == '="ab""c"'

    def test_respects_selection(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        selected = make_stat(ad, date=date(2026, 11, 3), views=1)
        make_stat(ad, date=date(2026, 11, 4), views=100)

        rows = export_rows(BannerDailyStat.objects.filter(pk=selected.pk))[1:]

        assert (rows[0][4], rows[0][5], rows[0][6]) == ("03.11.2026", "03.11.2026", "1")


# ---------------------------------------------------------------------------
# Раздел /marketing/: права, удаление баннера со статистикой, выгрузка
# ---------------------------------------------------------------------------


@pytest.fixture
def role_groups():
    _roles_migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))
    _stat_migration.grant_banner_stat_permissions(django_apps, SimpleNamespace(connection=connection))


def staff_client(group_name: str) -> Client:
    user = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@example.com", password="StrongPassword123!", is_staff=True
    )
    user.groups.add(Group.objects.get(name=group_name))
    client = Client()
    client.force_login(user)
    return client


def group_has(group_name: str, codename: str) -> bool:
    return Group.objects.get(name=group_name).permissions.filter(codename=codename).exists()


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.usefixtures("role_groups")
class TestMarketingSectionStats:
    def test_migration_grants_view_only(self):
        for group_name in (MARKETING_GROUP, SUPERVISORS_GROUP):
            assert group_has(group_name, "view_bannerdailystat")
            for codename in ("add_bannerdailystat", "change_bannerdailystat", "delete_bannerdailystat"):
                assert not group_has(group_name, codename)
        assert not group_has(MANAGERS_GROUP, "view_bannerdailystat")

    def test_migration_is_idempotent_and_keeps_manual_permissions(self):
        manual = Permission.objects.get(content_type__app_label="banners", codename="change_bannerdailystat")
        Group.objects.get(name=MARKETING_GROUP).permissions.add(manual)

        _stat_migration.grant_banner_stat_permissions(django_apps, SimpleNamespace(connection=connection))

        assert group_has(MARKETING_GROUP, "change_bannerdailystat")
        assert Group.objects.get(name=MARKETING_GROUP).permissions.filter(codename="view_bannerdailystat").count() == 1

    def test_registered_in_marketing_site(self):
        assert BannerDailyStat in marketing_site._registry

    def test_marketer_sees_stats_read_only(self):
        client = staff_client(MARKETING_GROUP)
        stat = make_stat(AdvertisementBannerFactory(erid="2VfnxAD"), views=3)

        listing = client.get(STATS_URL)
        card = client.get(f"{STATS_URL}{stat.pk}/change/")

        assert listing.status_code == 200
        assert f'href="{STATS_URL}add/"' not in listing.content.decode()
        assert card.status_code == 200
        assert 'name="views"' not in card.content.decode()
        assert client.post(f"{STATS_URL}{stat.pk}/change/", {"views": "999"}).status_code == 403
        assert client.post(f"{STATS_URL}{stat.pk}/delete/", {"post": "yes"}).status_code == 403
        stat.refresh_from_db()
        assert stat.views == 3

    def test_marketer_exports_csv(self):
        client = staff_client(MARKETING_GROUP)
        make_stat(AdvertisementBannerFactory(erid="2VfnxAD"), date=date(2026, 11, 3), views=3)

        response = client.get(EXPORT_URL, {"year": "2026", "month": "11"})

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        assert '"=""2VfnxAD"""' in response.content.decode("utf-8")

    def test_supervisor_sees_stats(self):
        client = staff_client(SUPERVISORS_GROUP)

        assert client.get(STATS_URL).status_code == 200

    def test_banner_columns_render_in_list(self):
        client = staff_client(MARKETING_GROUP)
        banner = AdvertisementBannerFactory()
        make_stat(banner, views=4, clicks=1)

        html = client.get(BANNERS_URL).content.decode()

        assert "Показы за 30 дней" in html
        assert "25,00 %" in html

    def test_delete_banner_with_stats_keeps_snapshot(self):
        client = staff_client(MARKETING_GROUP)
        banner = AdvertisementBannerFactory(erid="2VfnxGONE", title="Удаляемый")
        banner_pk = banner.pk
        make_stat(banner, date=date(2026, 11, 3), views=7, clicks=2)

        confirm = client.get(f"{BANNERS_URL}{banner_pk}/delete/")
        response = client.post(f"{BANNERS_URL}{banner_pk}/delete/", {"post": "yes"})

        assert confirm.status_code == 200
        assert response.status_code == 302
        assert not Banner.objects.filter(pk=banner_pk).exists()
        stat = BannerDailyStat.objects.get()
        assert (stat.banner_id, stat.banner_ref_id) == (None, banner_pk)
        assert (stat.banner_title, stat.erid, stat.advertiser_inn) == ("Удаляемый", "2VfnxGONE", "7718933790")

        rows = export_rows(BannerDailyStat.objects.all())[1:]
        assert rows == [
            [
                '="2VfnxGONE"',
                'ООО "Прайм Спорт Рус"',
                '="7718933790"',
                "Удаляемый",
                "03.11.2026",
                "03.11.2026",
                "7",
                "2",
            ]
        ]


# ---------------------------------------------------------------------------
# Сводка статистики за период
# ---------------------------------------------------------------------------

# Фиксированное «сегодня» для разбора периода: опции и проверки не зависят от даты прогона.
TODAY = date(2026, 11, 20)


@pytest.fixture
def period_rows():
    """Строки за 03.11.2026, 05.10.2026 и 01.06.2024 — опции периода строятся из них."""
    banner = BannerFactory()
    for day in (date(2026, 11, 3), date(2026, 10, 5), date(2024, 6, 1)):
        make_stat(banner, date=day, views=1)


@pytest.mark.django_db
@pytest.mark.usefixtures("period_rows")
class TestParsePeriod:
    @pytest.mark.parametrize(
        ("params", "expected"),
        [
            ({}, StatPeriod(2026, 11)),
            ({"year": ""}, StatPeriod(2026, 11)),
            ({"month": "11"}, StatPeriod(2026, 11)),
            ({"year": "all"}, StatPeriod()),
            ({"year": "all", "month": "11", "day": "3"}, StatPeriod()),
            ({"year": "2026"}, StatPeriod(2026)),
            ({"year": "2026", "month": "all"}, StatPeriod(2026)),
            ({"year": "2026", "month": "all", "day": "5"}, StatPeriod(2026)),
            ({"year": "2026", "month": "11"}, StatPeriod(2026, 11)),
            ({"year": "2026", "month": "11", "day": "all"}, StatPeriod(2026, 11)),
            ({"year": "2026", "month": "11", "day": "3"}, StatPeriod(2026, 11, 3)),
            # Сегодня — в опциях и без строк.
            ({"year": "2026", "month": "11", "day": "20"}, StatPeriod(2026, 11, 20)),
            ({"year": "2024", "month": "6", "day": "1"}, StatPeriod(2024, 6, 1)),
        ],
    )
    def test_valid_and_incomplete_input(self, params, expected):
        assert parse_period(params, TODAY) == (expected, False)

    @pytest.mark.parametrize(
        "params",
        [
            {"year": "abc"},
            {"year": "0"},
            {"year": "99999"},
            {"year": "9" * 1000},
            {"year": "²"},
            {"year": "-2026"},
            # Год без строк и будущий год.
            {"year": "2025"},
            {"year": "2027"},
            {"year": "2026", "month": "13"},
            {"year": "2026", "month": "0"},
            # Будущий месяц и месяц без строк.
            {"year": "2026", "month": "12"},
            {"year": "2024", "month": "7"},
            {"year": "2026", "month": "11", "day": "31"},
            # Будущий день и день без строк.
            {"year": "2026", "month": "11", "day": "21"},
            {"year": "2026", "month": "11", "day": "4"},
        ],
    )
    def test_invalid_input_gives_default_period(self, params):
        assert parse_period(params, TODAY) == (StatPeriod(2026, 11), True)

    def test_options_come_from_data_plus_current_without_future(self):
        make_stat(BannerFactory(), date=date(2026, 12, 1), views=1)
        make_stat(BannerFactory(), date=date(2027, 1, 1), views=1)

        assert year_options(TODAY) == [2026, 2024]
        assert month_options(2026, TODAY) == [10, 11]
        assert day_options(2026, 11, TODAY) == [3, 20]
        assert day_options(2026, 10, TODAY) == [5]

    def test_current_year_listed_without_rows(self):
        assert year_options(date(2028, 2, 10)) == [2028, 2026, 2024]
        assert month_options(2028, date(2028, 2, 10)) == [2]
        assert day_options(2028, 2, date(2028, 2, 10)) == [10]

    def test_query_and_label(self):
        assert StatPeriod().query() == {"year": "all"}
        assert StatPeriod(2026).query() == {"year": "2026", "month": "all"}
        assert StatPeriod(2026, 11).query() == {"year": "2026", "month": "11", "day": "all"}
        assert StatPeriod(2026, 11, 3).query() == {"year": "2026", "month": "11", "day": "3"}
        assert StatPeriod().label(TODAY) == "за весь период"
        assert StatPeriod(2026).label(TODAY) == "2026 год"
        assert StatPeriod(2026, 10).label(TODAY) == "октябрь 2026"
        assert StatPeriod(2026, 11).label(TODAY) == "ноябрь 2026 (с 1 по 20 ноября)"
        assert StatPeriod(2026, 11, 3).label(TODAY) == "3 ноября 2026"


def summary(client: Client, params: dict[str, str] | None = None) -> Any:
    response = client.get(STATS_URL, params or {})
    assert response.status_code == 200
    return response


def summary_table(response: Any) -> list[tuple[str, int, str, int, int]]:
    return [
        (row["banner_title"], row["banner_ref_id"], row["erid"], row["views"], row["clicks"])
        for row in response.context["rows"]
    ]


@pytest.mark.integration
@pytest.mark.django_db
@pytest.mark.usefixtures("role_groups")
class TestStatSummary:
    def test_month_sums_days_into_one_row(self):
        banner = AdvertisementBannerFactory(erid="2VfnxAD", title="Баннер")
        for day in (3, 4, 5, 6, 7):
            make_stat(banner, date=date(2026, 11, day), views=10, clicks=1)
        make_stat(banner, date=date(2026, 10, 31), views=1000)

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"})

        assert summary_table(response) == [("Баннер", banner.pk, "2VfnxAD", 50, 5)]
        assert response.context["total"] == {"views": 50, "clicks": 5, "ctr": "10,00 %"}
        html = response.content.decode()
        assert "Итого" in html
        assert "Период: ноябрь 2026" in html

    def test_day_shows_sums_for_that_day(self):
        first = BannerFactory(title="А")
        second = BannerFactory(title="Б")
        make_stat(first, date=date(2026, 11, 3), views=4, clicks=1)
        make_stat(second, date=date(2026, 11, 3), views=2)
        make_stat(first, date=date(2026, 11, 4), views=100)

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11", "day": "3"})

        assert summary_table(response) == [("А", first.pk, "", 4, 1), ("Б", second.pk, "", 2, 0)]
        assert "Период: 3 ноября 2026" in response.content.decode()

    def test_erid_change_mid_month_gives_two_rows(self):
        banner = AdvertisementBannerFactory(erid="2VfnxNEW", title="Баннер")
        make_stat(banner, date=date(2026, 11, 3), erid="2VfnxOLD", views=3)
        make_stat(banner, date=date(2026, 11, 10), views=5)

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"})

        assert summary_table(response) == [
            ("Баннер", banner.pk, "2VfnxNEW", 5, 0),
            ("Баннер", banner.pk, "2VfnxOLD", 3, 0),
        ]

    def test_year_groups_months(self):
        banner = AdvertisementBannerFactory(erid="2VfnxAD", title="Баннер")
        make_stat(banner, date=date(2026, 10, 5), views=3)
        make_stat(banner, date=date(2026, 11, 3), views=5)
        make_stat(banner, date=date(2024, 6, 1), views=100)

        client = staff_client(MARKETING_GROUP)
        year = summary(client, {"year": "2026", "month": "all"})
        everything = summary(client, {"year": "all"})

        assert summary_table(year) == [("Баннер", banner.pk, "2VfnxAD", 8, 0)]
        assert summary_table(everything) == [("Баннер", banner.pk, "2VfnxAD", 108, 0)]
        html = everything.content.decode()
        assert 'name="year"' in html
        assert 'name="month"' not in html
        assert 'name="day"' not in html

    def test_deleted_banner_listed_with_last_title(self):
        gone = AdvertisementBannerFactory(erid="2VfnxGONE")
        gone_pk = gone.pk
        make_stat(gone, date=date(2026, 11, 3), banner_title="Старое название", views=1)
        make_stat(gone, date=date(2026, 11, 4), banner_title="Последнее название", views=2)
        gone.delete()

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"})

        assert summary_table(response) == [("Последнее название", gone_pk, "2VfnxGONE", 3, 0)]
        assert f"Последнее название ({gone_pk})" in response.content.decode()

    def test_renamed_banner_has_one_row_with_new_title(self):
        banner = AdvertisementBannerFactory(erid="2VfnxAD", title="Старое")
        make_stat(banner, date=date(2026, 10, 5), views=2)
        make_stat(banner, date=date(2026, 10, 6), views=3)

        banner.title = "Новое"
        banner.save()
        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "10"})

        assert summary_table(response) == [("Новое", banner.pk, "2VfnxAD", 5, 0)]

    def test_titles_are_escaped(self):
        make_stat(BannerFactory(), date=date(2026, 11, 3), banner_title="<script>x</script>", views=1)

        html = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"}).content.decode()

        assert "<script>x</script>" not in html
        assert "&lt;script&gt;x&lt;/script&gt;" in html

    def test_default_is_current_month(self):
        today = timezone.localdate()
        banner = AdvertisementBannerFactory(erid="2VfnxAD")
        make_stat(banner, date=today, views=4)
        # 40 дней назад — всегда прошлый месяц или раньше.
        make_stat(banner, date=today - timedelta(days=40), views=1000)

        response = summary(staff_client(MARKETING_GROUP))

        assert response.context["period"] == StatPeriod(today.year, today.month)
        assert [row[3] for row in summary_table(response)] == [4]
        assert response.context["export_url"] == f"{EXPORT_URL}?year={today.year}&month={today.month}&day=all"
        assert f"{EXPORT_URL}?year={today.year}&amp;month={today.month}&amp;day=all" in response.content.decode()
        assert response.context["period_error"] == ""

    def test_options_from_data_plus_current_without_future(self):
        today = timezone.localdate()
        banner = BannerFactory()
        make_stat(banner, date=date(2024, 6, 1), views=1)
        make_stat(banner, date=date(today.year + 1, 1, 1), views=1)

        response = summary(staff_client(MARKETING_GROUP))

        years = [option["value"] for option in response.context["period_selects"][0]["options"]]
        assert years == ["all", str(today.year), "2024"]
        assert str(today.year + 1) not in years

    def test_year_without_rows_is_invalid(self):
        make_stat(BannerFactory(), date=date(2024, 6, 1), views=1)
        today = timezone.localdate()

        response = summary(staff_client(MARKETING_GROUP), {"year": "2023", "month": "all"})

        assert response.context["period"] == StatPeriod(today.year, today.month)
        assert "Период указан неверно" in response.content.decode()

    @pytest.mark.parametrize("year", ["abc", "0", "99999"])
    def test_garbage_year_does_not_fail(self, year):
        response = summary(staff_client(MARKETING_GROUP), {"year": year})

        assert "Период указан неверно" in response.content.decode()

    def test_export_csv_for_year_has_row_per_month(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD", title="Баннер")
        make_stat(ad, date=date(2026, 10, 5), views=3)
        make_stat(ad, date=date(2026, 11, 3), views=5, clicks=1)
        make_stat(ad, date=date(2024, 6, 1), views=100)

        response = staff_client(MARKETING_GROUP).get(EXPORT_URL, {"year": "2026", "month": "all"})

        assert response.status_code == 200
        assert response["Content-Type"].startswith("text/csv")
        content = response.content.decode("utf-8")
        assert content.startswith("﻿")
        rows = list(csv.reader(io.StringIO(content[1:]), delimiter=";"))
        assert rows[0][0] == "ERID"
        assert [(row[0], row[4], row[5], row[6], row[7]) for row in rows[1:]] == [
            ('="2VfnxAD"', "05.10.2026", "05.10.2026", "3", "0"),
            ('="2VfnxAD"', "03.11.2026", "03.11.2026", "5", "1"),
        ]

    def test_export_csv_for_day(self):
        ad = AdvertisementBannerFactory(erid="2VfnxAD")
        make_stat(ad, date=date(2026, 11, 3), views=3)
        make_stat(ad, date=date(2026, 11, 4), views=5)

        response = staff_client(MARKETING_GROUP).get(EXPORT_URL, {"year": "2026", "month": "11", "day": "4"})

        rows = list(csv.reader(io.StringIO(response.content.decode("utf-8")[1:]), delimiter=";"))[1:]
        assert [(row[4], row[6]) for row in rows] == [("04.11.2026", "5")]

    def test_supervisor_sees_summary_and_exports(self):
        client = staff_client(SUPERVISORS_GROUP)

        assert client.get(STATS_URL, {"year": "all"}).status_code == 200
        assert client.get(EXPORT_URL, {"year": "all"}).status_code == 200

    def test_section_member_without_permission_gets_403(self):
        view = Permission.objects.get(content_type__app_label="banners", codename="view_bannerdailystat")
        Group.objects.get(name=MARKETING_GROUP).permissions.remove(view)
        client = staff_client(MARKETING_GROUP)

        assert client.get(STATS_URL).status_code == 403
        assert client.get(EXPORT_URL, {"year": "all"}).status_code == 403

    def test_superuser_sees_summary_in_admin(self):
        user = User.objects.create_superuser(
            email=f"root_{get_unique_suffix()}@example.com", password="StrongPassword123!"
        )
        client = Client()
        client.force_login(user)
        make_stat(AdvertisementBannerFactory(erid="2VfnxAD"), date=date(2026, 11, 3), views=3)

        response = client.get("/admin/banners/bannerdailystat/", {"year": "2026", "month": "11"})

        assert response.status_code == 200
        assert response.context["export_url"] == "/admin/banners/bannerdailystat/export-ord/?year=2026&month=11&day=all"
        assert client.get(response.context["export_url"]).status_code == 200

    def test_export_with_invalid_period_redirects_to_summary(self):
        make_stat(AdvertisementBannerFactory(erid="2VfnxAD"), date=date(2024, 6, 1), views=1)

        response = staff_client(MARKETING_GROUP).get(EXPORT_URL, {"year": "2023", "month": "all"})

        assert response.status_code == 302
        assert response["Location"] == f"{STATS_URL}?year=2023&month=all"
        assert not response.get("Content-Type", "").startswith("text/csv")

    def test_requisites_and_ctr_from_latest_row(self):
        banner = AdvertisementBannerFactory(erid="2VfnxAD", title="Баннер")
        make_stat(
            banner,
            date=date(2026, 11, 3),
            views=10,
            clicks=1,
            advertiser_name="ООО Прежний",
            advertiser_inn="7718933790",
        )
        make_stat(
            banner,
            date=date(2026, 11, 4),
            views=30,
            clicks=3,
            advertiser_name="ООО Нынешний",
            advertiser_inn="500100732259",
        )

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"})

        [row] = response.context["rows"]
        assert (row["advertiser_name"], row["advertiser_inn"], row["ctr"]) == (
            "ООО Нынешний",
            "500100732259",
            "10,00 %",
        )
        html = response.content.decode()
        assert "ООО Нынешний" in html
        assert "500100732259" in html
        assert "ООО Прежний" not in html

    def test_rows_sorted_by_title_case_insensitive(self):
        # Порядок создания (pk) не совпадает с алфавитным и регистр не влияет на сортировку.
        for title in ("Б", "а", "В"):
            make_stat(BannerFactory(title=title), date=date(2026, 11, 3), views=1)

        response = summary(staff_client(MARKETING_GROUP), {"year": "2026", "month": "11"})

        assert [row["banner_title"] for row in response.context["rows"]] == ["а", "Б", "В"]

    def test_manager_redirected_to_login(self):
        client = staff_client(MANAGERS_GROUP)

        for url in (STATS_URL, EXPORT_URL):
            response = client.get(url)
            assert response.status_code == 302
            assert "/marketing/login/" in response["Location"]

"""
Приём событий баннеров `POST /api/v1/site-events/` и запись дневной статистики.

Покрытие (спека spec-banner-impressions-clicks-ord, матрица I/O):
- пачка событий, повтор баннера в пачке, text/plain-тело;
- неизвестный, выключенный и вне дат баннер — 204 без записи;
- баннер шапки (hero) и смешанная пачка — пишется только marketing
  (спека spec-banner-stats-marketing-only);
- невалидное тело — 400 без записи; бот — 204 без записи; лимит — 429;
- смена ERID — новая строка; ERID нерекламного баннера не пишется;
- сутки по Europe/Moscow; параллельные upsert; гонка с удалением баннера;
- ни cookie, ни IP/UA в БД.
"""

from __future__ import annotations

import json
import threading
from datetime import date, datetime, timedelta
from datetime import timezone as dt_timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.db import IntegrityError, connection
from django.utils import timezone
from rest_framework.test import APIClient

from apps.banners import services
from apps.banners.factories import (
    AdvertisementBannerFactory,
    BannerFactory,
    ExpiredBannerFactory,
    FutureBannerFactory,
    InactiveBannerFactory,
    MarketingBannerFactory,
)
from apps.banners.models import Banner, BannerDailyStat
from apps.common.throttling import SiteEventsThrottle

URL = "/api/v1/site-events/"
BROWSER_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0"


def post_events(client: APIClient, events: Any, **extra: Any) -> Any:
    extra.setdefault("HTTP_USER_AGENT", BROWSER_UA)
    return client.post(URL, data=json.dumps({"events": events}), content_type="application/json", **extra)


def view(banner: Banner) -> dict[str, Any]:
    return {"banner_id": banner.pk, "kind": "view"}


def click(banner: Banner) -> dict[str, Any]:
    return {"banner_id": banner.pk, "kind": "click"}


@pytest.fixture
def client() -> APIClient:
    cache.clear()
    return APIClient()


@pytest.mark.integration
@pytest.mark.django_db
class TestAcceptEvents:
    def test_batch_counts_view_and_click(self, client):
        banner = AdvertisementBannerFactory()

        response = post_events(client, [view(banner), click(banner)])

        assert response.status_code == 204
        stat = BannerDailyStat.objects.get()
        assert (stat.banner_id, stat.banner_ref_id, stat.date) == (banner.pk, banner.pk, timezone.localdate())
        assert (stat.views, stat.clicks) == (1, 1)
        assert stat.erid == banner.erid
        assert (stat.banner_title, stat.advertiser_name, stat.advertiser_inn) == (
            banner.title,
            banner.advertiser_name,
            banner.advertiser_inn,
        )

    def test_repeated_banner_in_batch_is_aggregated(self, client):
        first = AdvertisementBannerFactory()
        second = MarketingBannerFactory()

        response = post_events(client, [view(first), view(second), view(first), click(first), view(first)])

        assert response.status_code == 204
        assert BannerDailyStat.objects.get(banner_ref_id=first.pk).views == 3
        assert BannerDailyStat.objects.get(banner_ref_id=first.pk).clicks == 1
        assert (BannerDailyStat.objects.get(banner_ref_id=second.pk).views, BannerDailyStat.objects.count()) == (1, 2)

    def test_next_batch_increments_same_row(self, client):
        banner = AdvertisementBannerFactory()

        post_events(client, [view(banner)])
        post_events(client, [view(banner), click(banner)])

        stat = BannerDailyStat.objects.get()
        assert (stat.views, stat.clicks) == (2, 1)

    def test_text_plain_body_is_parsed_as_json(self, client):
        banner = MarketingBannerFactory()

        response = client.post(
            URL,
            data=json.dumps({"events": [view(banner)]}),
            content_type="text/plain;charset=UTF-8",
            HTTP_USER_AGENT=BROWSER_UA,
        )

        assert response.status_code == 204
        assert BannerDailyStat.objects.get().views == 1

    def test_marketing_banner_without_erid_is_counted_with_empty_erid(self, client):
        banner = MarketingBannerFactory()

        post_events(client, [view(banner)])

        stat = BannerDailyStat.objects.get()
        assert (stat.erid, stat.advertiser_name, stat.advertiser_inn) == ("", "", "")
        assert stat.banner_title == banner.title

    def test_authorization_header_is_ignored(self, client):
        """Аутентификации нет: битый токен не превращает запрос в 401."""
        banner = MarketingBannerFactory()

        response = post_events(client, [view(banner)], HTTP_AUTHORIZATION="Bearer broken")

        assert response.status_code == 204
        assert BannerDailyStat.objects.get().views == 1


@pytest.mark.integration
@pytest.mark.django_db
class TestDroppedEvents:
    @pytest.mark.parametrize(
        "factory",
        [InactiveBannerFactory, ExpiredBannerFactory, FutureBannerFactory],
        ids=["inactive", "expired", "future"],
    )
    def test_not_shown_banner_is_silently_dropped(self, client, factory):
        banner = factory(type=Banner.BannerType.MARKETING)

        response = post_events(client, [view(banner), click(banner)])

        assert response.status_code == 204
        assert not BannerDailyStat.objects.exists()

    def test_hero_banner_event_is_silently_dropped(self, client):
        banner = BannerFactory(type=Banner.BannerType.HERO)

        response = post_events(client, [view(banner), click(banner)])

        assert response.status_code == 204
        assert not BannerDailyStat.objects.exists()

    def test_mixed_batch_writes_only_marketing(self, client):
        hero = BannerFactory(type=Banner.BannerType.HERO)
        marketing = AdvertisementBannerFactory()

        response = post_events(client, [view(hero), view(marketing), click(hero), click(marketing)])

        assert response.status_code == 204
        assert list(BannerDailyStat.objects.values_list("banner_ref_id", "views", "clicks")) == [(marketing.pk, 1, 1)]

    def test_unknown_banner_is_dropped_and_known_is_counted(self, client):
        banner = MarketingBannerFactory()

        response = post_events(client, [{"banner_id": 999_999_999, "kind": "view"}, view(banner)])

        assert response.status_code == 204
        assert list(BannerDailyStat.objects.values_list("banner_ref_id", "views")) == [(banner.pk, 1)]

    @pytest.mark.parametrize(
        "user_agent",
        [
            "Mozilla/5.0 (compatible; YandexBot/3.0; +http://yandex.com/bots)",
            "Googlebot/2.1 (+http://www.google.com/bot.html)",
            "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko) HeadlessChrome/131.0 Safari/537.36",
            "Mozilla/5.0 (Linux; Android 11) Chrome-Lighthouse",
            "Screaming Frog SEO Spider/20.0",
            "SomeCrawler/1.0",
        ],
    )
    def test_bot_is_not_counted(self, client, user_agent):
        banner = MarketingBannerFactory()

        response = post_events(client, [view(banner)], HTTP_USER_AGENT=user_agent)

        assert response.status_code == 204
        assert not BannerDailyStat.objects.exists()


@pytest.mark.integration
@pytest.mark.django_db
class TestInvalidBody:
    @pytest.mark.parametrize(
        "body",
        [
            {"events": [{"banner_id": 1, "kind": "hover"}]},
            {"events": [{"banner_id": 0, "kind": "view"}]},
            {"events": [{"banner_id": "abc", "kind": "view"}]},
            {"events": [{"banner_id": 2**63, "kind": "view"}]},
            {"events": [{"kind": "view"}]},
            {"events": []},
            {"events": "view"},
            {},
            [{"banner_id": 1, "kind": "view"}],
        ],
        ids=["kind", "zero-id", "str-id", "bigint-overflow", "no-id", "empty", "not-list", "no-events", "list-body"],
    )
    def test_invalid_payload_is_400(self, client, body):
        MarketingBannerFactory()

        response = client.post(URL, data=json.dumps(body), content_type="application/json", HTTP_USER_AGENT=BROWSER_UA)

        assert response.status_code == 400
        assert not BannerDailyStat.objects.exists()

    def test_more_than_fifty_events_is_400_and_nothing_written(self, client):
        banner = MarketingBannerFactory()

        response = post_events(client, [view(banner)] * 51)

        assert response.status_code == 400
        assert not BannerDailyStat.objects.exists()

    def test_exactly_fifty_events_is_accepted(self, client):
        banner = MarketingBannerFactory()

        response = post_events(client, [view(banner)] * 50)

        assert response.status_code == 204
        assert BannerDailyStat.objects.get().views == 50

    @pytest.mark.parametrize("content_type", ["application/json", "text/plain"])
    def test_not_json_is_400(self, client, content_type):
        response = client.post(URL, data="not json{", content_type=content_type, HTTP_USER_AGENT=BROWSER_UA)

        assert response.status_code == 400
        assert not BannerDailyStat.objects.exists()


@pytest.mark.integration
@pytest.mark.django_db
class TestThrottle:
    def test_scope_is_explicit_and_global_throttles_do_not_apply(self):
        from apps.banners.views import SiteEventsView

        assert SiteEventsView.throttle_classes == [SiteEventsThrottle]
        assert SiteEventsThrottle.scope == "site_events"

    def test_limit_returns_429(self, client):
        banner = MarketingBannerFactory()
        statuses = []

        with patch.object(SiteEventsThrottle, "THROTTLE_RATES", {"site_events": "3/min"}):
            for _ in range(6):
                statuses.append(post_events(client, [view(banner)], REMOTE_ADDR="198.51.100.10").status_code)
            other_ip = post_events(client, [view(banner)], REMOTE_ADDR="198.51.100.11").status_code
        cache.clear()

        assert statuses == [204, 204, 204, 429, 429, 429]
        assert other_ip == 204
        assert BannerDailyStat.objects.get().views == 4


@pytest.mark.integration
@pytest.mark.django_db
class TestSnapshot:
    def test_erid_change_during_day_creates_new_row(self, client):
        banner = AdvertisementBannerFactory(erid="2VfnxOLD")
        post_events(client, [view(banner), view(banner)])

        banner.erid = "2VfnxNEW"
        banner.save()
        post_events(client, [view(banner)])

        rows = dict(BannerDailyStat.objects.values_list("erid", "views"))
        assert rows == {"2VfnxOLD": 2, "2VfnxNEW": 1}
        assert set(BannerDailyStat.objects.values_list("banner_ref_id", flat=True)) == {banner.pk}

    def test_non_advertisement_banner_does_not_write_erid_or_advertiser(self, client):
        # Галочку «Является рекламой» сняли, реквизиты остались в БД.
        banner = BannerFactory(
            type=Banner.BannerType.MARKETING,
            is_advertisement=False,
            erid="2VfnxSTALE",
            advertiser_name='ООО "Старый рекламодатель"',
            advertiser_inn="7718933790",
        )

        post_events(client, [view(banner)])

        stat = BannerDailyStat.objects.get()
        assert (stat.erid, stat.advertiser_name, stat.advertiser_inn) == ("", "", "")

    def test_title_snapshot_follows_latest_event(self, client):
        banner = AdvertisementBannerFactory(title="Старое название")
        post_events(client, [view(banner)])

        Banner.objects.filter(pk=banner.pk).update(title="Новое название")
        post_events(client, [view(banner)])

        stat = BannerDailyStat.objects.get()
        assert (stat.banner_title, stat.views) == ("Новое название", 2)

    def test_day_is_moscow_date(self):
        banner = MarketingBannerFactory()
        # 22:30 UTC — уже 01:30 следующих суток по Москве.
        moment = datetime(2026, 11, 19, 22, 30, tzinfo=dt_timezone.utc)

        with patch("django.utils.timezone.now", return_value=moment):
            services.record_events([view(banner)])

        assert BannerDailyStat.objects.get().date == date(2026, 11, 20)

    def test_banner_window_is_checked_at_event_time(self):
        banner = MarketingBannerFactory(end_date=timezone.now() + timedelta(hours=1))

        with patch("django.utils.timezone.now", return_value=timezone.now() + timedelta(hours=2)):
            services.record_events([view(banner)])

        assert not BannerDailyStat.objects.exists()


@pytest.mark.integration
@pytest.mark.django_db
class TestPrivacy:
    def test_no_cookies_are_set(self, client):
        banner = MarketingBannerFactory()

        response = post_events(client, [view(banner), click(banner)], REMOTE_ADDR="203.0.113.5")

        assert response.status_code == 204
        assert not response.cookies
        assert "Set-Cookie" not in response.headers

    def test_stat_has_no_identifying_columns(self):
        columns = {field.column for field in BannerDailyStat._meta.concrete_fields}  # type: ignore[attr-defined]

        assert columns == {
            "id",
            "banner_id",
            "banner_ref_id",
            "date",
            "erid",
            "banner_title",
            "advertiser_name",
            "advertiser_inn",
            "views",
            "clicks",
        }

    def test_ip_and_user_agent_are_not_stored(self, client):
        banner = MarketingBannerFactory()

        post_events(client, [view(banner)], REMOTE_ADDR="203.0.113.77", HTTP_USER_AGENT="UniqueAgent/77.7")

        dumped = json.dumps(list(BannerDailyStat.objects.values()), default=str)
        assert "203.0.113.77" not in dumped
        assert "UniqueAgent" not in dumped


@pytest.mark.django_db
class TestRecordEventsService:
    def test_empty_batch_writes_nothing(self):
        assert services.record_events([]) == 0
        assert not BannerDailyStat.objects.exists()

    def test_integrity_error_on_one_banner_is_swallowed(self, caplog):
        doomed = MarketingBannerFactory()
        survivor = MarketingBannerFactory()
        real_cursor = connection.cursor

        def cursor():
            wrapper = real_cursor()
            original_execute = wrapper.execute

            def execute(sql, params=None):
                if params and params.get("banner_id") == doomed.pk:
                    raise IntegrityError("insert or update violates foreign key constraint")
                return original_execute(sql, params)

            wrapper.execute = execute  # type: ignore[method-assign]
            return wrapper

        with patch("apps.banners.services.connection", SimpleNamespace(cursor=cursor)):
            written = services.record_events([view(doomed), view(survivor)])

        assert written == 1
        assert list(BannerDailyStat.objects.values_list("banner_ref_id", flat=True)) == [survivor.pk]
        assert str(doomed.pk) in caplog.text

    def test_deleted_banner_row_survives_and_new_events_are_dropped(self):
        banner = AdvertisementBannerFactory()
        services.record_events([view(banner)])
        banner_pk = banner.pk

        banner.delete()
        services.record_events([{"banner_id": banner_pk, "kind": "view"}])

        stat = BannerDailyStat.objects.get()
        assert (stat.banner_id, stat.banner_ref_id, stat.views) == (None, banner_pk, 1)


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestConcurrency:
    def test_parallel_upserts_lose_no_increment(self):
        first = AdvertisementBannerFactory()
        second = MarketingBannerFactory()
        threads_count, rounds = 6, 15
        errors: list[BaseException] = []
        barrier = threading.Barrier(threads_count)

        def worker(index: int) -> None:
            try:
                barrier.wait()
                for _ in range(rounds):
                    # Разный порядок баннеров в пачках: сортировка ключей не даёт дедлоков.
                    batch = [view(first), click(second)] if index % 2 else [click(second), view(first)]
                    services.record_events(batch)
            except BaseException as exc:  # noqa: BLE001 — ошибку потока проверяет тест
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(threads_count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert BannerDailyStat.objects.get(banner_ref_id=first.pk).views == threads_count * rounds
        assert BannerDailyStat.objects.get(banner_ref_id=second.pk).clicks == threads_count * rounds
        assert BannerDailyStat.objects.count() == 2

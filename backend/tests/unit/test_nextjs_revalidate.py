"""
Сброс ISR-кэша Next.js (`apps/common/services/nextjs_revalidate.py`).

- `RevalidateNextjsTest` — исходы запроса к Next в логе; перенесён из
  `apps/pages/tests.py` вместе с функцией (стори 42.6, решение 13), проверки
  прежние;
- `TestFeaturedBrandHomeRevalidation` — сигнал брендов сбрасывает главную `/home`
  после commit сохранения бренда, который был или стал избранным (стори 42.6, AC7);
- `TestPageRevalidation` — сигнал страниц сбрасывает `/<slug>` после commit
  сохранения и удаления `Page`.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`):
`transaction.on_commit` вне явной транзакции выполняется сразу.
"""

from __future__ import annotations

from unittest.mock import Mock, patch

import pytest
import requests
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, override_settings

from apps.common.services.nextjs_revalidate import (
    HOME_PAGE_PATH,
    revalidate_nextjs_path,
    revalidate_nextjs_path_in_background,
)
from apps.pages.models import Page
from apps.products.constants import FEATURED_BRANDS_CACHE_KEY
from apps.products.factories import BrandFactory
from apps.products.models import Brand

pytestmark = pytest.mark.django_db(transaction=True)


class RevalidateNextjsTest(TestCase):
    """Сброс ISR-кэша Next.js: каждый исход виден в логе.

    На проде обе настройки отсутствовали, и сброс не срабатывал ни разу,
    не оставив ни строки в логах. Эти тесты закрепляют, что тишины больше нет.
    """

    LOGGER = "apps.common.services.nextjs_revalidate"
    POST = "apps.common.services.nextjs_revalidate.requests.post"

    @override_settings(FRONTEND_INTERNAL_URL="", REVALIDATE_SECRET="s3cret")
    def test_missing_frontend_url_is_logged(self):
        with patch(self.POST) as post, self.assertLogs(self.LOGGER, "WARNING") as logs:
            revalidate_nextjs_path("/oferta")

        post.assert_not_called()
        self.assertIn("skipped for /oferta", logs.output[0])

    @override_settings(FRONTEND_INTERNAL_URL="http://frontend:3000", REVALIDATE_SECRET="")
    def test_missing_secret_is_logged(self):
        with patch(self.POST) as post, self.assertLogs(self.LOGGER, "WARNING") as logs:
            revalidate_nextjs_path("/oferta")

        post.assert_not_called()
        self.assertIn("skipped for /oferta", logs.output[0])

    @override_settings(FRONTEND_INTERNAL_URL="http://frontend:3000", REVALIDATE_SECRET="s3cret")
    def test_success_posts_path_with_secret(self):
        with patch(self.POST, return_value=Mock(ok=True, status_code=200)) as post:
            with self.assertLogs(self.LOGGER, "INFO") as logs:
                revalidate_nextjs_path("/oferta")

        post.assert_called_once_with(
            "http://frontend:3000/api/revalidate",
            json={"path": "/oferta"},
            headers={"x-revalidate-secret": "s3cret"},
            timeout=10,
        )
        self.assertIn("triggered for /oferta", logs.output[0])

    @override_settings(FRONTEND_INTERNAL_URL="http://frontend:3000", REVALIDATE_SECRET="s3cret")
    def test_rejected_response_is_logged_as_warning(self):
        with patch(self.POST, return_value=Mock(ok=False, status_code=401)):
            with self.assertLogs(self.LOGGER, "WARNING") as logs:
                revalidate_nextjs_path("/oferta")

        self.assertIn("rejected for /oferta: HTTP 401", logs.output[0])
        self.assertNotIn("triggered", "".join(logs.output))

    @override_settings(FRONTEND_INTERNAL_URL="http://frontend:3000", REVALIDATE_SECRET="s3cret")
    def test_network_error_is_logged_as_warning(self):
        error = requests.ConnectionError("refused")
        with patch(self.POST, side_effect=error):
            with self.assertLogs(self.LOGGER, "WARNING") as logs:
                revalidate_nextjs_path("/oferta")

        self.assertIn("failed for /oferta: refused", logs.output[0])


def test_background_runs_revalidation_in_daemon_thread():
    with patch("apps.common.services.nextjs_revalidate.threading.Thread") as thread_cls:
        revalidate_nextjs_path_in_background("/home")

    thread_cls.assert_called_once_with(target=revalidate_nextjs_path, args=("/home",), daemon=True)
    thread_cls.return_value.start.assert_called_once_with()


def test_home_page_path_literal():
    # Маршрут главной Next — (blue)/home; «/» — динамический редирект вне ISR.
    assert HOME_PAGE_PATH == "/home"


@pytest.fixture
def home_reset():
    with patch("apps.products.signals.revalidate_nextjs_path_in_background") as reset:
        yield reset


def featured_brand(**extra) -> Brand:
    return BrandFactory(is_featured=True, image="brands/logo.png", **extra)


class TestFeaturedBrandHomeRevalidation:
    """AC7: сброс `/home` — только для бренда, который был или стал избранным."""

    def test_became_featured(self, home_reset):
        brand = BrandFactory(is_featured=False, image="brands/logo.png")
        home_reset.reset_mock()

        brand.is_featured = True
        brand.save()

        home_reset.assert_called_once_with("/home")

    def test_stopped_being_featured(self, home_reset):
        brand = featured_brand()
        home_reset.reset_mock()

        brand.is_featured = False
        brand.save()

        home_reset.assert_called_once_with("/home")

    def test_featured_brand_changed(self, home_reset):
        """Правка описания избранного бренда — сброс главной, кэш API прежним условием не трогается."""
        brand = featured_brand()
        home_reset.reset_mock()
        cache.set(FEATURED_BRANDS_CACHE_KEY, ["stale"])

        brand.description = "Новое описание"
        brand.save(update_fields=["description", "updated_at"])

        home_reset.assert_called_once_with("/home")
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) == ["stale"]

    def test_featured_brand_renamed_resets_api_cache_first(self, home_reset):
        brand = featured_brand()
        cache.set(FEATURED_BRANDS_CACHE_KEY, ["stale"])
        seen_cache: list = []
        home_reset.side_effect = lambda path: seen_cache.append(cache.get(FEATURED_BRANDS_CACHE_KEY))

        brand.name = f"{brand.name} Pro"
        brand.save()

        # Пересборка главной читает featured endpoint — кэш API к этому моменту сброшен.
        assert seen_cache == [None]

    def test_not_featured_brand_changed(self, home_reset):
        """Неизбранный бренд на главной не виден: правка, в том числе импортом 1С, сброса не даёт."""
        brand = BrandFactory(is_featured=False)
        home_reset.reset_mock()

        brand.name = f"{brand.name} 1С"
        brand.is_active = False
        brand.save(update_fields=["name", "normalized_name", "is_active", "updated_at"])

        home_reset.assert_not_called()

    def test_queryset_update_bypasses_signals(self, home_reset):
        brand = featured_brand()
        other = BrandFactory(is_featured=False)
        home_reset.reset_mock()

        Brand.objects.filter(pk__in=[brand.pk, other.pk]).update(description="массово")

        home_reset.assert_not_called()

    def test_create_featured(self, home_reset):
        featured_brand()

        home_reset.assert_called_once_with("/home")

    def test_create_not_featured(self, home_reset):
        BrandFactory(is_featured=False)

        home_reset.assert_not_called()

    def test_delete_featured(self, home_reset):
        brand = featured_brand()
        home_reset.reset_mock()

        brand.delete()

        home_reset.assert_called_once_with("/home")

    def test_delete_not_featured(self, home_reset):
        brand = BrandFactory(is_featured=False)
        home_reset.reset_mock()

        brand.delete()

        home_reset.assert_not_called()

    def test_rollback_does_not_reset(self, home_reset):
        brand = BrandFactory(is_featured=False, image="brands/logo.png")
        home_reset.reset_mock()

        with pytest.raises(RuntimeError):
            with transaction.atomic():
                brand.is_featured = True
                brand.save()
                raise RuntimeError("откат")

        home_reset.assert_not_called()

    def test_reset_waits_for_commit(self, home_reset):
        brand = BrandFactory(is_featured=False, image="brands/logo.png")
        home_reset.reset_mock()

        with transaction.atomic():
            brand.is_featured = True
            brand.save()
            home_reset.assert_not_called()

        home_reset.assert_called_once_with("/home")


class TestPageRevalidation:
    """Сохранение и удаление `Page` сбрасывают ISR `/<slug>` после commit (R42.6-8)."""

    @pytest.fixture
    def page_reset(self):
        with patch("apps.pages.signals.revalidate_nextjs_path_in_background") as reset:
            yield reset

    def test_save_resets_page_path_after_commit(self, page_reset):
        with transaction.atomic():
            Page.objects.create(title="Оферта", slug="oferta", content="<p>текст</p>")
            page_reset.assert_not_called()

        page_reset.assert_called_once_with("/oferta")

    def test_delete_resets_page_path(self, page_reset):
        page = Page.objects.create(title="Оферта", slug="oferta", content="<p>текст</p>")
        page_reset.reset_mock()

        page.delete()

        page_reset.assert_called_once_with("/oferta")

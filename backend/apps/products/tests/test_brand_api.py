"""
Tests for Featured Brands API Endpoint (Story 33.2)

Tests cover:
- AC-1: GET /api/v1/brands/featured/ returns only is_featured=True brands
- AC-1: Response fields: id, name, slug, image, website
- AC-1: List ordered by name
- AC-2: Response is cached for 1 hour with invalidation on Brand changes
- AC-3: Response returns flat JSON list (no pagination wrapper)
- AC-3: image field uses cache-safe URL format (relative path without host dependency)
- Anonymous user access (no auth required)
"""

import struct
import zlib
from typing import Any, cast

import pytest
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test.utils import override_settings
from rest_framework.test import APIClient

from apps.products.constants import FEATURED_BRANDS_CACHE_KEY, FEATURED_BRANDS_CACHE_TIMEOUT, FEATURED_BRANDS_MAX_ITEMS
from apps.products.models import Brand


def _make_png():
    """Create a minimal valid 1x1 PNG image."""
    signature = b"\x89PNG\r\n\x1a\n"

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw_data = b"\x00\xff\x00\x00"
    compressed = zlib.compress(raw_data)
    return signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")


def _make_image(name="test.png"):
    return SimpleUploadedFile(name, _make_png(), content_type="image/png")


FEATURED_URL = "/api/v1/brands/featured/"


@pytest.mark.django_db
class TestFeaturedBrandsEndpoint:
    """Test GET /api/v1/brands/featured/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup_brands(self):
        cache.clear()
        self.client = cast(Any, APIClient())
        self.featured1 = Brand(
            name="Adidas", is_featured=True, image=_make_image("a.png"), website="https://adidas.com"
        )
        self.featured1.save()
        self.featured2 = Brand(name="Nike", is_featured=True, image=_make_image("n.png"), website="https://nike.com")
        self.featured2.save()
        self.regular = Brand(name="Puma", is_featured=False)
        self.regular.save()
        self.inactive = Brand(name="Reebok", is_featured=True, is_active=False, image=_make_image("r.png"))
        self.inactive.save()

    def test_status_200_anonymous(self):
        """AC-1: Anonymous users get 200."""
        response = self.client.get(FEATURED_URL)
        assert response.status_code == 200

    def test_returns_flat_json_list(self):
        """AC-3: Response is a flat JSON list, not paginated wrapper."""
        response = self.client.get(FEATURED_URL)
        assert isinstance(response.data, list)

    def test_returns_only_featured(self):
        """AC-1: Only is_featured=True brands returned."""
        response = self.client.get(FEATURED_URL)
        names = [b["name"] for b in response.data]
        assert "Adidas" in names
        assert "Nike" in names
        assert "Puma" not in names

    def test_excludes_inactive_brands(self):
        """Featured but inactive brands are excluded."""
        response = self.client.get(FEATURED_URL)
        names = [b["name"] for b in response.data]
        assert "Reebok" not in names

    def test_ordered_by_name(self):
        """AC-1: Results ordered by name."""
        response = self.client.get(FEATURED_URL)
        names = [b["name"] for b in response.data]
        assert names == sorted(names)

    def test_response_fields(self):
        """AC-1, AC-3: Response contains required fields in snake_case."""
        response = self.client.get(FEATURED_URL)
        brand_data = response.data[0]
        required_fields = {"id", "name", "slug", "image", "website"}
        assert required_fields.issubset(set(brand_data.keys()))

    def test_image_field_is_relative_url_for_cache_safety(self):
        """AC-3: image field в featured endpoint не зависит от request host."""
        response = self.client.get(FEATURED_URL)
        for brand_data in response.data:
            assert brand_data["image"], f"image empty for {brand_data['name']}"
            assert brand_data["image"].startswith("/"), f"Expected relative URL, got {brand_data['image']}"
            assert not brand_data["image"].startswith("http"), f"Expected non-absolute URL, got {brand_data['image']}"

    @override_settings(ALLOWED_HOSTS=["testserver", "internal.local", "public.example.com"])
    def test_cached_payload_not_host_dependent(self):
        """[AI-Review] Cache payload не должен фиксировать Host из заголовка запроса."""
        response_internal = self.client.get(FEATURED_URL, HTTP_HOST="internal.local:8000")
        assert response_internal.status_code == 200

        response_public = self.client.get(FEATURED_URL, HTTP_HOST="public.example.com")
        assert response_public.status_code == 200
        assert response_internal.data == response_public.data

        for brand_data in response_public.data:
            assert "internal.local" not in brand_data["image"]
            assert "public.example.com" not in brand_data["image"]

    def test_empty_when_no_featured(self):
        """Returns empty list when no featured brands exist."""
        cache.clear()
        Brand.objects.all().delete()
        Brand(name="OnlyRegular", is_featured=False).save()
        response = self.client.get(FEATURED_URL)
        assert response.status_code == 200
        assert response.data == []

    def test_no_pagination_keys(self):
        """Response does NOT contain pagination keys (count, next, previous, results)."""
        response = self.client.get(FEATURED_URL)
        assert isinstance(response.data, list)

    def test_featured_results_are_limited(self):
        """[AI-Review] Safety limit защищает endpoint от неограниченной выдачи."""
        for idx in range(FEATURED_BRANDS_MAX_ITEMS + 10):
            Brand(
                name=f"LimitBrand-{idx:03d}",
                is_featured=True,
                image=_make_image(f"limit-{idx}.png"),
            ).save()

        response = self.client.get(FEATURED_URL)
        assert response.status_code == 200
        assert len(response.data) == FEATURED_BRANDS_MAX_ITEMS

    def test_featured_ignores_search_param(self):
        """[AI-Review] Featured endpoint ignores search param to protect cache key."""
        cache.clear()
        # Request with search param that would filter result if applied
        # We search for "Adidas" but expect ALL featured brands because search is ignored
        response = self.client.get(FEATURED_URL, {"search": "adi"})
        assert response.status_code == 200
        names = [b["name"] for b in response.data]
        assert "Adidas" in names
        assert "Nike" in names


LOCMEM_CACHE = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}


@pytest.mark.django_db(transaction=True)
class TestFeaturedBrandsCaching:
    """Test caching behavior for featured brands endpoint (AC-2).

    Uses transaction=True so that transaction.on_commit callbacks
    (used in signal-based cache invalidation) actually fire.
    """

    @pytest.fixture(autouse=True)
    def setup(self):
        cache.clear()
        self.client = cast(Any, APIClient())
        self.brand = Brand(name="CachedBrand", is_featured=True, image=_make_image())
        self.brand.save()
        cache.clear()  # clear again after on_commit fires from save

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_cached_response_same_content(self):
        """AC-2: Second request returns cached content from manual cache."""
        cache.clear()
        response1 = self.client.get(FEATURED_URL)
        response2 = self.client.get(FEATURED_URL)
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response1.data == response2.data

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_cache_key_set_after_request(self):
        """AC-2: Cache key is populated after first request."""
        cache.clear()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is None
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_cache_invalidated_on_brand_save(self):
        """AC-2: Cache is cleared when a Brand is saved (via transaction.on_commit)."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        # Save a brand — signal fires on_commit which invalidates cache
        self.brand.name = "UpdatedBrand"
        self.brand.save()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_cache_invalidated_on_brand_delete(self):
        """AC-2: Cache is cleared when a Brand is deleted (via transaction.on_commit)."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        self.brand.delete()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_new_brand_visible_after_invalidation(self):
        """AC-2: New featured brand appears after cache invalidation."""
        cache.clear()
        response1 = self.client.get(FEATURED_URL)
        names1 = [b["name"] for b in response1.data]
        # Create new featured brand — triggers invalidation via on_commit
        new_brand = Brand(name="NewFeatured", is_featured=True, image=_make_image("new.png"))
        new_brand.save()
        response2 = self.client.get(FEATURED_URL)
        names2 = [b["name"] for b in response2.data]
        assert "NewFeatured" in names2
        assert len(names2) == len(names1) + 1

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_bulk_update_does_not_invalidate_cache(self):
        """Документирует ограничение: QuerySet.update() не инвалидирует кэш."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        # bulk update обходит signals — on_commit не вызывается
        Brand.objects.filter(pk=self.brand.pk).update(name="BulkUpdated")
        # кэш НЕ инвалидирован — это известное ограничение
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_irrelevant_field_change_does_not_invalidate_cache(self):
        """[AI-Review] Изменение description не инвалидирует кэш featured brands."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        self.brand.description = "Updated description that should not bust cache"
        self.brand.save()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_relevant_field_change_invalidates_cache(self):
        """[AI-Review] Изменение is_featured инвалидирует кэш."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        self.brand.is_featured = False
        self.brand.save()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_name_change_invalidates_cache(self):
        """[AI-Review] Изменение name инвалидирует кэш (влияет на сортировку и отображение)."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        self.brand.name = "RenamedBrand"
        self.brand.save()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_non_featured_brand_create_does_not_invalidate_cache(self):
        """[AI-Review] Создание non-featured бренда не инвалидирует кэш."""
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        Brand(name="RegularNew", is_featured=False).save()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None

    @override_settings(CACHES=LOCMEM_CACHE)
    def test_non_featured_delete_does_not_invalidate_cache(self):
        """[AI-Review] Удаление non-featured бренда не инвалидирует кэш."""
        regular = Brand(name="RegularForDelete", is_featured=False)
        regular.save()
        cache.clear()
        self.client.get(FEATURED_URL)
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None
        regular.delete()
        assert cache.get(FEATURED_BRANDS_CACHE_KEY) is not None


@pytest.mark.django_db
class TestBrandSearch:
    """Test search capabilities on BrandViewSet."""

    @pytest.fixture(autouse=True)
    def setup_brands(self):
        self.client = cast(Any, APIClient())
        Brand(name="Adidas", is_featured=True, image=_make_image("a.png")).save()
        Brand(name="Nike", is_featured=False).save()
        Brand(name="Puma", is_featured=False).save()

    def test_search_by_name(self):
        """[AI-Review] SearchFilter позволяет искать бренды по name."""
        response = self.client.get("/api/v1/brands/", {"search": "adi"})
        assert response.status_code == 200
        names = [b["name"] for b in response.data["results"]]
        assert "Adidas" in names
        assert "Nike" not in names

    def test_search_returns_all_without_query(self):
        """Без параметра search возвращаются все бренды."""
        response = self.client.get("/api/v1/brands/")
        assert response.status_code == 200
        assert len(response.data["results"]) == 3


@pytest.mark.django_db
class TestFeaturedBrandSerializer:
    """Test that featured endpoint uses lightweight serializer without description."""

    @pytest.fixture(autouse=True)
    def setup(self):
        cache.clear()
        self.client = cast(Any, APIClient())
        Brand(
            name="TestBrand",
            is_featured=True,
            image=_make_image("t.png"),
            description="Long description text",
        ).save()

    def test_featured_response_excludes_description(self):
        """[AI-Review] Featured endpoint не включает поле description для оптимизации payload."""
        response = self.client.get(FEATURED_URL)
        assert response.status_code == 200
        assert len(response.data) == 1
        assert "description" not in response.data[0]

    def test_featured_response_includes_required_fields(self):
        """Featured endpoint возвращает все необходимые поля кроме description."""
        response = self.client.get(FEATURED_URL)
        brand_data = response.data[0]
        # is_featured excluded as redundant (implicit true)
        required_fields = {"id", "name", "slug", "image", "website"}
        assert required_fields.issubset(set(brand_data.keys()))
        assert "is_featured" not in brand_data

    def test_serializer_forces_relative_url(self):
        """[AI-Review] Serializer должен возвращать relative URL даже при наличии request в контексте."""
        from apps.products.serializers import BrandFeaturedSerializer

        request = cast(Any, self.client.get("/"))  # Mock request
        # Manually force request with build_absolute_uri capability into context
        brand = Brand.objects.first()
        serializer = BrandFeaturedSerializer(brand, context={"request": request})
        image_url = serializer.data["image"]

        assert image_url.startswith("/")
        assert not image_url.startswith("http")


class TestFeaturedBrandsConstants:
    """Test that constants are properly defined and importable."""

    def test_cache_key_is_string(self):
        assert isinstance(FEATURED_BRANDS_CACHE_KEY, str)
        assert FEATURED_BRANDS_CACHE_KEY == "products:brands:featured:v1"

    def test_cache_timeout_is_one_hour(self):
        assert FEATURED_BRANDS_CACHE_TIMEOUT == 3600

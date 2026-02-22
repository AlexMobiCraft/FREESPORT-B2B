"""
Tests for Brand model updates (Story 33.1)

Tests cover:
- New fields existence (image, is_featured)
- clean() validation logic (featured requires image)
- is_featured default value
- __str__ method
- BrandViewSet is_featured filtering (review follow-up)
- BrandAdmin image_preview (review follow-up)
- Brand.slug uniqueness and collision handling (review follow-up)
- Brand.clean() normalized_name duplicate validation (review follow-up)
"""

import pytest
from typing import Any, cast
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.products.admin import BrandAdmin
from apps.products.models import Brand


@pytest.mark.django_db
class TestBrandModelFields:
    """Test Brand model field existence and configuration."""

    def test_image_field_exists(self):
        """AC-1: Brand model includes an image field (ImageField)."""
        field = Brand._meta.get_field("image")
        assert field is not None
        assert field.get_internal_type() == "FileField"  # ImageField extends FileField
        assert field.upload_to == "brands/"

    def test_is_featured_field_exists(self):
        """AC-1: Brand model includes an is_featured field (BooleanField)."""
        field = Brand._meta.get_field("is_featured")
        assert field is not None
        assert field.get_internal_type() == "BooleanField"

    def test_is_featured_default_false(self):
        """AC-1: is_featured defaults to False."""
        field = Brand._meta.get_field("is_featured")
        assert field.default is False

    def test_image_field_allows_blank(self):
        """Image field should allow blank (not required by default)."""
        field = Brand._meta.get_field("image")
        assert field.blank is True

    def test_str_returns_brand_name(self):
        """AC-1: __str__ still returns the brand name."""
        brand = Brand(name="TestBrand")
        assert str(brand) == "TestBrand"


@pytest.mark.django_db
class TestBrandCleanValidation:
    """Test Brand.clean() validation logic (AC-3)."""

    def _make_image(self):
        """Create a minimal valid image file for testing."""
        # 1x1 pixel red PNG
        import struct
        import zlib

        def create_png():
            signature = b"\x89PNG\r\n\x1a\n"

            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            raw_data = b"\x00\xff\x00\x00"
            compressed = zlib.compress(raw_data)

            return signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

        return SimpleUploadedFile("test.png", create_png(), content_type="image/png")

    def test_clean_featured_without_image_raises_error(self):
        """AC-3: is_featured=True without image raises ValidationError."""
        brand = Brand(name="TestBrand", is_featured=True)
        with pytest.raises(ValidationError) as exc_info:
            brand.clean()
        assert "image" in exc_info.value.message_dict
        assert "Image is required for featured brands" in str(exc_info.value.message_dict["image"])

    def test_clean_featured_with_image_passes(self):
        """AC-3: is_featured=True with image passes validation."""
        brand = Brand(name="TestBrand", is_featured=True, image=self._make_image())
        # Should not raise
        brand.clean()

    def test_clean_not_featured_without_image_passes(self):
        """is_featured=False without image passes validation."""
        brand = Brand(name="TestBrand", is_featured=False)
        # Should not raise
        brand.clean()

    def test_clean_not_featured_with_image_passes(self):
        """is_featured=False with image passes validation."""
        brand = Brand(name="TestBrand", is_featured=False, image=self._make_image())
        # Should not raise
        brand.clean()

    def test_featured_brand_saves_with_image(self):
        """Featured brand with image can be saved to DB."""
        brand = Brand(name="FeaturedBrand", is_featured=True, image=self._make_image())
        brand.clean()
        brand.save()
        assert brand.pk is not None
        assert brand.is_featured is True

    def test_non_featured_brand_saves_without_image(self):
        """Non-featured brand without image can be saved to DB."""
        brand = Brand(name="RegularBrand", is_featured=False)
        brand.clean()
        brand.save()
        assert brand.pk is not None
        assert brand.is_featured is False


@pytest.mark.django_db
class TestBrandViewSetIsFeaturedFilter:
    """Test BrandViewSet is_featured query parameter filtering (review follow-up)."""

    def _make_image(self):
        """Create a minimal valid image file for testing."""
        import struct
        import zlib

        def create_png():
            signature = b"\x89PNG\r\n\x1a\n"

            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            raw_data = b"\x00\xff\x00\x00"
            compressed = zlib.compress(raw_data)

            return signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

        return SimpleUploadedFile("test.png", create_png(), content_type="image/png")

    @pytest.fixture(autouse=True)
    def setup_brands(self):
        """Create test brands for filtering tests."""
        self.featured_brand = Brand(name="FeaturedBrand", is_featured=True, image=self._make_image())
        self.featured_brand.save()
        self.regular_brand = Brand(name="RegularBrand", is_featured=False)
        self.regular_brand.save()
        self.client = APIClient()

    def test_filter_featured_true(self):
        """is_featured=true returns only featured brands."""
        response = self.client.get("/api/v1/brands/", {"is_featured": "true"})
        assert response.status_code == 200
        names = [b["name"] for b in response.data["results"]]
        assert "FeaturedBrand" in names
        assert "RegularBrand" not in names

    def test_filter_featured_false(self):
        """is_featured=false returns only non-featured brands."""
        response = self.client.get("/api/v1/brands/", {"is_featured": "false"})
        assert response.status_code == 200
        names = [b["name"] for b in response.data["results"]]
        assert "RegularBrand" in names
        assert "FeaturedBrand" not in names

    def test_no_filter_returns_all(self):
        """No is_featured param returns all active brands."""
        response = self.client.get("/api/v1/brands/")
        assert response.status_code == 200
        names = [b["name"] for b in response.data["results"]]
        assert "FeaturedBrand" in names
        assert "RegularBrand" in names


@pytest.mark.django_db
class TestBrandAdminImagePreview:
    """Test BrandAdmin.image_preview method (review follow-up)."""

    def test_image_preview_with_image(self):
        """Brands with image show an img tag."""
        brand = Brand(name="WithImage", image="brands/test.png")
        brand_admin = BrandAdmin(Brand, AdminSite())
        result = brand_admin.image_preview(brand)
        assert "<img" in result
        assert "brands/test.png" in result

    def test_image_preview_without_image(self):
        """Brands without image show dash."""
        brand = Brand(name="NoImage")
        brand_admin = BrandAdmin(Brand, AdminSite())
        result = brand_admin.image_preview(brand)
        assert result == "-"


@pytest.mark.django_db
class TestBrandSerializerSlugGeneration:
    """Test that slug is generated by model.save(), not serializer.validate()."""

    def test_slug_generated_by_model_on_save(self):
        """Slug is auto-generated by Brand.save() when not provided."""
        brand = Brand(name="Test Slug Brand")
        brand.save()
        assert brand.slug  # slug is not empty
        assert brand.pk is not None

    def test_serializer_without_slug_delegates_to_model(self):
        """BrandSerializer without slug field relies on model for slug generation."""
        from apps.products.serializers import BrandSerializer

        data = {"name": "SerializerSlugTest"}
        serializer = BrandSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        # validated_data should NOT contain auto-generated slug (model handles it)
        assert "slug" not in serializer.validated_data or not serializer.validated_data.get("slug")


@pytest.mark.django_db
class TestBrandSlugUniqueness:
    """Test Brand.slug unique constraint and collision handling (review follow-up)."""

    def test_slug_field_is_unique(self):
        """Brand.slug field has unique=True."""
        field = Brand._meta.get_field("slug")
        assert field.unique is True

    def test_slug_collision_adds_suffix(self):
        """When auto-generated slug collides, a numeric suffix is appended."""
        # brand1 occupies slug "beta-brand" via explicit assignment
        brand1 = Brand(name="Alpha Brand", slug="beta-brand")
        brand1.save()

        # brand2 auto-generates slug "beta-brand" from name → collision
        brand2 = Brand(name="Beta Brand")
        brand2.save()

        assert brand1.slug == "beta-brand"
        assert brand2.slug == "beta-brand-1"

    def test_slug_collision_multiple_suffixes(self):
        """Multiple collisions produce incrementing suffixes."""
        Brand(name="Occupy Alpha", slug="gamma-brand").save()
        Brand(name="Occupy Beta", slug="gamma-brand-1").save()

        brand3 = Brand(name="Gamma Brand")
        brand3.save()
        assert brand3.slug == "gamma-brand-2"

    def test_multiple_brands_unique_slugs(self):
        """Multiple brands always get unique slugs."""
        names = ["AlphaOne", "BetaTwo", "GammaThree", "DeltaFour"]
        brands = []
        for name in names:
            b = Brand(name=name)
            b.save()
            brands.append(b)

        slugs = [b.slug for b in brands]
        assert len(slugs) == len(set(slugs)), f"Slugs not unique: {slugs}"

    def test_explicit_slug_preserved(self):
        """When slug is explicitly provided, it is not overwritten."""
        brand = Brand(name="Puma", slug="custom-puma-slug")
        brand.save()
        assert brand.slug == "custom-puma-slug"

    def test_cyrillic_slug_collision(self):
        """Cyrillic brand names with same transliteration get unique slugs."""
        brand1 = Brand(name="Найк Эйр", slug="najk-ejr")
        brand1.save()

        brand2 = Brand(name="Найк Про")
        brand2.save()
        # "najk-pro" should not collide with "najk-ejr"
        assert brand2.slug == "najk-pro"


@pytest.mark.django_db
class TestBrandNormalizedNameValidation:
    """Test Brand.clean() validates normalized_name uniqueness (review follow-up)."""

    def test_clean_raises_on_duplicate_normalized_name(self):
        """clean() raises ValidationError when normalized name collides."""
        Brand(name="BOYBO").save()

        brand2 = Brand(name="Boy Bo")  # normalizes to same "boybo"
        with pytest.raises(ValidationError) as exc_info:
            brand2.clean()
        assert "name" in exc_info.value.message_dict

    def test_clean_allows_unique_normalized_name(self):
        """clean() passes when normalized names are different."""
        Brand(name="Nike").save()
        brand2 = Brand(name="Adidas")
        # Should not raise
        brand2.clean()

    def test_clean_allows_editing_same_brand(self):
        """clean() does not flag the same brand as duplicate of itself."""
        brand = Brand(name="Puma")
        brand.save()
        # Editing the same brand should pass clean
        brand.name = "Puma"
        brand.clean()

    def test_clean_combined_featured_and_duplicate_name(self):
        """clean() reports both errors when featured without image AND duplicate name."""
        Brand(name="Nike").save()
        brand2 = Brand(name="Nike", is_featured=True)
        with pytest.raises(ValidationError) as exc_info:
            brand2.clean()
        errors = exc_info.value.message_dict
        assert "image" in errors
        assert "name" in errors


@pytest.mark.django_db
class TestBrandSerializerValidation:
    """Test BrandSerializer.validate() calls Brand.clean() (AI-Review HIGH fix)."""

    def _make_image(self):
        """Create a minimal valid image file for testing."""
        import struct
        import zlib

        def create_png():
            signature = b"\x89PNG\r\n\x1a\n"

            def chunk(chunk_type, data):
                c = chunk_type + data
                crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
                return struct.pack(">I", len(data)) + c + crc

            ihdr_data = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
            raw_data = b"\x00\xff\x00\x00"
            compressed = zlib.compress(raw_data)

            return signature + chunk(b"IHDR", ihdr_data) + chunk(b"IDAT", compressed) + chunk(b"IEND", b"")

        return SimpleUploadedFile("test.png", create_png(), content_type="image/png")

    def test_serializer_rejects_featured_without_image(self):
        """BrandSerializer raises validation error for is_featured=True without image."""
        from apps.products.serializers import BrandSerializer

        data = {"name": "FeaturedNoImg", "is_featured": True}
        serializer = BrandSerializer(data=data)
        assert not serializer.is_valid()
        assert "image" in serializer.errors

    def test_serializer_rejects_duplicate_normalized_name(self):
        """BrandSerializer raises validation error for duplicate normalized name."""
        from apps.products.serializers import BrandSerializer

        Brand(name="Adidas").save()
        data = {"name": "ADIDAS"}
        serializer = BrandSerializer(data=data)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_serializer_allows_valid_brand(self):
        """BrandSerializer passes for valid brand data."""
        from apps.products.serializers import BrandSerializer

        data = {"name": "NewUniqueBrand"}
        serializer = BrandSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

    def test_serializer_allows_edit_same_brand(self):
        """BrandSerializer allows editing brand without flagging duplicate."""
        from apps.products.serializers import BrandSerializer

        brand = Brand(name="EditableBrand")
        brand.save()
        data = {"name": "EditableBrand", "is_featured": False}
        serializer = BrandSerializer(instance=brand, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors


@pytest.mark.django_db
class TestBrandModelIndexes:
    """Test db_index settings on Brand fields (AI-Review MEDIUM fix)."""

    def test_is_featured_has_db_index(self):
        """Brand.is_featured has db_index=True."""
        field = Brand._meta.get_field("is_featured")
        assert cast(Any, field).db_index is True

    def test_is_active_has_db_index(self):
        """Brand.is_active has db_index=True."""
        field = Brand._meta.get_field("is_active")
        assert cast(Any, field).db_index is True


@pytest.mark.django_db
class TestBrandCustomManager:
    """Test Brand custom manager (AI-Review LOW fix)."""

    def test_active_returns_only_active_brands(self):
        """Brand.objects.active() returns only is_active=True brands."""
        Brand(name="ActiveBrand", is_active=True).save()
        Brand(name="InactiveBrand", is_active=False).save()
        active = Brand.objects.active()
        names = list(active.values_list("name", flat=True))
        assert "ActiveBrand" in names
        assert "InactiveBrand" not in names

    def test_active_is_queryset(self):
        """Brand.objects.active() returns a QuerySet."""
        from django.db.models import QuerySet

        assert isinstance(Brand.objects.active(), QuerySet)


@pytest.mark.django_db
class TestBrandAdminImagePreviewSize:
    """Test BrandAdmin.image_preview increased size (AI-Review LOW fix)."""

    def test_image_preview_size_50px(self):
        """Image preview uses max-height:50px."""
        brand = Brand(name="SizeBrand", image="brands/test.png")
        brand_admin = BrandAdmin(Brand, AdminSite())
        result = brand_admin.image_preview(brand)
        assert "max-height:50px" in result
        assert "max-width:100px" in result

"""
Тесты mobile_image функционала — Tech-Spec: Мобильные изображения для маркетинговых баннеров

Покрытие:
- AC1: API возвращает непустой mobile_image_url при загруженном mobile_image
- AC2: API возвращает "" при отсутствии mobile_image (никогда null)
- AC5: Admin поле и превью мобильного изображения
- Модель: поле mobile_image — blank=True, upload_to, help_text
- Сериализатор: mobile_image_url в fields и read_only_fields
- Фабрики: BannerFactory.mobile_image == "" (falsy), MarketingBannerWithMobileImageFactory — truthy
"""

import pytest
from django.utils.html import format_html

from apps.banners.admin import BannerAdmin
from apps.banners.factories import BannerFactory, MarketingBannerFactory, MarketingBannerWithMobileImageFactory
from apps.banners.models import Banner
from apps.banners.serializers import BannerSerializer

# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMobileImageModelField:
    """Тесты поля mobile_image на модели Banner."""

    def test_mobile_image_field_exists(self):
        """Поле mobile_image существует на модели."""
        field = Banner._meta.get_field("mobile_image")
        assert field is not None

    def test_mobile_image_field_blank(self):
        """mobile_image имеет blank=True (опциональное)."""
        field = Banner._meta.get_field("mobile_image")
        assert field.blank is True

    def test_mobile_image_field_upload_to(self):
        """mobile_image использует тот же upload_to что и image."""
        field = Banner._meta.get_field("mobile_image")
        assert field.upload_to == "promos/%Y/%m/"

    def test_mobile_image_field_help_text(self):
        """mobile_image содержит help_text с рекомендуемым размером."""
        field = Banner._meta.get_field("mobile_image")
        assert "1260×540" in field.help_text

    def test_create_banner_without_mobile_image(self):
        """Баннер создаётся без mobile_image — поле falsy."""
        banner = BannerFactory()
        assert not banner.mobile_image

    def test_create_banner_with_mobile_image(self):
        """Баннер создаётся с mobile_image — поле truthy."""
        banner = MarketingBannerWithMobileImageFactory(
            show_to_guests=True,
        )
        assert banner.mobile_image

    def test_mobile_image_field_position(self):
        """mobile_image расположено после image и перед image_alt."""
        field_names = [f.name for f in Banner._meta.get_fields()]
        image_idx = field_names.index("image")
        mobile_idx = field_names.index("mobile_image")
        image_alt_idx = field_names.index("image_alt")
        assert image_idx < mobile_idx < image_alt_idx


# ---------------------------------------------------------------------------
# Serializer Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMobileImageUrlSerializer:
    """Тесты mobile_image_url в BannerSerializer."""

    def test_mobile_image_url_in_fields(self):
        """mobile_image_url присутствует в fields сериализатора."""
        assert "mobile_image_url" in BannerSerializer.Meta.fields

    def test_mobile_image_url_in_read_only_fields(self):
        """mobile_image_url помечено как read_only."""
        assert "mobile_image_url" in BannerSerializer.Meta.read_only_fields

    def test_mobile_image_url_empty_when_no_image(self):
        """AC2: mobile_image_url — пустая строка при отсутствии mobile_image."""
        banner = BannerFactory()
        serializer = BannerSerializer(banner)
        assert serializer.data["mobile_image_url"] == ""

    def test_mobile_image_url_is_string_not_none(self):
        """AC2: mobile_image_url никогда не None — всегда str."""
        banner = BannerFactory()
        serializer = BannerSerializer(banner)
        assert serializer.data["mobile_image_url"] is not None
        assert isinstance(serializer.data["mobile_image_url"], str)

    def test_mobile_image_url_non_empty_with_image(self):
        """AC1: mobile_image_url — непустая строка при наличии mobile_image."""
        banner = MarketingBannerWithMobileImageFactory(
            show_to_guests=True,
        )
        serializer = BannerSerializer(banner)
        url = serializer.data["mobile_image_url"]
        assert url != ""
        assert isinstance(url, str)

    def test_mobile_image_url_is_relative_path(self):
        """AC1: mobile_image_url — относительный путь /media/..."""
        banner = MarketingBannerWithMobileImageFactory(
            show_to_guests=True,
        )
        serializer = BannerSerializer(banner)
        url = serializer.data["mobile_image_url"]
        assert url.startswith("/")


# ---------------------------------------------------------------------------
# Factory Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMobileImageFactories:
    """Тесты фабрик с mobile_image."""

    def test_banner_factory_mobile_image_falsy(self):
        """BannerFactory: mobile_image по умолчанию falsy (пустая строка)."""
        banner = BannerFactory()
        assert not bool(banner.mobile_image)

    def test_marketing_factory_type(self):
        """MarketingBannerFactory: type == MARKETING."""
        banner = MarketingBannerFactory(show_to_guests=True)
        assert banner.type == Banner.BannerType.MARKETING

    def test_marketing_factory_has_image(self):
        """MarketingBannerFactory: image truthy (унаследовано от BannerFactory)."""
        banner = MarketingBannerFactory(show_to_guests=True)
        assert bool(banner.image)

    def test_marketing_with_mobile_factory_mobile_image_truthy(self):
        """MarketingBannerWithMobileImageFactory: mobile_image truthy."""
        banner = MarketingBannerWithMobileImageFactory(
            show_to_guests=True,
        )
        assert bool(banner.mobile_image)

    def test_marketing_with_mobile_factory_type(self):
        """MarketingBannerWithMobileImageFactory: type == MARKETING."""
        banner = MarketingBannerWithMobileImageFactory(
            show_to_guests=True,
        )
        assert banner.type == Banner.BannerType.MARKETING


# ---------------------------------------------------------------------------
# Admin Tests
# ---------------------------------------------------------------------------


class TestMobileImageAdmin:
    """Тесты Django Admin для mobile_image."""

    def test_mobile_image_in_fieldsets(self):
        """mobile_image присутствует в fieldsets BannerAdmin."""
        content_fieldset = BannerAdmin.fieldsets[0]
        fields = content_fieldset[1]["fields"]
        assert "mobile_image" in fields

    def test_mobile_image_preview_in_fieldsets(self):
        """mobile_image_preview присутствует в fieldsets."""
        content_fieldset = BannerAdmin.fieldsets[0]
        fields = content_fieldset[1]["fields"]
        assert "mobile_image_preview" in fields

    def test_mobile_image_preview_in_readonly_fields(self):
        """mobile_image_preview в readonly_fields."""
        assert "mobile_image_preview" in BannerAdmin.readonly_fields

    def test_mobile_image_after_image_preview_in_fieldsets(self):
        """mobile_image расположено после image_preview в fieldsets."""
        content_fieldset = BannerAdmin.fieldsets[0]
        fields = content_fieldset[1]["fields"]
        fields_list = list(fields)
        image_preview_idx = fields_list.index("image_preview")
        mobile_image_idx = fields_list.index("mobile_image")
        assert mobile_image_idx == image_preview_idx + 1


# ---------------------------------------------------------------------------
# Cache Invalidation Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestMobileImageCacheInvalidation:
    """Тест кеш-инвалидации при обновлении только mobile_image."""

    def test_update_only_mobile_image_invalidates_cache(self):
        """Обновление только mobile_image инвалидирует кеш (post_save срабатывает)."""
        from apps.banners.factories import generate_test_image

        banner = MarketingBannerFactory(show_to_guests=True)
        original_updated_at = banner.updated_at

        # Обновляем только mobile_image
        banner.mobile_image = generate_test_image()
        banner.save()
        banner.refresh_from_db()

        # updated_at должен измениться (auto_now=True)
        assert banner.updated_at > original_updated_at

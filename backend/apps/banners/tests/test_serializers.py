"""
Тесты BannerSerializer — Story 32.1 Review Follow-ups

Покрытие:
- 5-1: type field присутствует в сериализаторе
"""

import pytest

from apps.banners.factories import BannerFactory
from apps.banners.models import Banner
from apps.banners.serializers import BannerSerializer


@pytest.mark.django_db
class TestBannerSerializerTypeField:
    """5-1: type field exposed via BannerSerializer."""

    def test_type_field_in_serialized_data(self):
        """type присутствует в output сериализатора."""
        banner = BannerFactory(type=Banner.BannerType.HERO)
        serializer = BannerSerializer(banner)
        assert "type" in serializer.data

    def test_type_field_value_hero(self):
        """type == 'hero' для Hero баннера."""
        banner = BannerFactory(type=Banner.BannerType.HERO)
        serializer = BannerSerializer(banner)
        assert serializer.data["type"] == "hero"

    def test_type_field_value_marketing(self):
        """type == 'marketing' для Marketing баннера."""
        banner = BannerFactory(type=Banner.BannerType.MARKETING)
        serializer = BannerSerializer(banner)
        assert serializer.data["type"] == "marketing"

    def test_type_field_is_read_only(self):
        """type поле read-only в сериализаторе."""
        serializer = BannerSerializer()
        assert "type" in serializer.Meta.read_only_fields

    def test_all_fields_are_read_only(self):
        """Все поля сериализатора помечены read-only (fields == read_only_fields)."""
        serializer = BannerSerializer()
        assert set(serializer.Meta.fields) == set(serializer.Meta.read_only_fields)

    def test_read_only_fields_is_tuple(self):
        """read_only_fields — tuple (не list), отдельная декларация."""
        serializer = BannerSerializer()
        assert isinstance(serializer.Meta.read_only_fields, tuple)

    def test_type_field_ignored_on_input(self):
        """type поле игнорируется при подаче данных через serializer (read-only)."""
        banner = BannerFactory(type=Banner.BannerType.HERO)
        serializer = BannerSerializer(banner, data={"type": "marketing"}, partial=True)
        assert serializer.is_valid(), serializer.errors
        # type не должен измениться — поле read-only
        assert serializer.validated_data.get("type") is None

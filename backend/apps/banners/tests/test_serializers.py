"""
Тесты BannerSerializer — Story 32.1 Review Follow-ups

Покрытие:
- 5-1: type field присутствует в сериализаторе
"""

import pytest

from apps.banners.factories import AdvertisementBannerFactory, BannerFactory
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


@pytest.mark.django_db
class TestBannerSerializerAdvertisementFields:
    """Реквизиты рекламодателя доступны фронту тем же запросом /api/banners/."""

    AD_FIELDS = ("is_advertisement", "advertiser_name", "advertiser_inn", "erid")

    def test_advertisement_fields_present_in_output(self):
        """Все четыре поля маркировки присутствуют в ответе сериализатора."""
        banner = AdvertisementBannerFactory()
        data = BannerSerializer(banner).data
        for field in self.AD_FIELDS:
            assert field in data

    def test_advertisement_values_serialized(self):
        """Значения реквизитов отдаются как есть."""
        banner = AdvertisementBannerFactory(
            advertiser_name='ООО "Прайм Спорт Рус"',
            advertiser_inn="7718933790",
            erid="2VfnxwTestToken",
        )
        data = BannerSerializer(banner).data
        assert data["is_advertisement"] is True
        assert data["advertiser_name"] == 'ООО "Прайм Спорт Рус"'
        assert data["advertiser_inn"] == "7718933790"
        assert data["erid"] == "2VfnxwTestToken"

    def test_regular_banner_returns_empty_requisites(self):
        """Нерекламный баннер отдаёт False и пустые строки — фронт скрывает метку."""
        banner = BannerFactory()
        data = BannerSerializer(banner).data
        assert data["is_advertisement"] is False
        assert data["advertiser_name"] == ""
        assert data["advertiser_inn"] == ""
        assert data["erid"] == ""

    def test_advertisement_fields_ignored_on_input(self):
        """Поля маркировки не принимаются на запись: проверяем поведение, а не константу."""
        banner = AdvertisementBannerFactory()
        serializer = BannerSerializer(
            banner,
            data={"advertiser_inn": "0000000000", "erid": "hacked", "is_advertisement": False},
            partial=True,
        )
        assert serializer.is_valid(), serializer.errors
        for field in self.AD_FIELDS:
            assert serializer.validated_data.get(field) is None

    def test_requisites_suppressed_when_flag_disabled(self):
        """Реквизиты гасятся, если галочка снята, но данные остались в БД.

        ИНН ИП или физлица — персональные данные: в публичном ответе гостям их быть
        не должно, когда баннер уже не рекламный.
        """
        banner = AdvertisementBannerFactory()
        # Обходим full_clean: воспроизводим состояние «галочку сняли, реквизиты остались»
        Banner.objects.filter(pk=banner.pk).update(is_advertisement=False)
        banner.refresh_from_db()

        data = BannerSerializer(banner).data

        assert data["is_advertisement"] is False
        assert data["advertiser_name"] == ""
        assert data["advertiser_inn"] == ""
        assert data["erid"] == ""

    def test_requisites_present_while_flag_enabled(self):
        """При включённой маркировке реквизиты не гасятся."""
        banner = AdvertisementBannerFactory(advertiser_inn="7718933790")
        data = BannerSerializer(banner).data
        assert data["advertiser_inn"] == "7718933790"

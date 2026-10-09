"""
Тесты Admin-интерфейса Banner — Story 32.1

Покрытие:
- AC2: BannerAdmin list_filter по type
- AC2: Image обязательна для Marketing type
- AC2: target_url (cta_link) доступен в форме
"""

from typing import Any, cast

import pytest
from django.contrib.admin.sites import AdminSite
from django.core.exceptions import ValidationError
from django.test import RequestFactory

from apps.banners.admin import BannerAdmin
from apps.banners.factories import BannerFactory, generate_test_image
from apps.banners.models import Banner


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

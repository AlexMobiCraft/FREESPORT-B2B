"""
Тесты модели Banner — Story 32.1: Database and Admin Updates

Покрытие:
- AC1: type поле (HERO/MARKETING), null=False, default=HERO
- AC2: Admin-валидация (image обязательна для Marketing)
- AC3: Cache invalidation
- 9-2: Temporal unit tests — start_date/end_date с мокированным временем
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from apps.banners.factories import BannerFactory, generate_test_image
from apps.banners.models import Banner, is_safe_internal_cta_link


@pytest.mark.unit
class TestIsSafeInternalCtaLink:
    """Pure unit tests for is_safe_internal_cta_link — no DB required."""

    def test_blocks_backslash_in_path(self):
        """Обратный слеш в пути должен быть заблокирован."""
        assert is_safe_internal_cta_link("/catalog\\..\\admin") is False

    def test_blocks_unc_path(self):
        """UNC-путь (\\\\server\\share) должен быть заблокирован."""
        assert is_safe_internal_cta_link("\\\\server\\share") is False

    def test_allows_normal_internal_path(self):
        """Обычный внутренний путь должен быть разрешён."""
        assert is_safe_internal_cta_link("/catalog?sale=summer") is True

    def test_blocks_protocol_relative(self):
        """Protocol-relative URL должен быть заблокирован."""
        assert is_safe_internal_cta_link("//evil.com") is False

    def test_blocks_javascript_scheme(self):
        """javascript: протокол должен быть заблокирован."""
        assert is_safe_internal_cta_link("javascript:alert(1)") is False


@pytest.mark.integration
@pytest.mark.django_db
class TestBannerTypeField:
    """AC1: Banner model has a 'type' field with choices HERO and MARKETING."""

    def test_type_field_exists(self):
        """type поле существует на модели."""
        banner = BannerFactory()
        assert hasattr(banner, "type")

    def test_type_choices_hero(self):
        """BannerType.HERO === 'hero'."""
        assert Banner.BannerType.HERO.value == "hero"

    def test_type_choices_marketing(self):
        """BannerType.MARKETING === 'marketing'."""
        assert Banner.BannerType.MARKETING.value == "marketing"

    def test_type_choices_labels(self):
        """Choices содержат корректные label."""
        choices_dict = dict(Banner.BannerType.choices)
        assert "hero" in choices_dict
        assert "marketing" in choices_dict

    def test_default_type_is_hero(self):
        """Новый баннер создаётся с type=HERO по умолчанию."""
        banner = BannerFactory()
        assert banner.type == Banner.BannerType.HERO

    def test_create_marketing_banner(self):
        """Можно создать баннер с type=MARKETING."""
        banner = BannerFactory(type=Banner.BannerType.MARKETING)
        assert banner.type == Banner.BannerType.MARKETING

    def test_type_field_not_nullable(self):
        """AC1: type поле non-nullable (null=False) на уровне БД."""
        field = Banner._meta.get_field("type")
        assert field.null is False

    def test_type_field_not_blank(self):
        """type поле не может быть пустым."""
        field = Banner._meta.get_field("type")
        assert field.blank is False

    def test_image_field_optional(self):
        """image поле имеет blank=True (AC: optional for Hero)."""
        field = Banner._meta.get_field("image")
        assert field.blank is True

    def test_cta_text_field_optional(self):
        """cta_text поле имеет blank=True."""
        field = Banner._meta.get_field("cta_text")
        assert field.blank is True

    def test_type_field_max_length(self):
        """type поле max_length=20."""
        field = Banner._meta.get_field("type")
        assert field.max_length == 20

    def test_type_persists_after_save(self):
        """type сохраняется и загружается из БД корректно."""
        banner = BannerFactory(type=Banner.BannerType.MARKETING)
        banner_from_db = Banner.objects.get(pk=banner.pk)
        assert banner_from_db.type == Banner.BannerType.MARKETING

    def test_existing_banners_have_hero_type(self):
        """Дефолтное значение type=HERO для новых записей."""
        banner = BannerFactory()
        banner.refresh_from_db()
        assert banner.type == Banner.BannerType.HERO


@pytest.mark.integration
@pytest.mark.django_db
class TestBannerSaveCallsFullClean:
    """5-4: save() вызывает full_clean() для валидации на уровне модели."""

    def test_save_marketing_without_image_raises_error(self):
        """save() Marketing баннера без image должен вызвать ValidationError."""
        banner = Banner(
            title="Test Marketing",
            subtitle="Test",
            cta_link="/test",
            type=Banner.BannerType.MARKETING,
        )
        with pytest.raises(ValidationError) as exc_info:
            banner.save()
        assert "image" in exc_info.value.message_dict

    def test_save_hero_without_image_succeeds(self):
        """save() Hero баннера без image проходит (image optional для Hero)."""
        banner = Banner(
            title="Test Hero",
            subtitle="Test",
            cta_link="/test",
            type=Banner.BannerType.HERO,
        )
        banner.save()
        assert banner.pk is not None

    @pytest.mark.parametrize(
        "unsafe_cta_link",
        [
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:MsgBox(1)",
            "https://evil.com/phishing",
            "//evil.com/phishing",
            "catalog/no-leading-slash",
            "   ",
            "/catalog\\..\\admin",
            "\\\\server\\share",
        ],
    )
    def test_save_with_unsafe_cta_link_raises_error(self, unsafe_cta_link):
        """save() должен блокировать небезопасные и внешние cta_link."""
        banner = Banner(
            title="Unsafe CTA",
            subtitle="Test",
            cta_link=unsafe_cta_link,
            type=Banner.BannerType.HERO,
        )

        with pytest.raises(ValidationError) as exc_info:
            banner.save()

        assert "cta_link" in exc_info.value.message_dict

    def test_save_trims_safe_internal_cta_link(self):
        """safe cta_link с пробелами нормализуется через trim перед сохранением."""
        banner = Banner(
            title="Trim CTA",
            subtitle="Test",
            cta_link="   /catalog?sale=summer   ",
            type=Banner.BannerType.HERO,
        )

        banner.save()
        banner.refresh_from_db()

        assert banner.cta_link == "/catalog?sale=summer"

    def test_save_marketing_with_image_succeeds(self):
        """save() Marketing баннера с image проходит."""
        banner = Banner(
            title="Test Marketing OK",
            subtitle="Test",
            cta_link="/test",
            type=Banner.BannerType.MARKETING,
            image=generate_test_image(),
        )
        banner.save()
        assert banner.pk is not None


@pytest.mark.integration
@pytest.mark.django_db
class TestIsScheduledActive:
    """9-2: is_scheduled_active учитывает start_date/end_date с мокированным временем."""

    def test_active_no_dates(self):
        """Активный баннер без дат — is_scheduled_active=True."""
        banner = BannerFactory(is_active=True, start_date=None, end_date=None)
        assert banner.is_scheduled_active is True

    def test_inactive_banner(self):
        """Неактивный баннер — is_scheduled_active=False."""
        banner = BannerFactory(is_active=False, start_date=None, end_date=None)
        assert banner.is_scheduled_active is False

    def test_before_start_date(self):
        """Баннер до start_date — is_scheduled_active=False."""
        now = timezone.now()
        future = now + timedelta(hours=1)
        banner = BannerFactory(is_active=True, start_date=future, end_date=None)
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is False

    def test_after_start_date(self):
        """Баннер после start_date — is_scheduled_active=True."""
        now = timezone.now()
        past = now - timedelta(hours=1)
        banner = BannerFactory(is_active=True, start_date=past, end_date=None)
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is True

    def test_after_end_date(self):
        """Баннер после end_date — is_scheduled_active=False."""
        now = timezone.now()
        past_end = now - timedelta(hours=1)
        banner = BannerFactory(is_active=True, start_date=None, end_date=past_end)
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is False

    def test_before_end_date(self):
        """Баннер до end_date — is_scheduled_active=True."""
        now = timezone.now()
        future_end = now + timedelta(hours=1)
        banner = BannerFactory(is_active=True, start_date=None, end_date=future_end)
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is True

    def test_within_date_range(self):
        """Баннер в пределах start_date..end_date — is_scheduled_active=True."""
        now = timezone.now()
        banner = BannerFactory(
            is_active=True,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is True

    def test_outside_date_range(self):
        """Баннер вне диапазона (now после end_date) — is_scheduled_active=False."""
        now = timezone.now()
        banner = BannerFactory(
            is_active=True,
            start_date=now - timedelta(days=10),
            end_date=now - timedelta(days=1),
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            assert banner.is_scheduled_active is False


@pytest.mark.integration
@pytest.mark.django_db
class TestGetForUserTemporalFiltering:
    """9-2: get_for_user корректно фильтрует по start_date/end_date."""

    def test_excludes_future_banners(self):
        """Баннер с start_date в будущем — не в queryset."""
        now = timezone.now()
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            start_date=now + timedelta(hours=1),
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            qs = Banner.get_for_user(None)
            assert qs.count() == 0

    def test_excludes_expired_banners(self):
        """Баннер с end_date в прошлом — не в queryset."""
        now = timezone.now()
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            end_date=now - timedelta(hours=1),
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            qs = Banner.get_for_user(None)
            assert qs.count() == 0

    def test_includes_active_within_range(self):
        """Баннер в пределах дат — в queryset."""
        now = timezone.now()
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            qs = Banner.get_for_user(None)
            assert qs.count() == 1

    def test_includes_banners_without_dates(self):
        """Баннер без дат — всегда в queryset (если активен)."""
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            start_date=None,
            end_date=None,
        )
        qs = Banner.get_for_user(None)
        assert qs.count() == 1

    def test_transition_at_end_date_boundary(self):
        """Баннер с end_date ровно сейчас — ещё в queryset (end_date__gte=now)."""
        now = timezone.now()
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            end_date=now,
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            qs = Banner.get_for_user(None)
            assert qs.count() == 1

    def test_transition_at_start_date_boundary(self):
        """Баннер с start_date ровно сейчас — в queryset (start_date__lte=now)."""
        now = timezone.now()
        BannerFactory(
            is_active=True,
            show_to_guests=True,
            start_date=now,
        )
        with patch("apps.banners.models.timezone.now", return_value=now):
            qs = Banner.get_for_user(None)
            assert qs.count() == 1

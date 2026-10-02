"""
Unit тесты для модели Banner

Story 17.1: Backend модели и Admin для баннеров
"""

from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from apps.banners.factories import (
    ActiveAuthenticatedBannerFactory,
    ActiveFederationBannerFactory,
    ActiveGuestBannerFactory,
    ActiveTrainerBannerFactory,
    ActiveWholesaleBannerFactory,
    BannerFactory,
    ExpiredBannerFactory,
    FutureBannerFactory,
    InactiveBannerFactory,
    ScheduledBannerFactory,
)
from apps.banners.models import Banner
from tests.factories import UserFactory


@pytest.mark.unit
@pytest.mark.django_db
class TestBannerModel(TestCase):
    """Unit-тесты модели Banner"""

    def test_banner_str_representation(self):
        """
        AC7: Тест строкового представления баннера

        Given: Создан баннер с title и priority
        When: Вызывается __str__()
        Then: Возвращается строка в формате "title (priority: N)"
        """
        banner = BannerFactory(title="Тестовый баннер", priority=5)

        assert str(banner) == "Тестовый баннер (priority: 5)"

    def test_banner_ordering_by_priority_and_created_at(self):
        """
        AC7: Тест сортировки баннеров по приоритету и дате создания

        Given: Созданы баннеры с разными приоритетами
        When: Запрашивается queryset без сортировки
        Then: Баннеры отсортированы по убыванию priority, затем по убыванию created_at
        """
        banner1 = BannerFactory(priority=1)
        banner2 = BannerFactory(priority=3)
        banner3 = BannerFactory(priority=2)

        banners = Banner.objects.all()

        assert list(banners) == [banner2, banner3, banner1]
        assert banners[0].priority == 3
        assert banners[1].priority == 2
        assert banners[2].priority == 1

    def test_is_scheduled_active_property(self):
        """
        AC7: Тест property is_scheduled_active для активного баннера в диапазоне дат

        Given: Создан активный баннер с датами start_date и end_date
        When: Текущее время находится между start_date и end_date
        Then: is_scheduled_active возвращает True
        """
        banner = ScheduledBannerFactory()

        assert banner.is_scheduled_active is True

    def test_is_scheduled_active_returns_false_for_inactive_banner(self):
        """
        AC7: Тест is_scheduled_active для неактивного баннера

        Given: Создан неактивный баннер (is_active=False)
        When: Проверяется is_scheduled_active
        Then: Возвращается False
        """
        banner = InactiveBannerFactory()

        assert banner.is_scheduled_active is False

    def test_is_scheduled_active_returns_false_for_future_banner(self):
        """
        AC7: Тест is_scheduled_active для будущего баннера

        Given: Создан баннер с start_date в будущем
        When: Проверяется is_scheduled_active
        Then: Возвращается False
        """
        banner = FutureBannerFactory()

        assert banner.is_scheduled_active is False

    def test_is_scheduled_active_returns_false_for_expired_banner(self):
        """
        AC7: Тест is_scheduled_active для просроченного баннера

        Given: Создан баннер с end_date в прошлом
        When: Проверяется is_scheduled_active
        Then: Возвращается False
        """
        banner = ExpiredBannerFactory()

        assert banner.is_scheduled_active is False

    def test_get_for_user_returns_guest_banners_for_anonymous(self):
        """
        AC7: Тест get_for_user для анонимного пользователя

        Given: Созданы баннеры для гостей и авторизованных пользователей
        When: Вызывается Banner.get_for_user(user=None)
        Then: Возвращаются только баннеры с show_to_guests=True
        """
        guest_banner = ActiveGuestBannerFactory()
        auth_banner = ActiveAuthenticatedBannerFactory()

        banners = Banner.get_for_user(user=None)

        assert banners.count() == 1
        assert guest_banner in banners
        assert auth_banner not in banners

    def test_get_for_user_returns_authenticated_banners_for_logged_in_user(self):
        """
        AC7: Тест get_for_user для авторизованного пользователя (retail)

        Given: Созданы баннеры для гостей и авторизованных пользователей
        When: Вызывается Banner.get_for_user() с авторизованным пользователем
        Then: Возвращаются только баннеры с show_to_authenticated=True
        """
        guest_banner = ActiveGuestBannerFactory()
        auth_banner = ActiveAuthenticatedBannerFactory()
        retail_user = UserFactory(role="retail")

        banners = Banner.get_for_user(user=retail_user)

        assert banners.count() == 1
        assert auth_banner in banners
        assert guest_banner not in banners

    def test_get_for_user_returns_wholesale_banners_for_wholesale_user(self):
        """
        AC7: Тест get_for_user для оптового покупателя

        Given: Созданы баннеры для оптовиков и других групп
        When: Вызывается Banner.get_for_user()
              с пользователем роли wholesale_level1
        Then: Возвращаются баннеры с show_to_wholesale=True
              или show_to_authenticated=True
        """
        wholesale_banner = ActiveWholesaleBannerFactory()
        auth_banner = ActiveAuthenticatedBannerFactory()
        trainer_banner = ActiveTrainerBannerFactory()
        wholesale_user = UserFactory(role="wholesale_level1")

        banners = Banner.get_for_user(user=wholesale_user)

        assert banners.count() == 2
        assert wholesale_banner in banners
        assert auth_banner in banners
        assert trainer_banner not in banners

    def test_get_for_user_returns_trainer_banners_for_trainer(self):
        """
        AC7: Тест get_for_user для тренера

        Given: Созданы баннеры для тренеров и других групп
        When: Вызывается Banner.get_for_user() с пользователем роли trainer
        Then: Возвращаются баннеры с show_to_trainers=True
              или show_to_authenticated=True
        """
        trainer_banner = ActiveTrainerBannerFactory()
        auth_banner = ActiveAuthenticatedBannerFactory()
        wholesale_banner = ActiveWholesaleBannerFactory()
        trainer_user = UserFactory(role="trainer")

        banners = Banner.get_for_user(user=trainer_user)

        assert banners.count() == 2
        assert trainer_banner in banners
        assert auth_banner in banners
        assert wholesale_banner not in banners

    def test_get_for_user_returns_federation_banners_for_federation_rep(self):
        """
        AC7: Тест get_for_user для представителя федерации

        Given: Созданы баннеры для федераций и других групп
        When: Вызывается Banner.get_for_user()
              с пользователем роли federation_rep
        Then: Возвращаются баннеры с show_to_federation=True
              или show_to_authenticated=True
        """
        federation_banner = ActiveFederationBannerFactory()
        auth_banner = ActiveAuthenticatedBannerFactory()
        trainer_banner = ActiveTrainerBannerFactory()
        federation_user = UserFactory(role="federation_rep")

        banners = Banner.get_for_user(user=federation_user)

        assert banners.count() == 2
        assert federation_banner in banners
        assert auth_banner in banners
        assert trainer_banner not in banners

    def test_get_for_user_excludes_inactive_banners(self):
        """
        AC7: Тест get_for_user исключает неактивные баннеры

        Given: Созданы активные и неактивные баннеры
        When: Вызывается Banner.get_for_user()
        Then: Возвращаются только активные баннеры
        """
        active_banner = ActiveGuestBannerFactory()
        inactive_banner = InactiveBannerFactory()

        banners = Banner.get_for_user(user=None)

        assert banners.count() == 1
        assert active_banner in banners
        assert inactive_banner not in banners

    def test_get_for_user_excludes_expired_banners(self):
        """
        AC7: Тест get_for_user исключает просроченные баннеры

        Given: Созданы активные, просроченные и будущие баннеры
        When: Вызывается Banner.get_for_user()
        Then: Возвращаются только баннеры в текущем временном диапазоне
        """
        active_banner = ActiveGuestBannerFactory()
        expired_banner = ExpiredBannerFactory(show_to_guests=True)
        future_banner = FutureBannerFactory(show_to_guests=True)

        banners = Banner.get_for_user(user=None)

        assert banners.count() == 1
        assert active_banner in banners
        assert expired_banner not in banners
        assert future_banner not in banners

"""
Integration-тесты для API баннеров

Тестирует эндпоинт /api/banners/ с различными ролями пользователей
и различными состояниями баннеров (активные, неактивные, истёкшие, будущие)
"""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

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
)
from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestBannersAPI:
    """Integration-тесты API баннеров"""

    def setup_method(self) -> None:
        """Настройка тестового окружения перед каждым тестом"""
        self.client = APIClient()
        self.url = reverse("banners:banner-list")

    def test_guest_gets_guest_banners(self) -> None:
        """Гость получает только баннеры с show_to_guests=True"""
        # Arrange
        guest_banner = ActiveGuestBannerFactory(title="Guest Banner")
        auth_banner = ActiveAuthenticatedBannerFactory(title="Auth Banner")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert guest_banner.title in titles
        assert auth_banner.title not in titles

    def test_retail_user_gets_authenticated_banners(self) -> None:
        """B2C пользователь (retail) получает баннеры с show_to_authenticated=True"""
        # Arrange
        user = UserFactory(role="retail")
        self.client.force_authenticate(user=user)

        auth_banner = ActiveAuthenticatedBannerFactory(title="Retail Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert auth_banner.title in titles
        assert guest_banner.title not in titles

    def test_wholesale_level1_user_gets_wholesale_banners(self) -> None:
        """Оптовик уровня 1 получает баннеры с show_to_wholesale=True"""
        # Arrange
        user = UserFactory(role="wholesale_level1")
        self.client.force_authenticate(user=user)

        wholesale_banner = ActiveWholesaleBannerFactory(title="Wholesale Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert wholesale_banner.title in titles
        assert guest_banner.title not in titles

    def test_wholesale_level2_user_gets_wholesale_banners(self) -> None:
        """Оптовик уровня 2 получает баннеры с show_to_wholesale=True"""
        # Arrange
        user = UserFactory(role="wholesale_level2")
        self.client.force_authenticate(user=user)

        wholesale_banner = ActiveWholesaleBannerFactory(title="Wholesale L2 Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert wholesale_banner.title in titles
        assert guest_banner.title not in titles

    def test_wholesale_level3_user_gets_wholesale_banners(self) -> None:
        """Оптовик уровня 3 получает баннеры с show_to_wholesale=True"""
        # Arrange
        user = UserFactory(role="wholesale_level3")
        self.client.force_authenticate(user=user)

        wholesale_banner = ActiveWholesaleBannerFactory(title="Wholesale L3 Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert wholesale_banner.title in titles
        assert guest_banner.title not in titles

    def test_trainer_gets_trainer_banners(self) -> None:
        """Тренер получает баннеры с show_to_trainers=True"""
        # Arrange
        user = UserFactory(role="trainer")
        self.client.force_authenticate(user=user)

        trainer_banner = ActiveTrainerBannerFactory(title="Trainer Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert trainer_banner.title in titles
        assert guest_banner.title not in titles

    def test_federation_gets_federation_banners(self) -> None:
        """Представитель федерации получает баннеры с show_to_federation=True"""
        # Arrange
        user = UserFactory(role="federation_rep")
        self.client.force_authenticate(user=user)

        federation_banner = ActiveFederationBannerFactory(title="Federation Banner")
        guest_banner = ActiveGuestBannerFactory(title="Guest Only")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert federation_banner.title in titles
        assert guest_banner.title not in titles

    def test_inactive_banners_excluded(self) -> None:
        """Неактивные баннеры не возвращаются"""
        # Arrange
        active_banner = ActiveGuestBannerFactory(title="Active Banner")
        inactive_banner = InactiveBannerFactory(title="Inactive Banner")

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert active_banner.title in titles
        assert inactive_banner.title not in titles

    def test_expired_banners_excluded(self) -> None:
        """Истёкшие баннеры не возвращаются"""
        # Arrange
        active_banner = ActiveGuestBannerFactory(title="Active Banner")
        expired_banner = ExpiredBannerFactory(title="Expired Banner", show_to_guests=True)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert active_banner.title in titles
        assert expired_banner.title not in titles

    def test_future_start_date_excluded(self) -> None:
        """Баннеры с start_date в будущем не возвращаются"""
        # Arrange
        active_banner = ActiveGuestBannerFactory(title="Active Now")
        future_banner = FutureBannerFactory(title="Future Banner", show_to_guests=True)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]
        assert active_banner.title in titles
        assert future_banner.title not in titles

    def test_banners_sorted_by_priority(self) -> None:
        """Баннеры возвращаются отсортированными по приоритету (DESC)"""
        # Arrange
        banner_low = ActiveGuestBannerFactory(title="Low Priority", priority=10)
        banner_high = ActiveGuestBannerFactory(title="High Priority", priority=100)
        banner_mid = ActiveGuestBannerFactory(title="Mid Priority", priority=50)

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        titles = [b["title"] for b in data]

        # Проверяем, что баннеры отсортированы по приоритету (DESC)
        high_index = titles.index(banner_high.title)
        mid_index = titles.index(banner_mid.title)
        low_index = titles.index(banner_low.title)

        assert high_index < mid_index < low_index, "Баннеры должны быть отсортированы по приоритету в порядке убывания"

    def test_response_contains_required_fields(self) -> None:
        """Ответ API содержит все обязательные поля"""
        # Arrange
        banner = ActiveGuestBannerFactory(
            title="Test Banner",
            subtitle="Test Subtitle",
            image_alt="Test Alt",
            cta_text="Click Me",
            cta_link="/test-link",
        )

        # Act
        response = self.client.get(self.url)

        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data) == 1

        banner_data = data[0]
        assert "id" in banner_data
        assert "title" in banner_data
        assert "subtitle" in banner_data
        assert "image_url" in banner_data
        assert "image_alt" in banner_data
        assert "cta_text" in banner_data
        assert "cta_link" in banner_data

        assert banner_data["title"] == banner.title
        assert banner_data["subtitle"] == banner.subtitle
        assert banner_data["image_alt"] == banner.image_alt
        assert banner_data["cta_text"] == banner.cta_text
        assert banner_data["cta_link"] == banner.cta_link

    def test_multiple_role_flags_work(self) -> None:
        """Баннер с несколькими флагами таргетинга доступен всем
        соответствующим ролям"""
        # Arrange
        multi_role_banner = BannerFactory(
            title="Multi Role Banner",
            is_active=True,
            show_to_guests=True,
            show_to_authenticated=True,
            show_to_trainers=True,
        )

        # Act & Assert - Гость
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        guest_titles = [b["title"] for b in response.json()]
        assert multi_role_banner.title in guest_titles

        # Act & Assert - Retail пользователь
        retail_user = UserFactory(role="retail")
        self.client.force_authenticate(user=retail_user)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        retail_titles = [b["title"] for b in response.json()]
        assert multi_role_banner.title in retail_titles

        # Act & Assert - Тренер
        trainer_user = UserFactory(role="trainer")
        self.client.force_authenticate(user=trainer_user)
        response = self.client.get(self.url)
        assert response.status_code == status.HTTP_200_OK
        trainer_titles = [b["title"] for b in response.json()]
        assert multi_role_banner.title in trainer_titles

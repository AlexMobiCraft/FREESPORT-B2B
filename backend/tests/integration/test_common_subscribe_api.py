"""Интеграционные тесты публичного API подписки на рассылку."""

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.common.models import Newsletter

pytestmark = pytest.mark.django_db


class TestSubscribeEndpoint:
    """Набор кейсов для POST /api/v1/subscribe."""

    def test_subscribe_success(self, api_client):
        """Проверяет успешное создание подписки."""
        url = reverse("common:subscribe")
        data = {"email": "newuser@example.com"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["message"] == "Вы успешно подписались на рассылку"
        assert response.data["email"] == "newuser@example.com"
        assert Newsletter.objects.filter(email="newuser@example.com").exists()

    def test_subscribe_duplicate_email(self, api_client):
        """Гарантирует корректный конфликт при повторной подписке."""
        Newsletter.objects.create(email="existing@example.com", is_active=True)

        url = reverse("common:subscribe")
        data = {"email": "existing@example.com"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_409_CONFLICT
        assert "уже подписан" in str(response.data["email"][0])

    def test_subscribe_reactivate_unsubscribed(self, api_client):
        """Проверяет реактивацию ранее отписавшегося email."""
        Newsletter.objects.create(
            email="unsubscribed@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )

        url = reverse("common:subscribe")
        data = {"email": "unsubscribed@example.com"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        subscription = Newsletter.objects.get(email="unsubscribed@example.com")
        assert subscription.is_active is True
        assert subscription.unsubscribed_at is None

    def test_subscribe_invalid_email(self, api_client):
        """Возвращает 400 для некорректного email."""
        url = reverse("common:subscribe")
        data = {"email": "invalid-email"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_subscribe_email_normalization(self, api_client):
        """Подтверждает нормализацию email в lowercase."""
        url = reverse("common:subscribe")
        data = {"email": "TestUser@EXAMPLE.COM"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        subscription = Newsletter.objects.get(email="testuser@example.com")
        assert subscription.email == "testuser@example.com"

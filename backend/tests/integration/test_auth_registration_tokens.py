import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient


@pytest.mark.django_db
class TestRegistrationTokens:
    def test_retail_registration_returns_tokens(self):
        """
        AC 1: При регистрации розничного пользователя ответ сервера (201)
        содержит access и refresh токены.
        """
        client = APIClient()
        # url = reverse('user-register') - Убрали, так как вызывает ошибку
        url = "/api/v1/auth/register/"

        data = {
            "email": "new_retail_user@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
            "role": "retail",
        }

        # Используем прямой путь, так как reverse может отличаться
        response = client.post("/api/v1/auth/register/", data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Проверяем наличие токенов
        assert "access" in response.data, "Access token missing in registration response"
        assert "refresh" in response.data, "Refresh token missing in registration response"

        # Проверяем структуру user
        assert response.data["user"]["role"] == "retail"
        assert response.data["user"]["is_verified"] is True

    def test_b2b_registration_does_not_return_tokens_if_pending(self):
        """
        AC 2: При регистрации оптового пользователя ответ сервера может не содержать токенов
        (если пользователь требует верификации).
        """
        client = APIClient()
        # Предполагаем прямой путь, если reverse сложен
        url = "/api/v1/auth/register/"

        data = {
            "email": "new_b2b_user@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "B2B",
            "last_name": "User",
            "role": "wholesale_level1",
            "company_name": "Test Company",
            "tax_id": "1234567890",
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Токенов быть НЕ должно, так как user.is_verified=False (по умолчанию для B2B)
        # ИЛИ user.is_active=False

        if not response.data["user"]["is_verified"]:
            assert "access" not in response.data, "Access token should not be present for unverified B2B"
            assert "refresh" not in response.data, "Refresh token should not be present for unverified B2B"

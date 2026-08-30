import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.mark.django_db
class TestRegistrationTokens:
    def test_retail_registration_is_rejected(self):
        """
        Розничная саморегистрация отключена: портал работает как B2B-площадка,
        такая заявка не проходит верификацию и не должна создавать аккаунт.
        """
        client = APIClient()

        data = {
            "email": "new_retail_user@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "New",
            "last_name": "User",
            "role": "retail",
            "pdp_consent": True,
        }

        response = client.post("/api/v1/auth/register/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data
        assert not User.objects.filter(email="new_retail_user@example.com").exists()

    def test_registration_without_role_is_rejected(self):
        """
        Без явной роли заявка отклоняется: у модели `role` есть default="retail",
        и молчаливая подстановка создала бы розничный аккаунт в обход запрета.
        """
        client = APIClient()

        data = {
            "email": "no_role_user@example.com",
            "password": "StrongPassword123!",
            "password_confirm": "StrongPassword123!",
            "first_name": "No",
            "last_name": "Role",
            "pdp_consent": True,
        }

        response = client.post("/api/v1/auth/register/", data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data
        assert not User.objects.filter(email="no_role_user@example.com").exists()

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
            "pdp_consent": True,
        }

        response = client.post(url, data, format="json")

        assert response.status_code == status.HTTP_201_CREATED

        # Токенов быть НЕ должно, так как user.is_verified=False (по умолчанию для B2B)
        # ИЛИ user.is_active=False

        if not response.data["user"]["is_verified"]:
            assert "access" not in response.data, "Access token should not be present for unverified B2B"
            assert "refresh" not in response.data, "Refresh token should not be present for unverified B2B"

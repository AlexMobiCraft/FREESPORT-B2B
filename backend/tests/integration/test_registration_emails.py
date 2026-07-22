"""
Integration тесты для email уведомлений при регистрации (Story 29.4).

Тестирует:
- B2B регистрация вызывает отправку email
- Retail регистрация НЕ вызывает отправку email
"""

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User


@pytest.mark.integration
@pytest.mark.django_db
class TestRegistrationEmailsIntegration:
    """Integration тесты для email при регистрации."""

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_b2b_registration_triggers_emails(self, mock_user_email, mock_admin_email):
        """B2B регистрация вызывает отправку email уведомлений."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "newb2b@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Test",
                "last_name": "User",
                "role": "trainer",
                "company_name": "Test Club",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="newb2b@example.com")

        # Проверяем, что email tasks были вызваны
        mock_admin_email.assert_called_once_with(user.id)
        mock_user_email.assert_called_once_with(user.id)

        # Проверяем статус пользователя
        assert user.is_active is False
        assert user.verification_status == "pending"
        assert user.is_verified is False

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_wholesale_registration_triggers_emails(self, mock_user_email, mock_admin_email):
        """Wholesale регистрация вызывает отправку email."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "wholesale@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Wholesale",
                "last_name": "Buyer",
                "role": "wholesale_level1",
                "company_name": "Wholesale Company",
                "tax_id": "1234567890",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="wholesale@example.com")

        mock_admin_email.assert_called_once_with(user.id)
        mock_user_email.assert_called_once_with(user.id)

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_retail_registration_does_not_trigger_emails(self, mock_user_email, mock_admin_email):
        """Retail регистрация НЕ вызывает отправку verification emails."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "retail@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Retail",
                "last_name": "Customer",
                "role": "retail",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="retail@example.com")

        # Email tasks НЕ должны вызываться для retail
        mock_admin_email.assert_not_called()
        mock_user_email.assert_not_called()

        # Retail пользователи сразу активны
        assert user.is_active is True
        assert user.verification_status == "verified"
        assert user.is_verified is True

    @patch("apps.users.serializers.send_manager_region_email.delay")
    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_b2b_registration_triggers_manager_region_email(
        self, mock_user_email, mock_admin_email, mock_manager_email
    ):
        """B2B регистрация дополнительно ставит в очередь письмо менеджеру региона."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "region-b2b@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Region",
                "last_name": "Buyer",
                "role": "wholesale_level1",
                "company_name": "ООО Регион",
                "tax_id": "7701234567",
                "country": "Россия",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="region-b2b@example.com")

        # Письмо менеджеру — дополнительно к письму админам, не вместо него.
        mock_admin_email.assert_called_once_with(user.id)
        mock_manager_email.assert_called_once_with(user.id)
        assert user.country == "Россия"

    @patch("apps.users.serializers.send_manager_region_email.delay")
    def test_retail_registration_skips_manager_region_email(self, mock_manager_email):
        """Retail регистрация НЕ ставит письмо менеджеру региона."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "region-retail@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Retail",
                "last_name": "Customer",
                "role": "retail",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        mock_manager_email.assert_not_called()

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_federation_rep_registration_triggers_emails(self, mock_user_email, mock_admin_email):
        """Регистрация представителя федерации вызывает email."""
        client = APIClient()

        response = client.post(
            "/api/v1/auth/register/",
            {
                "email": "federation@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Federation",
                "last_name": "Rep",
                "role": "federation_rep",
                "company_name": "Tennis Federation",
                "tax_id": "9876543210",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        user = User.objects.get(email="federation@example.com")

        mock_admin_email.assert_called_once_with(user.id)
        mock_user_email.assert_called_once_with(user.id)

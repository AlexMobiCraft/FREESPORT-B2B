"""
Regression тесты для Epic 28 функциональности

Story 29.2: Backend Verification Logic & Access Control
AC 6: Существующая функциональность Epic 28 (login, password reset) продолжает
      работать без изменений

Проверяем что изменения Epic 29.2 не сломали Epic 28:
- B2B регистрация (Epic 28) продолжает работать
- Вход существующего retail-аккаунта работает
- Password reset flow работает

Отклонение от исходной AC 6: розничная саморегистрация из Epic 28 намеренно
отключена (портал работает как B2B-площадка). Сценарий сохранён как проверка
отказа, а не как проверка успешного создания розничного аккаунта; уже
существующие retail-аккаунты продолжают входить и работать.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestEpic28Regression:
    """Regression тесты для Epic 28 функциональности"""

    def setup_method(self) -> None:
        self.client = APIClient()

    @patch("apps.users.serializers.send_manager_region_email.delay")
    @patch("apps.users.serializers.send_admin_verification_email.delay")
    @patch("apps.users.serializers.send_user_pending_email.delay")
    def test_b2b_registration_still_works(self, _user_email, _admin_email, _manager_email) -> None:
        """Саморегистрация B2B из Epic 28 продолжает работать"""
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newtrainer@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "New",
                "role": "trainer",
                "company_name": "Новый клуб",
                "tax_id": "7712345678",
                "pdp_consent": True,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data
        # B2B-заявка ждёт верификации: токены не выдаются
        assert response.data["user"]["is_verified"] is False
        assert "access" not in response.data

    def test_retail_registration_is_rejected(self) -> None:
        """Розничная саморегистрация отключена (замена сценария Epic 28)"""
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newretail@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "New",
                "role": "retail",
                "pdp_consent": True,
            },
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data

    def test_retail_login_still_works(self) -> None:
        """Retail вход из Epic 28 продолжает работать"""
        user = UserFactory(
            email="retailuser@example.com",
            role="retail",
            is_active=True,
            verification_status="verified",
        )
        user.set_password("TestPass123!")
        user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "retailuser@example.com", "password": "TestPass123!"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["role"] == "retail"

    def test_password_reset_flow_works(self) -> None:
        """Password reset flow работает для всех ролей"""
        # Создаем пользователей разных ролей
        retail_user = UserFactory(
            email="retail@example.com",
            role="retail",
            is_active=True,
            verification_status="verified",
        )
        b2b_user = UserFactory(
            email="b2b@example.com",
            role="trainer",
            is_active=True,
            verification_status="verified",
        )

        # Тест 1: Retail может запросить сброс пароля
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "retail@example.com"})
        assert response.status_code == status.HTTP_200_OK

        # Тест 2: B2B может запросить сброс пароля
        response = self.client.post("/api/v1/auth/password-reset/", {"email": "b2b@example.com"})
        assert response.status_code == status.HTTP_200_OK

    def test_existing_b2b_registration_flow_continues_working(self) -> None:
        """Существующая B2B регистрация flow (Epic 28) продолжает работать"""
        response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "newb2b@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "New",
                "role": "trainer",
                "company_name": "Test Company",
                "tax_id": "7702345678",
                "pdp_consent": True,
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "user" in response.data

        # Epic 29.2: B2B пользователи НЕ могут войти сразу после регистрации
        # Проверяем что они получают pending status
        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "newb2b@example.com", "password": "SecurePass123!"},
        )
        # Ожидаем 403 pending verification (Epic 29.2)
        assert login_response.status_code == status.HTTP_403_FORBIDDEN

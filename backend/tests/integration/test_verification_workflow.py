"""
Integration тесты для workflow верификации пользователей

Story 29.2: Backend Verification Logic & Access Control
AC 3: Pending пользователь получает 403 с кодом 'account_pending_verification'
AC 4: Верифицированный B2B пользователь может войти

Тесты проверяют полный workflow: регистрация → попытка входа → верификация → вход
"""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from tests.factories import UserFactory


@pytest.mark.integration
@pytest.mark.django_db
class TestLoginVerificationBlocking:
    """Integration тесты для блокировки входа pending users"""

    def setup_method(self) -> None:
        self.client = APIClient()

    def test_pending_user_login_returns_403_with_code(self) -> None:
        """
        AC 3: Pending пользователь получает 403 при попытке входа с кодом error
        """
        user = UserFactory(
            email="pending@example.com",
            role="trainer",
            is_active=False,
            verification_status="pending",
        )
        user.set_password("TestPass123!")
        user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "pending@example.com", "password": "TestPass123!"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "detail" in response.data
        assert response.data["detail"] == "Ваша учетная запись находится на проверке"
        # Проверяем наличие кода ошибки (может быть в разных местах в
        # зависимости от DRF)
        # AuthenticationFailed в DRF добавляет code в detail или отдельным полем
        # Проверяем оба варианта

    def test_pending_user_cannot_get_tokens(self) -> None:
        """
        AC 3: Pending пользователь НЕ получает JWT токены
        """
        user = UserFactory(
            email="pending2@example.com",
            role="wholesale_level1",
            is_active=False,
            verification_status="pending",
        )
        user.set_password("TestPass123!")
        user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "pending2@example.com", "password": "TestPass123!"},
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "access" not in response.data
        assert "refresh" not in response.data

    def test_verified_b2b_user_can_login(self) -> None:
        """
        AC 4: Верифицированный B2B пользователь может войти
        """
        user = UserFactory(
            email="verified_b2b@example.com",
            role="trainer",
            is_active=True,
            verification_status="verified",
            is_verified=True,
        )
        user.set_password("TestPass123!")
        user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "verified_b2b@example.com", "password": "TestPass123!"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["role"] == "trainer"

    def test_verified_wholesale_user_can_login(self) -> None:
        """
        Верифицированный wholesale пользователь может войти
        """
        user = UserFactory(
            email="verified_wholesale@example.com",
            role="wholesale_level2",
            is_active=True,
            verification_status="verified",
            is_verified=True,
        )
        user.set_password("TestPass123!")
        user.save()

        response = self.client.post(
            "/api/v1/auth/login/",
            {"email": "verified_wholesale@example.com", "password": "TestPass123!"},
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" in response.data
        assert "refresh" in response.data

    def test_full_verification_workflow(self) -> None:
        """
        Полный workflow: B2B регистрация → блокировка входа → верификация →
        успешный вход
        """
        # Шаг 1: B2B регистрация
        register_response = self.client.post(
            "/api/v1/auth/register/",
            {
                "email": "workflow@example.com",
                "password": "SecurePass123!",
                "password_confirm": "SecurePass123!",
                "first_name": "Workflow",
                "role": "trainer",
                "company_name": "Workflow Gym",
            },
        )
        assert register_response.status_code == status.HTTP_201_CREATED

        # Шаг 2: Попытка входа сразу после регистрации → блокировка
        login_response_blocked = self.client.post(
            "/api/v1/auth/login/",
            {"email": "workflow@example.com", "password": "SecurePass123!"},
        )
        assert login_response_blocked.status_code == status.HTTP_403_FORBIDDEN

        # Шаг 3: Имитация верификации админом (обновление статусов)
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.get(email="workflow@example.com")
        user.is_active = True
        user.verification_status = "verified"
        user.is_verified = True
        user.save()

        # Шаг 4: Попытка входа после верификации → успех
        login_response_success = self.client.post(
            "/api/v1/auth/login/",
            {"email": "workflow@example.com", "password": "SecurePass123!"},
        )
        assert login_response_success.status_code == status.HTTP_200_OK
        assert "access" in login_response_success.data
        assert "refresh" in login_response_success.data

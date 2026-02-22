"""
Unit тесты для логики верификации при регистрации

Story 29.2: Backend Verification Logic & Access Control
AC 1: Розничный покупатель получает is_active=True, verification_status='verified'
AC 2: B2B пользователи получают is_active=False, verification_status='pending'

Тесты проверяют логику установки статусов в UserRegistrationSerializer.create()
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from apps.users.serializers import UserRegistrationSerializer

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestUserRegistrationVerification:
    """Unit тесты для логики верификации при регистрации"""

    def test_retail_registration_sets_active_and_verified(self) -> None:
        """
        AC 1: Retail пользователь получает is_active=True,
        verification_status='verified'
        """
        data = {
            "email": "retail@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Test",
            "role": "retail",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.is_active is True
        assert user.verification_status == "verified"
        assert user.is_verified is True

    def test_b2b_trainer_registration_sets_pending_and_inactive(self) -> None:
        """
        AC 2: B2B trainer получает is_active=False, verification_status='pending'
        """
        data = {
            "email": "trainer@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Test",
            "role": "trainer",
            "company_name": "Test Gym",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.is_active is False
        assert user.verification_status == "pending"
        assert user.is_verified is False

    def test_b2b_wholesale_registration_sets_pending_and_inactive(self) -> None:
        """
        AC 2: B2B wholesale получает is_active=False, verification_status='pending'
        """
        data = {
            "email": "wholesale@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Test",
            "role": "wholesale_level1",
            "company_name": "Test Company",
            "tax_id": "1234567890",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.is_active is False
        assert user.verification_status == "pending"
        assert user.is_verified is False

    def test_b2b_federation_rep_registration_sets_pending_and_inactive(self) -> None:
        """
        AC 2: B2B federation_rep получает is_active=False, verification_status='pending'
        """
        data = {
            "email": "federation@example.com",
            "password": "SecurePass123!",
            "password_confirm": "SecurePass123!",
            "first_name": "Test",
            "role": "federation_rep",
            "company_name": "Test Federation",
            "tax_id": "9876543210",
        }
        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        user = serializer.save()

        assert user.is_active is False
        assert user.verification_status == "pending"
        assert user.is_verified is False

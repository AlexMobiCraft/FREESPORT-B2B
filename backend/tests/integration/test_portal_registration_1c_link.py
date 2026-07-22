"""
Integration-тесты привязки существующего 1С-клиента к регистрации на портале.

Покрывает I/O-матрицу спеки spec-1c-client-portal-linking.md:
- B2B-матч по ИНН, email формы совпадает с 1С -> сразу pending
- B2B-матч по ИНН, email формы отличается -> confirm-ссылка на новый email
- Confirm-эндпоинт применяет email/пароль/pending
- Просроченный/неверный/повторный токен -> 404/410
- Retail-матч по email -> 400 (временно вне скоупа)
- Дубликаты (портальный аккаунт / уже верифицированная 1С-запись) -> 400
- Сброс пароля непривязанного 1С-клиента -> 200 как для несуществующего email
"""

from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from django.core import signing
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User
from apps.users.serializers import PORTAL_LINK_CONFIRM_SALT

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

REGISTER_URL = "/api/v1/auth/register/"
PORTAL_LINK_CONFIRM_URL = "/api/v1/auth/portal-link/confirm/"
PASSWORD_RESET_URL = "/api/v1/auth/password-reset/"


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}@example.com"


def unique_tax_id() -> str:
    return str(1000000000 + (time.time_ns() % 900000000))


def b2b_registration_payload(**overrides):
    payload = {
        "email": unique_email("portal_link"),
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "first_name": "Форма",
        "last_name": "Регистрации",
        "role": "wholesale_level1",
        "company_name": "Форма Компани",
        "tax_id": unique_tax_id(),
        "pdp_consent": True,
    }
    payload.update(overrides)
    return payload


def create_1c_customer(**overrides) -> User:
    defaults = {
        "email": unique_email("1c_customer"),
        "first_name": "Иван",
        "last_name": "Петров",
        "company_name": "ООО 1С Компания",
        "tax_id": unique_tax_id(),
        "role": "wholesale_level1",
        "created_in_1c": True,
        "verification_status": "unverified",
        "onec_id": f"1C-{time.time_ns()}",
    }
    defaults.update(overrides)
    customer = User(**defaults)
    # Импортированный из 1С клиент ещё не имеет пароля на портале
    customer.set_unusable_password()
    customer.save()
    return customer


class TestB2BMatchSameEmail:
    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_password_and_pending_set_atomically_no_new_user(self, mock_admin_email):
        customer = create_1c_customer()
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=customer.email, tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert "access" not in response.data
        assert "refresh" not in response.data
        assert "user" not in response.data

        customer.refresh_from_db()
        assert customer.verification_status == "pending"
        assert customer.check_password("StrongPassword123!")
        assert User.objects.filter(email=customer.email).count() == 1

        mock_admin_email.assert_called_once_with(customer.id)

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_1c_wins_form_fields_do_not_override_matched_customer(self, mock_admin_email):
        customer = create_1c_customer(first_name="Оригинал", last_name="1С", company_name="ООО Оригинал")
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(
                email=customer.email,
                tax_id=customer.tax_id,
                first_name="Подделка",
                last_name="Формы",
                company_name="ООО Подделка",
                role="wholesale_level3",
            ),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        customer.refresh_from_db()
        assert customer.first_name == "Оригинал"
        assert customer.last_name == "1С"
        assert customer.company_name == "ООО Оригинал"
        assert customer.role == "wholesale_level1"

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_pending_1c_customer_cannot_be_rematched(self, mock_admin_email):
        customer = create_1c_customer()
        client = APIClient()

        first_response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=customer.email, tax_id=customer.tax_id),
            format="json",
        )
        assert first_response.status_code == status.HTTP_201_CREATED
        customer.refresh_from_db()
        assert customer.verification_status == "pending"
        assert customer.check_password("StrongPassword123!")

        second_response = client.post(
            REGISTER_URL,
            b2b_registration_payload(
                email=customer.email,
                tax_id=customer.tax_id,
                password="AttackerPassword1!",
                password_confirm="AttackerPassword1!",
            ),
            format="json",
        )

        assert second_response.status_code == status.HTTP_400_BAD_REQUEST
        assert second_response.data["tax_id"] == ["Компания с данным ИНН уже зарегистрирована."]

        customer.refresh_from_db()
        assert customer.check_password("StrongPassword123!")
        assert not customer.check_password("AttackerPassword1!")


class TestB2BMatchMismatchedEmail:
    @patch("apps.users.serializers.send_portal_link_confirmation_email.delay")
    def test_password_not_saved_confirmation_sent_to_new_email(self, mock_confirmation_email):
        customer = create_1c_customer()
        new_email = unique_email("new_address")
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=new_email, tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        customer.refresh_from_db()
        assert customer.verification_status == "unverified"
        assert not customer.check_password("StrongPassword123!")
        assert customer.email != new_email

        mock_confirmation_email.assert_called_once()
        called_args = mock_confirmation_email.call_args[0]
        assert called_args[0] == customer.id
        assert called_args[1] == new_email

        token = called_args[2].rsplit("/", 2)[-2]
        data = signing.loads(token, salt=PORTAL_LINK_CONFIRM_SALT)
        assert data == {"user_id": customer.id, "new_email": new_email}

    def test_new_email_already_taken_rejected_at_registration(self):
        customer = create_1c_customer()
        taken_email = unique_email("already_taken")
        User.objects.create_user(
            email=taken_email,
            password="ExistingPass1!",
            first_name="Занял",
            last_name="Раньше",
            role="retail",
            verification_status="verified",
            is_verified=True,
        )
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=taken_email, tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["email"] == ["Пользователь с таким email уже существует."]

        customer.refresh_from_db()
        assert customer.verification_status == "unverified"
        assert not customer.check_password("StrongPassword123!")


class TestPortalLinkConfirmView:
    def _make_token(self, customer: User, new_email: str) -> str:
        return signing.dumps({"user_id": customer.id, "new_email": new_email}, salt=PORTAL_LINK_CONFIRM_SALT)

    @patch("apps.users.views.authentication.send_admin_verification_email.delay")
    def test_confirm_applies_email_password_and_pending(self, mock_admin_email):
        customer = create_1c_customer()
        new_email = unique_email("confirmed")
        token = self._make_token(customer, new_email)
        client = APIClient()

        response = client.post(
            PORTAL_LINK_CONFIRM_URL,
            {
                "token": token,
                "new_password": "AnotherStrongPass1!",
                "new_password_confirm": "AnotherStrongPass1!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert "access" not in response.data
        assert "refresh" not in response.data

        customer.refresh_from_db()
        assert customer.email == new_email
        assert customer.verification_status == "pending"
        assert customer.check_password("AnotherStrongPass1!")

        mock_admin_email.assert_called_once_with(customer.id)

    @patch("apps.users.views.authentication.send_admin_verification_email.delay")
    def test_invalid_token_returns_404(self, mock_admin_email):
        client = APIClient()

        response = client.post(
            PORTAL_LINK_CONFIRM_URL,
            {
                "token": "not-a-valid-token",
                "new_password": "AnotherStrongPass1!",
                "new_password_confirm": "AnotherStrongPass1!",
            },
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND
        mock_admin_email.assert_not_called()

    @patch("apps.users.views.authentication.send_admin_verification_email.delay")
    def test_replayed_token_returns_410(self, mock_admin_email):
        customer = create_1c_customer()
        new_email = unique_email("replay")
        token = self._make_token(customer, new_email)
        client = APIClient()

        payload = {
            "token": token,
            "new_password": "AnotherStrongPass1!",
            "new_password_confirm": "AnotherStrongPass1!",
        }

        first_response = client.post(PORTAL_LINK_CONFIRM_URL, payload, format="json")
        assert first_response.status_code == status.HTTP_200_OK

        second_response = client.post(PORTAL_LINK_CONFIRM_URL, payload, format="json")
        assert second_response.status_code == status.HTTP_410_GONE


class TestRetailMatchOutOfScope:
    def test_retail_match_by_email_returns_400_same_as_duplicate(self):
        customer = create_1c_customer(role="retail", tax_id="")
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            {
                "email": customer.email,
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "first_name": "Форма",
                "last_name": "Регистрации",
                "role": "retail",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["email"] == ["Пользователь с таким email уже существует."]
        assert User.objects.filter(email=customer.email).count() == 1


class TestDuplicates:
    def test_duplicate_portal_account_by_email_returns_400(self):
        existing = User.objects.create_user(
            email=unique_email("portal_dup"),
            password="ExistingPass1!",
            first_name="Существующий",
            last_name="Пользователь",
            role="retail",
            verification_status="verified",
            is_verified=True,
        )
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            {
                "email": existing.email,
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "first_name": "Форма",
                "last_name": "Регистрации",
                "role": "retail",
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["email"] == ["Пользователь с таким email уже существует."]

    def test_already_verified_1c_record_by_tax_id_returns_400(self):
        customer = create_1c_customer(verification_status="verified")
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("verified_dup"), tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["tax_id"] == ["Компания с данным ИНН уже зарегистрирована."]

    def test_two_portal_accounts_same_tax_id_second_rejected(self):
        tax_id = unique_tax_id()
        client = APIClient()

        first_response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("first_owner"), tax_id=tax_id),
            format="json",
        )
        assert first_response.status_code == status.HTTP_201_CREATED

        second_response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("second_owner"), tax_id=tax_id),
            format="json",
        )

        assert second_response.status_code == status.HTTP_400_BAD_REQUEST
        assert second_response.data["tax_id"] == ["Компания с данным ИНН уже зарегистрирована."]
        assert User.objects.filter(tax_id=tax_id).count() == 1


class TestPasswordResetForUnlinked1CCustomer:
    @patch("apps.users.views.authentication.send_password_reset_email.delay")
    def test_returns_generic_ok_same_as_unknown_email(self, mock_reset_email):
        customer = create_1c_customer()
        client = APIClient()

        linked_response = client.post(PASSWORD_RESET_URL, {"email": customer.email}, format="json")
        unknown_response = client.post(PASSWORD_RESET_URL, {"email": unique_email("does_not_exist")}, format="json")

        assert linked_response.status_code == status.HTTP_200_OK
        assert unknown_response.status_code == status.HTTP_200_OK
        assert linked_response.data == unknown_response.data

"""
Integration-тесты регистрации при наличии контрагента 1С с тем же ИНН.

Автопривязка отключена (spec-1c-unregistered-role, 2026-07-26): ИНН публичен,
поэтому сам по себе правом на контрагента не является. Регистрация создаёт
обычную заявку, запись 1С не изменяется, связывание выполняет менеджер.

Покрывает I/O-матрицу спеки:
- ИНН известен 1С -> создаётся заявка, запись 1С нетронута
- Неоднозначный ИНН (несколько контрагентов) -> заявка создаётся, не 500
- ИНН принадлежит живому аккаунту -> 400
- Email занят -> 400
- role='unregistered' в запросе -> 400
- Сброс пароля непривязанного 1С-клиента -> 200 как для несуществующего email
"""

from __future__ import annotations

import itertools
import time
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

REGISTER_URL = "/api/v1/auth/register/"
PASSWORD_RESET_URL = "/api/v1/auth/password-reset/"


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}@example.com"


_tax_id_counter = itertools.count()


def unique_tax_id() -> str:
    # Только time_ns() давал период повторения 0.9 с — тесты, создающие
    # по десятку записей с одним ИНН и сверяющие точные count(), ловили
    # случайные пересечения. Счётчик снимает зависимость от таймера.
    return str(1000000000 + ((time.time_ns() + next(_tax_id_counter) * 7919) % 900000000))


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
        # Импорт 1С ставит новым контрагентам нейтральную роль — по ней
        # регистрация и отличает запись без портального аккаунта.
        "role": "unregistered",
        "created_in_1c": True,
        "verification_status": "unverified",
        "onec_id": f"1C-{time.time_ns()}",
    }
    defaults.update(overrides)
    customer = User(**defaults)
    # Импорт 1С создаёт запись через User.objects.create() без пароля, поэтому
    # password остаётся пустой строкой. Именно по ней отличается контрагент
    # без портального аккаунта — set_unusable_password() дал бы "!<random>"
    # и разошёлся бы с продакшеном (там все 4606 записей имеют "").
    customer.save()
    return customer


class Test1CRecordUntouchedByRegistration:
    """
    Регистрация с ИНН, известным 1С, не изменяет запись контрагента.

    Именно изменение записи (установка пароля, подмена email) позволяло
    занять контрагента чужой компании, зная лишь публичный ИНН.
    """

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_registration_creates_new_request_and_leaves_1c_record_intact(self, mock_admin_email):
        customer = create_1c_customer()
        before = {
            "password": customer.password,
            "email": customer.email,
            "verification_status": customer.verification_status,
            "role": customer.role,
        }
        users_before = User.objects.count()
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.count() == users_before + 1

        customer.refresh_from_db()
        assert customer.password == before["password"]
        assert customer.email == before["email"]
        assert customer.verification_status == before["verification_status"]
        assert customer.role == before["role"]

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_new_request_keeps_role_from_form(self, mock_admin_email):
        """Роль из формы сохраняется — иначе заявку не одобрить в админке."""
        customer = create_1c_customer()
        client = APIClient()
        payload = b2b_registration_payload(tax_id=customer.tax_id, role="trainer")

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        applicant = User.objects.get(email=payload["email"])
        assert applicant.role == "trainer"
        assert applicant.verification_status == "pending"
        assert applicant.is_active is False
        assert applicant.created_in_1c is False

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_matching_email_of_1c_record_is_rejected_as_duplicate(self, mock_admin_email):
        """
        Email записи 1С занят: заявку отклоняем, пароль на запись не ставим.
        Раньше этот путь давал 201 и устанавливал пароль на чужую запись.
        """
        customer = create_1c_customer()
        assert customer.email
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=customer.email, tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["email"] == ["Пользователь с таким email уже существует."]

        customer.refresh_from_db()
        assert customer.password == ""
        assert customer.verification_status == "unverified"

    def test_unregistered_role_is_rejected(self):
        """Служебную роль нельзя выбрать при регистрации."""
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(role="unregistered"),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data

    def test_admin_role_is_rejected(self):
        """Роль администратора нельзя получить самозаписью."""
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(role="admin"),
            format="json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "role" in response.data

    def test_non_russian_tax_id_duplicate_is_rejected(self):
        """
        9-значный УНП тоже проверяется на дубли.

        Раньше проверка шла через normalize_inn (только 10 и 12 цифр),
        поэтому белорусские и казахстанские номера её не проходили.
        """
        tax_id = "191234567"
        client = APIClient()

        first = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("by_first"), tax_id=tax_id, country="Беларусь"),
            format="json",
        )
        assert first.status_code == status.HTTP_201_CREATED

        second = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("by_second"), tax_id=tax_id, country="Беларусь"),
            format="json",
        )

        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert second.data["tax_id"] == ["Компания с данным ИНН уже зарегистрирована."]

    def test_1c_record_with_unusable_password_does_not_block_registration(self):
        """
        Запись 1С с паролем-заглушкой "!<random>" остаётся непривязанной.

        Django считает пустой пароль usable, поэтому признак проверяет оба
        варианта: пустую строку и заглушку от create_user(password=None).
        """
        customer = create_1c_customer()
        customer.set_unusable_password()
        customer.save(update_fields=["password"])
        assert customer.is_unlinked_1c_record is True

        client = APIClient()
        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(tax_id=customer.tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

    def test_unregistered_role_not_offered_by_roles_endpoint(self):
        client = APIClient()

        response = client.get("/api/v1/users/roles/")

        assert response.status_code == status.HTTP_200_OK
        keys = {role["key"] for role in response.data["roles"]}
        assert "unregistered" not in keys
        assert "admin" not in keys


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


class TestTrainerRoleRequiresTaxId:
    """
    Роль trainer («Тренер / Спортивный клуб») — такой же B2B-клиент:
    без ИНН резолвер не находит запись из 1С и создается дубль.
    """

    def test_trainer_without_tax_id_returns_400(self):
        client = APIClient()
        payload = b2b_registration_payload(role="trainer", company_name="Спортклуб")
        payload.pop("tax_id")

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["tax_id"] == ["ИНН обязателен для B2B пользователей."]
        assert not User.objects.filter(email=payload["email"]).exists()

    def test_trainer_with_malformed_tax_id_returns_400(self):
        client = APIClient()
        payload = b2b_registration_payload(role="trainer", company_name="Спортклуб", tax_id="abc1234567")

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["tax_id"] == ["ИНН должен содержать 10 или 12 цифр."]
        assert not User.objects.filter(email=payload["email"]).exists()

    def test_trainer_from_belarus_accepts_9_digit_tax_id(self):
        """У белорусского УНП 9 цифр — маска российского ИНН к нему не применяется."""
        client = APIClient()
        payload = b2b_registration_payload(
            role="trainer",
            company_name="Спортклуб",
            country="Беларусь",
            tax_id="191234567",
        )

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.get(email=payload["email"]).tax_id == "191234567"

    def test_trainer_from_russia_rejects_9_digit_tax_id(self):
        client = APIClient()
        payload = b2b_registration_payload(role="trainer", company_name="Спортклуб", tax_id="191234567")

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["tax_id"] == ["ИНН должен содержать 10 или 12 цифр."]

    def test_retail_tax_id_is_ignored_and_not_matched(self):
        """ИНН, оставшийся в форме после переключения на retail, не должен искать клиента 1С."""
        customer = create_1c_customer()
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            {
                "email": unique_email("retail_with_tax_id"),
                "password": "StrongPassword123!",
                "password_confirm": "StrongPassword123!",
                "first_name": "Розница",
                "last_name": "Покупатель",
                "role": "retail",
                "tax_id": customer.tax_id,
                "pdp_consent": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        new_user = User.objects.get(email=response.data["user"]["email"])
        assert new_user.tax_id == ""
        customer.refresh_from_db()
        assert customer.verification_status == "unverified"

    def test_trainer_tax_id_with_separators_is_normalized(self):
        """ИНН, скопированный с пробелами, не должен блокировать регистрацию."""
        client = APIClient()
        tax_id = unique_tax_id()
        payload = b2b_registration_payload(
            role="trainer",
            company_name="Спортклуб",
            tax_id=f" {tax_id[:3]} {tax_id[3:]} ",
        )

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        user = User.objects.get(email=payload["email"])
        assert user.tax_id == tax_id

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_trainer_with_known_tax_id_creates_request_without_touching_1c(self, mock_admin_email):
        """Тренер с ИНН из 1С заводит заявку; контрагент остаётся нетронутым."""
        customer = create_1c_customer(company_name="Спортклуб 1С")
        users_before = User.objects.count()
        client = APIClient()
        payload = b2b_registration_payload(
            tax_id=customer.tax_id,
            role="trainer",
            company_name="Спортклуб",
        )

        response = client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.count() == users_before + 1
        # Обе записи с одним ИНН сосуществуют: связывание — за менеджером
        assert User.objects.filter(tax_id=customer.tax_id).count() == 2

        applicant = User.objects.get(email=payload["email"])
        assert applicant.role == "trainer"
        assert applicant.company_name == "Спортклуб"

        customer.refresh_from_db()
        assert customer.verification_status == "unverified"
        assert customer.password == ""
        assert customer.company_name == "Спортклуб 1С"
        assert customer.role == "unregistered"

        mock_admin_email.assert_called_once_with(applicant.id)


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


class TestTaxIdSharedByManyContragents:
    """
    Один ИНН — несколько контрагентов 1С.

    На проде это норма: юрлицо ведётся как набор контрагентов (филиалы,
    точки, договоры), до 74 записей на ИНН. Проверяется путь регистрации
    (`_reject_if_tax_id_belongs_to_account` → `find_by_tax_id`): раньше
    поиск шёл через `.get()` и падал с `MultipleObjectsReturned` → HTTP 500.
    """

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_ambiguous_tax_id_does_not_block_registration(self, mock_admin_email):
        """Раньше такой ИНН давал MultipleObjectsReturned и HTTP 500."""
        tax_id = unique_tax_id()
        first = create_1c_customer(tax_id=tax_id, company_name="ООО Ромашка Филиал 1")
        second = create_1c_customer(tax_id=tax_id, company_name="ООО Ромашка Филиал 2")
        users_before = User.objects.count()
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("ambiguous"), tax_id=tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.count() == users_before + 1

        # Ни один из кандидатов не тронут — выбор делает менеджер
        for candidate in (first, second):
            candidate.refresh_from_db()
            assert candidate.password == ""
            assert candidate.verification_status == "unverified"

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_many_candidates_do_not_raise(self, mock_admin_email):
        """Воспроизводит продовую группу из десятков контрагентов на один ИНН."""
        tax_id = unique_tax_id()
        for index in range(12):
            create_1c_customer(tax_id=tax_id, company_name=f"ООО Ромашка Точка {index}")
        client = APIClient()

        response = client.post(
            REGISTER_URL,
            b2b_registration_payload(email=unique_email("many"), tax_id=tax_id),
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert User.objects.filter(tax_id=tax_id).count() == 13


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

    @patch("apps.users.views.authentication.send_password_reset_email.delay")
    def test_reset_email_is_not_sent_for_1c_record(self, mock_reset_email):
        """
        Ответ обезличен, но письмо уходить не должно.

        Иначе получатель почты контрагента задаёт пароль и входит в аккаунт
        с реквизитами юрлица: логин блокирует только статус "pending", а у
        импортированной записи он "unverified".
        """
        customer = create_1c_customer()
        client = APIClient()

        response = client.post(PASSWORD_RESET_URL, {"email": customer.email}, format="json")

        assert response.status_code == status.HTTP_200_OK
        mock_reset_email.assert_not_called()

        customer.refresh_from_db()
        assert customer.password == ""

    @patch("apps.users.views.authentication.send_password_reset_email.delay")
    def test_reset_email_is_sent_for_real_account(self, mock_reset_email):
        """Обычный пользователь сброс пароля получает."""
        user = User.objects.create_user(
            email=unique_email("real_account"),
            password="StrongPassword123!",
            role="retail",
        )
        client = APIClient()

        response = client.post(PASSWORD_RESET_URL, {"email": user.email}, format="json")

        assert response.status_code == status.HTTP_200_OK
        mock_reset_email.assert_called_once()


class TestB2BApprovalActivatesAccount:
    """
    Регистрация создаёт B2B-заявку с is_active=False; одобрение обязано её
    активировать, иначе логин выдаёт токены, но каждый следующий запрос
    отклоняется как обращение неактивного пользователя.
    """

    @patch("apps.users.serializers.send_admin_verification_email.delay")
    def test_approve_action_activates_applicant(self, mock_admin_email):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory

        from apps.users.admin import UserAdmin

        client = APIClient()
        payload = b2b_registration_payload()
        assert client.post(REGISTER_URL, payload, format="json").status_code == status.HTTP_201_CREATED

        applicant = User.objects.get(email=payload["email"])
        assert applicant.is_active is False

        request = RequestFactory().post("/admin/")
        request.user = User.objects.create_superuser(email=unique_email("root"), password="StrongPassword123!")
        # message_user требует поддержки сообщений — в тестовом запросе её нет
        request._messages = _DummyMessages()

        UserAdmin(User, AdminSite()).approve_b2b_users(request, User.objects.filter(pk=applicant.pk))

        applicant.refresh_from_db()
        assert applicant.verification_status == "verified"
        assert applicant.is_verified is True
        assert applicant.is_active is True


class _DummyMessages:
    def add(self, *args, **kwargs):
        return None

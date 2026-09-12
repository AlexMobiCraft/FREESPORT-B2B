from __future__ import annotations

import itertools
import json
import time
from unittest.mock import patch

import pytest
from django.db import DatabaseError
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.consent_texts import current_consent_text_version
from apps.common.models import UserConsent
from apps.users.models import User
from apps.common.serializers import CONSENT_TEXT_OUTDATED, CONSENT_TEXT_OUTDATED_CODE
from apps.users.serializers import UserRegistrationSerializer
from tests.consent_versions import REGISTRATION_MARKETING_TEXT_VERSION, REGISTRATION_PDP_TEXT_VERSION


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


_INN_COUNTER = itertools.count(1)


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}@example.com"


def unique_inn() -> str:
    """
    Уникальный 10-значный ИНН на каждую регистрацию.

    Повтор ИНН отклоняется `_reject_if_tax_id_belongs_to_account`, поэтому
    фиксированное значение сделало бы вторую регистрацию в тесте невозможной.
    """
    return f"77{next(_INN_COUNTER) % 10**8:08d}"


@pytest.fixture(autouse=True)
def _mute_b2b_notification_tasks():
    """
    Регистрация B2B ставит в очередь три письма. Розничной регистрации больше
    нет, поэтому очередь дёргает каждый тест файла — задачи глушим.
    """
    with (
        patch("apps.users.serializers.send_admin_verification_email.delay"),
        patch("apps.users.serializers.send_user_pending_email.delay"),
        patch("apps.users.serializers.send_manager_region_email.delay"),
    ):
        yield


def trainer_payload(**overrides):
    """Заявка тренера — базовый сценарий саморегистрации после отказа от retail."""
    payload = {
        "email": unique_email("consent_trainer"),
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "first_name": "Consent",
        "last_name": "Trainer",
        "role": "trainer",
        "company_name": "Consent Club",
        "tax_id": unique_inn(),
        "pdp_consent": True,
        "pdp_consent_text_version": REGISTRATION_PDP_TEXT_VERSION,
        # Маркетинговый чекбокс форма показывает всегда, поэтому его версию
        # она отправляет независимо от того, стоит ли галочка.
        "marketing_consent_text_version": REGISTRATION_MARKETING_TEXT_VERSION,
        "marketing_consent": False,
    }
    payload.update(overrides)
    return payload


def b2b_payload(**overrides):
    payload = {
        "email": unique_email("consent_b2b"),
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "first_name": "Consent",
        "last_name": "B2B",
        "role": "wholesale_level1",
        "company_name": "Consent Company",
        "tax_id": unique_inn(),
        "pdp_consent": True,
        "pdp_consent_text_version": REGISTRATION_PDP_TEXT_VERSION,
        # Маркетинговый чекбокс форма показывает всегда, поэтому его версию
        # она отправляет независимо от того, стоит ли галочка.
        "marketing_consent_text_version": REGISTRATION_MARKETING_TEXT_VERSION,
        "marketing_consent": False,
    }
    payload.update(overrides)
    return payload


def post_register(client: APIClient, payload: dict, **headers):
    return client.post("/api/v1/auth/register/", payload, format="json", **headers)


def test_registration_requires_pdp_consent():
    client = APIClient()
    payload = trainer_payload()
    payload.pop("pdp_consent")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pdp_consent" in response.data
    assert response.data["pdp_consent"] == ["Необходимо согласие на обработку персональных данных."]


def test_registration_rejects_outdated_pdp_text_version():
    """Вкладка с прежней формулировкой ПДн отклоняется, а не записывается новой версией.

    Иначе в журнал легло бы согласие с текстом, которого человек не видел: форма
    осталась старой, а версию проставил бы сервер по действующему реестру.
    """
    client = APIClient()
    # Payload сохраняется в переменную: `trainer_payload()` генерирует новый
    # уникальный email на каждый вызов, поэтому повторный вызов в проверке
    # искал бы несуществующий адрес и прошёл бы даже при созданном пользователе.
    payload = trainer_payload(pdp_consent_text_version="2020-01-01-deadbeef")

    response = post_register(client, payload)

    # Сверка по отрендеренному JSON: `ErrorDetail.code` до клиента не доходит,
    # поэтому машинный код стоит верхним уровнем ответа, а поля — в `details`.
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {"pdp_consent_text_version": [CONSENT_TEXT_OUTDATED]},
    }
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


def test_registration_requires_pdp_text_version():
    """Форма старого бандла версию не присылает — это тоже устаревшая форма.

    Внутренний код DRF у пропущенного поля — `required`, но клиенту нужен тот же
    машинный код: случай и лечение (обновить страницу) те же.
    """
    client = APIClient()
    payload = trainer_payload()
    payload.pop("pdp_consent_text_version")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {"pdp_consent_text_version": [CONSENT_TEXT_OUTDATED]},
    }
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


def test_registration_requires_marketing_text_version_when_consent_given():
    """Галочка маркетинга без версии текста — тот же отказ, что и устаревшая версия.

    Поле необязательно на уровне DRF (форма без галочки версию не доказывает),
    обязательным его делает `validate_marketing_consent_text_version()` при
    `marketing_consent=True`. Путь
    «поле отсутствует» проходит мимо ветки сравнения версий, поэтому проверяется
    отдельно от уже покрытой устаревшей версии.
    """
    client = APIClient()
    payload = trainer_payload(marketing_consent=True)
    payload.pop("marketing_consent_text_version")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {"marketing_consent_text_version": [CONSENT_TEXT_OUTDATED]},
    }
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


@pytest.mark.parametrize(
    "version",
    [["2020-01-01-deadbeef"], {"version": "2020-01-01-deadbeef"}, True, 20200101],
    ids=["list", "object", "boolean", "number"],
)
@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("pdp_consent_text_version", {}),
        # Маркетинговая версия сверяется с реестром только при данном согласии.
        ("marketing_consent_text_version", {"marketing_consent": True}),
    ],
    ids=["pdp", "marketing"],
)
def test_registration_non_string_text_version_asks_to_refresh_page(field, overrides, version):
    """Нестроковая версия получает то же требование обновить страницу, что и устаревшая.

    Любая ошибка поля версии помечает ответ `consent_text_outdated`, а фронт берёт
    текст из этого поля. DRF `CharField` на массив, объект и boolean отвечает кодом
    `invalid` со своим «Not a valid string.» — без переопределения человек увидел
    бы его вместо требования обновить страницу (седьмой круг ревью стори 41.9).
    Число DRF приводит к строке, и его отклоняет сверка с реестром — вариант
    фиксирует, что сообщение то же.
    """
    client = APIClient()
    payload = trainer_payload(**overrides, **{field: version})

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {field: [CONSENT_TEXT_OUTDATED]},
    }
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


@pytest.mark.parametrize(
    "version",
    ["2020-01-01-dead\x00beef", "2020-01-01-\ud800"],
    ids=["null-character", "lone-surrogate"],
)
@pytest.mark.parametrize(
    ("field", "overrides"),
    [
        ("pdp_consent_text_version", {}),
        ("marketing_consent_text_version", {"marketing_consent": True}),
    ],
    ids=["pdp", "marketing"],
)
def test_registration_version_rejected_by_field_validator_asks_to_refresh_page(field, overrides, version):
    """Строка, отсечённая валидатором `CharField`, получает то же требование обновить страницу.

    Ноль-байт и одиночный суррогат `CharField` отклоняет собственными валидаторами,
    и их сообщения ключами `error_messages` поля не переопределяются. Текст
    выравнивает `consent_text_outdated_payload()` — единая точка для любого отказа
    по полю версии (седьмой круг ревью стори 41.9, решение Alex).
    """
    client = APIClient()
    payload = trainer_payload(**overrides, **{field: version})

    # Одиночный суррогат в UTF-8 не кодируется, поэтому тело собирается
    # `json.dumps` с ASCII-экранированием — так его пришлёт внешний клиент.
    response = client.post("/api/v1/auth/register/", json.dumps(payload), content_type="application/json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {field: [CONSENT_TEXT_OUTDATED]},
    }
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


def test_registration_plain_validation_error_keeps_flat_shape():
    """Обычная валидация регистрации возвращается плоским объектом, как и прежде."""
    client = APIClient()
    payload = trainer_payload(password_confirm="Другой-пароль-123")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert "error" not in body
    assert "password_confirm" in body or "non_field_errors" in body


def test_registration_outdated_pdp_version_survives_other_field_error():
    """Устаревшая версия ПДн не теряется рядом с field-level ошибкой другого поля.

    DRF собирает field-level ошибки всех полей, а object-level `validate()` при
    любой из них не вызывает: сверка версии там пропадала бы молча, и ответ ушёл
    бы плоским — без машинного кода, по которому фронт требует обновить страницу.
    """
    client = APIClient()
    payload = trainer_payload(role="admin", pdp_consent_text_version="2020-01-01-deadbeef")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"] == CONSENT_TEXT_OUTDATED_CODE
    assert body["details"]["pdp_consent_text_version"] == [CONSENT_TEXT_OUTDATED]
    assert body["details"]["role"], "ошибка роли обязана остаться в ответе"
    assert User.objects.filter(email=payload["email"]).count() == 0
    assert UserConsent.objects.count() == 0


def test_registration_outdated_pdp_version_wins_over_password_mismatch():
    """Несовпадение паролей не прячет устаревшую формулировку.

    Пароли сверяются в `validate()` первыми; пока версия проверялась там же,
    ответ «пароли не совпадают» уходил без машинного кода — человек чинил бы
    пароль на форме, которую сервер всё равно отклонит.
    """
    client = APIClient()
    payload = trainer_payload(
        password_confirm="Другой-пароль-123",
        pdp_consent_text_version="2020-01-01-deadbeef",
    )

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"] == CONSENT_TEXT_OUTDATED_CODE
    assert body["details"]["pdp_consent_text_version"] == [CONSENT_TEXT_OUTDATED]
    assert User.objects.filter(email=payload["email"]).count() == 0


def test_registration_outdated_marketing_version_survives_other_field_error():
    """То же для маркетинговой версии: проверка условна, но не пропадает."""
    client = APIClient()
    payload = trainer_payload(
        role="admin",
        marketing_consent=True,
        marketing_consent_text_version="2020-01-01-deadbeef",
    )

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert body["error"] == CONSENT_TEXT_OUTDATED_CODE
    assert body["details"]["marketing_consent_text_version"] == [CONSENT_TEXT_OUTDATED]
    assert body["details"]["role"], "ошибка роли обязана остаться в ответе"
    assert UserConsent.objects.count() == 0


def test_registration_marketing_version_is_not_checked_without_consent_next_to_other_error():
    """Без галочки маркетинга устаревшая версия его текста отказом не считается.

    Условность проверки обязана пережить перенос на уровень поля: иначе рядом с
    любой обычной ошибкой форма без галочки получила бы «обновите страницу».
    """
    client = APIClient()
    payload = trainer_payload(
        role="admin",
        marketing_consent=False,
        marketing_consent_text_version="2020-01-01-deadbeef",
    )

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    body = response.json()
    assert "error" not in body
    assert "marketing_consent_text_version" not in body
    assert body["role"]


def test_registration_rejects_outdated_marketing_text_version_only_when_consent_given():
    """Версия маркетингового текста проверяется ровно тогда, когда галочка стоит.

    Без галочки записи `marketing_email` не появится, и требовать актуальность
    её формулировки не за что; с галочкой — согласие фиксируется, и текст обязан
    быть тем, что человек видел.
    """
    client = APIClient()

    rejected = post_register(
        client,
        trainer_payload(marketing_consent=True, marketing_consent_text_version="2020-01-01-deadbeef"),
    )

    assert rejected.status_code == status.HTTP_400_BAD_REQUEST
    assert rejected.json() == {
        "error": CONSENT_TEXT_OUTDATED_CODE,
        "details": {"marketing_consent_text_version": [CONSENT_TEXT_OUTDATED]},
    }
    assert UserConsent.objects.count() == 0

    accepted = post_register(
        client,
        trainer_payload(marketing_consent=False, marketing_consent_text_version="2020-01-01-deadbeef"),
    )

    assert accepted.status_code == status.HTTP_201_CREATED
    assert UserConsent.objects.filter(consent_type="marketing_email").count() == 0


def test_registration_rejects_pdp_consent_false():
    client = APIClient()

    response = post_register(client, trainer_payload(pdp_consent=False))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pdp_consent" in response.data


@pytest.mark.parametrize("invalid_value", ["not-bool", None])
def test_registration_rejects_invalid_pdp_consent_with_contract_message(invalid_value):
    client = APIClient()

    response = post_register(client, trainer_payload(pdp_consent=invalid_value))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["pdp_consent"] == ["Необходимо согласие на обработку персональных данных."]


@pytest.mark.parametrize("truthy_value", [1, "yes", "on", "t"])
def test_registration_accepts_drf_truthy_pdp_consent_values_by_decision(truthy_value):
    client = APIClient()

    response = post_register(client, trainer_payload(pdp_consent=truthy_value))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert UserConsent.objects.filter(user=user, consent_type="pdp_contract").exists()


def test_trainer_registration_creates_pdp_consent_record():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(marketing_consent=False),
        REMOTE_ADDR="1.2.3.4",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consents = UserConsent.objects.filter(user=user)
    assert consents.count() == 1
    consent = consents.get()
    assert consent.consent_type == "pdp_contract"
    assert consent.ip_address == "1.2.3.4"
    assert consent.user_agent == "ConsentTestAgent/1.0"


def test_trainer_registration_with_marketing_creates_two_records():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(marketing_consent=True),
        REMOTE_ADDR="1.2.3.4",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consents = list(UserConsent.objects.filter(user=user).order_by("consent_type"))
    assert {consent.consent_type for consent in consents} == {
        "pdp_contract",
        "marketing_email",
    }
    assert {consent.ip_address for consent in consents} == {"1.2.3.4"}
    assert {consent.user_agent for consent in consents} == {"ConsentTestAgent/1.0"}


@patch("apps.users.serializers.send_admin_verification_email.delay")
@patch("apps.users.serializers.send_user_pending_email.delay")
def test_b2b_registration_creates_pdp_consent_record_for_pending_user(
    mock_user_email,
    mock_admin_email,
):
    client = APIClient()

    response = post_register(client, b2b_payload())

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert user.is_active is False
    assert user.is_verified is False
    consent = UserConsent.objects.get(user=user)
    assert consent.consent_type == "pdp_contract"
    mock_admin_email.assert_called_once_with(user.id)
    mock_user_email.assert_called_once_with(user.id)


@patch("apps.users.serializers.send_admin_verification_email.delay")
@patch("apps.users.serializers.send_user_pending_email.delay")
def test_b2b_registration_with_marketing_creates_two_records_for_pending_user(
    mock_user_email,
    mock_admin_email,
):
    client = APIClient()

    response = post_register(
        client,
        b2b_payload(marketing_consent=True),
        REMOTE_ADDR="1.2.3.4",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert user.is_active is False
    assert user.is_verified is False
    consents = list(UserConsent.objects.filter(user=user).order_by("consent_type"))
    assert {consent.consent_type for consent in consents} == {
        "pdp_contract",
        "marketing_email",
    }
    assert {consent.ip_address for consent in consents} == {"1.2.3.4"}
    assert {consent.user_agent for consent in consents} == {"ConsentTestAgent/1.0"}
    mock_admin_email.assert_called_once_with(user.id)
    mock_user_email.assert_called_once_with(user.id)


def test_consent_record_captures_ip_and_user_agent_from_proxy_headers():
    client = APIClient()
    long_user_agent = "A" * 600

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
        HTTP_USER_AGENT=long_user_agent,
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "1.2.3.4"
    assert consent.user_agent == "A" * 512


def test_registration_normalizes_ipv4_mapped_ipv6_for_consent_record():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="::ffff:8.8.8.8",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "8.8.8.8"


def test_registration_ignores_invalid_forwarded_ip_for_consent_record():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="not-a-valid-ip, 5.6.7.8",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "127.0.0.1"
    assert consent.ip_address != "5.6.7.8"


def test_registration_falls_back_to_remote_addr_when_forwarded_ip_first_hop_is_blank():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR=", 5.6.7.8",
        REMOTE_ADDR="8.8.8.8",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "8.8.8.8"


def test_registration_falls_back_to_remote_addr_when_forwarded_ip_is_whitespace():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR=" ",
        REMOTE_ADDR="8.8.4.4",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "8.8.4.4"


@pytest.mark.parametrize(
    ("forwarded_ip", "expected_ip"),
    [
        ("[2606:4700:4700::1111]:443", "2606:4700:4700::1111"),
        ("1.2.3.4:8443", "1.2.3.4"),
        ("2606:4700:4700::ABCD", "2606:4700:4700::abcd"),
    ],
)
def test_registration_normalizes_forwarded_ip_with_port(forwarded_ip, expected_ip):
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR=forwarded_ip,
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == expected_ip


def test_registration_rejects_forwarded_ipv4_with_invalid_port_for_consent_record():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="1.2.3.4:99999",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "127.0.0.1"


def test_registration_rejects_bracketed_ipv6_with_invalid_port_for_consent_record():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="[2606:4700:4700::1111]:99999",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == "127.0.0.1"


@pytest.mark.parametrize("forwarded_ip", ["10.0.0.1", "127.0.0.10", "fe80::1"])
def test_registration_accepts_non_global_forwarded_ip_for_consent_record(forwarded_ip):
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR=forwarded_ip,
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert consent.ip_address == forwarded_ip


def test_registration_normalizes_forwarded_ipv6_zone_id_for_consent_record():
    """IPv6 zone id нормализуется до canonical IP перед записью в audit."""
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        HTTP_X_FORWARDED_FOR="fe80::1%eth0",
        HTTP_USER_AGENT="ConsentTestAgent/1.0",
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert str(consent.ip_address) == "fe80::1"


def test_registration_logs_warning_when_remote_addr_is_unknown(caplog):
    client = APIClient()

    with caplog.at_level("WARNING", logger="apps.common.consent_audit"):
        response = post_register(
            client,
            trainer_payload(),
            REMOTE_ADDR="unknown",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert "Unknown client IP skipped for consent audit" in caplog.text


def test_registration_sanitizes_invalid_ip_before_warning_log(caplog):
    client = APIClient()
    invalid_ip = "bad\x00\u2028\u2029\u202e\u200b\r\nINJECT\x1b[31m"

    with caplog.at_level("WARNING", logger="apps.common.consent_audit"):
        response = post_register(
            client,
            trainer_payload(),
            HTTP_X_FORWARDED_FOR=f"{invalid_ip}, 5.6.7.8",
            REMOTE_ADDR="unknown",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    record = next(item for item in caplog.records if item.message == "Invalid client IP skipped for consent audit")
    assert record.client_ip == "bad\\x00\\u2028\\u2029\\u202e\\u200b\\r\\nINJECT\\x1b[31m"
    for unsafe_char in ["\x00", "\u2028", "\u2029", "\u202e", "\u200b", "\r", "\n", "\x1b"]:
        assert unsafe_char not in record.client_ip


def test_registration_sanitizes_surrogate_from_invalid_ip_warning_log(caplog):
    client = APIClient()
    invalid_ip = "bad\udcff\r\nINJECT"

    with caplog.at_level("WARNING", logger="apps.common.consent_audit"):
        response = post_register(
            client,
            trainer_payload(),
            HTTP_X_FORWARDED_FOR=f"{invalid_ip}, 5.6.7.8",
            REMOTE_ADDR="unknown",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    record = next(item for item in caplog.records if item.message == "Invalid client IP skipped for consent audit")
    assert record.client_ip == "bad\\r\\nINJECT"
    assert "\udcff" not in record.client_ip


def test_registration_does_not_split_escape_sequence_when_truncating_warning_log(caplog):
    client = APIClient()

    with caplog.at_level("WARNING", logger="apps.common.consent_audit"):
        response = post_register(
            client,
            trainer_payload(),
            HTTP_X_FORWARDED_FOR=("A" * 127) + "\r\n",
            REMOTE_ADDR="unknown",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    record = next(item for item in caplog.records if item.message == "Invalid client IP skipped for consent audit")
    assert len(record.client_ip) <= 128
    assert not record.client_ip.endswith("\\")


def test_registration_sanitizes_invalid_user_agent_surrogates():
    client = APIClient()

    response = post_register(
        client,
        trainer_payload(),
        REMOTE_ADDR="1.2.3.4",
        HTTP_USER_AGENT="Agent\udcff" + "A" * 600,
    )

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consent = UserConsent.objects.get(user=user)
    assert "\udcff" not in consent.user_agent
    expected_tail_length = 512 - len("Agent")
    assert consent.user_agent == "Agent" + "A" * expected_tail_length


def test_consent_records_have_default_policy_version():
    client = APIClient()

    response = post_register(client, trainer_payload(marketing_consent=True))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert set(UserConsent.objects.filter(user=user).values_list("policy_version", flat=True)) == {"1.0"}


# ---------------------------------------------------------------------------
# Story 41.9 — источник и версия текста согласия
# ---------------------------------------------------------------------------


def test_registration_consents_record_source_and_text_versions():
    """AC3 + AC4: обычная регистрация помечается источником `registration`,
    а версии ПДн и маркетинга различаются — это два разных чекбокса формы."""
    client = APIClient()

    response = post_register(client, trainer_payload(marketing_consent=True))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    consents = {consent.consent_type: consent for consent in UserConsent.objects.filter(user=user)}

    assert set(consents) == {"pdp_contract", "marketing_email"}
    assert {consent.source for consent in consents.values()} == {UserConsent.SOURCE_REGISTRATION}

    expected_pdp = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract")
    expected_marketing = current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "marketing_email")

    assert consents["pdp_contract"].consent_text_version == expected_pdp
    assert consents["marketing_email"].consent_text_version == expected_marketing
    # Чекбоксов в форме регистрации два, значит и версии обязаны различаться.
    assert expected_pdp != expected_marketing


def test_registration_never_records_unknown_source():
    """AC3: `unknown` зарезервирован за строками до миграции 0019.

    Ни одна запись, созданная кодом, не имеет права им помечаться.
    """
    client = APIClient()

    response = post_register(client, trainer_payload(marketing_consent=True))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    sources = set(UserConsent.objects.filter(user=user).values_list("source", flat=True))

    assert UserConsent.SOURCE_UNKNOWN not in sources
    assert all(source for source in sources)


# ---------------------------------------------------------------------------
# Story 41.2 — ветка привязки к записи 1С
#
# Ветка недостижима через HTTP с коммита ffee94d5 (2026-07-26): `validate()`
# больше не ищет `_matched_1c_customer`, поэтому никакой payload флаги
# `_pending_admin_review` / `_pending_link_confirmation` не выставит. Дефект
# латентный, и достать его можно только патчем `create()` — продовый код ради
# тестируемости не правится.
# ---------------------------------------------------------------------------


def _pending_create(flag_name: str):
    """
    Обёртка над настоящим `create()`: помечает результат флагом привязки к 1С.

    Транзакция, форма ответа и helper'ы IP/UA при этом исполняются боевые —
    подменяется только признак, по которому view раньше пропускал запись
    согласия.
    """
    original_create = UserRegistrationSerializer.create

    def create_with_pending(self, validated_data):
        user = original_create(self, validated_data)
        setattr(user, flag_name, True)
        return user

    return patch.object(UserRegistrationSerializer, "create", create_with_pending)


def _historic_link_create(customer: User):
    """
    Эмулирует `create()` до ffee94d5: возврат найденной записи 1С вместо нового `User`.

    Тело `create()` подменяется целиком, поэтому присваивание `_marketing_consent`,
    оставленное только в текущем теле, эта обёртка обойдёт. Ровно это и требуется
    проверить: флаг обязан жить на пути `_link_matched_1c_customer`, иначе
    вернувший привязку потеряет отметку рассылки молча.
    """

    def create_via_link(self, validated_data):
        validated_data.pop("password_confirm", None)
        password = validated_data.pop("password")
        return self._link_matched_1c_customer(customer, validated_data["email"], password)

    return patch.object(UserRegistrationSerializer, "create", create_via_link)


def make_1c_customer(**overrides) -> User:
    """Импортированная из 1С запись без портального аккаунта — источник привязки."""
    fields = {
        "email": unique_email("consent_1c_record"),
        "password": None,
        "first_name": "Контрагент",
        "last_name": "ИзОдинС",
        "role": User.ROLE_UNREGISTERED,
        "verification_status": "unverified",
        "created_in_1c": True,
        "company_name": "Импортированное ООО",
    }
    fields.update(overrides)
    return User.objects.create_user(**fields)


PENDING_LINK_MESSAGE = "Если данные совпадают с записью в 1С, дальнейшие инструкции отправлены на указанный email."


@pytest.mark.parametrize("flag_name", ["_pending_admin_review", "_pending_link_confirmation"])
def test_pending_1c_link_registration_creates_pdp_consent(flag_name):
    """AC1 + AC2: согласие пишется в ветке привязки, ответ и PII не меняются."""
    client = APIClient()
    payload = trainer_payload(marketing_consent=False)

    with _pending_create(flag_name):
        response = post_register(
            client,
            payload,
            REMOTE_ADDR="1.2.3.4",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    # AC2: ни access, ни refresh, ни объект user — PII записи 1С не раскрывается.
    assert set(response.data) == {"message"}
    assert response.data["message"] == PENDING_LINK_MESSAGE

    # Email берётся из payload: в ответе ветки привязки его нет.
    user = User.objects.get(email=payload["email"])
    consents = UserConsent.objects.filter(user=user)
    assert consents.count() == 1
    consent = consents.get()
    assert consent.consent_type == "pdp_contract"
    assert consent.ip_address == "1.2.3.4"
    assert consent.user_agent == "ConsentTestAgent/1.0"
    # policy_version остаётся константой: версионирование текста политики ПДн
    # в объём 41.9 не входило (см. deferred-work.md).
    assert consent.policy_version == "1.0"
    # Story 41.9: ветка привязки к 1С помечается своим источником, а текст —
    # тот же, что и при обычной регистрации: человек видел ту же форму.
    assert consent.source == UserConsent.SOURCE_1C_LINK
    assert consent.consent_text_version == current_consent_text_version(UserConsent.SOURCE_1C_LINK, "pdp_contract")
    assert consent.consent_text_version == current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract")


def test_pending_1c_link_registration_without_marketing_creates_single_consent():
    """AC3 негативный: без отметки рассылки — ровно одна запись."""
    client = APIClient()
    payload = trainer_payload(marketing_consent=False)

    with _pending_create("_pending_admin_review"):
        response = post_register(client, payload)

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=payload["email"])
    assert list(UserConsent.objects.filter(user=user).values_list("consent_type", flat=True)) == ["pdp_contract"]


def test_historic_1c_link_path_keeps_marketing_consent():
    """
    AC3 позитивный: отметка рассылки переживает возврат мёртвой ветки.

    Проверка идёт через `_historic_link_create`, а не через `_pending_create`:
    только она проходит по пути `_link_matched_1c_customer` и различает
    реализации Task 3.
    """
    client = APIClient()
    customer = make_1c_customer()
    payload = trainer_payload(marketing_consent=True)

    with (
        _historic_link_create(customer),
        patch("apps.users.serializers.send_portal_link_confirmation_email.delay"),
    ):
        response = post_register(
            client,
            payload,
            REMOTE_ADDR="1.2.3.4",
            HTTP_USER_AGENT="ConsentTestAgent/1.0",
        )

    assert response.status_code == status.HTTP_201_CREATED
    assert set(response.data) == {"message"}

    # Согласие крепится к объекту, который вернул serializer.save(), — то есть
    # к найденной записи 1С, а не к новому пользователю: его тут не создают.
    assert not User.objects.filter(email=payload["email"]).exists()
    consents = list(UserConsent.objects.filter(user=customer).order_by("consent_type"))
    assert {consent.consent_type for consent in consents} == {"pdp_contract", "marketing_email"}
    assert {consent.ip_address for consent in consents} == {"1.2.3.4"}
    assert {consent.user_agent for consent in consents} == {"ConsentTestAgent/1.0"}
    # Story 41.9: обе записи ветки привязки помечены источником `1c_link`,
    # а версии — те же, что у обычной регистрации (форма одна и та же).
    assert {consent.source for consent in consents} == {UserConsent.SOURCE_1C_LINK}
    assert {consent.consent_type: consent.consent_text_version for consent in consents} == {
        "pdp_contract": current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract"),
        "marketing_email": current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "marketing_email"),
    }


def test_historic_1c_link_path_without_marketing_creates_single_consent():
    """AC3 негативный на историческом пути: лишней записи рассылки не появляется."""
    client = APIClient()
    customer = make_1c_customer()
    payload = trainer_payload(marketing_consent=False)

    with (
        _historic_link_create(customer),
        patch("apps.users.serializers.send_portal_link_confirmation_email.delay"),
    ):
        response = post_register(client, payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert list(UserConsent.objects.filter(user=customer).values_list("consent_type", flat=True)) == ["pdp_contract"]


def test_consent_failure_rolls_back_pending_1c_link_registration():
    """
    AC5: сбой записи согласия откатывает регистрацию целиком.

    Постановка писем в очередь не проверяется намеренно: `.delay` вызывается
    внутри `create()`, Celery живёт вне транзакции, и при откате задачи уже
    поставлены. Это известное свойство кода, а не дефект стори.
    """
    client = APIClient()
    payload = trainer_payload()

    with _pending_create("_pending_admin_review"):
        with patch(
            "apps.users.views.authentication.UserConsent.objects.create",
            side_effect=DatabaseError("consent insert failed"),
        ):
            with pytest.raises(DatabaseError):
                post_register(client, payload)

    assert not User.objects.filter(email=payload["email"]).exists()
    assert not UserConsent.objects.filter(user__email=payload["email"]).exists()

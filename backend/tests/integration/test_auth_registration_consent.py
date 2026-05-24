from __future__ import annotations

import time
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import UserConsent
from apps.users.models import User


pytestmark = [pytest.mark.integration, pytest.mark.django_db]


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}@example.com"


def retail_payload(**overrides):
    payload = {
        "email": unique_email("consent_retail"),
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "first_name": "Consent",
        "last_name": "Retail",
        "role": "retail",
        "pdp_consent": True,
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
        "tax_id": "1234567890",
        "pdp_consent": True,
        "marketing_consent": False,
    }
    payload.update(overrides)
    return payload


def post_register(client: APIClient, payload: dict, **headers):
    return client.post("/api/v1/auth/register/", payload, format="json", **headers)


def test_registration_requires_pdp_consent():
    client = APIClient()
    payload = retail_payload()
    payload.pop("pdp_consent")

    response = post_register(client, payload)

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pdp_consent" in response.data
    assert response.data["pdp_consent"] == ["Необходимо согласие на обработку персональных данных."]


def test_registration_rejects_pdp_consent_false():
    client = APIClient()

    response = post_register(client, retail_payload(pdp_consent=False))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "pdp_consent" in response.data


@pytest.mark.parametrize("invalid_value", ["not-bool", None])
def test_registration_rejects_invalid_pdp_consent_with_contract_message(invalid_value):
    client = APIClient()

    response = post_register(client, retail_payload(pdp_consent=invalid_value))

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["pdp_consent"] == ["Необходимо согласие на обработку персональных данных."]


@pytest.mark.parametrize("truthy_value", [1, "yes", "on", "t"])
def test_registration_accepts_drf_truthy_pdp_consent_values_by_decision(truthy_value):
    client = APIClient()

    response = post_register(client, retail_payload(pdp_consent=truthy_value))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert UserConsent.objects.filter(user=user, consent_type="pdp_contract").exists()


def test_retail_registration_creates_pdp_consent_record():
    client = APIClient()

    response = post_register(
        client,
        retail_payload(marketing_consent=False),
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


def test_retail_registration_with_marketing_creates_two_records():
    client = APIClient()

    response = post_register(
        client,
        retail_payload(marketing_consent=True),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
        retail_payload(),
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
            retail_payload(),
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
            retail_payload(),
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
            retail_payload(),
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
            retail_payload(),
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
        retail_payload(),
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

    response = post_register(client, retail_payload(marketing_consent=True))

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=response.data["user"]["email"])
    assert set(UserConsent.objects.filter(user=user).values_list("policy_version", flat=True)) == {"1.0"}

"""
Тесты модели UserConsent.
"""

from datetime import UTC, datetime

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import RequestFactory
from django.utils import timezone

from apps.common.admin import UserConsentAdmin
from apps.common.models import UserConsent


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


User = get_user_model()


def test_create_pdp_contract_consent_for_user():
    user = User.objects.create_user(
        email="pdp@example.com",
        password="test-password",
    )

    consent = UserConsent.objects.create(
        user=user,
        consent_type="pdp_contract",
        ip_address="192.168.1.10",
        user_agent="pytest",
    )

    assert consent.user == user
    assert consent.consent_type == "pdp_contract"
    assert consent.policy_version == "1.0"
    assert consent.given_at is not None


def test_create_marketing_email_consent_for_user():
    user = User.objects.create_user(
        email="marketing@example.com",
        password="test-password",
    )

    consent = UserConsent.objects.create(
        user=user,
        consent_type="marketing_email",
        ip_address="192.168.1.11",
        user_agent="pytest",
        policy_version="1.1",
    )

    assert consent.user == user
    assert consent.consent_type == "marketing_email"
    assert consent.policy_version == "1.1"


def test_create_anonymous_consent_with_session_key():
    consent = UserConsent.objects.create(
        session_key="anonymous-session-key-1234567890",
        consent_type="pdp_contract",
        ip_address="127.0.0.1",
    )

    assert consent.user is None
    assert consent.session_key == "anonymous-session-key-1234567890"


def test_user_consent_requires_user_or_session_key():
    with pytest.raises(IntegrityError):
        UserConsent.objects.create(
            user=None,
            session_key="",
            consent_type="pdp_contract",
        )


def test_user_consent_str_for_user():
    user = User.objects.create_user(
        email="str@example.com",
        password="test-password",
    )
    consent = UserConsent.objects.create(
        user=user,
        consent_type="pdp_contract",
    )

    result = str(consent)

    assert "str@example.com" in result
    assert "Согласие на обработку ПДн для исполнения договора" in result


def test_user_consent_str_for_anonymous_without_session_key_has_no_empty_parentheses():
    consent = UserConsent(
        consent_type="pdp_contract",
        given_at=timezone.now(),
    )

    result = str(consent)

    assert "аноним ()" not in result
    assert result.startswith("аноним —")


def test_user_consent_str_for_short_session_key():
    consent = UserConsent.objects.create(
        session_key="short",
        consent_type="marketing_email",
    )

    result = str(consent)

    assert result.startswith("аноним (short)")


def test_user_consent_str_uses_current_timezone():
    consent = UserConsent.objects.create(
        session_key="timezone-session",
        consent_type="pdp_contract",
    )
    consent.given_at = datetime(2026, 5, 9, 22, 30, tzinfo=UTC)
    consent.save(update_fields=["given_at"])

    with timezone.override("Europe/Moscow"):
        result = str(consent)

    assert "10.05.2026" in result


def test_user_consent_requires_consent_type():
    consent = UserConsent(session_key="anonymous", consent_type="")

    with pytest.raises(ValidationError):
        consent.full_clean()


def test_user_consent_hot_fields_are_indexed_and_user_agent_is_bounded():
    assert UserConsent._meta.get_field("session_key").db_index is True
    assert UserConsent._meta.get_field("consent_type").db_index is True
    assert UserConsent._meta.get_field("given_at").db_index is True
    assert UserConsent._meta.get_field("user_agent").max_length == 512


def test_user_consent_admin_is_read_only():
    request = RequestFactory().get("/admin/common/userconsent/")
    request.user = User.objects.create_superuser(
        email="admin@example.com",
        password="test-password",
    )
    model_admin = UserConsentAdmin(UserConsent, admin.site)

    assert model_admin.has_add_permission(request) is False
    assert model_admin.has_change_permission(request) is False
    assert model_admin.has_delete_permission(request) is False
    assert model_admin.search_fields == ["user__email"]
    assert model_admin.readonly_fields == [
        "user",
        "session_key",
        "consent_type",
        "given_at",
        "ip_address",
        "user_agent",
        "policy_version",
    ]


def test_user_consent_admin_excludes_delete_selected_action():
    request = RequestFactory().get("/admin/common/userconsent/")
    request.user = User.objects.create_superuser(
        email="admin-actions@example.com",
        password="test-password",
    )
    model_admin = UserConsentAdmin(UserConsent, admin.site)

    actions = model_admin.get_actions(request)

    assert "delete_selected" not in actions

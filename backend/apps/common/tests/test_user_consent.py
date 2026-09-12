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
from apps.common.consent_texts import current_consent_text_version
from apps.common.models import UserConsent


pytestmark = [pytest.mark.django_db, pytest.mark.unit]


User = get_user_model()


def audit_fields(consent_type: str = "pdp_contract", source: str = UserConsent.SOURCE_REGISTRATION) -> dict:
    """Обязательные с стори 41.9 поля аудита: источник и версия показанного текста.

    Значения берутся из реестра, а не литералом: тест обязан ломаться вместе
    с реестром, а не расходиться с ним молча. Без этих полей вставка падает
    на CheckConstraint — это работающая защита, а не сломанный тест.
    """
    return {
        "source": source,
        "consent_text_version": current_consent_text_version(source, consent_type),
    }


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
        **audit_fields("pdp_contract"),
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
        **audit_fields("marketing_email"),
    )

    assert consent.user == user
    assert consent.consent_type == "marketing_email"
    assert consent.policy_version == "1.1"


def test_create_anonymous_consent_with_session_key():
    consent = UserConsent.objects.create(
        session_key="anonymous-session-key-1234567890",
        consent_type="pdp_contract",
        ip_address="127.0.0.1",
        **audit_fields("pdp_contract", UserConsent.SOURCE_NEWSLETTER),
    )

    assert consent.user is None
    assert consent.session_key == "anonymous-session-key-1234567890"


def test_user_consent_requires_user_or_session_key():
    with pytest.raises(IntegrityError):
        UserConsent.objects.create(
            user=None,
            session_key="",
            consent_type="pdp_contract",
            **audit_fields("pdp_contract"),
        )


def test_user_consent_str_for_user():
    user = User.objects.create_user(
        email="str@example.com",
        password="test-password",
    )
    consent = UserConsent.objects.create(
        user=user,
        consent_type="pdp_contract",
        **audit_fields("pdp_contract"),
    )

    result = str(consent)

    assert "str@example.com" in result
    assert "Согласие на обработку ПДн для исполнения договора" in result


def test_user_consent_str_for_anonymous_without_session_key_has_no_empty_parentheses():
    consent = UserConsent(
        consent_type="pdp_contract",
        given_at=timezone.now(),
        **audit_fields("pdp_contract"),
    )

    result = str(consent)

    assert "аноним ()" not in result
    assert result.startswith("аноним —")


def test_user_consent_str_for_short_session_key():
    consent = UserConsent.objects.create(
        session_key="short",
        consent_type="marketing_email",
        **audit_fields("marketing_email", UserConsent.SOURCE_NEWSLETTER),
    )

    result = str(consent)

    assert result.startswith("аноним (short)")


def test_user_consent_str_uses_current_timezone():
    consent = UserConsent.objects.create(
        session_key="timezone-session",
        consent_type="pdp_contract",
        **audit_fields("pdp_contract", UserConsent.SOURCE_NEWSLETTER),
    )
    consent.given_at = datetime(2026, 5, 9, 22, 30, tzinfo=UTC)
    consent.save(update_fields=["given_at"])

    with timezone.override("Europe/Moscow"):
        result = str(consent)

    assert "10.05.2026" in result


def test_user_consent_requires_consent_type():
    consent = UserConsent(session_key="anonymous", consent_type="", **audit_fields("pdp_contract"))

    with pytest.raises(ValidationError):
        consent.full_clean()


def test_user_consent_hot_fields_are_indexed_and_user_agent_is_bounded():
    assert UserConsent._meta.get_field("session_key").db_index is True  # type: ignore[attr-defined]
    assert UserConsent._meta.get_field("consent_type").db_index is True  # type: ignore[attr-defined]
    assert UserConsent._meta.get_field("given_at").db_index is True  # type: ignore[attr-defined]
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
        "source",
        "consent_text_version",
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


# ---------------------------------------------------------------------------
# Story 41.9 — источник и версия текста согласия
# ---------------------------------------------------------------------------


def test_source_choices_include_reserved_unknown():
    """`unknown` остаётся в choices: им помечены строки, созданные до миграции 0019."""
    values = [value for value, _label in UserConsent.SOURCE_CHOICES]

    assert values == [
        UserConsent.SOURCE_NEWSLETTER,
        UserConsent.SOURCE_REGISTRATION,
        UserConsent.SOURCE_1C_LINK,
        UserConsent.SOURCE_UNKNOWN,
    ]
    assert UserConsent.SOURCE_UNKNOWN == "unknown"


def test_audit_fields_have_no_model_default():
    """Отсутствие `default` — суть защиты: забытое значение обязано ронять вставку.

    С `default="unknown"` код, забывший передать источник, тихо записал бы
    «неизвестно» — ровно та беда, которую чинит стори 41.9.
    """
    assert UserConsent._meta.get_field("source").has_default() is False
    assert UserConsent._meta.get_field("consent_text_version").has_default() is False


def test_audit_fields_are_indexed_and_bounded():
    """Оба поля участвуют в фильтрах админки и compliance-запросах."""
    source_field = UserConsent._meta.get_field("source")
    version_field = UserConsent._meta.get_field("consent_text_version")

    # django-stubs 4.2 не знает `db_index` у возвращаемого `get_field` типа —
    # точечный ignore, чтобы не наращивать базис ошибок mypy (AC7).
    assert source_field.db_index is True  # type: ignore[attr-defined]
    assert source_field.max_length == 20
    assert version_field.db_index is True  # type: ignore[attr-defined]
    assert version_field.max_length == 64


def test_empty_source_violates_check_constraint():
    """Пустой источник падает на CheckConstraint, а не пишет тихий мусор."""
    with pytest.raises(IntegrityError):
        UserConsent.objects.create(
            session_key="constraint-source-session",
            consent_type="pdp_contract",
            source="",
            consent_text_version=current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract"),
        )


def test_source_outside_choices_violates_check_constraint():
    """Опечатка в источнике падает на вставке, а не ложится в журнал молча.

    `choices` в Django проверяются формами и `full_clean()`; прямой
    `objects.create(source="registartion")` их не касается, поэтому
    перечисление продублировано ограничением уровня БД.
    """
    with pytest.raises(IntegrityError):
        UserConsent.objects.create(
            session_key="constraint-source-typo-session",
            consent_type="pdp_contract",
            source="registartion",
            consent_text_version=current_consent_text_version(UserConsent.SOURCE_REGISTRATION, "pdp_contract"),
        )


def test_source_values_match_choices():
    """Список для CheckConstraint не расходится с перечислением модели.

    Он объявлен на уровне модуля (тело `class Meta` не видит пространство имён
    внешнего класса), поэтому синхронность держится тестом, а не языком.
    """
    assert UserConsent.SOURCE_VALUES == [value for value, _label in UserConsent.SOURCE_CHOICES]


def test_empty_consent_text_version_violates_check_constraint():
    """Пустая версия текста падает на CheckConstraint."""
    with pytest.raises(IntegrityError):
        UserConsent.objects.create(
            session_key="constraint-version-session",
            consent_type="pdp_contract",
            source=UserConsent.SOURCE_REGISTRATION,
            consent_text_version="",
        )


def test_check_constraints_are_declared_on_model():
    """Оба ограничения объявлены в Meta — иначе миграция и модель разойдутся."""
    names = {constraint.name for constraint in UserConsent._meta.constraints}

    assert {
        "userconsent_user_or_session_required",
        "userconsent_source_valid",
        "userconsent_text_version_required",
    } <= names


def test_admin_shows_source_and_version_in_list_and_filters():
    """AC6: оператор видит источник и версию в списке и может фильтровать по ним."""
    model_admin = UserConsentAdmin(UserConsent, admin.site)

    assert "source" in model_admin.list_display
    assert "consent_text_version" in model_admin.list_display
    assert "source" in model_admin.list_filter
    assert "consent_text_version" in model_admin.list_filter

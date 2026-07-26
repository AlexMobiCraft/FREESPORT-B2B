"""Unit-тесты системных проверок приложения common."""

import pytest
from django.conf import settings
from django.core.checks import Tags, run_checks
from django.test import override_settings

from apps.common.apps import check_session_engine_for_subscribe_consent

pytestmark = pytest.mark.unit


def test_session_engine_check_accepts_db_sessions():
    """DB-backed sessions поддерживают session_key для анонимного consent audit."""
    with override_settings(SESSION_ENGINE="django.contrib.sessions.backends.db"):
        errors = check_session_engine_for_subscribe_consent(None)

    assert errors == []


def test_session_engine_check_rejects_signed_cookie_sessions():
    """signed_cookies не создают session_key для anonymous UserConsent."""
    with override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies"):
        errors = check_session_engine_for_subscribe_consent(None)

    assert len(errors) == 1
    assert errors[0].id == "common.E001"


def test_subscribe_throttle_scope_check_rejects_missing_rate():
    rest_framework = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            key: value for key, value in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].items() if key != "subscribe"
        },
    }
    with override_settings(REST_FRAMEWORK=rest_framework):
        errors = check_session_engine_for_subscribe_consent(None)

    assert len(errors) == 1
    assert errors[0].id == "common.E002"


def test_unsubscribe_throttle_scope_check_rejects_missing_rate():
    rest_framework = {
        **settings.REST_FRAMEWORK,
        "DEFAULT_THROTTLE_RATES": {
            key: value
            for key, value in settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"].items()
            if key != "unsubscribe"
        },
    }
    with override_settings(REST_FRAMEWORK=rest_framework):
        errors = check_session_engine_for_subscribe_consent(None)

    assert len(errors) == 1
    assert errors[0].id == "common.E003"


def test_session_engine_check_is_visible_under_security_tag():
    with override_settings(SESSION_ENGINE="django.contrib.sessions.backends.signed_cookies"):
        errors = run_checks(tags=[Tags.security])

    assert any(error.id == "common.E001" for error in errors)

"""Подписка на рассылку при регистрации и отписка из личного кабинета.

Рассылка уходит только активным `Newsletter`, поэтому регистрация с согласием
обязана создать (или реактивировать) подписку, а кабинет — уметь её снять.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.db import DatabaseError
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Newsletter, UserConsent
from apps.common.services.marketing_email import MarketingDeliveryService, TestMarketingTransport
from apps.common.services.newsletter_subscription import activate_newsletter_subscription
from apps.users.models import User
from tests.integration.test_auth_registration_consent import (  # noqa: F401 — autouse-фикстура
    _mute_b2b_notification_tasks,
    _pending_create,
    post_register,
    trainer_payload,
    unique_email,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

ME_URL = "/api/v1/newsletter/me/"
ME_UNSUBSCRIBE_URL = "/api/v1/newsletter/me/unsubscribe/"


def make_user(email: str | None = None) -> User:
    return User.objects.create_user(
        email=email or unique_email("newsletter_me"),
        password="StrongPassword123!",
        role="trainer",
    )


def auth_client(user: User) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=user)
    return client


# --- Сервис activate_newsletter_subscription --------------------------------


def test_service_creates_active_subscription_linked_to_user():
    user = make_user()

    subscription = activate_newsletter_subscription(user.email, "1.2.3.4", "Agent/1.0", user=user)

    assert subscription.is_active is True
    assert subscription.user_id == user.id
    assert subscription.ip_address == "1.2.3.4"


def test_service_reactivates_unsubscribed_email_with_new_token():
    user = make_user()
    old = Newsletter.objects.create(email=user.email)
    old.unsubscribe()
    old_token = old.unsubscribe_token

    subscription = activate_newsletter_subscription(user.email, "5.6.7.8", "Agent/2.0", user=user)

    subscription.refresh_from_db()
    assert subscription.pk == old.pk
    assert subscription.is_active is True
    assert subscription.unsubscribed_at is None
    assert subscription.unsubscribe_token != old_token
    assert subscription.user_id == user.id


def test_service_keeps_existing_user_link():
    owner = make_user()
    other = make_user()
    Newsletter.objects.create(email=owner.email, user=owner)

    subscription = activate_newsletter_subscription(owner.email, None, "", user=other)

    subscription.refresh_from_db()
    assert subscription.user_id == owner.id


def test_service_rotates_token_of_active_subscription():
    existing = Newsletter.objects.create(email=unique_email("active"))
    old_token = existing.unsubscribe_token

    subscription = activate_newsletter_subscription(existing.email, None, "")

    subscription.refresh_from_db()
    assert subscription.is_active is True
    assert subscription.unsubscribe_token != old_token


# --- Регистрация -------------------------------------------------------------


def test_registration_with_marketing_consent_creates_subscription():
    payload = trainer_payload(marketing_consent=True)

    response = post_register(APIClient(), payload)

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=payload["email"])
    subscription = Newsletter.objects.get(email=payload["email"].lower())
    assert subscription.is_active is True
    assert subscription.user_id == user.id
    assert UserConsent.objects.filter(user=user, consent_type="marketing_email").count() == 1


def test_registration_without_marketing_consent_creates_no_subscription():
    payload = trainer_payload(marketing_consent=False)

    response = post_register(APIClient(), payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert not Newsletter.objects.filter(email=payload["email"].lower()).exists()


def test_registration_with_marketing_consent_reactivates_unsubscribed_email():
    payload = trainer_payload(marketing_consent=True)
    old = Newsletter.objects.create(email=payload["email"].lower())
    old.unsubscribe()

    response = post_register(APIClient(), payload)

    assert response.status_code == status.HTTP_201_CREATED
    old.refresh_from_db()
    assert old.is_active is True
    assert old.unsubscribed_at is None
    assert old.user_id == User.objects.get(email=payload["email"]).id


def test_registration_rolls_back_when_subscription_fails():
    payload = trainer_payload(marketing_consent=True)

    with patch(
        "apps.users.views.authentication.activate_newsletter_subscription",
        side_effect=DatabaseError("newsletter insert failed"),
    ):
        with pytest.raises(DatabaseError):
            post_register(APIClient(), payload)

    assert not User.objects.filter(email=payload["email"]).exists()
    assert not UserConsent.objects.filter(user__email=payload["email"]).exists()


def test_pending_admin_review_registration_creates_subscription():
    payload = trainer_payload(marketing_consent=True)

    with _pending_create("_pending_admin_review"):
        response = post_register(APIClient(), payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert Newsletter.objects.filter(email=payload["email"].lower(), is_active=True).exists()


def test_pending_link_confirmation_registration_skips_subscription():
    """Email записи 1С отличается от адреса формы — чужой адрес не подписывается."""
    payload = trainer_payload(marketing_consent=True)

    with _pending_create("_pending_link_confirmation"):
        response = post_register(APIClient(), payload)

    assert response.status_code == status.HTTP_201_CREATED
    assert not Newsletter.objects.filter(email__iexact=payload["email"]).exists()
    # Согласие при этом в журнале остаётся: галочку человек поставил.
    assert UserConsent.objects.filter(user__email=payload["email"], consent_type="marketing_email").count() == 1


# --- Эндпоинты кабинета ------------------------------------------------------


@pytest.mark.parametrize(
    ("state", "expected"),
    [("active", True), ("inactive", False), ("missing", False)],
)
def test_newsletter_me_reports_status(state, expected):
    user = make_user()
    if state != "missing":
        subscription = Newsletter.objects.create(email=user.email)
        if state == "inactive":
            subscription.unsubscribe()

    response = auth_client(user).get(ME_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"subscribed": expected}


def test_newsletter_me_matches_email_case_insensitively():
    user = make_user(email=unique_email("MiXeD.Case").replace("example.com", "Example.COM"))
    # Историческая строка в смешанном регистре — `create()` обходит нормализацию.
    Newsletter.objects.create(email=user.email.upper())

    response = auth_client(user).get(ME_URL)

    assert response.json() == {"subscribed": True}


def test_unsubscribe_from_profile_deactivates_subscription_and_suppresses_delivery():
    user = make_user()
    subscription = Newsletter.objects.create(email=user.email)

    response = auth_client(user).post(ME_UNSUBSCRIBE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"subscribed": False}
    subscription.refresh_from_db()
    assert subscription.is_active is False
    assert subscription.unsubscribed_at is not None
    result = MarketingDeliveryService(TestMarketingTransport()).deliver(subscription.id, "campaign", "Тема")
    assert result.status == "suppressed"


def test_subscription_linked_to_user_is_found_after_email_change():
    """Подписка на прежний адрес остаётся привязанной к пользователю и отзывается из кабинета."""
    user = make_user()
    subscription = Newsletter.objects.create(email=unique_email("previous_address"), user=user)
    client = auth_client(user)

    assert client.get(ME_URL).json() == {"subscribed": True}

    client.post(ME_UNSUBSCRIBE_URL)

    subscription.refresh_from_db()
    assert subscription.is_active is False


def test_newsletter_me_database_error_returns_503():
    user = make_user()

    with patch("apps.common.views.is_user_subscribed", side_effect=DatabaseError("db down")):
        response = auth_client(user).get(ME_URL)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE


def test_unsubscribe_from_profile_keeps_consent_journal():
    user = make_user()
    Newsletter.objects.create(email=user.email)
    UserConsent.objects.create(
        user=user,
        consent_type="marketing_email",
        source=UserConsent.SOURCE_REGISTRATION,
        consent_text_version="2026-09-21-registration-b96d601aed0fd4809c3b0fa3171c1b45",
    )

    auth_client(user).post(ME_UNSUBSCRIBE_URL)

    assert UserConsent.objects.filter(user=user, consent_type="marketing_email").count() == 1


def test_repeated_unsubscribe_keeps_first_unsubscribe_date():
    user = make_user()
    subscription = Newsletter.objects.create(email=user.email)
    client = auth_client(user)
    client.post(ME_UNSUBSCRIBE_URL)
    subscription.refresh_from_db()
    first_unsubscribed_at = subscription.unsubscribed_at

    response = client.post(ME_UNSUBSCRIBE_URL)

    assert response.status_code == status.HTTP_200_OK
    subscription.refresh_from_db()
    assert subscription.unsubscribed_at == first_unsubscribed_at


def test_unsubscribe_without_subscription_is_neutral_success():
    user = make_user()

    response = auth_client(user).post(ME_UNSUBSCRIBE_URL)

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"subscribed": False}
    assert not Newsletter.objects.filter(email__iexact=user.email).exists()


def test_unsubscribe_ignores_email_from_request_body():
    user = make_user()
    stranger = Newsletter.objects.create(email=unique_email("stranger"))

    auth_client(user).post(ME_UNSUBSCRIBE_URL, {"email": stranger.email}, format="json")

    stranger.refresh_from_db()
    assert stranger.is_active is True


def test_unsubscribe_database_error_returns_503():
    user = make_user()

    with patch("apps.common.views.unsubscribe_user", side_effect=DatabaseError("db down")):
        response = auth_client(user).post(ME_UNSUBSCRIBE_URL)

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["error"] == "unsubscribe_processing_failed"


@pytest.mark.parametrize(("method", "url"), [("get", ME_URL), ("post", ME_UNSUBSCRIBE_URL)])
def test_newsletter_me_endpoints_require_authentication(method, url):
    response = getattr(APIClient(), method)(url)

    assert response.status_code == status.HTTP_401_UNAUTHORIZED

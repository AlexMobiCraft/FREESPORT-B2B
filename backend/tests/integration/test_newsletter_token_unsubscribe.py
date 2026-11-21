"""Интеграционные тесты token-based отписки от маркетинговой рассылки."""

import re
from concurrent.futures import ThreadPoolExecutor
from importlib import import_module
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from django.db import OperationalError, close_old_connections, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Newsletter
from apps.common.services.marketing_email import (
    MarketingDeliveryService,
    MarketingMessageBuilder,
    NewsletterRecipientSource,
    TestMarketingTransport,
)
from tests.integration.test_common_subscribe_api import subscribe_payload

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
INVALID_TOKEN_RESPONSE = {"error": "invalid_or_expired_unsubscribe_token"}


class TestNewsletterUnsubscribeToken:
    def test_new_subscription_gets_opaque_urlsafe_token(self):
        subscription = Newsletter.objects.create(email="token-format@example.com")

        assert TOKEN_PATTERN.fullmatch(subscription.unsubscribe_token)
        assert "token-format" not in subscription.unsubscribe_token
        assert "@" not in subscription.unsubscribe_token

    def test_tokens_are_unique(self):
        first = Newsletter.objects.create(email="token-first@example.com")
        second = Newsletter.objects.create(email="token-second@example.com")

        assert first.unsubscribe_token != second.unsubscribe_token

    def test_each_explicit_consent_rotates_token(self, api_client):
        subscription = Newsletter.objects.create(email="rotate-active@example.com")
        old_token = subscription.unsubscribe_token

        response = api_client.post(
            reverse("common:subscribe"),
            subscribe_payload(subscription.email),
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription.refresh_from_db()
        assert subscription.unsubscribe_token != old_token
        assert TOKEN_PATTERN.fullmatch(subscription.unsubscribe_token)

    def test_reactivation_rotates_token_and_old_link_is_invalid(self, api_client):
        subscription = Newsletter.objects.create(
            email="rotate-reactivated@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )
        old_token = subscription.unsubscribe_token

        response = api_client.post(
            reverse("common:subscribe"),
            subscribe_payload(subscription.email),
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription.refresh_from_db()
        assert subscription.unsubscribe_token != old_token
        old_response = api_client.post(
            reverse("common:newsletter-unsubscribe"),
            {"token": old_token},
            format="json",
        )
        assert old_response.status_code == status.HTTP_400_BAD_REQUEST
        assert old_response.json() == INVALID_TOKEN_RESPONSE


class TestNewsletterTokenUnsubscribeEndpoint:
    def test_active_subscription_is_deactivated_without_email_in_response(self, api_client):
        subscription = Newsletter.objects.create(email="token-unsubscribe@example.com")

        response = api_client.post(
            reverse("common:newsletter-unsubscribe"),
            {"token": subscription.unsubscribe_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "processed"}
        assert subscription.email not in response.content.decode()
        subscription.refresh_from_db()
        assert subscription.is_active is False
        assert subscription.unsubscribed_at is not None

    def test_repeat_is_neutral_and_preserves_first_unsubscribed_at(self, api_client):
        first_unsubscribed_at = timezone.now()
        subscription = Newsletter.objects.create(
            email="token-repeat@example.com",
            is_active=False,
            unsubscribed_at=first_unsubscribed_at,
        )
        url = reverse("common:newsletter-unsubscribe")

        first = api_client.post(url, {"token": subscription.unsubscribe_token}, format="json")
        second = api_client.post(url, {"token": subscription.unsubscribe_token}, format="json")

        assert first.status_code == second.status_code == status.HTTP_200_OK
        assert first.json() == second.json() == {"status": "processed"}
        subscription.refresh_from_db()
        assert subscription.unsubscribed_at == first_unsubscribed_at

    @pytest.mark.parametrize("payload", [{}, {"token": None}, {"token": ""}, {"token": "bad"}, {"token": "x" * 43}])
    def test_invalid_unknown_and_missing_tokens_share_one_response(self, api_client, payload):
        response = api_client.post(reverse("common:newsletter-unsubscribe"), payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == INVALID_TOKEN_RESPONSE

    def test_expired_jwt_is_ignored(self, api_client):
        subscription = Newsletter.objects.create(email="expired-jwt@example.com")
        api_client.credentials(HTTP_AUTHORIZATION="Bearer expired.jwt.value")

        response = api_client.post(
            reverse("common:newsletter-unsubscribe"),
            {"token": subscription.unsubscribe_token},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "processed"}

    def test_row_is_locked_during_unsubscribe(self, api_client):
        subscription = Newsletter.objects.create(email="locked-token@example.com")

        with CaptureQueriesContext(connection) as queries:
            response = api_client.post(
                reverse("common:newsletter-unsubscribe"),
                {"token": subscription.unsubscribe_token},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert any(" FOR UPDATE" in query["sql"].upper() for query in queries.captured_queries)

    def test_database_failure_is_not_reported_as_success(self, api_client):
        subscription = Newsletter.objects.create(email="token-db-failure@example.com")

        with patch(
            "apps.common.services.newsletter_unsubscribe.Newsletter.objects.select_for_update",
            side_effect=OperationalError("db unavailable"),
        ):
            response = api_client.post(
                reverse("common:newsletter-unsubscribe"),
                {"token": subscription.unsubscribe_token},
                format="json",
            )

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.json() == {
            "error": "unsubscribe_processing_failed",
            "details": {"non_field_errors": ["Не удалось обработать запрос. Попробуйте позже."]},
        }

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_posts_are_serialized_and_idempotent(self):
        subscription = Newsletter.objects.create(email="concurrent-token@example.com")
        url = reverse("common:newsletter-unsubscribe")
        barrier = Barrier(2)

        def unsubscribe_once() -> tuple[int, dict]:
            close_old_connections()
            client = APIClient()
            barrier.wait(timeout=5)
            response = client.post(url, {"token": subscription.unsubscribe_token}, format="json")
            result = response.status_code, response.json()
            close_old_connections()
            return result

        with ThreadPoolExecutor(max_workers=2) as executor:
            responses = list(executor.map(lambda _: unsubscribe_once(), range(2)))

        assert responses == [(status.HTTP_200_OK, {"status": "processed"})] * 2
        subscription.refresh_from_db()
        assert subscription.is_active is False
        assert subscription.unsubscribed_at is not None


class TestNewsletterStageOneChain:
    def test_template_api_database_and_prepared_queue_suppression(self, api_client, settings):
        settings.SITE_URL = "https://optisport.example"
        subscription = Newsletter.objects.create(email="stage-one-chain@example.com")
        prepared_recipient_ids = NewsletterRecipientSource().recipient_ids()
        message = MarketingMessageBuilder().build(
            subscription=subscription,
            campaign_id="stage-one-chain",
            subject="Тестовая рассылка",
        )
        transport = TestMarketingTransport()

        assert prepared_recipient_ids == [subscription.id]
        assert f"/unsubscribe#{subscription.unsubscribe_token}" in message.html_body
        response = api_client.post(
            reverse("common:newsletter-unsubscribe"),
            {"token": subscription.unsubscribe_token},
            format="json",
        )
        delivery = MarketingDeliveryService(transport=transport).deliver(
            recipient_ref=prepared_recipient_ids[0],
            campaign_id="stage-one-chain",
            subject="Тестовая рассылка",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription.refresh_from_db()
        assert subscription.is_active is False
        assert NewsletterRecipientSource().recipient_ids() == []
        assert delivery.status == "suppressed"
        assert transport.messages == []


class TestNewsletterTokenMigration:
    def test_existing_rows_receive_distinct_urlsafe_tokens(self):
        rows = [
            SimpleNamespace(unsubscribe_token=None, save=Mock()),
            SimpleNamespace(unsubscribe_token=None, save=Mock()),
        ]

        class Query:
            def iterator(self):
                return iter(rows)

        manager = Mock()
        manager.filter.return_value = Query()
        historical_newsletter = SimpleNamespace(objects=manager)
        historical_apps = Mock()
        historical_apps.get_model.return_value = historical_newsletter
        migration = import_module("apps.common.migrations.0021_newsletter_unsubscribe_token")

        migration.populate_unsubscribe_tokens(historical_apps, None)

        assert all(TOKEN_PATTERN.fullmatch(row.unsubscribe_token) for row in rows)
        assert rows[0].unsubscribe_token != rows[1].unsubscribe_token
        for row in rows:
            row.save.assert_called_once_with(update_fields=["unsubscribe_token"])


class TestNewsletterOneClickEndpoint:
    def test_get_is_safe_and_does_not_change_subscription(self, api_client):
        subscription = Newsletter.objects.create(email="one-click-get@example.com")
        url = reverse("common:newsletter-unsubscribe-one-click", args=[subscription.unsubscribe_token])

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "confirmation_required"}
        subscription.refresh_from_db()
        assert subscription.is_active is True
        assert subscription.unsubscribed_at is None

    def test_exact_rfc8058_post_unsubscribes(self, api_client):
        subscription = Newsletter.objects.create(email="one-click-post@example.com")
        url = reverse("common:newsletter-unsubscribe-one-click", args=[subscription.unsubscribe_token])

        response = api_client.post(
            url,
            "List-Unsubscribe=One-Click",
            content_type="application/x-www-form-urlencoded",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {"status": "processed"}
        subscription.refresh_from_db()
        assert subscription.is_active is False

    @pytest.mark.parametrize(
        "body",
        ["", "List-Unsubscribe=one-click", "List-Unsubscribe=One-Click&extra=value"],
    )
    def test_non_exact_rfc8058_body_is_rejected(self, api_client, body):
        subscription = Newsletter.objects.create(email=f"one-click-invalid-{len(body)}@example.com")
        url = reverse("common:newsletter-unsubscribe-one-click", args=[subscription.unsubscribe_token])

        response = api_client.post(url, body, content_type="application/x-www-form-urlencoded")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == INVALID_TOKEN_RESPONSE
        subscription.refresh_from_db()
        assert subscription.is_active is True

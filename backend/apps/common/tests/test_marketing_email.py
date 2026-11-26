"""Тесты локального контракта маркетинговой отправки."""

import pytest

from apps.common.models import Newsletter
from apps.common.services.marketing_email import (
    MarketingDeliveryService,
    MarketingMessageBuilder,
    NewsletterRecipientSource,
    TestMarketingTransport,
)

pytestmark = pytest.mark.django_db


class TestNewsletterRecipientSource:
    def test_returns_only_active_newsletter_ids(self):
        active = Newsletter.objects.create(email="active-recipient@example.com")
        Newsletter.objects.create(email="inactive-recipient@example.com", is_active=False)

        recipient_ids = NewsletterRecipientSource().recipient_ids()

        assert recipient_ids == [active.id]
        assert all(isinstance(recipient_id, int) for recipient_id in recipient_ids)


class TestMarketingMessageBuilder:
    def test_builds_safe_visible_links_and_rfc8058_headers(self, settings):
        settings.SITE_URL = "https://optisport.example/"
        subscription = Newsletter.objects.create(email="message-recipient@example.com")

        message = MarketingMessageBuilder().build(
            subscription=subscription,
            campaign_id="campaign-41-15",
            subject="Новости OPTISPORT",
        )

        public_url = f"https://optisport.example/unsubscribe#{subscription.unsubscribe_token}"
        one_click_url = (
            "https://optisport.example/api/v1/newsletter/unsubscribe/one-click/" f"{subscription.unsubscribe_token}/"
        )
        assert message.recipient == subscription.email
        assert message.recipient_ref == subscription.id
        assert public_url in message.html_body
        assert public_url in message.text_body
        assert ">Отписаться от рассылки<" in message.html_body
        assert "Отписаться от рассылки:" in message.text_body
        assert message.headers == {
            "List-Unsubscribe": f"<{one_click_url}>",
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        assert subscription.email not in public_url


class TestMarketingDeliveryService:
    def test_active_recipient_is_sent_through_test_transport(self):
        subscription = Newsletter.objects.create(email="deliver-active@example.com")
        transport = TestMarketingTransport()
        service = MarketingDeliveryService(transport=transport)

        result = service.deliver(
            recipient_ref=subscription.id,
            campaign_id="campaign-1",
            subject="Тестовая рассылка",
        )

        assert result.status == "sent"
        assert len(transport.messages) == 1
        assert transport.messages[0].recipient_ref == subscription.id

    def test_unsubscribed_prepared_recipient_is_suppressed_without_transport(self):
        subscription = Newsletter.objects.create(email="queued-then-unsubscribed@example.com")
        queued_recipient_id = subscription.id
        transport = TestMarketingTransport()
        service = MarketingDeliveryService(transport=transport)
        subscription.unsubscribe()

        result = service.deliver(
            recipient_ref=queued_recipient_id,
            campaign_id="campaign-2",
            subject="Тестовая рассылка",
        )

        assert result.status == "suppressed"
        assert transport.messages == []

    def test_missing_prepared_recipient_is_suppressed(self):
        transport = TestMarketingTransport()
        service = MarketingDeliveryService(transport=transport)

        result = service.deliver(
            recipient_ref=999999,
            campaign_id="campaign-3",
            subject="Тестовая рассылка",
        )

        assert result.status == "suppressed"
        assert transport.messages == []

    def test_retry_rechecks_activity(self):
        subscription = Newsletter.objects.create(email="retry-recipient@example.com")
        transport = TestMarketingTransport()
        service = MarketingDeliveryService(transport=transport)

        first = service.deliver(
            recipient_ref=subscription.id,
            campaign_id="campaign-retry",
            subject="Тестовая рассылка",
        )
        subscription.unsubscribe()
        retry = service.deliver(
            recipient_ref=subscription.id,
            campaign_id="campaign-retry",
            subject="Тестовая рассылка",
        )

        assert first.status == "sent"
        assert retry.status == "suppressed"
        assert len(transport.messages) == 1

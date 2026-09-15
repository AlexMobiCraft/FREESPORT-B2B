"""Локальные порты подготовки и отправки маркетинговых писем."""

from dataclasses import dataclass, field
from html import escape
from typing import Protocol
from urllib.parse import urlsplit

from django.conf import settings

from apps.common.models import Newsletter


@dataclass(frozen=True)
class MarketingMessage:
    recipient: str
    subject: str
    html_body: str
    text_body: str
    headers: dict[str, str]
    campaign_id: str
    recipient_ref: int


@dataclass(frozen=True)
class TransportResult:
    status: str


class MarketingTransport(Protocol):
    def send(self, message: MarketingMessage) -> TransportResult:
        ...


class NewsletterRecipientSource:
    def recipient_ids(self) -> list[int]:
        return list(Newsletter.objects.filter(is_active=True).order_by("id").values_list("id", flat=True))


class MarketingMessageBuilder:
    def __init__(self, public_origin: str | None = None):
        self.public_origin = self._normalize_origin(public_origin or settings.SITE_URL)

    @staticmethod
    def _normalize_origin(value: str) -> str:
        parsed = urlsplit(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
            raise ValueError("Некорректный public origin для маркетинговой рассылки")
        return f"{parsed.scheme}://{parsed.netloc}"

    def build(self, subscription: Newsletter, campaign_id: str, subject: str) -> MarketingMessage:
        public_url = f"{self.public_origin}/unsubscribe#{subscription.unsubscribe_token}"
        one_click_url = (
            f"{self.public_origin}/api/v1/newsletter/unsubscribe/one-click/" f"{subscription.unsubscribe_token}/"
        )
        safe_public_url = escape(public_url, quote=True)
        html_body = f"<p>{escape(subject)}</p>" f'<p><a href="{safe_public_url}">Отписаться от рассылки</a></p>'
        text_body = f"{subject}\n\nОтписаться от рассылки: {public_url}"
        return MarketingMessage(
            recipient=subscription.email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            headers={
                "List-Unsubscribe": f"<{one_click_url}>",
                "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
            },
            campaign_id=campaign_id,
            recipient_ref=subscription.id,
        )


@dataclass
class TestMarketingTransport:
    __test__ = False
    messages: list[MarketingMessage] = field(default_factory=list)

    def send(self, message: MarketingMessage) -> TransportResult:
        self.messages.append(message)
        return TransportResult(status="sent")


class MarketingDeliveryService:
    def __init__(
        self,
        transport: MarketingTransport,
        message_builder: MarketingMessageBuilder | None = None,
    ):
        self.transport = transport
        self.message_builder = message_builder or MarketingMessageBuilder()

    def deliver(self, recipient_ref: int, campaign_id: str, subject: str) -> TransportResult:
        subscription = Newsletter.objects.filter(pk=recipient_ref, is_active=True).first()
        if subscription is None:
            return TransportResult(status="suppressed")

        message = self.message_builder.build(
            subscription=subscription,
            campaign_id=campaign_id,
            subject=subject,
        )
        return self.transport.send(message)

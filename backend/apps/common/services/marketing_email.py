"""Локальные порты подготовки и отправки маркетинговых писем (ADR-008)."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from html import escape
from smtplib import (
    SMTPAuthenticationError,
    SMTPException,
    SMTPRecipientsRefused,
    SMTPResponseException,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from typing import Any, Protocol
from urllib.parse import urlsplit

from django.conf import settings
from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from apps.common.models import Newsletter

logger = logging.getLogger(__name__)

# Тестовое письмо сотруднику: ссылка отписки в нём — заглушка без токена.
TEST_EMAIL_NOTICE = "Тестовое письмо. Ссылка отписки в нём не работает."
SMTP_TIMEOUT_SECONDS = 30
# Результат транспорта «сбой ящика»: прогон останавливается, адрес не виноват.
STATUS_MAILBOX_FAILED = "mailbox_failed"
MAILBOX_REPLY_CODES = frozenset({421, 451})
# 421 — сервер закрывает сессию: сбой ящика на любом этапе, включая RCPT.
SESSION_CLOSED_CODE = 421
MAILBOX_ENHANCED_CODE = re.compile(r"\b5\.7\.\d{1,3}\b")


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
    error: str = ""


@dataclass(frozen=True)
class ArticleContent:
    """
    Анонс материала для письма рассылки.

    `excerpt_html` — уже очищенный HTML (`sanitize_rich_html` в `save()` модели),
    вставляется в HTML-часть как есть; `excerpt_text` — тот же анонс без тегов.
    URL собираются вызывающим от `SITE_URL`: `get_absolute_url` моделей для
    письма не годится.
    """

    title: str
    excerpt_html: str
    excerpt_text: str
    url: str
    image_url: str | None = None


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

    def build(
        self,
        subscription: Newsletter,
        campaign_id: str,
        subject: str,
        content: ArticleContent | None = None,
    ) -> MarketingMessage:
        public_url = f"{self.public_origin}/unsubscribe#{subscription.unsubscribe_token}"
        one_click_url = (
            f"{self.public_origin}/api/v1/newsletter/unsubscribe/one-click/" f"{subscription.unsubscribe_token}/"
        )
        if content is None:
            safe_public_url = escape(public_url, quote=True)
            html_body = f"<p>{escape(subject)}</p>" f'<p><a href="{safe_public_url}">Отписаться от рассылки</a></p>'
            text_body = f"{subject}\n\nОтписаться от рассылки: {public_url}"
        else:
            html_body, text_body = self._render_article(content, unsubscribe_url=public_url, is_test=False)
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

    def build_test(self, recipient: str, content: ArticleContent) -> MarketingMessage:
        """
        Тестовое письмо сотруднику: без подписки, кампании и заголовков RFC 8058.

        Ссылка отписки — `/unsubscribe` без токена: страница покажет «Ссылка
        недействительна», о чём предупреждает первая строка письма.
        """
        html_body, text_body = self._render_article(
            content, unsubscribe_url=f"{self.public_origin}/unsubscribe", is_test=True
        )
        return MarketingMessage(
            recipient=recipient,
            subject=content.title,
            html_body=html_body,
            text_body=text_body,
            headers={},
            campaign_id="test",
            recipient_ref=0,
        )

    @staticmethod
    def _render_article(content: ArticleContent, *, unsubscribe_url: str, is_test: bool) -> tuple[str, str]:
        context = {
            "content": content,
            "unsubscribe_url": unsubscribe_url,
            "test_notice": TEST_EMAIL_NOTICE if is_test else "",
        }
        html_body = render_to_string("emails/newsletter_article.html", context)
        text_body = render_to_string("emails/newsletter_article.txt", context)
        return html_body, text_body


@dataclass
class TestMarketingTransport:
    __test__ = False
    messages: list[MarketingMessage] = field(default_factory=list)

    def send(self, message: MarketingMessage) -> TransportResult:
        self.messages.append(message)
        return TransportResult(status="sent")


class _MailboxUnavailable(Exception):
    """Соединение с SMTP не открылось или не прошёл вход."""

    def __init__(self, original: OSError):
        super().__init__(str(original))
        self.original = original


def _error_text(exc: BaseException) -> str:
    if isinstance(exc, SMTPRecipientsRefused):
        # str() отказа — словарь с email подписчика; строки доставки не удаляются,
        # поэтому в ошибку идут только коды и ответы сервера.
        replies = "; ".join(
            f"{code} {text.decode('utf-8', 'replace') if isinstance(text, bytes) else text}"
            for code, text in exc.recipients.values()
        )
        return f"{type(exc).__name__}: {replies}"[:1000]
    return f"{type(exc).__name__}: {exc}"[:1000]


def _is_mailbox_reply(code: Any, text: Any) -> bool:
    """Ответ на MAIL FROM/DATA о состоянии ящика: 421, 451 или расширенный код 5.7.x."""
    if code in MAILBOX_REPLY_CODES:
        return True
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    return bool(MAILBOX_ENHANCED_CODE.search(str(text or "")))


def is_mailbox_failure(exc: BaseException) -> bool:
    """
    Ошибка ящика, а не конкретного адреса: дальше слать бессмысленно.

    Каждая следующая попытка продлевает 24-часовую блокировку Яндекса, общую с
    письмами о заказах, поэтому такой ответ останавливает рассылку целиком.

    Отказ на RCPT (`SMTPRecipientsRefused`) — отказ адреса с любым кодом, кроме
    421 (сервер закрывает сессию): на несуществующий адрес Яндекс отвечает
    `550 5.7.1 No such user!`, и правило «5.7.x — ящик» остановило бы рассылку
    на одной опечатке. 451 и `5.7.x` — сбой ящика только на MAIL FROM и DATA.
    """
    if isinstance(exc, (SMTPSenderRefused, SMTPAuthenticationError)):
        return True
    if isinstance(exc, SMTPRecipientsRefused):
        return any(code == SESSION_CLOSED_CODE for code, _text in exc.recipients.values())
    if isinstance(exc, SMTPResponseException):
        return _is_mailbox_reply(exc.smtp_code, exc.smtp_error)
    return False


class SmtpMarketingTransport:
    """
    Отправка через email-backend Django (на проде — SMTP Яндекс 360).

    Одно соединение на прогон: открывается лениво при первом `send`, закрывает его
    владелец транспорта (`close()` в `finally`). Обрыв соединения сервером —
    переподключение и один повтор. Ошибка SMTP по адресу — результат `failed` с
    текстом ошибки; соединение остаётся открытым (smtplib после отказа сам делает
    `RSET`), следующий адрес идёт по нему же.

    Сбой ящика — не открылось соединение или не прошёл вход, `SMTPSenderRefused`,
    второй обрыв подряд, RCPT 421, ответ 421/451 или `5.7.x` на MAIL FROM/DATA —
    даёт результат `mailbox_failed`: вызывающий останавливает прогон, адрес не
    помечается сбойным. Соединение закрывается только при сбое ящика и сетевой
    ошибке.
    """

    def __init__(self, timeout: int = SMTP_TIMEOUT_SECONDS, from_email: str | None = None):
        self.timeout = timeout
        self.from_email = from_email or settings.DEFAULT_FROM_EMAIL
        self._connection: Any = None

    def _get_connection(self) -> Any:
        if self._connection is None:
            connection = get_connection(fail_silently=False, timeout=self.timeout)
            connection.open()
            self._connection = connection
        return self._connection

    def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is None:
            return
        try:
            connection.close()
        except Exception:  # noqa: BLE001 — закрытие оборванного соединения не должно ронять прогон
            logger.warning("Рассылка: не удалось корректно закрыть SMTP-соединение", exc_info=True)

    def _email(self, message: MarketingMessage) -> EmailMultiAlternatives:
        email = EmailMultiAlternatives(
            subject=message.subject,
            body=message.text_body,
            from_email=self.from_email,
            to=[message.recipient],
            headers=dict(message.headers),
        )
        email.attach_alternative(message.html_body, "text/html")
        return email

    def _send_once(self, email: EmailMultiAlternatives) -> None:
        try:
            connection = self._get_connection()
        except OSError as exc:
            # Не открылось соединение или не прошёл вход — сбой ящика, а не адреса.
            raise _MailboxUnavailable(exc) from exc
        email.connection = connection
        email.send(fail_silently=False)

    def send(self, message: MarketingMessage) -> TransportResult:
        email = self._email(message)
        try:
            try:
                self._send_once(email)
            except SMTPServerDisconnected:
                logger.warning("Рассылка: SMTP-сервер разорвал соединение, переподключение")
                self.close()
                try:
                    self._send_once(email)
                except SMTPServerDisconnected as again:
                    # Второй обрыв подряд — ящик рвёт сессии, серия переподключений бессмысленна.
                    raise _MailboxUnavailable(again) from again
        except _MailboxUnavailable as exc:
            self.close()
            return TransportResult(status=STATUS_MAILBOX_FAILED, error=_error_text(exc.original))
        except OSError as exc:  # SMTPException — подкласс OSError, как и сетевые сбои
            if is_mailbox_failure(exc):
                self.close()
                return TransportResult(status=STATUS_MAILBOX_FAILED, error=_error_text(exc))
            if not isinstance(exc, SMTPException):
                # Сетевая ошибка посреди сессии: состояние соединения неизвестно.
                self.close()
            return TransportResult(status="failed", error=_error_text(exc))
        return TransportResult(status="sent")


class MarketingDeliveryService:
    def __init__(
        self,
        transport: MarketingTransport,
        message_builder: MarketingMessageBuilder | None = None,
    ):
        self.transport = transport
        self.message_builder = message_builder or MarketingMessageBuilder()

    def deliver(
        self,
        recipient_ref: int,
        campaign_id: str,
        subject: str,
        content: ArticleContent | None = None,
    ) -> TransportResult:
        subscription = Newsletter.objects.filter(pk=recipient_ref, is_active=True).first()
        if subscription is None:
            return TransportResult(status="suppressed")

        message = self.message_builder.build(
            subscription=subscription,
            campaign_id=campaign_id,
            subject=subject,
            content=content,
        )
        return self.transport.send(message)

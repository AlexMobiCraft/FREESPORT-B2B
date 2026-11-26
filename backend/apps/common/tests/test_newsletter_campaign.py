"""
Рассылка новостей и статей блога подписчикам: сервис запуска, SMTP-транспорт
и задача `send_newsletter_campaign`. Транспорт — locmem email-backend
тестовых настроек, подделка соединения — только для обрывов SMTP.
"""

from __future__ import annotations

import logging
import socket
from datetime import timedelta
from smtplib import (
    SMTPAuthenticationError,
    SMTPDataError,
    SMTPRecipientsRefused,
    SMTPSenderRefused,
    SMTPServerDisconnected,
)
from typing import Any
from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from apps.common import tasks
from apps.common.models import AuditLog, BlogPost, News, Newsletter, NewsletterCampaign, NewsletterDelivery
from apps.common.services.marketing_email import (
    STATUS_MAILBOX_FAILED,
    TEST_EMAIL_NOTICE,
    MarketingDeliveryService,
    MarketingMessage,
    MarketingMessageBuilder,
    SmtpMarketingTransport,
    TransportResult,
)
from apps.common.services.newsletter_campaign import (
    CAP_REACHED_MESSAGE,
    NO_EMAIL_MESSAGE,
    NOT_PUBLISHED_MESSAGE,
    NewsletterCampaignError,
    article_content,
    daily_sent_count,
    log_campaign_start,
    recipients_to_send,
    send_test,
    start_campaign,
)
from apps.users.models import User

pytestmark = pytest.mark.django_db

SITE = "https://optisport.example"
_counter = iter(range(1, 1_000_000))


@pytest.fixture(autouse=True)
def site_settings(settings):
    settings.SITE_URL = SITE + "/"
    settings.NEWSLETTER_DAILY_CAP = 150
    settings.NEWSLETTER_SEND_INTERVAL_SECONDS = 0
    settings.DEFAULT_FROM_EMAIL = "noreply@optisport.example"


def make_news(**overrides: Any) -> News:
    number = next(_counter)
    defaults: dict[str, Any] = {
        "title": f"Новость рассылки {number}",
        "slug": f"newsletter-news-{number}",
        "excerpt": "<p>Краткий <strong>анонс</strong> &amp; детали</p>",
        "content": "<p>Полный текст новости, который в письмо не идёт.</p>",
        "is_published": True,
        "published_at": timezone.now() - timedelta(hours=1),
    }
    defaults.update(overrides)
    return News.objects.create(**defaults)


def make_post(**overrides: Any) -> BlogPost:
    number = next(_counter)
    defaults: dict[str, Any] = {
        "title": f"Статья рассылки {number}",
        "slug": f"newsletter-post-{number}",
        "excerpt": "Анонс статьи",
        "content": "<p>Текст статьи</p>",
        "is_published": True,
        "published_at": timezone.now() - timedelta(hours=1),
    }
    defaults.update(overrides)
    return BlogPost.objects.create(**defaults)


def subscribers(count: int) -> list[Newsletter]:
    return [Newsletter.objects.create(email=f"reader{next(_counter)}@example.com") for _ in range(count)]


def make_staff(email: str = "") -> User:
    return User.objects.create_user(
        email=email or f"marketer{next(_counter)}@example.com", password="x-Strong-Pass-1", is_staff=True
    )


def run(campaign: NewsletterCampaign) -> dict[str, Any]:
    return tasks.send_newsletter_campaign(campaign.pk)


def statuses(campaign: NewsletterCampaign) -> dict[str, int]:
    result: dict[str, int] = {}
    for status in campaign.deliveries.values_list("status", flat=True):
        result[status] = result.get(status, 0) + 1
    return result


def set_sent(count: int, *, at: Any = None) -> None:
    """`count` доставок `sent` другой кампании за последние сутки — расход суточного потолка."""
    campaign = NewsletterCampaign.objects.create(news=make_news())
    for subscription in subscribers(count):
        NewsletterDelivery.objects.create(
            campaign=campaign,
            newsletter=subscription,
            status=NewsletterDelivery.STATUS_SENT,
            sent_at=at or timezone.now() - timedelta(hours=1),
        )
    Newsletter.objects.filter(deliveries__campaign=campaign).update(is_active=False)


# --------------------------------------------------------------------------
# Письмо
# --------------------------------------------------------------------------


class TestArticleMessage:
    def test_news_letter_has_announce_button_image_and_unsubscribe(self):
        news = make_news()
        news.image.name = "news/images/2026/11/24/cover.png"
        subscription = subscribers(1)[0]

        message = MarketingMessageBuilder().build(subscription, "1", news.title, content=article_content(news))

        article_url = f"{SITE}/news/{news.slug}"
        unsubscribe = f"{SITE}/unsubscribe#{subscription.unsubscribe_token}"
        assert message.subject == news.title
        assert message.recipient == subscription.email
        assert f'href="{article_url}"' in message.html_body
        assert ">Читать на сайте<" in message.html_body
        assert f'src="{SITE}/media/news/images/2026/11/24/cover.png"' in message.html_body
        assert "<strong>анонс</strong>" in message.html_body
        assert "Полный текст" not in message.html_body
        assert f'href="{unsubscribe}"' in message.html_body
        assert ">Отписаться от рассылки<" in message.html_body
        assert "Краткий анонс & детали" in message.text_body
        assert "<" not in message.text_body
        assert f"Читать на сайте: {article_url}" in message.text_body
        assert f"Отписаться от рассылки: {unsubscribe}" in message.text_body
        assert message.headers == {
            "List-Unsubscribe": (f"<{SITE}/api/v1/newsletter/unsubscribe/one-click/{subscription.unsubscribe_token}/>"),
            "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
        }
        assert TEST_EMAIL_NOTICE not in message.html_body + message.text_body

    def test_blog_link_without_image_and_empty_excerpt(self):
        words = " ".join(f"слово{index}" for index in range(60))
        post = make_post(excerpt="", content=f"<p>{words}</p>")

        content = article_content(post)
        message = MarketingMessageBuilder().build(subscribers(1)[0], "1", post.title, content=content)

        assert content.url == f"{SITE}/blog/{post.slug}"
        assert content.image_url is None
        assert "<img" not in message.html_body
        assert "слово39" in content.excerpt_text and "слово40" not in content.excerpt_text
        assert content.excerpt_text.endswith("…")
        assert "слово0" in message.html_body and "слово0" in message.text_body

    def test_fallback_excerpt_keeps_paragraph_boundaries(self):
        post = make_post(
            excerpt="",
            content="<p>Конец первого абзаца.</p><p>Начало второго.</p><ul><li>пункт</li><li>ещё</li></ul>"
            "<p>строка<br>перенос<br/>и&nbsp;так</p>",
        )

        content = article_content(post)

        assert content.excerpt_text == "Конец первого абзаца. Начало второго. пункт ещё строка перенос и так"
        assert "абзаца.Начало" not in content.excerpt_html

    def test_test_letter_has_notice_first_and_no_list_unsubscribe(self):
        news = make_news()

        message = MarketingMessageBuilder().build_test("staff@example.com", article_content(news))

        assert message.headers == {}
        assert message.text_body.splitlines()[0] == TEST_EMAIL_NOTICE
        body = message.html_body.split("<body", 1)[1]
        assert body.index(TEST_EMAIL_NOTICE) < body.index(news.title)
        assert f'href="{SITE}/unsubscribe"' in message.html_body
        assert f"Отписаться от рассылки: {SITE}/unsubscribe\n" in message.text_body


# --------------------------------------------------------------------------
# SMTP-транспорт
# --------------------------------------------------------------------------


def message(recipient: str = "one@example.com") -> MarketingMessage:
    return MarketingMessage(
        recipient=recipient,
        subject="Тема",
        html_body="<p>HTML</p>",
        text_body="Текст",
        headers={"List-Unsubscribe": "<https://x/one-click/t/>", "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"},
        campaign_id="1",
        recipient_ref=1,
    )


class FakeConnection:
    """Подмена SMTP-соединения: `None` в очереди сбоев — успешная отправка, `refuse` — отказ по адресу."""

    def __init__(
        self,
        failures: list[BaseException | None],
        open_error: BaseException | None = None,
        refuse: dict[str, BaseException] | None = None,
    ):
        self.failures = failures
        self.open_error = open_error
        self.refuse = refuse or {}
        self.opened = 0
        self.closed = 0
        self.sent: list[Any] = []

    def open(self) -> bool:
        self.opened += 1
        if self.open_error is not None:
            raise self.open_error
        return True

    def close(self) -> None:
        self.closed += 1

    def send_messages(self, messages: list[Any]) -> int:
        if self.failures:
            failure = self.failures.pop(0)
            if failure is not None:
                raise failure
        for email in messages:
            if email.to[0] in self.refuse:
                raise self.refuse[email.to[0]]
        self.sent.extend(messages)
        return len(messages)


class TestSmtpTransport:
    def test_sends_one_recipient_with_headers_from_default_sender(self):
        transport = SmtpMarketingTransport()
        try:
            result = transport.send(message())
        finally:
            transport.close()

        assert result.status == "sent"
        assert len(mail.outbox) == 1
        email = mail.outbox[0]
        assert email.to == ["one@example.com"]
        assert email.cc == [] and email.bcc == []
        assert email.from_email == "noreply@optisport.example"
        assert email.extra_headers["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert email.alternatives[0][1] == "text/html"

    def test_connection_is_lazy_shared_and_has_timeout(self):
        connection = FakeConnection([])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            assert factory.call_count == 0
            transport.send(message("a@example.com"))
            transport.send(message("b@example.com"))
            transport.close()

        factory.assert_called_once_with(fail_silently=False, timeout=30)
        assert (connection.opened, connection.closed, len(connection.sent)) == (1, 1, 2)

    def test_disconnect_reconnects_and_retries_once(self):
        connection = FakeConnection([SMTPServerDisconnected("bye")])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == "sent"
        assert factory.call_count == 2
        assert len(connection.sent) == 1

    def test_second_disconnect_in_a_row_is_mailbox_failure(self):
        connection = FakeConnection([SMTPServerDisconnected("bye"), SMTPServerDisconnected("bye again")])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            result = transport.send(message())

        assert result.status == STATUS_MAILBOX_FAILED
        assert "bye again" in result.error
        assert factory.call_count == 2
        assert transport._connection is None

    def test_address_refusal_keeps_connection_for_next_address(self):
        connection = FakeConnection(
            [], refuse={"a@example.com": SMTPRecipientsRefused({"a@example.com": (550, b"5.7.1 No such user!")})}
        )
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            refused = transport.send(message("a@example.com"))
            delivered = transport.send(message("b@example.com"))
            closed_before = connection.closed
            transport.close()

        assert (refused.status, delivered.status) == ("failed", "sent")
        assert "5.7.1 No such user!" in refused.error
        assert factory.call_count == 1 and connection.opened == 1
        assert closed_before == 0
        assert [email.to for email in connection.sent] == [["b@example.com"]]

    def test_data_error_by_address_keeps_connection(self):
        connection = FakeConnection([SMTPDataError(552, b"5.3.4 Message size exceeds limit"), None])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            first = transport.send(message("a@example.com"))
            second = transport.send(message("b@example.com"))
            transport.close()

        assert (first.status, second.status) == ("failed", "sent")
        assert factory.call_count == 1

    def test_network_error_mid_session_closes_connection(self):
        connection = FakeConnection([ConnectionResetError(104, "reset"), None])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            transport = SmtpMarketingTransport()
            first = transport.send(message("a@example.com"))
            second = transport.send(message("b@example.com"))
            transport.close()

        assert (first.status, second.status) == ("failed", "sent")
        assert factory.call_count == 2

    def test_smtp_error_on_address_is_failed(self):
        refused = SMTPRecipientsRefused({"one@example.com": (550, b"no such user")})
        connection = FakeConnection([refused])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection):
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == "failed"
        assert result.error == "SMTPRecipientsRefused: 550 no such user"
        assert "one@example.com" not in result.error

    @pytest.mark.parametrize(
        "open_error",
        [
            pytest.param(SMTPAuthenticationError(535, b"5.7.8 Error: authentication failed"), id="auth"),
            pytest.param(ConnectionRefusedError(111, "Connection refused"), id="refused"),
            pytest.param(socket.timeout("timed out"), id="timeout"),
        ],
    )
    def test_open_failure_is_mailbox_failure(self, open_error):
        connection = FakeConnection([], open_error=open_error)
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection):
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == STATUS_MAILBOX_FAILED
        assert type(open_error).__name__ in result.error
        assert connection.sent == []

    def test_reconnect_failure_after_disconnect_is_mailbox_failure(self):
        connection = FakeConnection([SMTPServerDisconnected("bye")])
        opened = {"count": 0}

        def factory(**kwargs):
            opened["count"] += 1
            if opened["count"] == 2:
                connection.open_error = ConnectionRefusedError(111, "Connection refused")
            return connection

        with patch("apps.common.services.marketing_email.get_connection", side_effect=factory):
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == STATUS_MAILBOX_FAILED

    @pytest.mark.parametrize(
        "error",
        [
            pytest.param(SMTPSenderRefused(553, b"5.7.1 Sender address rejected", "noreply@x"), id="sender"),
            pytest.param(SMTPDataError(421, b"4.7.0 Try again later"), id="421"),
            pytest.param(SMTPDataError(451, b"4.7.1 Ratelimit"), id="451"),
            pytest.param(SMTPDataError(554, b"5.7.1 Message rejected under suspicion of SPAM"), id="5.7.1"),
            pytest.param(SMTPRecipientsRefused({"one@example.com": (421, b"4.7.0 Closing")}), id="rcpt-421"),
        ],
    )
    def test_mailbox_replies_are_mailbox_failure(self, error):
        connection = FakeConnection([error])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection):
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == STATUS_MAILBOX_FAILED

    @pytest.mark.parametrize(
        "error",
        [
            # Реальный ответ Яндекса на несуществующий адрес — отказ адреса, не ящика.
            pytest.param(
                SMTPRecipientsRefused({"one@example.com": (550, b"5.7.1 No such user!")}), id="yandex-no-user"
            ),
            pytest.param(SMTPRecipientsRefused({"one@example.com": (451, b"4.7.1 Try later")}), id="rcpt-451"),
            pytest.param(
                SMTPRecipientsRefused({"one@example.com": (550, b"5.7.1 Sending limit exceeded")}), id="rcpt-5.7"
            ),
            pytest.param(SMTPDataError(552, b"5.3.4 Message size exceeds limit"), id="size"),
        ],
    )
    def test_address_errors_stay_failed(self, error):
        connection = FakeConnection([error])
        with patch("apps.common.services.marketing_email.get_connection", return_value=connection):
            transport = SmtpMarketingTransport()
            result = transport.send(message())
            transport.close()

        assert result.status == "failed"


# --------------------------------------------------------------------------
# Запуск рассылки
# --------------------------------------------------------------------------


class TestStartCampaign:
    def test_creates_rows_for_active_only_and_audit(self):
        news = make_news()
        active = subscribers(3)
        Newsletter.objects.create(email="gone@example.com", is_active=False)
        staff = make_staff()

        started = start_campaign(news, staff)

        assert started.queued == 3
        assert started.campaign.news == news and started.campaign.blog_post is None
        assert started.campaign.created_by == staff and started.campaign.last_run_at is not None
        assert sorted(started.campaign.deliveries.values_list("newsletter_id", flat=True)) == sorted(
            s.pk for s in active
        )
        assert not AuditLog.objects.filter(action="newsletter_send").exists()

        log_campaign_start(news, staff, started.queued)

        entry = AuditLog.objects.get(action="newsletter_send")
        assert (entry.user, entry.resource_type, entry.resource_id) == (staff, "News", str(news.pk))
        assert entry.changes == {"kind": "news", "title": news.title, "recipients": 3}

    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"is_published": False}, id="unpublished"),
            pytest.param({"published_at": None}, id="no-date"),
            pytest.param({"published_at": timezone.now() + timedelta(days=1)}, id="future"),
        ],
    )
    def test_unpublished_is_refused_without_campaign(self, overrides):
        news = make_news(**overrides)
        subscribers(1)

        with pytest.raises(NewsletterCampaignError, match=NOT_PUBLISHED_MESSAGE):
            start_campaign(news, make_staff())

        assert not NewsletterCampaign.objects.exists()
        assert not AuditLog.objects.filter(action="newsletter_send").exists()

    def test_cap_exhausted_before_start(self, settings):
        settings.NEWSLETTER_DAILY_CAP = 2
        set_sent(2)
        news = make_news()
        subscribers(1)

        with pytest.raises(NewsletterCampaignError, match=CAP_REACHED_MESSAGE):
            start_campaign(news, make_staff())

        assert not NewsletterCampaign.objects.filter(news=news).exists()

    def test_sent_older_than_day_do_not_count(self, settings):
        settings.NEWSLETTER_DAILY_CAP = 2
        set_sent(2, at=timezone.now() - timedelta(hours=25))
        news = make_news()
        subscribers(1)

        assert start_campaign(news, make_staff()).queued == 1

    def test_repeat_after_all_sent_queues_nothing(self):
        news = make_news()
        subscribers(2)
        staff = make_staff()
        run(start_campaign(news, staff).campaign)
        mail.outbox.clear()

        assert recipients_to_send(news) == 0
        again = start_campaign(news, staff)

        assert again.queued == 0
        assert not AuditLog.objects.filter(action="newsletter_send").exists()
        assert NewsletterCampaign.objects.filter(news=news).count() == 1

    def test_repeat_requeues_failed_resubscribed_and_new(self):
        news = make_news()
        sent, failed, resubscribed, gone = subscribers(4)
        staff = make_staff()
        campaign = start_campaign(news, staff).campaign
        campaign.deliveries.filter(newsletter=sent).update(status="sent", sent_at=timezone.now())
        campaign.deliveries.filter(newsletter=failed).update(status="failed", error="boom")
        campaign.deliveries.filter(newsletter__in=[resubscribed, gone]).update(status="suppressed")
        Newsletter.objects.filter(pk=gone.pk).update(is_active=False)
        newcomer = subscribers(1)[0]

        again = start_campaign(news, staff)

        assert again.campaign.pk == campaign.pk
        assert again.queued == 3
        rows = dict(campaign.deliveries.values_list("newsletter_id", "status"))
        assert rows == {
            sent.pk: "sent",
            failed.pk: "pending",
            resubscribed.pk: "pending",
            gone.pk: "suppressed",
            newcomer.pk: "pending",
        }

    def test_stale_sending_returns_to_pending_fresh_stays(self):
        news = make_news()
        stale, fresh = subscribers(2)
        campaign = start_campaign(news, make_staff()).campaign
        now = timezone.now()
        campaign.deliveries.filter(newsletter=stale).update(status="sending", claimed_at=now - timedelta(minutes=16))
        campaign.deliveries.filter(newsletter=fresh).update(status="sending", claimed_at=now - timedelta(minutes=5))

        again = start_campaign(news, make_staff())

        assert again.queued == 1
        assert dict(campaign.deliveries.values_list("newsletter_id", "status")) == {
            stale.pk: "pending",
            fresh.pk: "sending",
        }

    def test_blog_post_campaign(self):
        post = make_post()
        subscribers(1)

        staff = make_staff()
        started = start_campaign(post, staff)
        log_campaign_start(post, staff, started.queued)

        assert started.campaign.blog_post == post and started.campaign.news is None
        assert AuditLog.objects.get(action="newsletter_send").changes["kind"] == "blog"
        assert AuditLog.objects.get(action="newsletter_send").resource_type == "BlogPost"

    def test_pending_of_inactive_and_deleted_subscriptions_become_suppressed(self):
        news = make_news()
        stays, leaves, deleted = subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        leaves.unsubscribe()
        deleted.delete()

        again = start_campaign(news, make_staff())

        assert again.queued == 1
        assert sorted(campaign.deliveries.values_list("newsletter_id", "status"), key=str) == sorted(
            [(stays.pk, "pending"), (leaves.pk, "suppressed"), (None, "suppressed")], key=str
        )


# --------------------------------------------------------------------------
# Задача рассылки
# --------------------------------------------------------------------------


class TestSendTask:
    def test_blog_post_goes_through_task(self):
        post = make_post()
        subscribers(2)
        campaign = start_campaign(post, make_staff()).campaign

        result = run(campaign)

        assert result["sent"] == 2
        assert result["stopped"] == ""
        assert statuses(campaign) == {"sent": 2}
        assert len(mail.outbox) == 2
        for email in mail.outbox:
            assert f"/blog/{post.slug}" in email.body

    def test_first_run_sends_each_own_unsubscribe_link(self):
        news = make_news()
        readers = subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign

        result = run(campaign)

        assert result["sent"] == 3
        assert statuses(campaign) == {"sent": 3}
        assert sorted(email.to[0] for email in mail.outbox) == sorted(r.email for r in readers)
        for email in mail.outbox:
            reader = next(r for r in readers if r.email == email.to[0])
            assert email.subject == news.title
            assert f"/unsubscribe#{reader.unsubscribe_token}" in email.body
            assert reader.unsubscribe_token in email.extra_headers["List-Unsubscribe"]
            assert email.bcc == [] and email.cc == []
        assert all(row.sent_at for row in campaign.deliveries.all())

    def test_unsubscribed_after_queue_is_suppressed(self):
        news = make_news()
        stays, leaves = subscribers(2)
        campaign = start_campaign(news, make_staff()).campaign
        leaves.unsubscribe()

        run(campaign)

        assert [email.to for email in mail.outbox] == [[stays.email]]
        assert campaign.deliveries.get(newsletter=leaves).status == "suppressed"

    def test_unsubscribe_excludes_from_next_mailing(self):
        first, second = make_news(), make_news()
        stays, leaves = subscribers(2)
        run(start_campaign(first, make_staff()).campaign)
        leaves.unsubscribe()
        mail.outbox.clear()

        run(start_campaign(second, make_staff()).campaign)

        assert [email.to for email in mail.outbox] == [[stays.email]]

    def test_daily_cap_stops_and_leaves_pending(self, settings):
        settings.NEWSLETTER_DAILY_CAP = 5
        set_sent(2)
        news = make_news()
        subscribers(5)
        campaign = start_campaign(news, make_staff()).campaign

        result = run(campaign)

        assert result["stopped"] == "daily_cap"
        assert len(mail.outbox) == 3
        assert statuses(campaign) == {"sent": 3, "pending": 2}

    def test_unpublished_during_run_stops(self):
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        original = SmtpMarketingTransport.send

        def send_and_unpublish(transport, message):
            result = original(transport, message)
            News.objects.filter(pk=news.pk).update(is_published=False)
            return result

        with patch.object(SmtpMarketingTransport, "send", send_and_unpublish):
            result = run(campaign)

        assert result["stopped"] == "unpublished"
        assert statuses(campaign) == {"sent": 1, "pending": 2}

    def test_deleted_article_removes_campaign_keeps_rows(self):
        news = make_news()
        subscribers(2)
        campaign = start_campaign(news, make_staff()).campaign
        row_ids = list(campaign.deliveries.values_list("pk", flat=True))

        news.delete()

        assert not NewsletterCampaign.objects.filter(pk=campaign.pk).exists()
        rows = NewsletterDelivery.objects.filter(pk__in=row_ids)
        assert rows.count() == 2 and not rows.filter(campaign__isnull=False).exists()

    def test_deleted_during_run_stops_and_keeps_sent_in_cap(self):
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        row_ids = list(campaign.deliveries.values_list("pk", flat=True))
        original = SmtpMarketingTransport.send

        def send_and_delete(transport, message):
            result = original(transport, message)
            News.objects.filter(pk=news.pk).delete()
            return result

        with patch.object(SmtpMarketingTransport, "send", send_and_delete):
            result = run(campaign)

        assert result["stopped"] == "unpublished"
        assert len(mail.outbox) == 1
        rows = NewsletterDelivery.objects.filter(pk__in=row_ids)
        assert sorted(rows.values_list("status", flat=True)) == ["pending", "pending", "sent"]
        assert not rows.filter(campaign__isnull=False).exists()
        assert daily_sent_count() == 1

    def test_deleting_mailed_article_and_subscription_keeps_cap(self, settings):
        settings.NEWSLETTER_DAILY_CAP = 2
        news = make_news()
        first, _second = subscribers(2)
        run(start_campaign(news, make_staff()).campaign)
        assert daily_sent_count() == 2

        news.delete()
        first.delete()

        assert daily_sent_count() == 2
        subscribers(1)
        with pytest.raises(NewsletterCampaignError, match=CAP_REACHED_MESSAGE):
            start_campaign(make_news(), make_staff())

    def test_subscription_deleted_after_queue_is_suppressed(self):
        news = make_news()
        stays, gone = subscribers(2)
        campaign = start_campaign(news, make_staff()).campaign
        row = campaign.deliveries.get(newsletter=gone)
        gone.delete()

        run(campaign)

        assert [email.to for email in mail.outbox] == [[stays.email]]
        row.refresh_from_db()
        assert (row.newsletter_id, row.status) == (None, "suppressed")

    def test_smtp_failure_on_one_address_others_go(self):
        news = make_news()
        good, bad, other = subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        original = SmtpMarketingTransport.send

        def flaky(transport, message):
            if message.recipient == bad.email:
                return TransportResult(status="failed", error="SMTPDataError: 554")
            return original(transport, message)

        with patch.object(SmtpMarketingTransport, "send", flaky):
            result = run(campaign)

        assert (result["sent"], result["failed"]) == (2, 1)
        row = campaign.deliveries.get(newsletter=bad)
        assert (row.status, row.error) == ("failed", "SMTPDataError: 554")
        assert sorted(email.to[0] for email in mail.outbox) == sorted([good.email, other.email])

    def test_two_runs_at_once_send_each_address_once(self):
        news = make_news()
        subscribers(4)
        campaign = start_campaign(news, make_staff()).campaign
        original = SmtpMarketingTransport.send
        nested = {"started": False}

        def send_with_parallel_run(transport, message):
            # Пока первый прогон отправляет первое письмо, второй проходит всю очередь.
            if not nested["started"]:
                nested["started"] = True
                run(campaign)
            return original(transport, message)

        with patch.object(SmtpMarketingTransport, "send", send_with_parallel_run):
            run(campaign)

        recipients = [email.to[0] for email in mail.outbox]
        assert len(recipients) == 4 == len(set(recipients))
        assert statuses(campaign) == {"sent": 4}

    def test_claimed_row_is_skipped(self):
        news = make_news()
        claimed, free = subscribers(2)
        campaign = start_campaign(news, make_staff()).campaign
        campaign.deliveries.filter(newsletter=claimed).update(status="sending", claimed_at=timezone.now())

        run(campaign)

        assert [email.to for email in mail.outbox] == [[free.email]]
        assert campaign.deliveries.get(newsletter=claimed).status == "sending"

    def test_double_claim_returns_false(self):
        news = make_news()
        subscribers(1)
        campaign = start_campaign(news, make_staff()).campaign
        row = campaign.deliveries.get()

        assert tasks._claim(row.pk) is True
        assert tasks._claim(row.pk) is False
        row.refresh_from_db()
        assert row.status == "sending" and row.claimed_at is not None

    def test_unexpected_error_in_deliver_fails_one_address(self):
        news = make_news()
        good, bad, other = subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        original = MarketingDeliveryService.deliver

        def broken(service, recipient_ref, *args, **kwargs):
            if recipient_ref == bad.pk:
                raise ValueError("битый шаблон")
            return original(service, recipient_ref, *args, **kwargs)

        with patch.object(MarketingDeliveryService, "deliver", broken):
            result = run(campaign)

        assert (result["sent"], result["failed"], result["stopped"]) == (2, 1, "")
        row = campaign.deliveries.get(newsletter=bad)
        assert (row.status, row.error) == ("failed", "ValueError: битый шаблон")
        assert sorted(email.to[0] for email in mail.outbox) == sorted([good.email, other.email])

    def test_mailbox_failure_stops_run_and_requeues(self, caplog):
        news = make_news()
        subscribers(4)
        campaign = start_campaign(news, make_staff()).campaign
        original = SmtpMarketingTransport.send
        calls = []

        def blocked_after_first(transport, message):
            calls.append(message.recipient)
            if len(calls) == 1:
                return original(transport, message)
            return TransportResult(status=STATUS_MAILBOX_FAILED, error="SMTPDataError: (451, b'4.7.1 Try later')")

        with caplog.at_level(logging.ERROR, logger="apps.common.tasks"):
            with patch.object(SmtpMarketingTransport, "send", blocked_after_first):
                result = run(campaign)

        assert result["stopped"] == "mailbox"
        assert len(calls) == 2
        assert statuses(campaign) == {"sent": 1, "pending": 3}
        assert not campaign.deliveries.filter(claimed_at__isnull=False, status="pending").exists()
        assert "4.7.1 Try later" in caplog.text

        mail.outbox.clear()
        run(campaign)
        assert statuses(campaign) == {"sent": 4}
        assert len(mail.outbox) == 3

    def test_yandex_no_such_user_fails_address_and_run_goes_on(self):
        news = make_news()
        good, typo, other = subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        connection = FakeConnection(
            [], refuse={typo.email: SMTPRecipientsRefused({typo.email: (550, b"5.7.1 No such user!")})}
        )

        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            result = run(campaign)

        assert (result["sent"], result["failed"], result["stopped"]) == (2, 1, "")
        row = campaign.deliveries.get(newsletter=typo)
        assert row.status == "failed" and "5.7.1 No such user!" in row.error
        assert sorted(email.to[0] for email in connection.sent) == sorted([good.email, other.email])
        assert factory.call_count == 1 and connection.opened == 1

    def test_double_disconnect_stops_run_and_keeps_pending(self):
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        connection = FakeConnection([SMTPServerDisconnected("bye"), SMTPServerDisconnected("bye again")])

        with patch("apps.common.services.marketing_email.get_connection", return_value=connection) as factory:
            result = run(campaign)

        assert result["stopped"] == "mailbox"
        assert statuses(campaign) == {"pending": 3}
        assert factory.call_count == 2
        assert connection.sent == []

    def test_login_refused_sends_nothing_and_opens_once(self):
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign
        connection = FakeConnection([], open_error=SMTPAuthenticationError(535, b"5.7.8 Invalid user or password"))

        with patch("apps.common.services.marketing_email.get_connection", return_value=connection):
            result = run(campaign)

        assert result["stopped"] == "mailbox"
        assert connection.opened == 1
        assert statuses(campaign) == {"pending": 3}

    def test_pause_runs_before_checks(self, settings):
        settings.NEWSLETTER_SEND_INTERVAL_SECONDS = 2
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign

        def unpublish_during_pause(seconds):
            News.objects.filter(pk=news.pk).update(is_published=False)

        with patch("apps.common.tasks.time.sleep", side_effect=unpublish_during_pause) as sleep:
            result = run(campaign)

        assert sleep.call_count == 1
        assert result["stopped"] == "unpublished"
        assert len(mail.outbox) == 1
        assert statuses(campaign) == {"sent": 1, "pending": 2}

    def test_pause_between_letters(self, settings):
        settings.NEWSLETTER_SEND_INTERVAL_SECONDS = 2
        news = make_news()
        subscribers(3)
        campaign = start_campaign(news, make_staff()).campaign

        with patch("apps.common.tasks.time.sleep") as sleep:
            run(campaign)

        assert [call.args for call in sleep.call_args_list] == [(2.0,), (2.0,)]

    def test_missing_campaign_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="apps.common.tasks"):
            result = tasks.send_newsletter_campaign(987654)

        assert result["stopped"] == "campaign_missing"
        assert "campaign_id=987654" in caplog.text
        assert mail.outbox == []


# --------------------------------------------------------------------------
# Тестовое письмо
# --------------------------------------------------------------------------


class TestSendTest:
    def test_goes_only_to_staff_without_campaign(self):
        news = make_news(is_published=False)
        subscribers(2)
        staff = make_staff("me@example.com")

        result = send_test(news, staff)

        assert result.status == "sent"
        assert [email.to for email in mail.outbox] == [["me@example.com"]]
        email = mail.outbox[0]
        assert "List-Unsubscribe" not in email.extra_headers
        assert "List-Unsubscribe-Post" not in email.extra_headers
        assert email.body.splitlines()[0] == TEST_EMAIL_NOTICE
        assert not NewsletterCampaign.objects.exists() and not NewsletterDelivery.objects.exists()

    def test_staff_without_email_is_refused(self):
        staff = make_staff()
        staff.email = ""

        with pytest.raises(NewsletterCampaignError, match=NO_EMAIL_MESSAGE):
            send_test(make_news(), staff)

        assert mail.outbox == []

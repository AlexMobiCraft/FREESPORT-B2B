"""
Действия рассылки в списках новостей и статей: `/marketing/` (маркетинг и
руководитель) и `/admin/` (суперпользователь), колонка «Рассылка» и запись
в журнале руководителя.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group, Permission
from django.core import mail
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.common import tasks
from apps.common.admin import ALREADY_SENT_MESSAGE, ONE_ARTICLE_MESSAGE, QUEUE_DOWN_MESSAGE, TEST_FAILED_MESSAGE
from apps.common.models import AuditLog, BlogPost, News, NewsletterCampaign, NewsletterDelivery
from apps.common.services.marketing_email import (
    STATUS_MAILBOX_FAILED,
    TEST_EMAIL_NOTICE,
    SmtpMarketingTransport,
    TransportResult,
)
from apps.common.services.newsletter_campaign import CAP_REACHED_MESSAGE, NO_EMAIL_MESSAGE, NOT_PUBLISHED_MESSAGE
from apps.common.tests.test_newsletter_campaign import (  # noqa: F401 — autouse-фикстура настроек
    make_news,
    make_post,
    set_sent,
    site_settings,
    subscribers,
)
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from tests.conftest import get_unique_suffix
from tests.integration.test_manager_clients_section import (  # noqa: F401 — autouse-фикстура групп
    PASSWORD,
    make_staff_member,
    role_groups,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

NEWS_URL = "/marketing/common/news/"
BLOG_URL = "/marketing/common/blogpost/"
ADMIN_NEWS_URL = "/admin/common/news/"
JOURNAL_URL = "/supervisor/journal/"
DELAY = "apps.common.tasks.send_newsletter_campaign.delay"


def logged_in(user: User) -> Client:
    browser = Client()
    browser.force_login(user)
    return browser


def action(browser: Client, url: str, name: str, *articles: Any, confirm: bool = False, **extra: Any):
    data: dict[str, Any] = {"action": name, "_selected_action": [str(a.pk) for a in articles]}
    if confirm:
        data["post"] = "yes"
    return browser.post(url, data, follow=True, **extra)


def texts(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


@pytest.fixture
def marketer() -> User:
    return make_staff_member(MARKETING_GROUP)


@pytest.fixture
def as_marketer(marketer) -> Client:
    return logged_in(marketer)


class TestActionsAndRights:
    @pytest.mark.parametrize("group", [MARKETING_GROUP, SUPERVISORS_GROUP])
    @pytest.mark.parametrize("url", [NEWS_URL, BLOG_URL])
    def test_section_roles_see_both_actions(self, group, url):
        response = logged_in(make_staff_member(group)).get(url)

        choices = dict(response.context["action_form"].fields["action"].choices)
        assert choices["send_newsletter"] == "Разослать подписчикам"
        assert choices["send_newsletter_test"] == "Отправить тест мне"

    def test_superuser_in_admin(self):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        news = make_news()
        subscribers(2)

        response = action(logged_in(superuser), ADMIN_NEWS_URL, "send_newsletter", news)

        assert response.status_code == 200
        assert "Отправить 2 подписчикам?" in response.content.decode()

    def test_view_only_has_no_actions_and_cannot_post(self, as_marketer):
        group = Group.objects.get(name=MARKETING_GROUP)
        group.permissions.set(Permission.objects.filter(codename__in=["view_news", "view_blogpost"]))
        news = make_news()
        subscribers(1)

        response = as_marketer.get(NEWS_URL)
        assert response.context["action_form"] is None

        with patch(DELAY) as delay:
            action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    def test_manager_has_no_access(self):
        news = make_news()
        browser = logged_in(make_staff_member(MANAGERS_GROUP))

        response = browser.post(NEWS_URL, {"action": "send_newsletter", "_selected_action": [str(news.pk)]})

        assert response.status_code == 302 and "/marketing/login/" in response["Location"]
        assert not NewsletterCampaign.objects.exists()


class TestConfirmation:
    def test_page_shows_count_and_daily_limit_without_creating(self, as_marketer, settings):
        settings.NEWSLETTER_DAILY_CAP = 10
        set_sent(4)
        news = make_news()
        subscribers(3)

        response = action(as_marketer, NEWS_URL, "send_newsletter", news)

        assert response.status_code == 200
        assert response.templates[0].name == "admin/common/newsletter_send_confirmation.html"
        html = response.content.decode()
        assert "Отправить 3 подписчикам?" in html
        assert "За сутки уйдёт не больше 6" in html
        assert "Остаток останется в очереди" not in html
        assert news.title in html
        assert 'name="post" value="yes"' in html
        assert f'name="_selected_action" value="{news.pk}"' in html
        assert 'name="action" value="send_newsletter"' in html
        assert f'href="{NEWS_URL}"' in html  # «Отмена» и крошки — в разделе маркетинга
        assert 'href="/admin/' not in html
        assert not NewsletterCampaign.objects.filter(news=news).exists()

    def test_page_mentions_remainder_only_above_quota(self, as_marketer, settings):
        settings.NEWSLETTER_DAILY_CAP = 2
        news = make_news()
        subscribers(3)

        html = action(as_marketer, NEWS_URL, "send_newsletter", news).content.decode()

        assert "Отправить 3 подписчикам?" in html
        assert "За сутки уйдёт не больше 2" in html
        assert "Остаток останется в очереди" in html

    def test_cancel_sends_nothing(self, as_marketer):
        news = make_news()
        subscribers(2)

        with patch(DELAY) as delay:
            action(as_marketer, NEWS_URL, "send_newsletter", news)
            response = as_marketer.get(NEWS_URL)  # «Отмена» — ссылка на список

        assert response.status_code == 200
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()
        assert mail.outbox == []

    def test_confirm_starts_campaign_and_journal(self, as_marketer, marketer):
        news = make_news()
        readers = subscribers(3)

        with patch(DELAY, side_effect=lambda campaign_id: tasks.send_newsletter_campaign(campaign_id)) as delay:
            response = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)

        campaign = NewsletterCampaign.objects.get(news=news)
        delay.assert_called_once_with(campaign.pk)
        assert any("Рассылка запущена" in text and "получателей — 3" in text for text in texts(response))
        assert not any("остаток" in text for text in texts(response))
        assert sorted(email.to[0] for email in mail.outbox) == sorted(r.email for r in readers)
        for email in mail.outbox:
            assert "List-Unsubscribe" in email.extra_headers and "List-Unsubscribe-Post" in email.extra_headers
            assert f"/news/{news.slug}" in email.body
        entry = AuditLog.objects.get(action="newsletter_send")
        assert (entry.user, entry.resource_type, entry.resource_id) == (marketer, "News", str(news.pk))

        listing = as_marketer.get(NEWS_URL).content.decode()
        assert "отправлено 3 · ошибок 0 · в очереди 0" in listing

    def test_more_than_one_selected_is_refused(self, as_marketer):
        first, second = make_news(), make_news()
        subscribers(1)

        with patch(DELAY) as delay:
            response = action(as_marketer, NEWS_URL, "send_newsletter", first, second)
            confirmed = action(as_marketer, NEWS_URL, "send_newsletter", first, second, confirm=True)

        assert ONE_ARTICLE_MESSAGE in texts(response)
        assert ONE_ARTICLE_MESSAGE in texts(confirmed)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    @pytest.mark.parametrize("confirm", [False, True])
    def test_unpublished_is_refused(self, as_marketer, confirm):
        news = make_news(is_published=False)
        subscribers(1)

        with patch(DELAY) as delay:
            response = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=confirm)

        assert NOT_PUBLISHED_MESSAGE in texts(response)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    def test_queue_down_keeps_rows_pending(self, as_marketer):
        news = make_news()
        subscribers(2)

        with patch(DELAY, side_effect=ConnectionError("redis down")):
            response = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)

        assert QUEUE_DOWN_MESSAGE in texts(response)
        campaign = NewsletterCampaign.objects.get(news=news)
        assert list(campaign.deliveries.values_list("status", flat=True)) == ["pending", "pending"]
        assert mail.outbox == []
        assert not AuditLog.objects.filter(action="newsletter_send").exists()

    def test_success_mentions_remainder_above_quota(self, as_marketer, settings):
        settings.NEWSLETTER_DAILY_CAP = 2
        news = make_news()
        subscribers(3)

        with patch(DELAY):
            response = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)

        assert any("получателей — 3" in text and "За сутки уйдёт не больше 2 писем" in text for text in texts(response))

    @pytest.mark.parametrize("confirm", [False, True])
    def test_cap_exhausted_is_refused(self, as_marketer, settings, confirm):
        settings.NEWSLETTER_DAILY_CAP = 1
        set_sent(1)
        news = make_news()
        subscribers(1)

        with patch(DELAY) as delay:
            response = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=confirm)

        assert CAP_REACHED_MESSAGE in texts(response)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.filter(news=news).exists()

    def test_already_sent_to_all(self, as_marketer):
        news = make_news()
        subscribers(1)
        with patch(DELAY, side_effect=lambda campaign_id: tasks.send_newsletter_campaign(campaign_id)):
            action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)
        mail.outbox.clear()

        with patch(DELAY) as delay:
            response = action(as_marketer, NEWS_URL, "send_newsletter", news)
            confirmed = action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)

        assert ALREADY_SENT_MESSAGE in texts(response)
        assert ALREADY_SENT_MESSAGE in texts(confirmed)
        delay.assert_not_called()
        assert mail.outbox == []

    def test_blog_post_by_supervisor(self):
        supervisor = make_staff_member(SUPERVISORS_GROUP)
        post = make_post()
        subscribers(1)

        with patch(DELAY) as delay:
            response = action(logged_in(supervisor), BLOG_URL, "send_newsletter", post, confirm=True)

        campaign = NewsletterCampaign.objects.get(blog_post=post)
        delay.assert_called_once_with(campaign.pk)
        assert any("Статья блога" in text for text in texts(response))


class TestTestLetter:
    def test_goes_to_staff_only(self, as_marketer, marketer):
        news = make_news()
        subscribers(3)

        response = action(as_marketer, NEWS_URL, "send_newsletter_test", news)

        assert f"Тестовое письмо отправлено на {marketer.email}." in texts(response)
        assert [email.to for email in mail.outbox] == [[marketer.email]]
        assert "List-Unsubscribe" not in mail.outbox[0].extra_headers
        assert mail.outbox[0].body.startswith(TEST_EMAIL_NOTICE)
        assert not NewsletterCampaign.objects.exists() and not NewsletterDelivery.objects.exists()

    @pytest.mark.parametrize("status", ["failed", STATUS_MAILBOX_FAILED])
    def test_transport_failure_shows_error(self, as_marketer, status):
        news = make_news()
        failure = TransportResult(status=status, error="SMTPDataError: (554, b'5.7.1 rejected')")

        with patch.object(SmtpMarketingTransport, "send", return_value=failure):
            response = action(as_marketer, NEWS_URL, "send_newsletter_test", news)

        assert TEST_FAILED_MESSAGE in texts(response)
        assert not any("Тестовое письмо отправлено" in text for text in texts(response))
        assert mail.outbox == []
        assert not NewsletterCampaign.objects.exists()

    def test_more_than_one_selected_is_refused(self, as_marketer):
        response = action(as_marketer, NEWS_URL, "send_newsletter_test", make_news(), make_news())

        assert ONE_ARTICLE_MESSAGE in texts(response)
        assert mail.outbox == []

    def test_staff_without_email(self):
        member = make_staff_member(MARKETING_GROUP)
        User.objects.filter(pk=member.pk).update(email="")
        member.refresh_from_db()

        response = action(logged_in(member), NEWS_URL, "send_newsletter_test", make_news())

        assert any("не указан email" in text for text in texts(response))
        assert mail.outbox == []


class TestColumn:
    def test_counters_and_dash(self, as_marketer):
        sent_news, fresh_news = make_news(), make_news()
        a, b, c, d = subscribers(4)
        campaign = NewsletterCampaign.objects.create(news=sent_news)
        for subscription, status in ((a, "sent"), (b, "failed"), (c, "pending"), (d, "sending")):
            NewsletterDelivery.objects.create(campaign=campaign, newsletter=subscription, status=status)

        response = as_marketer.get(NEWS_URL)

        rows = {
            obj.pk: response.context["cl"].model_admin.newsletter_status(obj)
            for obj in response.context["cl"].result_list
        }
        assert rows[sent_news.pk] == "отправлено 1 · ошибок 1 · в очереди 2"
        assert rows[fresh_news.pk] == "—"
        assert "Рассылка" in response.content.decode()

    def test_column_does_not_add_queries_per_row(self, as_marketer):
        def add(count: int) -> None:
            for _ in range(count):
                news = make_news()
                campaign = NewsletterCampaign.objects.create(news=news)
                NewsletterDelivery.objects.create(campaign=campaign, newsletter=subscribers(1)[0], status="sent")

        add(2)
        with CaptureQueriesContext(connection) as first:
            assert as_marketer.get(NEWS_URL).status_code == 200
        add(5)
        with CaptureQueriesContext(connection) as second:
            assert as_marketer.get(NEWS_URL).status_code == 200

        assert len(second) == len(first)

    def test_news_with_campaign_can_be_deleted(self, as_marketer):
        news = make_news()
        subscribers(1)
        with patch(DELAY):
            action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)

        response = action(as_marketer, NEWS_URL, "delete_selected", news, confirm=True)

        assert response.status_code == 200
        assert not News.objects.filter(pk=news.pk).exists()
        assert not NewsletterCampaign.objects.exists()
        # Строки доставки остаются для суточного потолка (SET_NULL).
        assert NewsletterDelivery.objects.filter(campaign__isnull=True).count() == 1


class TestJournal:
    def test_supervisor_sees_mailing_with_article(self, as_marketer, marketer):
        post = make_post()
        subscribers(2)
        with patch(DELAY):
            action(as_marketer, BLOG_URL, "send_newsletter", post, confirm=True)

        html = logged_in(make_staff_member(SUPERVISORS_GROUP)).get(JOURNAL_URL).content.decode()

        assert "Рассылка подписчикам" in html
        assert f"Статья блога «{post.title}»" in html
        assert "получателей: 2" in html
        assert f'href="{BLOG_URL}{post.pk}/change/"' in html

    def test_deleted_article_has_no_link(self, as_marketer):
        news = make_news()
        subscribers(1)
        with patch(DELAY):
            action(as_marketer, NEWS_URL, "send_newsletter", news, confirm=True)
        title, pk = news.title, news.pk
        news.delete()

        html = logged_in(make_staff_member(SUPERVISORS_GROUP)).get(JOURNAL_URL).content.decode()

        assert f"Новость «{title}»" in html
        assert f"{NEWS_URL}{pk}/change/" not in html


# --------------------------------------------------------------------------
# Кнопки на форме материала
# --------------------------------------------------------------------------

SEND_BUTTON = "_newsletter_send"
TEST_BUTTON = "_newsletter_test"
FILTERS = "is_published__exact%3D1"  # `_changelist_filters` из списка с фильтром


@dataclass
class Section:
    """Форма материала в разделе: кто работает, какой каталог и чем создавать материал."""

    browser: Client
    user: User
    base: str
    make: Callable[..., Any]
    model: type

    def change_url(self, article: Any, query: str = "") -> str:
        return f"{self.base}{article.pk}/change/{query}"

    def confirm_url(self, article: Any, query: str = "") -> str:
        return f"{self.base}{article.pk}/newsletter/confirm/{query}"


@pytest.fixture(params=["marketing-news", "marketing-blog", "admin-news", "admin-blog"])
def section(request) -> Section:
    site, kind = request.param.split("-")
    if site == "marketing":
        user = make_staff_member(MARKETING_GROUP)
    else:
        user = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
    if kind == "news":
        base, make, model = ("/marketing/common/news/" if site == "marketing" else ADMIN_NEWS_URL), make_news, News
    else:
        base, make, model = (
            ("/marketing/common/blogpost/" if site == "marketing" else "/admin/common/blogpost/"),
            make_post,
            BlogPost,
        )
    return Section(browser=logged_in(user), user=user, base=base, make=make, model=model)


def form_data(slug: str | None = None, **overrides: Any) -> dict[str, Any]:
    """Поля формы новости/статьи; `None` в overrides убирает поле (снятая галочка)."""
    published = timezone.localtime(timezone.now() - timedelta(days=1))
    data: dict[str, Any] = {
        "title": "Заголовок формы",
        "slug": slug or f"form-{get_unique_suffix()}",
        "subtitle": "",
        "author": "",
        "excerpt": "Анонс формы",
        "content": "<p>Текст формы</p>",
        "is_published": "on",
        "published_at_0": published.strftime("%Y-%m-%d"),
        "published_at_1": published.strftime("%H:%M:%S"),
    }
    data.update(overrides)
    return {key: value for key, value in data.items() if value is not None}


def location(response) -> str:
    return response["Location"]


class TestButtonsOnForm:
    @pytest.mark.parametrize("form", ["add", "change"])
    def test_buttons_follow_the_save_button(self, section, form):
        article = section.make()
        url = f"{section.base}add/" if form == "add" else section.change_url(article)

        html = section.browser.get(url).content.decode()

        standard = html.index('class="submit-row"')
        ours = html.index('class="submit-row newsletter-submit-row"')
        assert standard < html.index('name="_save"') < ours
        assert ours < html.index(f'name="{SEND_BUTTON}"')
        assert ours < html.index(f'name="{TEST_BUTTON}"')
        assert "Сохранить и сделать рассылку" in html
        assert "Сохранить и отправить тестовое письмо на мой e-mail" in html

    @pytest.mark.parametrize("group", [MARKETING_GROUP, SUPERVISORS_GROUP])
    @pytest.mark.parametrize("base", [NEWS_URL, BLOG_URL])
    def test_section_roles_see_buttons(self, group, base):
        article = make_news() if base == NEWS_URL else make_post()

        html = logged_in(make_staff_member(group)).get(f"{base}{article.pk}/change/").content.decode()

        assert f'name="{SEND_BUTTON}"' in html and f'name="{TEST_BUTTON}"' in html

    def test_view_only_has_no_buttons_and_cannot_post(self):
        user = make_staff_member(MARKETING_GROUP)
        Group.objects.get(name=MARKETING_GROUP).permissions.set(
            Permission.objects.filter(codename__in=["view_news", "view_blogpost"])
        )
        news = make_news()
        browser = logged_in(user)

        html = browser.get(f"{NEWS_URL}{news.pk}/change/").content.decode()
        response = browser.post(f"{NEWS_URL}{news.pk}/change/", form_data(news.slug, **{TEST_BUTTON: "1"}))

        assert SEND_BUTTON not in html and TEST_BUTTON not in html
        assert response.status_code == 403
        assert mail.outbox == []

    @pytest.mark.parametrize("button", [SEND_BUTTON, TEST_BUTTON])
    def test_add_without_change_saves_but_does_nothing(self, button):
        user = make_staff_member(MARKETING_GROUP)
        Group.objects.get(name=MARKETING_GROUP).permissions.set(
            Permission.objects.filter(codename__in=["add_news", "view_news"])
        )
        browser = logged_in(user)
        subscribers(2)

        html = browser.get(f"{NEWS_URL}add/").content.decode()
        with patch(DELAY) as delay:
            response = browser.post(f"{NEWS_URL}add/", form_data("no-change-role", **{button: "1"}))

        assert SEND_BUTTON not in html and TEST_BUTTON not in html
        assert response.status_code == 302
        assert "/newsletter/confirm/" not in response["Location"]
        assert News.objects.filter(slug="no-change-role").exists()
        delay.assert_not_called()
        assert mail.outbox == []
        assert not NewsletterCampaign.objects.exists()

    def test_plain_save_does_nothing(self, section):
        subscribers(2)

        with patch(DELAY) as delay:
            response = section.browser.post(f"{section.base}add/", form_data(), follow=True)

        assert response.status_code == 200
        assert section.model.objects.count() == 1
        delay.assert_not_called()
        assert mail.outbox == [] and not NewsletterCampaign.objects.exists()

    @pytest.mark.parametrize("button", [SEND_BUTTON, TEST_BUTTON])
    def test_popup_save_does_nothing(self, button):
        user = make_staff_member(MARKETING_GROUP)
        browser = logged_in(user)
        subscribers(2)

        with patch(DELAY) as delay:
            response = browser.post(f"{NEWS_URL}add/", form_data("popup-save", _popup="1", **{button: "1"}))

        assert response.status_code == 200  # штатный ответ popup, без редиректа кнопки
        assert News.objects.filter(slug="popup-save").exists()
        delay.assert_not_called()
        assert mail.outbox == []
        assert not NewsletterCampaign.objects.exists()


class TestTestButton:
    def test_add_form_saves_and_sends_to_staff_only(self, section):
        subscribers(3)

        response = section.browser.post(f"{section.base}add/", form_data(**{TEST_BUTTON: "1"}), follow=True)

        article = section.model.objects.get()
        assert response.redirect_chain[-1][0] == section.change_url(article)
        assert response.status_code == 200
        shown = texts(response)
        assert len(shown) == 2 and shown[0] != shown[1]  # штатное сообщение сохранения, затем тест
        assert f"Тестовое письмо отправлено на {section.user.email}." in shown
        assert [email.to for email in mail.outbox] == [[section.user.email]]
        assert "List-Unsubscribe" not in mail.outbox[0].extra_headers
        assert not NewsletterCampaign.objects.exists() and not NewsletterDelivery.objects.exists()

    def test_change_form_saves_edit_and_sends_draft(self, section):
        article = section.make(is_published=False, published_at=None)

        response = section.browser.post(
            section.change_url(article),
            form_data(article.slug, title="Правка перед тестом", is_published=None, **{TEST_BUTTON: "1"}),
            follow=True,
        )

        article.refresh_from_db()
        assert article.title == "Правка перед тестом" and article.is_published is False
        assert response.redirect_chain[-1][0] == section.change_url(article)
        assert f"Тестовое письмо отправлено на {section.user.email}." in texts(response)
        assert len(mail.outbox) == 1 and mail.outbox[0].subject == "Правка перед тестом"

    def test_empty_staff_email_shows_own_message(self):
        member = make_staff_member(MARKETING_GROUP)
        User.objects.filter(pk=member.pk).update(email="")
        news = make_news()

        response = logged_in(member).post(
            f"{NEWS_URL}{news.pk}/change/",
            form_data(news.slug, title="Сохранено без email", **{TEST_BUTTON: "1"}),
            follow=True,
        )

        news.refresh_from_db()
        assert news.title == "Сохранено без email"
        assert NO_EMAIL_MESSAGE in texts(response)
        assert TEST_FAILED_MESSAGE not in texts(response)
        assert mail.outbox == []

    @pytest.mark.parametrize("status", ["failed", STATUS_MAILBOX_FAILED])
    def test_transport_failure_keeps_saved_material(self, section, status):
        failure = TransportResult(status=status, error="SMTPDataError: (554, b'5.7.1 rejected')")

        with patch.object(SmtpMarketingTransport, "send", return_value=failure):
            response = section.browser.post(f"{section.base}add/", form_data(**{TEST_BUTTON: "1"}), follow=True)

        assert section.model.objects.count() == 1
        assert TEST_FAILED_MESSAGE in texts(response)
        assert mail.outbox == []

    def test_value_error_keeps_saved_material(self, section, caplog):
        with patch("apps.common.admin.send_test", side_effect=ValueError("boom")):
            response = section.browser.post(f"{section.base}add/", form_data(**{TEST_BUTTON: "1"}), follow=True)

        assert section.model.objects.count() == 1
        assert TEST_FAILED_MESSAGE in texts(response)
        assert any(
            record.name == "apps.common.admin" and record.exc_info for record in caplog.records
        )  # logger.exception

    def test_database_error_does_not_poison_the_transaction(self, section):
        def broken_query(article, user):
            with connection.cursor() as cursor:
                cursor.execute("SELECT * FROM no_such_newsletter_table")

        with patch("apps.common.admin.send_test", side_effect=broken_query):
            response = section.browser.post(f"{section.base}add/", form_data(**{TEST_BUTTON: "1"}), follow=True)

        # Без savepoint транзакция формы отравлена: сохранение потеряно, запросы падают.
        assert section.model.objects.count() == 1
        assert User.objects.filter(pk=section.user.pk).exists()
        assert TEST_FAILED_MESSAGE in texts(response)

    def test_validation_error_does_not_send(self, section):
        response = section.browser.post(f"{section.base}add/", form_data(title="", **{TEST_BUTTON: "1"}))

        assert response.status_code == 200
        assert "errornote" in response.content.decode()
        assert section.model.objects.count() == 0
        assert mail.outbox == []


class TestSendButton:
    def test_redirects_to_confirmation_without_sending(self, section):
        subscribers(3)

        with patch(DELAY) as delay:
            response = section.browser.post(f"{section.base}add/", form_data(**{SEND_BUTTON: "1"}))

        article = section.model.objects.get()
        assert response.status_code == 302
        assert location(response) == section.confirm_url(article)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists() and mail.outbox == []

    def test_confirmation_page_is_get_and_repeatable(self, section):
        article = section.make()
        subscribers(3)

        first = section.browser.get(section.confirm_url(article))
        second = section.browser.get(section.confirm_url(article))  # F5

        assert first.status_code == second.status_code == 200
        html = first.content.decode()
        assert "Отправить 3 подписчикам?" in html
        assert 'name="csrfmiddlewaretoken"' in html
        assert 'name="post"' not in html and 'name="action"' not in html  # не форма действия списка
        assert f'action="{section.confirm_url(article)}"' in html
        assert f'href="{section.change_url(article)}"' in html  # «Отмена» — на форму материала
        assert not NewsletterCampaign.objects.exists()

    def test_yes_starts_campaign_and_goes_to_list(self, section):
        article = section.make()
        readers = subscribers(2)

        with patch(DELAY, side_effect=lambda campaign_id: tasks.send_newsletter_campaign(campaign_id)) as delay:
            response = section.browser.post(section.confirm_url(article), follow=True)

        campaign = NewsletterCampaign.objects.get(**{"news" if section.model is News else "blog_post": article})
        delay.assert_called_once_with(campaign.pk)
        assert response.redirect_chain[-1][0] == section.base
        assert any("Рассылка запущена" in text and "получателей — 2" in text for text in texts(response))
        assert sorted(email.to[0] for email in mail.outbox) == sorted(r.email for r in readers)
        entry = AuditLog.objects.get(action="newsletter_send")
        assert (entry.user, entry.resource_type, entry.resource_id) == (
            section.user,
            section.model.__name__,
            str(article.pk),
        )

    def test_full_path_from_form(self, section):
        subscribers(2)

        with patch(DELAY) as delay:
            sent = section.browser.post(f"{section.base}add/", form_data(**{SEND_BUTTON: "1"}))
            page = section.browser.get(location(sent))
            confirmed = section.browser.post(location(sent), follow=True)

        assert page.status_code == 200 and "Отправить 2 подписчикам?" in page.content.decode()
        delay.assert_called_once()
        assert any("Рассылка запущена" in text for text in texts(confirmed))

    def test_cancel_sends_nothing(self, section):
        article = section.make()
        subscribers(2)
        html = section.browser.get(section.confirm_url(article)).content.decode()

        with patch(DELAY) as delay:
            cancelled = section.browser.get(section.change_url(article))  # «Отмена» — ссылка на форму

        assert f'href="{section.change_url(article)}"' in html
        assert cancelled.status_code == 200
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists() and mail.outbox == []

    def test_draft_is_saved_but_not_sent(self, section):
        subscribers(2)

        with patch(DELAY) as delay:
            response = section.browser.post(
                f"{section.base}add/", form_data(is_published=None, **{SEND_BUTTON: "1"}), follow=True
            )

        article = section.model.objects.get()
        assert response.redirect_chain[-1][0] == section.change_url(article)
        assert NOT_PUBLISHED_MESSAGE in texts(response)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    def test_future_publication_date_is_refused(self, section):
        article = section.make(published_at=timezone.now() + timedelta(days=2))
        subscribers(1)

        direct = section.browser.get(section.confirm_url(article), follow=True)

        assert direct.redirect_chain[-1][0] == section.change_url(article)
        assert NOT_PUBLISHED_MESSAGE in texts(direct)
        assert not NewsletterCampaign.objects.exists()

    def test_unpublished_after_confirmation_page_is_refused_on_yes(self, section):
        article = section.make()
        subscribers(1)
        section.browser.get(section.confirm_url(article))
        section.model.objects.filter(pk=article.pk).update(is_published=False)

        with patch(DELAY) as delay:
            response = section.browser.post(section.confirm_url(article), follow=True)

        assert NOT_PUBLISHED_MESSAGE in texts(response)
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    def test_cap_exhausted_returns_to_form(self, section, settings):
        settings.NEWSLETTER_DAILY_CAP = 1
        set_sent(1)
        article = section.make()
        subscribers(1)

        with patch(DELAY) as delay:
            page = section.browser.get(section.confirm_url(article), follow=True)
            posted = section.browser.post(section.confirm_url(article), follow=True)

        for response in (page, posted):
            assert response.redirect_chain[-1][0] == section.change_url(article)
            assert CAP_REACHED_MESSAGE in texts(response)
        delay.assert_not_called()

    def test_already_sent_returns_to_form(self, section):
        article = section.make()
        subscribers(1)
        with patch(DELAY, side_effect=lambda campaign_id: tasks.send_newsletter_campaign(campaign_id)):
            section.browser.post(section.confirm_url(article))
        mail.outbox.clear()

        with patch(DELAY) as delay:
            page = section.browser.get(section.confirm_url(article), follow=True)
            posted = section.browser.post(section.confirm_url(article), follow=True)

        for response in (page, posted):
            assert response.redirect_chain[-1][0] == section.change_url(article)
            assert ALREADY_SENT_MESSAGE in texts(response)
        delay.assert_not_called()
        assert mail.outbox == []

    def test_queue_down_returns_to_form(self, section):
        article = section.make()
        subscribers(2)

        with patch(DELAY, side_effect=ConnectionError("redis down")):
            response = section.browser.post(section.confirm_url(article), follow=True)

        assert response.redirect_chain[-1][0] == section.change_url(article)
        assert QUEUE_DOWN_MESSAGE in texts(response)
        assert not AuditLog.objects.filter(action="newsletter_send").exists()

    def test_validation_error_does_not_redirect(self, section):
        subscribers(1)

        with patch(DELAY) as delay:
            response = section.browser.post(f"{section.base}add/", form_data(title="", **{SEND_BUTTON: "1"}))

        assert response.status_code == 200
        assert "errornote" in response.content.decode()
        assert section.model.objects.count() == 0
        delay.assert_not_called()


class TestConfirmationAccess:
    def test_unknown_pk_is_404(self, section):
        assert section.browser.get(f"{section.base}999999/newsletter/confirm/").status_code == 404

    def test_url_is_not_swallowed_by_catch_all(self, section):
        article = section.make()
        subscribers(1)

        response = section.browser.get(section.confirm_url(article))

        assert response.status_code == 200  # не редирект catch-all `<path:object_id>/`
        assert "newsletter-confirmation" in response.content.decode()

    @pytest.mark.parametrize("method", ["get", "post"])
    def test_view_only_is_forbidden(self, method):
        user = make_staff_member(MARKETING_GROUP)
        Group.objects.get(name=MARKETING_GROUP).permissions.set(
            Permission.objects.filter(codename__in=["view_news", "view_blogpost"])
        )
        news = make_news()
        subscribers(1)

        with patch(DELAY) as delay:
            response = getattr(logged_in(user), method)(f"{NEWS_URL}{news.pk}/newsletter/confirm/")

        assert response.status_code == 403
        delay.assert_not_called()
        assert not NewsletterCampaign.objects.exists()

    def test_manager_has_no_access(self):
        news = make_news()

        response = logged_in(make_staff_member(MANAGERS_GROUP)).get(f"{NEWS_URL}{news.pk}/newsletter/confirm/")

        assert response.status_code == 302 and "/marketing/login/" in response["Location"]

    def test_anonymous_is_sent_to_login(self):
        news = make_news()

        response = Client().get(f"{NEWS_URL}{news.pk}/newsletter/confirm/")

        assert response.status_code == 302 and "login" in response["Location"]

    def test_other_methods_are_not_allowed(self, as_marketer):
        news = make_news()

        assert as_marketer.put(f"{NEWS_URL}{news.pk}/newsletter/confirm/").status_code == 405

    def test_superuser_in_marketing_goes_to_login(self):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        news = make_news()

        response = logged_in(superuser).get(f"{NEWS_URL}{news.pk}/change/")

        assert response.status_code == 302 and "/marketing/login/" in response["Location"]


class TestPreservedFilters:
    def test_test_button_keeps_filters(self, section):
        article = section.make()

        response = section.browser.post(
            section.change_url(article, f"?_changelist_filters={FILTERS}"),
            form_data(article.slug, **{TEST_BUTTON: "1"}),
        )

        assert response.status_code == 302
        assert location(response) == section.change_url(article, f"?_changelist_filters={FILTERS}")

    def test_test_button_on_add_form_keeps_filters(self, section):
        response = section.browser.post(
            f"{section.base}add/?_changelist_filters={FILTERS}", form_data(**{TEST_BUTTON: "1"})
        )

        article = section.model.objects.get()
        assert location(response) == section.change_url(article, f"?_changelist_filters={FILTERS}")

    def test_filters_pass_form_confirmation_list_and_cancel(self, section):
        article = section.make()
        subscribers(2)
        query = f"?_changelist_filters={FILTERS}"

        sent = section.browser.post(section.change_url(article, query), form_data(article.slug, **{SEND_BUTTON: "1"}))
        assert location(sent) == section.confirm_url(article, query)

        page = section.browser.get(location(sent)).content.decode()
        assert f'href="{section.change_url(article, query)}"'.replace("&", "&amp;") in page  # «Отмена» → форма
        assert f'action="{section.confirm_url(article, query)}"'.replace("&", "&amp;") in page

        with patch(DELAY):
            yes = section.browser.post(section.confirm_url(article, query))
        assert location(yes) == f"{section.base}?is_published__exact=1"  # «Да» → список с фильтром

    def test_filters_survive_form_back_from_refusal(self, section):
        article = section.make(is_published=False, published_at=None)
        query = f"?_changelist_filters={FILTERS}"

        response = section.browser.get(section.confirm_url(article, query))

        assert location(response) == section.change_url(article, query)

    def test_list_action_confirmation_is_unchanged(self, section):
        article = section.make()
        subscribers(2)

        response = action(section.browser, section.base, "send_newsletter", article)

        html = response.content.decode()
        assert response.status_code == 200
        assert 'name="post" value="yes"' in html and 'name="action" value="send_newsletter"' in html
        assert f'name="_selected_action" value="{article.pk}"' in html
        assert f'href="{section.base}"' in html  # «Отмена» — в список

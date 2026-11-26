"""
Рассылка новостей и статей блога подписчикам `Newsletter`.

Запуск — вручную из списков новостей и статей (`/marketing/`, `/admin/`):
`start_campaign` готовит кампанию и строки доставки, задача
`apps.common.tasks.send_newsletter_campaign` их отправляет. `send_test` шлёт
письмо по материалу только сотруднику, без кампании и учёта.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone
from django.utils.html import strip_tags
from django.utils.text import Truncator

from apps.common.models import AuditLog, BlogPost, News, Newsletter, NewsletterCampaign, NewsletterDelivery
from apps.common.services.marketing_email import (
    ArticleContent,
    MarketingMessageBuilder,
    SmtpMarketingTransport,
    TransportResult,
)

Article = News | BlogPost

# `sending` дольше этого срока — брошенная строка (воркер упал), повторный запуск
# возвращает её в `pending`.
STALE_SENDING_AFTER = timedelta(minutes=15)
EXCERPT_FALLBACK_WORDS = 40
# Конец блока и перевод строки — граница слов: иначе strip_tags склеит
# «конца.</p><p>Начало» в «конца.Начало».
BLOCK_BOUNDARY = re.compile(
    r"</(?:p|div|li|ul|ol|h[1-6]|blockquote|pre|table|tr|td|th|section|article|figure|figcaption)\s*>|<br\s*/?>",
    re.IGNORECASE,
)
AUDIT_ACTION = "newsletter_send"

NOT_PUBLISHED_MESSAGE = "Рассылать можно только опубликованный материал с наступившей датой публикации."
CAP_REACHED_MESSAGE = "Суточный потолок рассылки исчерпан, повторите завтра."
NO_EMAIL_MESSAGE = "У вашей учётной записи не указан email — тестовое письмо отправить некуда."


class NewsletterCampaignError(Exception):
    """Отказ в запуске; текст показывается сотруднику как есть."""


@dataclass(frozen=True)
class CampaignStart:
    campaign: NewsletterCampaign
    queued: int


def article_kind(article: Article) -> str:
    return "news" if isinstance(article, News) else "blog"


def article_label(article: Article) -> str:
    kind = "Новость" if isinstance(article, News) else "Статья блога"
    return f"{kind} «{article.title}»"


def is_published(article: Article, now: Any = None) -> bool:
    """Тот же критерий, что у публичного API: флаг и наступившая дата публикации."""
    now = now or timezone.now()
    return bool(article.is_published and article.published_at and article.published_at <= now)


def _site_url() -> str:
    return str(settings.SITE_URL).rstrip("/")


def article_url(article: Article) -> str:
    # Только сборкой: get_absolute_url новости ведёт в JSON API, у статьи — NoReverseMatch.
    section = "news" if isinstance(article, News) else "blog"
    return f"{_site_url()}/{section}/{article.slug}"


def article_image_url(article: Article) -> str | None:
    if not article.image:
        return None
    url = article.image.url
    if url.startswith(("http://", "https://")):
        return str(url)
    return f"{_site_url()}{url}"


def plain_text(value: str) -> str:
    """Текст HTML без тегов: блоки и `<br>` разделены пробелом, пробелы схлопнуты."""
    text = html.unescape(strip_tags(BLOCK_BOUNDARY.sub(" ", value or "")))
    return " ".join(text.split())


def article_content(article: Article) -> ArticleContent:
    """Анонс для письма: `excerpt` (уже очищен в `save()`), пустой — 40 слов из `content`."""
    excerpt_html = (article.excerpt or "").strip()
    if strip_tags(excerpt_html).strip():
        excerpt_text = plain_text(excerpt_html)
    else:
        excerpt_text = Truncator(plain_text(article.content or "")).words(EXCERPT_FALLBACK_WORDS)
        excerpt_html = f"<p>{html.escape(excerpt_text)}</p>" if excerpt_text else ""
    return ArticleContent(
        title=article.title,
        excerpt_html=excerpt_html,
        excerpt_text=excerpt_text,
        url=article_url(article),
        image_url=article_image_url(article),
    )


def daily_sent_count(now: Any = None) -> int:
    now = now or timezone.now()
    return NewsletterDelivery.objects.filter(
        status=NewsletterDelivery.STATUS_SENT, sent_at__gt=now - timedelta(hours=24)
    ).count()


def remaining_daily_quota(now: Any = None) -> int:
    return max(0, int(settings.NEWSLETTER_DAILY_CAP) - daily_sent_count(now))


def _campaign_filter(article: Article) -> dict[str, Article]:
    return {"news": article} if isinstance(article, News) else {"blog_post": article}


def recipients_to_send(article: Article) -> int:
    """Активные подписки, которым этот материал ещё не отправлен (`sent`)."""
    already_sent = NewsletterDelivery.objects.filter(
        newsletter=OuterRef("pk"),
        status=NewsletterDelivery.STATUS_SENT,
        **{f"campaign__{key}": value for key, value in _campaign_filter(article).items()},
    )
    return Newsletter.objects.filter(is_active=True).exclude(Exists(already_sent)).count()


def start_campaign(article: Article, user: Any) -> CampaignStart:
    """
    Готовит рассылку материала и возвращает кампанию после коммита.

    Задачу не ставит: вызывающий после возврата сам зовёт
    `send_newsletter_campaign.delay(campaign.id)` и ловит сбой брокера. Повторный
    запуск досылает: новые активные подписки получают строки, `failed` и
    `suppressed` активных подписок и брошенные `sending` возвращаются в `pending`,
    а `pending` отписавшихся (или удалённых) подписок — в `suppressed`, иначе
    колонка вечно показывала бы их «в очереди». Запись журнала пишет вызывающий
    после успешной постановки задачи (`log_campaign_start`). `queued == 0` —
    отправлять некому.
    """
    now = timezone.now()
    if not is_published(article, now):
        raise NewsletterCampaignError(NOT_PUBLISHED_MESSAGE)
    if remaining_daily_quota(now) <= 0:
        raise NewsletterCampaignError(CAP_REACHED_MESSAGE)

    with transaction.atomic():
        campaign, _ = NewsletterCampaign.objects.get_or_create(
            **_campaign_filter(article), defaults={"created_by": user if user.is_authenticated else None}
        )
        # Блокировка строки кампании сериализует два одновременных запуска.
        campaign = NewsletterCampaign.objects.select_for_update().get(pk=campaign.pk)
        deliveries = NewsletterDelivery.objects.filter(campaign=campaign)
        deliveries.filter(status=NewsletterDelivery.STATUS_SENDING, claimed_at__lt=now - STALE_SENDING_AFTER).update(
            status=NewsletterDelivery.STATUS_PENDING, claimed_at=None
        )
        deliveries.filter(
            status__in=[NewsletterDelivery.STATUS_FAILED, NewsletterDelivery.STATUS_SUPPRESSED],
            newsletter__is_active=True,
        ).update(status=NewsletterDelivery.STATUS_PENDING, claimed_at=None)
        deliveries.filter(
            Q(newsletter__isnull=True) | Q(newsletter__is_active=False),
            status=NewsletterDelivery.STATUS_PENDING,
        ).update(status=NewsletterDelivery.STATUS_SUPPRESSED, claimed_at=None)
        active_ids = Newsletter.objects.filter(is_active=True).values_list("pk", flat=True)
        NewsletterDelivery.objects.bulk_create(
            [NewsletterDelivery(campaign=campaign, newsletter_id=pk) for pk in active_ids],
            ignore_conflicts=True,
        )
        queued = deliveries.filter(status=NewsletterDelivery.STATUS_PENDING, newsletter__is_active=True).count()
        if queued:
            campaign.last_run_at = now
            campaign.save(update_fields=["last_run_at"])
    return CampaignStart(campaign=campaign, queued=queued)


def log_campaign_start(article: Article, user: Any, queued: int) -> AuditLog:
    """Запись «Рассылка подписчикам» в журнал — только когда задача уже поставлена."""
    return AuditLog.log_action(
        user=user,
        action=AUDIT_ACTION,
        resource_type=type(article).__name__,
        resource_id=article.pk,
        changes={"kind": article_kind(article), "title": article.title, "recipients": queued},
    )


def send_test(article: Article, user: Any) -> TransportResult:
    """Письмо по материалу на email сотрудника: без кампании, учёта и заголовков RFC 8058."""
    email = (getattr(user, "email", "") or "").strip()
    if not email:
        raise NewsletterCampaignError(NO_EMAIL_MESSAGE)
    message = MarketingMessageBuilder().build_test(recipient=email, content=article_content(article))
    transport = SmtpMarketingTransport()
    try:
        return transport.send(message)
    finally:
        transport.close()

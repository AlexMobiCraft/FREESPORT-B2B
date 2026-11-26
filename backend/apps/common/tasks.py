"""Celery-задачи приложения common: рассылка новостей и статей блога подписчикам."""

from __future__ import annotations

import logging
import time
from typing import Any

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from apps.common.models import BlogPost, News, NewsletterCampaign, NewsletterDelivery
from apps.common.services.marketing_email import (
    STATUS_MAILBOX_FAILED,
    MarketingDeliveryService,
    SmtpMarketingTransport,
    TransportResult,
)
from apps.common.services.newsletter_campaign import article_content, daily_sent_count, is_published

logger = logging.getLogger(__name__)


def _published_article(campaign: NewsletterCampaign) -> News | BlogPost | None:
    """Материал кампании, перечитанный из БД; снят с публикации или удалён — None."""
    if campaign.news_id:
        article: News | BlogPost | None = News.objects.filter(pk=campaign.news_id).first()
    else:
        article = BlogPost.objects.filter(pk=campaign.blog_post_id).first()
    if article is None or not is_published(article):
        return None
    return article


def _next_pending_id(campaign_id: int) -> int | None:
    return (
        NewsletterDelivery.objects.filter(campaign_id=campaign_id, status=NewsletterDelivery.STATUS_PENDING)
        .order_by("pk")
        .values_list("pk", flat=True)
        .first()
    )


def _claim(delivery_id: int) -> bool:
    """Атомарный захват строки: второй параллельный прогон получит 0 строк и пропустит её."""
    return bool(
        NewsletterDelivery.objects.filter(pk=delivery_id, status=NewsletterDelivery.STATUS_PENDING).update(
            status=NewsletterDelivery.STATUS_SENDING, claimed_at=timezone.now()
        )
    )


def _finish(delivery_id: int, status: str, error: str = "") -> None:
    fields: dict[str, Any] = {"status": status, "error": error}
    if status == NewsletterDelivery.STATUS_SENT:
        fields["sent_at"] = timezone.now()
    NewsletterDelivery.objects.filter(pk=delivery_id).update(**fields)


def _release(delivery_id: int) -> None:
    """Возвращает захваченную строку в очередь: адрес не виноват, письмо уйдёт повторным запуском."""
    NewsletterDelivery.objects.filter(pk=delivery_id, status=NewsletterDelivery.STATUS_SENDING).update(
        status=NewsletterDelivery.STATUS_PENDING, claimed_at=None
    )


@shared_task(ignore_result=True)
def send_newsletter_campaign(campaign_id: int) -> dict[str, Any]:
    """
    Рассылает материал кампании по строкам `pending`, по одному письму на подписку.

    Итерация: пауза `NEWSLETTER_SEND_INTERVAL_SECONDS` после письма предыдущей
    итерации, затем проверки — материал всё ещё опубликован (иначе остановка),
    суточный потолок `NEWSLETTER_DAILY_CAP` не достигнут (иначе остановка, остаток
    ждёт повторного запуска), строка захвачена этим прогоном. Активность подписки
    перепроверяет `MarketingDeliveryService.deliver`. Сбой ящика (вход, соединение,
    421/451, 5.7.x) останавливает прогон сразу: строка возвращается в `pending`,
    каждая следующая попытка продлевала бы блокировку Яндекса. Гарантия
    at-least-once: падение воркера между отправкой и записью статуса оставит строку
    в `sending`, через 15 минут повторный запуск вернёт её в очередь.
    """
    campaign = NewsletterCampaign.objects.filter(pk=campaign_id).first()
    if campaign is None:
        logger.warning("Рассылка: кампания campaign_id=%s не найдена", campaign_id, extra={"campaign_id": campaign_id})
        return {"campaign_id": campaign_id, "stopped": "campaign_missing"}

    cap = int(settings.NEWSLETTER_DAILY_CAP)
    interval = float(settings.NEWSLETTER_SEND_INTERVAL_SECONDS)
    counters = {"sent": 0, "failed": 0, "suppressed": 0}
    stopped = ""
    transport = SmtpMarketingTransport()
    service = MarketingDeliveryService(transport=transport)
    # Предыдущая итерация обращалась к SMTP — перед следующей нужна пауза.
    previous_called_transport = False
    try:
        while True:
            # Пауза — до проверок итерации: снятый за время паузы материал уже не уйдёт.
            # Очередь пуста — паузу не ждём.
            if previous_called_transport and interval > 0:
                if _next_pending_id(campaign_id) is None:
                    break
                time.sleep(interval)
            previous_called_transport = False

            article = _published_article(campaign)
            if article is None:
                stopped = "unpublished"
                logger.warning(
                    "Рассылка campaign_id=%s остановлена: материал снят с публикации или удалён", campaign_id
                )
                break
            if daily_sent_count() >= cap:
                stopped = "daily_cap"
                logger.warning(
                    "Рассылка campaign_id=%s остановлена: суточный потолок %s писем достигнут, "
                    "остаток досылается повторным запуском",
                    campaign_id,
                    cap,
                )
                break
            delivery_id = _next_pending_id(campaign_id)
            if delivery_id is None:
                break
            if not _claim(delivery_id):
                continue
            newsletter_id = NewsletterDelivery.objects.values_list("newsletter_id", flat=True).get(pk=delivery_id)
            try:
                if newsletter_id is None:
                    # Подписку удалили после постановки: строка осталась (SET_NULL), слать некому.
                    result = TransportResult(status=NewsletterDelivery.STATUS_SUPPRESSED)
                else:
                    result = service.deliver(
                        recipient_ref=newsletter_id,
                        campaign_id=str(campaign_id),
                        subject=article.title,
                        content=article_content(article),
                    )
            except Exception as exc:  # noqa: BLE001 — сбой одного письма не останавливает рассылку
                logger.exception(
                    "Рассылка campaign_id=%s: сбой подготовки письма для подписки %s", campaign_id, newsletter_id
                )
                _finish(delivery_id, NewsletterDelivery.STATUS_FAILED, f"{type(exc).__name__}: {exc}"[:1000])
                counters["failed"] += 1
                continue

            if result.status == STATUS_MAILBOX_FAILED:
                _release(delivery_id)
                stopped = "mailbox"
                logger.error(
                    "Рассылка campaign_id=%s остановлена: почтовый ящик отклонил отправку (%s). "
                    "Строка и остаток ждут повторного запуска",
                    campaign_id,
                    result.error,
                )
                break
            # Подавленный адрес транспорт не трогает — паузы после него не нужно.
            previous_called_transport = result.status != NewsletterDelivery.STATUS_SUPPRESSED
            if result.status == NewsletterDelivery.STATUS_SENT:
                _finish(delivery_id, NewsletterDelivery.STATUS_SENT)
                counters["sent"] += 1
            elif result.status == NewsletterDelivery.STATUS_SUPPRESSED:
                _finish(delivery_id, NewsletterDelivery.STATUS_SUPPRESSED)
                counters["suppressed"] += 1
            else:
                _finish(delivery_id, NewsletterDelivery.STATUS_FAILED, result.error)
                counters["failed"] += 1
                logger.error(
                    "Рассылка campaign_id=%s: письмо подписке %s не отправлено: %s",
                    campaign_id,
                    newsletter_id,
                    result.error,
                )
    finally:
        transport.close()

    logger.info(
        "Рассылка campaign_id=%s: отправлено %s, ошибок %s, подавлено %s%s",
        campaign_id,
        counters["sent"],
        counters["failed"],
        counters["suppressed"],
        f", остановлена ({stopped})" if stopped else "",
    )
    return {"campaign_id": campaign_id, **counters, "stopped": stopped}

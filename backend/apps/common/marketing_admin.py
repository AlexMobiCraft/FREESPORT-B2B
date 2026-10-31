"""
Раздел маркетинга `/marketing/` — новости, блог и рубрики (стори 42.6).

Новости и статьи — родительские admin-классы с полным доступом; отличие одно:
нет ссылки «Смотреть на сайте» (`get_absolute_url` новости ведёт в JSON API,
у статьи и рубрики — в несуществующий маршрут, то есть 500 по клику). Рубрики —
тот же `ContentCategoryAdmin`, что в `/admin/`. Подписчики рассылки на сайте не
зарегистрированы: главная показывает только их число (`newsletter_stats`).

Модуль импортируется из `CommonConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/common/admin.py`.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from apps.common.admin import BlogPostAdmin, ContentCategoryAdmin, NewsAdmin
from apps.common.models import BlogPost, Category, News, Newsletter
from freesport.admin_site import marketing_site

NEWSLETTER_RECENT_DAYS = 30


class MarketingNewsAdmin(NewsAdmin):
    view_on_site = False


class MarketingBlogPostAdmin(BlogPostAdmin):
    view_on_site = False


def newsletter_stats() -> dict[str, Any]:
    """
    Число активных подписок и прирост за последние 30 дней — один запрос.

    Прирост — активные подписки с датой подписки за 30 дней. Повторная подписка
    после отписки сохраняет исходную дату и в прирост не попадает.
    """
    since = timezone.now() - timedelta(days=NEWSLETTER_RECENT_DAYS)
    stats = Newsletter.objects.filter(is_active=True).aggregate(
        total=Count("pk"),
        recent=Count("pk", filter=Q(subscribed_at__gte=since)),
    )
    total, recent = stats["total"], stats["recent"]
    return {
        "total": total,
        "recent": recent,
        "text": f"Подписчиков: {total} (+{recent} за {NEWSLETTER_RECENT_DAYS} дней)",
    }


marketing_site.register(News, MarketingNewsAdmin)
marketing_site.register(BlogPost, MarketingBlogPostAdmin)
marketing_site.register(Category, ContentCategoryAdmin)

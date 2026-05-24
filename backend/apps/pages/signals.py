"""
Signals для автоматической инвалидации кэша страниц
"""

import logging
import threading

import requests
from django.conf import settings
from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .models import Page

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Page)
def invalidate_page_cache(sender, instance, **kwargs):
    """Инвалидация кэша при изменении страницы"""
    cache.delete("pages_list")
    cache.delete(f"page_detail_{instance.slug}")

    thread = threading.Thread(
        target=_revalidate_nextjs,
        args=(f"/{instance.slug}",),
        daemon=True,
    )
    thread.start()


def _revalidate_nextjs(path: str) -> None:
    """Сбрасывает ISR-кеш Next.js для указанного пути (вызывается в фоновом потоке)."""
    frontend_url = getattr(settings, "FRONTEND_INTERNAL_URL", None)
    secret = getattr(settings, "REVALIDATE_SECRET", None)

    if not frontend_url or not secret:
        return

    try:
        requests.post(
            f"{frontend_url}/api/revalidate",
            json={"path": path},
            headers={"x-revalidate-secret": secret},
            timeout=10,
        )
        logger.info("Next.js revalidation triggered for %s", path)
    except Exception as exc:
        logger.warning("Next.js revalidation failed for %s: %s", path, exc)

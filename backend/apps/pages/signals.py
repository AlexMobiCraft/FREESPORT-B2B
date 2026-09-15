"""
Signals для автоматической инвалидации кэша страниц
"""

import logging
import threading

import requests
from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache_keys import bump_pages_list_version, get_pages_list_version, pages_list_cache_key
from .models import Page

logger = logging.getLogger(__name__)


@receiver([post_save, post_delete], sender=Page)
def invalidate_page_cache(sender, instance, **kwargs):
    """Инвалидация кэша при изменении страницы — строго ПОСЛЕ commit.

    Сигналы `post_save`/`post_delete` срабатывают внутри открытой транзакции,
    поэтому сбрасывать кэш прямо здесь нельзя: между сбросом и commit остаётся
    окно, в котором параллельный GET новую страницу ещё не видит (она не
    закоммичена), но уже заполняет свежий ключ допубликационным списком. Такая
    запись живёт сутки (`PAGES_LIST_CACHE_TTL`), и middleware фронтенда отдаёт
    по новой странице ложный 404 намного дольше собственного TTL в 5 минут.

    `transaction.on_commit` откладывает сброс до фактического commit; при
    откате транзакции сброса не происходит вовсе — данные не менялись. Вне
    транзакции (autocommit) callback выполняется немедленно.

    Slug захватывается сейчас, а не читается из `instance` в момент коллбэка:
    объект к тому времени может быть изменён вызывающим кодом.
    """
    slug = instance.slug
    transaction.on_commit(lambda: _invalidate_page_cache_now(slug))


def _invalidate_page_cache_now(slug: str) -> None:
    """Фактический сброс кэшей страницы (вызывается после commit).

    Список кэшируется целиком под одним версионированным ключом
    (см. `PageViewSet.list`), поэтому смены версии достаточно для любых
    вариантов пагинации: и для запроса без параметров, и для `?page_size=1000`
    от middleware фронтенда.

    Порядок важен: сначала удаляем данные текущей версии, затем увеличиваем
    счётчик. Одного удаления мало — запрос, начавший сериализацию до публикации,
    допишет устаревший список уже после удаления и вернёт ложные 404 в кэш ещё
    на сутки. После инкремента такая поздняя запись ложится под старый ключ,
    который никто не читает.
    """
    cache.delete(pages_list_cache_key(get_pages_list_version()))
    bump_pages_list_version()
    cache.delete(f"page_detail_{slug}")

    thread = threading.Thread(
        target=_revalidate_nextjs,
        args=(f"/{slug}",),
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

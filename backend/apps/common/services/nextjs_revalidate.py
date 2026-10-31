"""
Сброс ISR-кэша страниц Next.js после изменения данных в админке.

Next отдаёт часть страниц из ISR-кэша (`revalidate` у страницы) и без сброса
показывает правку только после пересборки страницы. Сброс — `POST
/api/revalidate` фронтенда с секретом; вызывается после commit, в фоновом
потоке, чтобы сохранение не ждало Next.
"""

from __future__ import annotations

import logging
import threading

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# Главная — маршрут (blue)/home: `/` — динамический редирект и в ISR не участвует.
HOME_PAGE_PATH = "/home"


def revalidate_nextjs_path(path: str) -> None:
    """Сбрасывает ISR-кеш Next.js для указанного пути (вызывается в фоновом потоке).

    Каждый исход пишется в лог. Раньше отсутствие настроек и ответ 401 проходили
    молча, и на проде сброс не работал ни разу, не оставив ни одной строки в логах.
    """
    frontend_url = getattr(settings, "FRONTEND_INTERNAL_URL", None)
    secret = getattr(settings, "REVALIDATE_SECRET", None)

    if not frontend_url or not secret:
        logger.warning(
            "Next.js revalidation skipped for %s: FRONTEND_INTERNAL_URL or REVALIDATE_SECRET is not set",
            path,
        )
        return

    try:
        response = requests.post(
            f"{frontend_url}/api/revalidate",
            json={"path": path},
            headers={"x-revalidate-secret": secret},
            timeout=10,
        )
    except Exception as exc:
        logger.warning("Next.js revalidation failed for %s: %s", path, exc)
        return

    if response.ok:
        logger.info("Next.js revalidation triggered for %s", path)
    else:
        # 401 — секреты backend и frontend расходятся.
        logger.warning("Next.js revalidation rejected for %s: HTTP %s", path, response.status_code)


def revalidate_nextjs_path_in_background(path: str) -> None:
    """Запускает `revalidate_nextjs_path` в фоновом daemon-потоке."""
    threading.Thread(target=revalidate_nextjs_path, args=(path,), daemon=True).start()

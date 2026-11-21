"""
Сервисный слой для баннеров — кеширование, фильтрация, инвалидация.

Story 32.1 Task 7-2: Вынесение логики из view в service layer.
Story 32.1 Task 7-1: Cache key включает роль пользователя для предотвращения утечки данных.
Story 32.1 Task 8-1: _ALL_ROLE_KEYS импортируется из User.ROLE_CHOICES.
Story 32.1 Task 8-2: CACHE_KEY_PATTERN — константа паттерна ключа кеша.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import IntegrityError, connection, transaction
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.users.models import User

from .models import WHOLESALE_LIKE_ROLES, Banner, BannerDailyStat

logger = logging.getLogger(__name__)

BANNER_CACHE_TTL = 60 * 15  # 15 минут
MIN_CACHE_TTL = 10  # Минимальный TTL — 10 секунд (защита от cache churn)
CACHE_KEY_PATTERN = "banners:list:{type}:{role}"

# Все возможные роли для полной инвалидации кеша — синхронизировано с User.ROLE_CHOICES
_ALL_ROLE_KEYS = tuple(role for role, _ in User.ROLE_CHOICES) + ("guest",)

_VALID_BANNER_TYPES = frozenset(choice.value for choice in Banner.BannerType)


def get_role_key(user: Any) -> str:
    """
    Определяет ключ роли пользователя для кеша.

    Args:
        user: Объект пользователя или None/AnonymousUser для гостей.

    Returns:
        Строка роли: 'guest' для неавторизованных, иначе user.role.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return "guest"
    return getattr(user, "role", "retail")


def validate_banner_type(banner_type: Optional[str]) -> str:
    """
    Валидирует тип баннера. Невалидные/отсутствующие значения возвращают 'hero' (FR6).

    Args:
        banner_type: Значение query param ?type=

    Returns:
        Валидный тип баннера. По умолчанию 'hero'.
    """
    if banner_type and banner_type in _VALID_BANNER_TYPES:
        return banner_type
    return Banner.BannerType.HERO.value


def build_cache_key(banner_type: str, role_key: str) -> str:
    """
    Строит ключ кеша с учётом типа баннера и роли пользователя.

    Формат: banners:list:{type}:{role} — предотвращает утечку данных
    между ролями (Task 7-1).

    Args:
        banner_type: Тип баннера (всегда resolved, default='hero').
        role_key: Ключ роли пользователя.

    Returns:
        Строка ключа кеша.
    """
    return CACHE_KEY_PATTERN.format(type=banner_type, role=role_key)


def get_cached_banners(cache_key: str) -> Any:
    """Получить закешированные данные баннеров. Возвращает None при промахе."""
    return cache.get(cache_key)


def get_active_banners_queryset(user: Any, banner_type: str = "hero", role_key: str | None = None) -> QuerySet[Banner]:
    """
    Получить отфильтрованный QuerySet активных баннеров.

    Args:
        user: Пользователь или None для гостей.
        banner_type: Фильтр по типу (всегда resolved, default='hero').
        role_key: Ключ роли пользователя (guest, retail, trainer, ...). Если None — учитываются все роли.

    Returns:
        QuerySet с баннерами.
    """
    effective_user = user if user and getattr(user, "is_authenticated", False) else None
    queryset = Banner.get_for_user(effective_user).filter(is_active=True)
    if banner_type:
        queryset = queryset.filter(type=banner_type)
    if role_key:
        queryset = queryset.filter(_get_role_filter(role_key))
    if banner_type == Banner.BannerType.MARKETING.value:
        limit = getattr(settings, "MARKETING_BANNER_LIMIT", 5)
        queryset = queryset[:limit]
    elif banner_type == Banner.BannerType.HERO.value:
        limit = getattr(settings, "HERO_BANNER_LIMIT", 10)
        queryset = queryset[:limit]
    return queryset


def _get_role_filter(role_key: str) -> Q:
    """
    Возвращает Q-фильтр для QuerySet по роли пользователя.

    Логика синхронизирована с ``Banner.get_for_user()``:
    - guest → ``show_to_guests=True``
    - authenticated роли → ``show_to_authenticated=True`` (база) OR role-specific flag

    Args:
        role_key: Ключ роли (guest, retail, trainer, ...)

    Returns:
        Q объект для Django ORM filter.
    """
    if role_key == "guest":
        return Q(show_to_guests=True)
    # Все authenticated роли имеют базовый доступ show_to_authenticated
    base = Q(show_to_authenticated=True)
    if role_key == "retail":
        return base
    elif role_key == "trainer":
        return base | Q(show_to_trainers=True)
    elif (
        role_key in {"wholesale_level1", "wholesale_level2", "wholesale_level3", "wholesale_level4"}
        or role_key in WHOLESALE_LIKE_ROLES
    ):
        return base | Q(show_to_wholesale=True)
    elif role_key == "federation_rep":
        return base | Q(show_to_federation=True)
    else:
        # Неизвестная роль — fallback на guest
        return Q(show_to_guests=True)


def compute_cache_ttl(
    banner_type: str | None = None,
    role_key: str | None = None,
) -> int:
    """
    Вычисляет динамический TTL на основе ближайших временных границ активных баннеров.

    Args:
        banner_type: Тип баннера (hero, marketing). Если None — hero по умолчанию.
        role_key: Ключ роли пользователя (guest, retail, trainer, ...). Если None — учитываются все роли.

    Returns:
        TTL в секундах, не менее MIN_CACHE_TTL.
    """
    now = timezone.now()
    nearest_seconds = BANNER_CACHE_TTL

    # Базовый queryset: только активные баннеры БЕЗ temporal/role фильтрации,
    # чтобы учесть будущие start_date и приближающиеся end_date для TTL.
    queryset = Banner.objects.filter(is_active=True)
    if banner_type:
        queryset = queryset.filter(type=banner_type)
    if role_key:
        queryset = queryset.filter(_get_role_filter(role_key))

    # Ближайший end_date текущих активных баннеров (истечёт раньше TTL)
    nearest_end = (
        queryset.filter(end_date__isnull=False, end_date__gt=now)
        .order_by("end_date")
        .values_list("end_date", flat=True)
        .first()
    )
    if isinstance(nearest_end, datetime):
        delta = int((nearest_end - now).total_seconds())
        if 0 < delta < nearest_seconds:
            nearest_seconds = delta

    # Ближайший start_date будущих баннеров (появится раньше TTL)
    nearest_start = (
        queryset.filter(start_date__isnull=False, start_date__gt=now)
        .order_by("start_date")
        .values_list("start_date", flat=True)
        .first()
    )
    if isinstance(nearest_start, datetime):
        delta = int((nearest_start - now).total_seconds())
        if 0 < delta < nearest_seconds:
            nearest_seconds = delta

    return max(nearest_seconds, MIN_CACHE_TTL)


def cache_banner_response(cache_key: str, data: Any, ttl: Optional[int] = None) -> None:
    """Кеширует сериализованные данные баннеров."""
    cache.set(cache_key, data, ttl if ttl is not None else BANNER_CACHE_TTL)


def invalidate_banner_cache(banner_type: str) -> None:
    """
    Инвалидирует все ключи кеша для данного типа баннера по всем ролям.

    Вызывается из сигналов при save/delete баннера.

    Args:
        banner_type: Тип баннера (hero, marketing).
    """
    keys_to_delete = []
    for role_key in _ALL_ROLE_KEYS:
        keys_to_delete.append(build_cache_key(banner_type, role_key))

    cache.delete_many(keys_to_delete)
    logger.debug(
        "Invalidated banner cache for type=%s across %d role keys",
        banner_type,
        len(_ALL_ROLE_KEYS),
    )


# ---------------------------------------------------------------------------
# Статистика показов и кликов для отчётности в ОРД
# ---------------------------------------------------------------------------

EVENT_VIEW = "view"
EVENT_CLICK = "click"
EVENT_KINDS = (EVENT_VIEW, EVENT_CLICK)

# Одна строка на баннер: снимок и ERID берутся из самого баннера в момент события,
# клиенту не доверяем. SELECT отбрасывает неизвестный, выключенный, вышедший из окна
# дат и не маркетинговый баннер (шапку, `type = hero`: для ОРД и маркетинга считаются
# только баннеры слайдера) — тогда вставлять нечего, и событие молча теряется. Приращение — в одном
# операторе (ON CONFLICT … SET views = t.views + EXCLUDED.views), без read-modify-write.
# Реквизиты рекламодателя и ERID у нерекламного баннера могут остаться в БД после
# снятия галочки — в снимок они не попадают.
_UPSERT_DAILY_STAT_SQL = f"""
INSERT INTO {BannerDailyStat._meta.db_table} AS t
    (banner_id, banner_ref_id, date, erid, banner_title, advertiser_name, advertiser_inn, views, clicks)
SELECT
    b.id,
    b.id,
    %(date)s,
    CASE WHEN b.is_advertisement THEN b.erid ELSE '' END,
    b.title,
    CASE WHEN b.is_advertisement THEN b.advertiser_name ELSE '' END,
    CASE WHEN b.is_advertisement THEN b.advertiser_inn ELSE '' END,
    %(views)s,
    %(clicks)s
FROM {Banner._meta.db_table} AS b
WHERE b.id = %(banner_id)s
    AND b.is_active
    AND b.type = %(marketing)s
    AND (b.start_date IS NULL OR b.start_date <= %(now)s)
    AND (b.end_date IS NULL OR b.end_date >= %(now)s)
ON CONFLICT (banner_ref_id, date, erid) DO UPDATE SET
    views = t.views + EXCLUDED.views,
    clicks = t.clicks + EXCLUDED.clicks,
    banner_id = EXCLUDED.banner_id,
    banner_title = EXCLUDED.banner_title,
    advertiser_name = EXCLUDED.advertiser_name,
    advertiser_inn = EXCLUDED.advertiser_inn
"""


def record_events(events: Iterable[Mapping[str, Any]]) -> int:
    """
    Прибавляет пачку событий «показ»/«клик» к дневной статистике баннеров.

    Пачка сначала сворачивается в Python до одной пары сумм на баннер: повтор
    одного ключа в одном операторе ON CONFLICT Postgres не принимает. Баннеры
    обходятся по возрастанию id — параллельные пачки берут блокировки строк в одном
    порядке и не взаимоблокируются. Каждый баннер — отдельный upsert в своей точке
    сохранения: гонка с удалением баннера (FK-нарушение) теряет одно событие, а не
    пачку и не транзакцию запроса.

    Учитываются только маркетинговые баннеры слайдера: события баннеров шапки
    (``type != marketing``) отбрасываются так же молча, как события выключенного
    баннера, — от старых вкладок и ручных запросов.

    Сутки — по часовому поясу проекта (`Europe/Moscow`).

    Args:
        events: Элементы вида ``{"banner_id": int, "kind": "view" | "click"}``.

    Returns:
        Число записанных (вставленных или обновлённых) строк статистики.
    """
    totals: dict[int, list[int]] = {}
    for event in events:
        counters = totals.setdefault(int(event["banner_id"]), [0, 0])
        counters[0 if event["kind"] == EVENT_VIEW else 1] += 1

    if not totals:
        return 0

    today = timezone.localdate()
    now = timezone.now()
    written = 0
    for banner_id in sorted(totals):
        views, clicks = totals[banner_id]
        params: dict[str, Any] = {
            "date": today,
            "now": now,
            "banner_id": banner_id,
            "marketing": Banner.BannerType.MARKETING.value,
            "views": views,
            "clicks": clicks,
        }
        try:
            with transaction.atomic(), connection.cursor() as cursor:
                cursor.execute(_UPSERT_DAILY_STAT_SQL, params)
                written += max(cursor.rowcount, 0)
        except IntegrityError:
            # Баннер удалили между SELECT и проверкой внешнего ключа.
            logger.warning("Статистика баннера %s не записана: баннер удалён во время записи", banner_id)
    return written


def sync_daily_stat_snapshots(banner: Banner) -> int:
    """
    Переписывает снимок баннера во всех его строках дневной статистики.

    Название — во всех строках с `banner_id = pk`, с любым ERID. Наименование и ИНН
    рекламодателя — только у рекламного баннера и только в рекламных строках
    (непустой `advertiser_name`; ERID у рекламы необязателен): нерекламная строка
    реквизитов не получает, а снятая маркировка не стирает их у старых строк.
    Строки удалённого баннера (`banner_id IS NULL`) не трогаются — их снимок
    заморожен. Два оператора UPDATE со значениями из баннера, без чтения строк;
    обновляются только строки, где значение отличается.

    Returns:
        Число обновлённых строк (строка, где сменилось и название, и реквизиты, — дважды).
    """
    rows = BannerDailyStat.objects.filter(banner_id=banner.pk)
    updated = rows.exclude(banner_title=banner.title).update(banner_title=banner.title)
    # Пустое наименование у рекламного баннера отсекает валидация модели; без этой
    # проверки сохранение в обход неё превратило бы рекламные строки в нерекламные.
    if banner.is_advertisement and banner.advertiser_name:
        updated += (
            rows.exclude(advertiser_name="")
            .exclude(advertiser_name=banner.advertiser_name, advertiser_inn=banner.advertiser_inn)
            .update(advertiser_name=banner.advertiser_name, advertiser_inn=banner.advertiser_inn)
        )
    return updated

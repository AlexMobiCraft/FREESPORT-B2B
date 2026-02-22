"""
Сервисный слой для баннеров — кеширование, фильтрация, инвалидация.

Story 32.1 Task 7-2: Вынесение логики из view в service layer.
Story 32.1 Task 7-1: Cache key включает роль пользователя для предотвращения утечки данных.
Story 32.1 Task 8-1: _ALL_ROLE_KEYS импортируется из User.ROLE_CHOICES.
Story 32.1 Task 8-2: CACHE_KEY_PATTERN — константа паттерна ключа кеша.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.users.models import User

from .models import Banner

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
    elif role_key in {"wholesale_level1", "wholesale_level2", "wholesale_level3"}:
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

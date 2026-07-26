"""Утилиты для фильтрации дерева категорий."""

from __future__ import annotations

import re

# Категории-заглушки создаются импортом 1С для неизвестных category_id.
# Шаблон: «Категория » + UUID в стандартном формате 8-4-4-4-12.
PLACEHOLDER_CATEGORY_RE_PATTERN = (
    r"^Категория\s+[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_PLACEHOLDER_RE = re.compile(PLACEHOLDER_CATEGORY_RE_PATTERN)

# Расширенный шаблон для repair-команды: UUID или другой ID-подобный суффикс (hex/цифры/разделители).
# Требует ≥ 12 символов — исключает человекочитаемые диапазоны вида «2024-2025».
_LEGACY_PLACEHOLDER_RE = re.compile(
    r"^Категория\s+[0-9a-fA-F_-]{12,}$"
)

# Полный паттерн для ORM-фильтра API: UUID + legacy hex-ID в одном выражении.
FULL_PLACEHOLDER_CATEGORY_RE_PATTERN = (
    r"^Категория\s+(?:[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r"|[0-9a-fA-F_-]{12,})$"
)

# Служебный onec_id для якоря, созданного repair-командой вручную.
REPAIR_ANCHOR_ONEC_ID = "__repair_anchor__"


def is_placeholder_category_name(name: str) -> bool:
    """Возвращает True только для UUID-placeholder вида «Категория 123e4567-e89b-…»."""
    return bool(_PLACEHOLDER_RE.match(name or ""))


def is_repair_placeholder_category_name(name: str) -> bool:
    """Расширенный check для repair-команды: UUID-placeholder или legacy hex/numeric ID.

    Отличие от is_placeholder_category_name: дополнительно распознаёт старые форматы ID
    (UUID без разделителей, длинные числовые ID), характерные для устаревших версий импорта.
    """
    return bool(_PLACEHOLDER_RE.match(name or "") or _LEGACY_PLACEHOLDER_RE.match(name or ""))

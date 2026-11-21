"""Утилиты для фильтрации дерева категорий."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import cast

from django.conf import settings
from django.db.models import Q

from .models import Category

# Категории-заглушки создаются импортом 1С для неизвестных category_id.
# Шаблон: «Категория » + UUID в стандартном формате 8-4-4-4-12.
PLACEHOLDER_CATEGORY_RE_PATTERN = (
    r"^Категория\s+[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_PLACEHOLDER_RE = re.compile(PLACEHOLDER_CATEGORY_RE_PATTERN)

# Расширенный шаблон для repair-команды: UUID или другой ID-подобный суффикс (hex/цифры/разделители).
# Требует ≥ 12 символов — исключает человекочитаемые диапазоны вида «2024-2025».
_LEGACY_PLACEHOLDER_RE = re.compile(r"^Категория\s+[0-9a-fA-F_-]{12,}$")

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


# Служебные категории, которые сайдбар каталога не показывает ни на одном уровне
SIDEBAR_EXCLUDED_SLUGS = ("uncategorized", "onec-unresolved-category")
SIDEBAR_EXCLUDED_NAME = "Без категории"


def sidebar_excluded_categories_q() -> Q:
    """Условие «категорию сайдбар каталога не показывает».

    Одно место для дерева категорий (`CategoryTreeViewSet`, `CategoryTreeSerializer`)
    и для порядка выдачи `ordering=category_tree`: если условие разойдётся, товары
    встанут не в том порядке, что ветки сайдбара.
    """
    return (
        Q(slug__in=SIDEBAR_EXCLUDED_SLUGS)
        | Q(name=SIDEBAR_EXCLUDED_NAME)
        | Q(name__regex=FULL_PLACEHOLDER_CATEGORY_RE_PATTERN)
    )


def _sidebar_rank(sort_order: int) -> int:
    """Ранг сайдбара: заданный `sort_order` раньше нулевого (как `categoryRank` фронта).

    Ранг «uncategorized последней» здесь не нужен: её вырезает `sidebar_excluded_categories_q`.
    """
    return 0 if sort_order > 0 else 1


def order_category_tree(
    rows: Iterable[tuple[int, int | None, int]],
    root_parent_ids: Iterable[int],
) -> list[int]:
    """Порядок категорий при обходе дерева в глубину — тот же, что в сайдбаре.

    Args:
        rows: `(id, parent_id, sort_order)` уже в порядке `sort_order, name, id`.
        root_parent_ids: якоря; их дети сливаются в один список братьев.

    Братья идут в порядке `rows`, затем стабильно по рангу сайдбара (`sort_order > 0`
    раньше нуля). Родитель раньше детей. Узлы, недостижимые от якорей (вне дерева,
    в цикле parent), в результат не попадают. Множество посещённых не даёт обходу
    зациклиться на битых данных.
    """
    anchors = set(root_parent_ids)
    children: dict[int, list[tuple[int, int]]] = {}
    roots: list[tuple[int, int]] = []
    for category_id, parent_id, sort_order in rows:
        node = (category_id, sort_order)
        # Корни берутся в общем порядке rows, а не группами по якорю: при нескольких
        # якорях их дети ранжируются вместе, как один запрос CategoryTreeViewSet
        if parent_id in anchors:
            roots.append(node)
        elif parent_id is not None:
            children.setdefault(parent_id, []).append(node)

    def ranked(nodes: list[tuple[int, int]]) -> list[int]:
        # sorted стабилен: внутри ранга остаётся порядок rows
        return [category_id for category_id, _ in sorted(nodes, key=lambda node: _sidebar_rank(node[1]))]

    order: list[int] = []
    visited: set[int] = set(anchors)
    stack = list(reversed(ranked(roots)))
    while stack:
        category_id = stack.pop()
        if category_id in visited:
            continue
        visited.add(category_id)
        order.append(category_id)
        stack.extend(reversed(ranked(children.get(category_id, []))))
    return order


def catalog_category_order() -> list[int]:
    """id категорий в порядке сайдбара каталога: обход в глубину от детей активных якорей.

    Один запрос, без кэша: позиции должны совпадать с сайдбаром сразу после правки
    `sort_order` в админке. Исключённые сайдбаром категории вырезаются запросом,
    поэтому обход не заходит ни в них, ни в их поддеревья. Неактивные категории
    остаются: товар в скрытой подкатегории стоит в своей ветке.
    """
    root_name = getattr(settings, "ROOT_CATEGORY_NAME", "СПОРТ")
    rows = (
        Category.objects.exclude(sidebar_excluded_categories_q())
        .order_by("sort_order", "name", "id")
        .values_list("id", "parent_id", "sort_order", "name", "is_active")
    )
    tree_rows: list[tuple[int, int | None, int]] = []
    anchor_ids: list[int] = []
    for category_id, raw_parent_id, sort_order, name, is_active in rows:
        # Стабы django-stubs считают parent_id не-NULL, хотя FK nullable
        parent_id = cast("int | None", raw_parent_id)
        # Якоря — те же, что у CategoryTreeViewSet: активные корни с именем ROOT_CATEGORY_NAME
        if parent_id is None and is_active and name == root_name:
            anchor_ids.append(category_id)
        tree_rows.append((category_id, parent_id, sort_order))
    if not anchor_ids:
        return []
    return order_category_tree(tree_rows, anchor_ids)

"""Команда восстановления витрины каталога после массовой деактивации категорий.

Инцидент: частичная выгрузка 1С гасила все категории, не встреченные в текущем XML,
и `/catalog` схлопывался до одной ветки. Команда возвращает `is_active=True` якорю
`ROOT_CATEGORY_NAME` и всем его потомкам, кроме технических категорий и веток,
скрытых через технического предка.

По умолчанию — dry-run; запись в БД только под `--execute`.
"""

from __future__ import annotations

import re
from collections import deque
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.products.category_utils import FULL_PLACEHOLDER_CATEGORY_RE_PATTERN

# Тот же набор исключений, что в CategoryTreeViewSet.get_queryset():
# технические категории не должны всплывать на витрине после восстановления.
EXCLUDED_SLUGS = frozenset({"uncategorized", "onec-unresolved-category"})
EXCLUDED_NAME = "Без категории"
_PLACEHOLDER_RE = re.compile(FULL_PLACEHOLDER_CATEGORY_RE_PATTERN)


class Command(BaseCommand):
    help = (
        "Восстанавливает активность якорной категории и её потомков после "
        "массовой деактивации частичной выгрузкой 1С. По умолчанию dry-run."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--execute", action="store_true", help="Выполнить изменения в БД")
        parser.add_argument(
            "--root-name",
            type=str,
            default=None,
            help="Имя якорной категории (override settings.ROOT_CATEGORY_NAME)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.products.models import Category

        execute = bool(options.get("execute"))
        root_name = options.get("root_name") or getattr(settings, "ROOT_CATEGORY_NAME", None)

        # Ошибка конфигурации, а не «категория не найдена»: без имени якоря
        # команде нечего искать и сообщение про отсутствие категории вводит в заблуждение.
        if not root_name:
            raise CommandError(
                "Имя якорной категории не задано: settings.ROOT_CATEGORY_NAME пуст "
                "и не передан --root-name. Это ошибка конфигурации."
            )

        anchors = list(Category.objects.filter(name=root_name, parent__isnull=True).order_by("pk"))
        if not anchors:
            raise CommandError(f"Якорная категория '{root_name}' (корневая) не найдена в БД.")
        if len(anchors) > 1:
            # Union-семантика витрины: CategoryTreeViewSet отдаёт детей всех активных якорей,
            # поэтому восстанавливаем все, а не выбираем произвольный.
            self.stdout.write(
                self.style.WARNING(
                    f"WARNING: найдено несколько корневых якорей '{root_name}' "
                    f"(count={len(anchors)}). Обрабатываются все (union-семантика витрины)."
                )
            )

        # Одна выборка всего дерева: обход по индексу в памяти вместо N+1 запросов.
        all_rows = Category.objects.values_list("pk", "parent_id", "name", "slug", "is_active")
        children_index: dict[int | None, list[int]] = {}
        node_info: dict[int, tuple[str, str, bool]] = {}
        for pk, parent_id, name, slug, is_active in all_rows:
            node_info[pk] = (name, slug, is_active)
            children_index.setdefault(parent_id, []).append(pk)

        # Между выборкой якорей и выборкой дерева якорь мог быть удалён параллельным
        # импортом: берём только те pk, что реально есть в индексе, иначе оператор
        # получит голый KeyError вместо внятного сообщения.
        anchor_pks = [anchor.pk for anchor in anchors if anchor.pk in node_info]
        if not anchor_pks:
            raise CommandError(
                f"Якорная категория '{root_name}' исчезла из БД во время работы команды. " "Повторите запуск."
            )
        anchor_pk_set = set(anchor_pks)
        anchors_to_activate = [pk for pk in anchor_pks if not node_info[pk][2]]

        # Итеративный обход в ширину с множеством посещённых pk: self-FK допускает
        # циклы в данных, рекурсия дала бы RecursionError.
        visited: set[int] = set(anchor_pks)
        queue: deque[int] = deque(anchor_pks)
        descendants_to_activate: list[int] = []
        skipped_technical: list[int] = []

        while queue:
            current = queue.popleft()
            for child_pk in children_index.get(current, []):
                if child_pk in visited:
                    continue
                visited.add(child_pk)
                name, slug, is_active = node_info[child_pk]
                if self._is_excluded(name, slug):
                    # Ветка скрыта целиком: не активируем ни саму техническую категорию,
                    # ни её потомков — иначе получим активную сироту под скрытой ветвью,
                    # видимую в плоском /api/v1/categories/.
                    skipped_technical.append(child_pk)
                    continue
                if not is_active:
                    descendants_to_activate.append(child_pk)
                queue.append(child_pk)

        to_activate = anchors_to_activate + descendants_to_activate
        mode = "EXECUTE" if execute else "DRY-RUN"
        self.stdout.write(
            f"{mode}: root_name={root_name!r}, anchors={len(anchors)}, "
            f"anchors_to_activate={len(anchors_to_activate)}, "
            f"descendants_to_activate={len(descendants_to_activate)}, "
            f"skipped_technical_branches={len(skipped_technical)}"
        )
        for pk in to_activate[:200]:
            name, slug, _ = node_info[pk]
            marker = "anchor" if pk in anchor_pk_set else "category"
            self.stdout.write(f"  [{marker}] id={pk} name={name!r} slug={slug!r}")
        if len(to_activate) > 200:
            self.stdout.write(f"  ... и ещё {len(to_activate) - 200} категор(ия/ий)")

        activated = 0
        if execute and to_activate:
            with transaction.atomic():
                activated = Category.objects.filter(pk__in=to_activate).update(is_active=True)

        self.stdout.write(
            "SUMMARY: "
            f"mode={mode}, anchor_activated={len(anchors_to_activate)}, "
            f"candidates={len(to_activate)}, reactivated={activated}, "
            f"skipped_technical={len(skipped_technical)}"
        )

    def _is_excluded(self, name: str, slug: str) -> bool:
        """Технические категории витрины: тот же набор, что в CategoryTreeViewSet.

        fullmatch, а не match: Postgres-оператор `~` в ORM-фильтре витрины не считает
        совпадением имя с висящим переводом строки, а `re.match` с `$` — считает.
        Иначе такая категория осталась бы скрытой здесь, но видимой на витрине.
        """
        return bool((slug or "") in EXCLUDED_SLUGS or name == EXCLUDED_NAME or _PLACEHOLDER_RE.fullmatch(name or ""))

"""
Правило допуска номенклатуры 1С: поддерево якорной категории и реестр
исключённых Ид.

Модуль общий для импорта (`VariantImportProcessor`) и разовой очистки
(`purge_products_outside_root`): обе стороны обязаны считать «поддерево
якоря» одинаково, иначе очистка удалит то, что импорт считает допущенным.
"""

from __future__ import annotations

import logging
from typing import Iterable, Mapping

logger = logging.getLogger("import_products")

# Причины недопуска. Текст попадает в построчный лог и в реестр: по нему
# оператор находит позицию в 1С, поэтому формулировки — человеческие.
REASON_NO_GROUP = "нет группы"
REASON_UNKNOWN_GROUP = "неизвестная группа"
REASON_OUTSIDE_TREE = "вне дерева"
REASON_PRODUCT_MARKED = "пометка товара"
REASON_GROUP_MARKED = "пометка группы"
REASON_OFFER_MARKED = "пометка предложения"
REASON_CATEGORY_OUTSIDE_TREE = "категория вне дерева"
REASON_HIDDEN_BY_IMPORT = "скрыт импортом 1С"

KIND_GROUP = "group"
KIND_PRODUCT = "product"
KIND_OFFER = "offer"


def category_key(pk: int, onec_id: str | None) -> str:
    """Ключ категории в дереве групп.

    Группы сравниваются по Ид 1С. Категория без Ид (якорь, созданный вручную
    или repair-командой) получает синтетический ключ: иначе её потомки
    оказались бы «без родителя» и выпали из поддерева.
    """
    return onec_id or f"__pk_{pk}__"


def load_db_category_tree() -> tuple[dict[int, str], dict[str, str], dict[str, str]]:
    """Дерево категорий из БД.

    Returns:
        (ключ по pk, ключ → ключ родителя или "", ключ → наименование)
    """
    from apps.products.models import Category

    rows = list(Category.objects.values_list("pk", "onec_id", "parent_id", "name"))
    key_by_pk = {pk: category_key(pk, onec_id) for pk, onec_id, _, _ in rows}
    parent_of = {key_by_pk[pk]: key_by_pk.get(parent_pk, "") if parent_pk else "" for pk, _, parent_pk, _ in rows}
    name_of = {key_by_pk[pk]: name for pk, _, _, name in rows}
    return key_by_pk, parent_of, name_of


def compute_subtree(
    parent_of: Mapping[str, str],
    anchor_keys: Iterable[str],
    blocked: Iterable[str] = (),
) -> set[str]:
    """Ключи групп, входящих в поддерево якоря.

    Группа входит в поддерево, если цепочка родителей доходит до якоря, не
    проходя через заблокированную группу (помеченную на удаление или вынесенную
    из дерева). Заблокированная группа исключает себя и всех потомков.

    Сам якорь заблокировать нельзя: пометка на нём — признак сбоя выгрузки, а
    не решение скрыть каталог целиком.
    """
    allowed: set[str] = {key for key in anchor_keys if key}
    blocked_keys = set(blocked)
    rejected: set[str] = set()

    for key in parent_of:
        path: list[str] = []
        seen: set[str] = set()
        node = key
        verdict = False
        while True:
            if node in allowed:
                verdict = True
                break
            # Пустой родитель — чужой корень; повтор узла — цикл в данных.
            if not node or node in rejected or node in blocked_keys or node in seen:
                break
            path.append(node)
            seen.add(node)
            node = parent_of.get(node, "")
        (allowed if verdict else rejected).update(path)

    return allowed


def first_blocked_reason(
    group_id: str,
    parent_of: Mapping[str, str],
    blocked: Mapping[str, str],
    *,
    stop_at: Iterable[str] = (),
) -> str | None:
    """Причина блокировки первой заблокированной группы на пути к корню."""
    stops = set(stop_at)
    seen: set[str] = set()
    node = group_id
    while node and node not in seen and node not in stops:
        if node in blocked:
            return blocked[node]
        seen.add(node)
        node = parent_of.get(node, "")
    return None


class ExclusionRegistry:
    """Реестр исключённых Ид 1С: копия в памяти и точечная запись в БД.

    Загружается один раз на сессию (на проде ≈ 20 тыс. строк). Запись в БД
    выполняется только при реальном изменении, поэтому повторный прогон той же
    выгрузки реестр не трогает вовсе.
    """

    def __init__(self) -> None:
        self._items: dict[str, tuple[str, str]] | None = None

    def _load(self) -> dict[str, tuple[str, str]]:
        if self._items is None:
            from apps.products.models import OnecExcludedItem

            self._items = {
                onec_id: (kind, reason)
                for onec_id, kind, reason in OnecExcludedItem.objects.values_list("onec_id", "kind", "reason")
            }
        return self._items

    def kind_of(self, onec_id: str) -> str | None:
        item = self._load().get(onec_id)
        return item[0] if item else None

    def is_product_excluded(self, onec_id: str) -> bool:
        return self.kind_of(onec_id) == KIND_PRODUCT

    def is_offer_excluded(self, onec_id: str) -> bool:
        """Ид предложения исключён сам по себе.

        У товара без характеристик Ид предложения совпадает с Ид товара,
        поэтому запись вида «товар» исключает и такое предложение.
        """
        return self.kind_of(onec_id) in (KIND_OFFER, KIND_PRODUCT)

    def groups(self) -> dict[str, str]:
        """Исключённые группы: Ид → причина."""
        return {onec_id: reason for onec_id, (kind, reason) in self._load().items() if kind == KIND_GROUP}

    def offer_parent_ids(self) -> set[str]:
        """Ид товаров, у которых в реестре есть исключённое предложение."""
        return {onec_id.split("#", 1)[0] for onec_id, (kind, _) in self._load().items() if kind == KIND_OFFER}

    def add(self, onec_id: str, kind: str, reason: str) -> bool:
        """Занести Ид в реестр. Возвращает True, если запись изменилась."""
        from apps.products.models import OnecExcludedItem

        items = self._load()
        current = items.get(onec_id)
        if current == (kind, reason):
            return False
        # Ид уникален, а у товара без характеристик он общий с предложением.
        # Исключение товара шире исключения предложения — его не понижаем.
        if current and current[0] == KIND_PRODUCT and kind == KIND_OFFER:
            return False

        OnecExcludedItem.objects.update_or_create(onec_id=onec_id, defaults={"kind": kind, "reason": reason})
        items[onec_id] = (kind, reason)
        return True

    def discard(self, onec_id: str, kind: str) -> bool:
        """Убрать Ид из реестра, если он занесён с этим видом."""
        from apps.products.models import OnecExcludedItem

        items = self._load()
        current = items.get(onec_id)
        if not current or current[0] != kind:
            return False

        OnecExcludedItem.objects.filter(onec_id=onec_id).delete()
        del items[onec_id]
        return True

"""
Тесты правила допуска 1С: поддерево якоря и реестр исключённых Ид.

`compute_subtree` и `ExclusionRegistry` общие для импорта и команды очистки —
расхождение между ними означало бы, что очистка удаляет допущенное.
"""

from __future__ import annotations

import pytest

from apps.products.models import Category, OnecExcludedItem
from apps.products.services.onec_admission import (
    KIND_GROUP,
    KIND_OFFER,
    KIND_PRODUCT,
    REASON_GROUP_MARKED,
    REASON_OFFER_MARKED,
    REASON_OUTSIDE_TREE,
    ExclusionRegistry,
    category_key,
    compute_subtree,
    first_blocked_reason,
    load_db_category_tree,
)

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


# Дерево: sport → (combat → gloves, football); trash → old
PARENT_OF = {
    "sport": "",
    "combat": "sport",
    "gloves": "combat",
    "football": "sport",
    "trash": "",
    "old": "trash",
}


class TestComputeSubtree:
    def test_descendants_of_anchor_are_allowed(self):
        allowed = compute_subtree(PARENT_OF, {"sport"})

        assert allowed == {"sport", "combat", "gloves", "football"}

    def test_foreign_roots_and_their_descendants_are_rejected(self):
        allowed = compute_subtree(PARENT_OF, {"sport"})

        assert "trash" not in allowed
        assert "old" not in allowed

    def test_blocked_group_excludes_itself_and_descendants(self):
        """Помеченная группа исключает себя и потомков, соседи остаются."""
        allowed = compute_subtree(PARENT_OF, {"sport"}, blocked={"combat"})

        assert allowed == {"sport", "football"}

    def test_anchor_cannot_be_blocked(self):
        """Пометка на якоре — сбой выгрузки, а не решение скрыть каталог целиком."""
        allowed = compute_subtree(PARENT_OF, {"sport"}, blocked={"sport"})

        assert allowed == {"sport", "combat", "gloves", "football"}

    def test_unknown_parent_is_rejected(self):
        """Родитель, которого нет в дереве, до якоря не ведёт."""
        allowed = compute_subtree({"sport": "", "orphan": "ghost"}, {"sport"})

        assert "orphan" not in allowed

    def test_cycle_does_not_hang_and_is_rejected(self):
        allowed = compute_subtree({"sport": "", "a": "b", "b": "a"}, {"sport"})

        assert allowed == {"sport"}

    def test_empty_anchor_key_is_ignored(self):
        """Пустой ключ якоря не должен допустить все корни (их родитель — пустая строка)."""
        allowed = compute_subtree(PARENT_OF, {""})

        assert allowed == set()


class TestFirstBlockedReason:
    def test_returns_reason_of_nearest_blocked_ancestor(self):
        blocked = {"combat": REASON_GROUP_MARKED}

        assert first_blocked_reason("gloves", PARENT_OF, blocked) == REASON_GROUP_MARKED
        assert first_blocked_reason("combat", PARENT_OF, blocked) == REASON_GROUP_MARKED

    def test_returns_none_when_path_is_clean(self):
        assert first_blocked_reason("football", PARENT_OF, {"combat": REASON_GROUP_MARKED}) is None

    def test_stops_at_given_nodes(self):
        """Обход не поднимается выше узлов из stop_at."""
        blocked = {"sport": REASON_GROUP_MARKED}

        assert first_blocked_reason("gloves", PARENT_OF, blocked, stop_at={"combat"}) is None

    def test_cycle_does_not_hang(self):
        assert first_blocked_reason("a", {"a": "b", "b": "a"}, {}) is None


class TestDbCategoryTree:
    def test_category_without_onec_id_gets_synthetic_key(self):
        """Якорь без Ид 1С не должен терять своих потомков."""
        anchor = Category.objects.create(name="СПОРТ", slug="sport-no-onec-id")
        child = Category.objects.create(name="Бокс", slug="boxing-tree", onec_id="boxing-tree", parent=anchor)

        key_by_pk, parent_of, name_of = load_db_category_tree()

        anchor_key = category_key(anchor.pk, None)
        assert key_by_pk[anchor.pk] == anchor_key == f"__pk_{anchor.pk}__"
        assert key_by_pk[child.pk] == "boxing-tree"
        assert parent_of["boxing-tree"] == anchor_key
        assert parent_of[anchor_key] == ""
        assert name_of[anchor_key] == "СПОРТ"
        assert compute_subtree(parent_of, {anchor_key}) == {anchor_key, "boxing-tree"}


class TestExclusionRegistry:
    def test_add_writes_to_db_and_memory(self):
        registry = ExclusionRegistry()

        assert registry.add("product-1", KIND_PRODUCT, REASON_OUTSIDE_TREE) is True

        item = OnecExcludedItem.objects.get(onec_id="product-1")
        assert (item.kind, item.reason) == (KIND_PRODUCT, REASON_OUTSIDE_TREE)
        assert registry.is_product_excluded("product-1") is True
        assert str(item) == f"Товар product-1: {REASON_OUTSIDE_TREE}"

    def test_repeated_add_does_not_touch_db(self, django_assert_num_queries):
        """Повторный прогон той же выгрузки реестр не трогает."""
        registry = ExclusionRegistry()
        registry.add("product-1", KIND_PRODUCT, REASON_OUTSIDE_TREE)

        with django_assert_num_queries(0):
            assert registry.add("product-1", KIND_PRODUCT, REASON_OUTSIDE_TREE) is False

    def test_registry_is_loaded_from_db_once(self, django_assert_num_queries):
        OnecExcludedItem.objects.create(onec_id="group-1", kind=KIND_GROUP, reason=REASON_GROUP_MARKED)
        OnecExcludedItem.objects.create(onec_id="p#v", kind=KIND_OFFER, reason=REASON_OFFER_MARKED)
        registry = ExclusionRegistry()

        with django_assert_num_queries(1):
            assert registry.groups() == {"group-1": REASON_GROUP_MARKED}
            assert registry.offer_parent_ids() == {"p"}
            assert registry.kind_of("missing") is None

    def test_discard_removes_only_matching_kind(self):
        registry = ExclusionRegistry()
        registry.add("p#v", KIND_OFFER, REASON_OFFER_MARKED)

        assert registry.discard("p#v", KIND_PRODUCT) is False
        assert OnecExcludedItem.objects.filter(onec_id="p#v").exists()

        assert registry.discard("p#v", KIND_OFFER) is True
        assert not OnecExcludedItem.objects.filter(onec_id="p#v").exists()
        assert registry.discard("p#v", KIND_OFFER) is False

    def test_reason_change_updates_record(self):
        registry = ExclusionRegistry()
        registry.add("group-1", KIND_GROUP, REASON_OUTSIDE_TREE)

        assert registry.add("group-1", KIND_GROUP, REASON_GROUP_MARKED) is True

        assert OnecExcludedItem.objects.get(onec_id="group-1").reason == REASON_GROUP_MARKED
        assert OnecExcludedItem.objects.count() == 1

    def test_product_exclusion_is_not_downgraded_to_offer(self):
        """У товара без характеристик Ид предложения совпадает с Ид товара.

        Исключение товара шире: пометка его единственного предложения не должна
        превратить запись «товар» в запись «предложение».
        """
        registry = ExclusionRegistry()
        registry.add("plain-id", KIND_PRODUCT, REASON_OUTSIDE_TREE)

        assert registry.add("plain-id", KIND_OFFER, REASON_OFFER_MARKED) is False

        assert registry.kind_of("plain-id") == KIND_PRODUCT
        assert registry.is_offer_excluded("plain-id") is True

    def test_offer_record_is_upgraded_to_product(self):
        registry = ExclusionRegistry()
        registry.add("plain-id", KIND_OFFER, REASON_OFFER_MARKED)

        assert registry.add("plain-id", KIND_PRODUCT, REASON_OUTSIDE_TREE) is True

        assert registry.is_product_excluded("plain-id") is True
        assert OnecExcludedItem.objects.get(onec_id="plain-id").kind == KIND_PRODUCT

    def test_offer_record_does_not_exclude_product(self):
        registry = ExclusionRegistry()
        registry.add("p#v", KIND_OFFER, REASON_OFFER_MARKED)

        assert registry.is_offer_excluded("p#v") is True
        assert registry.is_product_excluded("p#v") is False
        assert registry.is_product_excluded("p") is False

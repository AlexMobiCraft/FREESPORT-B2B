"""
Парсер CommerceML: пометка удаления и полный список групп товара.

XML — реальные выгрузки 1С. Для вариантов написания пометки и товара с
несколькими группами (в выгрузке таких нет) правится копия реального файла.
"""

from __future__ import annotations

import pytest

from apps.products.services.parser import XMLDataParser
from tests.onec_corpus import (
    BT45_BLUE_ID,
    BT45_RED_ID,
    FIXTURE_GOODS_XML,
    FIXTURE_GROUPS_XML,
    FIXTURE_OFFERS_XML,
    FIXTURE_PRODUCT_GROUP_ID,
    FIXTURE_PRODUCT_ID,
    FIXTURE_SPORT_ROOT_ID,
    edit_copy,
    mark_deleted,
    require_snapshot,
    snapshot_files,
)

pytestmark = [pytest.mark.unit]


@pytest.fixture
def parser() -> XMLDataParser:
    return XMLDataParser()


class TestGoodsDeletionMark:
    def test_real_goods_carry_mark_and_all_groups(self, parser):
        goods = parser.parse_goods_xml(str(FIXTURE_GOODS_XML))

        assert len(goods) == 3
        for item in goods:
            assert item["is_deleted"] is False
            assert item["category_ids"] == [item["category_id"]]
        product = next(item for item in goods if item["id"] == FIXTURE_PRODUCT_ID)
        assert product["category_ids"] == [FIXTURE_PRODUCT_GROUP_ID]

    @pytest.mark.parametrize("value", ["true", "True", "TRUE", "  true\n\t"])
    def test_mark_is_case_and_whitespace_insensitive(self, parser, tmp_path, value):
        path = edit_copy(
            FIXTURE_GOODS_XML, tmp_path / "goods.xml", lambda text: mark_deleted(text, FIXTURE_PRODUCT_ID, value)
        )

        goods = {item["id"]: item for item in parser.parse_goods_xml(str(path))}

        assert goods[FIXTURE_PRODUCT_ID]["is_deleted"] is True
        assert sum(1 for item in goods.values() if item["is_deleted"]) == 1

    def test_missing_tag_means_not_deleted(self, parser, tmp_path):
        path = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods.xml",
            lambda text: text.replace("<ПометкаУдаления>false</ПометкаУдаления>", ""),
        )

        goods = parser.parse_goods_xml(str(path))

        assert len(goods) == 3
        assert all(item["is_deleted"] is False for item in goods)

    def test_all_groups_are_kept_first_one_is_category_id(self, parser, tmp_path):
        """Раньше брался только первый Ид группы — правило «все группы в СПОРТ» было бы слепым."""
        first = f"<Ид>{FIXTURE_PRODUCT_GROUP_ID}</Ид>"
        path = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods.xml",
            lambda text: text.replace(first, f"{first}<Ид>{FIXTURE_SPORT_ROOT_ID}</Ид>{first}", 1),
        )

        goods = {item["id"]: item for item in parser.parse_goods_xml(str(path))}

        product = goods[FIXTURE_PRODUCT_ID]
        # Дубль группы снят, порядок выгрузки сохранён
        assert product["category_ids"] == [FIXTURE_PRODUCT_GROUP_ID, FIXTURE_SPORT_ROOT_ID]
        assert product["category_id"] == FIXTURE_PRODUCT_GROUP_ID

    def test_product_without_groups_has_empty_list(self, parser, tmp_path):
        path = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods.xml",
            lambda text: text.replace(f"<Ид>{FIXTURE_PRODUCT_GROUP_ID}</Ид>", "", 1),
        )

        goods = {item["id"]: item for item in parser.parse_goods_xml(str(path))}

        assert goods[FIXTURE_PRODUCT_ID]["category_ids"] == []
        assert goods[FIXTURE_PRODUCT_ID]["category_id"] == ""


class TestOffersDeletionMark:
    def test_real_offers_carry_mark(self, parser):
        offers = parser.parse_offers_xml(str(FIXTURE_OFFERS_XML))

        assert offers
        assert all(offer["is_deleted"] is False for offer in offers)

    def test_marked_offer_is_flagged(self, parser, tmp_path):
        offer_id = parser.parse_offers_xml(str(FIXTURE_OFFERS_XML))[0]["id"]
        path = edit_copy(FIXTURE_OFFERS_XML, tmp_path / "offers.xml", lambda text: mark_deleted(text, offer_id))

        offers = {offer["id"]: offer for offer in parser.parse_offers_xml(str(path))}

        assert offers[offer_id]["is_deleted"] is True
        assert sum(1 for offer in offers.values() if offer["is_deleted"]) == 1


class TestGroupsDeletionMark:
    def test_real_groups_carry_mark(self, parser):
        groups = parser.parse_groups_xml(str(FIXTURE_GROUPS_XML))

        assert len(groups) > 100
        assert all(group["is_deleted"] is False for group in groups)

    def test_marked_nested_group_is_flagged(self, parser, tmp_path):
        path = edit_copy(
            FIXTURE_GROUPS_XML,
            tmp_path / "groups.xml",
            lambda text: mark_deleted(text, FIXTURE_PRODUCT_GROUP_ID),
        )

        groups = {group["id"]: group for group in parser.parse_groups_xml(str(path))}

        assert groups[FIXTURE_PRODUCT_GROUP_ID]["is_deleted"] is True
        assert groups[FIXTURE_PRODUCT_GROUP_ID]["parent_id"]
        assert groups[FIXTURE_SPORT_ROOT_ID]["is_deleted"] is False
        assert sum(1 for group in groups.values() if group["is_deleted"]) == 1


@pytest.mark.data_dependent
class TestSnapshotDeletionMarks:
    """Пометки удаления в снимке 21.09.2026 — без правки XML."""

    def test_bt45_ru_is_marked_in_real_goods(self, parser):
        require_snapshot()
        goods: dict[str, dict] = {}
        for path in snapshot_files("goods"):
            goods.update({item["id"]: dict(item) for item in parser.parse_goods_xml(str(path))})

        assert goods[BT45_RED_ID]["is_deleted"] is True
        assert goods[BT45_BLUE_ID]["is_deleted"] is True
        assert "BT45-RU" in goods[BT45_RED_ID]["name"]
        assert sum(1 for item in goods.values() if item["is_deleted"]) == 2
        # В снимке нет товаров с несколькими группами, но есть товары без группы
        assert all(len(item["category_ids"]) <= 1 for item in goods.values())
        assert any(not item["category_ids"] for item in goods.values())

    def test_marked_offers_exist_in_real_offers(self, parser):
        require_snapshot()
        offers = [offer for path in snapshot_files("offers") for offer in parser.parse_offers_xml(str(path))]

        marked = [offer for offer in offers if offer["is_deleted"]]
        assert marked, "В подмножестве снимка обязаны быть предложения с пометкой удаления"
        assert len(marked) < len(offers)

    def test_no_marked_groups_in_real_tree(self, parser):
        require_snapshot()
        groups = parser.parse_groups_xml(str(snapshot_files("groups")[0]))

        roots = [group["name"] for group in groups if not group.get("parent_id")]
        assert "СПОРТ" in roots
        assert len(roots) == 5
        assert not any(group["is_deleted"] for group in groups)

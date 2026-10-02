"""
XMLDataParser: защита от плохих файлов, валидация картинок, НДС, виды цен и
справочники — на реальных выгрузках закоммиченного среза.

Помощники без XML-входа (`_validate_image_path`, `_map_price_type_to_field`,
разбор ставки НДС) проверяются напрямую: синтетические XML проект запрещает
только для сценариев импорта.
"""

from __future__ import annotations

from decimal import Decimal
from xml.etree.ElementTree import Element, SubElement

import pytest

from apps.products.services.parser import XMLDataParser
from tests.onec_corpus import FIXTURE_GOODS_XML, FIXTURE_OFFERS_XML, ONEC_FIXTURES, edit_copy

pytestmark = [pytest.mark.unit]


@pytest.fixture
def parser() -> XMLDataParser:
    return XMLDataParser()


class TestFileGuards:
    def test_missing_file_raises(self, parser, tmp_path):
        with pytest.raises(FileNotFoundError):
            parser.parse_goods_xml(str(tmp_path / "nope.xml"))

    def test_oversized_file_is_rejected(self, parser, monkeypatch):
        monkeypatch.setattr(parser, "MAX_FILE_SIZE", 10)

        with pytest.raises(ValueError, match="exceeds limit"):
            parser.parse_goods_xml(str(FIXTURE_GOODS_XML))

    def test_broken_xml_is_rejected(self, parser, tmp_path):
        broken = tmp_path / "broken.xml"
        broken.write_text("<КоммерческаяИнформация><Каталог>", encoding="utf-8")

        with pytest.raises(ValueError, match="Invalid XML structure"):
            parser.parse_goods_xml(str(broken))

    def test_local_tag_of_non_string_is_empty(self, parser):
        assert parser._get_local_tag(None) == ""
        assert parser._get_local_tag("{urn:x}Товар") == "Товар"

    def test_iter_elements_walks_nested_tags(self, parser):
        root = Element("a")
        SubElement(SubElement(root, "b"), "c")
        SubElement(root, "c")

        assert len(list(parser._iter_elements(root, "c"))) == 2

    def test_find_text_returns_default_for_empty_or_missing(self, parser):
        root = Element("a")
        SubElement(root, "empty")

        assert parser._find_text(root, "empty", "dflt") == "dflt"
        assert parser._find_text(root, "missing") == ""


class TestImagePaths:
    @pytest.mark.parametrize("value", ["", "   ", None, 42, "no-extension", "file.gif", "archive.zip"])
    def test_invalid_paths_are_rejected(self, parser, value):
        assert parser._validate_image_path(value) is None

    def test_path_is_normalized(self, parser):
        assert parser._validate_image_path("  import_files\\01\\photo.JPG ") == "import_files/01/photo.JPG"
        assert parser._validate_image_path("a/b.webp") == "a/b.webp"

    def test_offer_images_are_validated_and_deduplicated(self, parser, tmp_path):
        offer_id = parser.parse_offers_xml(str(FIXTURE_OFFERS_XML))[0]["id"]
        anchor = f"<Ид>{offer_id}</Ид>"
        images = (
            "<Картинка>import_files\\01\\a.jpg</Картинка><Картинка>import_files/01/a.jpg</Картинка>"
            "<Картинка>bad.gif</Картинка><Картинка>import_files/01/b.png</Картинка>"
        )
        path = edit_copy(
            FIXTURE_OFFERS_XML, tmp_path / "offers.xml", lambda text: text.replace(anchor, anchor + images, 1)
        )

        offers = {offer["id"]: offer for offer in parser.parse_offers_xml(str(path))}

        assert offers[offer_id]["images"] == ["import_files/01/a.jpg", "import_files/01/b.png"]

    def test_goods_category_name_is_kept(self, parser, tmp_path):
        group = "<Ид>9c5bad96-a802-11e7-8151-00155d87f90d</Ид>"
        path = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods.xml",
            lambda text: text.replace(group, group + "<Наименование>Гантели</Наименование>", 1),
        )

        goods = {item["id"]: item for item in parser.parse_goods_xml(str(path))}

        assert goods["018d777d-9094-11ec-a2ff-04421a23d8e8"]["category_name"] == "Гантели"


class TestVatRate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("22%", Decimal("22")), (" 10,5 ", Decimal("10.5")), ("", None), ("%", None), ("abc", None)],
    )
    def test_value_parsing(self, parser, raw, expected):
        assert parser._parse_vat_rate_value(raw) == expected

    def test_direct_tag_wins(self, parser):
        product = Element("Товар")
        SubElement(product, "СтавкаНДС").text = "22%"

        assert parser._extract_vat_rate(product) == Decimal("22")

    def test_tax_rates_block_skips_foreign_taxes_and_bad_values(self, parser):
        product = Element("Товар")
        rates = SubElement(product, "СтавкиНалогов")
        for name, value in (("Акциз", "5"), ("НДС", "n/a"), ("НДС", "10")):
            rate = SubElement(rates, "СтавкаНалога")
            SubElement(rate, "Наименование").text = name
            SubElement(rate, "Ставка").text = value

        assert parser._extract_vat_rate(product) == Decimal("10")

    def test_no_vat_information(self, parser):
        assert parser._extract_vat_rate(Element("Товар")) is None

        product = Element("Товар")
        rate = SubElement(SubElement(product, "СтавкиНалогов"), "СтавкаНалога")
        SubElement(rate, "Наименование").text = "Акциз"
        assert parser._extract_vat_rate(product) is None

    def test_real_goods_expose_vat_when_present(self, parser):
        goods = parser.parse_goods_xml(str(FIXTURE_GOODS_XML))

        assert all("vat_rate" not in item or isinstance(item["vat_rate"], Decimal) for item in goods)


class TestPriceTypeMapping:
    @pytest.mark.parametrize(
        ("name", "field"),
        [
            ("Опт 1", "opt1_price"),
            ("опт2", "opt2_price"),
            ("Опт 3", "opt3_price"),
            ("опт4", "opt4_price"),
            ("Тренер", "trainer_price"),
            ("РРЦ рекомендованная", "rrp"),
            ("РРЦ", "retail_price"),
            ("МРЦ", "msrp"),
            ("Розничная", "retail_price"),
        ],
    )
    def test_known_price_types(self, parser, name, field):
        assert parser._map_price_type_to_field(name) == field

    def test_unknown_price_type_is_not_applied_and_warns(self, parser, caplog):
        with caplog.at_level("WARNING", logger="import_products"):
            assert parser._map_price_type_to_field("Партнер") == ""

        assert any("Неопознанный вид цен" in r.getMessage() for r in caplog.records)


class TestRealReferenceFiles:
    def test_price_lists(self, parser):
        types = parser.parse_price_lists_xml(str(ONEC_FIXTURES / "priceLists" / "priceLists.xml"))

        assert types
        assert all(item["onec_id"] and item["onec_name"] for item in types)

    def test_prices_and_rests(self, parser):
        prices = parser.parse_prices_xml(str(ONEC_FIXTURES / "prices" / "prices.xml"))
        rests = parser.parse_rests_xml(str(ONEC_FIXTURES / "rests" / "rests.xml"))

        assert prices and all(item["prices"] for item in prices)
        assert rests and all(isinstance(item["quantity"], int) for item in rests)

    def test_brands_are_deduplicated_and_without_no_brand(self, parser):
        brands = []
        for path in sorted((ONEC_FIXTURES / "propertiesGoods").glob("propertiesGoods_*.xml")):
            brands.extend(parser.parse_properties_goods_xml(str(path)))

        assert brands
        assert all(brand["id"] and brand["name"] and brand["name"] != "Без Бренда" for brand in brands)
        assert len({brand["id"] for brand in brands if brand["id"]}) >= 1

    def test_rests_with_unparsable_quantity_are_skipped(self, parser, tmp_path):
        source = ONEC_FIXTURES / "rests" / "rests.xml"
        original = parser.parse_rests_xml(str(source))
        path = edit_copy(source, tmp_path / "rests.xml", lambda text: text.replace("<Количество>", "<Количество>x", 1))

        rests = parser.parse_rests_xml(str(path))

        assert len(rests) == len(original) - 1

    def test_group_without_id_or_name_is_skipped(self, parser, tmp_path):
        source = ONEC_FIXTURES / "groups" / "groups.xml"
        original = parser.parse_groups_xml(str(source))
        first_name = f"<Наименование>{original[0]['name']}</Наименование>"
        path = edit_copy(source, tmp_path / "groups.xml", lambda text: text.replace(first_name, "", 1))

        groups = parser.parse_groups_xml(str(path))

        assert len(groups) < len(original)

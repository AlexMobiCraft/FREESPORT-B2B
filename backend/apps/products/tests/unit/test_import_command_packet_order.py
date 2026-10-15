"""
Команда `import_products_from_1c`: порядок пакетов выгрузки и итог правила допуска.

Один товар повторяется в нескольких пакетах `goods_1_N` с разной группой, и
побеждать обязан более поздний. Имена файлов — реальные имена сегментов 1С.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest

from apps.products.management.commands.import_products_from_1c import Command, natural_sort_key

pytestmark = [pytest.mark.unit]

# Реальные имена пакетов снимка 21.09.2026 (goods_1_<N>_<guid>.xml)
REAL_PACKET_NAMES = [
    "goods_1_1_d0b3150e-1f3b-43f7-a036-070e4dabb9aa.xml",
    "goods_1_2_7c88f79a-5508-4fdb-9af5-c6ab166f14a3.xml",
    "goods_1_9_84cbe045-8016-461d-9027-e45f9c488cec.xml",
    "goods_1_10_0e3264b9-7cc6-48f7-89d6-90c4834feb95.xml",
    "goods_1_11_10a5f16a-bfd6-4826-abd8-d2ade21d1377.xml",
    "goods_1_20_1657206e-bb29-46a9-aa76-f11d8f4fac14.xml",
]


class TestNaturalSortKey:
    def test_packets_are_ordered_by_number_not_lexicographically(self):
        shuffled = sorted(REAL_PACKET_NAMES)  # лексикографически: 1_1, 1_10, 1_11, 1_2, 1_20, 1_9
        assert shuffled != REAL_PACKET_NAMES

        ordered = sorted((Path(name) for name in shuffled), key=natural_sort_key)

        assert [path.name for path in ordered] == REAL_PACKET_NAMES

    def test_key_never_compares_text_with_number(self):
        """Имена разной структуры сортируются без TypeError."""
        names = ["goods.xml", "goods_1_2_a.xml", "goods_a_b.xml", "goods_10.xml", "Goods_1_1_B.xml", "goods__3.xml"]

        ordered = sorted((Path(name) for name in names), key=natural_sort_key)

        assert len(ordered) == len(names)
        assert ordered.index(Path("Goods_1_1_B.xml")) < ordered.index(Path("goods_1_2_a.xml"))


class TestCollectXmlFilesOrder:
    def _command(self) -> Command:
        command = Command()
        command.stdout = StringIO()  # type: ignore[assignment]
        return command

    def test_segments_are_collected_in_packet_order(self, tmp_path):
        goods_dir = tmp_path / "goods"
        goods_dir.mkdir()
        for name in REAL_PACKET_NAMES:
            (goods_dir / name).write_bytes(b"")

        collected = self._command()._collect_xml_files(str(tmp_path), "goods", "goods.xml")

        assert [Path(path).name for path in collected] == REAL_PACKET_NAMES

    def test_single_file_precedes_segments_and_no_duplicates(self, tmp_path):
        offers_dir = tmp_path / "offers"
        offers_dir.mkdir()
        for name in ("offers_1_10_b.xml", "offers.xml", "offers_1_9_a.xml"):
            (offers_dir / name).write_bytes(b"")

        collected = self._command()._collect_xml_files(str(tmp_path), "offers", "offers.xml")

        assert [Path(path).name for path in collected] == ["offers.xml", "offers_1_9_a.xml", "offers_1_10_b.xml"]


class TestPrintStats:
    def test_admission_section_is_printed(self):
        command = Command()
        out = StringIO()
        command.stdout = out  # type: ignore[assignment]
        line = "Вне СПОРТ / к удалению: не создано 5 товаров / 7 вариантов, скрыто 2 / 1, возвращено 3 / 4"

        command._print_stats(
            {
                "skipped_products": 5,
                "hidden_products": 2,
                "restored_products": 3,
                "recategorized_products": 6,
                "skipped_variants": 7,
                "hidden_variants": 1,
                "restored_variants": 4,
            },
            line,
        )

        output = out.getvalue()
        assert "ВНЕ ДЕРЕВА ЯКОРЯ / К УДАЛЕНИЮ" in output
        assert "Товаров не создано:      5" in output
        assert "Товаров скрыто:          2" in output
        assert "Товаров возвращено:      3" in output
        assert "Перенесено в категорию:  6" in output
        assert "Вариантов не создано:    7" in output
        assert "Вариантов скрыто:        1" in output
        assert "Вариантов возвращено:    4" in output
        assert line in output

    def test_section_is_printed_without_summary_line(self):
        command = Command()
        out = StringIO()
        command.stdout = out  # type: ignore[assignment]

        command._print_stats({})

        output = out.getvalue()
        assert "Товаров не создано:      0" in output
        assert "Вне СПОРТ" not in output

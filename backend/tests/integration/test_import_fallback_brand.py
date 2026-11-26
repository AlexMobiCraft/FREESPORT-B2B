"""Интеграционные тесты fallback-бренда на реальной выгрузке 1С (Story 41.16).

Правило проекта: тесты импорта 1С гоняются на реальных XML из `data/import_1c`,
синтетика не создаётся. Каталог в .gitignore, поэтому на раннере тест скипается
(маркер `data_dependent`, как у остальных тестов корпуса).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.products.models import Brand, Brand1CMapping, ImportSession
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import NO_BRAND_ONEC_ID, VariantImportProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.integration, pytest.mark.data_dependent]

# Назначенный правилами проекта корпус runtime-выгрузок 1С.
ONEC_RUNTIME_CORPUS = Path(__file__).resolve().parents[2] / "data" / "import_1c"


def _smallest_goods_segment() -> Path | None:
    """Наименьший реальный goods.xml из корпуса или None, если корпуса нет."""
    segments = sorted(
        ONEC_RUNTIME_CORPUS.rglob("goods/*.xml"),
        key=lambda path: path.stat().st_size,
    )
    return segments[0] if segments else None


def _load_groups_for(goods_file: Path, processor: VariantImportProcessor) -> None:
    """Загрузить дерево групп той же выгрузки, что и goods.xml.

    Импорт допускает только товары из поддерева якоря «СПОРТ»: без дерева
    категорий сессия не создаёт ни одного товара.
    """
    groups_files = sorted((goods_file.parent.parent / "groups").glob("*.xml"))
    if not groups_files:
        pytest.skip(f"Рядом с {goods_file.name} нет groups*.xml — дерево якоря построить не из чего")
    for groups_file in groups_files:
        processor.process_categories(XMLDataParser().parse_groups_xml(str(groups_file)))


def _first_admitted(goods_file: Path, processor: VariantImportProcessor, predicate) -> tuple[Path, dict | None]:
    """Первый товар выгрузки, проходящий правило допуска и условие теста.

    Правило допуска — дерево СПОРТ без пометки удаления: большая часть выгрузки
    (спецзаказы, имущество, «к удалению») в БД не попадает, и в одном сегменте
    подходящего товара может не оказаться. Сегменты той же выгрузки перебираются
    от меньшего к большему.
    """
    segments = sorted(goods_file.parent.glob("*.xml"), key=lambda path: path.stat().st_size)
    for segment in segments:
        for goods in XMLDataParser().parse_goods_xml(str(segment)):
            goods_data = dict(goods)
            if predicate(goods_data) and processor._product_rejection_reason(goods_data) is None:
                return segment, goods_data
    return goods_file, None


@pytest.fixture
def processor() -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.IN_PROGRESS,
    )
    return VariantImportProcessor(session_id=session.id)


class TestFallbackBrandOnRealCorpus:
    """Товары «без бренда» из 1С не должны давать латинский «No Brand»."""

    def test_zero_uuid_brand_resolves_to_fallback(self, processor):
        """Нулевой UUID из goods.xml сводится к «Без ТМ», а не к «No Brand»."""
        goods_file = _smallest_goods_segment()
        if goods_file is None:
            pytest.skip(f"Корпус выгрузок 1С недоступен: {ONEC_RUNTIME_CORPUS}")

        _load_groups_for(goods_file, processor)
        goods_file, brandless = _first_admitted(
            goods_file, processor, lambda goods: goods.get("brand_id") == NO_BRAND_ONEC_ID
        )
        assert brandless, f"В реальной выгрузке {goods_file.parent} нет допущенных товаров с нулевым UUID бренда"

        product = processor.process_product_from_goods(brandless, base_dir=None, skip_images=True)

        assert product is not None, "Реальный товар без бренда не импортировался"
        assert product.brand is not None
        assert product.brand.name == "Без ТМ"
        # Значение 1С сохраняется как есть — признак «без бренда» не отбрасывается.
        assert product.onec_brand_id == NO_BRAND_ONEC_ID
        assert not Brand.objects.filter(normalized_name="nobrand").exists(), "Импорт создал латинский «No Brand»"
        assert Brand1CMapping.objects.filter(onec_id=NO_BRAND_ONEC_ID, brand=product.brand).exists()

    def test_branded_product_from_real_corpus_keeps_its_brand(self, processor):
        """Товар с реальным брендом не уезжает в fallback-бренд."""
        goods_file = _smallest_goods_segment()
        if goods_file is None:
            pytest.skip(f"Корпус выгрузок 1С недоступен: {ONEC_RUNTIME_CORPUS}")

        _load_groups_for(goods_file, processor)
        goods_file, goods = _first_admitted(
            goods_file, processor, lambda goods: goods.get("brand_id") not in (None, "", NO_BRAND_ONEC_ID)
        )
        assert goods, f"В реальной выгрузке {goods_file.parent} нет допущенных товаров с брендом"
        brand = Brand.objects.create(name=f"Реальный бренд {goods['id'][:8]}", slug=f"real-{goods['id'][:8]}")
        Brand1CMapping.objects.create(brand=brand, onec_id=goods["brand_id"], onec_name=brand.name)

        product = processor.process_product_from_goods(goods, base_dir=None, skip_images=True)

        assert product is not None
        assert product.brand_id == brand.pk
        assert not Brand.objects.filter(slug="bez-tm").exists()

"""Длинный «размер» из 1С не роняет вариант (AC7 стори гонки cleanup).

`ProductVariant.size_value` — единственное `varchar(50)` у модели. Импорт пишет
поле напрямую, минуя `full_clean()`, поэтому значение длиннее 50 символов
возвращает `DataError: value too long for type character varying(50)`, и вариант
**не создаётся вообще**. Так 25.08.2026 потерялись 12 вариантов в окне `offers`
17:20–17:24 — это потеря данных, а не косметика.

Разбор реальных выгрузок показал, откуда берётся длина. Характеристик «Размер»
длиннее 40 символов в корпусе нет ни одной; переполняет поле резервный путь —
`extract_size_from_name`, который забирает содержимое последних скобок
наименования. Для услуг и комплексов там лежит что угодно, кроме размера:

    Оборудование спортивное уличное (Romana 701.09.00 Боксерская груша
    подвесная (стандартный))   →   57 символов

Поэтому основной тест берёт именно этот оффер из назначенного корпуса
`data/import_1c/`, а не выдуманный XML.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from apps.products.models import (
    Brand,
    Category,
    ImportSession,
    Product,
    ProductVariant,
)
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor

# Назначенный корпус runtime-выгрузок (в .gitignore, на раннере отсутствует).
ONEC_RUNTIME_OFFERS = Path(__file__).resolve().parents[3] / "data" / "import_1c" / "offers"

# Оффер, чей fallback из скобок даёт 57 символов — прямой аналог прод-случая.
OVERFLOW_OFFER_ID = "45d113f2-bbcb-11f0-8110-fa163ea88911#3538958e-bbde-11f0-8110-fa163ea88911"
OVERFLOW_OFFER_FILE = "offers_1_14_e934b984-5c19-4e5a-af44-22174913fe9f.xml"

SIZE_MAX_LENGTH = ProductVariant._meta.get_field("size_value").max_length


def _make_parent(onec_id: str, slug: str) -> Product:
    """Родительский товар — без него предложение просто пропускается как orphan."""
    brand = Brand.objects.create(name=f"Бренд {slug}", slug=f"brand-{slug}", is_active=True)
    category = Category.objects.create(
        name=f"Категория {slug}", slug=f"cat-{slug}", onec_id=f"cat-{slug}", is_active=True
    )
    return Product.objects.create(
        name=f"Товар {slug}",
        slug=slug,
        onec_id=onec_id,
        parent_onec_id=onec_id,
        brand=brand,
        category=category,
        description="",
        is_active=False,
    )


@pytest.fixture
def processor(db) -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.STARTED,
    )
    return VariantImportProcessor(session_id=session.pk, batch_size=500)


@pytest.mark.django_db
class TestSizeValueOverflow:
    """AC7 — вариант обязан пережить любой вход, каким бы длинным он ни был."""

    @pytest.mark.data_dependent
    def test_real_offer_with_long_parenthetical_survives(self, processor):
        """Реальный оффер из корпуса: вариант создан, длинный «размер» отброшен."""
        segment = ONEC_RUNTIME_OFFERS / OVERFLOW_OFFER_FILE
        if not segment.exists():
            pytest.skip("Назначенный корпус data/import_1c отсутствует (в .gitignore)")

        offers = XMLDataParser().parse_offers_xml(str(segment))
        offer_data = next((o for o in offers if o.get("id") == OVERFLOW_OFFER_ID), None)
        assert offer_data is not None, f"Оффер {OVERFLOW_OFFER_ID} исчез из корпуса"

        parent_id = OVERFLOW_OFFER_ID.split("#", 1)[0]
        _make_parent(parent_id, "romana-outdoor")

        variant = processor.process_variant_from_offer(offer_data, skip_images=True)

        assert variant is not None, "Вариант потерян — это и есть дефект AC7"
        assert variant.size_value == ""
        assert processor.stats["variants_created"] == 1
        assert processor.stats["errors"] == 0
        assert processor.stats["size_value_dropped"] == 1

    def test_drop_is_visible_in_session_report(self, processor):
        """Отбрасывание видно в текстовом report и в report_details, а не только в логах."""
        _make_parent("parent-report", "parent-report")
        long_size = "Romana 501.96.00 Оборудование спортивное подвесное (черный)"
        assert len(long_size) > SIZE_MAX_LENGTH

        variant = processor.process_variant_from_offer(
            {
                "id": "parent-report#variant-report",
                "name": "Комплекс уличный",
                "article": "REPORT-001",
                "characteristics": [{"name": "Размер", "value": long_size}],
            },
            skip_images=True,
        )
        # Главное утверждение AC7, и оно обязано жить в тесте, который идёт в CI:
        # корпус data/import_1c на раннере отсутствует, data_dependent там скипается.
        assert variant is not None, "Вариант потерян — это и есть дефект AC7"
        assert variant.size_value == ""

        processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

        session = ImportSession.objects.get(pk=processor.session_id)
        assert session.report_details["size_value_dropped"] == 1
        assert "parent-report#variant-report" in session.report
        assert "size_value" in session.report

    def test_value_at_max_length_is_kept(self, processor):
        """Ровно лимит — это валидный вход, отбрасывать его нельзя."""
        _make_parent("parent-exact", "parent-exact")
        exact = "Р" * SIZE_MAX_LENGTH

        variant = processor.process_variant_from_offer(
            {
                "id": "parent-exact#variant-exact",
                "name": "Товар с длинным размером",
                "article": "EXACT-001",
                "characteristics": [{"name": "Размер", "value": exact}],
            },
            skip_images=True,
        )

        assert variant is not None
        assert variant.size_value == exact
        assert processor.stats["size_value_dropped"] == 0

    def test_value_one_over_max_length_is_dropped(self, processor):
        """Лимит + 1 — ближайшая точка, где ослабление сравнения вернуло бы DataError."""
        _make_parent("parent-edge", "parent-edge")
        over = "Р" * (SIZE_MAX_LENGTH + 1)

        variant = processor.process_variant_from_offer(
            {
                "id": "parent-edge#variant-edge",
                "name": "Товар на грани",
                "article": "EDGE-001",
                "characteristics": [{"name": "Размер", "value": over}],
            },
            skip_images=True,
        )

        assert variant is not None
        assert variant.size_value == ""
        assert processor.stats["size_value_dropped"] == 1

    def test_long_characteristic_does_not_block_size_from_name(self, processor):
        """Мусорная характеристика не должна съедать валидный размер из наименования.

        Порядок важен: если браковать длину после fallback, длинная характеристика
        успевает занять поле, fallback не срабатывает, и «XL» из скобок теряется.
        """
        _make_parent("parent-fallback", "parent-fallback")

        variant = processor.process_variant_from_offer(
            {
                "id": "parent-fallback#variant-fallback",
                "name": "Кимоно для джиу джитсу BoyBo, синий (XL)",
                "article": "FALLBACK-001",
                "characteristics": [{"name": "Размер", "value": "К" * 70}],
            },
            skip_images=True,
        )

        assert variant is not None
        assert variant.size_value == "XL"
        assert processor.stats["size_value_dropped"] == 1

    def test_repeated_offer_counted_once(self, processor):
        """Один оффер в двух сегментах — это один пострадавший вариант, не два."""
        _make_parent("parent-repeat", "parent-repeat")
        offer = {
            "id": "parent-repeat#variant-repeat",
            "name": "Комплекс без размера",
            "article": "REPEAT-001",
            "characteristics": [{"name": "Размер", "value": "К" * 70}],
        }

        processor.process_variant_from_offer(offer, skip_images=True)
        processor.process_variant_from_offer(offer, skip_images=True)

        assert processor.stats["size_value_dropped"] == 1

    def test_existing_size_not_overwritten_by_long_value(self, processor):
        """У живого варианта валидный размер не затирается мусором из новой выгрузки."""
        product = _make_parent("parent-update", "parent-update")
        variant = ProductVariant.objects.create(
            product=product,
            sku="UPD-001",
            onec_id="parent-update#variant-update",
            color_name="Синий",
            size_value="42",
            retail_price=Decimal("0"),
            is_active=True,
        )

        processor.process_variant_from_offer(
            {
                "id": variant.onec_id,
                "name": "Товар обновлённый",
                "article": "UPD-001",
                "characteristics": [{"name": "Размер", "value": "К" * 80}],
            },
            skip_images=True,
        )

        variant.refresh_from_db()
        assert variant.size_value == "42"
        assert processor.stats["size_value_dropped"] == 1

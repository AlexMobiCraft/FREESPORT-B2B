"""
Интеграционные тесты импорта цен вида «Опт 4» из 1С (Story 39.2).

Проверяют полную цепочку: priceLists.xml → PriceType.product_field →
prices.xml → ProductVariant.opt4_price.

Отдельно закрывается регресс стори 39.1: импорт справочника типов цен
перетирал `product_field` записи «Опт 4» на `retail_price`, из-за чего
оптовые цены четвёртого уровня уезжали в розничную цену.

Используются только реальные выгрузки из backend/data/import_1c/ —
синтетические XML для тестов импорта 1С запрещены (NFR-3940-01).
"""

from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pytest

from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.data_dependent, pytest.mark.django_db]

OPT4_PRICE_TYPE_GUID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"


def _import_1c_dir() -> Path:
    """Каталог реальных выгрузок 1С: в Docker примонтирован в /app/data."""
    if os.path.exists("/app/data"):
        return Path("/app/data/import_1c")
    # backend/tests/integration/<file>.py → parents[2] == backend/
    return Path(__file__).resolve().parents[2] / "data" / "import_1c"


@pytest.fixture
def price_lists_file() -> str:
    """Реальный снимок справочника типов цен из 1С."""
    matches = sorted(_import_1c_dir().glob("priceLists/priceLists_*.xml"))
    if not matches:
        pytest.skip("Реальный снимок priceLists из 1С не найден")
    return str(matches[0])


@pytest.fixture
def prices_file_with_opt4() -> str:
    """Первый реальный файл цен, содержащий цены вида «Опт 4».

    Файлов шесть по ~2.8 МБ, GUID «Опт 4» встречается не во всех — фильтруем
    по содержимому, а не по имени.
    """
    for path in sorted(_import_1c_dir().glob("prices/prices_*.xml")):
        if OPT4_PRICE_TYPE_GUID in path.read_text(encoding="utf-8"):
            return str(path)
    pytest.skip(f"В снимке prices нет цен вида «Опт 4» ({OPT4_PRICE_TYPE_GUID}) — переснимите выгрузку")


@pytest.fixture
def processor() -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.STARTED,
    )
    return VariantImportProcessor(session_id=session.pk)


@pytest.fixture
def opt4_price_type() -> PriceType:
    """Запись справочника «Опт 4» в состоянии после data-миграции 0053.

    Автоочистка БД (`clear_db_before_test`) сносит данные data-миграций,
    поэтому запись создаётся явно.
    """
    return PriceType.objects.create(
        onec_id=OPT4_PRICE_TYPE_GUID,
        onec_name="Опт 4 (до 50 тыс.руб в квартал)",
        product_field="opt4_price",
        user_role="wholesale_level4",
        is_active=True,
    )


def _create_variant(onec_id: str) -> ProductVariant:
    """Минимальные Product + ProductVariant под конкретный onec_id предложения."""
    suffix = get_unique_suffix()
    brand = Brand.objects.create(name=f"Бренд {suffix}", slug=f"brand-{suffix}", is_active=True)
    category = Category.objects.create(name=f"Категория {suffix}", slug=f"category-{suffix}", is_active=True)
    product = Product.objects.create(
        onec_id=f"product-{suffix}",
        name=f"Товар {suffix}",
        slug=f"product-{suffix}",
        brand=brand,
        category=category,
        description="",
        is_active=True,
    )
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{suffix}",
        onec_id=onec_id,
        retail_price=Decimal("0"),
        is_active=True,
    )


def _first_opt4_offer(prices_file: str) -> dict:
    """Первое предложение реальной выгрузки, у которого есть цена вида «Опт 4»."""
    parsed = XMLDataParser().parse_prices_xml(prices_file)
    return next(item for item in parsed if any(p["price_type_id"] == OPT4_PRICE_TYPE_GUID for p in item["prices"]))


def _opt4_value(offer: dict) -> Decimal:
    return next(p["value"] for p in offer["prices"] if p["price_type_id"] == OPT4_PRICE_TYPE_GUID)


# ============================================================================
# AC3: priceLists.xml → PriceType.product_field == "opt4_price"
# ============================================================================


def test_real_price_lists_maps_opt4_to_opt4_price_field(price_lists_file, processor):
    """AC3: разбор реального priceLists даёт product_field="opt4_price" и пишет его в БД."""
    parsed = XMLDataParser().parse_price_lists_xml(price_lists_file)

    opt4_entry = next((item for item in parsed if item["onec_id"] == OPT4_PRICE_TYPE_GUID), None)
    assert opt4_entry is not None, f"В реальном снимке priceLists нет вида цен «Опт 4» ({OPT4_PRICE_TYPE_GUID})"
    assert opt4_entry["product_field"] == "opt4_price"

    processed = processor.process_price_types(parsed)
    assert processed == len(parsed)

    stored = PriceType.objects.get(onec_id=OPT4_PRICE_TYPE_GUID)
    assert stored.product_field == "opt4_price"


def test_import_preserves_opt4_mapping_and_user_role(price_lists_file, processor, opt4_price_type):
    """AC3, страховка от регресса 39.1.

    Импорт справочника не перетирает `product_field` записи «Опт 4» на
    `retail_price` и не трогает `user_role`, выставленный миграцией 0053.
    """
    parsed = XMLDataParser().parse_price_lists_xml(price_lists_file)
    processor.process_price_types(parsed)

    opt4_price_type.refresh_from_db()
    assert opt4_price_type.product_field == "opt4_price"
    assert opt4_price_type.user_role == "wholesale_level4"


# ============================================================================
# AC4: prices.xml → ProductVariant.opt4_price
# ============================================================================


def test_real_prices_fill_variant_opt4_price(prices_file_with_opt4, processor, opt4_price_type):
    """AC4: цена вида «Опт 4» из реальной выгрузки попадает в ProductVariant.opt4_price."""
    offer = _first_opt4_offer(prices_file_with_opt4)
    expected = _opt4_value(offer)
    variant = _create_variant(offer["id"])

    assert processor.update_variant_prices(offer) is True

    variant.refresh_from_db()
    assert variant.opt4_price == expected


# ============================================================================
# AC6: идемпотентность повторного прогона
# ============================================================================


def test_price_types_import_is_idempotent(price_lists_file, processor, opt4_price_type):
    """AC6: повторный прогон priceLists не плодит дубли PriceType и не меняет маппинг."""
    parsed = XMLDataParser().parse_price_lists_xml(price_lists_file)

    processor.process_price_types(parsed)
    processor.process_price_types(parsed)

    assert PriceType.objects.filter(onec_id=OPT4_PRICE_TYPE_GUID).count() == 1
    stored = PriceType.objects.get(onec_id=OPT4_PRICE_TYPE_GUID)
    assert stored.product_field == "opt4_price"
    assert stored.user_role == "wholesale_level4"


def test_repeated_price_import_keeps_opt4_price_stable(prices_file_with_opt4, processor, opt4_price_type):
    """AC6: повторный прогон того же файла цен не меняет opt4_price и не плодит варианты."""
    offer = _first_opt4_offer(prices_file_with_opt4)
    expected = _opt4_value(offer)
    variant = _create_variant(offer["id"])

    processor.update_variant_prices(offer)
    processor.update_variant_prices(offer)

    variant.refresh_from_db()
    assert variant.opt4_price == expected
    assert ProductVariant.objects.filter(onec_id=offer["id"]).count() == 1
    assert PriceType.objects.filter(onec_id=OPT4_PRICE_TYPE_GUID).count() == 1

"""
VariantImportProcessor: ветки ошибок и обновления, не попавшие в основные тесты.

Правило допуска даёт процессору много новых точек отказа (дерево якоря,
реестр, скрытие) — здесь закреплено, что сбой одной записи не роняет сессию:
он уходит в `errors`, а не в исключение.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest

from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


@pytest.fixture
def processor(settings) -> VariantImportProcessor:
    settings.ROOT_CATEGORY_NAME = "СПОРТ"
    session = ImportSession.objects.create(import_type=ImportSession.ImportType.CATALOG, status="in_progress")
    return VariantImportProcessor(session_id=session.pk)


@pytest.fixture
def sport(db) -> Category:
    anchor = Category.objects.create(name="СПОРТ", slug="ep-sport", onec_id="ep-sport")
    return Category.objects.create(name="Бокс", slug="ep-boxing", onec_id="ep-boxing", parent=anchor)


@pytest.fixture
def product(sport) -> Product:
    brand = Brand.objects.create(name="EP Brand", slug="ep-brand")
    return Product.objects.create(
        name="Товар",
        slug="ep-product",
        onec_id="ep-1",
        parent_onec_id="ep-1",
        brand=brand,
        category=sport,
        description="",
    )


def _goods(onec_id: str = "ep-1", **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"id": onec_id, "name": "Товар", "category_ids": ["ep-boxing"], "category_id": "ep-boxing"}
    data.update(extra)
    return data


class TestAdmissionContext:
    def test_disabled_filter_warning_is_written_once(self, processor, caplog):
        with caplog.at_level("WARNING", logger="import_products"):
            processor._warn_root_filter_disabled()
            processor._warn_root_filter_disabled()

        assert sum("ROOT_CATEGORY_NAME пуст" in r.getMessage() for r in caplog.records) == 1

    def test_anchor_found_in_first_groups_file_is_reused_by_next_files(self, processor):
        """Второй groups*.xml сессии без якоря опирается на якорь первого, а не на БД."""
        processor.process_categories([{"id": "ep-sport", "name": "СПОРТ"}])
        Category.objects.filter(onec_id="ep-sport").delete()

        result = processor.process_categories([{"id": "ep-child", "name": "Потомок", "parent_id": "ep-sport"}])

        assert processor._anchor_id == "ep-sport"
        assert result.get("root_not_found") is not True

    def test_anchor_missing_is_reported_once_per_session(self, processor):
        processor.process_categories([{"id": "x", "name": "ДРУГОЕ"}])
        processor.process_categories([{"id": "y", "name": "ДРУГОЕ-2"}])

        report = ImportSession.objects.get(pk=processor.session_id).report
        assert report.count("не найден ни в XML, ни в БД") == 1


class TestProductErrors:
    def test_goods_without_id_is_an_error(self, processor):
        assert processor.process_product_from_goods({"name": "Без Ид"}) is None
        assert processor.stats["errors"] == 1

    def test_unexpected_failure_is_counted_not_raised(self, processor, sport):
        with patch.object(processor, "_ensure_admission_context", side_effect=RuntimeError("boom")):
            assert processor.process_product_from_goods(_goods()) is None

        assert processor.stats["errors"] == 1

    def test_save_failure_of_new_product_is_counted(self, processor, sport):
        with patch.object(Product, "save", side_effect=RuntimeError("db down")):
            assert processor.process_product_from_goods(_goods("ep-new"), skip_images=True) is None

        assert processor.stats["errors"] == 1
        assert processor.stats["products_created"] == 0

    def test_existing_product_without_onec_id_gets_it(self, processor, product):
        Product.objects.filter(pk=product.pk).update(onec_id=None)

        result = processor.process_product_from_goods(_goods(), skip_images=True)

        assert result is not None and result.onec_id == "ep-1"

    def test_category_missing_in_db_skips_product(self, processor, sport):
        """Группа в дереве, а категории нет (битое дерево) — товар не создаётся и не падает."""
        processor._admission_ready = True
        processor._category_filtering_active = True
        processor._anchor_id = "ep-sport"
        processor._allowed_category_ids = {"ep-sport", "ep-ghost"}
        processor._group_parent_of = {"ep-ghost": "ep-sport"}

        assert (
            processor.process_product_from_goods(_goods("ep-new", category_ids=["ep-ghost"]), skip_images=True) is None
        )

        assert processor.stats["skipped_products"] == 1
        assert not Product.objects.filter(onec_id="ep-new").exists()

    def test_slug_fallbacks(self, processor, product):
        assert processor._generate_unique_slug("!!!", "abcdefghij") == "product-abcdefgh"
        Product.objects.filter(pk=product.pk).update(slug="tovar")
        assert processor._generate_unique_slug("Товар", "x").startswith("tovar-")


class TestOfferErrors:
    def test_offer_without_id_is_an_error(self, processor):
        assert processor.process_variant_from_offer({"name": "Без Ид"}) is None
        assert processor.stats["errors"] == 1

    def test_unexpected_failure_is_counted_not_raised(self, processor, product):
        with patch.object(processor, "_is_product_excluded", side_effect=RuntimeError("boom")):
            assert processor.process_variant_from_offer({"id": "ep-1#v1"}) is None

        assert processor.stats["errors"] == 1

    def test_save_failure_of_new_variant_is_counted(self, processor, product):
        with patch.object(ProductVariant, "save", side_effect=RuntimeError("db down")):
            assert processor.process_variant_from_offer({"id": "ep-1#v1"}, skip_images=True) is None

        assert processor.stats["errors"] == 1
        assert processor.stats["variants_created"] == 0

    def test_existing_variant_takes_new_sku_color_and_size(self, processor, product):
        variant = ProductVariant.objects.create(
            product=product, sku="OLD-SKU", onec_id="ep-1#v1", retail_price=Decimal("1"), color_name="", size_value=""
        )

        processor.process_variant_from_offer(
            {
                "id": "ep-1#v1",
                "name": "Товар",
                "article": "NEW-SKU",
                "characteristics": [{"name": "Цвет", "value": "Красный"}, {"name": "Размер", "value": "42"}],
            },
            skip_images=True,
        )

        variant.refresh_from_db()
        assert (variant.sku, variant.color_name, variant.size_value) == ("NEW-SKU", "Красный", "42")

    def test_attribute_link_failure_is_counted_for_new_and_existing_variants(self, processor, product):
        offer = {"id": "ep-1#v1", "name": "Товар", "characteristics": [{"name": "Цвет", "value": "Красный"}]}

        with patch.object(processor, "_link_variant_attributes", side_effect=RuntimeError("attr")):
            assert processor.process_variant_from_offer(dict(offer), skip_images=True) is not None
            assert processor.process_variant_from_offer(dict(offer), skip_images=True) is not None

        assert processor.stats["errors"] == 2


class TestPricesAndStocksErrors:
    def test_price_without_id_is_an_error(self, processor):
        assert processor.update_variant_prices({"prices": []}) is False
        assert processor.stats["errors"] == 1

    def test_stock_without_id_is_an_error(self, processor):
        assert processor.update_variant_stock({"quantity": 1}) is False
        assert processor.stats["errors"] == 1

    def test_price_failure_is_counted_not_raised(self, processor, product):
        ProductVariant.objects.create(product=product, sku="P-1", onec_id="ep-1#v1", retail_price=Decimal("1"))
        PriceType.objects.create(onec_id="pt", onec_name="Розничная", product_field="retail_price", is_active=True)

        with patch.object(ProductVariant, "save", side_effect=RuntimeError("db down")):
            assert (
                processor.update_variant_prices({"id": "ep-1#v1", "prices": [{"price_type_id": "pt", "value": 5}]})
                is False
            )

        assert processor.stats["errors"] == 1

    def test_stock_failure_is_counted_not_raised(self, processor, product):
        ProductVariant.objects.create(product=product, sku="S-1", onec_id="ep-1#v1", retail_price=Decimal("1"))

        with patch.object(ProductVariant, "save", side_effect=RuntimeError("db down")):
            assert processor.update_variant_stock({"id": "ep-1#v1", "warehouse_id": "w", "quantity": 1}) is False

        assert processor.stats["errors"] == 1

    def test_price_with_unpriced_type_changes_nothing(self, processor, product):
        ProductVariant.objects.create(product=product, sku="P-2", onec_id="ep-1#v2", retail_price=Decimal("1"))

        assert processor.update_variant_prices({"id": "ep-1#v2", "prices": [{"price_type_id": "unknown"}]}) is False

    def test_price_type_error_is_counted(self, processor):
        assert processor.process_price_types([{"onec_name": "без Ид"}]) == 0  # type: ignore[list-item]
        assert processor.stats["errors"] == 1


class TestDefaultVariantBatches:
    def test_default_variants_are_created_in_batches(self, settings, sport):
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        session = ImportSession.objects.create(import_type=ImportSession.ImportType.CATALOG, status="in_progress")
        processor = VariantImportProcessor(session_id=session.pk, batch_size=1)
        brand = Brand.objects.create(name="Batch Brand", slug="batch-brand")
        for index in range(3):
            Product.objects.create(
                name=f"Товар {index}",
                slug=f"batch-{index}",
                onec_id=f"batch-{index}",
                brand=brand,
                category=sport,
                description="",
                is_active=False,
            )

        assert processor.create_default_variants() == 3
        assert Product.objects.filter(is_active=True).count() == 3

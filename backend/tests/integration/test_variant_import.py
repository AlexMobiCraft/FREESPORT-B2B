"""
Integration тесты для импорта ProductVariant из 1С (Story 13.2)

Тестирует новый workflow импорта:
1. goods.xml → Product (базовая информация, base_images)
2. offers.xml → ProductVariant (SKU, характеристики)
3. Default variants → ProductVariant для товаров без вариантов
4. prices.xml → ProductVariant (цены)
5. rests.xml → ProductVariant (остатки)
"""

import os
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest
from django.test import TestCase, TransactionTestCase, override_settings

from apps.products.models import (
    Brand,
    Brand1CMapping,
    Category,
    ColorMapping,
    ImportSession,
    PriceType,
    Product,
    ProductVariant,
)
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import (
    VariantImportProcessor,
    extract_color_from_name,
    extract_size_from_name,
    parse_characteristics,
    parse_onec_id,
)

# ============================================================================
# Test fixtures - XML data
# ============================================================================

SAMPLE_GOODS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">
    <Каталог>
        <Товары>
            <Товар>
                <Ид>test-product-001</Ид>
                <Наименование>Тестовый товар синий</Наименование>
                <Описание>Описание тестового товара</Описание>
                <Артикул>TEST-001</Артикул>
                <Группы>
                    <Ид>test-category-001</Ид>
                </Группы>
                <Картинка>import_files/00/test-image-1.jpg</Картинка>
                <Картинка>import_files/00/test-image-2.jpg</Картинка>
            </Товар>
            <Товар>
                <Ид>test-product-002</Ид>
                <Наименование>Товар без вариантов</Наименование>
                <Описание>Товар для теста default variant</Описание>
                <Артикул>TEST-002</Артикул>
            </Товар>
        </Товары>
    </Каталог>
</КоммерческаяИнформация>
"""

SAMPLE_OFFERS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">
    <ПакетПредложений>
        <Предложения>
            <Предложение>
                <Ид>test-product-001#variant-001</Ид>
                <Наименование>Тестовый товар синий (42)</Наименование>
                <Артикул>TEST-001-42</Артикул>
                <ХарактеристикиТовара>
                    <ХарактеристикаТовара>
                        <Наименование>Цвет</Наименование>
                        <Значение>Синий</Значение>
                    </ХарактеристикаТовара>
                    <ХарактеристикаТовара>
                        <Наименование>Размер</Наименование>
                        <Значение>42</Значение>
                    </ХарактеристикаТовара>
                </ХарактеристикиТовара>
            </Предложение>
            <Предложение>
                <Ид>test-product-001#variant-002</Ид>
                <Наименование>Тестовый товар синий (44)</Наименование>
                <Артикул>TEST-001-44</Артикул>
                <ХарактеристикиТовара>
                    <ХарактеристикаТовара>
                        <Наименование>Цвет</Наименование>
                        <Значение>Синий</Значение>
                    </ХарактеристикаТовара>
                    <ХарактеристикаТовара>
                        <Наименование>Размер</Наименование>
                        <Значение>44</Значение>
                    </ХарактеристикаТовара>
                </ХарактеристикиТовара>
            </Предложение>
            <Предложение>
                <Ид>orphan-product#variant-orphan</Ид>
                <Наименование>Вариант без родителя</Наименование>
                <Артикул>ORPHAN-001</Артикул>
            </Предложение>
        </Предложения>
    </ПакетПредложений>
</КоммерческаяИнформация>
"""

SAMPLE_PRICES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">
    <ПакетПредложений>
        <Предложения>
            <Предложение>
                <Ид>test-product-001#variant-001</Ид>
                <Цены>
                    <Цена>
                        <ИдТипаЦены>price-type-retail</ИдТипаЦены>
                        <ЦенаЗаЕдиницу>1500.00</ЦенаЗаЕдиницу>
                    </Цена>
                    <Цена>
                        <ИдТипаЦены>price-type-opt1</ИдТипаЦены>
                        <ЦенаЗаЕдиницу>1200.00</ЦенаЗаЕдиницу>
                    </Цена>
                </Цены>
            </Предложение>
        </Предложения>
    </ПакетПредложений>
</КоммерческаяИнформация>
"""

SAMPLE_RESTS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">
    <ПакетПредложений>
        <Предложения>
            <Предложение>
                <Ид>test-product-001#variant-001</Ид>
                <Остатки>
                    <Остаток>
                        <Склад>
                            <Ид>warehouse-001</Ид>
                            <Количество>50</Количество>
                        </Склад>
                    </Остаток>
                    <Остаток>
                        <Склад>
                            <Ид>warehouse-002</Ид>
                            <Количество>30</Количество>
                        </Склад>
                    </Остаток>
                </Остатки>
            </Предложение>
        </Предложения>
    </ПакетПредложений>
</КоммерческаяИнформация>
"""


# ============================================================================
# Unit tests for helper functions
# ============================================================================


class TestParseOnecId(TestCase):
    """Тесты для функции parse_onec_id"""

    def test_parse_composite_id(self):
        """AC2: Парсинг составного ID parent#variant"""
        parent_id, variant_id = parse_onec_id("12345678-abcd#87654321-dcba")
        assert parent_id == "12345678-abcd"
        assert variant_id == "87654321-dcba"

    def test_parse_simple_id(self):
        """Товар без вариантов - один ID для обоих"""
        parent_id, variant_id = parse_onec_id("simple-product-id")
        assert parent_id == "simple-product-id"
        assert variant_id == "simple-product-id"

    def test_parse_id_with_multiple_hashes(self):
        """ID с несколькими # - разделяем только по первому"""
        parent_id, variant_id = parse_onec_id("parent#variant#extra")
        assert parent_id == "parent"
        assert variant_id == "variant#extra"


class TestParseCharacteristics(TestCase):
    """Тесты для функции parse_characteristics"""

    def test_parse_color_and_size(self):
        """AC4: Извлечение цвета и размера из характеристик"""
        characteristics = [
            {"name": "Цвет", "value": "Синий"},
            {"name": "Размер", "value": "42"},
        ]
        result = parse_characteristics(characteristics)
        assert result["color_name"] == "Синий"
        assert result["size_value"] == "42"

    def test_parse_empty_values(self):
        """Пустые значения игнорируются"""
        characteristics = [
            {"name": "Цвет", "value": ""},
            {"name": "Размер", "value": ""},
        ]
        result = parse_characteristics(characteristics)
        assert result["color_name"] == ""
        assert result["size_value"] == ""

    def test_parse_invalid_values(self):
        """Невалидные значения (-999999999.9) игнорируются"""
        characteristics = [
            {"name": "Размер", "value": "-999 999 999,9"},
        ]
        result = parse_characteristics(characteristics)
        assert result["size_value"] == ""


@pytest.mark.django_db
class TestExtractFromName(TestCase):
    """Тесты для извлечения характеристик из названия"""

    def setUp(self):
        ColorMapping.objects.create(name="Синий", hex_code="#0000FF")

    def test_extract_size_from_name(self):
        """Извлечение размера из названия в скобках"""
        name = "Кимоно для джиу джитсу (BJJ) BoyBo, BBJJ24, синий (А5 (2XL))"
        size = extract_size_from_name(name)
        assert size == "А5 (2XL)"

    def test_extract_simple_size(self):
        """Извлечение простого размера"""
        name = "Боксерки BoyBo TITAN (42)"
        size = extract_size_from_name(name)
        assert size == "42"

    def test_extract_color_from_name(self):
        """Извлечение цвета из названия"""
        name = "Боксерки BoyBo TITAN,IB-26 (одобрены ФБР), синий"
        color = extract_color_from_name(name)
        assert color == "Синий"

    def test_extract_no_color(self):
        """Название без известного цвета"""
        name = "Боксерки BoyBo TITAN"
        color = extract_color_from_name(name)
        assert color == ""


# ============================================================================
# Integration tests for VariantImportProcessor
# ============================================================================


@pytest.mark.django_db(transaction=True)
class TestVariantImportProcessor(TransactionTestCase):
    """Integration тесты для VariantImportProcessor"""

    def setUp(self):
        """Подготовка тестовых данных"""
        # Создаём сессию импорта
        self.session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
        )

        # Создаём тестовый бренд
        self.brand = Brand.objects.create(
            name="Test Brand",
            slug="test-brand",
            is_active=True,
        )

        # Создаём тестовую категорию
        self.category = Category.objects.create(
            name="Test Category",
            slug="test-category",
            onec_id="test-category-001",
            is_active=True,
        )

        # Создаём типы цен
        PriceType.objects.create(
            onec_id="price-type-retail",
            onec_name="Розничная цена",
            product_field="retail_price",
            is_active=True,
        )
        PriceType.objects.create(
            onec_id="price-type-opt1",
            onec_name="Оптовая цена 1",
            product_field="opt1_price",
            is_active=True,
        )

        # Инициализируем процессор
        self.processor = VariantImportProcessor(
            session_id=self.session.pk,
            batch_size=500,
        )

        # Создаём временные XML файлы
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        """Очистка"""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_xml_file(self, content: str, filename: str) -> str:
        """Создаёт временный XML файл"""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    def test_process_product_from_goods_creates_product(self):
        """AC1: goods.xml создаёт Product с базовой информацией"""
        goods_data = {
            "id": "test-product-001",
            "name": "Тестовый товар",
            "description": "Описание товара",
            "category_id": "test-category-001",
        }

        product = self.processor.process_product_from_goods(goods_data)

        assert product is not None
        assert product.onec_id == "test-product-001"
        assert product.name == "Тестовый товар"
        assert product.description == "Описание товара"
        assert product.category == self.category
        assert product.is_active is False  # Неактивен до создания variants
        assert self.processor.stats["products_created"] == 1

    def test_process_product_from_goods_no_prices(self):
        """AC1: Product создаётся без цен (цены в ProductVariant)"""
        goods_data = {
            "id": "test-product-001",
            "name": "Тестовый товар",
        }

        product = self.processor.process_product_from_goods(goods_data)

        # Product не должен иметь полей цен (они удалены в Story 13.1)
        assert not hasattr(product, "retail_price") or product.retail_price is None

    def test_process_variant_from_offer_creates_variant(self):
        """AC2: offers.xml создаёт ProductVariant"""
        # Сначала создаём Product
        product = Product.objects.create(
            name="Тестовый товар",
            slug="test-product",
            onec_id="test-product-001",
            parent_onec_id="test-product-001",
            brand=self.brand,
            category=self.category,
            description="",
            is_active=False,
        )

        offer_data = {
            "id": "test-product-001#variant-001",
            "name": "Тестовый товар (42)",
            "article": "TEST-001-42",
            "characteristics": [
                {"name": "Цвет", "value": "Синий"},
                {"name": "Размер", "value": "42"},
            ],
        }

        variant = self.processor.process_variant_from_offer(offer_data)

        assert variant is not None
        assert variant.product == product
        assert variant.onec_id == "test-product-001#variant-001"
        assert variant.sku == "TEST-001-42"
        assert variant.color_name == "Синий"
        assert variant.size_value == "42"
        assert variant.is_active is True
        assert self.processor.stats["variants_created"] == 1

    def test_process_variant_from_offer_skips_orphan(self):
        """AC3: <Предложение> без parent пропускается с warning"""
        offer_data = {
            "id": "orphan-product#variant-orphan",
            "name": "Вариант без родителя",
            "article": "ORPHAN-001",
        }

        variant = self.processor.process_variant_from_offer(offer_data)

        assert variant is None
        assert self.processor.stats["skipped"] == 1

    def test_process_variant_extracts_characteristics(self):
        """AC4: Характеристики извлекаются из <ХарактеристикиТовара>"""
        product = Product.objects.create(
            name="Тестовый товар",
            slug="test-product-2",
            onec_id="test-product-002",
            parent_onec_id="test-product-002",
            brand=self.brand,
            category=self.category,
            description="",
        )

        offer_data = {
            "id": "test-product-002#variant-001",
            "name": "Товар красный XL",
            "article": "TEST-002-XL",
            "characteristics": [
                {"name": "Цвет", "value": "Красный"},
                {"name": "Размер", "value": "XL"},
            ],
        }

        variant = self.processor.process_variant_from_offer(offer_data)

        assert variant.color_name == "Красный"
        assert variant.size_value == "XL"

    def test_create_default_variants(self):
        """AC5: Создание default variants для товаров без вариантов"""
        # Создаём Product без вариантов
        product = Product.objects.create(
            name="Товар без вариантов",
            slug="product-no-variants",
            onec_id="no-variants-001",
            parent_onec_id="no-variants-001",
            brand=self.brand,
            category=self.category,
            description="",
            is_active=True,
        )

        count = self.processor.create_default_variants()

        assert count == 1
        assert ProductVariant.objects.filter(product=product).count() == 1

        variant = ProductVariant.objects.get(product=product)
        assert variant.color_name == ""
        assert variant.size_value == ""
        assert variant.retail_price == Decimal("0")

    def test_update_variant_prices(self):
        """AC7: prices.xml обновляет цены ProductVariant"""
        # Создаём Product и Variant
        product = Product.objects.create(
            name="Тестовый товар",
            slug="test-product-prices",
            onec_id="test-product-001",
            parent_onec_id="test-product-001",
            brand=self.brand,
            category=self.category,
            description="",
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="TEST-001-42",
            onec_id="test-product-001#variant-001",
            retail_price=Decimal("0"),
        )

        price_data = {
            "id": "test-product-001#variant-001",
            "prices": [
                {"price_type_id": "price-type-retail", "value": Decimal("1500.00")},
                {"price_type_id": "price-type-opt1", "value": Decimal("1200.00")},
            ],
        }

        result = self.processor.update_variant_prices(price_data)

        assert result is True
        variant.refresh_from_db()
        assert variant.retail_price == Decimal("1500.00")
        assert variant.opt1_price == Decimal("1200.00")
        assert self.processor.stats["prices_updated"] == 1

    def test_update_variant_stock(self):
        """AC8: rests.xml обновляет остатки ProductVariant"""
        # Создаём Product и Variant
        product = Product.objects.create(
            name="Тестовый товар",
            slug="test-product-stock",
            onec_id="test-product-001",
            parent_onec_id="test-product-001",
            brand=self.brand,
            category=self.category,
            description="",
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="TEST-001-42",
            onec_id="test-product-001#variant-001",
            retail_price=Decimal("0"),
            stock_quantity=0,
        )

        # Первый склад
        rest_data_1 = {
            "id": "test-product-001#variant-001",
            "warehouse_id": "warehouse-001",
            "quantity": 50,
        }
        self.processor.update_variant_stock(rest_data_1)

        # Второй склад (суммируется)
        rest_data_2 = {
            "id": "test-product-001#variant-001",
            "warehouse_id": "warehouse-002",
            "quantity": 30,
        }
        self.processor.update_variant_stock(rest_data_2)

        variant.refresh_from_db()
        assert variant.stock_quantity == 80  # 50 + 30
        assert self.processor.stats["stocks_updated"] == 2

    def test_batch_processing(self):
        """AC9/NFR4: Batch processing по 500 записей"""
        # Создаём Product
        product = Product.objects.create(
            name="Тестовый товар batch",
            slug="test-product-batch",
            onec_id="batch-product-001",
            parent_onec_id="batch-product-001",
            brand=self.brand,
            category=self.category,
            description="",
            is_active=True,
        )

        # Проверяем что batch_size установлен
        assert self.processor.batch_size == 500

        # Создаём несколько Products без вариантов для теста batch
        for i in range(10):
            Product.objects.create(
                name=f"Batch Product {i}",
                slug=f"batch-product-{i}",
                onec_id=f"batch-{i}",
                parent_onec_id=f"batch-{i}",
                brand=self.brand,
                category=self.category,
                description="",
                is_active=True,
            )

        count = self.processor.create_default_variants()
        assert count == 11  # 10 + 1 original

    def test_full_import_workflow(self):
        """Integration test: полный workflow импорта"""
        parser = XMLDataParser()

        # Шаг 1: Создаём Product из goods.xml
        goods_file = self._create_xml_file(SAMPLE_GOODS_XML, "goods.xml")
        goods_data = parser.parse_goods_xml(goods_file)

        for goods_item in goods_data:
            self.processor.process_product_from_goods(goods_item)

        assert Product.objects.count() == 2
        assert self.processor.stats["products_created"] == 2

        # Шаг 2: Создаём ProductVariant из offers.xml
        offers_file = self._create_xml_file(SAMPLE_OFFERS_XML, "offers.xml")
        offers_data = parser.parse_offers_xml(offers_file)

        for offer_item in offers_data:
            self.processor.process_variant_from_offer(offer_item)

        # 2 варианта создано, 1 пропущен (orphan)
        assert ProductVariant.objects.count() == 2
        assert self.processor.stats["variants_created"] == 2
        assert self.processor.stats["skipped"] == 1

        # Шаг 3: Создаём default variants
        count = self.processor.create_default_variants()
        # Один Product (test-product-002) без вариантов
        assert count == 1
        assert ProductVariant.objects.count() == 3

        # Шаг 4: Обновляем цены
        prices_file = self._create_xml_file(SAMPLE_PRICES_XML, "prices.xml")
        prices_data = parser.parse_prices_xml(prices_file)

        for price_item in prices_data:
            self.processor.update_variant_prices(price_item)

        variant = ProductVariant.objects.get(onec_id="test-product-001#variant-001")
        assert variant.retail_price == Decimal("1500.00")
        assert variant.opt1_price == Decimal("1200.00")

        # Шаг 5: Обновляем остатки
        rests_file = self._create_xml_file(SAMPLE_RESTS_XML, "rests.xml")
        rests_data = parser.parse_rests_xml(rests_file)

        for rest_item in rests_data:
            self.processor.update_variant_stock(rest_item)

        variant.refresh_from_db()
        assert variant.stock_quantity == 80  # 50 + 30

        # Финализация
        self.processor.finalize_session(status=ImportSession.ImportStatus.COMPLETED)

        self.session.refresh_from_db()
        assert self.session.status == ImportSession.ImportStatus.COMPLETED


# ============================================================================
# Integration Verification tests
# ============================================================================


@pytest.mark.django_db
class TestIntegrationVerification(TestCase):
    """Тесты Integration Verification (IV1, IV2, IV3)"""

    def test_iv1_brands_categories_unchanged(self):
        """IV1: Импорт брендов и категорий работает без изменений

        Note: Методы process_categories и process_brands перенесены
        в VariantImportProcessor в Story 27.1
        """
        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
        )

        processor = VariantImportProcessor(session_id=session.pk)

        # Тест категорий
        categories_data = [
            {"id": "cat-001", "name": "Категория 1"},
            {"id": "cat-002", "name": "Категория 2", "parent_id": "cat-001"},
        ]
        result = processor.process_categories(categories_data)

        assert result["created"] == 2
        assert Category.objects.filter(onec_id="cat-001").exists()
        assert Category.objects.filter(onec_id="cat-002").exists()

        # Тест брендов
        brands_data = [
            {"id": "brand-001", "name": "Бренд 1"},
        ]
        result = processor.process_brands(brands_data)

        assert result["brands_created"] == 1
        assert Brand.objects.filter(name="Бренд 1").exists()

    def test_iv2_commerceml_compatibility(self):
        """IV2: Совместимость с CommerceML 3.1"""
        parser = XMLDataParser()

        # Проверяем что парсер корректно обрабатывает namespace
        xml_with_namespace = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">
            <Каталог>
                <Товары>
                    <Товар>
                        <Ид>test-001</Ид>
                        <Наименование>Тест</Наименование>
                    </Товар>
                </Товары>
            </Каталог>
        </КоммерческаяИнформация>
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as f:
            f.write(xml_with_namespace)
            f.flush()

            goods = parser.parse_goods_xml(f.name)

        assert len(goods) == 1
        assert goods[0]["id"] == "test-001"

        os.unlink(f.name)

    def test_iv3_logging_warnings(self):
        """IV3: Логи содержат warnings для пропущенных записей"""
        import logging

        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
        )

        processor = VariantImportProcessor(session_id=session.pk)

        # Захватываем логи
        with self.assertLogs("import_products", level="WARNING") as cm:
            # Пытаемся создать variant без parent
            offer_data = {
                "id": "nonexistent-parent#variant-001",
                "name": "Orphan variant",
                "article": "ORPHAN",
            }
            processor.process_variant_from_offer(offer_data)

        # Проверяем что warning был залогирован
        assert any("parent Product not found" in log for log in cm.output)


# ============================================================================
# AC6: Hybrid Images Tests (TEST-GAP-1)
# ============================================================================


@pytest.mark.integration
@pytest.mark.django_db(transaction=True)
class TestHybridImagesLogic(TransactionTestCase):
    """
    Integration тесты для AC6 - Hybrid images логика
    - base_images fallback через effective_images()
    - Копирование изображений в products/base/ и products/variants/
    - main_image + gallery_images логика
    """

    def setUp(self):
        """Настройка тестовых данных"""
        # Создание Brand
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand", is_active=True)

        # Создание Category
        self.category = Category.objects.create(name="Test Category", slug="test-category", is_active=True)

        # Создание ImportSession
        self.session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.STARTED,
        )

        # Создание процессора
        self.processor = VariantImportProcessor(session_id=self.session.pk)
        # Отключаем проверку размера изображений для тестов
        # (иначе dummy jpg пропускается)
        self.processor.MIN_IMAGE_SIZE_BYTES = 0

    def _create_xml_file(self, content: str, filename: str) -> str:
        """Создание временного XML файла"""
        temp_dir = tempfile.mkdtemp()
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        return file_path

    def test_base_images_saved_to_product(self):
        """
        Тест: base_images сохраняются в Product.base_images
        """
        # Создаем Product напрямую с base_images
        product = Product.objects.create(
            onec_id="product-with-base-images",
            name="Товар с base images",
            slug="product-with-base-images",
            brand=self.brand,
            category=self.category,
            is_active=True,
            base_images=[
                "products/base/goods/image1.jpg",
                "products/base/goods/image2.jpg",
            ],
        )

        # Проверка: Product создан
        assert product is not None

        # Проверка: base_images содержит 2 изображения
        assert product.base_images is not None
        assert len(product.base_images) == 2
        assert "products/base/goods/image1.jpg" in product.base_images[0]
        assert "products/base/goods/image2.jpg" in product.base_images[1]

    def test_variant_images_saved_to_main_and_gallery(self):
        """
        Тест: Изображения варианта сохраняются в main_image и gallery_images
        """
        # Создаем Product
        product = Product.objects.create(
            onec_id="product-001",
            name="Test Product",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )

        # Создаем временные файлы изображений
        temp_dir = tempfile.mkdtemp()
        variant_dir = os.path.join(temp_dir, "offers")
        os.makedirs(variant_dir, exist_ok=True)

        dummy_jpg = (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
            b"\xff\xdb\x00C\x00\x03\x02\x02\x02\x02\x02\x03\x02\x02\x02\x03\x03\x03"
            b"\x03\x04\x06\x04\x04\x04\x04\x04\x08\x06\x06\x05\x06\t\x08\n\n\t\x08"
            b"\t\t\n\x0c\x0f\x0c\n\x0b\x0e\x0b\t\t\r\x11\r\x0e\x0f\x10\x10\x11\x10"
            b"\n\x0c\x12\x13\x12\x10\x13\x0f\x10\x10\x10\xff\xc9\x00\x0b\x08\x00\x01"
            b"\x00\x01\x01\x01\x11\x00\xff\xcc\x00\x06\x00\x10\x10\x05\xff\xda\x00"
            b"\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
        )

        variant_img1 = os.path.join(variant_dir, "variant1.jpg")
        variant_img2 = os.path.join(variant_dir, "variant2.jpg")
        variant_img3 = os.path.join(variant_dir, "variant3.jpg")

        for img_path in [variant_img1, variant_img2, variant_img3]:
            with open(img_path, "wb") as f:
                f.write(dummy_jpg)

        # Создаем offer_data с изображениями
        offer_data = {
            "id": "product-001#variant-001",
            "name": "Test Variant Red",
            "article": "VARIANT-001",
            "characteristics": [
                {"name": "Цвет", "value": "Красный"},
                {"name": "Размер", "value": "M"},
            ],
            "images": [
                "offers/variant1.jpg",
                "offers/variant2.jpg",
                "offers/variant3.jpg",
            ],
        }

        # Обработка варианта
        variant = self.processor.process_variant_from_offer(offer_data, base_dir=temp_dir, skip_images=False)

        # Проверка: variant создан
        assert variant is not None
        assert variant.color_name == "Красный"
        assert variant.size_value == "M"

        # Проверка: main_image установлен (первое изображение)
        assert variant.main_image is not None
        assert "products/variants/offers/variant1.jpg" in str(variant.main_image)

        # Проверка: gallery_images содержит остальные изображения
        assert variant.gallery_images is not None
        assert len(variant.gallery_images) == 2
        assert "products/variants/offers/variant2.jpg" in str(variant.gallery_images[0])
        assert "products/variants/offers/variant3.jpg" in str(variant.gallery_images[1])

    def test_default_variant_without_images_uses_base_images(self):
        """
        Тест: Default variant без своих изображений использует
        base_images через effective_images()
        """
        # Создаем Product с base_images
        product = Product.objects.create(
            onec_id="product-with-base",
            name="Product with base images",
            slug="product-with-base",
            brand=self.brand,
            category=self.category,
            is_active=True,
            base_images=[
                "products/base/image1.jpg",
                "products/base/image2.jpg",
            ],
        )

        # Создаем default variant
        count = self.processor.create_default_variants()
        assert count == 1

        # Получаем созданный variant
        variant = ProductVariant.objects.get(product=product)

        # Проверка: variant не имеет своих изображений
        assert variant.main_image is None or variant.main_image == ""
        assert variant.gallery_images is None or len(variant.gallery_images) == 0

        # Проверка: effective_images возвращает base_images
        effective = variant.effective_images
        assert effective is not None
        assert len(effective) == 2
        assert "products/base/image1.jpg" in effective[0]
        assert "products/base/image2.jpg" in effective[1]

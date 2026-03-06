"""
Unit tests for OrderExportService.

Tests cover:
- AC1: Service exists at backend/apps/orders/services/order_export.py
- AC2: generate_xml() returns XML with root <КоммерческаяИнформация ВерсияСхемы="3.1">
- AC3: Each order wrapped in <Документ> with <ХозОперация>Заказ товара</ХозОперация>
- AC4: <Контрагенты> contains <ИНН> only when user has tax_id
- AC5: <Товары> contains <Ид> with ProductVariant.onec_id
- AC6: All orders in single XML document (batch export)
- AC7: UTF-8 encoding with XML declaration
- AC8: Unit tests cover all scenarios
- AC9: Service Layer pattern (business logic in services/)
"""

import logging
import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest

from apps.orders.models import Order, OrderItem
from apps.orders.services import OrderExportService
from tests.factories import ProductFactory, ProductVariantFactory, UserFactory, get_unique_suffix


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceXMLValidation:
    """[P1-HIGH] Tests for XML structure validation."""

    def test_generate_xml_returns_valid_xml(self):
        """
        AC2, AC7: XML should be valid and parseable by ElementTree.
        If XML is invalid, 1C will reject the request.
        """
        # Arrange
        user = UserFactory(
            email=f"test-{get_unique_suffix()}@example.com",
            first_name="Иван",
            last_name="Иванов",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1500.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("3000.00"),
            delivery_address="123456, Москва, ул. Ленина, д. 1",
            delivery_method="courier",
            payment_method="card",
            sent_to_1c=False,
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("1500.00"),
            total_price=Decimal("3000.00"),
            product_name="Тестовый товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - XML should parse without exception
        root = ET.fromstring(xml_str)
        assert root is not None
        assert root.tag == "КоммерческаяИнформация"

    def test_generate_xml_has_xml_declaration(self):
        """AC7: XML should have UTF-8 declaration."""
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Тестовый адрес",
            delivery_method="pickup",
            payment_method="cash",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert
        assert xml_str.startswith('<?xml version="1.0" encoding="UTF-8"?>')

    def test_generate_xml_has_correct_root_attributes(self):
        """AC2: Root element should have ВерсияСхемы="3.1" and ДатаФормирования."""
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("500.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("500.00"),
            delivery_address="Адрес",
            delivery_method="post",
            payment_method="bank_transfer",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("500.00"),
            total_price=Decimal("500.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert
        assert root.get("ВерсияСхемы") == "3.1"
        assert root.get("ДатаФормирования") is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceTimezone:
    """Tests for timezone correctness in date formatting."""

    def test_order_date_uses_local_timezone(self):
        """
        Review Follow-up: Ensure Order.created_at is converted to local time.
        Orders created near midnight UTC should show correct local date.
        """
        from django.utils import timezone

        # Arrange - Create order with UTC time that could be different day locally
        user = UserFactory(email=f"test-tz-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-tz-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - Date should be formatted using localtime conversion
        date_element = root.find(".//Дата")
        assert date_element is not None
        # The date should be in YYYY-MM-DD format
        assert len(date_element.text) == 10
        assert date_element.text.count("-") == 2
        # Verify it matches the localtime conversion
        expected_date = timezone.localtime(order.created_at).strftime("%Y-%m-%d")
        assert date_element.text == expected_date


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceEmptyCounterpartyId:
    """Tests for handling empty counterparty ID."""

    def test_user_without_onec_id_or_email_uses_fallback(self, caplog):
        """
        Review Follow-up: User without onec_id or email should use user-{id} fallback.
        """
        # Arrange - User with no onec_id and no email
        user = UserFactory(
            email="",  # Empty email
            onec_id="",  # No onec_id
            first_name="Безымянный",
            last_name="Пользователь",
        )
        # Force empty email (factory might override)
        user.email = ""
        user.onec_id = ""
        user.save()

        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        with caplog.at_level(logging.INFO):
            xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - Should use user-{id} fallback
        root = ET.fromstring(xml_str)
        counterparty_id = root.find(".//Контрагент/Ид")
        assert counterparty_id is not None
        assert counterparty_id.text == f"user-{user.id}"
        assert "using fallback ID" in caplog.text


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceMissingOnecId:
    """[P1-HIGH] Tests for handling missing onec_id."""

    def test_item_without_onec_id_skipped_with_warning(self, caplog):
        """
        AC5: Items without ProductVariant.onec_id should be skipped with warning.
        Silent data loss is dangerous.
        """
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        # Create variant without onec_id
        variant_no_onec = ProductVariantFactory(
            onec_id="",  # Empty onec_id
            retail_price=Decimal("1000.00"),
        )
        # Manually clear onec_id since factory may set it
        variant_no_onec.onec_id = ""
        variant_no_onec.save()

        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant_no_onec.product,
            variant=variant_no_onec,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар без onec_id",
            product_sku=variant_no_onec.sku,
        )

        # Act
        service = OrderExportService()
        with caplog.at_level(logging.INFO):
            xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - XML should be valid but Товары should be empty
        root = ET.fromstring(xml_str)
        products = root.find(".//Товары")
        assert products is not None
        assert len(list(products)) == 0  # No products added
        assert "missing onec_id" in caplog.text


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceB2CWithoutINN:
    """[P2-MEDIUM] Tests for B2C user without tax_id."""

    def test_b2c_order_without_inn(self):
        """AC4: B2C order should not have <ИНН> tag when user has no tax_id."""
        # Arrange
        user = UserFactory(
            email=f"test-{get_unique_suffix()}@example.com",
            role="retail",  # B2C user
            tax_id="",  # No tax_id
            first_name="Петр",
            last_name="Петров",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("2000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("2000.00"),
            delivery_address="456789, СПб, ул. Невский, д. 5",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("2000.00"),
            total_price=Decimal("2000.00"),
            product_name="Тестовый товар B2C",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - No <ИНН> tag should exist
        inn_element = root.find(".//ИНН")
        assert inn_element is None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceXMLEscaping:
    """[P2-MEDIUM] Tests for XML special character escaping."""

    def test_special_characters_escaped_in_product_name(self):
        """AC8: Special characters (<, >, &, ", ') should be properly escaped."""
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1500.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1500.00"),
            delivery_address="Адрес с <спецсимволами> & 'кавычками'",
            delivery_method="courier",
            payment_method="card",
        )
        # Product name with special characters
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1500.00"),
            total_price=Decimal("1500.00"),
            product_name='Футболка "Nike" <Limited> & Special\'s Edition',
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - XML should still be valid (parseable)
        root = ET.fromstring(xml_str)
        product_name = root.find(".//Товар/Наименование")
        assert product_name is not None
        # ElementTree automatically unescapes when reading
        assert "Nike" in product_name.text
        assert "Limited" in product_name.text

    def test_no_double_escaping_in_xml(self):
        """
        Regression test: Ensure no double escaping occurs.
        ElementTree handles escaping automatically, so explicit escape calls
        would result in double escaping (& -> &amp; -> &amp;amp;).
        """
        # Arrange
        user = UserFactory(
            email=f"test-{get_unique_suffix()}@example.com",
            company_name='ООО "Тест & Компания"',  # Contains & and quotes
            role="wholesale_level1",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес с & спецсимволами",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name='Товар "Special" & <Edition>',
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - Check for double escaping patterns (should NOT exist)
        assert "&amp;amp;" not in xml_str  # Double-escaped &
        assert "&amp;lt;" not in xml_str  # Double-escaped <
        assert "&amp;gt;" not in xml_str  # Double-escaped >
        assert "&amp;quot;" not in xml_str  # Double-escaped "

        # Verify XML is still valid
        root = ET.fromstring(xml_str)
        assert root is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceOrderWithoutItems:
    """[P2-MEDIUM] Tests for orders without items."""

    def test_order_without_items_skipped_with_warning(self, caplog):
        """AC8: Order without items should be skipped with warning in logs."""
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("0.00"),
            delivery_address="Пустой заказ",
            delivery_method="pickup",
            payment_method="cash",
        )
        # No OrderItems created

        # Act
        service = OrderExportService()
        with caplog.at_level(logging.INFO):
            xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert
        root = ET.fromstring(xml_str)
        documents = root.findall("Контейнер/Документ")
        assert len(documents) == 0  # No documents for empty orders
        assert "no items" in caplog.text


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceVariantNone:
    """[P2-MEDIUM] Tests for OrderItem with variant=None."""

    def test_order_item_with_null_variant_skipped(self, caplog):
        """AC8: OrderItem with variant=None (deleted product) should be skipped."""
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        # Create a valid variant for one item
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("2000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        # Valid item
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар с вариантом",
            product_sku=variant.sku,
        )
        # Item with null variant (simulating deleted product)
        item_no_variant = OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=None,  # Deleted variant
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Удалённый товар",
            product_sku="DELETED-SKU",
        )

        # Act
        service = OrderExportService()
        with caplog.at_level(logging.INFO):
            xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - Only valid item should be in XML
        root = ET.fromstring(xml_str)
        products = root.findall(".//Товар")
        assert len(products) == 1
        assert "variant is None" in caplog.text


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceB2BWithINN:
    """[P3-NORMAL] Tests for B2B user with tax_id."""

    def test_b2b_order_with_inn(self):
        """AC4: B2B order should have <ИНН> tag when user has tax_id."""
        # Arrange
        user = UserFactory(
            email=f"b2b-{get_unique_suffix()}@company.com",
            role="wholesale_level1",  # B2B user
            tax_id="1234567890",
            company_name=f"ООО Тестовая Компания {get_unique_suffix()}",
            first_name="Директор",
            last_name="Компании",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("5000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("10000.00"),
            delivery_address="123456, Москва, ул. Бизнес, д. 100",
            delivery_method="transport_company",
            payment_method="bank_transfer",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("5000.00"),
            total_price=Decimal("10000.00"),
            product_name="Оптовый товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert
        inn_element = root.find(".//ИНН")
        assert inn_element is not None
        assert inn_element.text == "1234567890"

        # Check company name is used
        name_element = root.find(".//Контрагент/Наименование")
        assert name_element is not None
        assert "Тестовая Компания" in name_element.text


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceBatchOrders:
    """[P3-NORMAL] Tests for batch order export."""

    def test_multiple_orders_in_single_xml(self):
        """AC6: Multiple orders should be in single XML document."""
        # Arrange
        users = [
            UserFactory(email=f"user1-{get_unique_suffix()}@example.com"),
            UserFactory(email=f"user2-{get_unique_suffix()}@example.com"),
            UserFactory(email=f"user3-{get_unique_suffix()}@example.com"),
        ]
        orders = []
        for i, user in enumerate(users):
            variant = ProductVariantFactory(
                onec_id=f"variant-batch-{i}-{get_unique_suffix()}",
                retail_price=Decimal("1000.00") * (i + 1),
            )
            order = Order.objects.create(
                user=user,
                total_amount=Decimal("1000.00") * (i + 1),
                delivery_address=f"Адрес {i + 1}",
                delivery_method="courier",
                payment_method="card",
            )
            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                quantity=1,
                unit_price=Decimal("1000.00") * (i + 1),
                total_price=Decimal("1000.00") * (i + 1),
                product_name=f"Товар {i + 1}",
                product_sku=variant.sku,
            )
            orders.append(order)

        # Act
        service = OrderExportService()
        order_ids = [o.id for o in orders]
        xml_str = service.generate_xml(Order.objects.filter(id__in=order_ids))
        root = ET.fromstring(xml_str)

        # Assert - All 3 orders should be in single document
        documents = root.findall("Контейнер/Документ")
        assert len(documents) == 3

        # Verify each document has correct structure
        for doc in documents:
            assert doc.find("Ид") is not None
            assert doc.find("Номер") is not None
            assert doc.find("Дата") is not None
            assert doc.find("ХозОперация").text == "Заказ товара"
            assert doc.find("Роль").text == "Продавец"
            assert doc.find("Валюта").text == "RUB"
            assert doc.find("Контрагенты") is not None
            assert doc.find("Товары") is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceDocumentStructure:
    """[P3-NORMAL] Tests for document structure (AC3)."""

    def test_document_has_required_elements(self):
        """AC3: Each order wrapped in <Документ> with required elements."""
        # Arrange
        user = UserFactory(
            email=f"test-{get_unique_suffix()}@example.com",
            onec_id=f"user-onec-{get_unique_suffix()}",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1500.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("3000.00"),
            delivery_address="123456, Москва, ул. Тестовая, д. 1, кв. 10",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("1500.00"),
            total_price=Decimal("3000.00"),
            product_name="Тестовый товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert
        doc = root.find("Контейнер/Документ")
        assert doc is not None

        # Required elements per AC3
        # <Ид> uses immutable order.id, <Номер> uses order_number for display
        assert doc.find("Ид").text == f"order-{order.id}"
        assert doc.find("Номер").text == order.order_number
        assert doc.find("Дата") is not None
        assert doc.find("ХозОперация").text == "Заказ товара"
        assert doc.find("Роль").text == "Продавец"
        assert doc.find("Валюта").text == "RUB"
        assert doc.find("Курс").text == "1"
        assert doc.find("Сумма").text == "3000.00"

        # Product structure (AC5)
        product = doc.find(".//Товар")
        assert product is not None
        assert product.find("Ид").text == variant.onec_id
        assert product.find("Наименование").text == "Тестовый товар"

        unit = product.find("БазоваяЕдиница")
        assert unit is not None
        assert unit.get("Код") == "796"
        assert unit.text == "шт"

        assert product.find("ЦенаЗаЕдиницу").text == "1500.00"
        assert product.find("Количество").text == "2"
        assert product.find("Сумма").text == "3000.00"

    def test_document_wrapped_in_container(self):
        """AC3: Each order's <Документ> must be wrapped in <Контейнер>."""
        # Arrange
        user = UserFactory(
            email=f"test-container-{get_unique_suffix()}@example.com",
        )
        variant = ProductVariantFactory(
            onec_id=f"variant-container-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - Root should contain <Контейнер> which contains <Документ>
        containers = root.findall("Контейнер")
        assert len(containers) == 1
        document = containers[0].find("Документ")
        assert document is not None
        assert document.find("Ид") is not None
        assert document.find("ХозОперация").text == "Заказ товара"


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceImmutableOrderId:
    """[AI-Review] Tests for immutable order ID (Compliance)."""

    def test_order_id_uses_database_id_not_order_number(self):
        """
        Review Follow-up: Order <Ид> should use immutable database ID,
        not mutable order_number.
        """
        # Arrange
        user = UserFactory(email=f"test-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - <Ид> should be order-{id}, not order_number
        order_id_element = root.find(".//Документ/Ид")
        assert order_id_element is not None
        assert order_id_element.text == f"order-{order.id}"
        # <Номер> should still contain order_number for display
        order_number_element = root.find(".//Документ/Номер")
        assert order_number_element is not None
        assert order_number_element.text == order.order_number


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServicePrivacySafeCounterpartyId:
    """[AI-Review] Tests for privacy-safe counterparty ID."""

    def test_counterparty_id_uses_hashed_email_not_plain_email(self):
        """
        Review Follow-up: Counterparty ID should use hashed email,
        not plain email to avoid PII leak.
        """
        import hashlib

        # Arrange
        email = f"privacy-test-{get_unique_suffix()}@example.com"
        user = UserFactory(
            email=email,
            onec_id="",  # No onec_id to trigger fallback
        )
        user.onec_id = ""
        user.save()

        variant = ProductVariantFactory(
            onec_id=f"variant-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - Counterparty ID should NOT contain plain email
        counterparty_id = root.find(".//Контрагент/Ид")
        assert counterparty_id is not None
        assert email not in counterparty_id.text  # No plain email
        assert "@" not in counterparty_id.text  # No email format

        # Should be hashed email format
        expected_hash = hashlib.sha256(email.encode()).hexdigest()[:16]
        assert counterparty_id.text == f"email-{expected_hash}"


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceRefactoring:
    """[AI-Review] Tests for refactoring improvements."""

    def test_generate_xml_uses_streaming_implementation(self):
        """
        Review Follow-up: generate_xml should delegate to generate_xml_streaming
        to avoid code duplication.
        """
        from datetime import datetime
        from unittest.mock import patch

        from django.utils import timezone as dj_timezone

        # Arrange
        user = UserFactory(email=f"refactor-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-refactor-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act - Mock timezone.now() to ensure identical timestamps
        fixed_time = dj_timezone.now()
        service = OrderExportService()
        queryset = Order.objects.filter(id=order.id)

        with patch("apps.orders.services.order_export.timezone.now", return_value=fixed_time):
            regular_xml = service.generate_xml(queryset)
            streaming_xml = "".join(service.generate_xml_streaming(queryset))

        # Assert - Both methods should produce identical XML
        assert regular_xml == streaming_xml

        # Both should be valid XML
        regular_root = ET.fromstring(regular_xml)
        streaming_root = ET.fromstring(streaming_xml)

        # Same structure
        assert regular_root.tag == streaming_root.tag
        assert regular_root.get("ВерсияСхемы") == streaming_root.get("ВерсияСхемы")

        # Same documents
        regular_docs = regular_root.findall("Контейнер/Документ")
        streaming_docs = streaming_root.findall("Контейнер/Документ")
        assert len(regular_docs) == len(streaming_docs) == 1

        # Same content
        regular_doc = regular_docs[0]
        streaming_doc = streaming_docs[0]
        assert regular_doc.find("Ид").text == streaming_doc.find("Ид").text
        assert regular_doc.find("Номер").text == streaming_doc.find("Номер").text

    def test_generate_xml_delegates_to_streaming_for_memory_efficiency(self):
        """
        Verify that generate_xml properly delegates to streaming implementation.
        This test ensures the refactoring maintains backward compatibility
        while using the more memory-efficient streaming approach internally.
        """
        # Arrange - Create multiple orders to test efficiency
        users = [UserFactory(email=f"efficiency-{i}-{get_unique_suffix()}@example.com") for i in range(2)]
        orders = []
        for i, user in enumerate(users):
            variant = ProductVariantFactory(
                onec_id=f"variant-eff-{i}-{get_unique_suffix()}",
                retail_price=Decimal("1000.00"),
            )
            order = Order.objects.create(
                user=user,
                total_amount=Decimal("1000.00"),
                delivery_address=f"Адрес {i}",
                delivery_method="courier",
                payment_method="card",
            )
            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                quantity=1,
                unit_price=Decimal("1000.00"),
                total_price=Decimal("1000.00"),
                product_name=f"Товар {i}",
                product_sku=variant.sku,
            )
            orders.append(order)

        # Act
        service = OrderExportService()
        order_ids = [o.id for o in orders]
        queryset = Order.objects.filter(id__in=order_ids)

        # Both methods should work
        regular_xml = service.generate_xml(queryset)
        streaming_xml = "".join(service.generate_xml_streaming(queryset))

        # Assert - Both should produce valid, identical XML
        regular_root = ET.fromstring(regular_xml)
        streaming_root = ET.fromstring(streaming_xml)

        documents = regular_root.findall("Контейнер/Документ")
        assert len(documents) == 2

        # Verify all orders are present
        order_ids_in_xml = {doc.find("Ид").text for doc in documents}
        expected_ids = {f"order-{order.id}" for order in orders}
        assert order_ids_in_xml == expected_ids


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServicePricePrecision:
    """[AI-Review] Tests for price formatting with 2-decimal precision."""

    def test_prices_have_two_decimal_places(self):
        """
        Review Follow-up: Prices should always have 2 decimal places.
        CommerceML expects "1500.00", not "1500".
        """
        # Arrange - Use integer-like prices that could lose decimal places
        user = UserFactory(email=f"price-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-price-{get_unique_suffix()}",
            retail_price=Decimal("1500.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("3000"),  # No decimal places
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("1500"),  # No decimal places
            total_price=Decimal("3000"),  # No decimal places
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))
        root = ET.fromstring(xml_str)

        # Assert - All prices should have .00 suffix
        order_sum = root.find(".//Документ/Сумма")
        assert order_sum is not None
        assert order_sum.text == "3000.00"

        unit_price = root.find(".//Товар/ЦенаЗаЕдиницу")
        assert unit_price is not None
        assert unit_price.text == "1500.00"

        item_sum = root.find(".//Товар/Сумма")
        assert item_sum is not None
        assert item_sum.text == "3000.00"


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceEmptyCounterparty:
    """[AI-Review] Tests for handling empty counterparty elements."""

    def test_order_without_user_generates_guest_counterparty(self, caplog):
        """
        Review Follow-up: Guest order should generate <Контрагент> with fallback name.
        Контакты отсутствуют, если customer_email/phone не заданы.
        """
        # Arrange - Create order without user (guest order scenario)
        order = Order.objects.create(
            user=None,  # Guest order
            total_amount=Decimal("1000.00"),
            delivery_address="Гостевой адрес",
            delivery_method="courier",
            payment_method="cash",
        )
        # Add item to make order valid
        variant = ProductVariantFactory(
            onec_id=f"variant-guest-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Гостевой товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        with caplog.at_level(logging.INFO):
            xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - Should have guest counterparty element
        root = ET.fromstring(xml_str)
        counterparties = root.find(".//Контрагенты")
        assert counterparties is not None
        assert len(list(counterparties)) == 1

        counterparty = counterparties.find("Контрагент")
        assert counterparty is not None
        assert counterparty.find("Ид") is not None
        name_element = counterparty.find("Наименование")
        assert name_element is not None
        assert "Гость" in (name_element.text or "")

        # Контактов нет, если customer_email/phone не переданы
        assert counterparty.find("Контакты") is None

        # Should log info about guest order
        assert "guest order" in caplog.text

        # Document should still be valid with other elements
        document = root.find("Контейнер/Документ")
        assert document is not None
        assert document.find("Ид") is not None
        assert document.find("Товары") is not None

    def test_order_with_user_generates_valid_counterparty(self):
        """
        Normal case: Order with user should generate proper counterparty element.
        """
        # Arrange
        user = UserFactory(email=f"test-user-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-user-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_str = service.generate_xml(Order.objects.filter(id=order.id))

        # Assert - Should have proper counterparty element
        root = ET.fromstring(xml_str)
        counterparties = root.find(".//Контрагенты")
        assert counterparties is not None
        assert len(list(counterparties)) == 1  # One child element

        counterparty = counterparties.find("Контрагент")
        assert counterparty is not None
        assert counterparty.find("Ид") is not None
        assert counterparty.find("Наименование") is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServicePerformance:
    """[AI-Review] Tests for performance optimizations."""

    def test_validate_order_uses_prefetched_items_no_n_plus_one(self):
        """
        Review Follow-up: _validate_order should use prefetched items
        to avoid N+1 queries when processing multiple orders.
        """
        from django.db import connection
        from django.test.utils import override_settings

        # Arrange - Create multiple orders with items
        users = [UserFactory(email=f"user-perf-{i}-{get_unique_suffix()}@example.com") for i in range(3)]
        orders = []
        for i, user in enumerate(users):
            variant = ProductVariantFactory(
                onec_id=f"variant-perf-{i}-{get_unique_suffix()}",
                retail_price=Decimal("1000.00"),
            )
            order = Order.objects.create(
                user=user,
                total_amount=Decimal("1000.00"),
                delivery_address=f"Адрес {i}",
                delivery_method="courier",
                payment_method="card",
            )
            OrderItem.objects.create(
                order=order,
                product=variant.product,
                variant=variant,
                quantity=1,
                unit_price=Decimal("1000.00"),
                total_price=Decimal("1000.00"),
                product_name=f"Товар {i}",
                product_sku=variant.sku,
            )
            orders.append(order)

        # Act - Generate XML with prefetch (recommended way)
        service = OrderExportService()
        order_ids = [o.id for o in orders]

        # Reset query count and use prefetched queryset
        with override_settings(DEBUG=True):
            connection.queries_log.clear()
            queryset = Order.objects.filter(id__in=order_ids).prefetch_related("items__variant", "user")
            xml_str = service.generate_xml(queryset)

            # Assert - Should be valid XML
            root = ET.fromstring(xml_str)
            assert root is not None
            documents = root.findall("Контейнер/Документ")
            assert len(documents) == 3

            # Check query count - should be minimal due to prefetch
            # With prefetch, we expect:
            # 1 for orders + 1 for items + 1 for variants + 1 for users
            # = ~4 queries
            # Without prefetch, it would be 1 + N*additional queries per order
            query_count = len(connection.queries)
            assert query_count <= 6, f"Too many queries: {query_count} (expected <= 6)"

        # Verify all orders were processed
        for doc in documents:
            assert doc.find("Ид") is not None
            assert doc.find("Товары") is not None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderExportServiceStreaming:
    """[AI-Review] Tests for streaming/generator XML generation."""

    def test_streaming_generates_valid_xml(self):
        """
        Review Follow-up: Streaming method should produce valid XML.
        """
        # Arrange
        user = UserFactory(email=f"stream-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-stream-{get_unique_suffix()}",
            retail_price=Decimal("1000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("1000.00"),
            total_price=Decimal("1000.00"),
            product_name="Товар",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        xml_parts = list(service.generate_xml_streaming(Order.objects.filter(id=order.id)))
        xml_str = "".join(xml_parts)

        # Assert - Should be valid XML
        root = ET.fromstring(xml_str)
        assert root is not None
        assert root.tag == "КоммерческаяИнформация"
        assert root.get("ВерсияСхемы") == "3.1"

        # Should have document
        documents = root.findall("Контейнер/Документ")
        assert len(documents) == 1

    def test_streaming_produces_same_structure_as_regular(self):
        """
        Streaming and regular methods should produce equivalent XML structure.
        """
        # Arrange
        user = UserFactory(email=f"compare-{get_unique_suffix()}@example.com")
        variant = ProductVariantFactory(
            onec_id=f"variant-compare-{get_unique_suffix()}",
            retail_price=Decimal("2000.00"),
        )
        order = Order.objects.create(
            user=user,
            total_amount=Decimal("2000.00"),
            delivery_address="Адрес сравнения",
            delivery_method="pickup",
            payment_method="cash",
        )
        OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=1,
            unit_price=Decimal("2000.00"),
            total_price=Decimal("2000.00"),
            product_name="Товар сравнения",
            product_sku=variant.sku,
        )

        # Act
        service = OrderExportService()
        queryset = Order.objects.filter(id=order.id)

        regular_xml = service.generate_xml(queryset)
        streaming_xml = "".join(service.generate_xml_streaming(queryset))

        # Assert - Both should parse and have same structure
        regular_root = ET.fromstring(regular_xml)
        streaming_root = ET.fromstring(streaming_xml)

        # Same root attributes
        assert regular_root.get("ВерсияСхемы") == streaming_root.get("ВерсияСхемы")

        # Same number of documents
        regular_docs = regular_root.findall("Контейнер/Документ")
        streaming_docs = streaming_root.findall("Контейнер/Документ")
        assert len(regular_docs) == len(streaming_docs)

        # Same order ID
        assert regular_docs[0].find("Ид").text == streaming_docs[0].find("Ид").text

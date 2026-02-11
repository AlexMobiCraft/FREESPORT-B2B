"""Тесты для моделей товаров FREESPORT Platform"""

import time
import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from apps.products.models import Brand, Category, Product
from tests.factories import BrandFactory, CategoryFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestBrandModel(TestCase):
    """Тесты модели Brand"""

    def test_brand_creation(self):
        """Тест создания бренда"""
        brand = BrandFactory.create(name="Nike")

        assert brand.name == "Nike"
        assert brand.is_active is True
        assert brand.slug is not None
        assert str(brand) == "Nike"

    def test_brand_slug_generation(self):
        """Тест автогенерации slug"""
        brand = BrandFactory.build(name="Adidas Russia")
        brand.save()

        assert brand.slug == "adidas-russia"

    def test_brand_unique_name(self):
        """Тест уникальности названия бренда"""
        test_brand_name = "Puma"
        BrandFactory.create(name=test_brand_name)

        with pytest.raises(IntegrityError):
            BrandFactory.create(name=test_brand_name)

    def test_brand_meta_configuration(self):
        """Тест настроек Meta класса"""
        assert Brand._meta.verbose_name == "Бренд"
        assert Brand._meta.verbose_name_plural == "Бренды"
        assert Brand._meta.db_table == "brands"


@pytest.mark.django_db
class TestCategoryModel:
    """Тесты модели Category"""

    def test_category_creation(self):
        """Тест создания категории"""
        category = CategoryFactory.create(name="Футбол")

        assert category.name == "Футбол"
        assert category.is_active is True
        assert category.parent is None
        assert str(category) == "Футбол"

    def test_category_hierarchy(self):
        """Тест иерархии категорий"""
        parent = CategoryFactory.create(name="Спорт")
        child = CategoryFactory.create(name="Футбол", parent=parent)

        assert child.parent == parent
        assert str(child) == "Спорт > Футбол"
        assert child.full_name == "Спорт > Футбол"

    def test_category_deep_hierarchy(self):
        """Тест глубокой иерархии категорий"""
        root = CategoryFactory.create(name="Спорт")
        level1 = CategoryFactory.create(name="Командные игры", parent=root)
        level2 = CategoryFactory.create(name="Футбол", parent=level1)

        assert level2.full_name == "Спорт > Командные игры > Футбол"

    def test_category_ordering(self):
        """Тест сортировки категорий"""
        cat1 = CategoryFactory.create(name="Б", sort_order=2)
        cat2 = CategoryFactory.create(name="А", sort_order=1)

        categories = list(Category.objects.all())
        assert categories[0] == cat2  # Сортировка по sort_order
        assert categories[1] == cat1


@pytest.mark.django_db
class TestProductModel:
    """Тесты модели Product"""

    def test_product_creation(self):
        """Тест создания товара"""
        product = ProductFactory.create(name="Футбольный мяч Nike", retail_price=Decimal("2500.00"))

        assert product.name == "Футбольный мяч Nike"
        assert product.is_active is True

        # Цены и остатки теперь в ProductVariant
        variant = product.variants.first()
        assert variant is not None
        assert variant.retail_price == Decimal("2500.00")
        assert variant.stock_quantity >= 0
        assert str(product) == product.name


class ProductComputedPropertiesTest(TestCase):
    """
    Тесты для вычисляемых свойств модели ProductVariant.
    Цены, остатки и computed properties находятся в ProductVariant, не в Product.
    """

    def setUp(self):
        """Настройка тестовых данных."""
        from decimal import Decimal

        from apps.products.models import ProductVariant

        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            min_order_quantity=1,
            is_active=True,
        )
        # Цены и остатки находятся в ProductVariant
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="TEST-SKU-001",
            onec_id="TEST-1C-001",
            retail_price=Decimal("100.00"),
            stock_quantity=20,
            reserved_quantity=5,
        )

    def test_available_quantity(self):
        """Тест правильности расчета доступного количества."""
        self.assertEqual(self.variant.available_quantity, 15)

    def test_can_be_ordered_when_available(self):
        """Тест, что товар можно заказать, когда он доступен."""
        self.assertTrue(self.variant.can_be_ordered)

    def test_cannot_be_ordered_when_stock_is_fully_reserved(self):
        """Тест, что товар нельзя заказать, если все зарезервировано."""
        self.variant.reserved_quantity = 20
        self.variant.save()
        self.assertFalse(self.variant.can_be_ordered)
        self.assertEqual(self.variant.available_quantity, 0)

    def test_cannot_be_ordered_when_inactive(self):
        """Тест, что неактивный товар (Product) нельзя заказать."""
        self.product.is_active = False
        self.product.save()
        self.assertFalse(self.variant.can_be_ordered)

    def test_cannot_be_ordered_if_available_is_less_than_min_order(self):
        """Тест, что товар нельзя заказать, если доступно меньше минимальной партии."""
        self.product.min_order_quantity = 20
        self.product.save()
        self.assertFalse(self.variant.can_be_ordered)

    def test_product_pricing_for_different_roles(self):
        """Тест ценообразования для разных ролей пользователей"""
        product = ProductFactory.create(
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            opt2_price=Decimal("800.00"),
            opt3_price=Decimal("700.00"),
            trainer_price=Decimal("850.00"),
            federation_price=Decimal("750.00"),
        )

        # Получаем вариант товара - цены теперь в ProductVariant
        variant = product.variants.first()

        # Тест для разных ролей пользователей
        retail_user = UserFactory.create(role="retail")
        opt1_user = UserFactory.create(role="wholesale_level1")
        opt2_user = UserFactory.create(role="wholesale_level2")
        opt3_user = UserFactory.create(role="wholesale_level3")
        trainer_user = UserFactory.create(role="trainer")
        federation_user = UserFactory.create(role="federation_rep")

        assert variant.get_price_for_user(retail_user) == Decimal("1000.00")
        assert variant.get_price_for_user(opt1_user) == Decimal("900.00")
        assert variant.get_price_for_user(opt2_user) == Decimal("800.00")
        assert variant.get_price_for_user(opt3_user) == Decimal("700.00")
        assert variant.get_price_for_user(trainer_user) == Decimal("850.00")
        assert variant.get_price_for_user(federation_user) == Decimal("750.00")

    def test_product_price_fallback_to_retail(self):
        """Тест возврата к розничной цене если оптовая не указана"""
        product = ProductFactory.create(
            retail_price=Decimal("1000.00"),
            opt1_price=None,  # Не указана
            opt2_price=Decimal("800.00"),
        )

        # Получаем вариант товара
        variant = product.variants.first()

        opt1_user = UserFactory.create(role="wholesale_level1")
        opt2_user = UserFactory.create(role="wholesale_level2")

        assert variant.get_price_for_user(opt1_user) == Decimal("1000.00")  # Fallback
        assert variant.get_price_for_user(opt2_user) == Decimal("800.00")

    def test_product_price_for_anonymous_user(self):
        """Тест цены для анонимного пользователя"""
        product = ProductFactory.create(retail_price=Decimal("1000.00"))

        # Получаем вариант товара
        variant = product.variants.first()

        assert variant.get_price_for_user(None) == Decimal("1000.00")

    def test_product_stock_properties(self):
        """Тест свойств наличия товара (проверяются через ProductVariant)"""
        # Товар в наличии
        in_stock_product = ProductFactory.create(stock_quantity=10, is_active=True)
        in_stock_variant = in_stock_product.variants.first()
        assert in_stock_variant.is_in_stock is True
        assert in_stock_variant.can_be_ordered is True

        # Товар закончился
        out_of_stock_product = ProductFactory.create(stock_quantity=0, is_active=True)
        out_of_stock_variant = out_of_stock_product.variants.first()
        assert out_of_stock_variant.is_in_stock is False
        assert out_of_stock_variant.can_be_ordered is False

        # Товар неактивен (Product.is_active = False)
        inactive_product = ProductFactory.create(stock_quantity=10, is_active=False)
        inactive_variant = inactive_product.variants.first()
        assert inactive_variant.is_in_stock is True
        assert inactive_variant.can_be_ordered is False

    def test_product_sku_uniqueness(self):
        """Тест уникальности артикула (SKU в ProductVariant)"""
        test_sku = "UNIQUE-001"
        ProductFactory.create(sku=test_sku)

        with pytest.raises(IntegrityError):
            ProductFactory.create(sku=test_sku)

    def test_product_slug_generation(self):
        """Тест автогенерации slug модели Product при сохранении"""
        brand = BrandFactory.create()
        category = CategoryFactory.create()
        # Создаём Product напрямую без slug - модель должна сгенерировать его
        product = Product(
            name="Супер Товар 2024",
            brand=brand,
            category=category,
            description="Test description",
        )
        product.save()

        assert product.slug == "super-tovar-2024"

    def test_product_relationships(self):
        """Тест связей товара с брендом и категорией"""
        brand = BrandFactory.create(name="Nike")
        category = CategoryFactory.create(name="Футбол")
        product = ProductFactory.create(brand=brand, category=category)

        assert product.brand == brand
        assert product.category == category
        assert product in brand.products.all()
        assert product in category.products.all()

    def test_product_constraints_validation(self):
        """Тест валидации ограничений товара (валидация в ProductVariant)"""
        from apps.products.models import ProductVariant

        # Создаём Product для тестирования Variant
        product = ProductFactory.create(create_variant=False)

        # Тест отрицательных цен - валидация на уровне ProductVariant
        with pytest.raises(ValidationError):
            variant = ProductVariant(
                product=product,
                sku="NEGATIVE-PRICE-001",
                onec_id="1C-NEGATIVE-001",
                retail_price=Decimal("-100.00"),
                stock_quantity=10,
            )
            variant.full_clean()

        # Тест минимального количества заказа на Product
        with pytest.raises(ValidationError):
            product_invalid = ProductFactory.build(min_order_quantity=0)
            product_invalid.full_clean()

    def test_product_meta_configuration(self):
        """Тест настроек Meta класса Product"""
        assert Product._meta.verbose_name == "Товар"
        assert Product._meta.verbose_name_plural == "Товары"
        assert Product._meta.db_table == "products"
        assert Product._meta.ordering == ["-created_at"]


@pytest.mark.django_db
class TestProduct1CIntegrationFields:
    """Тесты полей интеграции с 1С (Story 3.1.1 AC: 3)"""

    def test_onec_id_unique_constraint(self):
        """Тест уникальности поля onec_id"""
        # Создаем первый товар с onec_id
        product1 = ProductFactory.create(onec_id="TEST_1C_ID_001")

        # Проверяем, что товар создался
        assert product1.onec_id == "TEST_1C_ID_001"

        # Пытаемся создать второй товар с тем же onec_id - должна быть ошибка
        with pytest.raises(IntegrityError):
            ProductFactory.create(onec_id="TEST_1C_ID_001")

    def test_onec_id_can_be_null(self):
        """Тест что onec_id может быть null"""
        product = ProductFactory.create(onec_id=None)
        assert product.onec_id is None

    def test_onec_id_can_be_blank(self):
        """Тест что onec_id может быть пустым"""
        product = ProductFactory.create(onec_id="")
        assert product.onec_id == ""

    def test_sync_status_choices(self):
        """Тест выбора статуса синхронизации"""
        valid_statuses = ["pending", "syncing", "synced", "error", "conflict"]

        for status in valid_statuses:
            product = ProductFactory.create(sync_status=status)
            assert product.sync_status == status

    def test_sync_status_default_value(self):
        """Тест значения по умолчанию для sync_status"""
        product = ProductFactory.create()
        assert product.sync_status == "pending"

    def test_last_sync_at_field(self):
        """Тест поля last_sync_at"""
        from datetime import datetime

        # Создаем товар без last_sync_at
        product = ProductFactory.create()
        assert product.last_sync_at is None

        # Обновляем с датой синхронизации
        sync_time = timezone.now()
        product.last_sync_at = sync_time
        product.save()

        # Перезагружаем из БД и проверяем
        product.refresh_from_db()
        assert product.last_sync_at is not None

    def test_error_message_field(self):
        """Тест поля error_message"""
        error_text = "Ошибка синхронизации с 1С: неверный формат данных"

        product = ProductFactory.create(sync_status="error", error_message=error_text)

        assert product.error_message == error_text
        assert product.sync_status == "error"

    def test_error_message_can_be_blank(self):
        """Тест что error_message может быть пустым"""
        product = ProductFactory.create()
        assert product.error_message == ""

    def test_product_1c_fields_together(self):
        """Тест использования всех 1С полей вместе"""
        sync_time = timezone.now()
        product = ProductFactory.create(
            onec_id="FULL_TEST_001",
            sync_status="synced",
            last_sync_at=sync_time,
            error_message="",
        )

        # Проверяем все поля
        assert product.onec_id == "FULL_TEST_001"
        assert product.sync_status == "synced"
        assert product.last_sync_at is not None
        assert product.error_message == ""

        # Проверяем что товар корректно сохраняется и загружается
        product.refresh_from_db()
        assert product.onec_id == "FULL_TEST_001"
        assert product.sync_status == "synced"

    def test_product_indexes_exist(self):
        """Тест что индексы для 1С полей созданы"""
        # Проверяем что в Meta есть индексы для onec_id и sync_status
        index_fields = []
        for index in Product._meta.indexes:
            index_fields.extend(index.fields)

        assert "onec_id" in index_fields
        assert "sync_status" in index_fields


@pytest.mark.django_db
class TestProductStockLogic:
    """
    Тесты логики остатков товаров (теперь в ProductVariant)
    """

    def test_reserved_quantity_default_value(self):
        """
        Тест значения по умолчанию для reserved_quantity в ProductVariant
        """
        product = ProductFactory.create()
        variant = product.variants.first()
        assert variant.reserved_quantity == 0

    def test_available_quantity_calculation(self):
        """
        Тест вычисления доступного количества в ProductVariant
        """
        product = ProductFactory.create(stock_quantity=10, reserved_quantity=3)
        variant = product.variants.first()

        assert variant.available_quantity == 7

        # Тест случая когда резерв больше остатка
        variant.reserved_quantity = 15
        variant.save()

        assert variant.available_quantity == 0  # max(0, 10-15) = 0

    def test_is_in_stock_property(self):
        """
        Тест свойства is_in_stock в ProductVariant
        """
        # Товар в наличии
        product = ProductFactory.create(stock_quantity=5)
        variant = product.variants.first()
        assert variant.is_in_stock is True

        # Товар не в наличии
        variant.stock_quantity = 0
        variant.save()
        assert variant.is_in_stock is False

    def test_can_be_ordered_basic(self):
        """
        Тест базовой логики can_be_ordered в ProductVariant
        """
        product = ProductFactory.create(is_active=True, stock_quantity=10, reserved_quantity=2)
        product.min_order_quantity = 1
        product.save()

        variant = product.variants.first()
        assert variant.can_be_ordered is True

    def test_can_be_ordered_insufficient_available(self):
        """
        Тест can_be_ordered при недостаточном доступном количестве
        """
        product = ProductFactory.create(
            is_active=True,
            stock_quantity=5,
            reserved_quantity=3,
        )
        product.min_order_quantity = 5  # Доступно только 2, а минимум 5
        product.save()

        variant = product.variants.first()
        assert variant.can_be_ordered is False

    def test_can_be_ordered_inactive_product(self):
        """
        Тест can_be_ordered для неактивного товара
        """
        product = ProductFactory.create(is_active=False, stock_quantity=10, reserved_quantity=0)

        variant = product.variants.first()
        assert variant.can_be_ordered is False

    def test_can_be_ordered_out_of_stock(self):
        """
        Тест can_be_ordered для товара без остатков
        """
        product = ProductFactory.create(is_active=True, stock_quantity=0, reserved_quantity=0)

        variant = product.variants.first()
        assert variant.can_be_ordered is False

    def test_stock_scenarios_realistic(self):
        """
        Тест реалистичных сценариев остатков
        """
        # Сценарий 1: Высокий остаток
        high_stock_product = ProductFactory.create(stock_quantity=100, reserved_quantity=5)
        high_stock_product.min_order_quantity = 1
        high_stock_product.save()
        variant = high_stock_product.variants.first()
        assert variant.is_in_stock is True
        assert variant.can_be_ordered is True
        assert variant.available_quantity == 95

        # Сценарий 2: Низкий остаток
        low_stock_product = ProductFactory.create(stock_quantity=3, reserved_quantity=1)
        low_stock_product.min_order_quantity = 1
        low_stock_product.save()
        variant2 = low_stock_product.variants.first()
        assert variant2.is_in_stock is True
        assert variant2.can_be_ordered is True
        assert variant2.available_quantity == 2

        # Сценарий 3: Перепродано (oversold)
        oversold_product = ProductFactory.create(stock_quantity=5, reserved_quantity=10)
        oversold_product.min_order_quantity = 1
        oversold_product.save()
        variant3 = oversold_product.variants.first()
        assert variant3.is_in_stock is True
        assert variant3.can_be_ordered is False  # available_quantity = 0
        assert variant3.available_quantity == 0

    def test_stock_edge_cases(self):
        """
        Тест граничных случаев остатков
        """
        from apps.products.models import ProductVariant

        # Тест: точно минимальное количество
        edge_case_product = ProductFactory.create(
            stock_quantity=5,
            reserved_quantity=2,
        )
        edge_case_product.min_order_quantity = 3  # available_quantity = 3
        edge_case_product.save()
        variant = edge_case_product.variants.first()
        assert variant.can_be_ordered is True

        # Тест: на единицу меньше минимального
        edge_case_product.min_order_quantity = 4
        edge_case_product.save()
        assert variant.can_be_ordered is False

    def test_reserved_quantity_validation(self):
        """
        Тест валидации reserved_quantity в ProductVariant
        """
        from apps.products.models import ProductVariant

        product = ProductFactory.create(stock_quantity=10, reserved_quantity=5)
        variant = product.variants.first()

        # Валидная ситуация
        assert variant.reserved_quantity == 5

        # Тест что поле имеет правильный тип - PositiveIntegerField
        assert isinstance(
            ProductVariant._meta.get_field("reserved_quantity"),
            type(ProductVariant._meta.get_field("stock_quantity")),
        )

    def test_stock_fields_help_text(self):
        """
        Тест что поля ProductVariant имеют правильный help_text
        """
        from apps.products.models import ProductVariant

        field = ProductVariant._meta.get_field("reserved_quantity")
        assert "зарезервированное" in field.help_text.lower()
        assert "корзин" in field.help_text.lower() or "заказ" in field.help_text.lower()

    def test_onec_brand_id_field(self):
        """
        Story 13.2: Тест поля onec_brand_id в Product
        """
        # Создание товара с onec_brand_id
        brand_id = "fb3f263e-dfd0-11ef-8361-fa163ea88911"
        product = ProductFactory.create(onec_brand_id=brand_id)

        assert product.onec_brand_id == brand_id

        # Проверка nullable
        product_without_brand_id = ProductFactory.create(onec_brand_id=None)
        assert product_without_brand_id.onec_brand_id is None

        # Проверка max_length=100
        field = Product._meta.get_field("onec_brand_id")
        assert field.max_length == 100

        # Проверка db_index
        assert field.db_index is True

        # Проверка nullable и blank
        assert field.null is True
        assert field.blank is True

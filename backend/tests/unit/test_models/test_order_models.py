"""
Тесты для моделей заказов FREESPORT Platform
"""

import uuid
from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.orders.models import Order, OrderItem
from tests.conftest import OrderFactory, OrderItemFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestOrderModel:
    """Тесты модели Order"""

    def test_order_creation(self):
        """Тест создания заказа"""
        user = UserFactory.create()
        order = OrderFactory.create(
            user=user,
            status="pending",
            total_amount=Decimal("5000.00"),
            delivery_method="courier",
        )

        assert order.user == user
        assert order.status == "pending"
        assert order.total_amount == Decimal("5000.00")
        assert order.delivery_method == "courier"
        assert order.order_number is not None
        assert str(order) == f"Заказ #{order.order_number}"

    def test_order_number_generation(self):
        """Тест автогенерации номера заказа"""
        order1 = OrderFactory.create()
        order2 = OrderFactory.create()

        assert order1.order_number != order2.order_number
        assert len(order1.order_number) > 3  # FS- плюс номер

    def test_order_number_uniqueness(self):
        """Тест уникальности номера заказа"""
        order1 = OrderFactory.create()

        # Попытка создать заказ с тем же номером должна вызвать ошибку
        with pytest.raises(IntegrityError):
            OrderFactory.create(order_number=order1.order_number)

    def test_order_status_choices(self):
        """Тест валидных статусов заказа"""
        valid_statuses = [
            "pending",
            "confirmed",
            "processing",
            "shipped",
            "delivered",
            "cancelled",
        ]

        for status in valid_statuses:
            order = OrderFactory.create(status=status)
            order.full_clean()  # Не должно вызывать ValidationError
            assert order.status == status

    def test_invalid_order_status(self):
        """Тест невалидного статуса заказа"""
        with pytest.raises(ValidationError):
            order = OrderFactory.build(status="invalid_status")
            order.full_clean()

    def test_delivery_method_choices(self):
        """Тест валидных способов доставки"""
        valid_methods = ["pickup", "courier", "post"]

        for method in valid_methods:
            order = OrderFactory.create(delivery_method=method)
            order.full_clean()
            assert order.delivery_method == method

    def test_payment_method_choices(self):
        """Тест валидных способов оплаты"""
        valid_methods = ["card", "cash", "bank_transfer", "payment_on_delivery"]

        for method in valid_methods:
            order = OrderFactory.create(payment_method=method)
            order.full_clean()
            assert order.payment_method == method

    def test_order_total_items_property(self):
        """Тест подсчета общего количества товаров в заказе"""
        order = OrderFactory.create()
        OrderItemFactory.create(order=order, quantity=2)
        OrderItemFactory.create(order=order, quantity=3)
        OrderItemFactory.create(order=order, quantity=1)

        assert order.total_items == 6

    def test_order_calculated_total_property(self):
        """Тест подсчета общей стоимости заказа"""
        order = OrderFactory.create()

        # Создаем элементы заказа с известными ценами
        OrderItemFactory.create(order=order, quantity=2, unit_price=Decimal("1000.00"))
        OrderItemFactory.create(order=order, quantity=1, unit_price=Decimal("500.00"))

        expected_total = Decimal("1000.00") * 2 + Decimal("500.00") * 1
        assert order.calculated_total == expected_total

    def test_order_can_be_cancelled_property(self):
        """Тест возможности отмены заказа"""
        # Заказы в статусах pending и confirmed могут быть отменены
        pending_order = OrderFactory.create(status="pending")
        confirmed_order = OrderFactory.create(status="confirmed")

        assert pending_order.can_be_cancelled is True
        assert confirmed_order.can_be_cancelled is True

        # Заказы в других статусах не могут быть отменены
        shipped_order = OrderFactory.create(status="shipped")
        delivered_order = OrderFactory.create(status="delivered")
        cancelled_order = OrderFactory.create(status="cancelled")

        assert shipped_order.can_be_cancelled is False
        assert delivered_order.can_be_cancelled is False
        assert cancelled_order.can_be_cancelled is False

    def test_order_validation_positive_total(self):
        """Тест валидации положительной суммы заказа"""
        with pytest.raises(ValidationError):
            order = OrderFactory.build(total_amount=Decimal("-100.00"))
            order.full_clean()

    def test_order_for_different_user_roles(self):
        """Тест создания заказов для разных ролей пользователей"""
        retail_user = UserFactory.create(role="retail")
        wholesale_user = UserFactory.create(role="wholesale_level1")
        trainer_user = UserFactory.create(role="trainer")

        retail_order = OrderFactory.create(user=retail_user)
        wholesale_order = OrderFactory.create(user=wholesale_user)
        trainer_order = OrderFactory.create(user=trainer_user)

        assert retail_order.user.role == "retail"
        assert wholesale_order.user.role == "wholesale_level1"
        assert trainer_order.user.role == "trainer"

    def test_order_timestamps(self):
        """Тест автоматических временных меток"""
        order = OrderFactory.create()

        assert order.created_at is not None
        assert order.updated_at is not None
        assert order.created_at <= order.updated_at

    def test_order_meta_configuration(self):
        """Тест настроек Meta класса Order"""
        assert Order._meta.verbose_name_plural == "Заказы"
        assert Order._meta.db_table == "orders"
        assert Order._meta.ordering == ["-created_at"]

    def test_generate_order_number_format(self):
        """Тест формата генерируемого номера заказа (должен быть UUID)"""
        order_number = Order.generate_order_number()
        try:
            # Проверяем, что строка является валидным UUID4
            val = uuid.UUID(order_number, version=4)
            assert str(val) == order_number, "Сгенерированный номер не соответствует каноническому формату UUID"
        except (ValueError, TypeError, AttributeError):
            pytest.fail("Сгенерированный номер заказа не является валидным UUID4")

    def test_order_number_auto_generation(self):
        """Тест автогенерации номера заказа при создании"""
        order = OrderFactory.create()

        assert order.order_number is not None

    def test_customer_display_name_with_user(self):
        """Тест отображаемого имени для авторизованного пользователя"""
        user = UserFactory.create(first_name="John", last_name="Doe")
        order = OrderFactory.create(user=user)

        assert order.customer_display_name == "John Doe"

    def test_customer_display_name_guest_order(self):
        """Тест отображаемого имени для гостевого заказа"""
        order = OrderFactory.create(
            user=None,
            customer_name="Jane Smith",
            customer_email="jane@example.com",
        )

        assert order.customer_display_name == "Jane Smith"


@pytest.mark.django_db
class TestOrderItemModel:
    """Тесты модели OrderItem"""

    def test_order_item_creation(self):
        """Тест создания элемента заказа"""
        order = OrderFactory.create()
        product = ProductFactory.create(name="Тестовый товар", sku="TEST-001")
        variant = product.variants.first()

        item = OrderItemFactory.create(
            order=order,
            product=product,
            variant=variant,
            quantity=2,
            unit_price=Decimal("1500.00"),
        )

        assert item.order == order
        assert item.product == product
        assert item.quantity == 2
        assert item.unit_price == Decimal("1500.00")
        assert item.product_name == "Тестовый товар"

        # sku теперь хранится в варианте, при создании товара в фабрике
        # SKU генерится для варианта автоматически
        # поэтому здесь мы проверяем, что он не пустой, или что он совпадает с вариантом
        assert item.product_sku == variant.sku

        assert str(item) == f"Тестовый товар x2 в заказе #{order.order_number}"

    def test_order_item_total_price_property(self):
        """Тест подсчета стоимости элемента заказа"""
        item = OrderItemFactory.create(quantity=3, unit_price=Decimal("750.00"))

        assert item.total_price == Decimal("2250.00")

    def test_order_item_saves_product_snapshot(self):
        """Тест сохранения снимка данных товара на момент заказа"""
        product = ProductFactory.create(name="Оригинальное название")
        variant = product.variants.first()
        variant.sku = "ORIG-001"
        variant.save()

        item = OrderItemFactory.create(
            product=product,
            variant=variant,
            product_name=product.name,
            product_sku=variant.sku,
        )

        # Изменяем товар после создания заказа
        product.name = "Новое название"
        product.save()
        variant.sku = "NEW-001"
        variant.save()

        # В элементе заказа должны остаться старые данные
        item.refresh_from_db()
        assert item.product_name == "Оригинальное название"
        assert item.product_sku == "ORIG-001"

    def test_order_item_validation_positive_quantity(self):
        """Тест валидации положительного количества"""
        with pytest.raises(ValidationError):
            item = OrderItemFactory.build(quantity=0)
            item.full_clean()

    def test_order_item_validation_positive_price(self):
        """Тест валидации положительной цены"""
        with pytest.raises(ValidationError):
            item = OrderItemFactory.build(unit_price=Decimal("-100.00"))
            item.full_clean()

    def test_order_item_with_different_user_role_pricing(self):
        """Тест элемента заказа с ценами для разных ролей пользователей"""
        # Создаем товар с разными ценами
        product = ProductFactory.create(
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            trainer_price=Decimal("850.00"),
        )
        variant = product.variants.first()

        # Создаем заказы для разных пользователей
        retail_user = UserFactory.create(role="retail")
        wholesale_user = UserFactory.create(role="wholesale_level1")
        trainer_user = UserFactory.create(role="trainer")

        retail_order = OrderFactory.create(user=retail_user)
        wholesale_order = OrderFactory.create(user=wholesale_user)
        trainer_order = OrderFactory.create(user=trainer_user)

        # Создаем элементы заказов с соответствующими ценами
        # Цены берутся из variant по методу get_price_for_user
        retail_item = OrderItemFactory.create(
            order=retail_order,
            product=product,
            variant=variant,
            unit_price=variant.get_price_for_user(retail_user),
        )
        wholesale_item = OrderItemFactory.create(
            order=wholesale_order,
            product=product,
            variant=variant,
            unit_price=variant.get_price_for_user(wholesale_user),
        )
        trainer_item = OrderItemFactory.create(
            order=trainer_order,
            product=product,
            variant=variant,
            unit_price=variant.get_price_for_user(trainer_user),
        )

        assert retail_item.unit_price == Decimal("1000.00")
        assert wholesale_item.unit_price == Decimal("900.00")
        assert trainer_item.unit_price == Decimal("850.00")

    def test_multiple_items_in_same_order(self):
        """Тест множественных элементов в одном заказе"""
        order = OrderFactory.create()

        item1 = OrderItemFactory.create(order=order, quantity=2)
        item2 = OrderItemFactory.create(order=order, quantity=3)
        item3 = OrderItemFactory.create(order=order, quantity=1)

        assert order.items.count() == 3
        assert item1 in order.items.all()
        assert item2 in order.items.all()
        assert item3 in order.items.all()

    def test_order_item_unique_product_in_order_constraint(self):
        """Тест уникальности товара (варианта) в рамках одного заказа"""
        order = OrderFactory.create()
        product = ProductFactory.create()
        variant = product.variants.first()

        OrderItemFactory.create(order=order, product=product, variant=variant)

        # Попытка добавить тот же вариант в тот же заказ должна вызвать ошибку
        with pytest.raises((IntegrityError, ValidationError, Exception)):
            OrderItemFactory.create(order=order, product=product, variant=variant)

    def test_order_item_meta_configuration(self):
        """Тест настроек Meta класса OrderItem"""
        assert OrderItem._meta.verbose_name == "Элемент заказа"
        assert OrderItem._meta.verbose_name_plural == "Элементы заказа"
        assert OrderItem._meta.db_table == "order_items"

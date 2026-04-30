# pyright: reportGeneralTypeIssues=false
# pyright: reportUnknownMemberType=false
# pyright: reportOptionalMemberAccess=false
"""
Тесты для Order Serializers - Story 2.7 Order Management API
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.orders.serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderItemSerializer,
    OrderListSerializer,
)
from apps.users.serializers import AddressSerializer as DeliveryAddressSerializer

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderDetailSerializer:
    """Тесты детального сериализатора заказов"""

    def test_order_serialization(self, user_factory, address_factory, order_factory):
        """Тест сериализации заказа"""
        user = user_factory.create()
        address = address_factory.create(user=user)
        order = order_factory.create(user=user, delivery_address=address, status="pending")

        serializer = OrderDetailSerializer(order)
        data = serializer.data  # type: ignore

        assert data["status"] == "pending"  # type: ignore
        assert "user" in data
        assert "delivery_address" in data

    def test_serializer_fields(self, user_factory, order_factory):
        """Тест корректности полей сериализатора"""
        user = user_factory.create(first_name="John", last_name="Doe")
        order = order_factory.create(
            user=user,
            total_amount=Decimal("1000.00"),
            delivery_cost=Decimal("500.00"),
        )

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert "order_number" in data
        assert "customer_display_name" in data
        assert "total_amount" in data
        assert "delivery_cost" in data
        assert "items" in data
        assert data["customer_display_name"] == "John Doe"  # type: ignore

    def test_order_with_items_serialization(self, user_factory, order_factory, product_factory, order_item_factory):
        """Тест сериализации заказа с товарами (субзаказ, is_master=False)"""
        user = user_factory.create()
        # is_master=False: items принадлежат субзаказу напрямую
        order = order_factory.create(user=user, is_master=False)

        product1 = product_factory.create(name="Товар 1", retail_price=Decimal("1000.00"))
        product2 = product_factory.create(name="Товар 2", retail_price=Decimal("1500.00"))

        order_item_factory.create(
            order=order,
            product=product1,
            variant=product1.variants.first(),
            quantity=2,
            unit_price=product1.variants.first().retail_price,
        )
        order_item_factory.create(
            order=order,
            product=product2,
            variant=product2.variants.first(),
            quantity=1,
            unit_price=product2.variants.first().retail_price,
        )

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert "items" in data
        assert len(data["items"]) == 2
        item_names = [item["product_name"] for item in data["items"]]
        assert "Товар 1" in item_names
        assert "Товар 2" in item_names

    def test_order_total_calculation(self, order_factory):
        """Тест расчета общей суммы заказа"""
        order = order_factory.create(total_amount=Decimal("5000.00"))

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert data["total_amount"] == "5000.00"  # type: ignore


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderItemSerializer:
    """Тесты сериализатора элементов заказа"""

    def test_order_item_serialization(self, user_factory, order_factory, product_factory, order_item_factory):
        """Тест сериализации элемента заказа"""
        user = user_factory.create()
        order = order_factory.create(user=user)
        product = product_factory.create(name="Тестовый товар", retail_price=Decimal("1500.00"))

        order_item = order_item_factory.create(
            order=order,
            product=product,
            variant=product.variants.first(),
            quantity=3,
            unit_price=product.variants.first().retail_price,
        )

        serializer = OrderItemSerializer(order_item)
        data = serializer.data

        assert data["product"]["name"] == "Тестовый товар"  # type: ignore
        assert data["quantity"] == 3  # type: ignore
        assert data["unit_price"] == "1500.00"  # type: ignore

    def test_order_item_total_calculation(self, order_item_factory):
        """Тест расчета суммы элемента заказа"""
        order_item = order_item_factory.create(quantity=4, unit_price=Decimal("250.00"))

        serializer = OrderItemSerializer(order_item)
        data = serializer.data

        expected_total = Decimal("250.00") * 4
        assert Decimal(data["total_price"]) == expected_total  # type: ignore

    def test_order_item_with_discount(self, product_factory, order_item_factory):
        """Тест элемента заказа со скидкой"""
        product = product_factory.create(retail_price=Decimal("1000.00"))

        order_item = order_item_factory.create(product=product, quantity=1, unit_price=Decimal("500.00"))

        serializer = OrderItemSerializer(order_item)
        data = serializer.data

        assert data["unit_price"] == "500.00"  # type: ignore
        assert data["total_price"] == "500.00"  # type: ignore


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderCreateSerializer:
    """Тесты сериализатора создания заказа"""

    def test_order_creation_validation(
        self,
        user_factory,
        address_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Тест валидации создания заказа"""
        user = user_factory.create()
        address = address_factory.create(user=user)

        # Создаем корзину с товарами
        cart = cart_factory.create(user=user)
        product = product_factory.create(stock_quantity=10)
        cart_item_factory.create(cart=cart, product=product, quantity=2)

        data = {
            "delivery_address": str(address),
            "payment_method": "card",
            "delivery_method": "courier",
        }

        # Создаем mock request
        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors

        order = serializer.save()
        assert order.user == user  # type: ignore

    def test_validate_empty_cart(self, user_factory, cart_factory):
        """Тест валидации пустой корзины"""
        user = user_factory.create()
        cart_factory.create(user=user)

        # Мокаем request объект
        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = OrderCreateSerializer(context={"request": MockRequest(user)})

        with pytest.raises(serializers.ValidationError, match="Корзина пуста"):
            serializer.validate(
                {
                    "delivery_address": "Test Address",
                    "delivery_method": "courier",
                    "payment_method": "card",
                }
            )

    def test_validate_insufficient_stock(self, user_factory, cart_factory, product_factory, cart_item_factory):
        """Тест валидации недостаточного количества товара"""
        user = user_factory.create()
        product = product_factory.create(stock_quantity=10)  # Создаем с достаточным запасом
        cart = cart_factory.create(user=user)
        cart_item_factory.create(cart=cart, product=product, quantity=5)

        # Теперь уменьшаем stock_quantity варианта, чтобы симулировать недостаток
        variant = product.variants.first()
        variant.stock_quantity = 2
        variant.save()

        class MockRequest:
            def __init__(self, user):
                self.user = user

        serializer = OrderCreateSerializer(context={"request": MockRequest(user)})

        with pytest.raises(serializers.ValidationError, match="Недостаточно товара"):
            serializer.validate(
                {
                    "delivery_address": "Test Address",
                    "delivery_method": "courier",
                    "payment_method": "card",
                }
            )

    def test_delivery_cost_calculation(self):
        """Тест расчета стоимости доставки"""
        serializer = OrderCreateSerializer()

        assert serializer.calculate_delivery_cost("pickup") == 0
        assert serializer.calculate_delivery_cost("courier") == 500
        assert serializer.calculate_delivery_cost("post") == 300
        assert serializer.calculate_delivery_cost("transport_company") == 1000

    def test_order_creation_with_b2b_user(
        self,
        user_factory,
        address_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Тест создания заказа B2B пользователем"""
        b2b_user = user_factory.create(role="wholesale_level1")
        company_address = address_factory.create(user=b2b_user, address_type="legal")
        # Создаем корзину с товарами
        cart = cart_factory.create(user=b2b_user)
        product = product_factory.create(stock_quantity=10)
        cart_item_factory.create(cart=cart, product=product, quantity=5)

        data = {
            "delivery_address": str(company_address),
            "payment_method": "bank_transfer",
            "delivery_method": "pickup",
        }

        # Создаем mock request
        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = b2b_user

        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors

        order = serializer.save()
        assert order.user.role == "wholesale_level1"  # type: ignore

    def test_order_creation_validation_errors(self, user_factory, address_factory):
        """Тест ошибок валидации при создании заказа"""
        user = user_factory.create()
        address = address_factory.create(user=user)

        data = {
            "user": user.id,
            "delivery_address": address.id,
            "payment_method": "invalid_method",
            "delivery_method": "courier",
        }

        serializer = OrderCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "payment_method" in serializer.errors

    def test_order_from_cart_creation(
        self,
        user_factory,
        address_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Тест создания заказа из корзины — items живут в субзаказах"""
        from apps.orders.models import OrderItem

        user = user_factory.create()
        address = address_factory.create(user=user)
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("100.00"))
        product2 = product_factory.create(retail_price=Decimal("200.00"))

        cart_item_factory.create(cart=cart, product=product1, quantity=2)
        cart_item_factory.create(cart=cart, product=product2, quantity=1)

        data = {
            "delivery_address": str(address),
            "payment_method": "card",
            "delivery_method": "courier",
        }

        # Создаем mock request
        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors

        master = serializer.save()
        # После Story 34-2: items живут в субзаказах, не на мастере
        assert master.is_master
        assert master.items.count() == 0
        total_sub_items = OrderItem.objects.filter(order__parent_order=master).count()
        assert total_sub_items == 2  # type: ignore

    def test_order_creation_without_address(self, user_factory, address_factory):
        """Тест создания заказа без адреса доставки"""
        user = user_factory.create()

        data = {"user": user.id, "payment_method": "card", "delivery_method": "pickup"}

        serializer = OrderCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "delivery_address" in serializer.errors


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderStatusUpdate:
    """Тесты обновления статуса заказа через модель"""

    def test_status_update_through_model(self, order_factory):
        """Тест обновления статуса заказа напрямую через модель"""
        order = order_factory.create(status="pending")

        # Обновляем статус напрямую
        order.status = "confirmed"
        order.save()

        order.refresh_from_db()
        assert order.status == "confirmed"

    def test_status_validation_in_model(self, order_factory):
        """Тест валидации статуса в модели"""
        order = order_factory.create(status="pending")

        # Валидные статусы
        valid_statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]

        for status in valid_statuses:
            order.status = status
            order.full_clean()  # Проверяем валидацию модели
            assert order.status == status


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderItemVatRateSnapshot:
    """Regression-тесты: vat_rate заполняется при bulk_create (Review 34-1 [High])"""

    def test_order_item_vat_rate_set_via_serializer(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
        product_variant_factory,
    ):
        """vat_rate из variant снимается при создании заказа через OrderCreateSerializer (bulk_create path)"""
        from decimal import Decimal
        from unittest.mock import Mock

        from apps.orders.models import OrderItem

        user = user_factory.create()
        product = product_factory.create(retail_price=Decimal("500.00"))
        variant = product.variants.first()

        # Устанавливаем vat_rate у варианта
        variant.vat_rate = Decimal("5.00")
        variant.save()

        cart = cart_factory.create(user=user)
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        data = {
            "delivery_address": "Ул. Тестовая, 1",
            "delivery_method": "pickup",
            "payment_method": "card",
        }
        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors

        master = serializer.save()

        # После Story 34-2: items в субзаказах
        sub_items = list(OrderItem.objects.filter(order__parent_order=master))
        assert len(sub_items) == 1
        assert sub_items[0].vat_rate == Decimal(
            "5.00"
        ), "vat_rate должен быть снят из variant при создании через bulk_create"

    def test_order_item_vat_rate_null_when_variant_has_no_vat(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """vat_rate остаётся None, если у variant нет vat_rate"""
        from decimal import Decimal
        from unittest.mock import Mock

        from apps.orders.models import OrderItem

        user = user_factory.create()
        product = product_factory.create(retail_price=Decimal("200.00"))
        variant = product.variants.first()

        # Убедимся, что vat_rate = None
        variant.vat_rate = None
        variant.save()

        cart = cart_factory.create(user=user)
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        data = {
            "delivery_address": "Ул. Тестовая, 2",
            "delivery_method": "pickup",
            "payment_method": "card",
        }
        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors

        master = serializer.save()

        # После Story 34-2: items в субзаказах
        sub_items = list(OrderItem.objects.filter(order__parent_order=master))
        assert len(sub_items) == 1
        assert sub_items[0].vat_rate is None


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderListSerializer:
    """Тесты сериализатора списка заказов"""

    def test_order_list_serialization(self, user_factory, order_factory):
        """Тест сериализации списка заказов"""
        user = user_factory.create()
        order1 = order_factory.create(user=user, status="pending", total_amount=Decimal("1000.00"))
        order2 = order_factory.create(user=user, status="confirmed", total_amount=Decimal("2000.00"))

        orders = [order1, order2]
        serializer = OrderListSerializer(orders, many=True)
        data = serializer.data

        assert len(data) == 2
        assert data[0]["status"] in ["pending", "confirmed"]
        assert data[1]["status"] in ["pending", "confirmed"]

    def test_order_list_user_filtering(self, user_factory, order_factory):
        """Тест фильтрации заказов по пользователю"""
        user1 = user_factory.create()
        user2 = user_factory.create()
        order1 = order_factory.create(user=user1, status="pending")
        order2 = order_factory.create(user=user2, status="shipped")

        # Сериализация заказов первого пользователя
        user1_orders = [order1]
        serializer = OrderListSerializer(user1_orders, many=True)
        data = serializer.data

        assert len(data) == 1
        assert data[0]["user"] == user1.id


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderDetailExtended:
    """Тесты расширенного детального сериализатора заказа"""

    def test_order_detail_serialization(
        self,
        user_factory,
        address_factory,
        order_factory,
        product_factory,
        order_item_factory,
    ):
        """Тест детальной сериализации заказа (субзаказ, is_master=False)"""
        user = user_factory.create()
        address = address_factory.create(user=user)
        # is_master=False: items принадлежат субзаказу
        order = order_factory.create(
            user=user,
            delivery_address=address,
            status="confirmed",
            payment_method="card",
            delivery_method="courier",
            is_master=False,
        )

        product = product_factory.create(name="Детальный товар")
        order_item_factory.create(order=order, product=product, quantity=3)

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert "items" in data
        assert "delivery_address" in data
        assert "payment_method" in data
        assert "delivery_method" in data
        assert len(data["items"]) == 1  # type: ignore

    def test_order_detail_performance(self, user_factory, order_factory, product_factory, order_item_factory):
        """Тест производительности детального сериализатора (субзаказ, is_master=False)"""
        user = user_factory.create()
        order = order_factory.create(user=user, is_master=False)

        # Создаем заказ с множеством товаров
        products = product_factory.create_batch(5)
        for product in products:
            order_item_factory.create(order=order, product=product)

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert len(data["items"]) == 5  # type: ignore
        assert "total_amount" in data


@pytest.mark.unit
@pytest.mark.django_db
class TestDeliveryAddressSerializer:
    """Тесты сериализатора адреса доставки"""

    def test_delivery_address_serialization(self, user_factory, address_factory):
        """Тест сериализации адреса доставки"""
        user = user_factory.create()
        address = address_factory.create(
            user=user,
            address_type="shipping",
            city="Москва",
            street="Тверская",
            building="1",
            apartment="10",
        )

        from apps.users.serializers import AddressSerializer

        serializer = AddressSerializer(address)
        data = serializer.data

        assert data["address_type"] == "shipping"  # type: ignore
        assert data["city"] == "Москва"  # type: ignore
        assert data["street"] == "Тверская"  # type: ignore

    def test_delivery_address_validation(self, user_factory):
        """Тест валидации адреса доставки"""
        user = user_factory.create()

        data = {
            "address_type": "shipping",
            "full_name": "Тест Пользователь",
            "phone": "+79111111111",
            "city": "Санкт-Петербург",
            "street": "Невский проспект",
            "building": "1",
            "postal_code": "190000",
        }

        from apps.users.serializers import AddressSerializer

        serializer = AddressSerializer(data=data, context={"user": user})
        assert serializer.is_valid(), serializer.errors

        address = serializer.save()
        assert address.city == "Санкт-Петербург"  # type: ignore


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderIntegration:
    """Интеграционные тесты заказов"""

    def test_full_order_workflow(
        self,
        user_factory,
        address_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Тест полного рабочего процесса заказа"""
        user = user_factory.create()
        address = address_factory.create(user=user)
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("500.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=2)

        # Создание заказа
        create_data = {
            "delivery_address": str(address),
            "payment_method": "card",
            "delivery_method": "courier",
        }

        # Создаем mock request
        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user

        create_serializer = OrderCreateSerializer(data=create_data, context={"request": mock_request})
        assert create_serializer.is_valid()
        order = create_serializer.save()

        # Обновление статуса напрямую через модель
        order.status = "confirmed"  # type: ignore
        order.save()  # type: ignore
        updated_order = order

        # Проверка детальной информации
        detail_serializer = OrderDetailSerializer(updated_order)
        detail_data = detail_serializer.data

        assert detail_data["status"] == "confirmed"  # type: ignore
        assert len(detail_data["items"]) == 1  # type: ignore

    def test_order_performance_with_many_items(
        self,
        user_factory,
        order_factory,
        product_factory,
        order_item_factory,
        category_factory,
        brand_factory,
    ):
        """Тест производительности заказа с множеством товаров (субзаказ, is_master=False)"""
        from tests.conftest import get_unique_suffix

        user = user_factory.create()
        order = order_factory.create(user=user, is_master=False)
        category = category_factory.create()
        brand = brand_factory.create()

        # Создаем множество элементов заказа с разными товарами
        for i in range(10):
            suffix = get_unique_suffix()
            product = product_factory.create(
                sku=f"PERF-{suffix}",
                name=f"Performance Product {suffix}",
                category=category,
                brand=brand,
            )
            order_item_factory.create(order=order, product=product, quantity=i + 1)

        serializer = OrderDetailSerializer(order)
        data = serializer.data

        assert len(data["items"]) == 10  # type: ignore
        assert "total_amount" in data

    def test_b2b_order_workflow(self, user_factory, address_factory, order_factory, order_item_factory):
        """Тест рабочего процесса B2B заказа"""
        b2b_user = user_factory.create(role="wholesale_level1")
        orders = order_factory.create_batch(3, user=b2b_user)

        for order in orders:
            order_item_factory.create(order=order)

        serializer = OrderListSerializer(orders, many=True)
        data = serializer.data

        assert len(data) == 3
        for order_data in data:
            assert order_data["user"] == b2b_user.id


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderVATSplit:
    """Unit-тесты разбивки заказа по VAT-группам (Story 34-2)."""

    def _create_order_via_serializer(self, user, cart_factory, additional_data=None):
        """Вспомогательный метод: создать заказ через сериализатор."""
        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user

        data = {
            "delivery_address": "Ул. Тестовая, 1",
            "delivery_method": "pickup",
            "payment_method": "card",
            **(additional_data or {}),
        }
        serializer = OrderCreateSerializer(data=data, context={"request": mock_request})
        assert serializer.is_valid(), serializer.errors
        return serializer.save()

    def test_multi_vat_split_two_rates(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC1: мульти-VAT (5% и 22%) → 1 мастер + 2 субзаказа с правильными vat_group."""
        from apps.orders.models import Order, OrderItem

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("100.00"))
        product2 = product_factory.create(retail_price=Decimal("200.00"))

        variant1 = product1.variants.first()
        variant2 = product2.variants.first()
        variant1.vat_rate = Decimal("5.00")
        variant1.save()
        variant2.vat_rate = Decimal("22.00")
        variant2.save()

        cart_item_factory.create(cart=cart, product=product1, quantity=1)
        cart_item_factory.create(cart=cart, product=product2, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)

        assert master.is_master
        assert master.parent_order is None

        sub_orders = list(Order.objects.filter(parent_order=master).order_by("vat_group"))
        assert len(sub_orders) == 2

        vat_groups = {sub.vat_group for sub in sub_orders}
        assert Decimal("5.00") in vat_groups
        assert Decimal("22.00") in vat_groups

        for sub in sub_orders:
            assert not sub.is_master
            assert sub.parent_order_id == master.pk

    def test_same_vat_split_two_warehouses(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Одинаковый НДС, но разные склады → отдельные субзаказы для 1С."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("100.00"))
        product2 = product_factory.create(retail_price=Decimal("200.00"))

        variant1 = product1.variants.first()
        variant2 = product2.variants.first()
        variant1.vat_rate = Decimal("22.00")
        variant1.warehouse_name = "1 СДВ склад"
        variant1.save(update_fields=["vat_rate", "warehouse_name"])
        variant2.vat_rate = Decimal("22.00")
        variant2.warehouse_name = "Intex ОСНОВНОЙ"
        variant2.save(update_fields=["vat_rate", "warehouse_name"])

        cart_item_factory.create(cart=cart, product=product1, quantity=1)
        cart_item_factory.create(cart=cart, product=product2, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)

        sub_orders = list(Order.objects.filter(parent_order=master).prefetch_related("items__variant"))
        assert len(sub_orders) == 2
        assert {sub.vat_group for sub in sub_orders} == {Decimal("22.00")}
        assert {sub.items.get().variant.warehouse_name for sub in sub_orders} == {
            "1 СДВ склад",
            "Intex ОСНОВНОЙ",
        }

    def test_homogeneous_cart_one_rate(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC2: однородная корзина (1 ставка) → 1 мастер + 1 субзаказ."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("100.00"))
        product2 = product_factory.create(retail_price=Decimal("50.00"))

        for p in [product1, product2]:
            v = p.variants.first()
            v.vat_rate = Decimal("5.00")
            v.save()

        cart_item_factory.create(cart=cart, product=product1, quantity=1)
        cart_item_factory.create(cart=cart, product=product2, quantity=2)

        master = self._create_order_via_serializer(user, cart_factory)

        sub_orders = list(Order.objects.filter(parent_order=master))
        assert len(sub_orders) == 1
        assert sub_orders[0].vat_group == Decimal("5.00")

    def test_mixed_none_and_rate(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC7: смесь vat_rate=None и vat_rate=5 → fallback DEFAULT_VAT_RATE и отдельная группа 5."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        p_with_vat = product_factory.create(retail_price=Decimal("100.00"))
        p_no_vat = product_factory.create(retail_price=Decimal("200.00"))

        v_with_vat = p_with_vat.variants.first()
        v_with_vat.vat_rate = Decimal("5.00")
        v_with_vat.save()

        v_no_vat = p_no_vat.variants.first()
        v_no_vat.vat_rate = None
        v_no_vat.save()

        cart_item_factory.create(cart=cart, product=p_with_vat, quantity=1)
        cart_item_factory.create(cart=cart, product=p_no_vat, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)

        sub_orders = list(Order.objects.filter(parent_order=master))
        assert len(sub_orders) == 2

        vat_groups = {sub.vat_group for sub in sub_orders}
        assert Decimal("22.00") in vat_groups
        assert Decimal("5.00") in vat_groups

    def test_product_vat_rate_used_when_variant_vat_missing(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Product.vat_rate используется при раздельном импорте goods.xml/offers.xml."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"))
        product.vat_rate = Decimal("10.00")
        product.save(update_fields=["vat_rate"])

        variant = product.variants.first()
        variant.vat_rate = None
        variant.save(update_fields=["vat_rate"])

        cart_item_factory.create(cart=cart, product=product, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)
        sub_order = Order.objects.get(parent_order=master)
        item = sub_order.items.get()

        assert sub_order.vat_group == Decimal("10.00")
        assert item.vat_rate == Decimal("10.00")

    def test_master_has_no_direct_items(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC3: master.items.count() == 0; все позиции в субзаказах."""
        from apps.orders.models import OrderItem

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("100.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=2)

        master = self._create_order_via_serializer(user, cart_factory)

        assert master.items.count() == 0
        sub_items = OrderItem.objects.filter(order__parent_order=master)
        assert sub_items.count() == 1

    def test_delivery_cost_only_on_master(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC4: delivery_cost только на мастере; у субзаказов = 0.
        master.total_amount = сумма позиций + delivery_cost."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"))
        variant = product.variants.first()
        variant.vat_rate = Decimal("5.00")
        variant.save()

        cart_item_factory.create(cart=cart, product=product, quantity=3)

        # delivery_method=courier → delivery_cost=500
        mock_request = __import__("unittest.mock", fromlist=["Mock"]).Mock()
        mock_request.user = user
        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Test",
                "delivery_method": "courier",
                "payment_method": "card",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()

        assert master.delivery_cost == Decimal("500")

        sub_orders = list(Order.objects.filter(parent_order=master))
        assert len(sub_orders) == 1
        assert sub_orders[0].delivery_cost == Decimal("0")

        # master.total_amount = 100*3 + 500
        assert master.total_amount == Decimal("800")
        # sub.total_amount = 100*3
        assert sub_orders[0].total_amount == Decimal("300")

    def test_atomicity_on_error(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC5: при ошибке ни мастер, ни субзаказы не сохраняются."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"), stock_quantity=1)
        # Добавляем количество, которое проходит validate(), но потом уменьшаем stock
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        # Уменьшаем stock до 0 ПОСЛЕ добавления в корзину (validate уже прошёл),
        # симулируем ошибку списания. Реальнее — просто убеждаемся через DB constraint.
        # Тест проверяет: если сервис бросит исключение, ничего не сохраняется.
        initial_order_count = Order.objects.count()

        from unittest.mock import Mock, patch

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Test",
                "delivery_method": "pickup",
                "payment_method": "card",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors

        # Патчим cart.clear() чтобы оно бросило исключение после создания заказов
        with patch.object(cart.__class__, "clear", side_effect=Exception("simulated error")):
            try:
                serializer.save()
            except Exception:
                pass

        # Транзакция откатилась — никаких заказов не создано
        assert Order.objects.count() == initial_order_count

    def test_vat_rate_snapshot_in_all_sub_orders(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC3/Task 6.7: OrderItem.vat_rate заполнен через build_snapshot во всех субзаказах."""
        from apps.orders.models import OrderItem

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        p1 = product_factory.create(retail_price=Decimal("100.00"))
        p2 = product_factory.create(retail_price=Decimal("200.00"))

        v1 = p1.variants.first()
        v1.vat_rate = Decimal("5.00")
        v1.save()

        v2 = p2.variants.first()
        v2.vat_rate = Decimal("22.00")
        v2.save()

        cart_item_factory.create(cart=cart, product=p1, quantity=1)
        cart_item_factory.create(cart=cart, product=p2, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)

        sub_items = list(OrderItem.objects.filter(order__parent_order=master).select_related("variant"))
        assert len(sub_items) == 2

        vat_rates = {item.vat_rate for item in sub_items}
        assert Decimal("5.00") in vat_rates
        assert Decimal("22.00") in vat_rates

    def test_sub_order_inherits_master_attributes(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC6: субзаказ наследует customer/delivery/payment данные от мастера."""
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user
        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Ленина, 1",
                "delivery_method": "courier",
                "payment_method": "card",
                "notes": "Test note",
                "customer_name": "Иван",
                "customer_email": "ivan@test.com",
                "customer_phone": "+79001234567",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()

        sub = Order.objects.get(parent_order=master)
        assert sub.customer_name == master.customer_name
        assert sub.customer_email == master.customer_email
        assert sub.customer_phone == master.customer_phone
        assert sub.delivery_address == master.delivery_address
        assert sub.delivery_method == master.delivery_method
        assert sub.payment_method == master.payment_method
        assert sub.notes == master.notes
        assert sub.status == "pending"
        assert sub.payment_status == "pending"

    def test_master_items_aggregated_in_serializer(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC11: OrderDetailSerializer для мастера показывает items всех субзаказов."""
        user = user_factory.create()
        cart = cart_factory.create(user=user)

        p1 = product_factory.create(retail_price=Decimal("100.00"))
        p2 = product_factory.create(retail_price=Decimal("200.00"))
        v1 = p1.variants.first()
        v1.vat_rate = Decimal("5.00")
        v1.save()
        v2 = p2.variants.first()
        v2.vat_rate = Decimal("22.00")
        v2.save()

        cart_item_factory.create(cart=cart, product=p1, quantity=2)
        cart_item_factory.create(cart=cart, product=p2, quantity=1)

        master = self._create_order_via_serializer(user, cart_factory)

        serializer = OrderDetailSerializer(master)
        data = serializer.data

        assert len(data["items"]) == 2
        assert data["total_items"] == 3  # 2 + 1

    def test_master_calculated_total_includes_delivery_cost(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC4/AC11: calculated_total мастера = сумма items субзаказов + delivery_cost."""
        user = user_factory.create()
        cart = cart_factory.create(user=user)

        p1 = product_factory.create(retail_price=Decimal("100.00"))
        p2 = product_factory.create(retail_price=Decimal("200.00"))
        v1 = p1.variants.first()
        v1.vat_rate = Decimal("5.00")
        v1.save()
        v2 = p2.variants.first()
        v2.vat_rate = Decimal("22.00")
        v2.save()

        cart_item_factory.create(cart=cart, product=p1, quantity=2)
        cart_item_factory.create(cart=cart, product=p2, quantity=1)

        # delivery_method=courier → delivery_cost=500
        master = self._create_order_via_serializer(user, cart_factory, additional_data={"delivery_method": "courier"})

        serializer = OrderDetailSerializer(master)
        data = serializer.data

        # 100*2 + 200*1 + 500 = 900
        expected_total = Decimal("900.00")
        assert Decimal(str(data["calculated_total"])) == expected_total
        # calculated_total должен совпадать с total_amount мастера (AC4)
        assert Decimal(str(data["calculated_total"])) == master.total_amount

    def test_master_calculated_total_homogeneous_cart_with_delivery(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Regression: calculated_total мастера корректен и для однородной корзины с доставкой."""
        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("150.00"))
        v = product.variants.first()
        v.vat_rate = Decimal("5.00")
        v.save()

        cart_item_factory.create(cart=cart, product=product, quantity=4)

        # post=300 стоимость доставки
        master = self._create_order_via_serializer(user, cart_factory, additional_data={"delivery_method": "post"})

        serializer = OrderDetailSerializer(master)
        data = serializer.data

        # 150*4 + 300 = 900
        expected_total = Decimal("900.00")
        assert Decimal(str(data["calculated_total"])) == expected_total
        assert Decimal(str(data["calculated_total"])) == master.total_amount

    def test_rollback_on_post_validation_stock_depletion(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC5/Task 6.6: реальный rollback при post-validation stock failure.

        Сценарий race condition:
        1. Валидация проходит (stock=3, qty=3).
        2. Параллельный checkout забрал остатки — stock=0.
        3. Наш service при conditional update получает updated=0 → ValidationError.
        4. Транзакция откатывается, ни мастер, ни субзаказы не создаются.
        """
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"), stock_quantity=3)
        cart_item_factory.create(cart=cart, product=product, quantity=3)

        initial_order_count = Order.objects.count()

        from unittest.mock import Mock

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Test",
                "delivery_method": "pickup",
                "payment_method": "card",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors

        # Симулируем параллельный checkout — stock ушёл в 0 ПОСЛЕ валидации
        variant = product.variants.first()
        variant.stock_quantity = 0
        variant.save()

        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.save()
        assert "Недостаточно" in str(exc_info.value)

        # Транзакция откатилась: ни мастер, ни субзаказы не сохранились
        assert Order.objects.count() == initial_order_count

    def test_snapshot_prices_used_not_live_catalog_price(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """[AI-Review][Medium] Regression: unit_price, sub_order.total_amount и
        master.total_amount вычисляются из cart snapshot, а не из live catalog price.

        Сценарий: товар добавлен в корзину по цене 100 руб. (snapshot), затем
        retail_price изменён на 999 руб. Все финансовые поля заказа должны
        использовать snapshot (100 руб.), а не обновлённую цену каталога.
        """
        from apps.orders.models import OrderItem

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("100.00"))
        variant = product.variants.first()
        variant.vat_rate = Decimal("5.00")
        variant.save()

        # Добавляем в корзину — snapshot фиксирует цену 100.00
        cart_item_factory.create(cart=cart, product=product, quantity=3)

        # Изменяем цену в каталоге ПОСЛЕ добавления в корзину
        variant.retail_price = Decimal("999.00")
        variant.save()

        master = self._create_order_via_serializer(user, cart_factory)

        # OrderItem.unit_price = snapshot (100), не live (999)
        items = list(OrderItem.objects.filter(order__parent_order=master))
        assert len(items) == 1
        assert items[0].unit_price == Decimal("100.00")
        assert items[0].total_price == Decimal("300.00")  # 100 * 3

        # sub_order.total_amount = snapshot total (300), не live (2997)
        from apps.orders.models import Order

        sub = Order.objects.get(parent_order=master)
        assert sub.total_amount == Decimal("300.00")

        # master.total_amount = sub totals + delivery_cost (pickup=0)
        assert master.total_amount == Decimal("300.00")

    def test_discount_amount_zero_on_master_and_subs_security_fix(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC4 + Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        discount_amount всегда 0 на мастере и субзаказах (promo-система не реализована).
        Клиентское значение discount_amount=50 игнорируется сервером.
        """
        from unittest.mock import Mock

        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("200.00"))
        product2 = product_factory.create(retail_price=Decimal("300.00"))
        variant1 = product1.variants.first()
        variant2 = product2.variants.first()
        variant1.vat_rate = Decimal("5.00")
        variant1.save()
        variant2.vat_rate = Decimal("22.00")
        variant2.save()

        cart_item_factory.create(cart=cart, product=product1, quantity=1)  # 200
        cart_item_factory.create(cart=cart, product=product2, quantity=1)  # 300
        # items_sum = 500, delivery pickup = 0; discount zeroed by server

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "50.00",  # будет проигнорирован сервером
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()

        # Server overrides discount to 0; total = items + delivery - 0 = 500
        assert master.discount_amount == Decimal("0.00")
        assert master.total_amount == Decimal("500.00")

        sub_orders = list(Order.objects.filter(parent_order=master))
        assert len(sub_orders) == 2
        for sub in sub_orders:
            assert sub.discount_amount == Decimal("0.00")

    def test_calculated_total_equals_total_amount_with_discount_zeroed(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """AC4/AC11 + Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        calculated_total совпадает с total_amount; discount_amount=0 (server override).
        Клиентское discount_amount=100 игнорируется — promo-система не реализована.
        """
        from apps.orders.models import Order

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product1 = product_factory.create(retail_price=Decimal("200.00"))
        product2 = product_factory.create(retail_price=Decimal("300.00"))
        variant1 = product1.variants.first()
        variant2 = product2.variants.first()
        variant1.vat_rate = Decimal("5.00")
        variant1.save()
        variant2.vat_rate = Decimal("22.00")
        variant2.save()

        cart_item_factory.create(cart=cart, product=product1, quantity=1)  # 200
        cart_item_factory.create(cart=cart, product=product2, quantity=1)  # 300
        # items_sum = 500, delivery pickup = 0, discount zeroed to 0
        # expected total_amount = 500, calculated_total = 500

        master = self._create_order_via_serializer(user, cart_factory, additional_data={"discount_amount": "100.00"})

        master_from_db = Order.objects.prefetch_related("sub_orders__items").get(pk=master.pk)
        data = OrderDetailSerializer(master_from_db).data

        expected = master_from_db.total_amount  # 500.00 (discount zeroed)
        assert expected == Decimal("500.00"), f"total_amount={expected}, expected 500.00"
        assert Decimal(str(data["calculated_total"])) == expected, (
            f"calculated_total={data['calculated_total']} != total_amount={expected}: "
            "serializer calculated_total должен совпадать с total_amount"
        )
        assert Decimal(str(data["calculated_total"])) == Decimal(
            str(data["total_amount"])
        ), "calculated_total и total_amount должны совпадать"
        assert Decimal(str(data["discount_amount"])) == Decimal(
            "0.00"
        ), "discount_amount должен быть 0 (server override)"

    def test_discount_amount_negative_rejected_with_validation_error(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Contract: отрицательный discount_amount явно отклоняется валидацией (400).

        Поле discount_amount присутствует в Meta.fields с min_value=0, поэтому
        отрицательные значения получают ValidationError, а не игнорируются молча.
        Клиент видит явную ошибку вместо schema drift. AC4: сервер по-прежнему
        устанавливает discount_amount=0 (promo-система не реализована).
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("200.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        # Client sends negative discount — field is in Meta.fields with min_value=0
        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "-10.00",  # rejected by min_value=0
            },
            context={"request": mock_request},
        )
        # Explicit ValidationError — not silent ignore
        assert not serializer.is_valid(), "Negative discount_amount should fail validation"
        assert "discount_amount" in serializer.errors

    def test_discount_amount_validation_exceeds_total_ignored_server_override(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        клиентский discount_amount игнорируется сервером — скидка всегда 0.
        Даже discount_amount=200 при order_total=100 принимается, но обнуляется.
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("100.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "200.00",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()
        # Server overrides discount to 0 — no unauthorized discount applied
        assert master.discount_amount == Decimal("0.00")
        assert master.total_amount == Decimal("100.00")

    def test_discount_amount_validation_equals_total_server_overrides_to_zero(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        клиентский discount_amount=total игнорируется сервером — скидка всегда 0.
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("100.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "100.00",
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()
        # Server overrides discount to 0; total_amount = 100, not 0
        assert master.discount_amount == Decimal("0.00")
        assert master.total_amount == Decimal("100.00")

    def test_arbitrary_client_discount_server_override_security_fix(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """Security regression [Story 34-2, Twenty-Seventh Follow-up, High]:
        подтверждает, что backend НЕ принимает произвольный discount_amount от клиента.

        Fix: клиентское значение discount_amount игнорируется; скидка всегда 0 на сервере
        (promo-система не реализована). Если этот тест падает — promo-система появилась;
        обновите тест для нового контракта.
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)

        product = product_factory.create(retail_price=Decimal("5000.00"))
        cart_item_factory.create(cart=cart, product=product, quantity=1)
        # order_total = 5000 (pickup, delivery=0)

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "4999.00",  # 99.98% скидка, ничем не подтверждённая
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()
        # Security fix: server overrides discount to 0
        assert master.discount_amount == Decimal("0.00")
        assert master.total_amount == Decimal("5000.00")

    def test_promo_code_stub_accepted_discount_stays_zero(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """[Review][Patch] Story 34-2: promo_code stub — поле принимается от клиента,
        discount_amount на мастере остаётся 0 (promo-система не реализована).

        AC4: discount_amount только на мастере = 0.
        Когда PromoCode-система появится, этот тест должен быть обновлён.
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("200.00"))
        variant = product.variants.first()
        variant.vat_rate = Decimal("20.00")
        variant.save()
        cart_item_factory.create(cart=cart, product=product, quantity=2)

        mock_request = Mock()
        mock_request.user = user

        serializer = OrderCreateSerializer(
            data={
                "delivery_address": "Ул. Тестовая, 1",
                "delivery_method": "pickup",
                "payment_method": "card",
                "promo_code": "SUMMER2026",  # stub: принимается, не применяется
            },
            context={"request": mock_request},
        )
        assert serializer.is_valid(), serializer.errors
        master = serializer.save()

        # promo_code не влияет на скидку — promo-система не реализована
        assert master.discount_amount == Decimal("0.00")
        assert master.total_amount == Decimal("400.00")  # 200 * 2 + pickup(0)

    def test_promo_code_stub_null_and_empty_accepted(
        self,
        user_factory,
        cart_factory,
        product_factory,
        cart_item_factory,
    ):
        """[Review][Patch] Story 34-2: promo_code=null и promo_code='' — валидны,
        backward-compatible с checkout без промокода.
        """
        from unittest.mock import Mock

        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(retail_price=Decimal("100.00"))
        variant = product.variants.first()
        variant.vat_rate = Decimal("5.00")
        variant.save()
        cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user

        for promo_value in [None, ""]:
            user2 = user_factory.create()
            cart2 = cart_factory.create(user=user2)
            cart_item_factory.create(cart=cart2, product=product, quantity=1)

            mock_req2 = Mock()
            mock_req2.user = user2

            serializer = OrderCreateSerializer(
                data={
                    "delivery_address": "Ул. Тестовая, 1",
                    "delivery_method": "pickup",
                    "payment_method": "card",
                    "promo_code": promo_value,
                },
                context={"request": mock_req2},
            )
            assert serializer.is_valid(), f"promo_code={promo_value!r} should be valid: {serializer.errors}"
            master = serializer.save()
            assert master.discount_amount == Decimal("0.00")

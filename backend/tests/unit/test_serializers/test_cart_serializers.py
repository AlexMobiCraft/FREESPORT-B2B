"""
Тесты для Cart Serializers - Story 2.6 Cart API
"""

from decimal import Decimal
from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model

from apps.cart.serializers import CartItemCreateSerializer, CartItemSerializer, CartItemUpdateSerializer, CartSerializer

User = get_user_model()


@pytest.mark.django_db
class TestCartItemSerializer:
    """Тесты сериализатора элементов корзины"""

    def test_cart_item_serialization(self, user_factory, product_factory, cart_factory, cart_item_factory):
        """Тест сериализации элемента корзины"""
        user = user_factory.create()
        product = product_factory.create(name="Тестовый товар", retail_price=Decimal("1000.00"))
        cart = cart_factory.create(user=user)
        cart_item = cart_item_factory.create(cart=cart, product=product, quantity=2)

        serializer = CartItemSerializer(cart_item)
        data = serializer.data

        assert data["product"]["name"] == "Тестовый товар"
        assert data["quantity"] == 2
        assert "total_price" in data
        assert data["unit_price"] == "1000.00"

    def test_cart_item_with_user_pricing(self, user_factory, product_factory, cart_factory, cart_item_factory):
        """Тест элемента корзины с ценообразованием для пользователя"""
        user = user_factory.create(role="retail")
        product = product_factory.create(retail_price=Decimal("1000.00"))
        cart = cart_factory.create(user=user)
        cart_item = cart_item_factory.create(cart=cart, product=product, quantity=1)

        mock_request = Mock()
        mock_request.user = user
        mock_request.build_absolute_uri = Mock(return_value="http://testserver/media/image.jpg")

        serializer = CartItemSerializer(cart_item, context={"request": mock_request})
        data = serializer.data

        # Цена берется из снимка в элементе корзины
        assert data["unit_price"] == "1000.00"

    def test_cart_item_b2b_pricing(self, user_factory, product_factory, cart_factory, cart_item_factory):
        """Тест элемента корзины с B2B ценообразованием"""
        user = user_factory.create(role="wholesale_level1")
        # Фабрика создаст вариант с opt1_price = 900.00 (по умолчанию в conftest)
        # Но мы укажем явно
        product = product_factory.create(retail_price=Decimal("1000.00"), opt1_price=Decimal("800.00"))
        cart = cart_factory.create(user=user)
        # При создании через фабрику CartItem, она берет цену из варианта
        cart_item = cart_item_factory.create(
            cart=cart,
            variant=product.variants.first(),
            quantity=5,
            price_snapshot=Decimal("800.00"),
        )

        mock_request = Mock()
        mock_request.user = user

        serializer = CartItemSerializer(cart_item, context={"request": mock_request})
        data = serializer.data

        assert data["unit_price"] == "800.00"


@pytest.mark.django_db
class TestCartSerializer:
    """Тесты сериализатора корзины"""

    def test_cart_serialization(self, user_factory, cart_factory, product_factory, cart_item_factory):
        """Тест сериализации корзины"""
        user = user_factory.create()

        expensive_product = product_factory.create(retail_price=Decimal("2000.00"))
        cheap_product = product_factory.create(retail_price=Decimal("500.00"))
        cart = cart_factory.create(user=user)
        expensive_item = cart_item_factory.create(cart=cart, product=expensive_product, quantity=1)
        cheap_item = cart_item_factory.create(cart=cart, product=cheap_product, quantity=2)

        serializer = CartSerializer(cart)
        data = serializer.data

        assert "items" in data
        assert len(data["items"]) == 2
        assert "total_amount" in data

    def test_empty_cart_serialization(self, user_factory, cart_factory):
        """Тест сериализации пустой корзины"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)

        serializer = CartSerializer(cart)
        data = serializer.data

        assert data["items"] == []
        assert data["total_amount"] == "0.00"

    def test_cart_with_multiple_items(self, user_factory, cart_factory, product_factory, cart_item_factory):
        """Тест корзины с несколькими товарами"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product1 = product_factory.create(retail_price=Decimal("1000.00"))
        product2 = product_factory.create(retail_price=Decimal("1500.00"))

        cart_item_factory.create(cart=cart, product=product1, quantity=2)
        cart_item_factory.create(cart=cart, product=product2, quantity=1)

        serializer = CartSerializer(cart)
        data = serializer.data

        assert len(data["items"]) == 2
        total = Decimal("1000.00") * 2 + Decimal("1500.00") * 1
        assert Decimal(data["total_amount"]) == total


@pytest.mark.django_db
class TestCartItemCreateSerializer:
    """Тесты сериализатора создания элемента корзины"""

    def test_cart_item_create_validation(self, user_factory, cart_factory, product_factory):
        """Тест валидации создания элемента корзины"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(name="Товар для корзины", is_active=True)
        variant = product.variants.first()

        data = {"variant_id": variant.id, "quantity": 2}

        serializer = CartItemCreateSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        cart_item = serializer.save(cart=cart)
        assert cart_item.quantity == 2
        assert cart_item.variant == variant

    def test_inactive_product_validation(self, user_factory, cart_factory, product_factory):
        """Тест валидации неактивного товара"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create(is_active=False)
        variant = product.variants.first()

        data = {"variant_id": variant.id, "quantity": 1}

        serializer = CartItemCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "variant_id" in serializer.errors

    def test_zero_quantity_validation(self, user_factory, cart_factory, product_factory):
        """Тест валидации нулевого количества"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create()
        variant = product.variants.first()

        data = {"variant_id": variant.id, "quantity": 0}

        serializer = CartItemCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors

    def test_negative_quantity_validation(self, user_factory, cart_factory, product_factory):
        """Тест валидации отрицательного количества"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create()
        variant = product.variants.first()

        data = {"variant_id": variant.id, "quantity": -1}

        serializer = CartItemCreateSerializer(data=data)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors


@pytest.mark.django_db
class TestCartItemUpdateSerializer:
    """Тесты сериализатора обновления элемента корзины"""

    def test_update_cart_item_quantity(self, user_factory, product_factory, cart_factory, cart_item_factory):
        """Тест обновления количества товара в корзине"""
        user = user_factory.create()
        product = product_factory.create()
        cart = cart_factory.create(user=user)
        cart_item = cart_item_factory.create(cart=cart, product=product, quantity=1)

        data = {"quantity": 5}

        serializer = CartItemUpdateSerializer(cart_item, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

        updated_item = serializer.save()
        assert updated_item.quantity == 5

    def test_update_cart_item_invalid_quantity(self, user_factory, cart_factory, product_factory, cart_item_factory):
        """Тест обновления с некорректным количеством"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product = product_factory.create()
        cart_item = cart_item_factory.create(cart=cart, product=product, quantity=2)

        data = {"quantity": 0}

        serializer = CartItemUpdateSerializer(cart_item, data=data, partial=True)
        assert not serializer.is_valid()
        assert "quantity" in serializer.errors


@pytest.mark.django_db
class TestCartIntegration:
    """Интеграционные тесты корзины"""

    def test_cart_workflow(self, user_factory, cart_factory, product_factory):
        """Тест полного рабочего процесса корзины"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        product1 = product_factory.create(retail_price=Decimal("100.00"), stock_quantity=10, min_order_quantity=1)
        product2 = product_factory.create(retail_price=Decimal("200.00"), stock_quantity=10, min_order_quantity=1)

        # Добавление товаров
        add_data1 = {"variant_id": product1.variants.first().id, "quantity": 2}
        add_serializer1 = CartItemCreateSerializer(data=add_data1)
        assert add_serializer1.is_valid(), add_serializer1.errors
        item1 = add_serializer1.save(cart=cart)

        add_data2 = {"variant_id": product2.variants.first().id, "quantity": 1}
        add_serializer2 = CartItemCreateSerializer(data=add_data2)
        assert add_serializer2.is_valid(), add_serializer2.errors
        item2 = add_serializer2.save(cart=cart)

        # Проверка корзины
        cart_serializer = CartSerializer(cart)
        cart_data = cart_serializer.data

        assert len(cart_data["items"]) == 2
        expected_total = Decimal("100.00") * 2 + Decimal("200.00") * 1
        assert Decimal(cart_data["total_amount"]) == expected_total

    def test_cart_performance_with_many_items(self, user_factory, cart_factory, product_factory, cart_item_factory):
        """Тест производительности корзины с множеством товаров"""
        user = user_factory.create()
        cart = cart_factory.create(user=user)
        products = product_factory.create_batch(10)

        for product in products:
            cart_item_factory.create(cart=cart, product=product, quantity=1)

        serializer = CartSerializer(cart)
        data = serializer.data

        assert len(data["items"]) == 10
        assert "total_amount" in data

"""
Integration тесты интеграции корзины и заказов
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


class CartOrderIntegrationTest(TestCase):
    """Тестирование интеграции корзины и заказов"""

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(email="test@example.com", password="testpass123", role="retail")

        # Создаем товары
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product1 = Product.objects.create(
            name="Test Product 1",
            slug="test-product-1",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant1 = ProductVariant.objects.create(
            product=self.product1,
            sku="VAR1",
            onec_id="1C-VAR1",
            retail_price=100.00,
            stock_quantity=10,
            is_active=True,
        )

        self.product2 = Product.objects.create(
            name="Test Product 2",
            slug="test-product-2",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant2 = ProductVariant.objects.create(
            product=self.product2,
            sku="VAR2",
            onec_id="1C-VAR2",
            retail_price=50.00,
            stock_quantity=5,
            is_active=True,
        )

    def test_full_cart_to_order_workflow(self):
        """Полный workflow от корзины до заказа"""
        self.client.force_authenticate(user=self.user)

        # 1. Добавляем товары в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 2})
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant2.id, "quantity": 1})

        # 2. Проверяем корзину
        cart_response = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_response.data["total_items"], 3)
        expected_total = (100.00 * 2) + (50.00 * 1)  # 250.00
        self.assertEqual(float(cart_response.data["total_amount"]), expected_total)

        # 3. Создаем заказ
        order_data = {
            "delivery_address": "Test Address 123",
            "delivery_method": "courier",
            "payment_method": "card",
            "notes": "Test order",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # 4. Проверяем, что заказ создался правильно
        order_id = order_response.data["id"]
        order_detail_response = self.client.get(f"/api/v1/orders/{order_id}/")

        self.assertEqual(len(order_detail_response.data["items"]), 2)
        self.assertEqual(order_detail_response.data["total_items"], 3)

        # 5. Проверяем, что корзина очистилась
        cart_after_order = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_after_order.data["total_items"], 0)

        # 6. Проверяем снимок данных в OrderItem
        order = Order.objects.get(id=order_id)
        order_items = order.items.all()

        for item in order_items:
            self.assertIsNotNone(item.product_name)
            self.assertIsNotNone(item.product_sku)
            self.assertGreater(item.unit_price, 0)

    def test_order_creation_preserves_cart_prices(self):
        """Создание заказа сохраняет цены из корзины"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Получаем цену из корзины
        cart_response = self.client.get("/api/v1/cart/")
        cart_price = float(cart_response.data["items"][0]["unit_price"])

        # Создаем заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)

        # Проверяем, что цена в заказе соответствует цене из корзины
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")
        order_price = float(order_detail.data["items"][0]["unit_price"])

        self.assertEqual(cart_price, order_price)

    def test_cart_validation_before_order_creation(self):
        """Валидация корзины перед созданием заказа"""
        self.client.force_authenticate(user=self.user)

        # Пытаемся создать заказ с пустой корзиной
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Корзина пуста", str(response.data))

    def test_stock_validation_during_order_creation(self):
        """Валидация остатков при создании заказа"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 2})

        # Уменьшаем остаток товара
        self.variant1.stock_quantity = 1
        self.variant1.save()

        # Пытаемся создать заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        # Заказ должен быть отклонен из-за недостатка товара
        self.assertEqual(response.status_code, 400)

    def test_transactional_integrity(self):
        """Транзакционная целостность при создании заказа"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Получаем начальное количество заказов
        initial_orders_count = Order.objects.count()
        initial_cart_items = CartItem.objects.filter(cart__user=self.user).count()

        # Деактивируем товар (эмуляция ошибки)
        self.product1.is_active = False
        self.product1.save()

        # Пытаемся создать заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        # Заказ должен быть отклонен
        self.assertEqual(response.status_code, 400)

        # Проверяем, что ничего не изменилось
        final_orders_count = Order.objects.count()
        final_cart_items = CartItem.objects.filter(cart__user=self.user).count()

        self.assertEqual(initial_orders_count, final_orders_count)
        self.assertEqual(initial_cart_items, final_cart_items)

"""
Integration тесты ролевого ценообразования
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.models import Brand, Category, Product

User = get_user_model()


class PricingIntegrationTest(TestCase):
    """Тестирование интеграции ролевого ценообразования"""

    def setUp(self):
        self.client = APIClient()

        # Создаем пользователей с разными ролями
        self.retail_user = User.objects.create_user(email="retail@example.com", password="testpass123", role="retail")
        self.wholesale_l1_user = User.objects.create_user(
            email="wholesale1@example.com",
            password="testpass123",
            role="wholesale_level1",
        )
        self.wholesale_l2_user = User.objects.create_user(
            email="wholesale2@example.com",
            password="testpass123",
            role="wholesale_level2",
        )
        self.trainer_user = User.objects.create_user(
            email="trainer@example.com", password="testpass123", role="trainer"
        )

        # Создаем товар с разными ценами
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        from apps.products.models import ProductVariant

        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            category=self.category,
            brand=self.brand,
            description="Test product for pricing integration",
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="PRICING-TEST-001",
            retail_price=1000.00,
            opt1_price=800.00,
            opt2_price=750.00,
            opt3_price=700.00,
            trainer_price=850.00,
            stock_quantity=10,
            is_active=True,
        )

    def test_product_api_role_based_pricing(self):
        """Тестирование ролевых цен в Product API"""
        test_cases = [
            (self.retail_user, 1000.00),
            (self.wholesale_l1_user, 800.00),
            (self.wholesale_l2_user, 750.00),
            (self.trainer_user, 850.00),
        ]

        for user, expected_price in test_cases:
            with self.subTest(user=user.role):
                self.client.force_authenticate(user=user)
                url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)

                current_price = float(response.data["current_price"])
                self.assertEqual(current_price, expected_price)

    def test_cart_role_based_pricing(self):
        """Тестирование ролевых цен в корзине"""
        test_cases = [
            (self.retail_user, 1000.00),
            (self.wholesale_l1_user, 800.00),
            (self.wholesale_l2_user, 750.00),
        ]

        for user, expected_price in test_cases:
            with self.subTest(user=user.role):
                self.client.force_authenticate(user=user)

                # Добавляем товар в корзину
                data = {"variant_id": self.variant.id, "quantity": 1}
                self.client.post("/api/v1/cart/items/", data)

                # Проверяем цену в корзине
                cart_response = self.client.get("/api/v1/cart/")
                cart_price = float(cart_response.data["items"][0]["unit_price"])

                self.assertEqual(cart_price, expected_price)

                # Очищаем корзину для следующего теста
                self.client.delete("/api/v1/cart/clear/")

    def test_order_preserves_role_based_pricing(self):
        """Заказ сохраняет ролевые цены"""
        self.client.force_authenticate(user=self.wholesale_l1_user)

        # Добавляем товар в корзину (цена wholesale_level1)
        data = {"variant_id": self.variant.id, "quantity": 2}
        self.client.post("/api/v1/cart/items/", data)

        # Создаем заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "bank_transfer",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # Проверяем цену в заказе
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")

        order_item_price = float(order_detail.data["items"][0]["unit_price"])
        expected_wholesale_price = 800.00

        self.assertEqual(order_item_price, expected_wholesale_price)

    def test_anonymous_user_gets_retail_prices(self):
        """Анонимные пользователи видят розничные цены"""
        # Не авторизуемся
        url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        current_price = float(response.data["current_price"])
        self.assertEqual(current_price, 1000.00)  # retail_price

    def test_b2b_user_sees_rrp_msrp(self):
        """B2B пользователи видят RRP и MSRP"""
        self.client.force_authenticate(user=self.wholesale_l1_user)
        url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # B2B пользователи должны видеть дополнительные поля
        self.assertIn("rrp", response.data)
        self.assertIn("msrp", response.data)

    def test_retail_user_does_not_see_rrp_msrp(self):
        """Розничные пользователи не видят RRP и MSRP"""
        self.client.force_authenticate(user=self.retail_user)
        url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

        # Розничные пользователи не должны видеть эти поля
        self.assertNotIn("rrp", response.data)
        self.assertNotIn("msrp", response.data)

    def test_price_consistency_across_apis(self):
        """Согласованность цен между разными API"""
        self.client.force_authenticate(user=self.wholesale_l2_user)

        # Получаем цену из Product API
        url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
        product_response = self.client.get(url)
        product_price = float(product_response.data["current_price"])

        # Добавляем в корзину и получаем цену из Cart API
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})
        cart_response = self.client.get("/api/v1/cart/")
        cart_price = float(cart_response.data["items"][0]["unit_price"])

        # Создаем заказ и получаем цену из Order API
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "bank_transfer",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")
        order_price = float(order_detail.data["items"][0]["unit_price"])

        # Все цены должны быть одинаковыми
        self.assertEqual(product_price, cart_price)
        self.assertEqual(cart_price, order_price)
        self.assertEqual(product_price, 750.00)  # opt2_price

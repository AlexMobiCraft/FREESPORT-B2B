"""
Integration тесты B2B workflow
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


class B2BWorkflowTest(TestCase):
    """Тестирование B2B рабочих процессов"""

    def setUp(self):
        self.client = APIClient()

        self.b2b_user = User.objects.create_user(
            email="b2b@example.com",
            password="testpass123",
            role="wholesale_level1",
            company_name="Test B2B Company",
            tax_id="1234567890",
        )

        # Создаем товар
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            category=self.category,
            brand=self.brand,
            description="Test product for B2B workflow",
            is_active=True,
            specifications={"test": "spec"},
        )

        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="B2B-TEST-001",
            color_name="Black",
            size_value="L",
            retail_price=1000.00,
            opt1_price=800.00,
            stock_quantity=50,
            is_active=True,
        )

    def test_full_b2b_purchase_workflow(self):
        """Полный B2B workflow покупки"""
        self.client.force_authenticate(user=self.b2b_user)

        # 1. Просмотр каталога с B2B ценами
        catalog_response = self.client.get("/api/v1/products/")
        self.assertEqual(catalog_response.status_code, 200)

        # 2. Просмотр детального товара с RRP/MSRP
        product_response = self.client.get(f"/api/v1/products/{self.product.slug}/")
        self.assertEqual(product_response.status_code, 200)
        self.assertEqual(float(product_response.data["opt1_price"]), 800.00)
        self.assertIn("retail_price", product_response.data)

        # 3. Добавление товара в корзину (минимальное количество)
        cart_data = {
            "variant_id": self.variant.id,
            "quantity": 5,
        }
        cart_response = self.client.post("/api/v1/cart/items/", cart_data)
        self.assertEqual(cart_response.status_code, 201, f"Cart error: {cart_response.data}")

        # 4. Проверка корзины с B2B ценами
        cart_check = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_check.data["total_items"], 5)
        expected_total = 800.00 * 5
        self.assertEqual(float(cart_check.data["total_amount"]), expected_total)

        # 5. Создание заказа с B2B способом оплаты
        order_data = {
            "delivery_address": "Business Address 123",
            "delivery_method": "transport_company",
            "payment_method": "bank_transfer",  # B2B способ оплаты
            "notes": "B2B order for Test Company",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201, f"Order error: {order_response.data}")

        # 6. Проверка созданного заказа
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")

        self.assertEqual(order_detail.data["payment_method"], "bank_transfer")
        self.assertEqual(len(order_detail.data["items"]), 1)
        self.assertEqual(order_detail.data["items"][0]["quantity"], 5)

    def test_b2b_payment_method_validation(self):
        """Валидация способов оплаты для B2B"""
        self.client.force_authenticate(user=self.b2b_user)

        # Добавляем товар в корзину
        cart_data = {"variant_id": self.variant.id, "quantity": 5}
        self.client.post("/api/v1/cart/items/", cart_data)

        # Пытаемся создать заказ с недопустимым способом оплаты
        order_data = {
            "delivery_address": "Business Address",
            "delivery_method": "courier",
            "payment_method": "card",  # Недопустимо для B2B
            "notes": "Test order",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("оптовых покупателей", str(response.data))

    def test_b2b_dashboard_specific_data(self):
        """B2B специфичные данные в дашборде"""
        self.client.force_authenticate(user=self.b2b_user)

        response = self.client.get("/api/v1/users/profile/dashboard/")
        self.assertEqual(response.status_code, 200)

        # B2B пользователи должны видеть дополнительную информацию
        self.assertIn("user_info", response.data)
        self.assertIn("company_name", response.data["user_info"])
        self.assertEqual(response.data["user_info"]["company_name"], "Test B2B Company")

    def test_b2b_bulk_operations(self):
        """B2B операции с большими объемами"""
        self.client.force_authenticate(user=self.b2b_user)

        # Добавляем большое количество товара
        cart_data = {"variant_id": self.variant.id, "quantity": 25}
        response = self.client.post("/api/v1/cart/items/", cart_data)
        self.assertEqual(response.status_code, 201)

        # Проверяем расчет общей суммы
        cart_response = self.client.get("/api/v1/cart/")
        expected_total = 800.00 * 25
        self.assertEqual(float(cart_response.data["total_amount"]), expected_total)

    def test_b2b_delivery_methods(self):
        """B2B способы доставки"""
        self.client.force_authenticate(user=self.b2b_user)

        # Добавляем товар
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 10})

        # Тестируем B2B способы доставки
        b2b_delivery_methods = ["transport_company", "pickup"]

        for delivery_method in b2b_delivery_methods:
            with self.subTest(delivery_method=delivery_method):
                order_data = {
                    "delivery_address": "Business Address",
                    "delivery_method": delivery_method,
                    "payment_method": "bank_transfer",
                }
                response = self.client.post("/api/v1/orders/", order_data)

                if response.status_code == 201:
                    # Если заказ создался, удаляем его для следующего теста
                    order_id = response.data["id"]
                    # TODO: Добавить метод удаления заказа или отмены

                # Восстанавливаем корзину если она очистилась
                cart_check = self.client.get("/api/v1/cart/")
                if cart_check.data["total_items"] == 0:
                    self.client.post(
                        "/api/v1/cart/items/",
                        {"variant_id": self.variant.id, "quantity": 10},
                    )

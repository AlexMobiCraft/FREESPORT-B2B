"""
Integration тесты B2C workflow
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Brand, Category, Product, ProductVariant
from apps.users.models import Favorite

User = get_user_model()


@pytest.mark.xdist_group(name="b2c_workflow")
class B2CWorkflowTest(TestCase):
    """Тестирование B2C рабочих процессов"""

    def setUp(self):
        self.client = APIClient()

        self.retail_user = User.objects.create_user(
            email="retail@example.com",
            password="testpass123",
            role="retail",
            first_name="John",
            last_name="Doe",
        )

        # Создаем товар
        self.category = Category.objects.create(name="Sports Equipment", slug="sports-equipment")
        self.brand = Brand.objects.create(name="Nike", slug="nike")
        self.product = Product.objects.create(
            name="Running Shoes",
            slug="running-shoes",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="B2C-RUN-001",
            color_name="Red",
            size_value="42",
            retail_price=150.00,
            stock_quantity=20,
            is_active=True,
        )
        # Очищаем все избранное и связанные данные
        Favorite.objects.all().delete()

    def tearDown(self):
        """Очистка после каждого теста"""
        Favorite.objects.all().delete()

    def test_full_b2c_purchase_workflow(self):
        """Полный B2C workflow покупки"""
        self.client.force_authenticate(user=self.retail_user)

        # 1. Просмотр дашборда
        dashboard_response = self.client.get("/api/v1/users/profile/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)

        # 2. Просмотр детального товара (без RRP/MSRP для B2C)
        product_response = self.client.get(f"/api/v1/products/{self.product.slug}/")
        self.assertEqual(product_response.status_code, 200)
        self.assertEqual(float(product_response.data["retail_price"]), 150.00)

        # B2C пользователи не должны видеть оптовые поля
        self.assertNotIn("rrp", product_response.data)
        self.assertNotIn("msrp", product_response.data)

        # 3. Добавление товара в корзину
        cart_data = {"variant_id": self.variant.id, "quantity": 2}
        cart_response = self.client.post("/api/v1/cart/items/", cart_data)
        self.assertEqual(cart_response.status_code, 201)

        # 4. Проверка корзины
        cart_check = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_check.data["total_items"], 2)
        expected_total = 150.00 * 2
        self.assertEqual(float(cart_check.data["total_amount"]), expected_total)

        # 5. Создание заказа с B2C способом оплаты
        order_data = {
            "delivery_address": "Home Address 456",
            "delivery_method": "courier",
            "payment_method": "card",  # B2C способ оплаты
            "notes": "Please deliver after 6 PM",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # 6. Проверка созданного заказа
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")

        self.assertEqual(order_detail.data["payment_method"], "card")
        self.assertEqual(len(order_detail.data["items"]), 1)
        self.assertEqual(order_detail.data["items"][0]["quantity"], 2)

        # 7. Проверка, что корзина очистилась
        final_cart = self.client.get("/api/v1/cart/")
        self.assertEqual(final_cart.data["total_items"], 0)

    def test_guest_user_workflow(self):
        """Workflow для гостевых пользователей"""
        # Не авторизуемся

        # 1. Просмотр каталога как гость
        catalog_response = self.client.get("/api/v1/products/")
        self.assertEqual(catalog_response.status_code, 200)

        # 2. Просмотр товара с розничными ценами
        product_response = self.client.get(f"/api/v1/products/{self.product.slug}/")
        self.assertEqual(product_response.status_code, 200)
        self.assertEqual(float(product_response.data["retail_price"]), 150.00)

        # 3. Добавление в гостевую корзину
        cart_data = {"variant_id": self.variant.id, "quantity": 1}
        cart_response = self.client.post("/api/v1/cart/items/", cart_data)
        self.assertEqual(cart_response.status_code, 201)

        # 4. Проверка гостевой корзины
        cart_check = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_check.data["total_items"], 1)

        # 5. Попытка создать заказ (должна требовать авторизации)
        order_data = {
            "delivery_address": "Guest Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
            "customer_name": "Guest User",
            "customer_email": "guest@example.com",
            "customer_phone": "+7900123456",
        }
        # TODO: Определить, требует ли система авторизации для заказов
        # order_response = self.client.post('/api/v1/orders/', order_data)

    def test_b2c_payment_methods(self):
        """B2C способы оплаты"""
        self.client.force_authenticate(user=self.retail_user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})

        # Тестируем B2C способы оплаты
        b2c_payment_methods = ["card", "cash", "payment_on_delivery"]

        for payment_method in b2c_payment_methods:
            with self.subTest(payment_method=payment_method):
                order_data = {
                    "delivery_address": "Home Address",
                    "delivery_method": "courier",
                    "payment_method": payment_method,
                }
                response = self.client.post("/api/v1/orders/", order_data)

                # Все B2C способы оплаты должны быть допустимы
                self.assertEqual(response.status_code, 201)

                # Восстанавливаем корзину для следующего теста
                self.client.post(
                    "/api/v1/cart/items/",
                    {"variant_id": self.variant.id, "quantity": 1},
                )

    def test_b2c_delivery_methods(self):
        """B2C способы доставки"""
        self.client.force_authenticate(user=self.retail_user)

        # Добавляем товар
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})

        # Тестируем B2C способы доставки
        b2c_delivery_methods = ["courier", "pickup", "post"]

        for delivery_method in b2c_delivery_methods:
            with self.subTest(delivery_method=delivery_method):
                order_data = {
                    "delivery_address": "Home Address",
                    "delivery_method": delivery_method,
                    "payment_method": "card",
                }
                response = self.client.post("/api/v1/orders/", order_data)

                self.assertEqual(response.status_code, 201)

                # Восстанавливаем корзину
                self.client.post(
                    "/api/v1/cart/items/",
                    {"variant_id": self.variant.id, "quantity": 1},
                )

    def test_b2c_order_without_minimum_quantity(self):
        """B2C заказы без минимального количества"""
        self.client.force_authenticate(user=self.retail_user)

        # B2C пользователи могут заказывать по 1 штуке
        cart_data = {
            "variant_id": self.variant.id,
            "quantity": 1,  # Минимальное количество для retail
        }
        response = self.client.post("/api/v1/cart/items/", cart_data)
        self.assertEqual(response.status_code, 201)

    def test_b2c_personal_cabinet_features(self):
        """B2C функции личного кабинета"""
        # Очищаем избранное перед тестом
        Favorite.objects.filter(user=self.retail_user).delete()

        self.client.force_authenticate(user=self.retail_user)

        # Дашборд
        dashboard_response = self.client.get("/api/v1/users/profile/dashboard/")
        self.assertEqual(dashboard_response.status_code, 200)

        # B2C пользователи не должны видеть B2B поля
        self.assertNotIn("company_name", dashboard_response.data.get("user_info", {}))
        self.assertNotIn("tax_id", dashboard_response.data.get("user_info", {}))

        # Избранное
        favorite_data = {"product": self.product.id}
        favorite_response = self.client.post("/api/v1/users/favorites/", favorite_data)
        self.assertEqual(favorite_response.status_code, 201)

        # Список избранного - проверяем только для текущего пользователя
        favorites_list = self.client.get("/api/v1/users/favorites/")
        self.assertEqual(favorites_list.status_code, 200)
        product_ids_in_favorites = [item["product"] for item in favorites_list.data["results"]]
        self.assertIn(self.product.id, product_ids_in_favorites)
        self.assertEqual(Favorite.objects.filter(user=self.retail_user).count(), 1)

    def test_b2c_quick_reorder(self):
        """Быстрый повторный заказ для B2C"""
        self.client.force_authenticate(user=self.retail_user)

        # Создаем первый заказ
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})

        order_data = {
            "delivery_address": "Home Address",
            "delivery_method": "courier",
            "payment_method": "card",
        }
        first_order = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(first_order.status_code, 201)

        # Проверяем, что можем легко повторить заказ
        # (добавляя тот же товар снова)
        repeat_cart = self.client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})
        self.assertEqual(repeat_cart.status_code, 201)

        second_order = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(second_order.status_code, 201)

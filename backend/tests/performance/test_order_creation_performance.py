"""
Performance тесты создания заказов
"""

import time

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.factories import ProductVariantFactory
from apps.products.models import Brand, Category, Product

User = get_user_model()


class OrderCreationPerformanceTest(TestCase):
    """Тестирование производительности создания заказов"""

    def setUp(self):
        self.client = APIClient()

        # Создаем пользователей
        self.retail_user = User.objects.create_user(
            email="perf_retail@example.com", password="testpass123", role="retail"
        )
        self.wholesale_user = User.objects.create_user(
            email="perf_wholesale@example.com",
            password="testpass123",
            role="wholesale_level1",
            company_name="Performance Test Company",
            tax_id="1234567890",
        )

        # Создаем товары для тестов
        self.category = Category.objects.create(name="Performance Category", slug="performance-category")
        self.brand = Brand.objects.create(name="Performance Brand", slug="performance-brand")

        self.products = []
        for i in range(20):
            variant = ProductVariantFactory.create(
                product__name=f"Performance Product {i}",
                product__slug=f"performance-product-{i}",
                product__category=self.category,
                product__brand=self.brand,
                product__description=f"Test product {i} for performance testing",
                retail_price=100.00 + i * 10,
                opt1_price=80.00 + i * 8,
                stock_quantity=100,
                product__min_order_quantity=1,
                product__is_active=True,
                sku=f"PERF-{i:03d}",
            )
            self.products.append(variant)

        # Очищаем корзину перед каждым тестом для обоих пользователей
        self.client.force_authenticate(user=self.retail_user)
        self.client.delete("/api/v1/cart/clear/")
        self.client.force_authenticate(user=self.wholesale_user)
        self.client.delete("/api/v1/cart/clear/")

    def test_single_item_order_performance(self):
        """Производительность создания заказа с одним товаром"""
        self.client.force_authenticate(user=self.retail_user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.products[0].id, "quantity": 1})

        # Создаем заказ и измеряем время
        start_time = time.time()

        order_data = {
            "delivery_address": "Test Address 123",
            "delivery_method": "courier",
            "payment_method": "card",
            "notes": "Performance test order",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            2.0,
            f"Single item order creation time {response_time:.2f}s exceeds 2s limit",
        )
        self.assertEqual(response.status_code, 201)

        # Проверяем, что заказ создался корректно
        response_data = response.json()
        self.assertIn("id", response_data)
        self.assertEqual(len(response_data["items"]), 1)

    def test_multiple_items_order_performance(self):
        """Производительность создания заказа с несколькими товарами"""
        self.client.force_authenticate(user=self.retail_user)

        # Добавляем 5 разных товаров в корзину
        for i in range(5):
            self.client.post(
                "/api/v1/cart/items/",
                {"variant_id": self.products[i].id, "quantity": 2},
            )

        # Создаем заказ
        start_time = time.time()

        order_data = {
            "delivery_address": "Multi-item Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            2.5,
            f"Multi-item order creation time {response_time:.2f}s exceeds 2.5s limit",
        )
        self.assertEqual(response.status_code, 201)
        response_data = response.json()
        self.assertEqual(len(response_data["items"]), 5)

    def test_b2b_order_performance(self):
        """Производительность создания B2B заказа"""
        self.client.force_authenticate(user=self.wholesale_user)

        # Добавляем товар с минимальным B2B количеством
        self.client.post("/api/v1/cart/items/", {"variant_id": self.products[0].id, "quantity": 10})

        start_time = time.time()

        order_data = {
            "delivery_address": "B2B Business Address",
            "delivery_method": "transport_company",
            "payment_method": "bank_transfer",
            "notes": "B2B order performance test",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            2.0,
            f"B2B order creation time {response_time:.2f}s exceeds 2.0s limit",
        )
        self.assertEqual(response.status_code, 201)

    def test_large_quantity_order_performance(self):
        """Производительность заказа с большим количеством"""
        self.client.force_authenticate(user=self.wholesale_user)

        # Добавляем товар с большим количеством
        self.client.post("/api/v1/cart/items/", {"variant_id": self.products[0].id, "quantity": 50})

        start_time = time.time()

        order_data = {
            "delivery_address": "Large Quantity Address",
            "delivery_method": "transport_company",
            "payment_method": "bank_transfer",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            2.5,
            (f"Large quantity order creation time {response_time:.2f}s " "exceeds 2.5s limit"),
        )
        self.assertEqual(response.status_code, 201)

    def test_order_calculation_performance(self):
        """Производительность расчета итогов заказа"""
        self.client.force_authenticate(user=self.retail_user)

        # Добавляем товары с разными ценами
        for i in range(10):
            self.client.post(
                "/api/v1/cart/items/",
                {"variant_id": self.products[i].id, "quantity": i + 1},
            )

        start_time = time.time()

        order_data = {
            "delivery_address": "Calculation Test Address",
            "delivery_method": "courier",
            "payment_method": "card",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            3.0,
            f"Order calculation time {response_time:.2f}s exceeds 3s limit",
        )
        self.assertEqual(response.status_code, 201)

        # Проверяем корректность расчетов
        response_data = response.json()
        self.assertGreater(float(response_data["total_amount"]), 0)
        self.assertEqual(len(response_data["items"]), 10)

    @pytest.mark.slow
    def test_concurrent_order_creation_performance(self):
        """Последовательное создание заказов для проверки производительности"""
        results = []

        # Создаем 3 заказа последовательно для разных пользователей
        users_products = [
            (self.retail_user, self.products[0].id),
            (self.wholesale_user, self.products[1].id),
            (self.retail_user, self.products[2].id),
        ]

        start_time = time.time()

        for i, (user, product_id) in enumerate(users_products):
            client = APIClient()
            client.force_authenticate(user=user)

            # Добавляем товар
            cart_response = client.post("/api/v1/cart/items/", {"variant_id": product_id, "quantity": 1})
            self.assertEqual(cart_response.status_code, 201, f"Cart creation failed for user {i}")

            # Создаем заказ
            order_start_time = time.time()

            order_data = {
                "delivery_address": f"Sequential Address {i}",
                "delivery_method": "pickup",
                "payment_method": "cash" if user.role == "retail" else "bank_transfer",
            }
            response = client.post("/api/v1/orders/", order_data)

            order_end_time = time.time()
            response_time = order_end_time - order_start_time

            results.append(
                {
                    "status_code": response.status_code,
                    "response_time": response_time,
                    "user_id": user.id,
                }
            )

        total_time = time.time() - start_time

        self.assertEqual(len(results), 3)

        # Все заказы должны создаться успешно
        for i, result in enumerate(results):
            self.assertEqual(result["status_code"], 201, f"Order {i} creation failed")
            self.assertLess(
                result["response_time"],
                5.0,
                f"Order {i} creation time exceeds 5s",
            )

        avg_response_time = sum(r["response_time"] for r in results) / len(results)

        print("Sequential order creation results:")
        print(f"Total time: {total_time:.3f}s")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max(r['response_time'] for r in results):.3f}s")

    def test_order_database_queries_optimization(self):
        """Оптимизация запросов к БД при создании заказа"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        self.client.force_authenticate(user=self.retail_user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.products[0].id, "quantity": 2})

        connection.queries_log.clear()

        with CaptureQueriesContext(connection) as ctx:
            order_data = {
                "delivery_address": "Query Optimization Address",
                "delivery_method": "courier",
                "payment_method": "card",
            }
            response = self.client.post("/api/v1/orders/", order_data)

        queries_count = len(ctx.captured_queries)

        # Создание заказа не должно генерировать слишком много запросов
        self.assertLess(
            queries_count,
            30,
            f"Order creation generates too many DB queries: {queries_count}",
        )
        self.assertEqual(response.status_code, 201)

        print(f"Order creation database queries count: {queries_count}")

    def test_order_memory_usage(self):
        """Использование памяти при создании заказа"""
        import tracemalloc

        self.client.force_authenticate(user=self.retail_user)

        # Добавляем несколько товаров
        for i in range(5):
            self.client.post(
                "/api/v1/cart/items/",
                {"variant_id": self.products[i].id, "quantity": 2},
            )

        tracemalloc.start()

        order_data = {
            "delivery_address": "Memory Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_mb = peak / 1024 / 1024
        self.assertLess(
            memory_mb,
            40,
            f"Order creation memory usage {memory_mb:.2f}MB exceeds 40MB limit",
        )

        self.assertEqual(response.status_code, 201)

        print(f"Order creation memory usage: {memory_mb:.2f}MB")

"""
Performance тесты каталога товаров
"""

import time

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.factories import ProductVariantFactory
from apps.products.models import Brand, Category, Product

User = get_user_model()


class CatalogPerformanceTest(TestCase):
    """Тестирование производительности каталога"""

    def setUp(self):
        self.client = APIClient()

        # Создаем тестовых пользователей
        self.user = User.objects.create_user(email="perf@example.com", password="testpass123")

        # Создаем структуру для performance тестов
        self.categories = []
        self.brands = []
        self.products = []

        # Создаем 10 категорий
        for i in range(10):
            category = Category.objects.create(name=f"Category {i}", slug=f"category-{i}")
            self.categories.append(category)

        # Создаем 5 брендов
        for i in range(5):
            brand = Brand.objects.create(name=f"Brand {i}", slug=f"brand-{i}")
            self.brands.append(brand)

        # Создаем 100 товаров для performance тестирования
        for i in range(100):
            variant = ProductVariantFactory.create(
                product__name=f"Product {i}",
                product__slug=f"product-{i}",
                product__category=self.categories[i % 10],
                product__brand=self.brands[i % 5],
                retail_price=100.00 + i,
                stock_quantity=50,
                product__is_active=True,
            )
            self.products.append(variant.product)

    def test_catalog_list_performance(self):
        """Тестирование производительности списка товаров"""
        start_time = time.time()

        response = self.client.get("/api/v1/products/")

        end_time = time.time()
        response_time = end_time - start_time

        # Каталог должен загружаться быстро
        self.assertLess(
            response_time,
            1.0,
            f"Catalog response time {response_time:.2f}s exceeds 1s limit",
        )
        self.assertEqual(response.status_code, 200)

        # Проверяем количество товаров в ответе
        response_data = response.json()
        self.assertGreaterEqual(len(response_data["results"]), 10)

    def test_catalog_with_filters_performance(self):
        """Производительность каталога с фильтрами"""
        start_time = time.time()

        # Тестируем фильтрацию по категории
        response = self.client.get(
            "/api/v1/products/",
            {"category_id": self.categories[0].id, "min_price": 100, "max_price": 200},
        )

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.5,
            f"Filtered catalog response time {response_time:.2f}s exceeds 1.5s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_product_detail_performance(self):
        """Производительность детальной страницы товара"""
        product = self.products[0]

        start_time = time.time()

        response = self.client.get(f"/api/v1/products/{product.slug}/")

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.5,
            f"Product detail response time {response_time:.2f}s exceeds 1.5s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_categories_tree_performance(self):
        """Производительность дерева категорий"""
        start_time = time.time()

        response = self.client.get("/api/v1/categories-tree/")

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.0,
            f"Categories tree response time {response_time:.2f}s exceeds 1.0s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_brands_list_performance(self):
        """Производительность списка брендов"""
        start_time = time.time()

        response = self.client.get("/api/v1/brands/")

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.0,
            f"Brands list response time {response_time:.2f}s exceeds 1.0s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_catalog_pagination_performance(self):
        """Производительность пагинации каталога"""
        # Тестируем первую страницу
        start_time = time.time()

        response = self.client.get("/api/v1/products/", {"page": 1, "page_size": 20})

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.0,
            f"Pagination response time {response_time:.2f}s exceeds 1s limit",
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(len(response_data["results"]), 20)

    def test_role_based_pricing_performance(self):
        """Производительность ролевого ценообразования"""
        self.client.force_authenticate(user=self.user)

        start_time = time.time()

        # Запрашиваем каталог с ролевыми ценами
        response = self.client.get("/api/v1/products/")

        end_time = time.time()
        response_time = end_time - start_time

        # Ролевое ценообразование не должно значительно замедлять запросы
        self.assertLess(
            response_time,
            1.2,
            f"Role-based pricing response time {response_time:.2f}s exceeds 1.2s limit",
        )
        self.assertEqual(response.status_code, 200)

    @pytest.mark.slow
    def test_catalog_stress_test(self):
        """Стресс-тест каталога (множественные запросы)"""
        response_times = []

        # Выполняем 10 запросов подряд
        for i in range(10):
            start_time = time.time()

            response = self.client.get("/api/v1/products/")

            end_time = time.time()
            response_time = end_time - start_time
            response_times.append(response_time)

            self.assertEqual(response.status_code, 200)

        # Проверяем среднее время ответа
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        self.assertLess(
            avg_response_time,
            1.0,
            f"Average response time {avg_response_time:.2f}s exceeds 1s",
        )
        self.assertLess(
            max_response_time,
            2.0,
            f"Max response time {max_response_time:.2f}s exceeds 2s",
        )

        print("Stress test results:")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Min response time: {min(response_times):.3f}s")

    def test_memory_usage_catalog(self):
        """Тестирование использования памяти"""
        import tracemalloc

        tracemalloc.start()

        # Запрашиваем каталог
        response = self.client.get("/api/v1/products/")

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Проверяем, что использование памяти разумное
        memory_mb = peak / 1024 / 1024
        self.assertLess(memory_mb, 50, f"Memory usage {memory_mb:.2f}MB exceeds 50MB limit")

        self.assertEqual(response.status_code, 200)

        print(f"Memory usage: {memory_mb:.2f}MB")

    def test_database_queries_count(self):
        """Тестирование количества запросов к БД"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        # Сбрасываем счетчик запросов (хотя для CaptureQueriesContext это не критично)
        connection.queries_log.clear()

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/v1/products/")

        queries_count = len(ctx.captured_queries)

        # Каталог не должен выполнять слишком много запросов
        self.assertLess(queries_count, 10, f"Too many DB queries: {queries_count}")
        self.assertEqual(response.status_code, 200)

        print(f"Database queries count: {queries_count}")

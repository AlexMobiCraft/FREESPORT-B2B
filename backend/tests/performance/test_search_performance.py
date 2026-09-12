"""
Performance тесты поисковой системы
"""

import time

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.factories import ProductVariantFactory
from apps.products.models import Brand, Category, Product

User = get_user_model()


@pytest.mark.django_db
class SearchPerformanceTest(TestCase):
    """Тестирование производительности поиска"""

    def setUp(self):
        self.client = APIClient()

        # Создаем структуру для search performance тестов
        self.categories = []
        self.brands = []
        self.products = []

        # Создаем 5 категорий
        for i in range(5):
            category = Category.objects.create(name=f"Search Category {i}", slug=f"search-category-{i}")
            self.categories.append(category)

        # Создаем 3 бренда
        for i in range(3):
            brand = Brand.objects.create(name=f"Search Brand {i}", slug=f"search-brand-{i}")
            self.brands.append(brand)

        # Создаем 200 товаров для тестирования поиска
        search_terms = ["футбол", "баскетбол", "теннис", "волейбол", "хоккей"]
        for i in range(200):
            term = search_terms[i % len(search_terms)]
            variant = ProductVariantFactory.create(
                product__name=f"{term} Product {i}",
                product__slug=f"{term.lower()}-product-{i}",
                product__category=self.categories[i % 5],
                product__brand=self.brands[i % 3],
                product__description=f"Описание товара для {term} номер {i}",
                retail_price=100.00 + i,
                stock_quantity=20,
                product__is_active=True,
            )
            self.products.append(variant.product)

    def test_simple_search_performance(self):
        """Производительность простого поиска"""
        start_time = time.time()

        response = self.client.get("/api/v1/products/", {"search": "футбол"})

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.5,
            f"Simple search response time {response_time:.2f}s exceeds 1.5s limit",
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertGreater(len(response_data["results"]), 0)

    def test_complex_search_performance(self):
        """Производительность сложного поиска с фильтрами"""
        start_time = time.time()

        response = self.client.get(
            "/api/v1/products/",
            {
                "search": "баскетбол",
                "category_id": self.categories[0].id,
                "min_price": 100,
                "max_price": 300,
                "in_stock": "true",
            },
        )

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.0,
            f"Complex search response time {response_time:.2f}s exceeds 1s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_full_text_search_performance(self):
        """Производительность полнотекстового поиска"""
        start_time = time.time()

        response = self.client.get("/api/v1/products/", {"search": "Описание товара для теннис"})

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.5,
            f"Full text search response time {response_time:.2f}s exceeds 1.5s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_empty_search_performance(self):
        """Производительность поиска без результатов"""
        start_time = time.time()

        response = self.client.get("/api/v1/products/", {"search": "несуществующий_товар_xyz123"})

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.0,
            f"Empty search response time {response_time:.2f}s exceeds 1.0s limit",
        )
        self.assertEqual(response.status_code, 200)
        response_data = response.json()
        self.assertEqual(len(response_data["results"]), 0)

    def test_search_pagination_performance(self):
        """Производительность пагинации поиска"""
        start_time = time.time()

        response = self.client.get("/api/v1/products/", {"search": "Product", "page": 2, "page_size": 20})

        end_time = time.time()
        response_time = end_time - start_time

        self.assertLess(
            response_time,
            1.5,
            f"Search pagination response time {response_time:.2f}s exceeds 1.5s limit",
        )
        self.assertEqual(response.status_code, 200)

    def test_search_sorting_performance(self):
        """Производительность сортировки результатов поиска"""
        sorting_options = ["name", "-name", "retail_price", "-retail_price"]

        for sort_by in sorting_options:
            with self.subTest(sort_by=sort_by):
                start_time = time.time()

                response = self.client.get("/api/v1/products/", {"search": "Product", "ordering": sort_by})

                end_time = time.time()
                response_time = end_time - start_time
                self.assertLess(
                    response_time,
                    1.5,
                    (f"Search sorting by {sort_by} response time " f"{response_time:.2f}s exceeds 1.5s limit"),
                )
                self.assertEqual(response.status_code, 200)

    @pytest.mark.slow
    def test_search_stress_test(self):
        """Стресс-тест поисковой системы"""
        search_queries = ["футбол", "баскетбол", "теннис", "Product", "Brand"]
        response_times = []

        # Выполняем 20 поисковых запросов
        for i in range(20):
            query = search_queries[i % len(search_queries)]

            start_time = time.time()

            response = self.client.get("/api/v1/products/", {"search": query})

            end_time = time.time()
            response_time = end_time - start_time
            response_times.append(response_time)

            self.assertEqual(response.status_code, 200)

        # Анализируем результаты
        avg_response_time = sum(response_times) / len(response_times)
        max_response_time = max(response_times)

        self.assertLess(
            avg_response_time,
            0.6,
            f"Average search response time {avg_response_time:.2f}s exceeds 0.6s",
        )
        self.assertLess(
            max_response_time,
            1.5,
            f"Max search response time {max_response_time:.2f}s exceeds 1.5s",
        )

        print("Search stress test results:")
        print(f"Average response time: {avg_response_time:.3f}s")
        print(f"Max response time: {max_response_time:.3f}s")
        print(f"Min response time: {min(response_times):.3f}s")

    def test_search_database_queries_optimization(self):
        """Оптимизация запросов к БД при поиске"""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        connection.queries_log.clear()

        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get("/api/v1/products/", {"search": "футбол"})

        queries_count = len(ctx.captured_queries)

        # Поиск не должен генерировать слишком много запросов
        self.assertLess(queries_count, 15, f"Search generates too many DB queries: {queries_count}")
        self.assertEqual(response.status_code, 200)

        print(f"Search database queries count: {queries_count}")

    def test_search_memory_usage(self):
        """Использование памяти при поиске"""
        import tracemalloc

        tracemalloc.start()

        # Выполняем поисковый запрос
        response = self.client.get("/api/v1/products/", {"search": "Product"})

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        memory_mb = peak / 1024 / 1024
        self.assertLess(memory_mb, 30, f"Search memory usage {memory_mb:.2f}MB exceeds 30MB limit")

        self.assertEqual(response.status_code, 200)

        print(f"Search memory usage: {memory_mb:.2f}MB")

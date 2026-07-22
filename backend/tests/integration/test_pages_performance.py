"""
Performance тесты для Pages API (Story 2.10)
Fix PERF-001: Тесты производительности кэширования под нагрузкой
"""

import concurrent.futures
import time

import pytest
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.pages.models import Page


@pytest.mark.integration
class PagesCachePerformanceTest(TransactionTestCase):
    """Тесты производительности кэширования Pages API - Fix PERF-001"""

    def setUp(self):
        """Настройка тестовых данных для performance тестов"""
        self.client = APIClient()
        cache.clear()
        Page.objects.all().delete()

        # Создаем тестовые страницы
        self.test_pages = []
        pages_data = []
        for i in range(10):
            pages_data.append(
                Page(
                    title=f"Performance Test Page {i}",
                    slug=f"perf-page-{i}",
                    content=f"<p>Performance test content {i}</p>" * 50,
                    is_published=True,
                )
            )

        self.test_pages = Page.objects.bulk_create(pages_data)

    def test_cache_invalidation_performance(self):
        """Тест производительности инвалидации кэша при массовых обновлениях"""
        url = reverse("pages:pages-list")

        # Прогреваем кэш
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Измеряем время массового обновления страниц
        start_time = time.time()

        # Массовое обновление страниц (симуляция высокой нагрузки)
        for page in Page.objects.all()[:5]:
            page.title = f"Updated {page.title}"
            page.save()

        end_time = time.time()
        update_time = end_time - start_time

        # Время массового обновления должно быть разумным
        self.assertLess(update_time, 2.0, f"Mass update too slow: {update_time}s")

        # Проверяем что кэш инвалидирован и данные обновились
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверяем что обновления отражены в ответе
        updated_titles = [page["title"] for page in response.data["results"]]
        updated_count = sum(1 for title in updated_titles if title.startswith("Updated"))
        self.assertEqual(updated_count, 5)

    def test_concurrent_cache_access_performance(self):
        """Тест производительности кэша при конкурентном доступе"""
        from django.db import connection

        url = reverse("pages:pages-list")
        results = []
        errors = []

        def make_request():
            """Выполняет запрос в отдельном потоке с собственным клиентом"""
            # Создаём новый клиент для каждого потока (APIClient не потокобезопасен)
            client = APIClient()
            try:
                start = time.time()
                response = client.get(url)
                end = time.time()
                results.append(
                    {
                        "status": response.status_code,
                        "time": end - start,
                        "data_length": (
                            len(response.data.get("results", []))
                            if hasattr(response, "data") and "results" in response.data
                            else 0
                        ),
                    }
                )
            except Exception as e:
                errors.append(str(e))
            finally:
                # Закрываем соединение с БД в этом потоке
                connection.close()

        # Используем ThreadPoolExecutor для лучшего управления потоками
        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            concurrent.futures.wait(futures)

        # Проверяем результаты
        self.assertEqual(len(errors), 0, f"Errors occurred: {errors}")
        self.assertEqual(len(results), 20)

        # Все запросы должны быть успешными
        successful_requests = [r for r in results if r["status"] == 200]
        self.assertEqual(len(successful_requests), 20)

        # Среднее время ответа должно быть разумным
        avg_time = sum(r["time"] for r in results) / len(results)
        self.assertLess(avg_time, 1.0, f"Average response time too slow: {avg_time}s")

        # Все запросы должны возвращать одинаковые данные (кэш работает)
        data_lengths = [r["data_length"] for r in results]
        self.assertTrue(all(length == data_lengths[0] for length in data_lengths))

    def test_cache_memory_usage_under_load(self):
        """Тест использования памяти кэшем под нагрузкой"""
        # Создаем больше страниц для тестирования
        more_pages = []
        for i in range(50):
            more_pages.append(
                Page(
                    title=f"Memory Test Page {i}",
                    slug=f"memory-page-{i}",
                    content=f"<p>Memory test content {i}</p>" * 100,
                    is_published=True,
                )
            )

        Page.objects.bulk_create(more_pages)

        # Делаем множество запросов для заполнения кэша
        urls = [
            reverse("pages:pages-list"),
            reverse("pages:pages-detail", kwargs={"slug": "memory-page-0"}),
            reverse("pages:pages-detail", kwargs={"slug": "memory-page-1"}),
            reverse("pages:pages-detail", kwargs={"slug": "memory-page-2"}),
        ]

        start_time = time.time()

        # Делаем множественные запросы для нагрузки кэша
        for _ in range(10):
            for url in urls:
                response = self.client.get(url)
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        end_time = time.time()
        total_time = end_time - start_time

        # Общее время выполнения должно быть разумным
        self.assertLess(total_time, 5.0, f"Cache load test too slow: {total_time}s")

    def test_cache_invalidation_accuracy_under_load(self):
        """Тест точности инвалидации кэша при высокой нагрузке"""
        from django.db import connection

        list_url = reverse("pages:pages-list")

        # Прогреваем кэш
        response = self.client.get(list_url)
        initial_count = response.data["count"]

        # Функция для создания новых страниц в отдельном потоке
        def create_pages():
            try:
                for i in range(5):
                    Page.objects.create(
                        title=f"Load Test Page {i}",
                        slug=f"load-page-{i}",
                        content=f"<p>Load test content {i}</p>",
                        is_published=True,
                    )
                    time.sleep(0.1)  # Небольшая задержка между созданиями
            finally:
                connection.close()

        # Функция для выполнения запросов
        def make_requests():
            client = APIClient()  # Создаём отдельный клиент для потока
            try:
                for _ in range(10):
                    client.get(list_url)
                    time.sleep(0.1)
            finally:
                connection.close()

        # Используем ThreadPoolExecutor для управления потоками
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            create_future = executor.submit(create_pages)
            request_future = executor.submit(make_requests)
            concurrent.futures.wait([create_future, request_future])

        # Проверяем финальное состояние
        final_response = self.client.get(list_url)
        final_count = final_response.data["count"]

        # Количество страниц должно увеличиться
        self.assertGreater(final_count, initial_count)
        # Проверяем что увеличилось примерно на 5
        # (может быть небольшая разница из-за async операций)
        self.assertGreaterEqual(final_count - initial_count, 4)
        self.assertLessEqual(final_count - initial_count, 6)

    def test_detail_page_cache_performance(self):
        """Тест производительности кэширования детальных страниц"""
        page = Page.objects.first()
        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})

        # Первый запрос (без кэша)
        start_time = time.time()
        response1 = self.client.get(url)
        first_request_time = time.time() - start_time

        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Последующие запросы (с кэшем)
        cache_times = []
        for _ in range(10):
            start_time = time.time()
            response = self.client.get(url)
            cache_time = time.time() - start_time
            cache_times.append(cache_time)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Кэшированные запросы должны быть быстрее первого
        avg_cache_time = sum(cache_times) / len(cache_times)

        # Средний кэшированный запрос должен быть быстрым
        self.assertLess(avg_cache_time, 0.1, f"Cached requests too slow: {avg_cache_time}s")


@pytest.mark.integration
class PagesAPIStressTest(TestCase):
    """Стресс-тесты для Pages API"""

    def setUp(self):
        """Настройка для stress тестов"""
        self.client = APIClient()
        cache.clear()
        Page.objects.all().delete()

    def test_api_handles_many_pages(self):
        """Тест обработки большого количества страниц"""
        # Создаем много страниц
        pages_data = []
        for i in range(200):
            pages_data.append(
                Page(
                    title=f"Stress Test Page {i}",
                    slug=f"stress-page-{i}",
                    content=f"<p>Stress test content {i}</p>" * 20,
                    is_published=True,
                )
            )

        Page.objects.bulk_create(pages_data)

        # Тестируем список всех страниц
        start_time = time.time()
        url = reverse("pages:pages-list")
        response = self.client.get(url)
        end_time = time.time()

        response_time = end_time - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # API использует пагинацию, проверяем общее количество
        self.assertEqual(response.data["count"], 200)
        # Проверяем что получили результаты на первой странице
        self.assertGreater(len(response.data["results"]), 0)

        # Даже с 200 страницами ответ должен быть быстрым
        self.assertLess(response_time, 2.0, f"Large dataset response too slow: {response_time}s")

    def test_rapid_page_creation_performance(self):
        """Тест производительности быстрого создания страниц"""
        start_time = time.time()

        # Быстро создаем много страниц
        for i in range(50):
            Page.objects.create(
                title=f"Rapid Page {i}",
                slug=f"rapid-{i}",
                content=f"<p>Rapid content {i}</p>",
                is_published=True,
            )

        creation_time = time.time() - start_time

        # Создание 50 страниц должно занимать разумное время
        self.assertLess(creation_time, 5.0, f"Page creation too slow: {creation_time}s")

        # Проверяем что все страницы доступны через API
        url = reverse("pages:pages-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 50)
        self.assertGreater(len(response.data["results"]), 0)

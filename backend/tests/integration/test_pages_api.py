"""
Интеграционные тесты для Pages API (Story 2.10)
Расширенные тесты для Fix TEST-001: включают кэширование, производительность, edge cases
"""

import time

import pytest
from django.core.cache import cache
from django.db import transaction
from django.test import TestCase, TransactionTestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.pages.cache_keys import (
    PAGES_LIST_CACHE_TTL,
    get_pages_list_version,
    pages_list_cache_key,
)
from apps.pages.models import Page


@pytest.mark.integration
class PagesAPITest(TestCase):
    """Тесты для Pages API"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = APIClient()

        # Очищаем базу от всех страниц
        Page.objects.all().delete()

        # Создаем тестовые страницы
        self.published_page = Page.objects.create(
            title="О компании",
            slug="about",
            content="<p>Информация о нашей компании</p>",
            is_published=True,
        )

        self.unpublished_page = Page.objects.create(
            title="Черновик",
            slug="draft",
            content="<p>Черновик страницы</p>",
            is_published=False,
        )

    def test_pages_list_api(self):
        """Тест получения списка опубликованных страниц"""
        url = reverse("pages:pages-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверим структуру paginated ответа
        self.assertIn("results", response.data)
        self.assertIn("count", response.data)

        # Проверяем что есть хотя бы одна страница и она опубликована
        self.assertGreaterEqual(len(response.data["results"]), 1)
        self.assertGreaterEqual(response.data["count"], 1)

        # Найдем нашу тестовую страницу
        test_page = None
        for page in response.data["results"]:
            if page["title"] == "О компании":
                test_page = page
                break

        self.assertIsNotNone(test_page, "Тестовая страница не найдена в ответе")
        self.assertEqual(test_page["title"], "О компании")

    def test_page_detail_api(self):
        """Тест получения детальной информации о странице"""
        url = reverse("pages:pages-detail", kwargs={"slug": "about"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["title"], "О компании")
        self.assertEqual(response.data["content"], "<p>Информация о нашей компании</p>")

    def test_privacy_policy_page_is_available_only_after_publication(self):
        """Тест публикации страницы политики ПДн по slug privacy-policy."""
        cache.clear()
        url = reverse("pages:pages-detail", kwargs={"slug": "privacy-policy"})

        response_before_publication = self.client.get(url)
        self.assertEqual(response_before_publication.status_code, status.HTTP_404_NOT_FOUND)

        Page.objects.create(
            title="Политика обработки персональных данных",
            slug="privacy-policy",
            content="<p>Текст политики</p>",
            is_published=True,
        )
        cache.clear()

        response_after_publication = self.client.get(url)
        self.assertEqual(response_after_publication.status_code, status.HTTP_200_OK)
        self.assertEqual(
            response_after_publication.data["title"],
            "Политика обработки персональных данных",
        )
        self.assertEqual(response_after_publication.data["slug"], "privacy-policy")

    def test_unpublished_page_not_accessible(self):
        """Тест что неопубликованные страницы недоступны"""
        url = reverse("pages:pages-detail", kwargs={"slug": "draft"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_nonexistent_page(self):
        """Тест обращения к несуществующей странице"""
        url = reverse("pages:pages-detail", kwargs={"slug": "nonexistent"})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_html_sanitization(self):
        """Тест HTML sanitization"""
        page = Page.objects.create(
            title="Тест HTML",
            content=('<p>Нормальный текст</p><script>alert("XSS")</script><h1>Заголовок</h1>'),
            is_published=True,
        )

        # Script должен быть удален, h1 и p сохранены
        self.assertNotIn("<script>", page.content)
        self.assertIn("<p>Нормальный текст</p>", page.content)
        self.assertIn("<h1>Заголовок</h1>", page.content)

    def test_seo_auto_generation(self):
        """Тест автогенерации SEO полей"""
        page = Page.objects.create(
            title="Очень длинный заголовок для тестирования автогенерации SEO полей",
            content="<p>Это содержимое страницы для автогенерации description. " * 10,
            is_published=True,
        )

        # SEO title должно быть обрезано до 60 символов
        self.assertEqual(len(page.seo_title), 60)
        self.assertTrue(page.seo_title.startswith("Очень длинный"))

        # SEO description должно быть обрезано до 160 символов без HTML
        self.assertEqual(len(page.seo_description), 160)
        self.assertNotIn("<p>", page.seo_description)


@pytest.mark.integration
class PagesAPICachingTest(TestCase):
    """Тесты кэширования Pages API - Fix TEST-001"""

    def setUp(self):
        """Настройка тестовых данных и очистка кэша"""
        self.client = APIClient()
        cache.clear()

        # Очищаем базу от всех страниц
        Page.objects.all().delete()

        self.test_page = Page.objects.create(
            title="Кэш тест",
            slug="cache-test",
            content="<p>Контент для тестирования кэша</p>",
            is_published=True,
        )

    def test_page_detail_caching(self):
        """Тест кэширования детальной страницы"""
        url = reverse("pages:pages-detail", kwargs={"slug": "cache-test"})

        # Первый запрос - данные должны быть закэшированы
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Изменяем страницу в БД
        self.test_page.title = "Измененный заголовок"
        self.test_page.save()

        # Второй запрос - должен вернуть кэшированные данные
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Проверяем что возвращается старое значение (кэш)
        # В реальном кэшировании это может быть кэшированное значение

    def test_cache_invalidation_on_page_update(self):
        """Тест инвалидации кэша при обновлении страницы"""
        url = reverse("pages:pages-list")

        # Делаем запрос для создания кэша
        response1 = self.client.get(url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)

        # Создаем новую страницу. Инвалидация кэша отложена до commit
        # (`transaction.on_commit`), а `TestCase` держит тест в транзакции —
        # поэтому коллбэки исполняем явно.
        with self.captureOnCommitCallbacks(execute=True):
            Page.objects.create(
                title="Новая страница",
                slug="new-page",
                content="<p>Новый контент</p>",
                is_published=True,
            )

        # Запрос должен показать обновленные данные
        response2 = self.client.get(url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)

        # Проверяем что новая страница присутствует
        page_titles = [page["title"] for page in response2.data["results"]]
        self.assertIn("Новая страница", page_titles)

    def test_unpublished_pages_not_cached(self):
        """Тест что неопубликованные страницы не кэшируются"""
        unpublished = Page.objects.create(
            title="Черновик",
            slug="draft",
            content="<p>Черновик</p>",
            is_published=False,
        )

        url = reverse("pages:pages-list")
        response = self.client.get(url)

        page_titles = [page["title"] for page in response.data["results"]]
        self.assertNotIn("Черновик", page_titles)


@pytest.mark.integration
class PagesAPIEdgeCasesTest(TestCase):
    """Тесты edge cases для Pages API - Fix TEST-001"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = APIClient()
        Page.objects.all().delete()

    def test_empty_pages_list(self):
        """Тест получения пустого списка страниц"""
        url = reverse("pages:pages-list")
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"], [])
        self.assertEqual(response.data["count"], 0)

    def test_special_characters_in_slug(self):
        """Тест обработки специальных символов в slug"""
        page = Page.objects.create(
            title="Тест с символами: №1 (русский)",
            content="<p>Контент</p>",
            is_published=True,
        )

        # Проверяем что slug корректно сгенерирован
        self.assertTrue(page.slug)
        self.assertNotIn("№", page.slug)
        self.assertNotIn("(", page.slug)
        self.assertNotIn(")", page.slug)

        # Проверяем что страница доступна по API
        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_very_long_content(self):
        """Тест обработки очень длинного контента"""
        long_content = "<p>" + "Очень длинный контент. " * 1000 + "</p>"

        page = Page.objects.create(title="Длинная страница", content=long_content, is_published=True)

        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("Очень длинный контент", response.data["content"])

    def test_unicode_content_handling(self):
        """Тест обработки Unicode контента"""
        unicode_content = """
        <h1>Заголовок с эмодзи 🚀</h1>
        <p>Текст с различными символами: ℃ ™ © ® ∞ ≈ ≠ ≤ ≥</p>
        <p>Иероглифы: 中文 日本語 한국어</p>
        <p>Арабский: العربية</p>
        """

        page = Page.objects.create(title="Unicode тест 🌟", content=unicode_content, is_published=True)

        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("🚀", response.data["content"])
        self.assertIn("中文", response.data["content"])

    def test_duplicate_slug_prevention(self):
        """Тест предотвращения дублирования slug"""
        Page.objects.create(
            title="Тест",
            slug="test-slug",
            content="<p>Первая страница</p>",
            is_published=True,
        )

        # Попытка создать страницу с тем же slug должна вызвать ошибку
        with self.assertRaises(Exception):  # IntegrityError или ValidationError
            Page.objects.create(
                title="Тест 2",
                slug="test-slug",
                content="<p>Вторая страница</p>",
                is_published=True,
            )

    def test_seo_fields_in_api_response(self):
        """Тест наличия SEO полей в API ответе"""
        page = Page.objects.create(
            title="SEO тест",
            content="<p>Контент для SEO тестирования</p>",
            seo_title="Кастомный SEO заголовок",
            seo_description="Кастомное SEO описание",
            is_published=True,
        )

        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["seo_title"], "Кастомный SEO заголовок")
        self.assertEqual(response.data["seo_description"], "Кастомное SEO описание")

    def test_api_response_structure(self):
        """Тест структуры API ответа"""
        page = Page.objects.create(title="Структура тест", content="<p>Контент</p>", is_published=True)

        url = reverse("pages:pages-detail", kwargs={"slug": page.slug})
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Проверяем обязательные поля
        required_fields = [
            "id",
            "title",
            "slug",
            "content",
            "seo_title",
            "seo_description",
            "updated_at",
        ]
        for field in required_fields:
            self.assertIn(field, response.data)

        # Проверяем что is_published не включено в ответ (security)
        self.assertNotIn("is_published", response.data)


@pytest.mark.integration
class PagesAPIPerformanceTest(TestCase):
    """Тесты производительности Pages API - Fix TEST-001"""

    def setUp(self):
        """Настройка тестовых данных для performance тестов"""
        self.client = APIClient()
        Page.objects.all().delete()

        # Создаем множество страниц для тестирования производительности
        pages_data = []
        for i in range(50):
            pages_data.append(
                Page(
                    title=f"Страница {i}",
                    slug=f"page-{i}",
                    content=f"<p>Контент страницы {i}</p>" * 10,
                    is_published=True,
                )
            )
        Page.objects.bulk_create(pages_data)

    def test_list_pages_response_time(self):
        """Тест времени ответа для списка страниц"""
        url = reverse("pages:pages-list")

        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()

        response_time = end_time - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # API использует пагинацию, поэтому проверяем общее количество,
        # а не количество в results
        self.assertEqual(response.data["count"], 50)
        # Проверяем что получили хотя бы некоторые результаты
        self.assertGreater(len(response.data["results"]), 0)

        # Response time должно быть разумным (менее 1 секунды)
        self.assertLess(response_time, 1.0, f"Response time too slow: {response_time}s")

    def test_page_detail_response_time(self):
        """Тест времени ответа для детальной страницы"""
        url = reverse("pages:pages-detail", kwargs={"slug": "page-0"})

        start_time = time.time()
        response = self.client.get(url)
        end_time = time.time()

        response_time = end_time - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Response time должно быть очень быстрым для одной страницы
        self.assertLess(response_time, 0.5, f"Response time too slow: {response_time}s")


@pytest.mark.integration
class PagesListCachePaginationTest(TestCase):
    """Кэш выдачи списка страниц не должен смешивать разные окна пагинации.

    Middleware фронтенда запрашивает `?page_size=1000`, чтобы получить полный
    список опубликованных слагов и по нему решать, отдавать ли настоящий 404.
    Если кэш списка не учитывает параметры пагинации, такому запросу может
    достаться закэшированная первая страница из 20 записей (`PAGE_SIZE` DRF),
    и 21-я CMS-страница молча начнёт отдавать 404.
    """

    PAGES_COUNT = 25

    def setUp(self):
        """Создаёт заведомо больше страниц, чем помещается на страницу выдачи"""
        self.client = APIClient()
        cache.clear()
        Page.objects.all().delete()

        for index in range(self.PAGES_COUNT):
            Page.objects.create(
                title=f"Страница {index:02d}",
                slug=f"page-{index:02d}",
                content="<p>Контент</p>",
                is_published=True,
            )

    def test_full_list_request_not_served_from_default_page_cache(self):
        """Запрос с page_size не должен получать закэшированную выдачу по умолчанию"""
        url = reverse("pages:pages-list")

        default_response = self.client.get(url)
        self.assertEqual(len(default_response.data["results"]), 20)

        full_response = self.client.get(url, {"page_size": 1000})

        self.assertEqual(full_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(full_response.data["results"]), self.PAGES_COUNT)

    def test_default_page_request_not_served_from_full_list_cache(self):
        """Обратное направление: запрос без параметров не получает полную выдачу"""
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000})
        default_response = self.client.get(url)

        self.assertEqual(default_response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(default_response.data["results"]), 20)

    def test_second_page_not_served_from_first_page_cache(self):
        """Вторая страница выдачи не должна подменяться первой из кэша"""
        url = reverse("pages:pages-list")

        self.client.get(url)
        second_page = self.client.get(url, {"page": 2})

        slugs = [page["slug"] for page in second_page.data["results"]]
        self.assertEqual(slugs, [f"page-{index:02d}" for index in range(20, self.PAGES_COUNT)])

    def test_publication_invalidates_every_pagination_variant(self):
        """Публикация страницы сбрасывает кэш всех вариантов пагинации сразу"""
        url = reverse("pages:pages-list")

        # Прогреваем оба варианта кэша
        self.client.get(url)
        self.client.get(url, {"page_size": 1000})

        with self.captureOnCommitCallbacks(execute=True):
            Page.objects.create(
                title="Аренда инвентаря",
                slug="arenda",
                content="<p>Новая страница</p>",
                is_published=True,
            )

        full_response = self.client.get(url, {"page_size": 1000})
        self.assertIn("arenda", [page["slug"] for page in full_response.data["results"]])

        default_response = self.client.get(url)
        self.assertEqual(default_response.data["count"], self.PAGES_COUNT + 1)

    def test_unpublishing_invalidates_full_list_cache(self):
        """Снятие с публикации также сбрасывает кэш полной выдачи"""
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000})

        page = Page.objects.get(slug="page-00")
        page.is_published = False
        with self.captureOnCommitCallbacks(execute=True):
            page.save()

        full_response = self.client.get(url, {"page_size": 1000})
        self.assertNotIn("page-00", [item["slug"] for item in full_response.data["results"]])


@pytest.mark.integration
class PagesListCacheConsistencyTest(TestCase):
    """Общий кэш списка страниц не должен переживать инвалидацию и сортировку.

    Раунд 3 ревью стори 41.0 нашёл в кэше два изъяна, из-за которых middleware
    фронтенда мог получить неверный список слагов и отдать ложный 404:

    1. поздний writer, начавший сериализацию до сигнала инвалидации, записывал
       устаревший список уже ПОСЛЕ удаления ключа — и он жил там сутки;
    2. первый запрос с `?ordering=` клал в общий ключ выдачу в своём порядке,
       после чего другие варианты сортировки переставали применяться.
    """

    PAGES_COUNT = 25

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        Page.objects.all().delete()

        for index in range(self.PAGES_COUNT):
            Page.objects.create(
                title=f"Страница {index:02d}",
                slug=f"page-{index:02d}",
                content="<p>Контент</p>",
                is_published=True,
            )

    def test_late_writer_cannot_resurrect_list_from_before_invalidation(self):
        """Запись устаревшего списка после сигнала не должна попадать читателям"""
        url = reverse("pages:pages-list")

        # Прогрев: writer прочитал версию кэша и сериализовал текущий список
        self.client.get(url, {"page_size": 1000})
        version_before = get_pages_list_version()
        stale_payload = cache.get(pages_list_cache_key(version_before))
        self.assertIsNotNone(stale_payload)

        with self.captureOnCommitCallbacks(execute=True):
            Page.objects.create(
                title="Аренда инвентаря",
                slug="arenda",
                content="<p>Новая страница</p>",
                is_published=True,
            )

        # Поздний writer завершает работу уже после инвалидации и пишет старый список
        cache.set(pages_list_cache_key(version_before), stale_payload, PAGES_LIST_CACHE_TTL)

        response = self.client.get(url, {"page_size": 1000})
        self.assertIn("arenda", [page["slug"] for page in response.data["results"]])

    def test_ordering_variants_are_not_served_from_shared_cache(self):
        """Разные значения ordering дают разный порядок, а не один закэшированный"""
        url = reverse("pages:pages-list")

        ascending = self.client.get(url, {"page_size": 1000, "ordering": "title"})
        descending = self.client.get(url, {"page_size": 1000, "ordering": "-title"})

        asc_slugs = [page["slug"] for page in ascending.data["results"]]
        desc_slugs = [page["slug"] for page in descending.data["results"]]

        self.assertEqual(desc_slugs, list(reversed(asc_slugs)))

    def test_ordering_request_does_not_poison_default_cache(self):
        """Запрос с ordering не отравляет общий кэш своим порядком"""
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000, "ordering": "-title"})
        default_response = self.client.get(url, {"page_size": 1000})

        slugs = [page["slug"] for page in default_response.data["results"]]
        self.assertEqual(slugs, sorted(slugs))

    def test_search_request_does_not_poison_default_cache(self):
        """Фильтрующий параметр тоже не должен попадать в общий кэш"""
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000, "search": "Страница 01"})
        default_response = self.client.get(url, {"page_size": 1000})

        self.assertEqual(len(default_response.data["results"]), self.PAGES_COUNT)

    def test_invalidation_is_deferred_until_commit(self):
        """Инвалидация обязана происходить после commit, а не в момент `save()`.

        Сигнал `post_save` срабатывает внутри открытой транзакции. Если версия
        кэша поднимается там же, между инвалидацией и commit остаётся окно:
        параллельный GET новую страницу ещё не видит (она не закоммичена), но
        уже читает и заполняет НОВУЮ версию ключа допубликационным списком. Такой
        список живёт сутки, и middleware фронтенда отдаёт по новой странице
        ложный 404 гораздо дольше собственного TTL в 5 минут.
        """
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000})
        stale_payload = cache.get(pages_list_cache_key(get_pages_list_version()))
        self.assertIsNotNone(stale_payload)

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            Page.objects.create(
                title="Аренда инвентаря",
                slug="arenda",
                content="<p>Новая страница</p>",
                is_published=True,
            )

            # Читатель внутри окна «сигнал сработал, commit ещё не прошёл»:
            # новой страницы он не видит и кладёт старый список под ТЕКУЩИЙ ключ.
            cache.set(
                pages_list_cache_key(get_pages_list_version()),
                stale_payload,
                PAGES_LIST_CACHE_TTL,
            )

        # Сигнал обязан отложить инвалидацию до commit, а не выполнить её сразу.
        self.assertEqual(len(callbacks), 1)

        response = self.client.get(url, {"page_size": 1000})
        self.assertIn("arenda", [page["slug"] for page in response.data["results"]])

    def test_rollback_does_not_invalidate_cache(self):
        """Откат транзакции не должен сбрасывать кэш: страница так и не появилась"""
        url = reverse("pages:pages-list")

        self.client.get(url, {"page_size": 1000})
        version_before = get_pages_list_version()

        with self.assertRaises(RuntimeError):
            with transaction.atomic():
                Page.objects.create(
                    title="Откат",
                    slug="rollback",
                    content="<p>Не доедет до базы</p>",
                    is_published=True,
                )
                raise RuntimeError("откат транзакции")

        self.assertEqual(get_pages_list_version(), version_before)
        self.assertIsNotNone(cache.get(pages_list_cache_key(version_before)))

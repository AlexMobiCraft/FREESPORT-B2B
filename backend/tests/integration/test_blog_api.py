"""Интеграционные тесты для публичного API блога."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.common.models import BlogPost, Category

pytestmark = pytest.mark.django_db


@pytest.fixture
def test_category():
    """Создает тестовую категорию для статей блога."""
    return Category.objects.create(
        name="Руководства",
        slug="guides",
        description="Руководства и инструкции",
    )


@pytest.fixture
def published_blog_posts(test_category):
    """Создает набор опубликованных статей блога для проверки выборки."""
    now = timezone.now()
    return [
        BlogPost.objects.create(
            title="Статья 1",
            slug="article-1",
            subtitle="Подзаголовок 1",
            excerpt="Описание статьи 1",
            content="Полное содержание статьи 1",
            author="Автор 1",
            category=test_category,
            is_published=True,
            published_at=now - timedelta(days=1),
            meta_title="SEO Заголовок 1",
            meta_description="SEO описание 1",
        ),
        BlogPost.objects.create(
            title="Статья 2",
            slug="article-2",
            subtitle="Подзаголовок 2",
            excerpt="Описание статьи 2",
            content="Полное содержание статьи 2",
            author="Автор 2",
            category=test_category,
            is_published=True,
            published_at=now - timedelta(days=2),
            meta_title="SEO Заголовок 2",
            meta_description="SEO описание 2",
        ),
        BlogPost.objects.create(
            title="Статья 3",
            slug="article-3",
            subtitle="Подзаголовок 3",
            excerpt="Описание статьи 3",
            content="Полное содержание статьи 3",
            author="Автор 3",
            category=test_category,
            is_published=True,
            published_at=now - timedelta(days=3),
            meta_title="SEO Заголовок 3",
            meta_description="SEO описание 3",
        ),
    ]


class TestBlogListEndpoint:
    """Набор кейсов для GET /api/v1/blog/."""

    def test_get_blog_list_success(self, api_client, published_blog_posts):
        """Проверяет успешное получение списка статей блога."""
        url = reverse("common:blog-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3
        # Проверка сортировки (новые первые)
        assert response.data["results"][0]["title"] == "Статья 1"

    def test_get_blog_list_only_published(self, api_client, test_category):
        """Проверяет фильтрацию по признаку публикации."""
        now = timezone.now()

        BlogPost.objects.create(
            title="Опубликованная статья",
            slug="published-article",
            excerpt="Описание",
            content="Содержание",
            is_published=True,
            published_at=now - timedelta(days=1),
            category=test_category,
        )
        BlogPost.objects.create(
            title="Черновик статьи",
            slug="draft-article",
            excerpt="Описание",
            content="Содержание",
            is_published=False,
            published_at=now - timedelta(days=1),
            category=test_category,
        )

        url = reverse("common:blog-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Опубликованная статья"

    def test_get_blog_list_with_pagination(self, api_client, published_blog_posts):
        """Убеждаемся, что API возвращает стандартные поля пагинации."""
        url = reverse("common:blog-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert {"results", "count", "next", "previous"}.issubset(response.data)

    def test_get_blog_list_pagination_fields(self, api_client, published_blog_posts):
        """Проверяет наличие полей пагинации в ответе."""
        url = reverse("common:blog-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Проверяем наличие всех полей пагинации
        assert "count" in response.data
        assert "next" in response.data
        assert "previous" in response.data
        assert "results" in response.data
        assert isinstance(response.data["results"], list)

    def test_get_blog_list_sorted_by_published_date(self, api_client, published_blog_posts):
        """Проверяет сортировку статей по дате публикации (новые первые)."""
        url = reverse("common:blog-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        results = response.data["results"]
        assert results[0]["title"] == "Статья 1"
        assert results[1]["title"] == "Статья 2"
        assert results[2]["title"] == "Статья 3"

    def test_get_blog_list_excludes_future_posts(self, api_client, test_category):
        """Убеждаемся, что будущие публикации не попадают в выдачу."""
        now = timezone.now()

        BlogPost.objects.create(
            title="Прошлая статья",
            slug="past-article",
            excerpt="Описание",
            content="Содержание",
            is_published=True,
            published_at=now - timedelta(days=1),
            category=test_category,
        )
        BlogPost.objects.create(
            title="Будущая статья",
            slug="future-article",
            excerpt="Описание",
            content="Содержание",
            is_published=True,
            published_at=now + timedelta(days=1),
            category=test_category,
        )

        url = reverse("common:blog-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Прошлая статья"

    def test_get_blog_list_response_structure(self, api_client, published_blog_posts):
        """Проверяет структуру ответа списка (наличие всех полей)."""
        url = reverse("common:blog-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        first_item = response.data["results"][0]

        # Проверка полей BlogPostListSerializer
        expected_fields = {
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "image",
            "author",
            "category",
            "published_at",
        }
        assert expected_fields.issubset(first_item.keys())

        # Проверка, что content не включен в список (только в DetailSerializer)
        assert "content" not in first_item
        assert "meta_title" not in first_item
        assert "meta_description" not in first_item


class TestBlogDetailEndpoint:
    """Набор кейсов для GET /api/v1/blog/{slug}/."""

    def test_get_blog_detail_success(self, api_client, published_blog_posts):
        """Проверяет успешное получение детальной информации о статье."""
        blog_post = published_blog_posts[0]
        url = reverse("common:blog-detail", kwargs={"slug": blog_post.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == blog_post.id
        assert response.data["title"] == blog_post.title
        assert response.data["slug"] == blog_post.slug

    def test_get_blog_detail_not_found(self, api_client):
        """Проверяет 404 для несуществующего slug."""
        url = reverse("common:blog-detail", kwargs={"slug": "non-existent-slug"})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_blog_detail_unpublished_returns_404(self, api_client, test_category):
        """Проверяет 404 для неопубликованной статьи."""
        now = timezone.now()
        unpublished_post = BlogPost.objects.create(
            title="Неопубликованная статья",
            slug="unpublished-article",
            excerpt="Описание",
            content="Содержание",
            is_published=False,
            published_at=now - timedelta(days=1),
            category=test_category,
        )

        url = reverse("common:blog-detail", kwargs={"slug": unpublished_post.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_blog_detail_future_post_returns_404(self, api_client, test_category):
        """Проверяет 404 для статьи с будущей датой публикации."""
        now = timezone.now()
        future_post = BlogPost.objects.create(
            title="Будущая статья",
            slug="future-article",
            excerpt="Описание",
            content="Содержание",
            is_published=True,
            published_at=now + timedelta(days=1),
            category=test_category,
        )

        url = reverse("common:blog-detail", kwargs={"slug": future_post.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_blog_detail_response_structure(self, api_client, published_blog_posts):
        """Проверяет структуру ответа детальной страницы (все поля присутствуют)."""
        blog_post = published_blog_posts[0]
        url = reverse("common:blog-detail", kwargs={"slug": blog_post.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

        # Проверка полей BlogPostDetailSerializer
        expected_fields = {
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "content",
            "image",
            "author",
            "category",
            "published_at",
            "meta_title",
            "meta_description",
            "created_at",
            "updated_at",
        }
        assert expected_fields.issubset(response.data.keys())

    def test_get_blog_detail_category_structure(self, api_client, published_blog_posts):
        """Проверяет структуру вложенной категории."""
        blog_post = published_blog_posts[0]
        url = reverse("common:blog-detail", kwargs={"slug": blog_post.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        category = response.data["category"]

        # Категория должна быть объектом с полями id, name, slug
        assert isinstance(category, dict)
        assert {"id", "name", "slug"}.issubset(category.keys())
        assert category["id"] == blog_post.category.id
        assert category["name"] == blog_post.category.name
        assert category["slug"] == blog_post.category.slug

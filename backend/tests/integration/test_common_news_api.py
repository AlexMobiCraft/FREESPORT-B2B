"""Интеграционные тесты для публичного API новостей."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from apps.common.models import News

pytestmark = pytest.mark.django_db


@pytest.fixture
def published_news():
    """Создает набор опубликованных новостей для проверки выборки."""
    now = timezone.now()
    return [
        News.objects.create(
            title="Новость 1",
            slug="news-1",
            excerpt="Описание новости 1",
            is_published=True,
            published_at=now - timedelta(days=1),
        ),
        News.objects.create(
            title="Новость 2",
            slug="news-2",
            excerpt="Описание новости 2",
            is_published=True,
            published_at=now - timedelta(days=2),
        ),
        News.objects.create(
            title="Новость 3",
            slug="news-3",
            excerpt="Описание новости 3",
            is_published=True,
            published_at=now - timedelta(days=3),
        ),
    ]


class TestNewsListEndpoint:
    """Набор кейсов для GET /api/v1/news."""

    def test_get_news_list_success(self, api_client, published_news):
        """Проверяет успешное получение списка и сортировку новостей."""
        url = reverse("common:news-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 3
        assert len(response.data["results"]) == 3
        assert response.data["results"][0]["title"] == "Новость 1"

    def test_get_news_list_with_pagination(self, api_client, published_news):
        """Убеждаемся, что API возвращает стандартные поля пагинации."""
        url = reverse("common:news-list")

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert {"results", "count", "next", "previous"}.issubset(response.data)

    def test_get_news_list_only_published(self, api_client):
        """Проверяет фильтрацию по признаку публикации."""
        now = timezone.now()

        News.objects.create(
            title="Опубликованная",
            slug="published",
            excerpt="Описание",
            is_published=True,
            published_at=now - timedelta(days=1),
        )
        News.objects.create(
            title="Черновик",
            slug="draft",
            excerpt="Описание",
            is_published=False,
            published_at=now - timedelta(days=1),
        )

        url = reverse("common:news-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Опубликованная"

    def test_get_news_list_exclude_future_news(self, api_client):
        """Убеждаемся, что будущие публикации не попадают в выдачу."""
        now = timezone.now()

        News.objects.create(
            title="Прошлая новость",
            slug="past-news",
            excerpt="Описание",
            is_published=True,
            published_at=now - timedelta(days=1),
        )
        News.objects.create(
            title="Будущая новость",
            slug="future-news",
            excerpt="Описание",
            is_published=True,
            published_at=now + timedelta(days=1),
        )

        url = reverse("common:news-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1
        assert response.data["results"][0]["title"] == "Прошлая новость"

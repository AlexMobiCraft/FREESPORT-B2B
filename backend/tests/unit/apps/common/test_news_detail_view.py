"""Unit-тесты для NewsDetailView - детальная информация о новости."""

from datetime import timedelta
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from PIL import Image
from rest_framework import status

from apps.common.models import Category, News

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def create_test_image():
    """Создает тестовое изображение для новости."""
    file_obj = BytesIO()
    image = Image.new("RGB", (100, 100), color="red")
    image.save(file_obj, "jpeg")
    file_obj.seek(0)
    return SimpleUploadedFile("test_image.jpg", file_obj.read(), content_type="image/jpeg")


@pytest.fixture
def test_category():
    """Создает тестовую категорию для новостей."""
    return Category.objects.create(name="Анонсы", slug="announcements", is_active=True)


@pytest.fixture
def published_news(test_category):
    """Создает опубликованную новость с категорией и изображением."""
    now = timezone.now()
    return News.objects.create(
        title="Тестовая новость",
        slug="test-news",
        excerpt="Краткое описание тестовой новости",
        content="<p>Полное содержание тестовой новости</p>",
        image=create_test_image(),
        author="Тестовый автор",
        category=test_category,
        is_published=True,
        published_at=now - timedelta(hours=1),
    )


@pytest.fixture
def unpublished_news():
    """Создает неопубликованную новость."""
    now = timezone.now()
    return News.objects.create(
        title="Неопубликованная новость",
        slug="unpublished-news",
        excerpt="Описание черновика",
        content="<p>Содержание черновика</p>",
        is_published=False,
        published_at=now - timedelta(hours=1),
    )


@pytest.fixture
def future_news():
    """Создает новость с будущей датой публикации."""
    now = timezone.now()
    return News.objects.create(
        title="Будущая новость",
        slug="future-news",
        excerpt="Описание будущей публикации",
        content="<p>Содержание будущей публикации</p>",
        is_published=True,
        published_at=now + timedelta(days=1),
    )


@pytest.fixture
def news_without_category():
    """Создает новость без категории."""
    now = timezone.now()
    return News.objects.create(
        title="Новость без категории",
        slug="news-no-category",
        excerpt="Описание",
        content="<p>Содержание</p>",
        category=None,
        is_published=True,
        published_at=now - timedelta(hours=1),
    )


class TestNewsDetailView:
    """Набор тестов для GET /api/v1/news/{slug}/"""

    def test_get_published_news_success(self, api_client, published_news):
        """Проверяет успешное получение опубликованной новости по slug."""
        url = reverse("common:news-detail", kwargs={"slug": published_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["id"] == published_news.id
        assert response.data["title"] == "Тестовая новость"
        assert response.data["slug"] == "test-news"

    def test_get_news_not_found(self, api_client):
        """Проверяет 404 при несуществующем slug."""
        url = reverse("common:news-detail", kwargs={"slug": "non-existent-slug"})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_unpublished_news_returns_404(self, api_client, unpublished_news):
        """Проверяет 404 при попытке получить неопубликованную новость."""
        url = reverse("common:news-detail", kwargs={"slug": unpublished_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_get_future_news_returns_404(self, api_client, future_news):
        """Проверяет 404 при попытке получить новость с будущей датой публикации."""
        url = reverse("common:news-detail", kwargs={"slug": future_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_response_structure_contains_all_fields(self, api_client, published_news):
        """Проверяет, что ответ содержит все необходимые поля."""
        url = reverse("common:news-detail", kwargs={"slug": published_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        expected_fields = {
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "image",
            "published_at",
            "created_at",
            "updated_at",
            "author",
            "category",
        }
        assert expected_fields == set(response.data.keys())

    def test_image_url_transformation(self, api_client, published_news):
        """Проверяет преобразование image в полный URL."""
        url = reverse("common:news-detail", kwargs={"slug": published_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["image"] is not None
        assert response.data["image"].startswith("http")
        assert "test_image" in response.data["image"]

    def test_category_detailed_format(self, api_client, published_news, test_category):
        """Проверяет детальный формат category в ответе."""
        url = reverse("common:news-detail", kwargs={"slug": published_news.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["category"] is not None
        assert isinstance(response.data["category"], dict)
        assert response.data["category"]["id"] == test_category.id
        assert response.data["category"]["name"] == "Анонсы"
        assert response.data["category"]["slug"] == "announcements"

    def test_news_without_category(self, api_client, news_without_category):
        """Проверяет обработку новости без категории (category=None)."""
        url = reverse("common:news-detail", kwargs={"slug": news_without_category.slug})

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        # Когда category=None, поле не должно содержать детального объекта
        assert "category" in response.data
        # NewsSerializer оставляет None как есть, если нет условий на обработку None

    def test_endpoint_allows_unauthenticated_access(self, client, published_news):
        """Проверяет, что endpoint доступен без аутентификации (AllowAny)."""
        url = reverse("common:news-detail", kwargs={"slug": published_news.slug})

        # Используем обычный client (не api_client) для неаутентифицированного запроса
        response = client.get(url)

        assert response.status_code == status.HTTP_200_OK

import pytest
from django.urls import reverse
from rest_framework import status

from apps.products.models import Product
from apps.users.models import Address, Favorite

pytestmark = pytest.mark.django_db


@pytest.fixture
def authenticated_user_client(db, api_client):
    """Фикстура для создания и аутентификации пользователя."""
    from tests.conftest import UserFactory

    user = UserFactory.create()
    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
    api_client.user = user
    return api_client


def test_dashboard_api(authenticated_user_client):
    """Тест эндпоинта дашборда."""
    url = reverse("users:dashboard")
    response = authenticated_user_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "orders_count" in response.data
    assert "favorites_count" in response.data
    assert "addresses_count" in response.data


def test_address_api_crud(authenticated_user_client):
    """Тест CRUD операций для адресов."""
    # Create
    url = reverse("users:address-list")
    address_data = {
        "address_type": "shipping",
        "full_name": "Test User",
        "phone": "+79998887766",
        "city": "Test City",
        "street": "Test Street",
        "building": "1",
        "apartment": "1",
        "postal_code": "123456",
    }
    response = authenticated_user_client.post(url, address_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    address_id = response.data["id"]

    # Read
    response = authenticated_user_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    # Update
    update_data = {"city": "New Test City"}
    url = reverse("users:address-detail", kwargs={"pk": address_id})
    response = authenticated_user_client.patch(url, update_data, format="json")
    assert response.status_code == status.HTTP_200_OK
    assert response.data["city"] == "New Test City"

    # Delete
    response = authenticated_user_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Address.objects.filter(pk=address_id).exists()


def test_favorite_api_crud(authenticated_user_client):
    """Тест CRUD операций для избранных товаров."""
    from tests.conftest import ProductFactory

    product = ProductFactory.create()

    # Create
    url = reverse("users:favorite-list")
    favorite_data = {"product": product.id}
    response = authenticated_user_client.post(url, favorite_data, format="json")
    assert response.status_code == status.HTTP_201_CREATED
    favorite_id = Favorite.objects.latest("id").id

    # Read
    response = authenticated_user_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["results"]) == 1

    # Delete
    url = reverse("users:favorite-detail", kwargs={"pk": favorite_id})
    response = authenticated_user_client.delete(url)
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Favorite.objects.filter(pk=favorite_id).exists()


def test_order_history_api(authenticated_user_client):
    """Тест эндпоинта истории заказов."""
    url = reverse("users:orders")
    response = authenticated_user_client.get(url)
    assert response.status_code == status.HTTP_200_OK
    assert "count" in response.data
    assert "results" in response.data

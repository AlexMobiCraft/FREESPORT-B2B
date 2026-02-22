import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User

# Используем маркер pytest для доступа к БД во всех тестах этого модуля
pytestmark = pytest.mark.django_db

TEST_USER_PASSWORD = "TestPassword123!"


@pytest.fixture
def api_client():
    """Фикстура для создания клиента API."""
    return APIClient()


@pytest.fixture
def create_user_and_get_token(api_client):
    """
    Фикстура для регистрации и авторизации пользователя, возвращает токен.
    """

    def _create_user_and_get_token(role="retail", email=None):
        if email is None:
            email = f"test_user_{role}@example.com"

        # Удаляем пользователя, если он существует, для чистоты теста
        User.objects.filter(email=email).delete()

        registration_data = {
            "email": email,
            "password": TEST_USER_PASSWORD,
            "password_confirm": TEST_USER_PASSWORD,
            "first_name": "Тест",
            "last_name": f"Пользователь {role}",
            "role": role,
        }
        if role != "retail":
            registration_data.update({"company_name": f"Тестовая компания {role}", "tax_id": "1234567890"})

        # Регистрация
        url = reverse("users:register")
        response = api_client.post(url, registration_data, format="json")
        assert response.status_code == 201, (
            f"Registration failed for role {role} with status {response.status_code}: " f"{response.json()}"
        )

        # Авторизация
        url = reverse("users:login")
        response = api_client.post(url, {"email": email, "password": TEST_USER_PASSWORD}, format="json")
        assert response.status_code == 200, (
            f"Login failed for role {role} with status {response.status_code}: " f"{response.json()}"
        )

        return response.data["access"]

    return _create_user_and_get_token


def test_user_registration(api_client):
    """Тестирование POST /auth/register/ (AC 1)"""
    url = reverse("users:register")
    data = {
        "email": "newuser@example.com",
        "password": TEST_USER_PASSWORD,
        "password_confirm": TEST_USER_PASSWORD,
        "first_name": "New",
        "last_name": "User",
        "role": "retail",
    }
    response = api_client.post(url, data, format="json")
    assert response.status_code == 201
    assert User.objects.filter(email="newuser@example.com").exists()

    # Повторная регистрация с тем же email должна быть отклонена
    response = api_client.post(url, data, format="json")
    assert response.status_code == 400
    assert "email" in response.json()


def test_user_login(api_client, create_user_and_get_token):
    """Тестирование POST /auth/login/ (AC 2)"""
    email = "login_test@example.com"
    create_user_and_get_token(email=email)  # Просто создаем пользователя

    url = reverse("users:login")
    data = {"email": email, "password": TEST_USER_PASSWORD}
    response = api_client.post(url, data, format="json")
    assert response.status_code == 200
    assert "access" in response.json()
    assert "refresh" in response.json()


def test_token_refresh(api_client, create_user_and_get_token):
    """Тестирование POST /auth/refresh/ (AC 3)"""
    email = "refresh_test@example.com"
    # Получаем refresh token
    access_token = create_user_and_get_token(email=email)
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    # Получаем refresh token из ответа логина
    login_url = reverse("users:login")
    login_response = api_client.post(login_url, {"email": email, "password": TEST_USER_PASSWORD}, format="json")
    refresh_token = login_response.json()["refresh"]

    url = reverse("users:token_refresh")
    response = api_client.post(url, {"refresh": refresh_token}, format="json")
    assert response.status_code == 200
    assert "access" in response.json()


def test_user_profile_get_patch(api_client, create_user_and_get_token):
    """Тестирование GET/PATCH /users/profile/ (AC 4)"""
    token = create_user_and_get_token(role="retail", email="profile_test@example.com")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    url = reverse("users:profile")

    # GET профиля
    response = api_client.get(url)
    assert response.status_code == 200
    assert response.json()["email"] == "profile_test@example.com"

    # PATCH профиля
    patch_data = {"first_name": "Updated", "phone": "+79001234567"}
    response = api_client.patch(url, patch_data, format="json")
    assert response.status_code == 200
    assert response.json()["first_name"] == "Updated"
    assert response.json()["phone"] == "+79001234567"


def test_user_roles_endpoint(api_client):
    """Тестирование GET /users/roles/ (AC 5 - часть)"""
    url = reverse("users:roles")
    response = api_client.get(url)
    assert response.status_code == 200
    assert isinstance(response.json()["roles"], list)
    assert len(response.json()["roles"]) > 0
    # Проверяем, что одна из ролей присутствует
    assert any(role["key"] == "retail" for role in response.json()["roles"])

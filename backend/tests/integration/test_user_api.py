import itertools
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from apps.users.models import User

# Используем маркер pytest для доступа к БД во всех тестах этого модуля
pytestmark = pytest.mark.django_db

TEST_USER_PASSWORD = "TestPassword123!"

_TAX_ID_COUNTER = itertools.count(1)


def unique_tax_id() -> str:
    """Уникальный 10-значный ИНН: повтор отклоняется валидацией регистрации."""
    return f"77{next(_TAX_ID_COUNTER) % 10**8:08d}"


@pytest.fixture
def api_client():
    """Фикстура для создания клиента API."""
    return APIClient()


@pytest.fixture
def create_user_and_get_token(api_client):
    """
    Фикстура для регистрации и авторизации пользователя, возвращает токен.
    """

    def _create_user_and_get_token(role="wholesale_level1", email=None):
        if email is None:
            email = f"test_user_{role}@example.com"

        # Удаляем пользователя, если он существует, для чистоты теста
        User.objects.filter(email=email).delete()

        # Розничная саморегистрация отключена: доступны только B2B-роли,
        # каждой из которых обязательны название компании и уникальный ИНН
        registration_data = {
            "email": email,
            "password": TEST_USER_PASSWORD,
            "password_confirm": TEST_USER_PASSWORD,
            "first_name": "Тест",
            "last_name": f"Пользователь {role}",
            "role": role,
            "company_name": f"Тестовая компания {role}",
            "tax_id": unique_tax_id(),
            "pdp_consent": True,
        }

        # Регистрация. Заявка B2B ставит в очередь три письма — глушим, чтобы
        # тесты пользовательского API не зависели от брокера.
        url = reverse("users:register")
        with (
            patch("apps.users.serializers.send_admin_verification_email.delay"),
            patch("apps.users.serializers.send_user_pending_email.delay"),
            patch("apps.users.serializers.send_manager_region_email.delay"),
        ):
            response = api_client.post(url, registration_data, format="json")
        assert response.status_code == 201, (
            f"Registration failed for role {role} with status {response.status_code}: " f"{response.json()}"
        )

        # B2B-заявка создаётся неверифицированной и неактивной — логин
        # возможен только после верификации менеджером
        User.objects.filter(email=email).update(
            is_active=True,
            is_verified=True,
            verification_status="verified",
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
        "role": "trainer",
        "company_name": "Новый клуб",
        "tax_id": unique_tax_id(),
        "pdp_consent": True,
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
    token = create_user_and_get_token(email="profile_test@example.com")
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
    roles = response.json()["roles"]
    assert isinstance(roles, list)
    assert len(roles) > 0
    keys = {role["key"] for role in roles}
    # Эндпоинт отдаёт ровно роли саморегистрации: без служебных и без розницы
    assert "wholesale_level1" in keys
    assert "trainer" in keys
    assert "retail" not in keys
    assert "admin" not in keys
    assert "unregistered" not in keys


@override_settings(REGISTRATION_ALLOW_RETAIL=True)
def test_user_roles_endpoint_follows_retail_flag(api_client):
    """
    Список ролей идёт из того же источника, что и проверка регистрации:
    при включённой рознице витрина не должна отставать от бэкенда.
    """
    url = reverse("users:roles")
    response = api_client.get(url)

    assert response.status_code == 200
    keys = {role["key"] for role in response.json()["roles"]}
    assert "retail" in keys
    # Служебные роли не появляются ни при каком значении флага
    assert "admin" not in keys
    assert "unregistered" not in keys

"""
Functional тесты для Dashboard API с реальными данными заказов
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.mark.django_db
class TestDashboardAPI:
    """Functional тесты для Dashboard API"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.client = APIClient()

    def test_dashboard_with_no_orders(self, user_factory):
        """Тест дашборда без заказов"""
        # Создаем пользователя
        user = user_factory.create(role="retail")

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к дашборду
        response = self.client.get("/api/v1/users/profile/dashboard/")

        assert response.status_code == 200
        data = response.json()

        # Проверяем статистику заказов
        assert data["orders_count"] == 0
        # Для retail пользователей эти поля не возвращаются
        assert "total_order_amount" not in data
        assert "avg_order_amount" not in data

    def test_dashboard_with_orders(self, user_factory, order_factory):
        """Тест дашборда с реальными заказами"""
        # Создаем пользователя
        user = user_factory.create(role="retail")

        # Создаем заказы
        order_factory.create(user=user, status="delivered", total_amount=1000.00)
        order_factory.create(user=user, status="pending", total_amount=2000.00)
        order_factory.create(user=user, status="cancelled", total_amount=500.00)

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к дашборду
        response = self.client.get("/api/v1/users/profile/dashboard/")

        assert response.status_code == 200
        data = response.json()

        # Проверяем статистику заказов
        assert data["orders_count"] == 3
        # Для retail пользователей финансовые данные не возвращаются
        assert "total_order_amount" not in data
        assert "avg_order_amount" not in data

    def test_b2b_dashboard_with_verification_status(self, user_factory, order_factory):
        """Тест B2B дашборда с верификацией"""
        # Создаем B2B пользователя
        user = user_factory.create(role="wholesale_level1", is_verified=True, company_name="Test B2B Company")

        # Создаем заказы
        order_factory.create(user=user, total_amount=5000.00)
        order_factory.create(user=user, total_amount=3000.00)

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к дашборду
        response = self.client.get("/api/v1/users/profile/dashboard/")

        assert response.status_code == 200
        data = response.json()

        # Проверяем B2B специфичные данные
        assert data["orders_count"] == 2
        assert float(data["total_order_amount"]) == 8000.0
        assert float(data["avg_order_amount"]) == 4000.0
        assert data["verification_status"] == "verified"
        assert data["user_info"]["company_name"] == "Test B2B Company"

    def test_dashboard_isolation_between_users(self, user_factory, order_factory):
        """Тест изоляции данных между пользователями"""
        # Создаем двух пользователей
        user1 = user_factory.create(role="retail")
        user2 = user_factory.create(role="retail")

        # Создаем заказы для первого пользователя
        order_factory.create(user=user1, total_amount=1000.00)
        order_factory.create(user=user1, total_amount=2000.00)

        # Создаем заказы для второго пользователя
        order_factory.create(user=user2, total_amount=500.00)

        # Тестируем дашборд первого пользователя
        refresh1 = RefreshToken.for_user(user1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh1.access_token}")

        response1 = self.client.get("/api/v1/users/profile/dashboard/")
        assert response1.status_code == 200
        data1 = response1.json()

        assert data1["orders_count"] == 2
        # Для retail пользователей финансовые данные не возвращаются
        assert "total_order_amount" not in data1

        # Тестируем дашборд второго пользователя
        refresh2 = RefreshToken.for_user(user2)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh2.access_token}")

        response2 = self.client.get("/api/v1/users/profile/dashboard/")
        assert response2.status_code == 200
        data2 = response2.json()

        assert data2["orders_count"] == 1
        # Для retail пользователей финансовые данные не возвращаются
        assert "total_order_amount" not in data2

    def test_dashboard_unauthorized(self):
        """Тест дашборда без авторизации"""
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 401

"""
Functional тесты для Order History API
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.mark.django_db
class TestOrderHistoryAPI:
    """Functional тесты для Order History API"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.client = APIClient()

    def test_order_history_empty(self, user_factory):
        """Тест пустой истории заказов"""
        user = user_factory.create(role="retail")

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к истории заказов
        response = self.client.get("/api/v1/users/orders/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 0
        assert data["results"] == []

    def test_order_history_with_orders(self, user_factory, order_factory):
        """Тест истории с заказами"""
        user = user_factory.create(role="retail")

        # Создаем заказы
        order_factory.create(user=user, order_number="TEST-001", status="delivered", total_amount=1000.00)
        order_factory.create(user=user, order_number="TEST-002", status="pending", total_amount=2000.00)

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к истории заказов
        response = self.client.get("/api/v1/users/orders/")

        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        assert len(data["results"]) == 2

        # Проверяем структуру данных (должна соответствовать OrderHistorySerializer)
        order_data = data["results"][0]  # Первый заказ (самый новый)
        expected_fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "total_amount",
            "discount_amount",
            "delivery_cost",
            "items_count",
            "customer_display_name",
            "created_at",
            "updated_at",
        ]
        for field in expected_fields:
            assert field in order_data, f"Поле {field} отсутствует"

    def test_order_history_filtering(self, user_factory, order_factory):
        """Тест фильтрации по статусу"""
        user = user_factory.create(role="retail")

        # Создаем заказы с разными статусами
        order_factory.create(user=user, status="pending")
        order_factory.create(user=user, status="delivered")
        order_factory.create(user=user, status="pending")

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Тест фильтрации по статусу 'pending'
        response = self.client.get("/api/v1/users/orders/?status=pending")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 2
        for order in data["results"]:
            assert order["status"] == "pending"

        # Тест фильтрации по статусу 'delivered'
        response = self.client.get("/api/v1/users/orders/?status=delivered")
        assert response.status_code == 200
        data = response.json()
        assert data["count"] == 1
        assert data["results"][0]["status"] == "delivered"

    def test_order_history_sorting(self, user_factory, order_factory):
        """Тест сортировки по дате создания"""
        user = user_factory.create(role="retail")

        # Создаем заказы (они будут созданы в хронологическом порядке)
        order_factory.create(user=user, order_number="FIRST")
        order_factory.create(user=user, order_number="SECOND")
        order_factory.create(user=user, order_number="THIRD")

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Запрос к истории заказов
        response = self.client.get("/api/v1/users/orders/")
        assert response.status_code == 200
        data = response.json()

        # Проверяем что заказы отсортированы по убыванию даты (новые первыми)
        order_numbers = [order["order_number"] for order in data["results"]]
        assert order_numbers[0] == "THIRD"  # Самый новый
        assert order_numbers[1] == "SECOND"
        assert order_numbers[2] == "FIRST"  # Самый старый

    def test_order_history_isolation(self, user_factory, order_factory):
        """Тест изоляции данных между пользователями"""
        user1 = user_factory.create(role="retail")
        user2 = user_factory.create(role="retail")

        # Создаем заказы для разных пользователей
        order_factory.create(user=user1, order_number="USER1-ORDER")
        order_factory.create(user=user2, order_number="USER2-ORDER")

        # Тестируем первого пользователя
        refresh1 = RefreshToken.for_user(user1)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh1.access_token}")

        response1 = self.client.get("/api/v1/users/orders/")
        assert response1.status_code == 200
        data1 = response1.json()
        assert data1["count"] == 1
        assert data1["results"][0]["order_number"] == "USER1-ORDER"

        # Тестируем второго пользователя
        refresh2 = RefreshToken.for_user(user2)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh2.access_token}")

        response2 = self.client.get("/api/v1/users/orders/")
        assert response2.status_code == 200
        data2 = response2.json()
        assert data2["count"] == 1
        assert data2["results"][0]["order_number"] == "USER2-ORDER"

    def test_order_history_unauthorized(self):
        """Тест доступа без авторизации"""
        response = self.client.get("/api/v1/users/orders/")
        assert response.status_code == 401

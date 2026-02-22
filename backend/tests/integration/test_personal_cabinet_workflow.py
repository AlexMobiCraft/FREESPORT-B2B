"""
Интеграционные тесты для полного workflow Personal Cabinet
"""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@pytest.mark.django_db
class TestPersonalCabinetWorkflow:
    """Интеграционные тесты полного workflow личного кабинета"""

    def setup_method(self):
        """Настройка для каждого теста"""
        self.client = APIClient()

    def test_complete_order_workflow(self, user_factory, order_factory, order_item_factory, product_factory):
        """
        Тест полного workflow: создание заказа → отображение в дашборде →
        история заказов
        """

        # Шаг 1: Создаем пользователя
        user = user_factory.create(
            role="wholesale_level1",
            is_verified=True,
            company_name="Test Integration Company",
        )

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Шаг 2: Проверяем начальное состояние дашборда (без заказов)
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        initial_data = response.json()
        assert initial_data["orders_count"] == 0
        assert initial_data["total_order_amount"] is None
        assert initial_data["verification_status"] == "verified"

        # Шаг 3: Проверяем пустую историю заказов
        response = self.client.get("/api/v1/users/orders/")
        assert response.status_code == 200
        history_data = response.json()
        assert history_data["count"] == 0
        assert history_data["results"] == []

        # Шаг 4: Создаем заказы с товарами
        product1 = product_factory.create(name="Test Product 1")
        product2 = product_factory.create(name="Test Product 2")

        order1 = order_factory.create(
            user=user,
            order_number="INT-001",
            status="pending",
            total_amount=5000.00,
            discount_amount=200.00,
            delivery_cost=300.00,
        )

        # Создаем варианты для товаров
        variant1 = product1.variants.create(sku="PROD1-VAR1", retail_price=2000.00, onec_id="PROD1-VAR1-1C")
        variant2 = product2.variants.create(sku="PROD2-VAR1", retail_price=1000.00, onec_id="PROD2-VAR1-1C")

        # Добавляем товары в заказ
        order_item_factory.create(
            order=order1,
            product=product1,
            variant=variant1,
            quantity=2,
            unit_price=2000.00,
        )
        order_item_factory.create(
            order=order1,
            product=product2,
            variant=variant2,
            quantity=1,
            unit_price=1000.00,
        )

        order2 = order_factory.create(
            user=user,
            order_number="INT-002",
            status="delivered",
            total_amount=3000.00,
            discount_amount=100.00,
            delivery_cost=200.00,
        )

        order_item_factory.create(
            order=order2,
            product=product1,
            variant=variant1,
            quantity=1,
            unit_price=3000.00,
        )

        # Шаг 5: Проверяем обновленный дашборд
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        updated_data = response.json()

        assert updated_data["orders_count"] == 2
        assert float(updated_data["total_order_amount"]) == 8000.0
        assert float(updated_data["avg_order_amount"]) == 4000.0
        assert updated_data["verification_status"] == "verified"
        assert updated_data["user_info"]["company_name"] == "Test Integration Company"

        # Шаг 6: Проверяем историю заказов
        response = self.client.get("/api/v1/users/orders/")
        assert response.status_code == 200
        history_data = response.json()

        assert history_data["count"] == 2
        assert len(history_data["results"]) == 2

        # Проверяем данные первого заказа (самый новый)
        latest_order = history_data["results"][0]
        assert latest_order["order_number"] == "INT-002"
        assert latest_order["status"] == "delivered"
        assert float(latest_order["total_amount"]) == 3000.0
        assert float(latest_order["discount_amount"]) == 100.0
        assert float(latest_order["delivery_cost"]) == 200.0
        assert latest_order["items_count"] == 1  # 1 товар

        # Проверяем данные второго заказа
        older_order = history_data["results"][1]
        assert older_order["order_number"] == "INT-001"
        assert older_order["status"] == "pending"
        assert float(older_order["total_amount"]) == 5000.0
        assert older_order["items_count"] == 3  # 2 + 1 товар

        # Шаг 7: Тестируем фильтрацию истории заказов
        response = self.client.get("/api/v1/users/orders/?status=pending")
        assert response.status_code == 200
        filtered_data = response.json()
        assert filtered_data["count"] == 1
        assert filtered_data["results"][0]["order_number"] == "INT-001"

        # Шаг 8: Создаем еще один заказ и проверяем обновления
        order_factory.create(
            user=user,
            order_number="INT-003",
            status="cancelled",
            total_amount=1500.00,
        )

        # Проверяем финальное состояние дашборда
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        final_data = response.json()

        assert final_data["orders_count"] == 3
        assert float(final_data["total_order_amount"]) == 9500.0
        assert abs(float(final_data["avg_order_amount"]) - 3166.67) < 0.01

    def test_b2c_vs_b2b_workflow_differences(self, user_factory, order_factory):
        """Тест различий в workflow между B2C и B2B пользователями"""

        # Создаем B2C пользователя
        b2c_user = user_factory.create(role="retail")
        order_factory.create(user=b2c_user, total_amount=1000.00)

        # Создаем B2B пользователя
        b2b_user = user_factory.create(
            role="wholesale_level2",
            is_verified=True,
            company_name="B2B Test Company",
        )
        order_factory.create(user=b2b_user, total_amount=5000.00)

        # Тестируем B2C дашборд
        refresh_b2c = RefreshToken.for_user(b2c_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_b2c.access_token}")

        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        b2c_data = response.json()

        assert b2c_data["orders_count"] == 1
        # B2C пользователи не видят финансовые данные
        assert "total_order_amount" not in b2c_data
        assert "avg_order_amount" not in b2c_data
        assert "verification_status" not in b2c_data

        # Тестируем B2B дашборд
        refresh_b2b = RefreshToken.for_user(b2b_user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh_b2b.access_token}")

        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        b2b_data = response.json()

        assert b2b_data["orders_count"] == 1
        # B2B пользователи видят все данные
        assert float(b2b_data["total_order_amount"]) == 5000.0
        assert float(b2b_data["avg_order_amount"]) == 5000.0
        assert b2b_data["verification_status"] == "verified"
        assert b2b_data["user_info"]["company_name"] == "B2B Test Company"

    def test_error_handling_workflow(self, user_factory):
        """Тест обработки ошибок в workflow"""

        user = user_factory.create(role="retail")

        # Тест без авторизации
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 401

        response = self.client.get("/api/v1/users/orders/")
        assert response.status_code == 401

        # Аутентификация
        refresh = RefreshToken.for_user(user)
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Тест с неверными параметрами фильтрации
        response = self.client.get("/api/v1/users/orders/?status=invalid_status")
        assert response.status_code == 200  # Должен вернуть пустой результат
        data = response.json()
        assert data["count"] == 0

        # Тест корректной работы при отсутствии данных
        response = self.client.get("/api/v1/users/profile/dashboard/")
        assert response.status_code == 200
        data = response.json()
        assert data["orders_count"] == 0

"""
API тесты для AttributeFilterViewSet (Story 14.3.6)

Тестирует endpoint /api/v1/catalog/filters/ с фильтрацией
активных атрибутов и параметром include_inactive для staff users.
"""

from __future__ import annotations

from typing import Any

import pytest
from django.conf import settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.models import Attribute, AttributeValue
from apps.users.models import User


@pytest.mark.django_db
class TestAttributeFilterViewSet:
    """Тесты для AttributeFilterViewSet (Story 14.3.6)"""

    @pytest.fixture
    def api_client(self) -> APIClient:
        """Fixture для API клиента"""
        return APIClient()

    @pytest.fixture
    def staff_user(self, db: Any) -> User:
        """Fixture для staff пользователя"""
        return User.objects.create_user(
            email="staff@test.com",
            password="testpass123",
            is_staff=True,
        )

    @pytest.fixture
    def regular_user(self, db: Any) -> User:
        """Fixture для обычного пользователя"""
        return User.objects.create_user(
            email="user@test.com",
            password="testpass123",
            is_staff=False,
        )

    @pytest.fixture
    def active_attribute(self, db: Any) -> Attribute:
        """Fixture для активного атрибута"""
        attr = Attribute.objects.create(
            name="Цвет",
            is_active=True,
        )
        AttributeValue.objects.create(attribute=attr, value="Красный")
        AttributeValue.objects.create(attribute=attr, value="Синий")
        return attr

    @pytest.fixture
    def inactive_attribute(self, db: Any) -> Attribute:
        """Fixture для неактивного атрибута"""
        attr = Attribute.objects.create(
            name="Материал",
            is_active=False,
        )
        AttributeValue.objects.create(attribute=attr, value="Хлопок")
        return attr

    def test_catalog_filters_returns_only_active_attributes(
        self,
        api_client: APIClient,
        active_attribute: Attribute,
        inactive_attribute: Attribute,
    ) -> None:
        """
        AC 14.3.6.1: GET /catalog/filters/ возвращает только активные атрибуты

        Анонимный пользователь должен видеть только атрибуты с is_active=True.
        """
        url = reverse("products:catalog-filter-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Проверяем структуру ответа (может быть с пагинацией или без)
        results = data.get("results", data)
        if isinstance(results, dict):
            results = [results]

        # Должен быть только активный атрибут
        attribute_names = [attr["name"] for attr in results]
        assert "Цвет" in attribute_names
        assert "Материал" not in attribute_names

    def test_catalog_filters_include_inactive_for_staff(
        self,
        api_client: APIClient,
        staff_user: User,
        active_attribute: Attribute,
        inactive_attribute: Attribute,
    ) -> None:
        """
        AC 14.3.6.3: include_inactive=true работает для staff users

        Staff users с параметром include_inactive=true должны видеть
        все атрибуты, включая неактивные.
        """
        api_client.force_authenticate(user=staff_user)

        url = reverse("products:catalog-filter-list")
        response = api_client.get(url, {"include_inactive": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        results = data.get("results", data)
        if isinstance(results, dict):
            results = [results]

        # Должны быть оба атрибута
        attribute_names = [attr["name"] for attr in results]
        assert "Цвет" in attribute_names
        assert "Материал" in attribute_names

    def test_catalog_filters_include_inactive_ignored_for_regular_user(
        self,
        api_client: APIClient,
        regular_user: User,
        active_attribute: Attribute,
        inactive_attribute: Attribute,
    ) -> None:
        """
        AC 14.3.6.3: include_inactive=true игнорируется для обычных пользователей

        Обычные пользователи не должны видеть неактивные атрибуты,
        даже если передан параметр include_inactive=true.
        """
        api_client.force_authenticate(user=regular_user)

        url = reverse("products:catalog-filter-list")
        response = api_client.get(url, {"include_inactive": "true"})

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        results = data.get("results", data)
        if isinstance(results, dict):
            results = [results]

        # Должен быть только активный атрибут
        attribute_names = [attr["name"] for attr in results]
        assert "Цвет" in attribute_names
        assert "Материал" not in attribute_names

    def test_catalog_filters_returns_attribute_values(self, api_client: APIClient, active_attribute: Attribute) -> None:
        """
        AC 14.3.6.2: Ответ содержит значения атрибутов

        Каждый атрибут должен содержать список значений с id, value и slug.
        """
        url = reverse("products:catalog-filter-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        results = data.get("results", data)
        if isinstance(results, dict):
            results = [results]

        # Находим атрибут "Цвет"
        color_attr = next((a for a in results if a["name"] == "Цвет"), None)
        assert color_attr is not None

        # Проверяем структуру атрибута
        assert "id" in color_attr
        assert "name" in color_attr
        assert "slug" in color_attr
        assert "values" in color_attr

        # Проверяем значения
        values = color_attr["values"]
        assert len(values) == 2

        value_names = [v["value"] for v in values]
        assert "Красный" in value_names
        assert "Синий" in value_names

        # Проверяем структуру каждого значения
        for value in values:
            assert "id" in value
            assert "value" in value
            assert "slug" in value

    def test_catalog_filters_empty_when_no_active_attributes(self, api_client, db):
        """
        Если нет активных атрибутов, должен вернуться пустой список.
        """
        # Создаем только неактивный атрибут
        Attribute.objects.create(name="Неактивный", is_active=False)

        url = reverse("products:catalog-filter-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        results = data.get("results", data)
        if isinstance(results, dict):
            results = [results] if results else []

        # Без пагинации массив должен быть пустым
        if isinstance(data, list):
            assert len(data) == 0
        else:
            # С пагинацией count должен быть 0
            assert data.get("count", len(results)) == 0


@pytest.mark.django_db
class TestCatalogFiltersIntegration:
    """Интеграционные тесты для /catalog/filters/"""

    @pytest.fixture
    def api_client(self) -> APIClient:
        return APIClient()

    def test_prefetch_related_used_no_n_plus_one(self, api_client, db, django_assert_num_queries):
        """
        Тест: prefetch_related используется (избегаем N+1 queries)

        Должно быть фиксированное количество запросов независимо от
        количества атрибутов и значений.
        """
        # Создаем 10 атрибутов с 5 значениями каждый
        for i in range(10):
            attr = Attribute.objects.create(name=f"Атрибут {i}", is_active=True)
            for j in range(5):
                AttributeValue.objects.create(attribute=attr, value=f"Значение {j}")

        url = reverse("products:catalog-filter-list")

        # Calculate expected queries based on ATOMIC_REQUESTS
        # 3 base queries:
        # 1. SELECT Attributes
        # 2. SELECT AttributeValues
        # 3. COUNT
        expected_queries = 3
        if settings.DATABASES["default"].get("ATOMIC_REQUESTS", False):
            expected_queries += 2  # SAVEPOINT + RELEASE SAVEPOINT

        # Главное: НЕ должно быть N+1, т.е. количество не должно расти с числом атрибутов
        with django_assert_num_queries(expected_queries):
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK

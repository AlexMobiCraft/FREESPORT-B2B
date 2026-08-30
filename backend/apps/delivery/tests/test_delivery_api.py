"""
Тесты для API способов доставки.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from rest_framework.test import APIClient

from apps.delivery.models import DeliveryMethod

if TYPE_CHECKING:
    from collections.abc import Sequence


@pytest.fixture
def api_client() -> APIClient:
    """Возвращает API клиент для тестирования."""
    return APIClient()


@pytest.fixture
def delivery_methods() -> Sequence[DeliveryMethod]:
    """Создаёт тестовые способы доставки."""
    return [
        DeliveryMethod.objects.create(
            id="courier",
            name="Курьер",
            description="До двери",
            icon="truck",
            is_available=True,
            sort_order=1,
        ),
        DeliveryMethod.objects.create(
            id="pickup",
            name="Самовывоз",
            description="Забрать",
            icon="store",
            is_available=True,
            sort_order=2,
        ),
        DeliveryMethod.objects.create(
            id="disabled",
            name="Отключён",
            description="",
            icon="x",
            is_available=False,
            sort_order=3,
        ),
    ]


@pytest.mark.django_db
class TestDeliveryMethodsListAPI:
    """Тесты для GET /api/v1/delivery/methods/."""

    def test_list_returns_available_methods(
        self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]
    ) -> None:
        """Проверяет, что API возвращает только доступные способы доставки."""
        response = api_client.get("/api/v1/delivery/methods/")
        assert response.status_code == 200
        if isinstance(response.data, list):
            results = response.data
        else:
            results = response.data.get("results", response.data)
        assert len(results) == 2  # Только is_available=True

    def test_list_excludes_unavailable(self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]) -> None:
        """Проверяет, что недоступные способы исключаются из списка."""
        response = api_client.get("/api/v1/delivery/methods/")
        if isinstance(response.data, list):
            results = response.data
        else:
            results = response.data.get("results", response.data)
        ids = [m["id"] for m in results]
        assert "disabled" not in ids

    def test_response_structure(self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]) -> None:
        """Проверяет структуру ответа API."""
        response = api_client.get("/api/v1/delivery/methods/")
        if isinstance(response.data, list):
            results = response.data
        else:
            results = response.data.get("results", response.data)
        method = results[0]
        assert "id" in method
        assert "name" in method
        assert "description" in method
        assert "icon" in method
        assert "is_available" in method

    def test_empty_list_returns_200(self, api_client: APIClient) -> None:
        """Проверяет, что пустой список возвращает 200."""
        response = api_client.get("/api/v1/delivery/methods/")
        assert response.status_code == 200
        if isinstance(response.data, list):
            results = response.data
        else:
            results = response.data.get("results", response.data)
        assert results == []

    def test_ordering_by_sort_order(self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]) -> None:
        """Проверяет сортировку по sort_order."""
        response = api_client.get("/api/v1/delivery/methods/")
        if isinstance(response.data, list):
            results = response.data
        else:
            results = response.data.get("results", response.data)
        ids = [m["id"] for m in results]
        assert ids == ["courier", "pickup"]  # Сортировка по sort_order


@pytest.mark.django_db
class TestDeliveryMethodRetrieveAPI:
    """Тесты для GET /api/v1/delivery/methods/{id}/."""

    def test_retrieve_single_method(self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]) -> None:
        """Проверяет получение одного способа доставки по ID."""
        response = api_client.get("/api/v1/delivery/methods/courier/")
        assert response.status_code == 200
        assert response.data["id"] == "courier"
        assert response.data["name"] == "Курьер"
        assert response.data["icon"] == "truck"

    def test_retrieve_unavailable_method_returns_404(
        self, api_client: APIClient, delivery_methods: Sequence[DeliveryMethod]
    ) -> None:
        """Проверяет, что недоступный способ возвращает 404."""
        response = api_client.get("/api/v1/delivery/methods/disabled/")
        assert response.status_code == 404

    def test_retrieve_nonexistent_method_returns_404(self, api_client: APIClient) -> None:
        """Проверяет, что несуществующий ID возвращает 404."""
        response = api_client.get("/api/v1/delivery/methods/nonexistent/")
        assert response.status_code == 404


@pytest.mark.django_db
class TestDeliveryMethodModel:
    """Тесты для модели DeliveryMethod."""

    def test_str_returns_name(self) -> None:
        """Проверяет, что __str__ возвращает название способа доставки."""
        method = DeliveryMethod.objects.create(
            id="test_method",
            name="Тестовый способ",
            description="Описание",
            is_available=True,
            sort_order=1,
        )
        assert str(method) == "Тестовый способ"

    def test_default_values(self) -> None:
        """Проверяет значения по умолчанию."""
        method = DeliveryMethod.objects.create(
            id="minimal",
            name="Минимальный",
        )
        assert method.is_available is True
        assert method.sort_order == 0
        assert method.description == ""
        assert method.icon == ""

    def test_ordering(self) -> None:
        """Проверяет порядок сортировки по sort_order и name."""
        DeliveryMethod.objects.create(id="c", name="C Method", sort_order=2)
        DeliveryMethod.objects.create(id="a", name="A Method", sort_order=1)
        DeliveryMethod.objects.create(id="b", name="B Method", sort_order=1)

        methods = list(DeliveryMethod.objects.all())
        assert methods[0].id == "a"  # sort_order=1, name=A
        assert methods[1].id == "b"  # sort_order=1, name=B
        assert methods[2].id == "c"  # sort_order=2

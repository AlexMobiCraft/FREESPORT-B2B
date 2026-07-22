"""
Unit-тесты полей интеграции с 1С для модели Order.
Story 4.1: sent_to_1c, sent_to_1c_at, status_1c

Расположение: backend/tests/unit/test_orders_1c_fields.py
Соответствует: docs/architecture/10-testing-strategy.md §10.2, §10.6
"""

import pytest
from django.utils import timezone

from apps.orders.models import Order
from apps.orders.serializers import OrderCreateSerializer, OrderDetailSerializer, OrderListSerializer

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


class TestOrder1CFieldsDefaults:
    """AC5: Тест дефолтных значений sent_to_1c, sent_to_1c_at, status_1c."""

    def test_default_sent_to_1c_is_false(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        order.refresh_from_db()

        # ASSERT
        assert order.sent_to_1c is False

    def test_default_sent_to_1c_at_is_none(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        order.refresh_from_db()

        # ASSERT
        assert order.sent_to_1c_at is None

    def test_default_status_1c_is_empty_string(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        order.refresh_from_db()

        # ASSERT
        assert order.status_1c == ""


class TestOrder1CFieldsSetValues:
    """Тест установки значений полей 1С."""

    def test_set_sent_to_1c_true(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        order.sent_to_1c = True
        order.save()
        order.refresh_from_db()

        # ASSERT
        assert order.sent_to_1c is True

    def test_set_sent_to_1c_at_stores_datetime(self, order_factory):
        # ARRANGE
        order = order_factory.create()
        now = timezone.now()

        # ACT
        order.sent_to_1c_at = now
        order.save()
        order.refresh_from_db()

        # ASSERT
        assert order.sent_to_1c_at is not None
        assert abs((order.sent_to_1c_at - now).total_seconds()) < 1

    def test_set_status_1c_stores_text(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        order.status_1c = "Отгружен"
        order.save()
        order.refresh_from_db()

        # ASSERT
        assert order.status_1c == "Отгружен"


class TestOrder1CFieldsFilter:
    """Тест фильтрации по sent_to_1c."""

    def test_filter_not_sent_excludes_sent_orders(self, order_factory):
        # ARRANGE
        order_not_sent = order_factory.create()
        order_sent = order_factory.create()
        order_sent.sent_to_1c = True
        order_sent.save()

        # ACT
        not_sent_qs = Order.objects.filter(sent_to_1c=False)

        # ASSERT
        assert order_not_sent in not_sent_qs
        assert order_sent not in not_sent_qs


class TestOrder1CFieldsSerialization:
    """Тесты сериализации полей 1С в OrderDetailSerializer и OrderListSerializer."""

    def test_detail_serializer_includes_1c_fields(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        data = OrderDetailSerializer(order).data

        # ASSERT
        assert "sent_to_1c" in data
        assert "sent_to_1c_at" in data
        assert "status_1c" in data
        assert data["sent_to_1c"] is False
        assert data["sent_to_1c_at"] is None
        assert data["status_1c"] == ""

    def test_list_serializer_includes_sent_to_1c(self, order_factory):
        # ARRANGE
        order = order_factory.create()

        # ACT
        data = OrderListSerializer(order).data

        # ASSERT
        assert "sent_to_1c" in data

    def test_create_serializer_excludes_1c_fields(self):
        """AC: sent_to_1c, sent_to_1c_at, status_1c НЕ в OrderCreateSerializer."""
        # ARRANGE / ACT
        fields = OrderCreateSerializer().fields

        # ASSERT
        assert "sent_to_1c" not in fields
        assert "sent_to_1c_at" not in fields
        assert "status_1c" not in fields

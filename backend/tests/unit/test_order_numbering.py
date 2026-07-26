import re
from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.db import transaction

from apps.orders.models import CustomerCodeSequence, CustomerOrderSequence, Order, OrderItem
from apps.orders.services.order_numbering import (
    CustomerCodeSequenceExhausted,
    OrderNumberSequenceExhausted,
    OrderNumberingService,
    format_order_number,
    normalize_order_number_query,
)
from apps.orders.tasks import _get_order_display_items
from tests.conftest import UserFactory
from tests.factories import ProductVariantFactory


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestOrderNumberingService:
    def test_next_master_number_generates_customer_year_sequence(self, monkeypatch):
        user = UserFactory.create(customer_code="04620")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))

        with transaction.atomic():
            first = OrderNumberingService.next_master_number(user)
        with transaction.atomic():
            second = OrderNumberingService.next_master_number(user)

        assert first.order_number == "0462026001"
        assert second.order_number == "0462026002"
        counter = CustomerOrderSequence.objects.get(customer_code="04620", year=2026)
        assert counter.last_sequence == 2

    def test_next_master_number_auto_assigns_customer_code(self, monkeypatch):
        user = UserFactory.create(customer_code="")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))

        with transaction.atomic():
            result = OrderNumberingService.next_master_number(user)

        assert re.fullmatch(r"\d{5}", result.customer_code_snapshot)
        user.refresh_from_db()
        assert user.customer_code == result.customer_code_snapshot

    def test_next_master_number_preserves_existing_customer_code(self, monkeypatch):
        user = UserFactory.create(customer_code="05000")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))

        with transaction.atomic():
            result = OrderNumberingService.next_master_number(user)

        assert result.customer_code_snapshot == "05000"
        user.refresh_from_db()
        assert user.customer_code == "05000"
        assert not CustomerCodeSequence.objects.exists()

    def test_next_master_number_assigns_unique_codes_to_different_users(self, monkeypatch):
        first_user = UserFactory.create(customer_code="")
        second_user = UserFactory.create(customer_code="")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))

        with transaction.atomic():
            first_result = OrderNumberingService.next_master_number(first_user)
        with transaction.atomic():
            second_result = OrderNumberingService.next_master_number(second_user)

        assert first_result.customer_code_snapshot != second_result.customer_code_snapshot
        first_user.refresh_from_db()
        second_user.refresh_from_db()
        assert first_user.customer_code == first_result.customer_code_snapshot
        assert second_user.customer_code == second_result.customer_code_snapshot

    def test_next_master_number_skips_customer_code_taken_out_of_band(self, monkeypatch):
        """Код, занятый в обход счётчика (например, вручную через админку),

        не должен приводить к необработанному IntegrityError -- сервис
        обязан пропустить занятое значение и подобрать следующее свободное.
        """
        CustomerCodeSequence.objects.create(pk=1, last_value=0)
        UserFactory.create(customer_code="00001")  # занял код в обход счётчика
        user = UserFactory.create(customer_code="")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))

        with transaction.atomic():
            result = OrderNumberingService.next_master_number(user)

        assert result.customer_code_snapshot == "00002"
        user.refresh_from_db()
        assert user.customer_code == "00002"
        assert CustomerCodeSequence.objects.get(pk=1).last_value == 2

    def test_next_master_number_raises_when_customer_code_sequence_exhausted(self, monkeypatch):
        user = UserFactory.create(customer_code="")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))
        CustomerCodeSequence.objects.create(pk=1, last_value=99999)

        with transaction.atomic(), pytest.raises(CustomerCodeSequenceExhausted):
            OrderNumberingService.next_master_number(user)

        counter = CustomerCodeSequence.objects.get(pk=1)
        assert counter.last_value == 99999

    def test_sequence_overflow_raises_exhausted(self, monkeypatch):
        user = UserFactory.create(customer_code="99999")
        monkeypatch.setattr("apps.orders.services.order_numbering.timezone.localdate", lambda: date(2026, 5, 2))
        CustomerOrderSequence.objects.create(customer_code="99999", year=2026, last_sequence=999)

        with transaction.atomic(), pytest.raises(OrderNumberSequenceExhausted):
            OrderNumberingService.next_master_number(user)

        # Счётчик не должен превысить 999
        counter = CustomerOrderSequence.objects.get(customer_code="99999", year=2026)
        assert counter.last_sequence == 999

    def test_build_suborder_number_inherits_master_fields(self):
        master = Order(
            order_number="0462026007",
            customer_code_snapshot="04620",
            order_year=2026,
            customer_year_sequence=7,
            total_amount="0",
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )

        suborder = OrderNumberingService.build_suborder_number(master, 2)

        assert suborder.order_number == "04620260072"
        assert suborder.customer_code_snapshot == "04620"
        assert suborder.order_year == 2026
        assert suborder.customer_year_sequence == 7
        assert suborder.suborder_sequence == 2


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestEmailSignalIsMasterGuard:
    def test_email_tasks_not_queued_for_suborders(self):
        """Сигнал должен ставить email-задачи только для master-заказов."""
        user = UserFactory.create(customer_code="11111")

        master = Order.objects.create(
            order_number="1111126001",
            user=user,
            is_master=True,
            total_amount=Decimal("100"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            customer_code_snapshot="11111",
            order_year=2026,
            customer_year_sequence=1,
        )
        suborder = Order(
            order_number="11111260011",
            user=user,
            is_master=False,
            parent_order=master,
            total_amount=Decimal("100"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            customer_code_snapshot="11111",
            order_year=2026,
            customer_year_sequence=1,
            suborder_sequence=1,
        )

        with patch("apps.orders.tasks.send_order_confirmation_to_customer") as mock_customer, \
             patch("apps.orders.tasks.send_order_notification_email") as mock_admin:
            suborder.save()
            mock_customer.delay.assert_not_called()
            mock_admin.delay.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db(transaction=True)
class TestGetOrderDisplayItems:
    def _make_order_item(self, order, name="Товар", sku="SKU1", qty=2, price=Decimal("50")):
        variant = ProductVariantFactory.create(sku=sku, retail_price=price)
        return OrderItem.objects.create(
            order=order,
            product=variant.product,
            variant=variant,
            quantity=qty,
            unit_price=price,
        )

    def test_master_with_suborders_returns_suborder_items(self):
        user = UserFactory.create(customer_code="22222")
        master = Order.objects.create(
            order_number="2222226001",
            user=user,
            is_master=True,
            total_amount=Decimal("0"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            customer_code_snapshot="22222",
            order_year=2026,
            customer_year_sequence=1,
        )
        sub = Order.objects.create(
            order_number="22222260011",
            user=user,
            is_master=False,
            parent_order=master,
            total_amount=Decimal("0"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
            customer_code_snapshot="22222",
            order_year=2026,
            customer_year_sequence=1,
            suborder_sequence=1,
        )
        item = self._make_order_item(sub, sku="TST-A1")

        items = list(_get_order_display_items(master))
        assert len(items) == 1
        assert items[0].pk == item.pk

    def test_legacy_order_without_suborders_returns_direct_items(self):
        user = UserFactory.create(customer_code="33333")
        legacy = Order.objects.create(
            order_number="legacy-uuid-test",
            user=user,
            is_master=True,
            total_amount=Decimal("0"),
            delivery_address="Test",
            delivery_method="courier",
            payment_method="card",
        )
        item = self._make_order_item(legacy, sku="TST-B1")

        items = list(_get_order_display_items(legacy))
        assert len(items) == 1
        assert items[0].pk == item.pk


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderNumberFormatting:
    def test_format_order_number_formats_master_suborder_and_legacy(self):
        assert format_order_number("0462026007") == "4620-26007"
        assert format_order_number("04620260071") == "04620-26007-1"
        assert format_order_number("legacy-uuid") == "legacy-uuid"

    def test_normalize_order_number_query_supports_ui_and_canonical_variants(self):
        assert normalize_order_number_query("0462026007") == ["0462026007"]
        assert normalize_order_number_query("4620-26007") == ["462026007"]
        assert normalize_order_number_query("04620-26007-1") == ["04620260071"]
        assert normalize_order_number_query("04620260071") == ["04620260071"]
        assert normalize_order_number_query("invalid") == []

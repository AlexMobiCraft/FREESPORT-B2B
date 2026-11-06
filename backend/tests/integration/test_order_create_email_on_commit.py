"""
CAP-1: письма о новом заказе ставятся в очередь только после фиксации заказа.

Проверяем через `OrderCreateService`: до коммита задач нет, после коммита каждая
поставлена один раз и находит заказ со всеми позициями, при откате не ставятся.
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.orders.services.order_create import OrderCreateService
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()

VALIDATED_DATA = {
    "delivery_address": "г. Москва, ул. Тестовая, д. 1",
    "delivery_method": "courier",
    "payment_method": "card",
}


@pytest.fixture
def cart_with_item(db):
    """Корзина клиента с одной позицией (запас 10 шт.)."""

    def build(quantity=1, stock=10):
        user = User.objects.create_user(
            email=f"oncommit{quantity}{stock}@example.com",
            password="testpass",
            role="retail",
            customer_code="04621",
        )
        brand = Brand.objects.create(name="OC Brand", slug="oc-brand")
        category = Category.objects.create(name="OC Category", slug="oc-category")
        product = Product.objects.create(name="OC Product", slug="oc-product", brand=brand, category=category)
        variant = ProductVariant.objects.create(
            product=product,
            sku="OC001",
            onec_id="1C-OC001",
            retail_price=Decimal("100.00"),
            stock_quantity=max(stock, quantity),
            is_active=True,
        )
        cart = Cart.objects.create(user=user)
        CartItem.objects.create(cart=cart, variant=variant, quantity=quantity, price_snapshot=variant.retail_price)
        # Запас уменьшаем после добавления: CartItem.save() проверяет остаток
        ProductVariant.objects.filter(pk=variant.pk).update(stock_quantity=stock)
        return user, cart

    return build


@pytest.mark.integration
@pytest.mark.django_db
class TestOrderEmailTasksOnCommit:
    def _service(self, user, cart):
        return OrderCreateService(cart, user, dict(VALIDATED_DATA), Decimal("500.00"))

    def test_tasks_queued_only_after_commit_and_see_all_items(self, cart_with_item, django_capture_on_commit_callbacks):
        user, cart = cart_with_item()
        seen = {}

        def record_state(order_id):
            """Состояние заказа на момент постановки задачи, как его увидел бы воркер."""
            seen["master"] = Order.objects.filter(pk=order_id, is_master=True).exists()
            seen["items"] = OrderItem.objects.filter(order__parent_order_id=order_id).count()

        with patch("apps.orders.tasks.send_order_confirmation_to_customer") as customer, patch(
            "apps.orders.tasks.send_order_notification_email"
        ) as recipients:
            customer.delay.side_effect = record_state
            # Внешняя транзакция задаёт момент коммита: внутренний atomic сервиса
            # без неё был бы внешним и сам зафиксировал бы заказ. Захват колбэков
            # нужен на случай, когда БД теста обёрнута своей транзакцией.
            with django_capture_on_commit_callbacks(execute=True):
                with transaction.atomic():
                    master = self._service(user, cart).create()
                    # До коммита: задачи не поставлены
                    customer.delay.assert_not_called()
                    recipients.delay.assert_not_called()

        # После коммита: по одной задаче на заказ (субзаказ задач не ставит)
        customer.delay.assert_called_once_with(master.id)
        recipients.delay.assert_called_once_with(master.id)
        assert Order.objects.filter(parent_order=master).count() == 1
        assert seen == {"master": True, "items": 1}

    def test_rollback_queues_nothing(self, cart_with_item, django_capture_on_commit_callbacks):
        # Запас меньше количества в корзине: create() откатывает транзакцию целиком
        user, cart = cart_with_item(quantity=5, stock=1)

        with patch("apps.orders.tasks.send_order_confirmation_to_customer") as customer, patch(
            "apps.orders.tasks.send_order_notification_email"
        ) as recipients:
            with django_capture_on_commit_callbacks(execute=True) as callbacks:
                with pytest.raises(serializers.ValidationError):
                    self._service(user, cart).create()

        assert callbacks == []
        customer.delay.assert_not_called()
        recipients.delay.assert_not_called()
        assert not Order.objects.filter(user=user).exists()

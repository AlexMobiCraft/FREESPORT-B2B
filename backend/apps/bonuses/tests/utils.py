"""Хелперы для тестов бонусной программы."""

from __future__ import annotations

import time
import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model

from apps.bonuses.models import BonusProgramSettings
from apps.orders.models import Order, OrderItem
from apps.products.factories import ProductFactory

User = get_user_model()

_counter = 0


def unique_suffix() -> str:
    """Уникальный суффикс для изоляции тестовых данных."""
    global _counter
    _counter += 1
    return f"{int(time.time() * 1000)}-{_counter}-{uuid.uuid4().hex[:6]}"


def create_user(role: str = "trainer", is_verified: bool = True) -> User:
    """Создаёт пользователя с указанной ролью."""
    return User.objects.create_user(
        email=f"user-{unique_suffix()}@freesport.test",
        password="test_password123",
        role=role,
        is_verified=is_verified,
    )


def ensure_program_started() -> BonusProgramSettings:
    """Создаёт настройки до заказов, чтобы отсечка `program_start_at` была в прошлом.

    В проде программа запускается раньше заказов; в тестах порядок пришлось бы
    соблюдать вручную, иначе отсечка отсекла бы сами тестовые заказы.
    """
    return BonusProgramSettings.load()


def create_order(
    user: User,
    *,
    is_master: bool = True,
    parent: Order | None = None,
    status: str = "pending",
    delivery_cost: Decimal | str = "0",
) -> Order:
    """Создаёт заказ с минимально необходимыми полями."""
    ensure_program_started()
    return Order.objects.create(
        user=user,
        status=status,
        is_master=is_master,
        parent_order=parent,
        total_amount=Decimal("0"),
        delivery_cost=Decimal(str(delivery_cost)),
        delivery_address="г. Москва, ул. Тестовая, д. 1",
        delivery_method="courier",
        payment_method="card",
    )


def add_item(order: Order, unit_price: Decimal | str, quantity: int = 1) -> OrderItem:
    """Добавляет позицию в заказ (total_price считается в save())."""
    return OrderItem.objects.create(
        order=order,
        product=ProductFactory(),
        quantity=quantity,
        unit_price=Decimal(str(unit_price)),
        total_price=Decimal("0"),
    )


def create_master_with_subs(
    user: User,
    sub_totals: list[str],
    *,
    delivery_cost: Decimal | str = "0",
    sub_statuses: list[str] | None = None,
) -> Order:
    """Мастер-заказ с субзаказами: позиции живут только в субзаказах.

    `sub_statuses` позволяет собрать смешанный заказ (часть отменена).
    """
    master = create_order(user, is_master=True, delivery_cost=delivery_cost)
    for index, total in enumerate(sub_totals):
        status = sub_statuses[index] if sub_statuses else "pending"
        sub = create_order(user, is_master=False, parent=master, status=status)
        add_item(sub, total)
    return master


def close_master(master: Order, status: str = "delivered") -> Order:
    """Переводит мастер-заказ в целевой статус — триггер начисления."""
    master.status = status
    master.save(update_fields=["status", "updated_at"])
    return master

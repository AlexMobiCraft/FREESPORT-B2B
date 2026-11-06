"""
Unit-тесты раздела заказов менеджера `/manager/` (стори 42.5).

`scope_orders`, склонение дней, очередь главной на пустых данных и при урезанных
правах, нейтрализация формул в CSV, страж белого списка полей карточки и
регистрация на двух сайтах.
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.test import RequestFactory

from apps.orders.admin import OrderAdmin
from apps.orders.manager_admin import ManagerOrderAdmin, csv_cell, days_ru, manager_queue, scope_orders
from apps.orders.models import Order
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP
from freesport.admin_site import manager_site
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

HIDDEN_FIELDS = (
    "payment_id",
    "parent_order",
    "vat_group",
    "status_1c",
    "sent_to_1c_at",
    "export_skipped",
    "customer_code_snapshot",
    "order_year",
    "customer_year_sequence",
    "suborder_sequence",
    "is_master",
    "user",
)


def make_user(**extra) -> User:
    return User.objects.create_user(
        email=f"u_{get_unique_suffix()}@example.com", password="StrongPassword123!", **extra
    )


def make_manager(*codenames: str) -> User:
    """Член «Менеджеров»; права группы — перечисленные `app_label.codename`."""
    manager = make_user(is_staff=True)
    group, _ = Group.objects.get_or_create(name=MANAGERS_GROUP)
    group.permissions.set(
        [
            Permission.objects.get(content_type__app_label=app_label, codename=codename)
            for app_label, codename in (name.split(".") for name in codenames)
        ]
    )
    manager.groups.add(group)
    return manager


def make_client(manager: User | None, **extra) -> User:
    client = make_user(role="wholesale_level1", **extra)
    User.objects.filter(pk=client.pk).update(responsible_manager=manager)
    return client


def make_order(user: User | None, **extra) -> Order:
    defaults = {
        "user": user,
        "total_amount": Decimal("100.00"),
        "delivery_address": "Адрес",
        "delivery_method": "courier",
        "payment_method": "card",
    }
    defaults.update(extra)
    return Order.objects.create(**defaults)


def request_for(user: User):
    request = RequestFactory().get("/manager/")
    request.user = user
    return request


@pytest.fixture(autouse=True)
def no_order_emails():
    """Письма о новом заказе (`orders/signals.py`) — без брокера Celery."""
    with (
        patch("apps.orders.tasks.send_order_confirmation_to_customer"),
        patch("apps.orders.tasks.send_order_notification_email"),
    ):
        yield


class TestScopeOrders:
    def test_only_own_master_orders(self):
        manager = make_manager()
        other = make_manager()
        own_client = make_client(manager)
        own = make_order(own_client)
        own_sub = make_order(own_client, is_master=False, parent_order=own, suborder_sequence=1)
        foreign = make_order(make_client(other))
        guest = make_order(None)
        staff = make_client(manager)
        User.objects.filter(pk=staff.pk).update(is_staff=True)
        staff_order = make_order(staff)

        visible = set(scope_orders(request_for(manager), Order.objects.all()))

        assert visible == {own}
        assert not visible & {own_sub, foreign, guest, staff_order}


@pytest.mark.parametrize(
    ("n", "expected"),
    [
        (1, "1 день"),
        (2, "2 дня"),
        (4, "4 дня"),
        (5, "5 дней"),
        (11, "11 дней"),
        (12, "12 дней"),
        (14, "14 дней"),
        (21, "21 день"),
        (22, "22 дня"),
        (25, "25 дней"),
        (101, "101 день"),
        (111, "111 дней"),
        (112, "112 дней"),
        (203, "203 дня"),
    ],
)
def test_days_ru(n, expected):
    assert days_ru(n) == expected


class TestManagerQueue:
    def test_empty_queue(self):
        queue = manager_queue(request_for(make_manager("users.view_user", "orders.view_order")), manager_site)

        assert [item["text"] for item in queue] == ["Заявки на верификацию: 0", "Новые заказы: 0"]
        assert [item["count"] for item in queue] == [0, 0]
        assert [item["url"] for item in queue] == [
            "/manager/users/user/?verification_status__exact=pending",
            "/manager/orders/order/?status__exact=pending",
        ]

    @pytest.mark.parametrize(
        ("codenames", "texts"),
        [
            pytest.param(("users.change_user",), ["Заявки на верификацию: 0"], id="only-users"),
            pytest.param(("orders.change_order",), ["Новые заказы: 0"], id="only-orders"),
            pytest.param((), [], id="nothing"),
        ],
    )
    def test_counter_needs_model_permission(self, codenames, texts):
        queue = manager_queue(request_for(make_manager(*codenames)), manager_site)

        assert [item["text"] for item in queue] == texts


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("=1+1", "'=1+1"),
        ("+79001234567", "'+79001234567"),
        ("-5", "'-5"),
        ("@SUM(A1)", "'@SUM(A1)"),
        (" =1+1", "' =1+1"),
        ("\t=1+1", "'\t=1+1"),
        ("\r\n=1+1", "'\r\n=1+1"),
        ("\x00=1+1", "'\x00=1+1"),
        ("​=1+1", "'​=1+1"),
        ("＝1+1", "'＝1+1"),
        ("\t", "'\t"),
        ("Иван Петров", "Иван Петров"),
        ("ivan@example.com", "ivan@example.com"),
        ("0000026001", "0000026001"),
        ("1000.00", "1000.00"),
        ("2026-10-15 01:30", "2026-10-15 01:30"),
        ("", ""),
    ],
)
def test_csv_cell(value, expected):
    assert csv_cell(value) == expected


class TestWhitelist:
    def test_hidden_fields_are_not_in_card(self):
        model_admin = ManagerOrderAdmin(Order, manager_site)
        request = request_for(make_manager())

        fieldset_fields = {name for _, options in model_admin.get_fieldsets(request) for name in options["fields"]}
        readonly = set(model_admin.get_readonly_fields(request))

        assert not fieldset_fields & set(HIDDEN_FIELDS)
        assert not readonly & set(HIDDEN_FIELDS)
        assert fieldset_fields - readonly == {"tracking_number", "delivery_date"}
        assert "notes" in readonly


class TestRegistration:
    def test_sites_have_own_admin_classes(self):
        assert type(manager_site._registry[Order]) is ManagerOrderAdmin
        assert type(admin.site._registry[Order]) is OrderAdmin

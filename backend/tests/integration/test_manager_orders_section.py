"""
Integration-тесты раздела менеджера `/manager/` — заказы своих клиентов и главная (стори 42.5).

Покрывает:
- AC1 — вход в заказы раздела и блок «Заказы» на главной;
- AC2 — список и поиск только по мастер-заказам своих клиентов;
- AC3 — 404 на чужой заказ и на субзаказ, 403 на добавление и удаление;
- AC4 — белый список полей карточки, блок субзаказов только для чтения;
- AC5 — подделанный POST: пишутся только правимые поля, бонус не начисляется лишний раз;
- AC6 — экспорт CSV только своих заказов, русские заголовки и BOM;
- AC7 — запись AuditLog `update_order`;
- AC8 — счётчики главной и списки по их ссылкам;
- AC9 — права внутри раздела при одном `view_order`;
- AC10 — ссылки и редиректы не уводят в /admin/;
- AC11 — число запросов списка и главной не зависит от числа строк.

Хелперы и autouse-фикстуры — из тестов раздела клиентов (стори 42.4). Тесты
транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`).
"""

from __future__ import annotations

import csv
import io
import itertools
import re
import threading
import time as clock
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from html.parser import HTMLParser
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import label_for_field
from django.contrib.auth.models import Group, Permission
from django.db import connection, connections
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.common.models import AuditLog
from apps.orders.manager_admin import ManagerOrderAdmin, manager_queue
from apps.orders.models import Order, OrderItem
from apps.products.models import Product
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import manager_site
from tests.factories import ProductFactory
from tests.integration.test_manager_clients_section import (  # noqa: F401 — фикстуры подключаются импортом
    INDEX_URL,
    PASSWORD,
    form_payload,
    get_unique_suffix,
    make_client,
    make_staff_member,
    manager,
    manager_client,
    message_texts,
    no_routing_rules,
    other_manager,
    role_groups,
    section_client,
    section_member,
    unique_digits,
    verified_email_task,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

ORDERS_URL = "/manager/orders/order/"
_sequence = itertools.count(1)

# Решение 8 стори: заголовки экспорта раздела — литералом, независимо от реализации.
EXPECTED_CSV_HEADER = [
    "Номер заказа",
    "Номер (UI)",
    "Клиент",
    "Статус",
    "Оплата",
    "Сумма",
    "Способ доставки",
    "Дата создания",
]
STALE_CARD_TEXT = "Обновите страницу"

# AC4: поля карточки только для чтения — литералом, независимо от реализации.
CARD_READONLY_FIELDS = {
    "order_number_ui",
    "order_number",
    "client_link",
    "status",
    "customer_name",
    "customer_email",
    "customer_phone",
    "notes",
    "items_table",
    "total_amount",
    "discount_amount",
    "delivery_cost",
    "delivery_address",
    "delivery_method",
    "payment_method",
    "payment_status",
    "paid_at",
    "shipped_at",
    "sent_to_1c_ru",
    "created_at",
    "updated_at",
}

# Поля блока «Не показывать» section-contents: в HTML нет ни поля, ни подписи.
HIDDEN_FIELDS = {
    "payment_id": "ID платежа (ЮKassa)",
    "parent_order": "Мастер-заказ",
    "vat_group": "Группа НДС (%)",
    "status_1c": "Статус из 1С",
    "sent_to_1c_at": "Дата и время отправки в 1С",
    "export_skipped": "Пропущен при экспорте",
}


@pytest.fixture(autouse=True)
def order_emails():
    """Письма о новом заказе (`orders/signals.py`) — без брокера Celery."""
    with (
        patch("apps.orders.tasks.send_order_confirmation_to_customer") as customer,
        patch("apps.orders.tasks.send_order_notification_email") as admins,
    ):
        yield customer, admins


def canonical_number() -> str:
    """Канонический номер мастера `CCCCCYYNNN`: без него Order.save ставит UUID."""
    return f"{unique_digits(5)}26{next(_sequence) % 999 + 1:03d}"


def make_item(order: Order, product: Product | None = None, **overrides: Any) -> OrderItem:
    product = product or ProductFactory()
    defaults = {
        "order": order,
        "product": product,
        "variant": product.variants.first(),
        "quantity": 2,
        "unit_price": Decimal("250.00"),
        "product_name": product.name,
        "product_sku": f"ART-{unique_digits(8)}",
    }
    defaults.update(overrides)
    return OrderItem.objects.create(**defaults)


def make_master(
    client: User | None, *, status: str = "pending", subs: int = 2, product: Product | None = None, **overrides: Any
) -> Order:
    """Мастер-заказ с субзаказами по одной позиции; `subs=0` — legacy-мастер со своей позицией."""
    product = product or ProductFactory()
    defaults: dict[str, Any] = {
        "user": client,
        "is_master": True,
        "order_number": canonical_number(),
        "status": status,
        "total_amount": Decimal("1000.00"),
        "delivery_address": "г. Москва, ул. Тестовая, д. 1",
        "delivery_method": "courier",
        "payment_method": "card",
        "customer_name": "Покупатель Заказов",
        "customer_email": f"order_{get_unique_suffix()}@example.com",
        "customer_phone": f"+7901{unique_digits(7)}",
    }
    defaults.update(overrides)
    master = Order.objects.create(**defaults)
    for index in range(1, subs + 1):
        sub = Order.objects.create(
            user=client,
            is_master=False,
            parent_order=master,
            order_number=f"{master.order_number}{index}",
            suborder_sequence=index,
            vat_group=Decimal("22.00") if index == 1 else Decimal("5.00"),
            status=status,
            total_amount=Decimal("500.00"),
            delivery_address=master.delivery_address,
            delivery_method=master.delivery_method,
            payment_method=master.payment_method,
        )
        make_item(sub, product)
    if subs == 0:
        make_item(master, product)
    return master


def order_change_url(order: Order) -> str:
    return reverse("manager:orders_order_change", args=[order.pk])


def order_history_url(order: Order) -> str:
    return reverse("manager:orders_order_history", args=[order.pk])


def post_order_action(client, action: str, *orders: Order, follow: bool = False, **extra: Any):
    payload = {"action": action, "_selected_action": [str(order.pk) for order in orders]}
    payload.update(extra)
    return client.post(ORDERS_URL, payload, follow=follow)


def order_audit(order: Order):
    return AuditLog.objects.filter(resource_type="Order", resource_id=str(order.pk))


def order_snapshot(order: Order) -> dict[str, Any]:
    return Order.objects.filter(pk=order.pk).values().get()


def csv_rows(response) -> list[list[str]]:
    # Через поток, а не splitlines(): перевод строки внутри кавыченной ячейки сохраняется.
    return list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"), newline="")))


def listed_ids(response) -> set[int]:
    return {order.pk for order in response.context["cl"].result_list}


# Предел SQL работника в другом соединении и запас на его завершение.
OTHER_CONNECTION_SQL_TIMEOUT_MS = 10_000
OTHER_CONNECTION_JOIN_TIMEOUT = 30


class ConnectionWorkers:
    """
    Потоки со своими соединениями PostgreSQL для проверок конкурентного доступа.

    SQL каждого работника ограничен `statement_timeout`, поэтому `join` с запасом
    успевает. Если поток всё же жив после `join`, его запрос снимается
    `pg_cancel_backend`, и поток ждут ещё раз. Исключения работников собираются
    в `errors` и поднимаются в вызывающем потоке (R42.5-17, R42.5-19).
    """

    def __init__(self) -> None:
        self.errors: dict[str, BaseException] = {}
        self._workers: list[tuple[threading.Thread, list[int]]] = []

    def start(self, name: str, action: Any) -> None:
        pids: list[int] = []

        def work() -> None:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(f"SET statement_timeout = {OTHER_CONNECTION_SQL_TIMEOUT_MS}")
                    cursor.execute("SELECT pg_backend_pid()")
                    pids.append(cursor.fetchone()[0])
                action()
            except BaseException as error:  # передаётся в вызывающий поток
                self.errors[name] = error
            finally:
                connections.close_all()

        worker = threading.Thread(target=work, name=name)
        self._workers.append((worker, pids))
        worker.start()

    def join(self, *, raise_errors: bool = True) -> None:
        for worker, pids in self._workers:
            worker.join(timeout=OTHER_CONNECTION_JOIN_TIMEOUT)
            if worker.is_alive() and pids:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT pg_cancel_backend(%s)", [pids[0]])
                worker.join(timeout=OTHER_CONNECTION_JOIN_TIMEOUT)
        alive = [worker.name for worker, _ in self._workers if worker.is_alive()]
        if alive:
            raise AssertionError(f"работники не завершились: {alive}")
        if raise_errors and self.errors:
            raise next(iter(self.errors.values()))


@pytest.fixture
def connection_workers():
    """
    Работники в других соединениях; при любом выходе из теста фикстура дожидается их.

    Teardown идёт раньше очистки БД: `clear_db_before_test` — autouse и завершается
    последним. Исключения работников здесь не поднимаются повторно — их уже поднял
    `join()` теста, а на ошибочном пути тест упал по своей причине.
    """
    workers = ConnectionWorkers()
    yield workers
    workers.join(raise_errors=False)


@pytest.fixture
def other_connection(connection_workers):
    """Выполняет действие в отдельном соединении PostgreSQL и дожидается его фиксации."""
    names = itertools.count(1)

    def run(action) -> None:
        connection_workers.start(f"other-connection-{next(names)}", action)
        connection_workers.join()

    return run


class _FormInputs(HTMLParser):
    """Значения `<input>` страницы — то, что отправит браузер (без кнопок отправки)."""

    def __init__(self) -> None:
        super().__init__()
        self.values: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        name = attributes.get("name")
        if tag == "input" and name and attributes.get("type") not in ("submit", "button"):
            self.values[name] = attributes.get("value") or ""


def html_inputs(content: str) -> dict[str, str]:
    parser = _FormInputs()
    parser.feed(content)
    return parser.values


def card_payload(client, order: Order, **changes: Any) -> dict[str, Any]:
    """POST карточки, как его отправит браузер: со скрытыми значениями на момент открытия."""
    response = client.get(order_change_url(order))
    data = form_payload(response)
    form = response.context["adminform"].form
    for name in form.fields:
        bound = form[name]
        if bound.field.show_hidden_initial:
            data[bound.html_initial_name] = "" if bound.initial is None else bound.initial
    data.update(changes)
    data.setdefault("_save", "Сохранить")
    return data


class TestEntry:
    """AC1 — кто входит в заказы раздела."""

    @pytest.mark.parametrize("group_name", [MANAGERS_GROUP, SUPERVISORS_GROUP])
    def test_manager_and_supervisor_enter(self, client, group_name):
        client.force_login(make_staff_member(group_name))

        response = client.get(ORDERS_URL)

        assert response.status_code == 200
        assert "<h1>Заказы</h1>" in response.content.decode()

    @pytest.mark.parametrize(
        "make_user",
        [
            pytest.param(lambda: make_staff_member(MARKETING_GROUP), id="marketing"),
            pytest.param(lambda: make_staff_member(None), id="staff-without-group"),
            pytest.param(
                lambda: User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD),
                id="superuser",
            ),
            pytest.param(None, id="anonymous"),
        ],
    )
    def test_others_are_redirected_to_login(self, client, make_user):
        if make_user is not None:
            client.force_login(make_user())

        response = client.get(ORDERS_URL)

        assert response.status_code == 302
        assert "/manager/login/" in response.url

    def test_index_has_orders_block(self, manager_client):
        response = manager_client.get(INDEX_URL)

        orders_app = next(app for app in response.context["app_list"] if app["app_label"] == "orders")
        assert orders_app["name"] == "Заказы"
        assert [(model["name"], model["admin_url"]) for model in orders_app["models"]] == [("Заказы", ORDERS_URL)]


class TestChangelist:
    """AC2 — список только мастер-заказов своих клиентов."""

    def test_only_own_master_orders(self, section_client, section_member, other_manager):
        own = make_master(make_client(section_member))
        foreign = make_master(make_client(other_manager))
        guest = make_master(None)

        # Учётные записи сотрудников с ответственным A — по одной на каждое условие staff_accounts_q().
        staff_orders = []
        for flags in ({"is_staff": True}, {"is_superuser": True}, {"role": "admin"}):
            account = make_client(section_member)
            User.objects.filter(pk=account.pk).update(**flags)
            staff_orders.append(make_master(account))
        marketer = make_client(section_member)
        marketer.groups.add(Group.objects.get(name=MARKETING_GROUP))
        staff_orders.append(make_master(marketer))

        response = section_client.get(ORDERS_URL)

        assert listed_ids(response) == {own.pk}
        hidden = {foreign.pk, guest.pk, *(order.pk for order in staff_orders)}
        assert not hidden & listed_ids(response)
        assert Order.objects.filter(parent_order=own).count() == 2

    def test_search_finds_only_own_orders(self, section_client, section_member, other_manager):
        # Свои заказы у разных клиентов: у каждого все шесть значений поиска свои.
        own = [
            make_master(
                make_client(section_member, company_name=f"ООО Своя Компания {name}"),
                tracking_number=f"TRK{unique_digits(8)}",
            )
            for name in ("Альфа", "Бета", "Гамма")
        ]
        foreign_client = make_client(other_manager, company_name="ООО Чужая Компания")
        foreign = make_master(foreign_client, tracking_number=f"TRK{unique_digits(8)}")

        def values(order: Order) -> list[str]:
            assert order.user is not None
            return [
                order.order_number,
                order.order_number_display,
                order.user.email,
                order.customer_email,
                order.tracking_number,
                order.user.company_name,
            ]

        def found(query: str) -> set[int]:
            return listed_ids(section_client.get(ORDERS_URL, {"q": query}))

        assert foreign.order_number_display != foreign.order_number
        # Без поиска видны все свои: точные множества ниже — заслуга поиска, а не выборки.
        assert listed_ids(section_client.get(ORDERS_URL)) == {order.pk for order in own}
        for query in values(foreign):
            assert found(query) == set(), query
        for order in own:
            for query in values(order):
                assert found(query) == {order.pk}, query
        assert found("НЕТ-ТАКОГО-ЗНАЧЕНИЯ-42-5") == set()

    def test_columns_filters_and_title(self, manager_client, manager):
        make_master(make_client(manager))

        response = manager_client.get(ORDERS_URL)

        cl = response.context["cl"]
        assert list(cl.list_display) == [
            "action_checkbox",
            "order_number_ui",
            "customer",
            "status",
            "payment_status_ru",
            "total_amount",
            "positions",
            "created_at",
        ]
        labels = [label_for_field(name, Order, cl.model_admin) for name in cl.list_display[1:]]
        assert labels == ["Номер", "Клиент", "Статус заказа", "Оплата", "Общая сумма", "Позиций", "Дата создания"]
        filters = [spec.field_path for spec in cl.filter_specs]
        assert filters == ["status", "payment_status", "delivery_method"]
        content = response.content.decode()
        assert 'class="addlink"' not in content
        assert "/manager/orders/order/add/" not in content

    def test_positions_column_shows_number_of_items(self, manager_client, manager):
        client_user = make_client(manager)
        # Число позиций и сумма количеств различаются у каждого заказа.
        split = make_master(client_user)
        for sub in split.sub_orders.all():
            sub.items.update(quantity=3)
        sub = split.sub_orders.first()
        assert sub is not None
        make_item(sub, quantity=5)
        legacy = make_master(client_user, subs=0)

        response = manager_client.get(ORDERS_URL)

        rows = re.findall(
            r'name="_selected_action" value="(\d+)".*?<td class="field-positions">(\d+)</td>',
            response.content.decode(),
            flags=re.S,
        )
        # Позиций: 3 и 1; сумма количеств была бы 3 + 3 + 5 = 11 и 2.
        assert dict(rows) == {str(split.pk): "3", str(legacy.pk): "1"}


class TestForeignOrder:
    """AC3 — 404 на чужой заказ и на субзаказ."""

    def test_direct_urls_answer_404(self, section_client, section_member, other_manager):
        own = make_master(make_client(section_member))
        own_sub = Order.objects.filter(parent_order=own).first()
        foreign = make_master(make_client(other_manager))
        assert own_sub is not None

        # Контроль: те же адреса своего заказа открываются — 404 ниже не от отказа во входе.
        assert section_client.get(order_change_url(own)).status_code == 200
        assert section_client.get(order_history_url(own)).status_code == 200

        payload = card_payload(section_client, own, tracking_number="ПОДМЕНА")
        before_foreign = order_snapshot(foreign)
        before_sub = order_snapshot(own_sub)

        for order in (foreign, own_sub):
            assert section_client.get(order_change_url(order)).status_code == 404
            assert section_client.get(order_history_url(order)).status_code == 404
            assert section_client.post(order_change_url(order), payload).status_code == 404

        assert order_snapshot(foreign) == before_foreign
        assert order_snapshot(own_sub) == before_sub
        assert not AuditLog.objects.filter(resource_type="Order").exists()

    def test_add_and_delete_are_forbidden(self, manager_client, manager):
        own = make_master(make_client(manager))
        delete_url = reverse("manager:orders_order_delete", args=[own.pk])

        assert manager_client.get(reverse("manager:orders_order_add")).status_code == 403
        assert manager_client.get(delete_url).status_code == 403
        assert manager_client.post(delete_url, {"post": "yes"}).status_code == 403
        assert Order.objects.filter(pk=own.pk).exists()


class TestOrderCard:
    """AC4 — состав карточки."""

    def test_only_tracking_and_delivery_date_are_editable(self, manager_client, manager):
        own = make_master(make_client(manager))

        response = manager_client.get(order_change_url(own))

        assert set(response.context["adminform"].form.fields) == {"tracking_number", "delivery_date"}
        content = response.content.decode()
        assert 'name="tracking_number"' in content
        assert 'name="delivery_date"' in content

    def test_read_only_content(self, manager_client, manager):
        client_user = make_client(manager, company_name="ООО Видимый Клиент")
        own = make_master(
            client_user,
            notes="Звонить после 18:00",
            customer_name="Пётр Покупателев",
            customer_phone="+79005554433",
            sent_to_1c=True,
            total_amount=Decimal("987.65"),
            discount_amount=Decimal("43.21"),
            delivery_cost=Decimal("210.98"),
        )
        skus = list(OrderItem.objects.filter(order__parent_order=own).values_list("product_sku", flat=True))
        assert len(skus) == 2

        response = manager_client.get(order_change_url(own))

        content = response.content.decode()
        assert "Звонить после 18:00" in content
        assert "Комментарий клиента" in content
        assert 'name="notes"' not in content
        assert f'href="/manager/users/user/{client_user.pk}/change/"' in content
        for text in (
            own.order_number,
            own.order_number_display,
            "Пётр Покупателев",
            own.customer_email,
            "+79005554433",
        ):
            assert text in content, text
        for sku in skus:
            assert sku in content, sku
        for label in ("Передан в 1С", "Дата оплаты", "Дата отгрузки", "Способ оплаты", "Статус оплаты"):
            assert label in content, label
        # Состав — по AC4, независимо от readonly_fields реализации (R42.5-22).
        cells = {
            field.field["name"]: str(field.contents())
            for fieldset in response.context["adminform"]
            for line in fieldset
            for field in line
            if field.is_readonly
        }
        assert set(cells) == CARD_READONLY_FIELDS
        assert (cells["total_amount"], cells["discount_amount"], cells["delivery_cost"]) == (
            "987,65",
            "43,21",
            "210,98",
        )

    def test_items_table_rows_have_quantity_price_and_sum(self, manager_client, manager):
        own = make_master(make_client(manager))
        first, second = Order.objects.filter(parent_order=own).order_by("suborder_sequence")
        # Количество, цена и сумма различаются в каждой строке: подмена одной
        # колонки другой видна в проверке.
        OrderItem.objects.filter(order=first).update(
            product_name="Мяч первый", quantity=3, unit_price=Decimal("120.50"), total_price=Decimal("361.50")
        )
        OrderItem.objects.filter(order=second).update(
            product_name="Мяч второй", quantity=4, unit_price=Decimal("75.25"), total_price=Decimal("301.00")
        )
        first_sku = OrderItem.objects.get(order=first).product_sku
        second_sku = OrderItem.objects.get(order=second).product_sku

        content = manager_client.get(order_change_url(own)).content.decode()

        assert (
            f"<tr><td>{first.order_number_display}</td><td>Мяч первый</td><td>{first_sku}</td>"
            "<td>3</td><td>120.50</td><td>361.50</td></tr>"
        ) in content
        assert (
            f"<tr><td>{second.order_number_display}</td><td>Мяч второй</td><td>{second_sku}</td>"
            "<td>4</td><td>75.25</td><td>301.00</td></tr>"
        ) in content

    def test_legacy_master_without_sub_orders_shows_own_items(self, manager_client, manager):
        own = make_master(make_client(manager), subs=0)
        sku = OrderItem.objects.get(order=own).product_sku

        content = manager_client.get(order_change_url(own)).content.decode()

        assert sku in content

    def test_hidden_fields_are_absent(self, manager_client, manager):
        own = make_master(
            make_client(manager),
            payment_id="PAY-SECRET-777",
            status_1c="Секретный статус 1С",
            sent_to_1c_at=timezone.now(),
        )

        content = manager_client.get(order_change_url(own)).content.decode()

        for name, label in HIDDEN_FIELDS.items():
            assert f'name="{name}"' not in content, name
            assert label not in content, label
        assert "PAY-SECRET-777" not in content
        assert "Секретный статус 1С" not in content

    def test_sub_orders_block_is_read_only(self, manager_client, manager):
        own = make_master(make_client(manager))
        first, second = Order.objects.filter(parent_order=own).order_by("suborder_sequence")
        # Статус и сумма у субзаказов разные: подмена или пропуск колонки виден (R42.5-18).
        Order.objects.filter(pk=first.pk).update(status="processing", total_amount=Decimal("300.00"))
        Order.objects.filter(pk=second.pk).update(status="shipped", total_amount=Decimal("700.00"))

        response = manager_client.get(order_change_url(own))

        content = response.content.decode()
        assert "Субзаказы" in content
        (inline,) = response.context["inline_admin_formsets"]
        rows = {}
        for inline_form in inline:
            cells = {
                field.field["name"]: str(field.contents())
                for fieldset in inline_form
                for line in fieldset
                for field in line
            }
            rows[cells["sub_number"]] = (cells["status"], cells["total_amount"])
        assert rows == {
            first.order_number_display: ("В обработке", "300,00"),
            second.order_number_display: ("Отправлен", "700,00"),
        }
        for sub in (first, second):
            assert sub.order_number_display in content
            assert f'href="{order_change_url(sub)}"' not in content
        assert not inline.has_add_permission
        assert not inline.has_change_permission
        assert not inline.has_delete_permission
        assert 'class="addlink"' not in content
        assert 'class="deletelink"' not in content


class TestStaleCard:
    """R42.5-1 — карточка, открытая до чужой правки трек-номера или даты, отклоняется."""

    @pytest.mark.parametrize(
        ("first_change", "second_change", "expected"),
        [
            pytest.param(
                {"tracking_number": "NEW-TRK"},
                {"delivery_date": "2026-11-05"},
                ("NEW-TRK", date(2026, 10, 20)),
                id="track-then-date",
            ),
            pytest.param(
                {"delivery_date": "2026-11-01"},
                {"tracking_number": "SECOND-TRK"},
                ("OLD-TRK", date(2026, 11, 1)),
                id="date-then-track",
            ),
            pytest.param(
                {"delivery_date": ""},
                {"tracking_number": "SECOND-TRK"},
                ("OLD-TRK", None),
                id="cleared-date-then-track",
            ),
            pytest.param(
                {"delivery_date": "2026-11-01"},
                {"delivery_date": "2026-12-01"},
                ("OLD-TRK", date(2026, 11, 1)),
                id="date-then-date",
            ),
        ],
    )
    def test_second_open_card_is_rejected(self, manager_client, manager, first_change, second_change, expected):
        own = make_master(make_client(manager), tracking_number="OLD-TRK", delivery_date=date(2026, 10, 20))
        first_tab = card_payload(manager_client, own, **first_change)
        second_tab = card_payload(manager_client, own, **second_change)
        assert manager_client.post(order_change_url(own), first_tab).status_code == 302
        saved = order_snapshot(own)
        assert (saved["tracking_number"], saved["delivery_date"]) == expected

        response = manager_client.post(order_change_url(own), second_tab)

        assert response.status_code == 200
        assert STALE_CARD_TEXT in response.content.decode()
        assert order_snapshot(own) == saved
        assert order_audit(own).count() == 1
        assert LogEntry.objects.filter(object_id=str(own.pk)).count() == 1

        # Повторная отправка той же устаревшей формы — снова отказ, пока страницу не обновят.
        again = manager_client.post(order_change_url(own), second_tab)
        assert again.status_code == 200
        assert STALE_CARD_TEXT in again.content.decode()
        assert order_snapshot(own) == saved
        assert order_audit(own).count() == 1
        assert LogEntry.objects.filter(object_id=str(own.pk)).count() == 1

    @pytest.mark.parametrize("stored", ["TRK ", " TRK", " TRK "])
    def test_spaces_in_stored_tracking_do_not_make_fresh_card_stale(self, manager_client, manager, stored):
        # Order.save() пробелы не срезает: трек с пробелами мог прийти не из формы.
        own = make_master(make_client(manager), tracking_number=stored)

        response = manager_client.post(
            order_change_url(own), card_payload(manager_client, own, delivery_date="2026-11-05")
        )

        assert response.status_code == 302
        own.refresh_from_db()
        assert own.delivery_date == date(2026, 11, 5)
        assert own.tracking_number == stored
        (record,) = order_audit(own)
        assert record.details["changes"]["fields"] == {"delivery_date": {"old": None, "new": "2026-11-05"}}

    def test_spaces_in_stored_tracking_keep_conflict_check(self, manager_client, manager):
        own = make_master(make_client(manager), tracking_number="TRK ")
        first_tab = card_payload(manager_client, own, tracking_number="NEW-TRK")
        second_tab = card_payload(manager_client, own, delivery_date="2026-11-05")
        assert manager_client.post(order_change_url(own), first_tab).status_code == 302
        saved = order_snapshot(own)

        response = manager_client.post(order_change_url(own), second_tab)

        assert response.status_code == 200
        assert STALE_CARD_TEXT in response.content.decode()
        assert order_snapshot(own) == saved
        assert order_audit(own).count() == 1

    def test_refreshed_card_saves(self, manager_client, manager):
        own = make_master(make_client(manager), tracking_number="OLD-TRK")
        stale = card_payload(manager_client, own, delivery_date="2026-11-05")
        manager_client.post(order_change_url(own), card_payload(manager_client, own, tracking_number="NEW-TRK"))
        assert manager_client.post(order_change_url(own), stale).status_code == 200

        response = manager_client.post(
            order_change_url(own), card_payload(manager_client, own, delivery_date="2026-11-05")
        )

        assert response.status_code == 302
        own.refresh_from_db()
        assert own.tracking_number == "NEW-TRK"
        assert own.delivery_date == date(2026, 11, 5)

    def test_check_locks_order_row(self, manager_client, manager):
        own = make_master(make_client(manager))
        data = card_payload(manager_client, own, tracking_number="TRK-LOCK")

        with CaptureQueriesContext(connection) as captured:
            assert manager_client.post(order_change_url(own), data).status_code == 302

        locks = [query["sql"] for query in captured if "FOR UPDATE" in query["sql"]]
        assert any('FROM "orders"' in sql for sql in locks), locks

    def test_concurrent_card_waits_for_lock_and_is_rejected(self, manager_client, manager, connection_workers):
        """Два POST в разных соединениях PostgreSQL: второй ждёт блокировку первого и видит его правку."""
        own = make_master(make_client(manager), tracking_number="OLD-TRK")
        first_tab = card_payload(manager_client, own, tracking_number="NEW-TRK")
        second_tab = card_payload(manager_client, own, delivery_date="2026-11-05")
        first_saved, release = threading.Event(), threading.Event()
        responses: dict[str, Any] = {}
        original_save_model = ManagerOrderAdmin.save_model

        def save_model_and_hold(admin_obj, request, obj, form, change):
            original_save_model(admin_obj, request, obj, form, change)
            if threading.current_thread().name == "first":
                # Транзакция первого запроса открыта, строка заказа заблокирована.
                first_saved.set()
                release.wait(timeout=15)

        def post(name: str, data: dict[str, Any]) -> None:
            tab = Client()
            tab.force_login(manager)
            responses[name] = tab.post(order_change_url(own), data)

        def blocked_on_lock() -> bool:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE datname = current_database() AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
                )
                return cursor.fetchone()[0] > 0

        with patch.object(ManagerOrderAdmin, "save_model", save_model_and_hold):
            try:
                connection_workers.start("first", lambda: post("first", first_tab))
                assert first_saved.wait(timeout=15), "первый POST не дошёл до сохранения"
                connection_workers.start("second", lambda: post("second", second_tab))
                deadline = clock.monotonic() + 5
                waited = blocked_on_lock()
                while not waited and clock.monotonic() < deadline:
                    clock.sleep(0.05)
                    waited = blocked_on_lock()
            finally:
                # При любом выходе отпустить первый запрос (R42.5-13). SQL обоих
                # ограничен statement_timeout, дождётся их connection_workers: здесь
                # на успешном пути или в своём teardown — до очистки БД (R42.5-19).
                release.set()
            connection_workers.join()

        assert waited, "второй POST не ждал блокировку строки заказа"
        assert responses["first"].status_code == 302
        assert responses["second"].status_code == 200
        assert STALE_CARD_TEXT in responses["second"].content.decode()
        after = order_snapshot(own)
        assert after["tracking_number"] == "NEW-TRK"
        assert after["delivery_date"] is None
        assert order_audit(own).count() == 1
        assert LogEntry.objects.filter(object_id=str(own.pk)).count() == 1

    def test_order_deleted_after_open_answers_404(self, manager_client, manager, other_connection):
        """R42.5-12: заказ удалён из /admin/ между чтением карточки и проверкой под блокировкой — 404, не 500."""
        own = make_master(make_client(manager))
        data = card_payload(manager_client, own, tracking_number="TRK-GONE")
        original_get_object = ManagerOrderAdmin.get_object

        def get_object_then_delete(admin_obj, request, object_id, from_field=None):
            obj = original_get_object(admin_obj, request, object_id, from_field)
            if request.method == "POST":
                # Удаление в другом соединении фиксируется до ManagerOrderForm.clean().
                other_connection(lambda: Order.objects.filter(pk=own.pk).delete())
            return obj

        with patch.object(ManagerOrderAdmin, "get_object", get_object_then_delete):
            response = manager_client.post(order_change_url(own), data)

        assert response.status_code == 404
        assert not Order.objects.filter(pk=own.pk).exists()
        assert not order_audit(own).exists()
        assert not LogEntry.objects.filter(object_id=str(own.pk)).exists()

    @pytest.mark.parametrize(
        ("moved_to", "expected_status"),
        [
            pytest.param("foreign_client", 404, id="foreign-client"),
            pytest.param("sub_order", 404, id="not-master"),
            # Контроль: клиент сменён на другого своего — заказ в выборке, правка проходит.
            pytest.param("own_client", 302, id="other-own-client"),
        ],
    )
    def test_order_moved_after_open_follows_section_scope(
        self, manager_client, manager, other_manager, other_connection, moved_to, expected_status
    ):
        """R42.5-15: до блокировки суперпользователь в /admin/ сменил клиента или `is_master` заказа."""
        own = make_master(make_client(manager), tracking_number="OLD-TRK")
        changes = {
            "foreign_client": {"user_id": make_client(other_manager).pk},
            "sub_order": {"is_master": False},
            "own_client": {"user_id": make_client(manager).pk},
        }[moved_to]
        data = card_payload(manager_client, own, tracking_number="TRK-MOVED")
        original_get_object = ManagerOrderAdmin.get_object

        def get_object_then_move(admin_obj, request, object_id, from_field=None):
            obj = original_get_object(admin_obj, request, object_id, from_field)
            if request.method == "POST":
                # Правка в другом соединении фиксируется до ManagerOrderForm.clean().
                other_connection(lambda: Order.objects.filter(pk=own.pk).update(**changes))
            return obj

        with patch.object(ManagerOrderAdmin, "get_object", get_object_then_move):
            response = manager_client.post(order_change_url(own), data)

        assert response.status_code == expected_status
        after = order_snapshot(own)
        assert {name: after[name] for name in changes} == changes
        if expected_status == 404:
            assert after["tracking_number"] == "OLD-TRK"
            assert not order_audit(own).exists()
            assert not LogEntry.objects.filter(object_id=str(own.pk)).exists()
        else:
            assert after["tracking_number"] == "TRK-MOVED"
            assert order_audit(own).count() == 1

    def test_card_carries_values_seen_on_open(self, manager_client, manager):
        own = make_master(make_client(manager), tracking_number="SEEN-TRK")

        content = manager_client.get(order_change_url(own)).content.decode()

        assert 'name="initial-tracking_number" value="SEEN-TRK"' in content
        assert 'name="initial-delivery_date"' in content

    def test_browser_card_with_delivery_date_saves(self, manager_client, manager):
        """R42.5-20: POST собран из HTML, как его отправит браузер; скрытая исходная дата не пуста."""
        own = make_master(make_client(manager), tracking_number="OLD-TRK", delivery_date=date(2026, 11, 5))
        inputs = html_inputs(manager_client.get(order_change_url(own)).content.decode())
        assert inputs["initial-tracking_number"] == inputs["tracking_number"] == "OLD-TRK"
        # Скрытое поле рендерит дату в ISO, видимое — в формате локали: строки разные.
        assert inputs["delivery_date"] == "05.11.2026"
        assert inputs["initial-delivery_date"] == "2026-11-05"

        response = manager_client.post(
            order_change_url(own), {**inputs, "tracking_number": "NEW-TRK", "_save": "Сохранить"}
        )

        assert response.status_code == 302
        after = order_snapshot(own)
        assert after["tracking_number"] == "NEW-TRK"
        assert after["delivery_date"] == date(2026, 11, 5)
        (record,) = order_audit(own)
        assert record.changes["fields"] == {"tracking_number": {"old": "OLD-TRK", "new": "NEW-TRK"}}

    def test_import_of_other_fields_does_not_make_card_stale(self, manager_client, manager):
        own = make_master(make_client(manager), status="pending")
        data = card_payload(manager_client, own, tracking_number="TRK-AFTER-IMPORT")
        # Импорт статусов 1С пишет свои поля и updated_at, правимые поля не трогает.
        Order.objects.filter(pk=own.pk).update(status="processing", updated_at=timezone.now() + timedelta(minutes=1))

        response = manager_client.post(order_change_url(own), data)

        assert response.status_code == 302
        after = order_snapshot(own)
        assert after["tracking_number"] == "TRK-AFTER-IMPORT"
        assert after["status"] == "processing"


@pytest.fixture
def bonus_program() -> BonusProgramSettings:
    settings = BonusProgramSettings.load()
    settings.is_active = True
    settings.accrual_status = "delivered"
    settings.program_start_at = None
    settings.save()
    return settings


@pytest.fixture
def trainer(manager) -> User:
    return make_client(manager, role="trainer", is_verified=True)


class TestForgedPost:
    """AC5 — подделанный POST заказа."""

    def test_only_tracking_number_is_saved(self, manager_client, manager, trainer, bonus_program, other_manager):
        own = make_master(trainer, status="processing", notes="Комментарий клиента")
        foreign = make_master(make_client(other_manager))
        data = card_payload(manager_client, own)
        before = order_snapshot(own)
        data.update(
            {
                "tracking_number": "TRK-NEW-001",
                "status": "delivered",
                "payment_status": "paid",
                "sent_to_1c": "on",
                "total_amount": "1.00",
                "payment_id": "PAY-FORGED",
                "user": str(foreign.user_id),
                "parent_order": str(foreign.pk),
                "vat_group": "22.00",
                "status_1c": "Подделка",
                "notes": "Подделанный комментарий",
            }
        )

        original_save = Order.save
        with patch.object(Order, "save", autospec=True, side_effect=original_save) as save:
            response = manager_client.post(order_change_url(own), data)

        assert response.status_code == 302
        after = order_snapshot(own)
        assert after["tracking_number"] == "TRK-NEW-001"
        unchanged = {key: value for key, value in after.items() if key not in ("tracking_number", "updated_at")}
        assert unchanged == {
            key: value for key, value in before.items() if key not in ("tracking_number", "updated_at")
        }
        assert not BonusTransaction.objects.filter(order=own).exists()
        master_saves = [call for call in save.call_args_list if call.args[0].pk == own.pk]
        assert [call.kwargs.get("update_fields") for call in master_saves] == [["tracking_number", "updated_at"]]

    def test_pending_bonus_is_accrued_once(self, manager_client, manager, trainer, bonus_program):
        own = make_master(trainer, status="processing")
        # Перевод в delivered в обход сигнала: начисление отложено до следующего сохранения.
        Order.objects.filter(pk=own.pk).update(status="delivered")
        assert not BonusTransaction.objects.filter(order=own).exists()

        for number in ("TRK-1", "TRK-2"):
            response = manager_client.post(
                order_change_url(own), card_payload(manager_client, own, tracking_number=number)
            )
            assert response.status_code == 302
            assert BonusTransaction.objects.filter(order=own).count() == 1

    def test_unchanged_card_neither_saves_nor_accrues(self, manager_client, manager, trainer, bonus_program):
        """R42.5-14: сохранение без изменений не зовёт save() — отложенный бонус не начисляется."""
        own = make_master(trainer, status="processing", tracking_number="SAME-TRK")
        Order.objects.filter(pk=own.pk).update(status="delivered")
        data = card_payload(manager_client, own)

        original_save = Order.save
        with patch.object(Order, "save", autospec=True, side_effect=original_save) as save:
            response = manager_client.post(order_change_url(own), data)

        assert response.status_code == 302
        assert [call for call in save.call_args_list if call.args[0].pk == own.pk] == []
        assert not BonusTransaction.objects.filter(order=own).exists()


class TestExport:
    """AC6 — экспорт CSV только своих заказов."""

    def test_selected_forged_foreign_id_is_ignored(self, manager_client, manager, other_manager):
        client_user = make_client(manager)
        first, second = make_master(client_user), make_master(client_user)
        # Свой, но не выбранный: экспорт выгружает выбор, а не весь раздел (R42.5-21).
        make_master(client_user)
        foreign = make_master(make_client(other_manager))

        response = post_order_action(manager_client, "export_orders_csv", first, second, foreign)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert response["Content-Disposition"] == 'attachment; filename="orders_export.csv"'
        assert response.content[:3] == b"\xef\xbb\xbf"
        rows = csv_rows(response)
        assert rows[0] == EXPECTED_CSV_HEADER
        assert {row[0] for row in rows[1:]} == {first.order_number, second.order_number}

    def test_select_across_exports_only_own_masters(self, manager_client, manager, other_manager):
        client_user = make_client(manager)
        first, second = make_master(client_user), make_master(client_user)
        foreign = make_master(make_client(other_manager))

        response = post_order_action(manager_client, "export_orders_csv", first, select_across="1")

        assert response.status_code == 200
        numbers = {row[0] for row in csv_rows(response)[1:]}
        assert numbers == {first.order_number, second.order_number}
        assert foreign.order_number not in numbers

    def test_select_across_keeps_changelist_filter(self, manager_client, manager, other_manager):
        # Действие получает отфильтрованную выборку списка, а не весь раздел (R42.5-24).
        client_user = make_client(manager)
        first, second = make_master(client_user), make_master(client_user)
        processing = make_master(client_user, status="processing")
        make_master(make_client(other_manager))

        response = manager_client.post(
            f"{ORDERS_URL}?status__exact=pending",
            {"action": "export_orders_csv", "_selected_action": [str(first.pk)], "select_across": "1"},
        )

        assert response.status_code == 200
        numbers = {row[0] for row in csv_rows(response)[1:]}
        assert numbers == {first.order_number, second.order_number}
        assert processing.order_number not in numbers

    def test_export_does_not_load_order_items(self, manager_client, manager):
        # Позиции в CSV не выгружаются: prefetch родителя снят (R42.5-25).
        client_user = make_client(manager)
        orders = [make_master(client_user) for _ in range(3)]

        with CaptureQueriesContext(connection) as queries:
            response = post_order_action(manager_client, "export_orders_csv", *orders)

        assert response.status_code == 200
        assert len(csv_rows(response)) == 4
        items_table = f'"{OrderItem._meta.db_table}"'
        assert [query["sql"] for query in queries if items_table in query["sql"]] == []

    def test_row_values_follow_admin_export_order(self, manager_client, manager):
        own = make_master(make_client(manager))
        # 22:30 UTC 14.10 — это 01:30 15.10 по Москве: дата файла совпадает с карточкой.
        Order.objects.filter(pk=own.pk).update(created_at=datetime(2026, 10, 14, 22, 30, tzinfo=UTC))

        rows = csv_rows(post_order_action(manager_client, "export_orders_csv", own))

        assert rows[1] == [
            own.order_number,
            own.order_number_display,
            own.customer_display_name,
            own.get_status_display(),
            own.get_payment_status_display(),
            str(own.total_amount),
            own.get_delivery_method_display(),
            "2026-10-15 01:30",
        ]

    @pytest.mark.parametrize("name", ["=1+1", "+7(900)", "-2+3", "@SUM(A1)", '=HYPERLINK("http://evil")'])
    def test_formula_in_client_name_is_neutralized(self, manager_client, manager, name):
        own = make_master(make_client(manager, first_name=name, last_name=""))

        rows = csv_rows(post_order_action(manager_client, "export_orders_csv", own))

        assert rows[1][2] == f"'{name}"
        assert rows[1][0] == own.order_number

    def test_multiline_client_name_is_kept_in_one_cell(self, manager_client, manager):
        own = make_master(make_client(manager, first_name="Первая\nВторая", last_name=""))

        response = post_order_action(manager_client, "export_orders_csv", own)

        rows = csv_rows(response)
        assert len(rows) == 2
        assert rows[1][2] == "Первая\nВторая"
        assert rows[1][0] == own.order_number

    def test_action_choices_are_russian_without_delete(self, manager_client, manager):
        make_master(make_client(manager))

        response = manager_client.get(ORDERS_URL)

        choices = list(response.context["action_form"].fields["action"].choices)
        assert choices == [("", "---------"), ("export_orders_csv", "Выгрузить выбранные заказы в CSV")]

    def test_admin_export_is_unchanged(self, client):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        client.force_login(superuser)
        order = make_master(make_client(None))

        response = client.post("/admin/orders/order/", {"action": "export_to_csv", "_selected_action": [str(order.pk)]})

        assert response.status_code == 200
        assert not response.content.startswith(b"\xef\xbb\xbf")
        assert csv_rows(response)[0][0] == "Order Number"


class TestAuditLog:
    """AC7 — журнал правки заказа."""

    def test_tracking_number_change(self, manager_client, manager):
        own = make_master(make_client(manager))

        response = manager_client.post(
            order_change_url(own), card_payload(manager_client, own, tracking_number="TRK-77")
        )

        assert response.status_code == 302
        (record,) = order_audit(own)
        assert record.action == "update_order"
        assert record.user == manager
        assert record.details["changes"] == {
            "order_number": own.order_number,
            "fields": {"tracking_number": {"old": None, "new": "TRK-77"}},
        }

    def test_both_fields_change(self, manager_client, manager):
        own = make_master(make_client(manager), tracking_number="OLD-TRK", delivery_date=datetime(2026, 10, 20).date())

        response = manager_client.post(
            order_change_url(own),
            card_payload(manager_client, own, tracking_number="NEW-TRK", delivery_date="2026-11-01"),
        )

        assert response.status_code == 302
        (record,) = order_audit(own)
        assert record.details["changes"]["fields"] == {
            "tracking_number": {"old": "OLD-TRK", "new": "NEW-TRK"},
            "delivery_date": {"old": "2026-10-20", "new": "2026-11-01"},
        }
        own.refresh_from_db()
        assert own.tracking_number == "NEW-TRK"
        assert own.delivery_date == date(2026, 11, 1)

    def test_clearing_date_writes_none(self, manager_client, manager):
        own = make_master(make_client(manager), delivery_date=datetime(2026, 10, 20).date())

        manager_client.post(order_change_url(own), card_payload(manager_client, own, delivery_date=""))

        (record,) = order_audit(own)
        assert record.details["changes"]["fields"] == {"delivery_date": {"old": "2026-10-20", "new": None}}
        own.refresh_from_db()
        assert own.delivery_date is None

    def test_save_without_changes_writes_nothing(self, manager_client, manager):
        own = make_master(make_client(manager), tracking_number="SAME-TRK")
        before = order_snapshot(own)

        response = manager_client.post(order_change_url(own), card_payload(manager_client, own))

        assert response.status_code == 302
        assert order_snapshot(own) == before
        assert not order_audit(own).exists()

    def test_failed_audit_rolls_back_order(self, manager_client, manager):
        # Заказ без записи журнала не сохраняется: сбой журнала откатывает правку (R42.5-23).
        own = make_master(make_client(manager), tracking_number="OLD-TRK", delivery_date=date(2026, 10, 20))
        payload = card_payload(manager_client, own, tracking_number="NEW-TRK", delivery_date="2026-11-01")
        before = order_snapshot(own)

        def fail_after_save(**kwargs: Any) -> None:
            # Сбой — уже после настоящего save(): в транзакции запроса правка записана.
            assert Order.objects.values_list("tracking_number", flat=True).get(pk=own.pk) == "NEW-TRK"
            raise RuntimeError("журнал недоступен")

        with patch.object(AuditLog, "log_action", side_effect=fail_after_save) as log_action:
            with pytest.raises(RuntimeError, match="журнал недоступен"):
                manager_client.post(order_change_url(own), payload)

        assert log_action.call_count == 1
        after = order_snapshot(own)
        assert after["tracking_number"] == "OLD-TRK"
        assert after["delivery_date"] == date(2026, 10, 20)
        assert after["updated_at"] == before["updated_at"]
        assert not order_audit(own).exists()
        assert not LogEntry.objects.filter(object_id=str(own.pk)).exists()


def make_applicant(manager: User | None, **overrides: Any) -> User:
    defaults = {"verification_status": "pending", "is_verified": False, "is_active": False}
    defaults.update(overrides)
    return make_client(manager, **defaults)


def set_created_at(user: User, value: datetime) -> None:
    User.objects.filter(pk=user.pk).update(created_at=value)


def local_noon(days_ago: int) -> datetime:
    """Полдень N календарных дней назад по времени проекта — без границы суток в тесте."""
    return timezone.make_aware(datetime.combine(timezone.localdate() - timedelta(days=days_ago), time(12, 0)))


class TestQueue:
    """AC8 — главная со счётчиками."""

    def test_counters_and_links(self, manager_client, manager, other_manager):
        applicants = [make_applicant(manager) for _ in range(3)]
        set_created_at(applicants[0], local_noon(5))
        # Запись 1С без аккаунта в статусе pending: список клиентов её по умолчанию скрывает.
        make_client(manager, role=User.ROLE_UNREGISTERED, verification_status="pending", is_verified=False)
        client_user = make_client(manager)
        new_orders = [make_master(client_user), make_master(client_user)]
        make_master(client_user, status="processing")
        make_applicant(other_manager)
        make_master(make_client(other_manager))

        response = manager_client.get(INDEX_URL)

        content = response.content.decode()
        assert "Заявки на верификацию: 3, старейшая — 5 дней" in content
        assert "Новые заказы: 2" in content
        users_url = "/manager/users/user/?verification_status__exact=pending"
        orders_url = "/manager/orders/order/?status__exact=pending"
        assert f'href="{users_url}"' in content
        assert f'href="{orders_url}"' in content

        users_list = manager_client.get(users_url).context["cl"]
        assert users_list.result_count == 3
        assert {user.pk for user in users_list.result_list} == {user.pk for user in applicants}
        orders_list = manager_client.get(orders_url).context["cl"]
        assert orders_list.result_count == 2
        assert {order.pk for order in orders_list.result_list} == {order.pk for order in new_orders}

    def test_zero_applications_without_oldest(self, manager_client):
        content = manager_client.get(INDEX_URL).content.decode()

        assert "Заявки на верификацию: 0" in content
        assert "старейшая" not in content
        assert "Новые заказы: 0" in content

    def test_application_today(self, manager_client, manager):
        make_applicant(manager)

        content = manager_client.get(INDEX_URL).content.decode()

        assert "Заявки на верификацию: 1, старейшая — сегодня" in content

    def test_calendar_day_boundary(self, manager):
        moscow = ZoneInfo("Europe/Moscow")
        applicant = make_applicant(manager)
        set_created_at(applicant, datetime(2026, 10, 14, 23, 50, tzinfo=moscow))
        request = RequestFactory().get(INDEX_URL)
        request.user = manager

        with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 15, 0, 10, tzinfo=moscow)):
            queue = manager_queue(request, manager_site)

        assert queue[0]["text"] == "Заявки на верификацию: 1, старейшая — 1 день"


def set_group_permissions(*codenames: str) -> None:
    """Права группы «Менеджеры» — только перечисленные `app_label.codename`."""
    permissions = [
        Permission.objects.get(content_type__app_label=app_label, codename=codename)
        for app_label, codename in (name.split(".") for name in codenames)
    ]
    Group.objects.get(name=MANAGERS_GROUP).permissions.set(permissions)


class TestQueuePermissions:
    """R42.5-3 — счётчик показан, только если открывается список по его ссылке."""

    @pytest.fixture(autouse=True)
    def queue_data(self, manager):
        make_applicant(manager)
        make_master(make_client(manager))

    def test_without_order_permissions_no_orders_counter(self, manager_client):
        set_group_permissions("users.view_user", "users.change_user")

        content = manager_client.get(INDEX_URL).content.decode()

        assert "Заявки на верификацию: 1" in content
        assert "Новые заказы" not in content
        assert "/manager/orders/order/?status__exact=pending" not in content
        assert manager_client.get("/manager/orders/order/?status__exact=pending").status_code == 403

    def test_without_user_permissions_no_applications_counter(self, manager_client):
        set_group_permissions("orders.view_order", "orders.change_order")

        content = manager_client.get(INDEX_URL).content.decode()

        assert "Новые заказы: 1" in content
        assert "Заявки на верификацию" not in content
        assert "/manager/users/user/?verification_status__exact=pending" not in content
        assert manager_client.get("/manager/users/user/?verification_status__exact=pending").status_code == 403

    def test_view_permission_alone_keeps_counters(self, manager_client):
        set_group_permissions("orders.view_order", "users.view_user")

        content = manager_client.get(INDEX_URL).content.decode()

        assert "Заявки на верификацию: 1" in content
        assert "Новые заказы: 1" in content

    def test_without_both_no_queue_block(self, manager_client):
        set_group_permissions()

        response = manager_client.get(INDEX_URL)

        assert response.status_code == 200
        assert 'id="manager-queue"' not in response.content.decode()


class TestViewOnlyPermissions:
    """AC9 — права внутри раздела при одном `view_order`."""

    @pytest.fixture(autouse=True)
    def view_only_group(self):
        group = Group.objects.get(name=MANAGERS_GROUP)
        full = list(group.permissions.all())
        view_only = [
            Permission.objects.get(content_type__app_label="orders", codename="view_order"),
            Permission.objects.get(content_type__app_label="users", codename="view_user"),
        ]
        group.permissions.set(view_only)
        return group, full, view_only

    def test_card_is_read_only_and_post_forbidden(self, manager_client, manager, view_only_group):
        group, full, view_only = view_only_group
        own = make_master(make_client(manager))

        response = manager_client.get(order_change_url(own))
        assert response.status_code == 200
        content = response.content.decode()
        assert 'name="tracking_number"' not in content
        assert 'name="delivery_date"' not in content

        # Форма, какую отправил бы менеджер с полными правами, — снята до урезания прав.
        group.permissions.set(full)
        data = card_payload(manager_client, own, tracking_number="TRK-FORBIDDEN")
        group.permissions.set(view_only)
        before = order_snapshot(own)

        assert manager_client.post(order_change_url(own), data).status_code == 403
        assert order_snapshot(own) == before
        assert not order_audit(own).exists()

    def test_export_is_available_for_own_orders(self, manager_client, manager, other_manager):
        own = make_master(make_client(manager))
        foreign = make_master(make_client(other_manager))

        response = post_order_action(manager_client, "export_orders_csv", own, foreign)

        assert response.status_code == 200
        assert [row[0] for row in csv_rows(response)[1:]] == [own.order_number]


class TestLinksStayInSection:
    """AC10 — ссылки и редиректы раздела ведут в раздел."""

    @staticmethod
    def assert_no_admin_links(response) -> None:
        assert response.status_code == 200
        assert 'href="/admin/' not in response.content.decode()

    def test_pages_have_no_admin_links(self, manager_client, manager):
        own = make_master(make_client(manager))
        make_applicant(manager)

        response = manager_client.post(order_change_url(own), card_payload(manager_client, own, tracking_number="T-1"))
        assert response.status_code == 302
        assert response.url == ORDERS_URL
        assert LogEntry.objects.filter(user=manager, object_id=str(own.pk)).exists()

        index = manager_client.get(INDEX_URL)
        self.assert_no_admin_links(index)
        assert "recent-actions-module" not in index.content.decode()
        for url in (ORDERS_URL, order_change_url(own), order_history_url(own)):
            self.assert_no_admin_links(manager_client.get(url))

    def test_save_and_continue_stays_on_card(self, manager_client, manager):
        own = make_master(make_client(manager))

        data = card_payload(manager_client, own, tracking_number="T-2")
        data.pop("_save")
        data["_continue"] = "1"
        response = manager_client.post(order_change_url(own), data)

        assert response.status_code == 302
        assert response.url.startswith(order_change_url(own))
        assert Order.objects.get(pk=own.pk).tracking_number == "T-2"


class TestQueryCount:
    """AC11 — число SQL-запросов не зависит от числа строк (NFR-42-04)."""

    def test_changelist(self, manager_client, manager, django_assert_num_queries):
        client_user = make_client(manager)
        product = ProductFactory()

        def add_orders(count: int) -> None:
            for _ in range(count):
                make_master(client_user, product=product)

        add_orders(5)
        with CaptureQueriesContext(connection) as captured:
            first = manager_client.get(ORDERS_URL)
        assert len(first.context["cl"].result_list) == 5
        baseline = len(captured)

        add_orders(45)
        with django_assert_num_queries(baseline):
            second = manager_client.get(ORDERS_URL)
        rows = second.context["cl"].result_list
        assert len(rows) == 50
        assert all(second.context["cl"].model_admin.items_count(row) == 2 for row in rows)

    def test_index(self, manager_client, manager, django_assert_num_queries):
        client_user = make_client(manager)
        product = ProductFactory()

        def add_queue(count: int) -> None:
            for _ in range(count):
                make_applicant(manager)
                make_master(client_user, subs=0, product=product)

        add_queue(3)
        with CaptureQueriesContext(connection) as captured:
            first = manager_client.get(INDEX_URL)
        assert "Новые заказы: 3" in first.content.decode()
        baseline = len(captured)

        add_queue(27)
        with django_assert_num_queries(baseline):
            second = manager_client.get(INDEX_URL)
        assert "Новые заказы: 30" in second.content.decode()

"""
Integration-тесты журнала действий сотрудников `/supervisor/journal/` (стори 42.9).

Покрывает:
- AC1 — вход и отказ, страницы нет на других сайтах, просмотр не пишет журнал;
- AC2 — каждое действие перечня (FR-42-30) пишет ровно одну запись и видно в ленте;
- AC3 — вид строки, ссылки на объекты, отсутствие IP, User-Agent и JSON, экранирование;
- AC4 — фильтры по сотруднику и периоду, период по умолчанию, ошибки фильтра;
- AC5 — только действия сотрудников трёх ролей;
- AC6 — порядок и страницы; AC7 — число запросов; AC8 — главная и ссылки раздела;
- AC9 — сброс пароля и журнал в одной транзакции (R42.7-D2);
- AC11 — автора записей ленты нельзя удалить в `/admin/`.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`):
группы ролей заново создаёт `role_groups`, правила регионов задаёт сам тест.
Ожидаемые подписи, тексты и ссылки — литералами. Записи AC3–AC7 и AC11
создаются `AuditLog.log_action()` напрямую, AC2 — только настоящими запросами.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from html.parser import HTMLParser
from types import SimpleNamespace
from typing import Any, Callable
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.contrib.messages.storage.cookie import CookieStorage
from django.contrib.sessions.backends.signed_cookies import SessionStore
from django.db import connection
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import AuditLog, ManagerRoutingRule
from apps.orders.models import Order
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import manager_site, supervisor_site
from tests.integration.test_manager_clients_section import (  # noqa: F401 — фикстуры подключаются импортом
    NEW_PASSWORD,
    PASSWORD,
    change_url,
    form_payload,
    get_unique_suffix,
    make_1c_record,
    make_client,
    make_staff_member,
    manager,
    no_routing_rules,
    other_manager,
    password_url,
    post_action,
    region_tax_id,
    role_groups,
    verified_email_task,
    verify_url,
)
from tests.integration.test_manager_orders_section import (  # noqa: F401 — фикстуры подключаются импортом
    card_payload,
    make_master,
    order_change_url,
    order_emails,
)
from tests.integration.test_supervisor_section import (  # noqa: F401 — фикстуры подключаются импортом
    RULES_ADD_URL,
    STAFF_ADD_URL,
    client_change_url,
    count_queries,
    failing_journal,
    logged_in,
    post_staff_action,
    rule,
    rule_change_url,
    rule_payload,
    staff_change_url,
    staff_create_payload,
    staff_password_url,
    superuser_client,
    supervisor,
    supervisor_client,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

JOURNAL_URL = "/supervisor/journal/"
ALL_TIME = {"date_from": "", "date_to": ""}
MOSCOW = ZoneInfo("Europe/Moscow")
# «Сегодня» ленты в тестах периода: 17.10.2026, период по умолчанию — 18.09–17.10.
TODAY_NOON = datetime(2026, 10, 17, 12, 0, tzinfo=MOSCOW)
TECH_IP = "203.0.113.7"
TECH_AGENT = "JournalAgent/1.0"
INVALID_FILTER = "Фильтр указан неверно — записи не показаны."
DELETE_GUARD_MESSAGE = (
    "Учётная запись — автор записей журнала действий сотрудников. "
    "Удаление стёрло бы автора: заблокируйте сотрудника вместо удаления."
)
RESPONSIBLE_GUARD_MESSAGE = (
    "Учётная запись — ответственный менеджер клиентов или менеджер правила региона. "
    "Сначала назначьте клиентам нового менеджера и замените менеджера в правилах регионов."
)


class _Rows(HTMLParser):
    """Строки ленты (`tr.journal-row`): тексты ячеек и ссылки."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: list[tuple[str, ...]] = []
        self.links: list[list[str]] = []
        self._row: list[str] | None = None
        self._row_links: list[str] = []
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "tr" and values.get("class") == "journal-row":
            self._row, self._row_links = [], []
        elif tag == "td" and self._row is not None:
            self._cell = []
        elif tag == "a" and self._row is not None:
            self._row_links.append(values["href"] or "")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "td" and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(tuple(self._row))
            self.links.append(self._row_links)
            self._row = None


def journal_page(response) -> _Rows:
    assert response.status_code == 200
    parser = _Rows()
    parser.feed(response.content.decode())
    return parser


class _FilterForm(HTMLParser):
    """Форма фильтра (`div#journal-filter > form`): способ отправки, адрес, имена полей и варианты выбора."""

    def __init__(self) -> None:
        super().__init__()
        self.method: str | None = None
        self.action: str | None = None
        self.names: list[str] = []
        self.options: dict[str, list[str]] = {}
        self._in_block = False
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag == "div" and values.get("id") == "journal-filter":
            self._in_block = True
        elif not self._in_block:
            return
        elif tag == "form":
            self.method, self.action = values.get("method"), values.get("action")
        elif tag == "select":
            self._select = values["name"] or ""
            self.names.append(self._select)
            self.options[self._select] = []
        elif tag == "option" and self._select is not None:
            self.options[self._select].append(values.get("value") or "")
        elif tag == "input" and values.get("type") != "submit":
            self.names.append(values["name"] or "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._select = None
        elif tag == "form":
            self._in_block = False


def filter_form_of(response) -> _FilterForm:
    assert response.status_code == 200
    parser = _FilterForm()
    parser.feed(response.content.decode())
    return parser


def listed(response) -> list[int]:
    """pk записей страницы ленты в порядке вывода."""
    return [record.pk for record in response.context["page_obj"].object_list]


def label(user: User) -> str:
    return f"{user.first_name} {user.last_name} ({user.email})"


def ui_number(order: Order) -> str:
    return f"{order.order_number[1:5]}-{order.order_number[5:10]}"


def log(
    author: User | None,
    action: str,
    target: Any,
    changes: dict[str, Any] | None = None,
    at: datetime | None = None,
    resource_type: str | None = None,
) -> AuditLog:
    """Запись журнала напрямую, с IP и User-Agent, которых в ленте быть не должно."""
    entry = AuditLog.log_action(
        user=author,
        action=action,
        resource_type=resource_type or type(target).__name__,
        resource_id=target.pk,
        changes=changes or {"email": getattr(target, "email", "")},
        ip_address=TECH_IP,
        user_agent=TECH_AGENT,
    )
    if at is not None:
        AuditLog.objects.filter(pk=entry.pk).update(created_at=at)
    return entry


def moscow(day: int, hour: int, minute: int, month: int = 10) -> datetime:
    return datetime(2026, month, day, hour, minute, tzinfo=MOSCOW)


@pytest.fixture
def today():
    with patch("django.utils.timezone.now", return_value=TODAY_NOON):
        yield


@pytest.fixture
def as_supervisor(supervisor) -> Client:
    return logged_in(supervisor)


# --------------------------------------------------------------------------
# AC1 — вход и отказ
# --------------------------------------------------------------------------


class TestEntry:
    def test_supervisor_opens_journal(self, supervisor_client, manager):
        log(manager, "block_user", make_client(manager))
        audit_before = AuditLog.objects.count()

        response = supervisor_client.get(JOURNAL_URL)

        assert response.status_code == 200
        html = response.content.decode()
        assert "OPTISPORT — Руководитель" in html
        assert "<h1>Журнал действий</h1>" in html
        assert AuditLog.objects.count() == audit_before

    @pytest.mark.parametrize(
        "make_user",
        [
            pytest.param(lambda: make_staff_member(MANAGERS_GROUP), id="manager"),
            pytest.param(lambda: make_staff_member(MARKETING_GROUP), id="marketing"),
            pytest.param(lambda: make_staff_member(None), id="staff-without-group"),
            pytest.param(lambda: make_staff_member(SUPERVISORS_GROUP, is_active=False), id="blocked-supervisor"),
            pytest.param(
                lambda: User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD),
                id="superuser",
            ),
            pytest.param(
                lambda: make_staff_member(SUPERVISORS_GROUP, is_superuser=True), id="superuser-in-supervisors"
            ),
            pytest.param(None, id="anonymous"),
        ],
    )
    def test_others_are_redirected_to_login(self, client, make_user):
        if make_user is not None:
            client.force_login(make_user())

        response = client.get(JOURNAL_URL)

        assert response.status_code == 302
        assert response["Location"] == "/supervisor/login/?next=/supervisor/journal/"

    def test_no_journal_on_other_sites(self, supervisor_client):
        assert supervisor_client.get("/manager/journal/").status_code == 404
        assert supervisor_client.get("/marketing/journal/").status_code == 404


# --------------------------------------------------------------------------
# AC2 — каждое действие перечня пишет ровно одну запись (FR-42-30)
# --------------------------------------------------------------------------


@dataclass
class Expected:
    """Что действие должно оставить в журнале и в ленте."""

    author: User
    action: str
    resource_type: str
    resource_id: int
    row: tuple[str, str, str, str]  # сотрудник, действие, объект, подробности
    link: str  # ссылка объекта; пустая — без ссылки


def client_row(author: User, target: User, action: str, details: str = "—") -> Expected:
    return Expected(
        author,
        "",
        "User",
        target.pk,
        (label(author), action, label(target), details),
        f"/manager/users/user/{target.pk}/change/",
    )


def deleted_client_row(author: User, target: User, action: str) -> Expected:
    """Удалённый клиент: лента подписывает его email из записи и ссылки не даёт."""
    return Expected(author, "", "User", target.pk, (label(author), action, str(target.email), "—"), "")


def staff_row(author: User, member: User, action: str, details: str) -> Expected:
    return Expected(
        author,
        "",
        "User",
        member.pk,
        (label(author), action, label(member), details),
        f"/supervisor/users/user/{member.pk}/change/",
    )


def with_code(expected: Expected, code: str) -> Expected:
    expected.action = code
    return expected


def card_flag(ctx: SimpleNamespace, target: User, active: bool) -> None:
    data = form_payload(ctx.as_manager.get(change_url(target)))
    if active:
        data["is_active"] = "on"
    else:
        data.pop("is_active")
    data["_save"] = "Сохранить"
    assert ctx.as_manager.post(change_url(target), data).status_code == 302


def do_verify_page(ctx: SimpleNamespace) -> Expected:
    applicant = make_client(
        ctx.manager, role="wholesale_level1", verification_status="pending", is_verified=False, is_active=False
    )
    response = ctx.as_manager.post(
        verify_url(applicant), {"confirm": "on", "confirm_without_1c": "on", "role": "trainer"}
    )
    assert response.status_code == 302
    return with_code(
        client_row(ctx.manager, applicant, "Подтверждение B2B-заявки", "роль: Оптовик уровень 1 → Тренер/Фитнес-клуб"),
        "verify_b2b",
    )


def do_approve_action(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager, verification_status="pending", is_verified=False)
    post_action(ctx.as_manager, "approve_b2b_users", target)
    return with_code(client_row(ctx.manager, target, "Верификация клиента"), "approve_b2b")


def do_reject_page(ctx: SimpleNamespace) -> Expected:
    applicant = make_client(ctx.manager, verification_status="pending", is_verified=False, is_active=False)
    assert ctx.as_manager.post(verify_url(applicant), {"_reject": "1"}).status_code == 302
    assert not User.objects.filter(pk=applicant.pk).exists()
    return with_code(deleted_client_row(ctx.manager, applicant, "Отказ в верификации"), "reject_b2b")


def do_reject_action(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager, verification_status="pending", is_verified=False)
    post_action(ctx.as_manager, "reject_b2b_users", target)
    assert not User.objects.filter(pk=target.pk).exists()
    return with_code(deleted_client_row(ctx.manager, target, "Отказ в верификации"), "reject_b2b")


def do_block_action(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager)
    post_action(ctx.as_manager, "block_users", target)
    return with_code(client_row(ctx.manager, target, "Блокировка клиента"), "block_user")


def do_unblock_action(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager, is_active=False)
    post_action(ctx.as_manager, "unblock_users", target)
    return with_code(client_row(ctx.manager, target, "Разблокировка клиента"), "unblock_user")


def do_block_card(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager)
    card_flag(ctx, target, active=False)
    return with_code(client_row(ctx.manager, target, "Блокировка клиента"), "block_user")


def do_unblock_card(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager, is_active=False)
    card_flag(ctx, target, active=True)
    return with_code(client_row(ctx.manager, target, "Разблокировка клиента"), "unblock_user")


def do_client_password(ctx: SimpleNamespace) -> Expected:
    target = make_client(ctx.manager)
    response = ctx.as_manager.post(
        password_url(target), {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )
    assert response.status_code == 302
    return with_code(client_row(ctx.manager, target, "Сброс пароля"), "change_password")


def do_link_action(ctx: SimpleNamespace) -> Expected:
    applicant = make_client(ctx.manager, verification_status="pending", is_verified=False)
    source = make_1c_record(applicant.tax_id)
    post_action(ctx.as_manager, "link_1c_customer", applicant, apply="1", candidate=f"{source.pk}:{source.onec_id}")
    applicant.refresh_from_db()
    assert applicant.onec_id == source.onec_id
    return with_code(client_row(ctx.manager, applicant, "Привязка к контрагенту 1С"), "link_1c_customer")


def do_order_card(ctx: SimpleNamespace) -> Expected:
    own = make_master(make_client(ctx.manager), delivery_date=date(2026, 10, 20))
    payload = card_payload(ctx.as_manager, own, tracking_number="RR123456789RU", delivery_date="2026-10-25")
    assert ctx.as_manager.post(order_change_url(own), payload).status_code == 302
    return Expected(
        ctx.manager,
        "update_order",
        "Order",
        own.pk,
        (
            label(ctx.manager),
            "Изменение заказа",
            f"Заказ {ui_number(own)}",
            "трек-номер: — → RR123456789RU; дата доставки: 20.10.2026 → 25.10.2026",
        ),
        f"/manager/orders/order/{own.pk}/change/",
    )


def assign_in_card(ctx: SimpleNamespace, customer: User, manager: User | None) -> None:
    data = form_payload(ctx.as_supervisor.get(client_change_url(customer)))
    if manager is not None:
        data["responsible_manager"] = str(manager.pk)
    else:
        data.pop("responsible_manager_manual")
    assert ctx.as_supervisor.post(client_change_url(customer), data).status_code == 302


def do_assign(ctx: SimpleNamespace) -> Expected:
    customer = make_client(ctx.manager, manual=False)
    assign_in_card(ctx, customer, ctx.other_manager)
    details = f"{label(ctx.manager)} → {label(ctx.other_manager)}"
    return with_code(
        client_row(ctx.supervisor, customer, "Назначение ответственного менеджера", details),
        "assign_responsible_manager",
    )


def do_reassign(ctx: SimpleNamespace) -> Expected:
    customer = make_client(ctx.manager, manual=True)
    assign_in_card(ctx, customer, ctx.other_manager)
    details = f"{label(ctx.manager)} → {label(ctx.other_manager)}"
    return with_code(
        client_row(ctx.supervisor, customer, "Назначение ответственного менеджера", details),
        "assign_responsible_manager",
    )


def do_release_manual(ctx: SimpleNamespace) -> Expected:
    rule("50", ctx.other_manager)
    customer = make_client(ctx.manager, manual=True, tax_id=region_tax_id("50"))
    assign_in_card(ctx, customer, None)
    details = f"{label(ctx.manager)} → {label(ctx.other_manager)}; по правилу региона"
    return with_code(
        client_row(ctx.supervisor, customer, "Назначение ответственного менеджера", details),
        "assign_responsible_manager",
    )


def rule_expected(ctx: SimpleNamespace, rule_id: int, action: str, rule_text: str, details: str, link: bool):
    return Expected(
        ctx.supervisor,
        "change_routing_rule",
        "ManagerRoutingRule",
        rule_id,
        (label(ctx.supervisor), action, rule_text, details),
        f"/supervisor/common/managerroutingrule/{rule_id}/change/" if link else "",
    )


def do_rule_create(ctx: SimpleNamespace) -> Expected:
    assert ctx.as_supervisor.post(RULES_ADD_URL, rule_payload(manager=ctx.manager.pk)).status_code == 302
    created = ManagerRoutingRule.objects.get(match_value="23")
    return rule_expected(
        ctx,
        created.pk,
        "Создание правила региона",
        f"Код субъекта РФ (по ИНН):23 → {ctx.manager.email}",
        f"тип: — → Код субъекта РФ (по ИНН); значение: — → 23; активно: — → да; менеджер: — → {label(ctx.manager)}",
        link=True,
    )


def do_rule_update(ctx: SimpleNamespace) -> Expected:
    region_rule = rule("23", ctx.manager)
    data = form_payload(ctx.as_supervisor.get(rule_change_url(region_rule)))
    data["manager"] = str(ctx.other_manager.pk)
    assert ctx.as_supervisor.post(rule_change_url(region_rule), data).status_code == 302
    return rule_expected(
        ctx,
        region_rule.pk,
        "Изменение правила региона",
        f"Код субъекта РФ (по ИНН):23 → {ctx.other_manager.email}",
        f"менеджер: {label(ctx.manager)} → {label(ctx.other_manager)}",
        link=True,
    )


def do_rule_delete(ctx: SimpleNamespace) -> Expected:
    region_rule = rule("23", ctx.manager)
    assert ctx.as_supervisor.post(f"{rule_change_url(region_rule)[:-7]}delete/", {"post": "yes"}).status_code == 302
    return rule_expected(
        ctx,
        region_rule.pk,
        "Удаление правила региона",
        f"Код субъекта РФ (по ИНН):23 → {ctx.manager.email}",
        f"тип: Код субъекта РФ (по ИНН) → —; значение: 23 → —; активно: да → —; менеджер: {label(ctx.manager)} → —",
        link=False,
    )


def do_staff_create(ctx: SimpleNamespace) -> Expected:
    payload = staff_create_payload()
    assert ctx.as_supervisor.post(STAFF_ADD_URL, payload).status_code == 302
    member = User.objects.get(email=payload["email"])
    return with_code(staff_row(ctx.supervisor, member, "Создание сотрудника", "группа: Менеджеры"), "create_staff")


def do_staff_block(ctx: SimpleNamespace) -> Expected:
    member = make_staff_member(MANAGERS_GROUP)
    post_staff_action(ctx.as_supervisor, "block_staff", member)
    return with_code(staff_row(ctx.supervisor, member, "Блокировка сотрудника", "группа: Менеджеры"), "block_staff")


def do_staff_unblock(ctx: SimpleNamespace) -> Expected:
    member = make_staff_member(MANAGERS_GROUP, is_active=False)
    post_staff_action(ctx.as_supervisor, "unblock_staff", member)
    return with_code(
        staff_row(ctx.supervisor, member, "Разблокировка сотрудника", "группа: Менеджеры"), "unblock_staff"
    )


def do_staff_group(ctx: SimpleNamespace) -> Expected:
    member = make_staff_member(MANAGERS_GROUP)
    data = form_payload(ctx.as_supervisor.get(staff_change_url(member)))
    data["role_group"] = MARKETING_GROUP
    assert ctx.as_supervisor.post(staff_change_url(member), data).status_code == 302
    return with_code(
        staff_row(ctx.supervisor, member, "Смена группы сотрудника", "Менеджеры → Маркетинг"), "change_staff_group"
    )


def do_staff_password(ctx: SimpleNamespace) -> Expected:
    member = make_staff_member(MANAGERS_GROUP)
    response = ctx.as_supervisor.post(
        staff_password_url(member), {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )
    assert response.status_code == 302
    return with_code(staff_row(ctx.supervisor, member, "Сброс пароля", "—"), "change_password")


# Перечень действий section-contents.md: русское название → сценарий настоящим запросом.
STAFF_ACTION_SCENARIOS: list[tuple[str, Callable[[SimpleNamespace], Expected]]] = [
    ("Верификация на странице подтверждения со сменой роли", do_verify_page),
    ("Верификация действием списка", do_approve_action),
    ("Отказ на странице подтверждения", do_reject_page),
    ("Отказ действием списка", do_reject_action),
    ("Блокировка клиента действием списка", do_block_action),
    ("Разблокировка клиента действием списка", do_unblock_action),
    ("Блокировка клиента флагом в карточке", do_block_card),
    ("Разблокировка клиента флагом в карточке", do_unblock_card),
    ("Сброс пароля клиенту", do_client_password),
    ("Привязка к 1С действием списка", do_link_action),
    ("Трек-номер и дата доставки", do_order_card),
    ("Назначение ответственного вручную", do_assign),
    ("Переназначение ответственного другому", do_reassign),
    ("Снятие флага «вручную»", do_release_manual),
    ("Создание правила региона", do_rule_create),
    ("Правка правила региона", do_rule_update),
    ("Удаление правила региона", do_rule_delete),
    ("Создание сотрудника", do_staff_create),
    ("Блокировка сотрудника", do_staff_block),
    ("Разблокировка сотрудника", do_staff_unblock),
    ("Смена группы сотрудника", do_staff_group),
    ("Сброс пароля сотруднику", do_staff_password),
]


@pytest.fixture
def actors(manager, other_manager, supervisor) -> SimpleNamespace:
    return SimpleNamespace(
        manager=manager,
        other_manager=other_manager,
        supervisor=supervisor,
        as_manager=logged_in(manager),
        as_supervisor=logged_in(supervisor),
    )


class TestEveryActionIsJournaled:
    @pytest.mark.parametrize(
        "name, scenario",
        [pytest.param(name, scenario, id=name) for name, scenario in STAFF_ACTION_SCENARIOS],
    )
    def test_action_writes_one_record_and_one_row(self, actors, name, scenario):
        before = AuditLog.objects.count()

        expected = scenario(actors)

        delta = AuditLog.objects.count() - before
        assert delta == 1, f"«{name}»: записей {delta}, ожидалась одна"
        entry = AuditLog.objects.latest("pk")
        assert (entry.action, entry.user_id, entry.resource_type, entry.resource_id) == (
            expected.action,
            expected.author.pk,
            expected.resource_type,
            str(expected.resource_id),
        ), f"«{name}»: запись не та"

        page = journal_page(actors.as_supervisor.get(JOURNAL_URL))
        assert [row[1:] for row in page.rows] == [expected.row], f"«{name}»: строка ленты не та"
        assert page.links == [[expected.link] if expected.link else []], f"«{name}»: ссылка не та"

    def test_verify_page_with_1c_candidate_writes_two_kinds(self, actors):
        applicant = make_client(
            actors.manager, role="wholesale_level1", verification_status="pending", is_verified=False, is_active=False
        )
        source = make_1c_record(applicant.tax_id)
        before = AuditLog.objects.count()

        response = actors.as_manager.post(
            verify_url(applicant),
            {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}", "role": "wholesale_level1"},
        )

        assert response.status_code == 302
        assert AuditLog.objects.count() - before == 2
        actions = sorted(AuditLog.objects.filter(resource_id=str(applicant.pk)).values_list("action", flat=True))
        assert actions == ["link_1c_customer", "verify_b2b"]
        page = journal_page(actors.as_supervisor.get(JOURNAL_URL))
        applicant.refresh_from_db()
        assert sorted(row[1:] for row in page.rows) == [
            (label(actors.manager), "Подтверждение B2B-заявки", label(applicant), "с привязкой к 1С"),
            (label(actors.manager), "Привязка к контрагенту 1С", label(applicant), "—"),
        ]


# --------------------------------------------------------------------------
# AC3 — вид строки, ссылки, отсутствие технических полей
# --------------------------------------------------------------------------


class TestRows:
    def test_rows_links_and_no_technical_fields(self, supervisor_client, supervisor, manager, other_manager):
        customer = make_client(manager)
        own = make_master(make_client(manager))
        region_rule = rule("23", manager)
        member = make_staff_member(MARKETING_GROUP, first_name="Мария", last_name="Маркетова")
        ghost = make_client(manager)
        ghost_pk, ghost_email = ghost.pk, ghost.email
        gone_rule = rule("61", manager)
        gone_rule_text = str(gone_rule)

        at = moscow(12, 23, 59)
        log(manager, "block_user", customer, at=at)
        log(
            manager,
            "update_order",
            own,
            {
                "order_number": own.order_number,
                "fields": {"delivery_date": {"old": "2026-10-20", "new": "2026-10-25"}},
            },
            at=at - timedelta(minutes=1),
        )
        log(
            supervisor,
            "change_routing_rule",
            region_rule,
            {
                "operation": "update",
                "rule": str(region_rule),
                "fields": {"manager_id": {"old": manager.pk, "new": other_manager.pk}},
            },
            at=at - timedelta(minutes=2),
        )
        log(
            supervisor,
            "block_staff",
            member,
            {"email": member.email, "group": "Маркетинг"},
            at=at - timedelta(minutes=3),
        )
        log(manager, "unblock_user", ghost, at=at - timedelta(minutes=4))
        ghost.delete()
        log(
            supervisor,
            "change_routing_rule",
            gone_rule,
            {"operation": "delete", "rule": gone_rule_text, "fields": {"is_active": {"old": True, "new": None}}},
            at=at - timedelta(minutes=5),
        )
        gone_rule.delete()

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)
        page = journal_page(response)

        assert page.rows == [
            ("12.10.2026 23:59", label(manager), "Блокировка клиента", label(customer), "—"),
            (
                "12.10.2026 23:58",
                label(manager),
                "Изменение заказа",
                f"Заказ {ui_number(own)}",
                "дата доставки: 20.10.2026 → 25.10.2026",
            ),
            (
                "12.10.2026 23:57",
                label(supervisor),
                "Изменение правила региона",
                f"Код субъекта РФ (по ИНН):23 → {manager.email}",
                f"менеджер: {label(manager)} → {label(other_manager)}",
            ),
            ("12.10.2026 23:56", label(supervisor), "Блокировка сотрудника", label(member), "группа: Маркетинг"),
            ("12.10.2026 23:55", label(manager), "Разблокировка клиента", ghost_email, "—"),
            ("12.10.2026 23:54", label(supervisor), "Удаление правила региона", gone_rule_text, "активно: да → —"),
        ]
        assert page.links == [
            [f"/manager/users/user/{customer.pk}/change/"],
            [f"/manager/orders/order/{own.pk}/change/"],
            [f"/supervisor/common/managerroutingrule/{region_rule.pk}/change/"],
            [f"/supervisor/users/user/{member.pk}/change/"],
            [],
            [],
        ]
        assert f"ID {ghost_pk}" not in response.content.decode()
        html = response.content.decode()
        for forbidden in (TECH_IP, TECH_AGENT, "role_before", '"fields"', "&quot;fields&quot;", '{"', "{&quot;"):
            assert forbidden not in html, forbidden
        assert 'href="/admin/' not in html

    def test_deleted_client_is_labelled_by_target_email(self, supervisor_client, manager):
        # Запись привязки к 1С хранит почту клиента в `target_email`, а не в `email`.
        ghost = make_client(manager)
        ghost_pk, ghost_email = ghost.pk, ghost.email
        log(
            manager,
            "link_1c_customer",
            ghost,
            {"target_id": ghost_pk, "target_email": ghost_email},
            at=moscow(12, 10, 0),
        )
        ghost.delete()

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)
        page = journal_page(response)

        assert page.rows == [
            ("12.10.2026 10:00", label(manager), "Привязка к контрагенту 1С", ghost_email, "—"),
        ]
        assert page.links == [[]]
        assert f"ID {ghost_pk}" not in response.content.decode()

    def test_staff_has_no_manager_link(self, supervisor_client, supervisor):
        member = make_staff_member(MANAGERS_GROUP)
        log(supervisor, "change_password", member)

        page = journal_page(supervisor_client.get(JOURNAL_URL, ALL_TIME))

        assert page.links == [[f"/supervisor/users/user/{member.pk}/change/"]]

    def test_superuser_and_admin_role_objects_have_no_link(self, supervisor_client, manager):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        robot = User.objects.create_user(email=f"1c_{get_unique_suffix()}@example.com", password=PASSWORD, role="admin")
        log(manager, "block_user", superuser)
        log(manager, "block_user", robot)

        page = journal_page(supervisor_client.get(JOURNAL_URL, ALL_TIME))

        assert page.links == [[], []]

    def test_order_not_visible_in_manager_has_no_link(self, supervisor_client, manager):
        # Клиента перевели в сотрудники: его заказов нет в /manager/, ссылка вела бы на 404.
        converted = make_client(manager)
        hidden = make_master(converted, subs=0)
        User.objects.filter(pk=converted.pk).update(is_staff=True)
        # Заказ без клиента руководитель в /manager/ видит (наследие order_export).
        orphan = make_master(None, subs=0)
        for index, order in enumerate((hidden, orphan)):
            log(manager, "update_order", order, {"order_number": order.order_number}, at=moscow(12, 10, 2 - index))

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)
        page = journal_page(response)

        assert [row[3] for row in page.rows] == [f"Заказ {ui_number(hidden)}", f"Заказ {ui_number(orphan)}"]
        assert page.links == [[], [f"/manager/orders/order/{orphan.pk}/change/"]]

    @pytest.mark.parametrize("resource_id", ["²", "abc", "-1", "١٢", "9" * 30])
    def test_unusual_resource_ids_do_not_break_page(self, supervisor_client, manager, resource_id):
        for index, resource_type in enumerate(("User", "Order", "ManagerRoutingRule")):
            entry = AuditLog.log_action(
                user=manager,
                action="block_user",
                resource_type=resource_type,
                resource_id=resource_id,
                changes={"email": "gone@example.com"},
            )
            AuditLog.objects.filter(pk=entry.pk).update(created_at=moscow(12, 10, 3 - index))

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)
        page = journal_page(response)

        assert [row[3] for row in page.rows] == [
            "gone@example.com",
            f"Заказ ID {resource_id}",
            f"ID {resource_id}",
        ]
        assert page.links == [[], [], []]

    def test_responsible_assignment_labels(self, supervisor_client, supervisor, manager, other_manager):
        customer = make_client(other_manager)
        log(
            supervisor,
            "assign_responsible_manager",
            customer,
            {"old": manager.email, "new": other_manager.email, "manual": True},
            at=moscow(12, 10, 3),
        )
        log(
            supervisor,
            "assign_responsible_manager",
            customer,
            {"old": "gone@example.com", "new": other_manager.email, "manual": True},
            at=moscow(12, 10, 2),
        )
        log(
            supervisor,
            "assign_responsible_manager",
            customer,
            {"old": None, "new": other_manager.email, "manual": False},
            at=moscow(12, 10, 1),
        )

        page = journal_page(supervisor_client.get(JOURNAL_URL, ALL_TIME))

        assert [row[4] for row in page.rows] == [
            f"{label(manager)} → {label(other_manager)}",
            f"gone@example.com → {label(other_manager)}",
            f"— → {label(other_manager)}; по правилу региона",
        ]

    def test_user_data_is_escaped(self, supervisor_client, supervisor):
        tricky = make_staff_member(MANAGERS_GROUP, first_name="<b>X</b>", last_name="Тегов")
        tagged_rule = ManagerRoutingRule.objects.create(
            match_type=ManagerRoutingRule.MATCH_INN_REGION, match_value="23", manager_email="<b>Y</b>@example.com"
        )
        order = make_master(make_client(tricky))
        log(tricky, "block_user", make_client(tricky))
        log(supervisor, "change_routing_rule", tagged_rule, {"operation": "update", "rule": str(tagged_rule)})
        # Подробности — отдельная ячейка: `|safe` только на ней не должен пройти (R42.9-12).
        log(
            supervisor,
            "update_order",
            order,
            {
                "order_number": order.order_number,
                "fields": {"tracking_number": {"old": None, "new": "<i>RR1</i>"}},
            },
        )

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)
        html = response.content.decode()

        assert "<b>X</b>" not in html
        assert "<b>Y</b>" not in html
        assert "<i>RR1</i>" not in html
        assert "&lt;b&gt;X&lt;/b&gt; Тегов" in html
        assert "&lt;b&gt;Y&lt;/b&gt;@example.com" in html
        assert "трек-номер: — → &lt;i&gt;RR1&lt;/i&gt;" in html
        # Парсер возвращает текст ячейки уже без экранирования: значение целое, тег не стал разметкой.
        assert "трек-номер: — → <i>RR1</i>" in [row[4] for row in journal_page(response).rows]


# --------------------------------------------------------------------------
# AC4 — фильтры по сотруднику и периоду
# --------------------------------------------------------------------------


@pytest.fixture
def period_records(today, supervisor):
    a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Аверина")
    b = make_staff_member(MANAGERS_GROUP, first_name="Борис", last_name="Борисов")
    records = SimpleNamespace(
        a=a,
        b=b,
        a_late=log(a, "block_user", make_client(a), at=moscow(12, 23, 59)),
        b_midnight=log(b, "block_user", make_client(b), at=moscow(13, 0, 0)),
        chief_utc=log(supervisor, "block_staff", b, at=datetime(2026, 10, 9, 21, 30, tzinfo=UTC)),
        a_after=log(a, "unblock_user", make_client(a), at=moscow(15, 12, 0)),
    )
    return records


class TestFilters:
    def test_staff(self, as_supervisor, period_records):
        r = period_records
        response = as_supervisor.get(JOURNAL_URL, {"staff": r.a.pk, **ALL_TIME})
        assert listed(response) == [r.a_after.pk, r.a_late.pk]

    @pytest.mark.parametrize(
        "role",
        [
            pytest.param({}, id="active"),
            pytest.param({"is_active": False}, id="blocked"),
            pytest.param({"group": None, "is_staff": False}, id="former"),
            pytest.param({"group": None, "is_staff": False, "is_active": False}, id="former-blocked"),
        ],
    )
    def test_staff_choice_of_any_author(self, as_supervisor, period_records, role):
        # Выбранный автор остаётся автором записей при любом сочетании признаков:
        # отбор по текущему `is_staff` или группе скрыл бы бывшего сотрудника (R42.9-11).
        group = role.get("group", MANAGERS_GROUP)
        author = make_staff_member(group, **{key: value for key, value in role.items() if key != "group"})
        mine = log(author, "block_user", make_client(None), at=moscow(14, 10, 0))
        log(period_records.a, "block_user", make_client(None), at=moscow(14, 11, 0))

        response = as_supervisor.get(JOURNAL_URL, {"staff": author.pk, **ALL_TIME})

        assert response.context["filter_form"].is_valid()
        assert listed(response) == [mine.pk]
        assert [row[1] for row in journal_page(response).rows] == [label(author)]

    def test_period_bounds(self, as_supervisor, period_records):
        r = period_records
        # Последняя микросекунда выбранного дня тоже входит: граница на 23:59:00
        # скрыла бы её (R42.9-14). Полночь следующего дня (`b_midnight`) по-прежнему вне периода.
        last_microsecond = log(
            r.a,
            "unblock_user",
            make_client(r.a),
            at=moscow(12, 23, 59).replace(second=59, microsecond=999999),
        )
        response = as_supervisor.get(JOURNAL_URL, {"date_from": "2026-10-10", "date_to": "2026-10-12"})
        assert listed(response) == [last_microsecond.pk, r.a_late.pk, r.chief_utc.pk]
        assert response.context["period_label"] == "Период: 10.10.2026 — 12.10.2026"

    def test_filter_form_submits_by_get(self, as_supervisor, period_records):
        # Кнопка «Показать» работает, пока форма отправляется GET: обработчик читает только
        # `request.GET`, а `method="post"` молча сломал бы фильтр (R42.9-15).
        r = period_records
        form = filter_form_of(as_supervisor.get(JOURNAL_URL))

        assert (form.method or "get").lower() == "get"
        assert sorted(form.names) == ["date_from", "date_to", "staff"]
        assert str(r.a.pk) in form.options["staff"]

        chosen = {"staff": str(r.a.pk), "date_from": "2026-10-10", "date_to": "2026-10-12"}
        response = as_supervisor.get(form.action or JOURNAL_URL, {name: chosen[name] for name in form.names})

        assert listed(response) == [r.a_late.pk]
        assert [row[1] for row in journal_page(response).rows] == [label(r.a)]

    def test_one_sided(self, as_supervisor, period_records):
        r = period_records
        response = as_supervisor.get(JOURNAL_URL, {"date_from": "2026-10-13"})
        assert listed(response) == [r.a_after.pk, r.b_midnight.pk]
        assert response.context["period_label"] == "Период: с 13.10.2026"
        response = as_supervisor.get(JOURNAL_URL, {"date_to": "2026-10-12"})
        assert listed(response) == [r.a_late.pk, r.chief_utc.pk]
        assert response.context["period_label"] == "Период: по 12.10.2026"

    def test_staff_and_period(self, as_supervisor, period_records):
        r = period_records
        response = as_supervisor.get(JOURNAL_URL, {"staff": r.a.pk, "date_from": "2026-10-10", "date_to": "2026-10-12"})
        assert listed(response) == [r.a_late.pk]

    def test_staff_choices(self, as_supervisor, supervisor, period_records):
        r = period_records
        blocked = make_staff_member(MANAGERS_GROUP, first_name="Вера", last_name="Веткина", is_active=False)
        former = make_staff_member(None, first_name="Глеб", last_name="Глебов", is_staff=False)
        log(former, "block_user", make_client(None))
        former_blocked = make_staff_member(None, first_name="Дина", last_name="Дымова", is_staff=False, is_active=False)
        log(former_blocked, "approve_b2b", make_client(None))
        make_client(None, first_name="Клиент", last_name="Беззаписей")
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        log(superuser, "block_user", make_client(None))

        form = as_supervisor.get(JOURNAL_URL).context["filter_form"]

        assert [(str(value), text) for value, text in form.fields["staff"].choices] == [
            ("", "Все сотрудники"),
            (str(r.a.pk), label(r.a)),
            (str(r.b.pk), label(r.b)),
            (str(blocked.pk), f"{label(blocked)} — заблокирован"),
            (str(former.pk), f"{label(former)} — бывший сотрудник"),
            (str(former_blocked.pk), f"{label(former_blocked)} — бывший сотрудник — заблокирован"),
            (str(supervisor.pk), label(supervisor)),
        ]

    def test_period_links_keep_staff_and_mark_selected(self, as_supervisor, period_records):
        a = period_records.a.pk
        response = as_supervisor.get(JOURNAL_URL, {"staff": a, "date_from": "2026-10-11", "date_to": "2026-10-17"})

        assert [(link["name"], link["url"], link["selected"]) for link in response.context["period_links"]] == [
            ("Всё время", f"?staff={a}&date_from=&date_to=", False),
            ("Сегодня", f"?staff={a}&date_from=2026-10-17&date_to=2026-10-17", False),
            ("7 дней", f"?staff={a}&date_from=2026-10-11&date_to=2026-10-17", True),
            ("30 дней", f"?staff={a}&date_from=2026-09-18&date_to=2026-10-17", False),
            ("Этот месяц", f"?staff={a}&date_from=2026-10-01&date_to=2026-10-17", False),
            ("Прошлый месяц", f"?staff={a}&date_from=2026-09-01&date_to=2026-09-30", False),
        ]
        html = response.content.decode()
        assert (
            f'<strong><a href="?staff={a}&amp;date_from=2026-10-11&amp;date_to=2026-10-17">7 дней</a></strong>' in html
        )
        assert html.count("<strong><a") == 1

    def test_quick_periods_follow_project_timezone(self, as_supervisor, period_records):
        # 00:30 17.10.2026 по Москве — ещё 16.10 по UTC. Ссылки и умолчание обязаны
        # считать «сегодня» по поясу проекта, а не по UTC (R42.9-13).
        night = datetime(2026, 10, 16, 21, 30, tzinfo=UTC)
        with patch("django.utils.timezone.now", return_value=night):
            response = as_supervisor.get(JOURNAL_URL)

        links = {link["name"]: link for link in response.context["period_links"]}
        assert links["Сегодня"]["url"] == "?date_from=2026-10-17&date_to=2026-10-17"
        assert links["7 дней"]["url"] == "?date_from=2026-10-11&date_to=2026-10-17"
        assert links["30 дней"]["url"] == "?date_from=2026-09-18&date_to=2026-10-17"
        assert [name for name, link in links.items() if link["selected"]] == ["30 дней"]
        assert response.context["period_label"] == "Период: 18.09.2026 — 17.10.2026"

    def test_links_without_staff(self, as_supervisor, period_records):
        response = as_supervisor.get(JOURNAL_URL, ALL_TIME)
        assert [(link["url"], link["selected"]) for link in response.context["period_links"][:2]] == [
            ("?date_from=&date_to=", True),
            ("?date_from=2026-10-17&date_to=2026-10-17", False),
        ]


@pytest.fixture
def default_edge(today, manager):
    return SimpleNamespace(
        old=log(manager, "block_user", make_client(manager), at=moscow(17, 23, 59, month=9)),
        edge=log(manager, "unblock_user", make_client(manager), at=moscow(18, 0, 0, month=9)),
    )


class TestDefaultPeriod:
    def assert_last_30_days(self, response, edge) -> None:
        assert listed(response) == [edge.edge.pk]
        form = response.context["filter_form"]
        assert (form["date_from"].value(), form["date_to"].value()) == ("2026-09-18", "2026-10-17")
        html = response.content.decode()
        assert 'value="2026-09-18"' in html
        assert 'value="2026-10-17"' in html
        assert [link["name"] for link in response.context["period_links"] if link["selected"]] == ["30 дней"]
        assert '<p id="journal-period-label">Период: 18.09.2026 — 17.10.2026</p>' in html

    def test_without_params(self, as_supervisor, default_edge):
        self.assert_last_30_days(as_supervisor.get(JOURNAL_URL), default_edge)

    def test_only_staff(self, as_supervisor, manager, default_edge):
        self.assert_last_30_days(as_supervisor.get(JOURNAL_URL, {"staff": manager.pk}), default_edge)

    def test_all_time(self, as_supervisor, default_edge):
        response = as_supervisor.get(JOURNAL_URL, ALL_TIME)

        assert listed(response) == [default_edge.edge.pk, default_edge.old.pk]
        assert [link["name"] for link in response.context["period_links"] if link["selected"]] == ["Всё время"]
        assert '<p id="journal-period-label">Период: всё время</p>' in response.content.decode()


class TestInvalidFilter:
    @pytest.mark.parametrize(
        "params, error",
        [
            pytest.param(
                {"date_from": "2026-10-13", "date_to": "2026-10-12"}, "Начало периода позже его конца.", id="reversed"
            ),
            pytest.param(
                {"date_from": "2026-10-13", "date_to": "9999-12-31"},
                "Конец периода вне допустимого диапазона.",
                id="date-max",
            ),
            pytest.param({"staff": "999999999"}, "Выберите корректный вариант.", id="missing-staff"),
            pytest.param({"staff": "abc"}, "Выберите корректный вариант.", id="non-numeric-staff"),
        ],
    )
    def test_error_and_no_rows(self, as_supervisor, manager, params, error):
        log(manager, "block_user", make_client(manager))

        response = as_supervisor.get(JOURNAL_URL, params)

        assert response.status_code == 200
        html = response.content.decode()
        assert INVALID_FILTER in html
        assert error in html
        assert response.context["rows"] == []
        assert 'class="journal-row"' not in html

    @pytest.mark.parametrize(
        "dates",
        [
            pytest.param({"date_from": "2026-10-12", "date_to": "2026-10-10"}, id="reversed"),
            pytest.param({"date_from": "2026-10-13", "date_to": "9999-12-31"}, id="date-max"),
        ],
    )
    def test_period_links_keep_staff(self, today, as_supervisor, manager, dates):
        a = manager.pk

        response = as_supervisor.get(JOURNAL_URL, {"staff": a, **dates})

        assert INVALID_FILTER in response.content.decode()
        assert [(link["name"], link["url"], link["selected"]) for link in response.context["period_links"]] == [
            ("Всё время", f"?staff={a}&date_from=&date_to=", False),
            ("Сегодня", f"?staff={a}&date_from=2026-10-17&date_to=2026-10-17", False),
            ("7 дней", f"?staff={a}&date_from=2026-10-11&date_to=2026-10-17", False),
            ("30 дней", f"?staff={a}&date_from=2026-09-18&date_to=2026-10-17", False),
            ("Этот месяц", f"?staff={a}&date_from=2026-10-01&date_to=2026-10-17", False),
            ("Прошлый месяц", f"?staff={a}&date_from=2026-09-01&date_to=2026-09-30", False),
        ]

    def test_period_links_drop_invalid_staff(self, today, as_supervisor):
        response = as_supervisor.get(JOURNAL_URL, {"staff": "abc"})

        assert INVALID_FILTER in response.content.decode()
        assert [link["url"] for link in response.context["period_links"]][:2] == [
            "?date_from=&date_to=",
            "?date_from=2026-10-17&date_to=2026-10-17",
        ]


# --------------------------------------------------------------------------
# AC5 — только действия сотрудников трёх ролей
# --------------------------------------------------------------------------


class TestOnlyStaffActions:
    def test_service_superuser_and_unknown_codes_are_hidden(self, supervisor_client, manager):
        customer = make_client(manager)
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        log(None, "role_from_1c", customer)
        log(superuser, "block_user", customer)
        log(manager, "sync_customer", customer)

        blocked = make_staff_member(MANAGERS_GROUP, is_active=False)
        ungrouped = make_staff_member(MANAGERS_GROUP)
        ungrouped.groups.clear()
        former = make_staff_member(MANAGERS_GROUP, is_staff=False)
        # Обычный бывший сотрудник: у него нет ни `is_staff`, ни группы. Отбор
        # «текущий is_staff ИЛИ есть группа» скрыл бы его записи (R42.9-10).
        former_plain = make_staff_member(None, is_staff=False)
        visible = {
            log(blocked, "block_user", customer).pk,
            log(ungrouped, "unblock_user", customer).pk,
            log(former, "change_password", customer).pk,
            log(former_plain, "approve_b2b", customer).pk,
        }

        response = supervisor_client.get(JOURNAL_URL, ALL_TIME)

        assert set(listed(response)) == visible
        assert sorted(row[1] for row in journal_page(response).rows) == sorted(
            [label(blocked), label(ungrouped), label(former), label(former_plain)]
        )


# --------------------------------------------------------------------------
# AC6 — порядок и страницы
# --------------------------------------------------------------------------


class TestPages:
    def make_records(self, author: User, count: int) -> list[int]:
        target = make_client(author)
        ids = [log(author, "block_user", target).pk for _ in range(count)]
        same_second = moscow(15, 12, 0)
        AuditLog.objects.filter(pk__in=ids).update(created_at=same_second)
        # Самая старая по pk — самая новая по времени: время важнее pk.
        AuditLog.objects.filter(pk=ids[0]).update(created_at=same_second + timedelta(minutes=1))
        return ids

    def test_order_and_pages(self, today, as_supervisor, manager):
        ids = self.make_records(manager, 230)
        newest_first = [ids[0], *reversed(ids[1:])]

        response = as_supervisor.get(JOURNAL_URL)
        html = response.content.decode()
        assert listed(response) == newest_first[:100]
        assert len(journal_page(response).rows) == 100
        assert '<p id="journal-count">Записей: 230</p>' in html
        assert "Страница 1 из 3" in html
        assert "← Новее" not in html
        # Периода в адресе нет — в ссылке он стоит явно.
        assert '<a href="?date_from=2026-09-18&amp;date_to=2026-10-17&amp;page=2">Старее →</a>' in html

        response = as_supervisor.get(JOURNAL_URL, {"date_from": "2026-09-18", "date_to": "2026-10-17", "page": 2})
        html = response.content.decode()
        assert listed(response) == newest_first[100:200]
        assert "Страница 2 из 3" in html
        assert '<a href="?date_from=2026-09-18&amp;date_to=2026-10-17&amp;page=1">← Новее</a>' in html
        assert '<a href="?date_from=2026-09-18&amp;date_to=2026-10-17&amp;page=3">Старее →</a>' in html

        response = as_supervisor.get(JOURNAL_URL, {"page": 99})
        assert listed(response) == newest_first[200:]
        assert "Страница 3 из 3" in response.content.decode()

    def test_links_keep_staff_and_dates(self, today, as_supervisor, manager):
        self.make_records(manager, 120)

        html = as_supervisor.get(
            JOURNAL_URL, {"staff": manager.pk, "date_from": "2026-10-01", "date_to": "2026-10-17"}
        ).content.decode()

        assert (
            f'<a href="?staff={manager.pk}&amp;date_from=2026-10-01&amp;date_to=2026-10-17&amp;page=2">Старее →</a>'
            in html
        )

    def test_empty(self, as_supervisor):
        html = as_supervisor.get(JOURNAL_URL).content.decode()
        assert '<p id="journal-count">Записей нет</p>' in html


# --------------------------------------------------------------------------
# AC7 — число запросов (NFR-42-04)
# --------------------------------------------------------------------------


class TestQueryCount:
    SPREAD = 4
    KINDS = 6

    @pytest.fixture
    def objects(self, manager) -> SimpleNamespace:
        ghosts = []
        for number in range(self.SPREAD):
            ghost = make_client(manager)
            ghosts.append(SimpleNamespace(pk=ghost.pk, email=f"ghost{number}@example.com"))
            ghost.delete()
        return SimpleNamespace(
            customers=[make_client(manager) for _ in range(self.SPREAD)],
            managers=[make_staff_member(MANAGERS_GROUP) for _ in range(self.SPREAD)],
            members=[make_staff_member(MARKETING_GROUP) for _ in range(self.SPREAD)],
            orders=[make_master(make_client(manager), subs=0) for _ in range(self.SPREAD)],
            rules=[rule(str(23 + number), manager) for number in range(self.SPREAD)],
            ghosts=ghosts,
        )

    @staticmethod
    def add(objects: SimpleNamespace, authors: list[User], count: int, spread: int) -> None:
        """
        Записи шести видов по кругу. Объектов каждого вида — `spread`: число запросов
        не должно расти и с числом строк, и с числом различных клиентов, заказов и правил.
        """
        for index in range(count):
            author = authors[index % len(authors)]
            kind = index % TestQueryCount.KINDS
            variant = (index // TestQueryCount.KINDS) % spread
            if kind == 0:
                log(author, "block_user", objects.customers[variant])
            elif kind == 1:
                log(author, "block_staff", objects.members[variant], {"group": "Маркетинг"})
            elif kind == 2:
                order = objects.orders[variant]
                log(author, "update_order", order, {"order_number": order.order_number})
            elif kind == 3:
                region_rule = objects.rules[variant]
                # Пара менеджеров своя у каждого варианта: запрос на каждый уникальный
                # `manager_id` (даже с кешем на страницу) растил бы число запросов.
                log(
                    author,
                    "change_routing_rule",
                    region_rule,
                    {
                        "operation": "update",
                        "rule": str(region_rule),
                        "fields": {
                            "manager_id": {
                                "old": objects.managers[variant].pk,
                                "new": objects.managers[(variant + 1) % len(objects.managers)].pk,
                            }
                        },
                    },
                )
            elif kind == 4:
                log(author, "unblock_user", objects.ghosts[variant], resource_type="User")
            else:
                # Прежний и новый менеджер — разные учётные записи на каждой строке;
                # у нечётных вариантов прежней почты в базе нет.
                old = objects.managers[variant].email if variant % 2 == 0 else f"former{variant}@example.com"
                new = objects.managers[(variant + 1) % len(objects.managers)].email
                log(
                    author,
                    "assign_responsible_manager",
                    objects.customers[variant],
                    {"old": old, "new": new, "manual": True},
                )

    @pytest.mark.parametrize("filtered", [False, True], ids=["all", "staff-and-period"])
    def test_constant(self, today, as_supervisor, objects, filtered, django_assert_num_queries):
        first = make_staff_member(MANAGERS_GROUP)
        self.add(objects, [first], self.KINDS, spread=1)
        query = f"?staff={first.pk}&date_from=2026-10-01&date_to=2026-10-17" if filtered else "?date_from=&date_to="
        baseline, response = count_queries(as_supervisor, JOURNAL_URL + query)
        assert len(response.context["rows"]) == self.KINDS

        team = [first, *(make_staff_member(MANAGERS_GROUP) for _ in range(19))]
        # С фильтром по сотруднику его записей должно хватить на две страницы.
        self.add(objects, [first] if filtered else team, 195, spread=self.SPREAD)

        with django_assert_num_queries(baseline):
            response = as_supervisor.get(JOURNAL_URL + query)
        assert len(response.context["rows"]) == 100
        assert len({row["object_label"] for row in response.context["rows"]}) > self.KINDS
        assert len({row["details"] for row in response.context["rows"] if "→" in row["details"]}) > 2
        with django_assert_num_queries(baseline):
            response = as_supervisor.get(JOURNAL_URL + query + "&page=2")
        assert len(response.context["rows"]) == 100


# --------------------------------------------------------------------------
# AC8 — главная и ссылки раздела
# --------------------------------------------------------------------------


class TestLinks:
    def test_journal_is_current_section(self, supervisor_client):
        html = supervisor_client.get(JOURNAL_URL).content.decode()
        block = html[html.index('id="supervisor-sections"') : html.index("</table>", html.index("supervisor-sections"))]

        assert re.findall(r'<a href="([^"]+)"( aria-current="page")?>([^<]+)</a>', block) == [
            ("/supervisor/", "", "Сводка"),
            ("/supervisor/journal/", ' aria-current="page"', "Журнал действий"),
            ("/manager/", "", "Клиенты и заказы"),
            ("/marketing/", "", "Маркетинг"),
        ]
        assert '<tr class="current-model">' in block

    def test_journal_links_stay_in_sections(self, supervisor_client, supervisor, manager):
        customer = make_client(manager)
        own = make_master(make_client(manager), subs=0)
        region_rule = rule("23", manager)
        member = make_staff_member(MARKETING_GROUP)
        log(manager, "block_user", customer)
        log(manager, "update_order", own, {"order_number": own.order_number})
        log(supervisor, "change_routing_rule", region_rule, {"operation": "update", "rule": str(region_rule)})
        log(supervisor, "block_staff", member)

        html = supervisor_client.get(JOURNAL_URL, {"staff": manager.pk, **ALL_TIME}).content.decode()
        assert 'href="/admin/' not in html
        html = supervisor_client.get(JOURNAL_URL, ALL_TIME).content.decode()
        assert 'href="/admin/' not in html
        assert re.search(r'<div class="breadcrumbs">\s*<a href="/supervisor/">', html)
        assert 'href="/supervisor/password_change/"' in html
        assert 'action="/supervisor/logout/"' in html


# --------------------------------------------------------------------------
# AC9 — сброс пароля и журнал атомарны (R42.7-D2)
# --------------------------------------------------------------------------


def password_request(author: User, url: str) -> Any:
    """
    POST формы пароля для прямого вызова метода админки: тестовый клиент
    обернул бы запрос в транзакцию `ATOMIC_REQUESTS` настроек тестов.
    """
    request = RequestFactory().post(
        url, {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}
    )
    request.user = author
    # Django после смены пароля обновляет ключ сессии (update_session_auth_hash).
    request.session = SessionStore()
    request._messages = CookieStorage(request)
    # У user_change_password есть csrf_protect_m.
    request._dont_enforce_csrf_checks = True
    return request


class TestPasswordAtomic:
    @pytest.fixture(params=["supervisor", "manager"])
    def case(self, request, supervisor, manager) -> SimpleNamespace:
        if request.param == "supervisor":
            target = make_staff_member(MANAGERS_GROUP)
            return SimpleNamespace(
                author=supervisor,
                target=target,
                model_admin=supervisor_site._registry[User],
                url=staff_password_url(target),
            )
        target = make_client(manager)
        return SimpleNamespace(
            author=manager, target=target, model_admin=manager_site._registry[User], url=password_url(target)
        )

    def test_failed_journal_keeps_password(self, case):
        with failing_journal(), pytest.raises(RuntimeError, match="журнал недоступен"):
            case.model_admin.user_change_password(password_request(case.author, case.url), str(case.target.pk))

        case.target.refresh_from_db()
        assert case.target.check_password(PASSWORD)
        assert not AuditLog.objects.filter(action="change_password").exists()

    def test_success_writes_one_record(self, case):
        response = case.model_admin.user_change_password(password_request(case.author, case.url), str(case.target.pk))

        assert response.status_code == 302
        case.target.refresh_from_db()
        assert case.target.check_password(NEW_PASSWORD)
        (entry,) = AuditLog.objects.all()
        assert (entry.action, entry.user_id, entry.resource_id) == (
            "change_password",
            case.author.pk,
            str(case.target.pk),
        )


# --------------------------------------------------------------------------
# AC11 — автора записей ленты нельзя удалить
# --------------------------------------------------------------------------


def delete_url(user: User) -> str:
    return reverse("admin:users_user_delete", args=[user.pk])


def delete_selected(browser: Client, *users: User):
    return browser.post(
        reverse("admin:users_user_changelist"),
        {"action": "delete_selected", "_selected_action": [str(user.pk) for user in users], "post": "yes"},
    )


# Литерал, а не `STAFF_ACTIONS`: подмена перечня в охране должна ронять тест (урок R42.5-7).
ALL_CODES = [
    "verify_b2b",
    "approve_b2b",
    "reject_b2b",
    "block_user",
    "unblock_user",
    "change_password",
    "link_1c_customer",
    "update_order",
    "assign_responsible_manager",
    "change_user_role",
    "change_routing_rule",
    "create_staff",
    "block_staff",
    "unblock_staff",
    "change_staff_group",
]


class TestDeleteGuard:
    @pytest.fixture
    def authors(self) -> dict[str, User]:
        customer = make_client(None)
        authors = {
            "manager": make_staff_member(MANAGERS_GROUP),
            "blocked": make_staff_member(MANAGERS_GROUP, is_active=False),
            "former": make_staff_member(None, is_staff=False),
        }
        for author in authors.values():
            log(author, "block_user", customer)
        return authors

    @pytest.mark.parametrize("kind", ["manager", "blocked", "former"])
    def test_author_card_delete_is_refused(self, authors, kind):
        author = authors[kind]
        browser = superuser_client()

        assert DELETE_GUARD_MESSAGE in browser.get(delete_url(author)).content.decode()
        response = browser.post(delete_url(author), {"post": "yes"})

        assert response.status_code == 200
        html = response.content.decode()
        assert DELETE_GUARD_MESSAGE in html
        assert f"Журнал действий сотрудников — записи автора {label(author)}" in html
        assert User.objects.filter(pk=author.pk).exists()
        assert AuditLog.objects.filter(user=author, action="block_user").count() == 1

    @pytest.mark.parametrize("kind", ["manager", "blocked", "former"])
    def test_author_bulk_delete_is_refused(self, authors, kind):
        author = authors[kind]
        clean = make_staff_member(MANAGERS_GROUP)

        response = delete_selected(superuser_client(), author, clean)

        assert response.status_code == 200
        assert DELETE_GUARD_MESSAGE in response.content.decode()
        assert User.objects.filter(pk__in=[author.pk, clean.pk]).count() == 2
        assert AuditLog.objects.filter(user=author).count() == 1

    @pytest.mark.parametrize("code", ALL_CODES)
    def test_author_of_any_listed_action_card_delete_is_refused(self, code):
        author = make_staff_member(MANAGERS_GROUP)
        log(author, code, make_client(None))
        browser = superuser_client()

        response = browser.post(delete_url(author), {"post": "yes"})

        assert response.status_code == 200
        assert DELETE_GUARD_MESSAGE in response.content.decode()
        assert User.objects.filter(pk=author.pk).exists()
        assert AuditLog.objects.filter(user=author, action=code).count() == 1

    @pytest.mark.parametrize("code", ALL_CODES)
    def test_author_of_any_listed_action_bulk_delete_is_refused(self, code):
        author = make_staff_member(MANAGERS_GROUP)
        clean = make_staff_member(MARKETING_GROUP)
        log(author, code, make_client(None))

        response = delete_selected(superuser_client(), author, clean)

        assert response.status_code == 200
        assert DELETE_GUARD_MESSAGE in response.content.decode()
        assert User.objects.filter(pk__in=[author.pk, clean.pk]).count() == 2
        assert AuditLog.objects.filter(user=author, action=code).count() == 1

    def test_authors_query_has_no_ordering_and_no_duplicates(self):
        # `AuditLog.Meta.ordering = ["-created_at"]` попал бы в `SELECT DISTINCT`
        # и вернул бы автора по разу на каждую запись (R42.9-9).
        author = make_staff_member(MANAGERS_GROUP)
        customer = make_client(None)
        for number, code in enumerate(["block_user", "unblock_user", "change_password"]):
            record = log(author, code, customer)
            AuditLog.objects.filter(pk=record.pk).update(created_at=moscow(10 + number, 12, 0))

        with CaptureQueriesContext(connection) as queries:
            response = superuser_client().get(delete_url(author))

        assert DELETE_GUARD_MESSAGE in response.content.decode()
        authors_sql = [
            query["sql"]
            for query in queries.captured_queries
            if "DISTINCT" in query["sql"] and 'FROM "common_auditlog"' in query["sql"]
        ]
        assert len(authors_sql) == 1
        assert "ORDER BY" not in authors_sql[0]
        with connection.cursor() as cursor:
            cursor.execute(authors_sql[0])
            assert [row[0] for row in cursor.fetchall()] == [author.pk]

    def test_without_journal_records_is_deleted(self):
        clean = make_staff_member(MANAGERS_GROUP)
        log(clean, "sync_customer", make_client(None))
        browser = superuser_client()

        assert DELETE_GUARD_MESSAGE not in browser.get(delete_url(clean)).content.decode()
        assert browser.post(delete_url(clean), {"post": "yes"}).status_code == 302
        assert not User.objects.filter(pk=clean.pk).exists()

    def test_superuser_author_is_deleted(self):
        owner = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        log(owner, "block_user", make_client(None))
        browser = superuser_client()

        assert browser.post(delete_url(owner), {"post": "yes"}).status_code == 302
        assert not User.objects.filter(pk=owner.pk).exists()

    def test_bulk_delete_of_clean_accounts_works(self):
        first, second = make_staff_member(MANAGERS_GROUP), make_staff_member(MARKETING_GROUP)

        assert delete_selected(superuser_client(), first, second).status_code == 302
        assert not User.objects.filter(pk__in=[first.pk, second.pk]).exists()

    def test_manager_with_clients_and_records_gets_both_warnings(self):
        author = make_staff_member(MANAGERS_GROUP)
        log(author, "block_user", make_client(author))

        html = superuser_client().get(delete_url(author)).content.decode()

        assert RESPONSIBLE_GUARD_MESSAGE in html
        assert DELETE_GUARD_MESSAGE in html

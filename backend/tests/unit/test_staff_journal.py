"""
Unit-тесты журнала действий сотрудников `/supervisor/journal/` (стори 42.9).

Перечень кодов, формулировки `describe` на каждом коде и на неполных
записях, форма фильтра, период по умолчанию и маршрут страницы. Ожидаемые
подписи и тексты — литералами.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.test import RequestFactory
from django.urls import resolve, reverse

from apps.common.models import AuditLog
from apps.common.staff_actions import STAFF_ACTIONS
from apps.common.staff_journal import DEFAULT_DAYS, PER_PAGE, JournalFilterForm, KnownUsers, describe, journal_filter
from apps.users.models import User

pytestmark = [pytest.mark.unit]

MOSCOW = ZoneInfo("Europe/Moscow")
TODAY_NOON = datetime(2026, 10, 17, 12, 0, tzinfo=MOSCOW)

ANNA = User(pk=101, email="anna@example.com", first_name="Анна", last_name="Менеджерова")
BORIS = User(pk=102, email="boris@example.com", first_name="Борис", last_name="Второй")
USERS = KnownUsers.of([ANNA, BORIS])


def record(action: str, changes: Any = None, **details: Any) -> AuditLog:
    if changes is not None:
        details["changes"] = changes
    return AuditLog(action=action, resource_type="User", resource_id="1", details=details)


def test_staff_actions_are_exactly_the_list():
    assert set(STAFF_ACTIONS) == {
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
    }


def test_page_constants():
    assert PER_PAGE == 100
    assert DEFAULT_DAYS == 30


@pytest.mark.parametrize(
    "action, changes, expected",
    [
        pytest.param(
            "approve_b2b",
            {"email": "c@example.com", "role": "wholesale_level1", "verified": True},
            ("Верификация клиента", "—"),
            id="approve_b2b",
        ),
        pytest.param(
            "verify_b2b",
            {
                "mode": "decision",
                "role_before": "wholesale_level1",
                "role_after": "trainer",
                "role_source": "manager",
                "linked_now": False,
            },
            ("Подтверждение B2B-заявки", "роль: Оптовик уровень 1 → Тренер/Фитнес-клуб"),
            id="verify_b2b-decision-role-changed",
        ),
        pytest.param(
            "verify_b2b",
            {
                "mode": "decision",
                "role_before": "wholesale_level1",
                "role_after": "wholesale_level1",
                "role_source": "manager",
                "linked_now": False,
            },
            ("Подтверждение B2B-заявки", "—"),
            id="verify_b2b-decision-same-role",
        ),
        pytest.param(
            "verify_b2b",
            {
                "mode": "link_only",
                "role_before": "retail",
                "role_after": "wholesale_level2",
                "role_source": "1c_price_type",
                "linked_now": True,
            },
            (
                "Подтверждение роли при привязке к 1С",
                "роль: Розничный покупатель → Оптовик уровень 2; роль по виду цен 1С; с привязкой к 1С",
            ),
            id="verify_b2b-link_only",
        ),
        pytest.param(
            "verify_b2b",
            {"mode": "decision", "role_before": "boss", "role_after": "trainer"},
            ("Подтверждение B2B-заявки", "роль: boss → Тренер/Фитнес-клуб"),
            id="verify_b2b-unknown-role",
        ),
        pytest.param("reject_b2b", {"email": "c@example.com", "verified": False}, ("Отказ в верификации", "—")),
        pytest.param("block_user", {"blocked": True, "source": "card"}, ("Блокировка клиента", "—")),
        pytest.param("unblock_user", {"blocked": False}, ("Разблокировка клиента", "—")),
        pytest.param(
            "change_password",
            {"email": "c@example.com", "usable_password": True},
            ("Сброс пароля", "—"),
            id="change_password-usable",
        ),
        pytest.param(
            "change_password",
            {"email": "c@example.com", "usable_password": False},
            ("Сброс пароля", "вход по паролю отключён"),
            id="change_password-unusable",
        ),
        pytest.param(
            "link_1c_customer",
            {"target_email": "c@example.com", "onec_id": "1C-1", "previous_values": {"tax_id": "1"}},
            ("Привязка к контрагенту 1С", "—"),
        ),
        pytest.param(
            "update_order",
            {
                "order_number": "1234526007",
                "fields": {
                    "delivery_date": {"old": "2026-10-20", "new": "2026-10-25"},
                    "tracking_number": {"old": None, "new": "RR123456789RU"},
                },
            },
            ("Изменение заказа", "трек-номер: — → RR123456789RU; дата доставки: 20.10.2026 → 25.10.2026"),
            id="update_order",
        ),
        pytest.param(
            "update_order",
            {"fields": {"delivery_date": {"old": "2026-10-20", "new": None}}},
            ("Изменение заказа", "дата доставки: 20.10.2026 → —"),
            id="update_order-cleared-date",
        ),
        pytest.param(
            "assign_responsible_manager",
            {"old": "anna@example.com", "new": "boris@example.com", "manual": True},
            (
                "Назначение ответственного менеджера",
                "Анна Менеджерова (anna@example.com) → Борис Второй (boris@example.com)",
            ),
            id="assign-manual",
        ),
        pytest.param(
            "assign_responsible_manager",
            {"old": None, "new": "gone@example.com", "manual": False},
            ("Назначение ответственного менеджера", "— → gone@example.com; по правилу региона"),
            id="assign-by-rule-unknown-email",
        ),
        pytest.param(
            "change_user_role",
            {"email": "c@example.com", "old": "wholesale_level1", "new": "retail", "source": "card"},
            ("Смена роли клиента", "Оптовик уровень 1 → Розничный покупатель"),
            id="change_user_role",
        ),
        pytest.param(
            "change_routing_rule",
            {
                "operation": "create",
                "rule": "Код субъекта РФ (по ИНН):23 → anna@example.com",
                "fields": {
                    "manager_id": {"old": None, "new": 101},
                    "is_active": {"old": None, "new": True},
                    "match_value": {"old": None, "new": "23"},
                    "match_type": {"old": None, "new": "inn_region"},
                },
            },
            (
                "Создание правила региона",
                "тип: — → Код субъекта РФ (по ИНН); значение: — → 23; активно: — → да; "
                "менеджер: — → Анна Менеджерова (anna@example.com)",
            ),
            id="rule-create",
        ),
        pytest.param(
            "change_routing_rule",
            {
                "operation": "update",
                "fields": {
                    "manager_email": {"old": "", "new": "region@example.com"},
                    "manager_id": {"old": 101, "new": 102},
                    "is_active": {"old": True, "new": False},
                },
            },
            (
                "Изменение правила региона",
                "активно: да → нет; менеджер: Анна Менеджерова (anna@example.com) → Борис Второй (boris@example.com); "
                "email менеджера: — → region@example.com",
            ),
            id="rule-update",
        ),
        pytest.param(
            "change_routing_rule",
            {"operation": "delete", "fields": {"manager_id": {"old": 999, "new": None}}},
            ("Удаление правила региона", "менеджер: ID 999 → —"),
            id="rule-delete-unknown-manager",
        ),
        pytest.param(
            "create_staff",
            {"email": "s@example.com", "group": "Менеджеры"},
            ("Создание сотрудника", "группа: Менеджеры"),
        ),
        pytest.param("block_staff", {"group": "Маркетинг"}, ("Блокировка сотрудника", "группа: Маркетинг")),
        pytest.param("unblock_staff", {"group": ""}, ("Разблокировка сотрудника", "—"), id="unblock_staff-no-group"),
        pytest.param(
            "change_staff_group",
            {"old": "Менеджеры", "new": "Маркетинг"},
            ("Смена группы сотрудника", "Менеджеры → Маркетинг"),
        ),
    ],
)
def test_describe(action, changes, expected):
    assert describe(record(action, changes), USERS) == expected


@pytest.mark.parametrize(
    "action, expected",
    [
        ("verify_b2b", ("Подтверждение B2B-заявки", "—")),
        ("approve_b2b", ("Верификация клиента", "—")),
        ("reject_b2b", ("Отказ в верификации", "—")),
        ("block_user", ("Блокировка клиента", "—")),
        ("unblock_user", ("Разблокировка клиента", "—")),
        ("change_password", ("Сброс пароля", "—")),
        ("link_1c_customer", ("Привязка к контрагенту 1С", "—")),
        ("update_order", ("Изменение заказа", "—")),
        ("assign_responsible_manager", ("Назначение ответственного менеджера", "— → —")),
        ("change_user_role", ("Смена роли клиента", "— → —")),
        ("change_routing_rule", ("Изменение правила региона", "—")),
        ("create_staff", ("Создание сотрудника", "группа: —")),
        ("block_staff", ("Блокировка сотрудника", "—")),
        ("unblock_staff", ("Разблокировка сотрудника", "—")),
        ("change_staff_group", ("Смена группы сотрудника", "— → —")),
    ],
)
def test_describe_without_expected_keys(action, expected):
    """Старые записи без ключей: «—», без исключения."""
    assert describe(record(action), USERS) == expected


@pytest.mark.parametrize(
    "details",
    [
        pytest.param({"changes": "строка"}, id="changes-not-dict"),
        pytest.param({"changes": {"fields": ["tracking_number"], "operation": ["create"]}}, id="fields-not-dict"),
        pytest.param({"changes": {"fields": {"match_type": {"old": ["x"], "new": {"y": 1}}}}}, id="unhashable"),
    ],
)
@pytest.mark.parametrize("action", ["update_order", "change_routing_rule", "verify_b2b"])
def test_describe_malformed_details_do_not_raise(action, details):
    label, text = describe(AuditLog(action=action, resource_type="User", resource_id="1", details=details), USERS)
    assert label
    assert text


def test_describe_details_not_dict():
    entry = AuditLog(action="block_staff", resource_type="User", resource_id="1", details=["x"])
    assert describe(entry, USERS) == ("Блокировка сотрудника", "—")


# --------------------------------------------------------------------------
# Форма фильтра
# --------------------------------------------------------------------------


@pytest.mark.django_db
class TestJournalFilterForm:
    def test_empty_is_valid(self):
        form = JournalFilterForm({})
        assert form.is_valid(), form.errors
        assert form.cleaned_data == {"staff": None, "date_from": None, "date_to": None}

    def test_only_date_from(self):
        form = JournalFilterForm({"date_from": "2026-10-13"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["date_from"] == date(2026, 10, 13)
        assert form.cleaned_data["date_to"] is None

    def test_only_date_to(self):
        form = JournalFilterForm({"date_to": "2026-10-12"})
        assert form.is_valid(), form.errors
        assert form.cleaned_data["date_from"] is None
        assert form.cleaned_data["date_to"] == date(2026, 10, 12)

    def test_reversed_period(self):
        form = JournalFilterForm({"date_from": "2026-10-13", "date_to": "2026-10-12"})
        assert not form.is_valid()
        assert form.non_field_errors() == ["Начало периода позже его конца."]

    def test_date_max(self):
        form = JournalFilterForm({"date_from": "2026-10-13", "date_to": "9999-12-31"})
        assert not form.is_valid()
        assert form.errors["date_to"] == ["Конец периода вне допустимого диапазона."]

    @pytest.mark.parametrize("value", ["abc", "999999999"])
    def test_bad_staff(self, value):
        form = JournalFilterForm({"staff": value})
        assert not form.is_valid()
        assert list(form.errors) == ["staff"]


class TestJournalFilterDefaults:
    def bound(self, query: str) -> dict[str, Any]:
        with patch("django.utils.timezone.now", return_value=TODAY_NOON):
            form = journal_filter(RequestFactory().get(f"/supervisor/journal/{query}"))
        return {key: form.data.get(key) for key in ("staff", "date_from", "date_to")}

    def test_no_dates_gets_last_30_days(self):
        assert self.bound("") == {"staff": None, "date_from": "2026-09-18", "date_to": "2026-10-17"}

    def test_only_staff_gets_last_30_days(self):
        assert self.bound("?staff=7") == {"staff": "7", "date_from": "2026-09-18", "date_to": "2026-10-17"}

    def test_page_only_gets_last_30_days(self):
        assert self.bound("?page=2") == {"staff": None, "date_from": "2026-09-18", "date_to": "2026-10-17"}

    def test_empty_keys_mean_all_time(self):
        assert self.bound("?date_from=&date_to=") == {"staff": None, "date_from": "", "date_to": ""}

    def test_one_date_is_kept_alone(self):
        assert self.bound("?date_from=2026-10-13") == {"staff": None, "date_from": "2026-10-13", "date_to": None}
        assert self.bound("?date_to=2026-10-12") == {"staff": None, "date_from": None, "date_to": "2026-10-12"}


def test_journal_route():
    assert reverse("supervisor:journal") == "/supervisor/journal/"
    assert resolve("/supervisor/journal/").url_name == "journal"

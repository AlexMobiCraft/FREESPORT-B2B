"""
Unit-тесты data-миграции `common/0023_link_routing_rules_to_staff` (стори 42.2, AC1).

Функция миграции вызывается напрямую с глобальным реестром приложений:
транзакционные тесты делают `flush`, и на состояние БД после миграций
полагаться нельзя. Тест сам готовит правила и учётные записи.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.db import connection

from apps.common.models import ManagerRoutingRule
from apps.users.models import User
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

migration = importlib.import_module("apps.common.migrations.0023_link_routing_rules_to_staff")

INN_REGION = ManagerRoutingRule.MATCH_INN_REGION
FALLBACK = ManagerRoutingRule.MATCH_FALLBACK


def run_migration() -> None:
    migration.link_rules_to_staff(django_apps, SimpleNamespace(connection=connection))


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    ManagerRoutingRule.objects.all().delete()


def make_user(email: str, **extra) -> User:
    return User.objects.create_user(email=email, password="StrongPassword123!", **extra)


def make_rule(match_type: str, match_value: str, email: str, active: bool = True) -> ManagerRoutingRule:
    return ManagerRoutingRule.objects.create(
        match_type=match_type, match_value=match_value, manager_email=email, is_active=active
    )


def manager_of(rule: ManagerRoutingRule) -> User | None:
    rule.refresh_from_db()
    return rule.manager


def test_links_staff_case_insensitive():
    suffix = get_unique_suffix()
    staff = make_user(f"manager_{suffix}@freesportopt.ru", is_staff=True)
    rule = make_rule(INN_REGION, "23", f"Manager_{suffix}@FreeSportOpt.ru")
    run_migration()
    assert manager_of(rule) == staff


def test_first_staff_by_pk_when_several():
    suffix = get_unique_suffix()
    first = make_user(f"dup_{suffix}@freesportopt.ru", is_staff=True)
    make_user(f"DUP_{suffix}@freesportopt.ru", is_staff=True)
    rule = make_rule(INN_REGION, "23", f"dup_{suffix}@freesportopt.ru")
    run_migration()
    assert manager_of(rule) == first


def test_client_with_same_email_not_linked():
    email = f"client_{get_unique_suffix()}@freesportopt.ru"
    make_user(email, role="wholesale_level1")
    rule = make_rule(INN_REGION, "23", email)
    run_migration()
    assert manager_of(rule) is None
    assert rule.is_active
    assert rule.manager_email == email


def test_superuser_not_linked():
    email = f"root_{get_unique_suffix()}@freesportopt.ru"
    make_user(email, is_staff=True, is_superuser=True)
    rule = make_rule(INN_REGION, "23", email)
    run_migration()
    assert manager_of(rule) is None


def test_rule_without_account_stays_active():
    rule = make_rule(INN_REGION, "23", f"nobody_{get_unique_suffix()}@freesportopt.ru")
    run_migration()
    assert manager_of(rule) is None
    assert rule.is_active


def test_only_first_fallback_linked():
    suffix = get_unique_suffix()
    chief = make_user(f"chief_{suffix}@freesportopt.ru", is_staff=True)
    admin = make_user(f"admin_{suffix}@freesportopt.ru", is_staff=True)
    first = make_rule(FALLBACK, "default", chief.email)
    second = make_rule(FALLBACK, "default", admin.email)
    run_migration()
    assert manager_of(first) == chief
    assert manager_of(second) is None


def test_fallback_without_account_does_not_block_next():
    suffix = get_unique_suffix()
    chief = make_user(f"chief_{suffix}@freesportopt.ru", is_staff=True)
    orphan = make_rule(FALLBACK, "default", f"orphan_{suffix}@freesportopt.ru")
    linked = make_rule(FALLBACK, "default", chief.email)
    run_migration()
    assert manager_of(orphan) is None
    assert manager_of(linked) == chief


def test_rerun_changes_nothing():
    suffix = get_unique_suffix()
    chief = make_user(f"chief_{suffix}@freesportopt.ru", is_staff=True)
    admin = make_user(f"admin_{suffix}@freesportopt.ru", is_staff=True)
    manager = make_user(f"manager_{suffix}@freesportopt.ru", is_staff=True)
    rules = [
        make_rule(FALLBACK, "default", chief.email),
        make_rule(FALLBACK, "default", admin.email),
        make_rule(INN_REGION, "23", manager.email),
        make_rule(INN_REGION, "24", f"nobody_{suffix}@freesportopt.ru"),
    ]
    run_migration()
    before = list(ManagerRoutingRule.objects.order_by("pk").values_list("pk", "manager_id", "is_active"))
    run_migration()
    after = list(ManagerRoutingRule.objects.order_by("pk").values_list("pk", "manager_id", "is_active"))
    assert before == after
    assert [manager_of(r) for r in rules] == [chief, None, manager, None]

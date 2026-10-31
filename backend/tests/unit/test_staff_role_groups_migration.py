"""
Unit-тесты data-миграции `users/0023_staff_role_groups` (стори 42.1, AC1 и AC5).

Функция миграции вызывается напрямую с глобальным реестром приложений:
тестовая БД строится с миграциями, но транзакционные тесты делают `flush`,
который стирает группы (права восстанавливает `post_migrate`, группы — нет).
Поэтому тест не полагается на состояние БД, а сам готовит исходные данные.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission
from django.db import connection

from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, STAFF_ROLE_GROUPS, SUPERVISORS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")
LEGACY_MANAGER_GROUP = "Менеджер"


def run_migration() -> None:
    migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


def permission_names(group: Group) -> set[str]:
    return {
        f"{app_label}.{codename}"
        for app_label, codename in group.permissions.values_list("content_type__app_label", "codename")
    }


def get_permission(name: str) -> Permission:
    app_label, codename = name.split(".", 1)
    return Permission.objects.get(content_type__app_label=app_label, codename=codename)


def make_user() -> User:
    return User.objects.create_user(email=f"member_{get_unique_suffix()}@example.com", password="StrongPassword123!")


@pytest.fixture(autouse=True)
def no_role_groups():
    """Группы ролей и старая «Менеджер» могут остаться от миграций — убираем."""
    Group.objects.filter(name__in=(*STAFF_ROLE_GROUPS, LEGACY_MANAGER_GROUP)).delete()


def test_role_names_match_staff_roles_module():
    assert tuple(migration.ROLE_PERMISSIONS) == STAFF_ROLE_GROUPS


def test_clean_database_creates_three_groups_with_role_permissions():
    run_migration()

    for role in STAFF_ROLE_GROUPS:
        group = Group.objects.get(name=role)
        assert permission_names(group) == set(migration.ROLE_PERMISSIONS[role])


def test_supervisors_get_managers_and_marketing_permissions():
    supervisors = set(migration.ROLE_PERMISSIONS[SUPERVISORS_GROUP])

    assert set(migration.ROLE_PERMISSIONS[MANAGERS_GROUP]) <= supervisors
    assert set(migration.ROLE_PERMISSIONS[MARKETING_GROUP]) <= supervisors
    assert "users.add_user" in supervisors
    assert "users.add_user" not in migration.ROLE_PERMISSIONS[MANAGERS_GROUP]


def test_rerun_is_idempotent_and_keeps_manual_permission():
    run_migration()
    manual = get_permission("pages.change_page")
    Group.objects.get(name=MARKETING_GROUP).permissions.add(manual)

    run_migration()

    for role in STAFF_ROLE_GROUPS:
        assert Group.objects.filter(name=role).count() == 1
    marketing = Group.objects.get(name=MARKETING_GROUP)
    assert permission_names(marketing) == {*migration.ROLE_PERMISSIONS[MARKETING_GROUP], "pages.change_page"}


def test_rerun_adds_missing_role_permission():
    run_migration()
    managers = Group.objects.get(name=MANAGERS_GROUP)
    managers.permissions.remove(get_permission("orders.view_order"))

    run_migration()

    assert "orders.view_order" in permission_names(managers)


def test_legacy_manager_group_is_renamed_with_permissions_replaced():
    legacy = Group.objects.create(name=LEGACY_MANAGER_GROUP)
    legacy.permissions.add(get_permission("pages.change_page"), get_permission("users.delete_user"))
    member = make_user()
    member.groups.add(legacy)

    run_migration()

    managers = Group.objects.get(name=MANAGERS_GROUP)
    assert managers.pk == legacy.pk
    assert permission_names(managers) == set(migration.ROLE_PERMISSIONS[MANAGERS_GROUP])
    assert managers.user_set.filter(pk=member.pk).exists()
    assert not Group.objects.filter(name=LEGACY_MANAGER_GROUP).exists()
    assert Group.objects.filter(name__startswith="Менеджер").count() == 1


def test_legacy_and_target_groups_are_merged():
    legacy = Group.objects.create(name=LEGACY_MANAGER_GROUP)
    legacy_member = make_user()
    legacy_member.groups.add(legacy)
    target = Group.objects.create(name=MANAGERS_GROUP)
    manual = get_permission("pages.change_page")
    target.permissions.add(manual)
    target_member = make_user()
    target_member.groups.add(target)

    run_migration()

    managers = Group.objects.get(name=MANAGERS_GROUP)
    assert managers.pk == target.pk
    assert set(managers.user_set.values_list("pk", flat=True)) == {legacy_member.pk, target_member.pk}
    assert not Group.objects.filter(name=LEGACY_MANAGER_GROUP).exists()
    assert permission_names(managers) == {*migration.ROLE_PERMISSIONS[MANAGERS_GROUP], "pages.change_page"}


def test_no_role_gets_exchange_or_auth_permissions():
    run_migration()

    for role in STAFF_ROLE_GROUPS:
        names = permission_names(Group.objects.get(name=role))
        assert "integrations.can_exchange_1c" not in names
        assert not any(name.startswith(("auth.", "integrations.")) for name in names)
        assert "users.delete_user" not in names
        assert "orders.delete_order" not in names
        assert "products.change_category" not in names


def test_unknown_permission_raises(monkeypatch):
    monkeypatch.setitem(migration.ROLE_PERMISSIONS, MANAGERS_GROUP, ("users.view_usr",))

    with pytest.raises(Permission.DoesNotExist):
        run_migration()

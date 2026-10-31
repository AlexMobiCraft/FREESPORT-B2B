"""
Unit-тесты раздела менеджера (стори 42.4): доступ к сайту `/manager/`,
правило видимости `scope_clients`, фильтр «Учётная запись на портале» и
действие «Разблокировать» в `/admin/`.
"""

from __future__ import annotations

import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.auth.models import AnonymousUser, Group
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import connection
from django.test import RequestFactory

from apps.common.models import AuditLog, ManagerRoutingRule
from apps.users.manager_admin import PortalAccountFilter, scope_clients
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import manager_site
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")


@pytest.fixture(autouse=True)
def role_groups():
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


@pytest.fixture(autouse=True)
def no_routing_rules():
    ManagerRoutingRule.objects.all().delete()


def make_user(group_name: str | None = None, **extra) -> User:
    user = User.objects.create_user(email=f"u_{get_unique_suffix()}@example.com", password=PASSWORD, **extra)
    if group_name:
        user.groups.add(Group.objects.get(name=group_name))
    return User.objects.get(pk=user.pk)


def make_client(manager: User | None, **extra) -> User:
    extra.setdefault("role", "wholesale_level1")
    client = make_user(**extra)
    User.objects.filter(pk=client.pk).update(responsible_manager=manager)
    return User.objects.get(pk=client.pk)


def request_for(user, path: str = "/manager/", data: dict | None = None):
    request = RequestFactory().get(path, data or {})
    request.user = user
    return request


class TestHasPermission:
    @pytest.mark.parametrize(
        "group_name, extra, expected",
        [
            (MANAGERS_GROUP, {"is_staff": True}, True),
            (SUPERVISORS_GROUP, {"is_staff": True}, True),
            (MARKETING_GROUP, {"is_staff": True}, False),
            (None, {"is_staff": True}, False),
            (MANAGERS_GROUP, {"is_staff": False}, False),
            (MANAGERS_GROUP, {"is_staff": True, "is_active": False}, False),
            (MANAGERS_GROUP, {"is_staff": True, "is_superuser": True}, False),
            (None, {"is_staff": True, "is_superuser": True}, False),
        ],
    )
    def test_matrix(self, group_name, extra, expected):
        user = make_user(group_name, **extra)
        assert manager_site.has_permission(request_for(user)) is expected

    def test_anonymous(self):
        assert manager_site.has_permission(request_for(AnonymousUser())) is False

    def test_membership_is_read_once_per_request(self, django_assert_num_queries):
        user = make_user(MANAGERS_GROUP, is_staff=True)
        request = request_for(user)

        with django_assert_num_queries(1):
            assert manager_site.has_permission(request)
            assert manager_site.has_permission(request)
            assert manager_site.has_permission(request)


class TestScopeClients:
    def test_only_own_non_staff_clients(self):
        manager = make_user(MANAGERS_GROUP, is_staff=True)
        other = make_user(MANAGERS_GROUP, is_staff=True)
        own = make_client(manager)
        foreign = make_client(other)
        staff = make_client(manager, is_staff=True)
        superuser = make_client(manager, is_superuser=True)
        robot = make_client(manager, role="admin")
        marketer = make_client(manager)
        marketer.groups.add(Group.objects.get(name=MARKETING_GROUP))

        visible = list(scope_clients(request_for(manager), User.objects.all()))

        assert visible == [own]
        assert foreign not in visible
        assert not {staff, superuser, robot, marketer} & set(visible)

    def test_member_of_several_groups_is_not_duplicated(self):
        # Строка клиента размножилась бы при JOIN по m2m групп вместо подзапроса:
        # клиент состоит в двух группах вне ролей (видимость не теряет), менеджер —
        # в обеих группах раздела.
        manager = make_user(MANAGERS_GROUP, is_staff=True)
        manager.groups.add(Group.objects.get(name=SUPERVISORS_GROUP))
        own = make_client(manager)
        own.groups.add(
            Group.objects.create(name=f"Прочие_{get_unique_suffix()}"),
            Group.objects.create(name=f"Рассылка_{get_unique_suffix()}"),
        )

        assert scope_clients(request_for(manager), User.objects.all()).count() == 1
        assert list(scope_clients(request_for(manager), User.objects.all())) == [own]


class TestPortalAccountFilter:
    @pytest.fixture
    def users(self):
        registered = make_client(None)
        unregistered = make_client(None, role=User.ROLE_UNREGISTERED)
        return registered, unregistered

    def apply(self, params: dict[str, str]) -> set[User]:
        request = request_for(AnonymousUser(), data=params)
        list_filter = PortalAccountFilter(request, dict(request.GET.lists()), User, None)
        return set(list_filter.queryset(request, User.objects.all()))

    def test_default_hides_unregistered(self, users):
        registered, unregistered = users
        assert self.apply({}) == {registered}

    def test_no_shows_only_unregistered(self, users):
        registered, unregistered = users
        assert self.apply({"portal_account": "no"}) == {unregistered}

    def test_all_shows_everyone(self, users):
        assert self.apply({"portal_account": "all"}) == set(users)

    def test_explicit_yes_hides_unregistered_even_with_role_filter(self, users):
        # «Есть» явным значением: связка с фильтром роли его не отменяет (R42.4-7).
        registered, unregistered = users
        assert self.apply({"portal_account": "yes"}) == {registered}
        assert self.apply({"portal_account": "yes", "role__exact": User.ROLE_UNREGISTERED}) == {registered}

    def test_role_filter_unregistered_disables_default(self, users):
        registered, unregistered = users
        # Фильтр роли применяется своим field-фильтром; здесь проверяется, что
        # этот фильтр не вычитает unregistered при выборе такой роли.
        assert self.apply({"role__exact": User.ROLE_UNREGISTERED}) == {registered, unregistered}

    def test_default_choice_is_selected_without_parameter(self, users):
        request = request_for(AnonymousUser())
        list_filter = PortalAccountFilter(request, {}, User, None)
        changelist = SimpleNamespace(get_query_string=lambda new_params=None, remove=None: "?")

        choices = list(list_filter.choices(changelist))

        assert [choice["display"] for choice in choices] == ["Есть", "Нет", "Все"]
        assert [choice["selected"] for choice in choices] == [True, False, False]

    def test_role_filter_unregistered_selects_all(self, users):
        # Записи без аккаунта видны (исключение фильтра роли) — выделено «Все», не «Есть».
        request = request_for(AnonymousUser(), data={"role__exact": User.ROLE_UNREGISTERED})
        list_filter = PortalAccountFilter(request, dict(request.GET.lists()), User, None)
        changelist = SimpleNamespace(get_query_string=lambda new_params=None, remove=None: "?")

        choices = list(list_filter.choices(changelist))

        assert [choice["selected"] for choice in choices] == [False, False, True]


class TestUnblockUsersInAdmin:
    """Действие «Разблокировать» в `/admin/` у суперпользователя — те же исключения, что в разделе."""

    def run_action(self, actor: User, queryset):
        request = RequestFactory().post("/admin/users/user/")
        request.user = actor
        request.session = {}
        request._messages = FallbackStorage(request)
        admin.site._registry[User].unblock_users(request, queryset)
        return [str(message) for message in request._messages]

    def test_exclusions(self):
        actor = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        blocked = make_client(None, is_active=False, verification_status="verified")
        pending = make_client(None, is_active=False, verification_status="pending")
        rejected = make_client(None, is_active=False, verification_status="unverified")
        shadow = make_client(None, is_active=False, role=User.ROLE_UNREGISTERED)
        superuser = make_user(is_superuser=True, is_staff=True, is_active=False)
        staff = make_user(MANAGERS_GROUP, is_staff=True, is_active=False)
        robot = make_user(role="admin", is_active=False)
        marketer = make_user(MARKETING_GROUP, is_active=False)
        selected = (blocked, pending, rejected, shadow, superuser, staff, robot, marketer)

        texts = self.run_action(actor, User.objects.filter(pk__in=[u.pk for u in selected]))

        assert User.objects.get(pk=blocked.pk).is_active
        for skipped in (pending, rejected, shadow, superuser, staff, robot, marketer):
            assert not User.objects.get(pk=skipped.pk).is_active, skipped
        assert list(AuditLog.objects.filter(action="unblock_user").values_list("resource_id", flat=True)) == [
            str(blocked.pk)
        ]
        assert any(f"/admin/users/user/{pending.pk}/verify/" in text for text in texts)

    def test_only_pending_selected(self):
        actor = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        pending = make_client(None, is_active=False, verification_status="pending")

        texts = self.run_action(actor, User.objects.filter(pk=pending.pk))

        assert not User.objects.get(pk=pending.pk).is_active
        assert not AuditLog.objects.exists()
        assert not any("Разблокировано" in text for text in texts)

"""
Integration-тесты раздела менеджера `/manager/` — клиенты своего региона (стори 42.4).

Покрывает:
- AC1 — вход: менеджер и руководитель пускаются, остальные роли, суперпользователь
  (в том числе в группе «Менеджеры»), аноним и заблокированный менеджер — нет;
- AC2 — список и поиск только по своим клиентам, учётные записи сотрудников скрыты,
  `unregistered` — только с фильтром «Учётная запись на портале»;
- AC3 — 404 на чужого клиента по прямым URL, массовые действия его не трогают;
- AC4/AC5 — белый список полей карточки, подделанный POST, инлайны реквизитов
  и адресов только своего клиента;
- AC6 — разблокировка; AC7 — записи AuditLog; AC8 — ссылки и редиректы в разделе;
- AC9 — права внутри раздела при одном `view_user` (долг VG1 стори 42.1);
- AC10 — клиент ушёл к другому менеджеру после правки ИНН;
- AC11 — число запросов списка не зависит от числа клиентов;
- смена роли в карточке (FR-42-13): только верифицированный B2B, журнал, цены каталога.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`):
правки групп внутри теста стирает `flush`, а следующий тест заново получает
группы из `role_groups`.
"""

from __future__ import annotations

import importlib
import itertools
import threading
import time
import uuid
from contextlib import ExitStack, contextmanager
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, Iterator
from unittest.mock import patch

import pytest
from django.apps import apps as django_apps
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.admin.utils import label_for_field
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, Permission
from django.db import DEFAULT_DB_ALIAS, DatabaseError, OperationalError, connection, connections, transaction
from django.db.models import QuerySet
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from psycopg2.errorcodes import LOCK_NOT_AVAILABLE
from rest_framework.test import APIClient

from apps.common.models import AuditLog, ManagerRoutingRule
from apps.products.models import Brand, Category, Product, ProductVariant
from apps.users import admin as users_admin
from apps.users.manager_admin import ManagerClientAdmin, PortalAccountFilter
from apps.users.models import Address, Company, User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"
NEW_PASSWORD = "AnotherStrongPass456!"
INDEX_URL = "/manager/"
CHANGELIST_URL = "/manager/users/user/"

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")
_counter = itertools.count()

# Поля блока «Не показывать» section-contents: в HTML нет ни поля, ни подписи.
HIDDEN_FIELDS = (
    "is_staff",
    "is_superuser",
    "groups",
    "user_permissions",
    "onec_id",
    "onec_guid",
    "onec_price_type_id",
    "onec_link_candidates",
    "sync_status",
    "created_in_1c",
    "needs_1c_export",
    "last_sync_at",
    "last_sync_from_1c",
    "sync_error_message",
    "responsible_manager_manual",
)


@pytest.fixture(autouse=True)
def role_groups():
    """Группы ролей с полным набором прав — через функцию data-миграции 0023."""
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


@pytest.fixture(autouse=True)
def no_routing_rules():
    """
    Сид правил `0018` в тестовой БД то есть, то стёрт `flush`, а хук 42.2
    назначает ответственного при создании клиента — правила задаёт сам тест.
    """
    ManagerRoutingRule.objects.all().delete()


@pytest.fixture(autouse=True)
def verified_email_task():
    with patch("apps.users.signals.send_user_verified_email") as task:
        yield task


def unique_digits(length: int) -> str:
    value = (time.time_ns() + next(_counter) * 7919) % (10**length)
    return str(value).zfill(length)


def region_tax_id(region: str) -> str:
    return region + unique_digits(8)


def unique_tax_id() -> str:
    return region_tax_id("50")


def make_staff_member(group_name: str | None = MANAGERS_GROUP, **extra: Any) -> User:
    """Сотрудник роли: `is_staff=True`, член группы, не суперпользователь."""
    defaults = {
        "email": f"staff_{get_unique_suffix()}@freesportopt.ru",
        "first_name": "Сотрудник",
        "last_name": f"Тестов{next(_counter)}",
        "is_staff": True,
    }
    defaults.update(extra)
    member = User.objects.create_user(password=PASSWORD, **defaults)
    if group_name:
        member.groups.add(Group.objects.get(name=group_name))
    return User.objects.get(pk=member.pk)


def make_client(manager: User | None, **overrides: Any) -> User:
    """
    Клиент, закреплённый за менеджером.

    Хук 42.2 в `save()` перезаписал бы `responsible_manager` результатом правил,
    поэтому ответственный ставится `update()` после создания. Флаг «назначен
    вручную» по умолчанию стоит: подтверждение заявки и привязка к 1С иначе
    пересчитали бы ответственного по (пустым) правилам и увели клиента из раздела.
    """
    manual = overrides.pop("manual", True) and manager is not None
    defaults = {
        "email": f"client_{get_unique_suffix()}@example.com",
        "first_name": "Клиент",
        "last_name": f"Фамилия{next(_counter)}",
        "role": "wholesale_level1",
        "company_name": f"ООО Клиент {next(_counter)}",
        "tax_id": unique_tax_id(),
        "phone": f"+7900{unique_digits(7)}",
        "verification_status": "verified",
        "is_verified": True,
    }
    defaults.update(overrides)
    client = User.objects.create_user(password=PASSWORD, **defaults)
    User.objects.filter(pk=client.pk).update(responsible_manager=manager, responsible_manager_manual=manual)
    return User.objects.get(pk=client.pk)


def make_1c_record(tax_id: str, **overrides: Any) -> User:
    defaults = {
        "email": f"1c_{get_unique_suffix()}@example.com",
        "first_name": "Контрагент",
        "last_name": "Из1С",
        "company_name": "ООО Импортированное",
        "tax_id": tax_id,
        "role": User.ROLE_UNREGISTERED,
        "created_in_1c": True,
        "verification_status": "unverified",
        "onec_id": f"1C-{get_unique_suffix()}",
        "password": "",
    }
    defaults.update(overrides)
    record = User(**defaults)
    record.save()
    return record


def make_company(user: User, **overrides: Any) -> Company:
    defaults = {
        "legal_name": f"ООО Реквизиты {next(_counter)}",
        "tax_id": user.tax_id,
        "kpp": "770101001",
        "legal_address": "г. Москва, ул. Тверская, д. 1",
    }
    defaults.update(overrides)
    return Company.objects.create(user=user, **defaults)


def make_address(user: User, **overrides: Any) -> Address:
    defaults = {
        "full_name": "Получатель Тестов",
        "phone": "+79001234567",
        "city": "Москва",
        "street": "Тверская",
        "building": "1",
        "postal_code": "125009",
    }
    defaults.update(overrides)
    return Address.objects.create(user=user, **defaults)


def related_snapshot(user: User) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Company и адреса клиента как значения полей — для сравнения «до» и «после»."""
    company = Company.objects.filter(user=user).values().first() or {}
    addresses = list(Address.objects.filter(user=user).order_by("pk").values())
    return company, addresses


def inline_prefixes(response) -> dict[type, str]:
    """Префиксы формсетов инлайнов карточки по модели."""
    return {inline.formset.model: inline.formset.prefix for inline in response.context["inline_admin_formsets"]}


def change_url(user: User) -> str:
    return reverse("manager:users_user_change", args=[user.pk])


def history_url(user: User) -> str:
    return reverse("manager:users_user_history", args=[user.pk])


def verify_url(user: User) -> str:
    return reverse("manager:users_user_verify", args=[user.pk])


def password_url(user: User) -> str:
    return reverse("manager:auth_user_password_change", args=[user.pk])


def post_action(client, action: str, *targets: User, follow: bool = True, **extra: Any):
    payload = {"action": action, "_selected_action": [str(target.pk) for target in targets]}
    payload.update(extra)
    return client.post(CHANGELIST_URL, payload, follow=follow)


def message_texts(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


def audit_records(user: User, action: str | None = None):
    records = AuditLog.objects.filter(resource_type="User", resource_id=str(user.pk))
    return records.filter(action=action) if action else records


def form_payload(response) -> dict[str, Any]:
    """POST-данные карточки из GET-контекста: поля формы и формсеты инлайнов."""

    def put(data: dict[str, Any], name: str, value: Any) -> None:
        if value is None or value is False:
            return
        data[name] = "on" if value is True else value

    data: dict[str, Any] = {}
    form = response.context["adminform"].form
    for name in form.fields:
        bound = form[name]
        put(data, name, bound.value())
        # Как браузер: скрытое начальное значение, при перерисовке — из прошлого POST.
        if bound.field.show_hidden_initial:
            data[bound.html_initial_name] = form.data.get(bound.html_initial_name, bound.value())
    for inline in response.context["inline_admin_formsets"]:
        formset = inline.formset
        management = formset.management_form
        for name in management.fields:
            data[f"{formset.prefix}-{name}"] = management[name].value()
        for inline_form in formset.forms:
            for name in inline_form.fields:
                put(data, inline_form.add_prefix(name), inline_form[name].value())
    return data


@pytest.fixture
def manager() -> User:
    return make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Менеджерова")


@pytest.fixture
def other_manager() -> User:
    return make_staff_member(MANAGERS_GROUP)


@pytest.fixture
def manager_client(client, manager):
    client.force_login(manager)
    return client


@pytest.fixture(params=[MANAGERS_GROUP], ids=["manager"])
def section_member(request) -> User:
    """
    Менеджер раздела для негативных проверок видимости «только свои».

    До 42.7 здесь был и вариант `supervisor`: руководитель видел только своих.
    Стори 42.7 открыла руководителю всех клиентов и заказы, его видимость
    проверяет `tests/integration/test_supervisor_section.py`.
    """
    return make_staff_member(request.param)


@pytest.fixture
def section_client(client, section_member):
    client.force_login(section_member)
    return client


class TestEntry:
    """AC1 — кто входит в раздел."""

    @pytest.mark.parametrize("group_name", [MANAGERS_GROUP, SUPERVISORS_GROUP])
    def test_manager_and_supervisor_enter(self, client, group_name):
        client.force_login(make_staff_member(group_name))

        for url in (INDEX_URL, CHANGELIST_URL):
            response = client.get(url)
            assert response.status_code == 200, url
            assert "OPTISPORT — Менеджер" in response.content.decode()

    @pytest.mark.parametrize(
        "make_user",
        [
            pytest.param(lambda: make_staff_member(MARKETING_GROUP), id="marketing"),
            pytest.param(lambda: make_staff_member(None), id="staff-without-group"),
            pytest.param(
                lambda: User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD),
                id="superuser",
            ),
            pytest.param(
                lambda: make_staff_member(MANAGERS_GROUP, is_superuser=True),
                id="superuser-in-managers-group",
            ),
            pytest.param(lambda: make_staff_member(MANAGERS_GROUP, is_active=False), id="blocked-manager"),
            pytest.param(lambda: make_staff_member(MANAGERS_GROUP, is_staff=False), id="manager-without-is-staff"),
            pytest.param(None, id="anonymous"),
        ],
    )
    def test_others_are_redirected_to_login(self, client, make_user):
        if make_user is not None:
            client.force_login(make_user())

        for url in (INDEX_URL, CHANGELIST_URL):
            response = client.get(url)
            assert response.status_code == 302, url
            assert "/manager/login/" in response.url

    def test_superuser_keeps_admin(self, client):
        """Суперпользователь в группе «Менеджеры» по-прежнему работает в /admin/."""
        client.force_login(make_staff_member(MANAGERS_GROUP, is_superuser=True))
        assert client.get("/admin/").status_code == 200


class TestChangelist:
    """AC2 — список и поиск только по своим клиентам."""

    def test_search_finds_only_own_clients(self, section_client, section_member, other_manager):
        own = make_client(section_member, customer_code=unique_digits(5))
        foreign = make_client(
            other_manager,
            customer_code=unique_digits(5),
            last_name="Чужаков",
            company_name="ООО Чужая Компания",
        )

        listed = section_client.get(CHANGELIST_URL).context["cl"].result_list
        assert own in listed
        assert foreign not in listed

        for query in (
            foreign.email,
            foreign.tax_id,
            foreign.phone,
            foreign.last_name,
            foreign.company_name,
            foreign.customer_code,
        ):
            result = section_client.get(CHANGELIST_URL, {"q": query}).context["cl"].result_list
            assert foreign not in result, query

        # Поиск сам по себе работает: те же поля своего клиента находятся.
        for query in (own.email, own.tax_id, own.phone, own.last_name, own.company_name, own.customer_code):
            result = section_client.get(CHANGELIST_URL, {"q": query}).context["cl"].result_list
            assert own in result, query

    def test_staff_accounts_are_hidden(self, manager_client, manager):
        """По одной записи на каждое условие `staff_accounts_q()`."""
        staff = make_client(manager)
        User.objects.filter(pk=staff.pk).update(is_staff=True)
        superuser = make_client(manager)
        User.objects.filter(pk=superuser.pk).update(is_superuser=True)
        robot = make_client(manager)
        User.objects.filter(pk=robot.pk).update(role="admin")
        marketer = make_client(manager)
        marketer.groups.add(Group.objects.get(name=MARKETING_GROUP))
        own = make_client(manager)

        listed = list(manager_client.get(CHANGELIST_URL, {"portal_account": "all"}).context["cl"].result_list)

        assert listed == [own]

    def test_unregistered_hidden_by_default(self, manager_client, manager):
        record = make_client(manager, role=User.ROLE_UNREGISTERED, verification_status="unverified", is_verified=False)
        own = make_client(manager)

        def listed(params: dict[str, str]) -> list[User]:
            return list(manager_client.get(CHANGELIST_URL, params).context["cl"].result_list)

        assert listed({}) == [own]
        assert listed({"portal_account": "no"}) == [record]
        assert set(listed({"portal_account": "all"})) == {own, record}
        assert listed({"role__exact": User.ROLE_UNREGISTERED}) == [record]

    def test_have_account_link_keeps_its_choice(self, manager_client, manager):
        # R42.4-7: переход по «Есть» при фильтре роли «Не зарегистрирован» выделяет «Есть».
        record = make_client(manager, role=User.ROLE_UNREGISTERED, verification_status="unverified", is_verified=False)
        make_client(manager)

        def portal_choices(response) -> list[dict[str, Any]]:
            changelist = response.context["cl"]
            spec = next(spec for spec in changelist.filter_specs if isinstance(spec, PortalAccountFilter))
            return list(spec.choices(changelist))

        response = manager_client.get(CHANGELIST_URL, {"role__exact": User.ROLE_UNREGISTERED})
        have = next(choice for choice in portal_choices(response) if choice["display"] == "Есть")
        followed = manager_client.get(CHANGELIST_URL + have["query_string"])

        assert [choice["display"] for choice in portal_choices(followed) if choice["selected"]] == ["Есть"]
        assert record not in list(followed.context["cl"].result_list)

    def test_columns_filters_and_title(self, manager_client, manager):
        make_client(manager)

        response = manager_client.get(CHANGELIST_URL)

        cl = response.context["cl"]
        assert list(cl.list_display) == [
            "action_checkbox",
            "email",
            "full_name",
            "company_name",
            "tax_id",
            "customer_code",
            "role_display",
            "verification_status_display",
            "has_1c_candidate",
            "verify_b2b_link",
            "phone",
            "created_at",
            "is_active",
        ]
        filters = [getattr(spec, "field_path", None) or spec.parameter_name for spec in cl.filter_specs]
        assert filters == ["role", "verification_status", "has_1c_candidate", "is_active", "portal_account"]
        content = response.content.decode()
        assert "<h1>Клиенты</h1>" in content
        assert 'class="addlink"' not in content
        assert "/manager/users/user/add/" not in content

    def test_index_names_block_clients(self, manager_client):
        response = manager_client.get(INDEX_URL)

        users_app = next(app for app in response.context["app_list"] if app["app_label"] == "users")
        assert users_app["name"] == "Клиенты"
        assert [model["name"] for model in users_app["models"]] == ["Клиенты"]


class TestForeignClient:
    """AC3 — 404 на чужого клиента."""

    def test_direct_urls_answer_404(self, section_client, section_member, other_manager):
        own = make_client(section_member, verification_status="pending", is_verified=False, is_active=False)
        foreign = make_client(other_manager, verification_status="pending", is_verified=False, is_active=False)
        source = make_1c_record(foreign.tax_id)

        # Контроль: те же адреса своего клиента открываются — 404 ниже не от отказа во входе.
        for url in (change_url(own), history_url(own), verify_url(own), password_url(own)):
            assert section_client.get(url).status_code == 200, url

        assert section_client.get(change_url(foreign)).status_code == 404
        assert section_client.post(change_url(foreign), {"email": "hacked@example.com"}).status_code == 404
        assert section_client.get(history_url(foreign)).status_code == 404
        assert section_client.get(verify_url(foreign)).status_code == 404
        response = section_client.post(
            verify_url(foreign), {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}"}
        )
        assert response.status_code == 404
        assert section_client.post(verify_url(foreign), {"_reject": "1"}).status_code == 404
        assert section_client.get(password_url(foreign)).status_code == 404
        response = section_client.post(
            password_url(foreign),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )
        assert response.status_code == 404

        foreign.refresh_from_db()
        assert foreign.email != "hacked@example.com"
        assert foreign.verification_status == "pending"
        assert not foreign.onec_id
        assert foreign.check_password(PASSWORD)
        assert not audit_records(foreign).exists()

    @pytest.mark.parametrize(
        "action, foreign_state, field, expected",
        [
            (
                "approve_b2b_users",
                {"verification_status": "pending", "is_verified": False},
                "verification_status",
                "pending",
            ),
            (
                "reject_b2b_users",
                {"verification_status": "pending", "is_verified": False},
                "verification_status",
                "pending",
            ),
            ("block_users", {"is_active": True}, "is_active", True),
            ("unblock_users", {"is_active": False}, "is_active", False),
        ],
    )
    def test_mass_action_skips_forged_foreign_id(
        self, manager_client, manager, other_manager, action, foreign_state, field, expected
    ):
        own = make_client(manager, **foreign_state)
        foreign = make_client(other_manager, **foreign_state)

        post_action(manager_client, action, own, foreign)

        foreign.refresh_from_db()
        assert getattr(foreign, field) == expected
        assert not audit_records(foreign).exists()
        # Своего клиента действие при этом обработало.
        assert audit_records(own).count() == 1

    def test_link_action_skips_forged_foreign_id(self, manager_client, other_manager):
        foreign = make_client(other_manager, verification_status="pending", is_verified=False)
        source = make_1c_record(foreign.tax_id)

        post_action(manager_client, "link_1c_customer", foreign, apply="1", candidate=f"{source.pk}:{source.onec_id}")

        foreign.refresh_from_db()
        assert not foreign.onec_id
        assert not audit_records(foreign).exists()


class TestClientCard:
    """AC4, AC5 — белый список полей карточки."""

    def test_card_shows_only_whitelisted_fields(self, manager_client, manager):
        own = make_client(manager)

        response = manager_client.get(change_url(own))

        assert response.status_code == 200
        adminform = response.context["adminform"]
        assert set(adminform.form.fields) == {
            "email",
            "password",
            "first_name",
            "last_name",
            "phone",
            "company_name",
            "tax_id",
            "country",
            "role",
            "is_active",
        }
        assert set(adminform.readonly_fields) == {
            "customer_code",
            "verification_status",
            "is_verified",
            "linked_to_1c",
            "onec_price_type_name",
            "responsible_manager_display",
            "company_legal_address",
            "created_at",
            "last_login",
        }
        prefixes = {inline.formset.prefix for inline in response.context["inline_admin_formsets"]}
        assert len(prefixes) == 2

        content = response.content.decode()
        for field in HIDDEN_FIELDS:
            assert f'name="{field}"' not in content, field
            # Подпись — как её вывела бы полная карточка /admin/ (поле модели или display-метод).
            label = str(label_for_field(field, User, admin.site._registry[User]))
            assert label not in content, (field, label)
        assert 'class="deletelink"' not in content
        assert reverse("manager:users_user_delete", args=[own.pk]) not in content
        assert 'class="addlink"' not in content

    def test_responsible_manager_is_text_without_link(self, manager_client, manager):
        own = make_client(manager)

        content = manager_client.get(change_url(own)).content.decode()

        assert f"Анна Менеджерова ({manager.email})" in content
        assert f"/manager/users/user/{manager.pk}/" not in content

    def test_forged_post_changes_only_allowed_fields(self, manager_client, manager, other_manager):
        own = make_client(manager, verification_status="pending", is_verified=False, customer_code=unique_digits(5))
        before = User.objects.get(pk=own.pk)
        data = form_payload(manager_client.get(change_url(own)))
        data.update(
            {
                "phone": "+79001112233",
                "role": "wholesale_level3",
                "is_staff": "on",
                "is_superuser": "on",
                "groups": [str(Group.objects.get(name=SUPERVISORS_GROUP).pk)],
                "onec_id": "FORGED-1C",
                "verification_status": "verified",
                "is_verified": "on",
                "customer_code": "99999",
                "responsible_manager": str(other_manager.pk),
                "responsible_manager_manual": "",
                "_save": "Сохранить",
            }
        )

        response = manager_client.post(change_url(own), data)

        assert response.status_code == 302, response.context["adminform"].form.errors if response.context else ""
        own.refresh_from_db()
        assert own.phone == "+79001112233"
        assert own.role == before.role
        assert not own.is_staff
        assert not own.is_superuser
        assert not own.groups.exists()
        assert own.onec_id == before.onec_id
        assert own.verification_status == "pending"
        assert not own.is_verified
        assert own.customer_code == before.customer_code
        assert own.responsible_manager == manager
        assert own.responsible_manager_manual

    @pytest.mark.parametrize(
        "state",
        [
            pytest.param({"verification_status": "pending", "is_verified": False}, id="pending"),
            pytest.param({"verification_status": "unverified", "is_verified": False}, id="rejected"),
            pytest.param({"role": User.ROLE_UNREGISTERED, "verification_status": "unverified"}, id="1c-record"),
        ],
    )
    @pytest.mark.parametrize("initially_active", [True, False], ids=["active", "blocked"])
    def test_active_flag_is_read_only_without_portal_access(self, manager_client, manager, state, initially_active):
        """R42.4-32: флаг «активен» заявки и записи 1С карточкой не меняется — ни включить, ни выключить."""
        own = make_client(manager, is_active=initially_active, **state)

        response = manager_client.get(change_url(own))
        adminform = response.context["adminform"]
        assert "is_active" not in adminform.form.fields
        assert "is_active" in adminform.readonly_fields

        data = form_payload(response)
        data.update({"phone": "+79001112244", "is_active": "" if initially_active else "on", "_save": "Сохранить"})
        assert manager_client.post(change_url(own), data).status_code == 302

        own.refresh_from_db()
        assert own.phone == "+79001112244"
        assert own.is_active is initially_active
        assert not audit_records(own).exists()


def form_index(data: dict[str, Any], prefix: str, obj: Any) -> int:
    """Номер формы формсета, которая редактирует `obj`."""
    total = int(data[f"{prefix}-TOTAL_FORMS"])
    return next(index for index in range(total) if str(data.get(f"{prefix}-{index}-id")) == str(obj.pk))


class TestClientInlines:
    """AC4, AC3 — реквизиты и адреса правятся только у своего клиента."""

    def test_own_company_and_addresses_are_saved(self, manager_client, manager):
        own = make_client(manager)
        company = make_company(own)
        kept = make_address(own, city="Москва")
        removed = make_address(own, city="Тула")
        response = manager_client.get(change_url(own))
        prefixes = inline_prefixes(response)
        company_prefix, address_prefix = prefixes[Company], prefixes[Address]
        data = form_payload(response)

        data[f"{company_prefix}-0-legal_name"] = "ООО Новые реквизиты"
        data[f"{company_prefix}-0-kpp"] = "771001001"
        data[f"{address_prefix}-{form_index(data, address_prefix, kept)}-city"] = "Казань"
        data[f"{address_prefix}-{form_index(data, address_prefix, removed)}-DELETE"] = "on"
        added = int(data[f"{address_prefix}-TOTAL_FORMS"])
        data[f"{address_prefix}-TOTAL_FORMS"] = str(added + 1)
        data.update(
            {
                f"{address_prefix}-{added}-address_type": "shipping",
                f"{address_prefix}-{added}-full_name": "Новый Получатель",
                f"{address_prefix}-{added}-phone": "+79007654321",
                f"{address_prefix}-{added}-city": "Сочи",
                f"{address_prefix}-{added}-street": "Морская",
                f"{address_prefix}-{added}-building": "5",
                "_save": "Сохранить",
            }
        )

        response = manager_client.post(change_url(own), data)

        assert response.status_code == 302, response.context["errors"] if response.context else ""
        company.refresh_from_db()
        assert company.legal_name == "ООО Новые реквизиты"
        assert company.kpp == "771001001"
        kept.refresh_from_db()
        assert kept.city == "Казань"
        assert not Address.objects.filter(pk=removed.pk).exists()
        assert sorted(Address.objects.filter(user=own).values_list("city", flat=True)) == ["Казань", "Сочи"]

    @pytest.mark.parametrize("mode", ["change", "delete"])
    def test_forged_foreign_inline_ids_change_nothing(self, manager_client, manager, other_manager, mode):
        own = make_client(manager)
        own_company = make_company(own)
        own_address = make_address(own)
        foreign = make_client(other_manager)
        foreign_company = make_company(foreign)
        foreign_address = make_address(foreign)
        foreign_before = related_snapshot(foreign)
        response = manager_client.get(change_url(own))
        prefixes = inline_prefixes(response)
        company_prefix, address_prefix = prefixes[Company], prefixes[Address]
        data = form_payload(response)
        index = form_index(data, address_prefix, own_address)

        # ID записей чужого клиента вместо своих — в формах, где они уже стоят.
        data[f"{address_prefix}-{index}-id"] = str(foreign_address.pk)
        if mode == "change":
            data[f"{company_prefix}-0-id"] = str(foreign_company.pk)
            data[f"{company_prefix}-0-legal_name"] = "ООО Подмена"
            data[f"{address_prefix}-{index}-city"] = "Подмена"
        else:
            data[f"{address_prefix}-{index}-DELETE"] = "on"
        data["_save"] = "Сохранить"

        response = manager_client.post(change_url(own), data)

        if mode == "change":
            # Чужой ID не входит в queryset формсета — форма с ошибкой, ничего не сохранено.
            assert response.status_code == 200
            assert response.context["errors"]
        assert related_snapshot(foreign) == foreign_before
        own_company.refresh_from_db()
        assert own_company.legal_name != "ООО Подмена"
        assert list(Address.objects.filter(user=own).values_list("pk", "city")) == [(own_address.pk, own_address.city)]
        assert not audit_records(foreign).exists()


class TestUnblock:
    """AC6 — разблокировка."""

    def test_unblock_restores_login(self, manager_client, manager):
        blocked = make_client(manager, is_active=False)
        assert authenticate(email=blocked.email, password=PASSWORD) is None

        post_action(manager_client, "unblock_users", blocked)

        blocked.refresh_from_db()
        assert blocked.is_active
        assert blocked.verification_status == "verified"
        assert authenticate(email=blocked.email, password=PASSWORD) == blocked
        assert audit_records(blocked, "unblock_user").count() == 1
        assert audit_records(blocked).count() == 1

        # Портал входит не через authenticate(), а через UserLoginSerializer
        # и отдельно отказывает статусу `pending` (R42.4-25).
        response = APIClient().post(
            reverse("users:login"), {"email": blocked.email, "password": PASSWORD}, format="json"
        )
        assert response.status_code == 200, response.data
        assert response.data["access"]
        assert response.data["refresh"]
        assert response.data["user"]["id"] == blocked.pk

    def test_pending_application_and_superuser_are_skipped(self, manager_client, manager):
        pending = make_client(manager, is_active=False, verification_status="pending", is_verified=False)
        superuser = User.objects.create_superuser(
            email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD, is_active=False
        )
        User.objects.filter(pk=superuser.pk).update(responsible_manager=manager)

        response = post_action(manager_client, "unblock_users", pending, superuser)

        pending.refresh_from_db()
        superuser.refresh_from_db()
        assert not pending.is_active
        assert not superuser.is_active
        assert not audit_records(pending).exists()
        assert not audit_records(superuser).exists()
        texts = message_texts(response)
        assert any(f"/manager/users/user/{pending.pk}/verify/" in text for text in texts)

    def test_retail_client_is_unblocked(self, manager_client, manager):
        # Розничному клиенту подтверждение не нужно — статус верификации не важен.
        retail = make_client(
            manager, role="retail", verification_status="unverified", is_verified=False, is_active=False
        )

        post_action(manager_client, "unblock_users", retail)

        retail.refresh_from_db()
        assert retail.is_active
        assert audit_records(retail, "unblock_user").count() == 1

    def test_rejected_application_and_1c_record_are_skipped(self, manager_client, manager):
        """R42.4-31: отклонённая заявка и запись 1С без аккаунта не разблокируются."""
        rejected = make_client(manager, verification_status="unverified", is_verified=False, is_active=False)
        # Отработанный источник привязки: роль unregistered, идентификаторы 1С сняты.
        shadow = make_client(
            manager, role=User.ROLE_UNREGISTERED, verification_status="unverified", is_verified=False, is_active=False
        )
        blocked = make_client(manager, is_active=False)

        # Запись 1С менеджер видит в списке только с фильтром «Учётная запись на портале: все».
        response = manager_client.post(
            f"{CHANGELIST_URL}?portal_account=all",
            {"action": "unblock_users", "_selected_action": [str(user.pk) for user in (rejected, shadow, blocked)]},
            follow=True,
        )

        for skipped in (rejected, shadow):
            skipped.refresh_from_db()
            assert not skipped.is_active
            assert not audit_records(skipped).exists()
        blocked.refresh_from_db()
        assert blocked.is_active
        texts = message_texts(response)
        assert any("Пропущено 2" in text for text in texts), texts
        assert any("Разблокировано 1" in text for text in texts), texts

    def test_empty_selection_warns(self, manager_client, manager):
        active = make_client(manager)

        response = post_action(manager_client, "unblock_users", active)

        assert any("ни одного заблокированного" in text for text in message_texts(response))
        assert not audit_records(active).exists()


class TestAuditLog:
    """AC7 — на одно действие одна запись своего вида, автор — менеджер."""

    def assert_single(self, client_user: User, action: str, manager: User) -> AuditLog:
        records = list(audit_records(client_user))
        assert [record.action for record in records] == [action]
        assert records[0].user == manager
        return records[0]

    def test_verify_page_decision(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)

        response = manager_client.post(
            verify_url(applicant), {"confirm": "on", "confirm_without_1c": "on", "role": "wholesale_level1"}
        )

        assert response.status_code == 302
        assert response.url == change_url(applicant)
        self.assert_single(applicant, "verify_b2b", manager)

    def test_verify_page_with_link_writes_two_kinds(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)
        source = make_1c_record(applicant.tax_id)

        response = manager_client.post(
            verify_url(applicant),
            {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}", "role": "wholesale_level1"},
        )

        assert response.status_code == 302
        actions = sorted(audit_records(applicant).values_list("action", flat=True))
        assert actions == ["link_1c_customer", "verify_b2b"]

    def test_verify_page_reject(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)

        response = manager_client.post(verify_url(applicant), {"_reject": "1"})

        assert response.status_code == 302
        # Карточки заявителя больше нет: возврат в список клиентов раздела.
        assert response.url == CHANGELIST_URL
        assert not User.objects.filter(pk=applicant.pk).exists()
        self.assert_single(applicant, "reject_b2b", manager)

    @pytest.mark.parametrize(
        "action, state, expected",
        [
            ("approve_b2b_users", {"verification_status": "pending", "is_verified": False}, "approve_b2b"),
            ("reject_b2b_users", {"verification_status": "pending", "is_verified": False}, "reject_b2b"),
            ("block_users", {}, "block_user"),
            ("unblock_users", {"is_active": False}, "unblock_user"),
        ],
    )
    def test_mass_actions(self, manager_client, manager, action, state, expected):
        target = make_client(manager, **state)

        post_action(manager_client, action, target)

        self.assert_single(target, expected, manager)

    def test_link_action(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        source = make_1c_record(applicant.tax_id)

        post_action(manager_client, "link_1c_customer", applicant, apply="1", candidate=f"{source.pk}:{source.onec_id}")

        applicant.refresh_from_db()
        assert applicant.onec_id == source.onec_id
        self.assert_single(applicant, "link_1c_customer", manager)

    def test_password_change(self, manager_client, manager):
        target = make_client(manager)

        response = manager_client.post(
            password_url(target),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        assert response.status_code == 302
        assert response.url == change_url(target)
        target.refresh_from_db()
        assert target.check_password(NEW_PASSWORD)
        self.assert_single(target, "change_password", manager)

    @pytest.mark.parametrize("initially_active, expected", [(True, "block_user"), (False, "unblock_user")])
    def test_card_active_flag(self, manager_client, manager, initially_active, expected):
        target = make_client(manager, is_active=initially_active)
        data = form_payload(manager_client.get(change_url(target)))
        if initially_active:
            data.pop("is_active")
        else:
            data["is_active"] = "on"
        data["_save"] = "Сохранить"

        response = manager_client.post(change_url(target), data)

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.is_active is not initially_active
        record = self.assert_single(target, expected, manager)
        assert record.details["changes"]["source"] == "card"
        assert record.details["changes"]["blocked"] is initially_active

    def test_card_save_without_flag_change_writes_nothing(self, manager_client, manager):
        target = make_client(manager)
        data = form_payload(manager_client.get(change_url(target)))
        data["phone"] = "+79005554433"
        data["_save"] = "Сохранить"

        assert manager_client.post(change_url(target), data).status_code == 302
        assert not audit_records(target).exists()


class TestClientRole:
    """FR-42-13 — смена роли в карточке: кто, у какого клиента, на что и что остаётся в журнале."""

    @staticmethod
    def post_role(client, target: User, role: str, **extra: Any):
        data = form_payload(client.get(change_url(target)))
        data.update({"role": role, "_save": "Сохранить", **extra})
        return client.post(change_url(target), data)

    def test_role_change_is_saved_and_logged(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level1")

        response = self.post_role(manager_client, target, "wholesale_level3")

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.role == "wholesale_level3"
        record = audit_records(target).get()
        assert record.action == "change_user_role"
        assert record.user == manager
        assert record.details["changes"] == {
            "email": target.email,
            "old": "wholesale_level1",
            "new": "wholesale_level3",
            "source": "card",
        }

    def test_downgrade_to_retail_closes_role(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level2")

        assert self.post_role(manager_client, target, "retail").status_code == 302

        target.refresh_from_db()
        assert target.role == "retail"
        record = audit_records(target, "change_user_role").get()
        assert record.details["changes"]["old"] == "wholesale_level2"
        assert record.details["changes"]["new"] == "retail"
        # Вернуть B2B в карточке нельзя: это делает владелец в /admin/ или обмен с 1С.
        assert "role" not in manager_client.get(change_url(target)).context["adminform"].form.fields

    def test_choices_have_no_service_roles(self, manager_client, manager):
        response = manager_client.get(change_url(make_client(manager)))

        assert [value for value, _ in response.context["adminform"].form.fields["role"].choices] == [
            "retail",
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "wholesale_level4",
            "trainer",
            "federation_rep",
            "vip",
            "special_price",
        ]

    @pytest.mark.parametrize("forged_role", ["admin", "unregistered"])
    def test_forged_service_role_is_rejected(self, manager_client, manager, forged_role):
        target = make_client(manager, role="wholesale_level1")

        response = self.post_role(manager_client, target, forged_role)

        assert response.status_code == 200
        assert "role" in response.context["adminform"].form.errors
        target.refresh_from_db()
        assert target.role == "wholesale_level1"
        assert not audit_records(target).exists()

    @pytest.mark.parametrize("posted_role", ["wholesale_level3", "admin"])
    @pytest.mark.parametrize(
        "state",
        [
            pytest.param({"role": "retail", "verification_status": "unverified", "is_verified": False}, id="retail"),
            pytest.param({"verification_status": "pending", "is_verified": False}, id="pending"),
            pytest.param({"verification_status": "unverified", "is_verified": False}, id="rejected"),
            pytest.param({"verification_status": "verified", "is_verified": False}, id="verified-status-without-flag"),
            pytest.param(
                {"role": User.ROLE_UNREGISTERED, "verification_status": "unverified", "is_verified": False},
                id="1c-record",
            ),
        ],
    )
    def test_role_is_read_only_outside_verified_b2b(self, manager_client, manager, state, posted_role):
        target = make_client(manager, **state)
        role_before = target.role

        adminform = manager_client.get(change_url(target)).context["adminform"]
        assert "role" not in adminform.form.fields
        assert "role" in adminform.readonly_fields

        response = self.post_role(manager_client, target, posted_role, phone="+79001112266")

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.phone == "+79001112266"
        assert target.role == role_before
        assert not audit_records(target).exists()

    def test_foreign_client_answers_404(self, manager_client, other_manager):
        foreign = make_client(other_manager, role="wholesale_level1")

        response = manager_client.post(change_url(foreign), {"role": "wholesale_level3", "_save": "Сохранить"})

        assert response.status_code == 404
        foreign.refresh_from_db()
        assert foreign.role == "wholesale_level1"
        assert not audit_records(foreign).exists()

    def test_same_role_writes_nothing(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level1")

        assert self.post_role(manager_client, target, "wholesale_level1").status_code == 302

        assert not audit_records(target).exists()

    def test_validation_error_keeps_role_input(self, manager_client, manager):
        # is_valid() пишет выбранную роль в объект: по ней «Розница» убрала бы
        # поле из перерисованной формы, и повторный POST упал бы без роли.
        target = make_client(manager, role="wholesale_level1")
        email = target.email

        response = self.post_role(manager_client, target, "retail", email="не-почта")

        assert response.status_code == 200
        adminform = response.context["adminform"]
        assert "email" in adminform.form.errors
        assert "role" not in adminform.readonly_fields
        content = response.content.decode()
        assert 'name="role"' in content
        assert 'name="initial-role" value="wholesale_level1"' in content
        target.refresh_from_db()
        assert target.role == "wholesale_level1"
        assert not audit_records(target).exists()

        retry = form_payload(response)
        retry.update({"email": email, "_save": "Сохранить"})
        assert retry["role"] == "retail"
        assert manager_client.post(change_url(target), retry).status_code == 302
        target.refresh_from_db()
        assert target.role == "retail"
        assert audit_records(target, "change_user_role").count() == 1

    def test_old_role_is_read_under_lock(self, manager_client, manager):
        # Импорт 1С сменил роль, пока форма была открыта: «было» — его значение,
        # а не то, что менеджер видел в форме.
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        User.objects.filter(pk=target.pk).update(role="wholesale_level2")
        data.update({"role": "wholesale_level3", "_save": "Сохранить"})

        assert manager_client.post(change_url(target), data).status_code == 302

        changes = audit_records(target, "change_user_role").get().details["changes"]
        assert (changes["old"], changes["new"]) == ("wholesale_level2", "wholesale_level3")

    def test_stale_card_keeps_role_changed_after_opening(self, manager_client, manager):
        # Менеджер правит только телефон: старая роль из формы не откатывает импорт.
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        assert data["initial-role"] == "wholesale_level1"
        User.objects.filter(pk=target.pk).update(role="wholesale_level2")
        data.update({"phone": "+79001112277", "_save": "Сохранить"})

        assert manager_client.post(change_url(target), data).status_code == 302

        target.refresh_from_db()
        assert target.phone == "+79001112277"
        assert target.role == "wholesale_level2"
        assert not audit_records(target, "change_user_role").exists()

    def test_post_without_role_keeps_it(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        del data["role"], data["initial-role"]
        data.update({"phone": "+79001112288", "_save": "Сохранить"})

        assert manager_client.post(change_url(target), data).status_code == 302

        target.refresh_from_db()
        assert target.phone == "+79001112288"
        assert target.role == "wholesale_level1"
        assert not audit_records(target, "change_user_role").exists()

    def test_redrawn_form_without_role_shows_current_role(self, manager_client, manager):
        # Ошибка в другом поле: select без значения показал бы первую опцию
        # «Розница», и повторное сохранение понизило бы клиента.
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        email = data["email"]
        del data["role"], data["initial-role"]
        data.update({"email": "не-почта", "_save": "Сохранить"})

        response = manager_client.post(change_url(target), data)

        assert response.status_code == 200
        assert '<option value="wholesale_level1" selected>' in response.content.decode()
        retry = form_payload(response)
        retry.update({"email": email, "_save": "Сохранить"})
        assert manager_client.post(change_url(target), retry).status_code == 302
        target.refresh_from_db()
        assert target.role == "wholesale_level1"
        assert not audit_records(target, "change_user_role").exists()

    def test_empty_role_keeps_it(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level1")

        assert self.post_role(manager_client, target, "").status_code == 302

        target.refresh_from_db()
        assert target.role == "wholesale_level1"
        assert not audit_records(target, "change_user_role").exists()

    def test_empty_role_in_stale_form_writes_nothing(self, manager_client, manager):
        # initial-role отличается от строки, `role` попадает в changed_data, но смены нет.
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        User.objects.filter(pk=target.pk).update(role="wholesale_level2")
        data.update({"role": "", "_save": "Сохранить"})

        assert manager_client.post(change_url(target), data).status_code == 302

        target.refresh_from_db()
        assert target.role == "wholesale_level2"
        assert not audit_records(target, "change_user_role").exists()

    def test_client_turned_retail_after_form_opened_stays_retail(self, manager_client, manager):
        target = make_client(manager, role="wholesale_level1")
        data = form_payload(manager_client.get(change_url(target)))
        User.objects.filter(pk=target.pk).update(role="retail")
        data.update({"role": "wholesale_level3", "_save": "Сохранить"})

        assert manager_client.post(change_url(target), data).status_code == 302

        target.refresh_from_db()
        assert target.role == "retail"
        assert not audit_records(target).exists()

    def test_role_change_holds_row_lock(self, manager_client, manager, prod_like_requests, locked_at_save):
        target = make_client(manager, role="wholesale_level1")

        assert self.post_role(manager_client, target, "wholesale_level3").status_code == 302

        assert locked_at_save[target.pk] is True
        assert audit_records(target, "change_user_role").count() == 1

    @pytest.mark.parametrize(
        "link",
        [
            pytest.param(lambda: {"onec_id": f"1C-{get_unique_suffix()}"}, id="onec_id"),
            pytest.param(lambda: {"onec_guid": uuid.uuid4()}, id="onec_guid"),
        ],
    )
    def test_1c_hint_is_shown_only_for_linked_client(self, manager_client, manager, link):
        hint = "обмен может вернуть роль"

        linked = manager_client.get(change_url(make_client(manager, **link())))
        plain = manager_client.get(change_url(make_client(manager)))

        assert hint in linked.context["adminform"].form.fields["role"].help_text
        assert hint in linked.content.decode()
        assert hint not in plain.content.decode()

    @pytest.mark.parametrize(
        "new_role, expected_price",
        [("wholesale_level3", Decimal("700.00")), ("retail", Decimal("1000.00"))],
    )
    def test_catalog_shows_prices_of_new_role(self, manager_client, manager, new_role, expected_price):
        suffix = get_unique_suffix()
        product = Product.objects.create(
            name=f"Товар-{suffix}",
            slug=f"product-{suffix}",
            category=Category.objects.create(name=f"Кат-{suffix}", slug=f"cat-{suffix}"),
            brand=Brand.objects.create(name=f"Бренд-{suffix}", slug=f"brand-{suffix}"),
            onec_id=f"1c-{suffix}",
            is_active=True,
        )
        ProductVariant.objects.create(
            product=product,
            sku=f"SKU-{suffix}",
            onec_id=f"var-{suffix}",
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            opt3_price=Decimal("700.00"),
            stock_quantity=50,
            is_active=True,
        )
        target = make_client(manager, role="wholesale_level1")

        def catalog_price() -> Decimal:
            api = APIClient()
            api.force_authenticate(user=User.objects.get(pk=target.pk))
            response = api.get(reverse("products:product-detail", kwargs={"slug": product.slug}))
            assert response.status_code == 200
            return Decimal(str(response.data["variants"][0]["current_price"]))

        assert catalog_price() == Decimal("900.00")

        assert self.post_role(manager_client, target, new_role).status_code == 302

        assert catalog_price() == expected_price

    def test_supervisor_changes_any_client_and_sees_journal(self, client, other_manager):
        supervisor = make_staff_member(SUPERVISORS_GROUP, first_name="Ирина", last_name="Руководитель")
        client.force_login(supervisor)
        target = make_client(other_manager, role="wholesale_level1")

        assert self.post_role(client, target, "trainer").status_code == 302

        target.refresh_from_db()
        assert target.role == "trainer"
        assert audit_records(target, "change_user_role").get().user == supervisor
        html = client.get("/supervisor/journal/").content.decode()
        assert "Смена роли клиента" in html
        assert "Оптовик уровень 1 → Тренер/Фитнес-клуб" in html
        assert f"Ирина Руководитель ({supervisor.email})" in html


class TestLinksStayInSection:
    """AC8 — ни одна ссылка и ни один редирект не ведут в /admin/."""

    @staticmethod
    def assert_no_admin_links(response) -> None:
        assert response.status_code == 200
        assert 'href="/admin/' not in response.content.decode()

    def test_pages_have_no_admin_links(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)
        make_1c_record(applicant.tax_id)
        target = make_client(manager)

        # Сохранение карточки создаёт LogEntry: без своей главной (решение 13)
        # блок «Последние действия» вёл бы в /admin/users/user/<id>/change/.
        data = form_payload(manager_client.get(change_url(target)))
        data["_save"] = "Сохранить"
        response = manager_client.post(change_url(target), data)
        assert response.status_code == 302
        assert response.url.startswith("/manager/")
        assert LogEntry.objects.filter(user=manager).exists()

        index = manager_client.get(INDEX_URL)
        self.assert_no_admin_links(index)
        assert "recent-actions-module" not in index.content.decode()

        self.assert_no_admin_links(manager_client.get(CHANGELIST_URL))
        self.assert_no_admin_links(manager_client.get(change_url(applicant)))
        self.assert_no_admin_links(manager_client.get(verify_url(applicant)))
        self.assert_no_admin_links(manager_client.get(password_url(target)))
        link_page = post_action(manager_client, "link_1c_customer", applicant, follow=False)
        self.assert_no_admin_links(link_page)
        assert "/manager/" in link_page.content.decode()

        # Кнопка «Подтвердить заявку» в карточке и ссылка в списке — в разделе.
        assert verify_url(applicant) in manager_client.get(change_url(applicant)).content.decode()
        assert verify_url(applicant) in manager_client.get(CHANGELIST_URL).content.decode()

    def test_change_with_continue_stays_in_section(self, manager_client, manager):
        target = make_client(manager)
        data = form_payload(manager_client.get(change_url(target)))
        data["_continue"] = "1"

        response = manager_client.post(change_url(target), data)

        assert response.status_code == 302
        assert response.url.startswith(change_url(target))

    def test_link_warning_after_approve_points_to_section(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        make_1c_record(applicant.tax_id)

        response = post_action(manager_client, "approve_b2b_users", applicant)

        texts = message_texts(response)
        assert any(change_url(applicant) in text for text in texts)
        assert not any("/admin/" in text for text in texts)


class TestViewOnlyPermissions:
    """AC9 — внутренние проверки права change в разделе (долг VG1 стори 42.1)."""

    @pytest.fixture(autouse=True)
    def view_only_group(self):
        group = Group.objects.get(name=MANAGERS_GROUP)
        view_only = [Permission.objects.get(content_type__app_label="users", codename="view_user")]
        full = list(group.permissions.all())
        group.permissions.set(view_only)
        return SimpleNamespace(group=group, full=full, view_only=view_only)

    def test_card_post_is_forbidden(self, manager_client, manager, view_only_group):
        own = make_client(manager)
        make_company(own)
        address = make_address(own)
        # Форма, какую отправил бы менеджер с полными правами, — снята до урезания прав.
        view_only_group.group.permissions.set(view_only_group.full)
        response = manager_client.get(change_url(own))
        prefixes = inline_prefixes(response)
        data = form_payload(response)
        view_only_group.group.permissions.set(view_only_group.view_only)
        before = User.objects.filter(pk=own.pk).values().get()
        related_before = related_snapshot(own)
        data.update(
            {
                "first_name": "Подмена",
                "phone": "+79001112233",
                "role": "wholesale_level3",
                f"{prefixes[Company]}-0-legal_name": "ООО Подмена",
                f"{prefixes[Address]}-{form_index(data, prefixes[Address], address)}-city": "Подмена",
                "_save": "Сохранить",
            }
        )

        data.pop("is_active", None)  # снятый флаг — попытка заблокировать

        response = manager_client.post(change_url(own), data)

        assert response.status_code == 403
        assert User.objects.filter(pk=own.pk).values().get() == before
        assert related_snapshot(own) == related_before
        assert not audit_records(own).exists()
        assert not LogEntry.objects.filter(object_id=str(own.pk)).exists()

    def test_card_is_read_only_without_verify_button(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)

        response = manager_client.get(change_url(applicant))

        assert response.status_code == 200
        assert response.context["show_verify_b2b_button"] is False
        assert not response.context["has_change_permission"]
        assert verify_url(applicant) not in response.content.decode()

    def test_role_has_no_input_without_change_permission(self, manager_client, manager):
        response = manager_client.get(change_url(make_client(manager)))

        assert response.status_code == 200
        assert 'name="role"' not in response.content.decode()

    def test_verify_and_password_are_forbidden(self, manager_client, manager):
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)

        assert manager_client.get(verify_url(applicant)).status_code == 403
        response = manager_client.post(
            verify_url(applicant), {"confirm": "on", "confirm_without_1c": "on", "role": "wholesale_level1"}
        )
        assert response.status_code == 403
        assert manager_client.post(verify_url(applicant), {"_reject": "1"}).status_code == 403
        assert manager_client.get(password_url(applicant)).status_code == 403
        response = manager_client.post(
            password_url(applicant),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )
        assert response.status_code == 403

        applicant.refresh_from_db()
        assert applicant.verification_status == "pending"
        assert applicant.check_password(PASSWORD)
        assert not audit_records(applicant).exists()

    @pytest.mark.parametrize(
        "action", ["approve_b2b_users", "reject_b2b_users", "block_users", "unblock_users", "link_1c_customer"]
    )
    def test_actions_are_unavailable(self, manager_client, manager, action):
        target = make_client(manager, verification_status="pending", is_verified=False)

        changelist = manager_client.get(CHANGELIST_URL)
        assert changelist.status_code == 200
        assert not changelist.context["action_form"]

        post_action(manager_client, action, target)

        changed = User.objects.get(pk=target.pk)
        assert changed.is_active == target.is_active
        assert changed.verification_status == "pending"
        assert not audit_records(target).exists()


class TestClientMovedAway:
    """AC10 — клиент ушёл к другому менеджеру после правки ИНН."""

    def test_redirect_to_changelist_with_message(self, manager_client, manager, other_manager):
        ManagerRoutingRule.objects.create(match_type="inn_region", match_value="23", manager=manager)
        ManagerRoutingRule.objects.create(match_type="inn_region", match_value="77", manager=other_manager)
        # Клиент, созданный после правил, получает ответственного хуком 42.2.
        client_user = User.objects.create_user(
            email=f"client_{get_unique_suffix()}@example.com",
            password=PASSWORD,
            role="wholesale_level1",
            company_name="ООО Регион 23",
            tax_id=region_tax_id("23"),
            verification_status="verified",
            is_verified=True,
        )
        assert User.objects.get(pk=client_user.pk).responsible_manager == manager

        data = form_payload(manager_client.get(change_url(client_user)))
        data["tax_id"] = region_tax_id("77")
        data["_continue"] = "1"
        response = manager_client.post(change_url(client_user), data)

        assert response.status_code == 302
        assert response.url == CHANGELIST_URL
        client_user.refresh_from_db()
        assert client_user.tax_id == data["tax_id"]
        assert client_user.responsible_manager == other_manager
        texts = message_texts(manager_client.get(response.url))
        assert any(f"передан менеджеру {other_manager.email} по правилу региона" in text for text in texts)


def in_other_connection(func: Any) -> Any:
    """Выполнить `func` в отдельном потоке — своё соединение и своя транзакция."""
    outcome: dict[str, Any] = {}

    def run() -> None:
        try:
            outcome["result"] = func()
        except BaseException as exc:  # noqa: BLE001 — исключение возвращается в тест
            outcome["error"] = exc
        finally:
            connections.close_all()

    thread = threading.Thread(target=run)
    thread.start()
    thread.join(timeout=30)
    assert not thread.is_alive(), "второе соединение зависло"
    if "error" in outcome:
        raise outcome["error"]
    return outcome["result"]


def row_is_locked(pk: int) -> bool:
    """
    Строку пользователя держит чужая транзакция: `FOR UPDATE NOWAIT` из второго соединения.

    Блокировкой считается только отказ NOWAIT — SQLSTATE `55P03`
    (lock_not_available). Любая другая ошибка пробрасывается: иначе сбой
    пробного соединения подтвердил бы блокировку, которой нет.
    """

    def probe() -> bool:
        try:
            with transaction.atomic():
                User.objects.select_for_update(nowait=True).filter(pk=pk).exists()
        except DatabaseError as exc:
            if getattr(exc.__cause__, "pgcode", None) == LOCK_NOT_AVAILABLE:
                return True
            raise
        return False

    return bool(in_other_connection(probe))


@pytest.fixture
def prod_like_requests(monkeypatch):
    """
    Запросы без `ATOMIC_REQUESTS`, как на production.

    Тестовые настройки оборачивают каждый запрос в транзакцию: там блокировка
    строки работала бы и без собственной транзакции раздела.
    """
    monkeypatch.setitem(connections.settings[DEFAULT_DB_ALIAS], "ATOMIC_REQUESTS", False)


@pytest.fixture
def locked_at_save(monkeypatch) -> dict[int, bool]:
    """`{pk: строка заблокирована}` в момент первого `User.save()` этой записи."""
    seen: dict[int, bool] = {}
    original_save = User.save

    def save(self: User, *args: Any, **kwargs: Any) -> None:
        if self.pk is not None and self.pk not in seen:
            seen[self.pk] = row_is_locked(self.pk)
        original_save(self, *args, **kwargs)

    monkeypatch.setattr(User, "save", save)
    return seen


def waits_for_lock(pid: int | None) -> bool:
    """Соединение `pid` стоит в очереди на блокировку (`pg_stat_activity.wait_event_type = 'Lock'`)."""
    with connection.cursor() as cursor:
        # Статистика активности кэшируется на транзакцию — сбросить снимок.
        cursor.execute("SELECT pg_stat_clear_snapshot()")
        cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [pid])
        row = cursor.fetchone()
    return bool(row) and row[0] == "Lock"


class BackgroundWrite:
    """
    Запись из второго соединения, запущенная посреди запроса раздела.

    `start()` возвращается, когда запись либо завершилась, либо встала в
    очередь на блокировку строки (`pg_stat_activity.wait_event_type = 'Lock'`) —
    без угадывания задержек. `blocked` — запись ждала: вклиниться между
    чтением клиента и записью раздела она не могла и применится после.
    """

    def __init__(self, func: Any) -> None:
        self.func = func
        self.pid: int | None = None
        self.blocked = False
        self.outcome: dict[str, Any] = {}
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._run)

    def _run(self) -> None:
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                self.pid = cursor.fetchone()[0]
            self.ready.set()
            self.outcome["result"] = self.func()
        except BaseException as exc:  # noqa: BLE001 — исключение возвращается в тест
            self.outcome["error"] = exc
        finally:
            self.ready.set()
            connections.close_all()

    def start(self) -> None:
        self.thread.start()
        assert self.ready.wait(timeout=10), "второе соединение не открылось"
        deadline = time.monotonic() + 10
        while self.thread.is_alive() and time.monotonic() < deadline:
            if waits_for_lock(self.pid):
                self.blocked = True
                return
            time.sleep(0.01)
        assert not self.thread.is_alive(), "вторая запись не завершилась и не ждёт блокировку"

    def join(self) -> None:
        self.thread.join(timeout=30)
        assert not self.thread.is_alive(), "вторая запись зависла"
        if "error" in self.outcome:
            raise self.outcome["error"]

    def join_if_started(self) -> None:
        """Для `finally`: запрос мог упасть раньше, чем запустил запись (R42.4-29)."""
        if self.thread.ident is not None:
            self.join()


def transfer_to(user: User, manager: User) -> BackgroundWrite:
    return BackgroundWrite(lambda: User.objects.filter(pk=user.pk).update(responsible_manager=manager))


class TestTransferDuringWrite:
    """
    R42.4-1, R42.4-4…6 — передача клиента или импорт между чтением и записью.

    Строка клиента блокируется до чтения объекта: передача, начатая посреди
    записи раздела, ждёт её конца и применяется после, а не теряется; клиент,
    переданный до блокировки, — 404. Устаревший объект не затирает ни
    ответственного, ни скрытые поля.
    """

    def test_card_save_after_transfer_answers_404(self, manager_client, manager, other_manager, prod_like_requests):
        own = make_client(manager, manual=False)
        phone_before = own.phone
        data = form_payload(manager_client.get(change_url(own)))
        data.update({"phone": "+79005556677", "_save": "Сохранить"})
        # Форма открыта, пересчёт передаёт клиента B до отправки.
        in_other_connection(lambda: User.objects.filter(pk=own.pk).update(responsible_manager=other_manager))

        response = manager_client.post(change_url(own), data)

        assert response.status_code == 404
        own.refresh_from_db()
        assert own.responsible_manager == other_manager
        assert own.phone == phone_before
        assert not audit_records(own).exists()

    def test_card_keeps_concurrent_import(self, manager_client, manager, prod_like_requests):
        # R42.4-5: импорт 1С посреди сохранения карточки не затирается её объектом.
        own = make_client(manager)
        data = form_payload(manager_client.get(change_url(own)))
        data.update({"phone": "+79005556679", "_save": "Сохранить"})
        imported_id = f"IMPORTED-{get_unique_suffix()}"
        import_1c = BackgroundWrite(lambda: User.objects.filter(pk=own.pk).update(onec_id=imported_id))
        original_save_form = ManagerClientAdmin.save_form

        def import_then_save_form(self: ManagerClientAdmin, request: Any, form: Any, change: bool) -> Any:
            import_1c.start()
            return original_save_form(self, request, form, change)

        try:
            with patch.object(ManagerClientAdmin, "save_form", import_then_save_form):
                response = manager_client.post(change_url(own), data)
        finally:
            import_1c.join_if_started()

        assert response.status_code == 302
        assert import_1c.blocked
        own.refresh_from_db()
        assert own.onec_id == imported_id
        assert own.phone == "+79005556679"

    def test_password_change_does_not_undo_transfer(self, manager_client, manager, other_manager, prod_like_requests):
        # R42.4-6: полное save() формы пароля не возвращает прежнего ответственного.
        own = make_client(manager)
        transfer = transfer_to(own, other_manager)
        form_class = ManagerClientAdmin.change_password_form
        original_save = form_class.save

        def transfer_then_save(form: Any, *args: Any, **kwargs: Any) -> Any:
            transfer.start()
            return original_save(form, *args, **kwargs)

        try:
            with patch.object(form_class, "save", transfer_then_save):
                response = manager_client.post(
                    password_url(own),
                    {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
                )
        finally:
            transfer.join_if_started()

        assert response.status_code == 302
        assert transfer.blocked
        own.refresh_from_db()
        assert own.responsible_manager == other_manager
        assert own.check_password(NEW_PASSWORD)

    @pytest.mark.parametrize(
        "service, payload",
        [
            ("verify_b2b_application", {"confirm": "on", "confirm_without_1c": "on", "role": "wholesale_level1"}),
            ("reject_b2b_application", {"_reject": "1"}),
        ],
    )
    def test_verify_page_waits_for_transfer(
        self, manager_client, manager, other_manager, prod_like_requests, service, payload
    ):
        # R42.4-6: решение по заявке принимается, пока клиент ещё у менеджера.
        applicant = make_client(manager, verification_status="pending", is_verified=False, is_active=False)
        transfer = transfer_to(applicant, other_manager)
        original = getattr(users_admin, service)

        def transfer_then_call(**kwargs: Any) -> Any:
            transfer.start()
            return original(**kwargs)

        try:
            with patch.object(users_admin, service, transfer_then_call):
                response = manager_client.post(verify_url(applicant), payload)
        finally:
            transfer.join_if_started()

        assert response.status_code == 302
        assert transfer.blocked
        if service == "reject_b2b_application":
            # Отказ удалил заявителя под блокировкой: передача ждала и ничего не нашла.
            assert not User.objects.filter(pk=applicant.pk).exists()
            return
        applicant.refresh_from_db()
        assert applicant.responsible_manager == other_manager

    def test_link_after_transfer_answers_404(self, manager_client, manager, other_manager, prod_like_requests):
        # R42.4-6: привязка перепроверяет принадлежность под блокировкой.
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        source = make_1c_record(applicant.tax_id)
        original_find = users_admin.find_link_candidates

        def transfer_then_find(target: User) -> list[User]:
            # Цель уже прочитана действием, привязка впереди.
            in_other_connection(lambda: User.objects.filter(pk=applicant.pk).update(responsible_manager=other_manager))
            return original_find(target)

        with patch.object(users_admin, "find_link_candidates", transfer_then_find):
            response = post_action(
                manager_client,
                "link_1c_customer",
                applicant,
                follow=False,
                apply="1",
                candidate=f"{source.pk}:{source.onec_id}",
            )

        assert response.status_code == 404
        applicant.refresh_from_db()
        assert applicant.onec_id is None
        assert applicant.responsible_manager == other_manager
        assert not audit_records(applicant).exists()

    def test_link_rechecks_scope_under_lock(self, manager_client, manager, other_manager, prod_like_requests):
        # R42.4-23: клиента передали после успешной предварительной проверки
        # принадлежности (exists() в _lock_link_rows), но до захвата строк.
        # Отсечь его может только повторная проверка выборкой раздела в самом
        # запросе блокировки цели.
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        source = make_1c_record(applicant.tax_id)
        source_before = User.objects.filter(pk=source.pk).values().get()
        original_lock = ManagerClientAdmin._lock_link_rows
        original_exists = QuerySet.exists
        prechecked: list[bool] = []

        def exists_then_transfer(queryset: QuerySet) -> bool:
            result = original_exists(queryset)
            if not prechecked:
                prechecked.append(result)
                in_other_connection(
                    lambda: User.objects.filter(pk=applicant.pk).update(responsible_manager=other_manager)
                )
            return result

        def lock_with_transfer_after_precheck(
            self: ManagerClientAdmin, request: Any, target: User, source_pks: Any
        ) -> None:
            with patch.object(QuerySet, "exists", exists_then_transfer):
                original_lock(self, request, target, source_pks)

        with patch.object(ManagerClientAdmin, "_lock_link_rows", lock_with_transfer_after_precheck):
            response = post_action(
                manager_client,
                "link_1c_customer",
                applicant,
                follow=False,
                apply="1",
                candidate=f"{source.pk}:{source.onec_id}",
            )

        # Передача пришлась именно на интервал: предварительная проверка своего клиента пропустила.
        assert prechecked == [True]
        assert response.status_code == 404
        applicant.refresh_from_db()
        assert applicant.onec_id is None
        assert applicant.responsible_manager == other_manager
        assert User.objects.filter(pk=source.pk).values().get() == source_before
        assert not audit_records(applicant).exists()

    def test_link_locks_source_and_target_in_pk_order(self, manager_client, manager, prod_like_requests):
        # R42.4-12: привязка захватывает источник и цель по возрастанию pk, как
        # сервис и пересчёт ответственных. Вторая транзакция держит источник
        # (меньший pk) и, когда привязка встала за ним в очередь, берёт цель.
        # Предварительная блокировка одной цели дала бы взаимную блокировку.
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        applicant = make_client(manager, tax_id=tax_id, verification_status="pending", is_verified=False)
        assert source.pk < applicant.pk
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            request_pid = cursor.fetchone()[0]
        source_held = threading.Event()

        def write_in_pk_order() -> None:
            with transaction.atomic():
                User.objects.filter(pk=source.pk).update(phone="+79005550101")
                source_held.set()
                deadline = time.monotonic() + 10
                while not waits_for_lock(request_pid):
                    assert time.monotonic() < deadline, "привязка не встала в очередь за строкой источника"
                    time.sleep(0.01)
                User.objects.filter(pk=applicant.pk).update(phone="+79005550102")

        writer = BackgroundWrite(write_in_pk_order)
        writer.thread.start()
        assert source_held.wait(timeout=10), "вторая транзакция не захватила источник"
        try:
            response = post_action(
                manager_client,
                "link_1c_customer",
                applicant,
                follow=False,
                apply="1",
                candidate=f"{source.pk}:{source.onec_id}",
            )
        finally:
            writer.join()

        assert response.status_code == 302
        applicant.refresh_from_db()
        source.refresh_from_db()
        assert applicant.onec_id is not None
        assert applicant.phone == "+79005550102"
        assert source.onec_id is None
        assert source.phone == "+79005550101"
        assert audit_records(applicant, "link_1c_customer").count() == 1

    @pytest.mark.parametrize(
        "actions, index",
        [
            (["block_users", "link_1c_customer"], "0"),
            # R42.4-34: блокировка из нижней формы списка, привязка — в верхней.
            (["link_1c_customer", "block_users"], "1"),
        ],
    )
    def test_second_action_field_does_not_skip_lock(
        self, manager_client, manager, prod_like_requests, locked_at_save, actions, index
    ):
        # R42.4-4: Django выполняет значение action по index, исключение привязки — тоже.
        own = make_client(manager)

        response = manager_client.post(
            CHANGELIST_URL,
            {"action": actions, "index": index, "_selected_action": [str(own.pk)]},
            follow=True,
        )

        assert response.status_code == 200
        assert locked_at_save[own.pk] is True
        own.refresh_from_db()
        assert own.is_active is False
        assert audit_records(own, "block_user").count() == 1

    def test_card_save_holds_row_lock(self, manager_client, manager, prod_like_requests, locked_at_save):
        own = make_client(manager)
        data = form_payload(manager_client.get(change_url(own)))
        data.update({"phone": "+79005556678", "_save": "Сохранить"})

        response = manager_client.post(change_url(own), data)

        assert response.status_code == 302
        assert locked_at_save[own.pk] is True
        own.refresh_from_db()
        assert own.phone == "+79005556678"

    @pytest.mark.parametrize(
        "action, overrides",
        [
            ("approve_b2b_users", {"verification_status": "pending", "is_verified": False, "is_active": False}),
            ("block_users", {}),
            ("unblock_users", {"is_active": False}),
        ],
    )
    def test_actions_hold_row_lock(
        self, manager_client, manager, prod_like_requests, locked_at_save, action, overrides
    ):
        own = make_client(manager, **overrides)
        before = audit_records(own).count()

        response = post_action(manager_client, action, own)

        assert response.status_code == 200
        assert locked_at_save[own.pk] is True
        assert audit_records(own).count() == before + 1

    def test_reject_action_holds_row_lock_at_delete(
        self, manager_client, manager, prod_like_requests, locked_at_delete
    ):
        own = make_client(manager, verification_status="pending", is_verified=False)

        response = post_action(manager_client, "reject_b2b_users", own)

        assert response.status_code == 200
        assert locked_at_delete[own.pk] is True
        assert not User.objects.filter(pk=own.pk).exists()
        assert audit_records(own, "reject_b2b").count() == 1


@pytest.fixture
def locked_at_delete(monkeypatch) -> dict[int, bool]:
    """`{pk: строка заблокирована}` в момент первого `User.delete()` этой записи."""
    seen: dict[int, bool] = {}
    original_delete = User.delete

    def delete(self: User, *args: Any, **kwargs: Any) -> Any:
        if self.pk is not None and self.pk not in seen:
            seen[self.pk] = row_is_locked(self.pk)
        return original_delete(self, *args, **kwargs)

    monkeypatch.setattr(User, "delete", delete)
    return seen


@contextmanager
def row_held_elsewhere(pk: int) -> Iterator[None]:
    """
    Строку пользователя держит транзакция второго соединения.

    Соединению теста на это время задан `lock_timeout`: запрос, который
    попытается заблокировать эту строку, не повиснет, а упадёт с
    `OperationalError` — признак лишней блокировки.
    """
    acquired = threading.Event()
    release = threading.Event()
    outcome: dict[str, Any] = {}

    def hold() -> None:
        try:
            with transaction.atomic():
                list(User.objects.select_for_update().filter(pk=pk).values_list("pk", flat=True))
                acquired.set()
                release.wait(timeout=30)
        except BaseException as exc:  # noqa: BLE001 — исключение возвращается в тест
            outcome["error"] = exc
        finally:
            acquired.set()
            connections.close_all()

    thread = threading.Thread(target=hold)
    thread.start()
    assert acquired.wait(timeout=10), "второе соединение не открылось"
    try:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '2s'")
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("RESET lock_timeout")
        release.set()
        thread.join(timeout=30)
    assert not thread.is_alive(), "второе соединение зависло"
    if "error" in outcome:
        raise outcome["error"]


def post_without_locking(client, url: str, data: dict[str, Any]):
    try:
        return client.post(url, data)
    except OperationalError as exc:
        pytest.fail(f"{url}: запрос пытался заблокировать недоступную ему строку ({exc})")


# Изменяющие POST по клиенту, которые блокируют его строку.
CLIENT_WRITE_POSTS = [
    pytest.param(change_url, {"phone": "+79005550000", "_save": "Сохранить"}, id="card"),
    pytest.param(
        password_url, {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD}, id="password"
    ),
    pytest.param(verify_url, {"confirm": "on", "confirm_without_1c": "on", "role": "wholesale_level1"}, id="verify"),
    pytest.param(verify_url, {"_reject": "1"}, id="reject"),
]


class TestNoLockWithoutAccess:
    """
    R42.4-9 — запрос без доступа к клиенту не блокирует его строку.

    Строку клиента держит другая транзакция. Запрос к чужому клиенту и запрос
    без права change сразу получают отказ, а не ждут её освобождения.
    """

    @pytest.mark.parametrize("url_for, data", CLIENT_WRITE_POSTS)
    def test_foreign_client_answers_404_without_lock(
        self, manager_client, other_manager, prod_like_requests, url_for, data
    ):
        foreign = make_client(other_manager, verification_status="pending", is_verified=False, is_active=False)
        before = User.objects.filter(pk=foreign.pk).values().get()

        with row_held_elsewhere(foreign.pk):
            response = post_without_locking(manager_client, url_for(foreign), data)

        assert response.status_code == 404
        assert User.objects.filter(pk=foreign.pk).values().get() == before
        assert not audit_records(foreign).exists()

    @pytest.mark.parametrize("url_for, data", CLIENT_WRITE_POSTS)
    def test_view_only_answers_403_without_lock(self, manager_client, manager, prod_like_requests, url_for, data):
        Group.objects.get(name=MANAGERS_GROUP).permissions.set(
            [Permission.objects.get(content_type__app_label="users", codename="view_user")]
        )
        own = make_client(manager, verification_status="pending", is_verified=False, is_active=False)
        before = User.objects.filter(pk=own.pk).values().get()

        with row_held_elsewhere(own.pk):
            response = post_without_locking(manager_client, url_for(own), data)

        assert response.status_code == 403
        assert User.objects.filter(pk=own.pk).values().get() == before
        assert not audit_records(own).exists()

    @pytest.mark.parametrize("url_for, data", CLIENT_WRITE_POSTS)
    def test_client_assigned_after_empty_lock_answers_404(
        self, manager_client, manager, other_manager, prod_like_requests, url_for, data
    ):
        # R42.4-10: пустая блокировка — отказ. Клиента передают менеджеру сразу
        # после неё: читать и записывать его строку без блокировки запрос не должен.
        target = make_client(other_manager, verification_status="pending", is_verified=False, is_active=False)
        expected = User.objects.filter(pk=target.pk).values().get()
        expected["responsible_manager_id"] = manager.pk
        original_lock_client = ManagerClientAdmin._lock_client

        def lock_then_assign(self: ManagerClientAdmin, request: Any, object_id: str) -> None:
            try:
                original_lock_client(self, request, object_id)
            finally:
                in_other_connection(lambda: User.objects.filter(pk=target.pk).update(responsible_manager=manager))

        with patch.object(ManagerClientAdmin, "_lock_client", lock_then_assign):
            response = manager_client.post(url_for(target), data)

        assert response.status_code == 404
        assert User.objects.filter(pk=target.pk).values().get() == expected
        assert not audit_records(target).exists()

    def test_link_to_transferred_client_answers_404_without_lock(
        self, manager_client, manager, other_manager, prod_like_requests
    ):
        # R42.4-11: цель, уже переданную другому менеджеру, привязка отсекает
        # до общей блокировки и не ждёт её строку, которую держит чужая транзакция.
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        source = make_1c_record(applicant.tax_id)
        original_find = users_admin.find_link_candidates

        with ExitStack() as held:

            def transfer_hold_then_find(target: User) -> list[User]:
                # Цель уже прочитана действием, привязка впереди.
                in_other_connection(
                    lambda: User.objects.filter(pk=applicant.pk).update(responsible_manager=other_manager)
                )
                held.enter_context(row_held_elsewhere(applicant.pk))
                return original_find(target)

            with patch.object(users_admin, "find_link_candidates", transfer_hold_then_find):
                response = post_without_locking(
                    manager_client,
                    CHANGELIST_URL,
                    {
                        "action": "link_1c_customer",
                        "_selected_action": [str(applicant.pk)],
                        "apply": "1",
                        "candidate": f"{source.pk}:{source.onec_id}",
                    },
                )

        assert response.status_code == 404
        applicant.refresh_from_db()
        assert applicant.onec_id is None
        assert applicant.responsible_manager == other_manager
        assert not audit_records(applicant).exists()

    def test_link_target_transferred_right_before_lock_answers_404_without_lock(
        self, manager_client, manager, other_manager, prod_like_requests
    ):
        # R42.4-14: передача завершилась прямо перед захватом строк привязки, а
        # строку цели держит чужая транзакция. Цель захватывается только из
        # выборки раздела — запрос не ждёт её строку, а отвечает 404.
        applicant = make_client(manager, verification_status="pending", is_verified=False)
        source = make_1c_record(applicant.tax_id)
        original_lock = ManagerClientAdmin._lock_link_rows

        with ExitStack() as held:

            def transfer_hold_then_lock(self: ManagerClientAdmin, request: Any, target: User, source_pks: Any) -> None:
                in_other_connection(
                    lambda: User.objects.filter(pk=applicant.pk).update(responsible_manager=other_manager)
                )
                held.enter_context(row_held_elsewhere(applicant.pk))
                original_lock(self, request, target, source_pks)

            with patch.object(ManagerClientAdmin, "_lock_link_rows", transfer_hold_then_lock):
                response = post_without_locking(
                    manager_client,
                    CHANGELIST_URL,
                    {
                        "action": "link_1c_customer",
                        "_selected_action": [str(applicant.pk)],
                        "apply": "1",
                        "candidate": f"{source.pk}:{source.onec_id}",
                    },
                )

        assert response.status_code == 404
        applicant.refresh_from_db()
        assert applicant.onec_id is None
        assert applicant.responsible_manager == other_manager
        assert not audit_records(applicant).exists()

    def test_link_to_transferred_client_skips_held_source_with_lower_pk(
        self, manager_client, manager, other_manager, prod_like_requests
    ):
        # R42.4-21: источник 1С с меньшим pk захватывается раньше цели. Цель
        # передали прямо перед захватом строк, а источник держит чужая
        # транзакция: запрос отвечает 404, не вставая в очередь за источником.
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        applicant = make_client(manager, tax_id=tax_id, verification_status="pending", is_verified=False)
        assert source.pk < applicant.pk
        source_before = User.objects.filter(pk=source.pk).values().get()
        original_lock = ManagerClientAdmin._lock_link_rows

        with ExitStack() as held:

            def transfer_hold_then_lock(self: ManagerClientAdmin, request: Any, target: User, source_pks: Any) -> None:
                in_other_connection(
                    lambda: User.objects.filter(pk=applicant.pk).update(responsible_manager=other_manager)
                )
                held.enter_context(row_held_elsewhere(source.pk))
                original_lock(self, request, target, source_pks)

            with patch.object(ManagerClientAdmin, "_lock_link_rows", transfer_hold_then_lock):
                response = post_without_locking(
                    manager_client,
                    CHANGELIST_URL,
                    {
                        "action": "link_1c_customer",
                        "_selected_action": [str(applicant.pk)],
                        "apply": "1",
                        "candidate": f"{source.pk}:{source.onec_id}",
                    },
                )

        assert response.status_code == 404
        applicant.refresh_from_db()
        assert applicant.onec_id is None
        assert applicant.responsible_manager == other_manager
        assert User.objects.filter(pk=source.pk).values().get() == source_before
        assert not audit_records(applicant).exists()


class TestRowLockProbe:
    """R42.4-22 — `row_is_locked` признаёт блокировкой только отказ NOWAIT (SQLSTATE 55P03)."""

    def test_free_row_is_not_locked(self, manager):
        own = make_client(manager)

        assert row_is_locked(own.pk) is False

    def test_row_held_elsewhere_is_locked(self, manager):
        own = make_client(manager)

        with row_held_elsewhere(own.pk):
            assert row_is_locked(own.pk) is True

    def test_other_database_error_is_raised(self, manager):
        own = make_client(manager)

        with patch("django.db.models.query.QuerySet.exists", side_effect=DatabaseError("посторонняя ошибка SQL")):
            with pytest.raises(DatabaseError, match="посторонняя ошибка SQL"):
                row_is_locked(own.pk)


class TestChangelistQueryCount:
    """AC11 — число SQL-запросов списка не зависит от числа клиентов (NFR-42-04)."""

    def test_query_count_does_not_grow_with_rows(self, manager_client, manager, django_assert_num_queries):
        def add_applicants_with_candidates(count: int) -> None:
            # Каждая строка — заявка с кандидатом 1С: так замер ловит и запросы,
            # которые display-методы `has_1c_candidate`/`verify_b2b_link` делали бы
            # только для таких строк.
            for _ in range(count):
                tax_id = unique_tax_id()
                make_1c_record(tax_id)
                make_client(manager, tax_id=tax_id, verification_status="pending", is_verified=False)

        add_applicants_with_candidates(5)
        with CaptureQueriesContext(connection) as captured:
            first = manager_client.get(CHANGELIST_URL)
        assert first.status_code == 200
        assert len(first.context["cl"].result_list) == 5
        baseline = len(captured)

        add_applicants_with_candidates(45)
        with django_assert_num_queries(baseline):
            second = manager_client.get(CHANGELIST_URL)
        rows = second.context["cl"].result_list
        assert len(rows) == 50
        assert all(row._has_1c_candidate for row in rows)

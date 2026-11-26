"""
Integration-тесты команды recalculate_responsible_managers (стори 42.3, AC4–AC8).

Клиенты, созданные через save(), сразу получают ответственного хуком 42.2,
а создание правила переводит клиентов сигналом. Поэтому «существующих
клиентов без ответственного» тесты получают сбросом через QuerySet.update()
после подготовки правил и клиентов.
"""

from __future__ import annotations

import threading
import time
from io import StringIO
from typing import Callable
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import DEFAULT_DB_ALIAS, OperationalError, connection, connections
from django.db.models import QuerySet
from django.test.utils import CaptureQueriesContext

from apps.common.models import ManagerRoutingRule
from apps.users.management.commands import import_customers_from_1c as import_module
from apps.users.management.commands import recalculate_responsible_managers as command_module
from apps.users.models import User
from apps.users.services.bulk_clients_lock import BULK_CLIENTS_LOCK_ID, acquire_bulk_clients_lock
from apps.users.services.responsible_manager import resolve_responsible
from apps.users.staff_roles import MANAGERS_GROUP, STAFF_ROLE_GROUPS, SUPERVISORS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

COMMAND = "recalculate_responsible_managers"
INN_REGION = ManagerRoutingRule.MATCH_INN_REGION
COUNTRY = ManagerRoutingRule.MATCH_COUNTRY
FALLBACK = ManagerRoutingRule.MATCH_FALLBACK
NO_FALLBACK = "Нет активного резервного правила с менеджером"
DRY_RUN_HEADER = "Пересчёт ответственных менеджеров (пробный запуск, изменения не сохранены)"
COUNTER_LINES = (
    "Назначено по коду региона",
    "Назначено по стране",
    "Ушло на резервное правило",
    "Пропущено (назначен вручную)",
    "Без изменений",
    "Пропущено (изменились во время пересчёта)",
    "Без ответственного (нет резервного правила с менеджером)",
)
CODES_HEADER = "Коды без менеджера, клиенты ушли на резерв:"
LOCK_NOT_AVAILABLE = "55P03"


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    """Изолируем тесты от правил, засеянных data-миграцией common/0018."""
    ManagerRoutingRule.objects.all().delete()


def make_staff(group: str = MANAGERS_GROUP, **extra) -> User:
    user = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@freesportopt.ru",
        password="StrongPassword123!",
        is_staff=True,
        **extra,
    )
    user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


def make_client(tax_id: str = "", country: str = User.COUNTRY_RUSSIA, **extra) -> User:
    extra.setdefault("role", "wholesale_level1")
    return User.objects.create_user(
        email=f"client_{get_unique_suffix()}@example.com",
        password="StrongPassword123!",
        tax_id=tax_id,
        country=country,
        **extra,
    )


def rule(match_type: str, match_value: str, manager: User | None = None, active: bool = True) -> ManagerRoutingRule:
    return ManagerRoutingRule.objects.create(
        match_type=match_type,
        match_value=match_value,
        manager=manager,
        manager_email="" if manager else f"rule_{get_unique_suffix()}@freesportopt.ru",
        is_active=active,
    )


def reset_responsible(users) -> None:
    """Состояние «до выката 42.2»: ответственного нет, хук и сигналы не срабатывают."""
    User.objects.filter(pk__in=[user.pk for user in users]).update(responsible_manager=None)


def run(*args: str) -> tuple[str, str]:
    stdout, stderr = StringIO(), StringIO()
    call_command(COMMAND, *args, stdout=stdout, stderr=stderr)
    return stdout.getvalue(), stderr.getvalue()


def counter(report: str, label: str) -> int | None:
    for line in report.splitlines():
        if line.startswith(f"{label}: "):
            return int(line.rsplit(": ", 1)[1])
    return None


def assert_sum_matches(report: str) -> None:
    total = sum(counter(report, label) or 0 for label in COUNTER_LINES)
    assert total == counter(report, "Проверено клиентов")


def codes_section(report: str) -> list[str]:
    lines = report.splitlines()
    return lines[lines.index(CODES_HEADER) + 1 :] if CODES_HEADER in lines else []


def run_with_change_before_write(change: Callable[[], None], *args: str) -> tuple[str, str]:
    """Запуск, в котором change() выполняется после чтения клиентов, но до записи."""
    original_apply = command_module.Command._apply

    def apply_after_change(self, *apply_args, **apply_kwargs):
        change()
        return original_apply(self, *apply_args, **apply_kwargs)

    with patch.object(command_module.Command, "_apply", apply_after_change):
        return run(*args)


@pytest.fixture
def managers():
    return {
        "region": make_staff(),
        "country": make_staff(),
        "fallback": make_staff(SUPERVISORS_GROUP),
        "manual": make_staff(),
        "other": make_staff(),
    }


@pytest.fixture
def rules(managers):
    rule(INN_REGION, "23", managers["region"])
    rule(INN_REGION, "24")  # только manager_email — ответственного не даёт
    rule(COUNTRY, "Беларусь", managers["country"])
    rule(FALLBACK, "default", managers["fallback"])


@pytest.fixture
def population(managers, rules):
    """Набор клиентов AC4 и сотрудники с ИНН региона."""
    clients = {
        "no_manager": make_client("2311111111"),
        "already_ok": make_client("2322222222"),
        "foreign_manager": make_client("2333333333"),
        "manual": make_client("2344444444"),
        "unregistered": make_client("2355555555", role="unregistered"),
        "no_inn": make_client(""),
        "email_only_region": make_client("2466666666"),
        "moscow_new": make_client("9777777777"),
        "belarus": make_client("2388888888", country="Беларусь"),
        "inactive": make_client("2399999999", is_active=False),
    }
    staff = {
        "is_staff": User.objects.create_user(
            email=f"s_{get_unique_suffix()}@freesportopt.ru",
            password="StrongPassword123!",
            is_staff=True,
            tax_id="2300000001",
        ),
        "superuser": User.objects.create_superuser(
            email=f"su_{get_unique_suffix()}@freesportopt.ru", password="StrongPassword123!", tax_id="2300000002"
        ),
        "admin_role": make_client("2300000003", role="admin"),
    }
    for group in STAFF_ROLE_GROUPS:
        member = make_client("2300000004")
        member.groups.add(Group.objects.get_or_create(name=group)[0])
        staff[f"group_{group}"] = member

    reset_responsible(list(clients.values()) + list(staff.values()))
    User.objects.filter(pk=clients["already_ok"].pk).update(responsible_manager=managers["region"])
    User.objects.filter(pk=clients["foreign_manager"].pk).update(responsible_manager=managers["other"])
    User.objects.filter(pk=clients["manual"].pk).update(
        responsible_manager=managers["manual"], responsible_manager_manual=True
    )
    for user in list(clients.values()) + list(staff.values()):
        user.refresh_from_db()
    return clients, staff


class TestAssignment:
    def test_invariant_for_every_non_manual_client(self, population, managers):
        clients, staff = population
        updated_at = {user.pk: user.updated_at for user in list(clients.values()) + list(staff.values())}

        run()

        for name, client in clients.items():
            client.refresh_from_db()
            assert client.updated_at == updated_at[client.pk], name
            if name == "manual":
                continue
            assert client.responsible_manager == resolve_responsible(client.country, client.tax_id).manager, name
        assert clients["no_manager"].responsible_manager == managers["region"]
        assert clients["foreign_manager"].responsible_manager == managers["region"]
        assert clients["unregistered"].responsible_manager == managers["region"]
        assert clients["inactive"].responsible_manager == managers["region"]
        assert clients["belarus"].responsible_manager == managers["country"]
        assert clients["no_inn"].responsible_manager == managers["fallback"]
        assert clients["moscow_new"].responsible_manager == managers["fallback"]

    def test_manual_and_staff_untouched(self, population, managers):
        clients, staff = population

        run()

        clients["manual"].refresh_from_db()
        assert clients["manual"].responsible_manager == managers["manual"]
        assert clients["manual"].responsible_manager_manual is True
        for name, user in staff.items():
            user.refresh_from_db()
            assert user.responsible_manager is None, name

    def test_email_only_rule_gives_no_manager(self, population, managers):
        clients, _staff = population

        run()

        clients["email_only_region"].refresh_from_db()
        # Правило 24 без учётной записи: клиент уходит на резерв, а не «к правилу».
        assert clients["email_only_region"].responsible_manager == managers["fallback"]


class TestReport:
    def test_counters(self, population):
        clients, _staff = population

        report, _err = run()

        assert report.splitlines()[0] == "Пересчёт ответственных менеджеров"
        assert "Проверено клиентов: 10" in report
        # no_manager, foreign_manager, unregistered, inactive.
        assert "Назначено по коду региона: 4" in report
        assert "Назначено по стране: 1" in report
        # no_inn, email_only_region, moscow_new.
        assert "Ушло на резервное правило: 3" in report
        assert "Пропущено (назначен вручную): 1" in report
        assert "Без изменений: 1" in report
        assert "Без ответственного" not in report
        assert_sum_matches(report)

    def test_fallback_codes_listed(self, population):
        clients, _staff = population
        make_client("9711111111")
        reset_responsible(User.objects.filter(tax_id="9711111111"))

        report, _err = run()

        lines = report.splitlines()
        header = lines.index("Коды без менеджера, клиенты ушли на резерв:")
        assert lines[header + 1 : header + 3] == [
            "  97 — г. Москва (ИНН с 2014 г.): 2",
            "  24 — Красноярский край: 1",
        ]

    def test_codes_sorted_by_count_then_code(self, managers):
        rule(FALLBACK, "default", managers["fallback"])
        users = [make_client("8011111111"), make_client("8511111111"), make_client("8111111111")]
        users.append(make_client("8522222222"))
        reset_responsible(users)

        report, _err = run()

        lines = report.splitlines()
        header = lines.index("Коды без менеджера, клиенты ушли на резерв:")
        assert lines[header + 1 :] == [
            "  85 — Усть-Ордынский Бурятский АО (Иркутская область): 2",
            "  80 — Агинский Бурятский АО (Забайкальский край): 1",
            "  81 — Коми-Пермяцкий АО (Пермский край): 1",
        ]

    def test_unknown_code_listed_as_is(self, managers):
        rule(FALLBACK, "default", managers["fallback"])
        reset_responsible([make_client("9611111111")])

        report, _err = run()

        assert "  96: 1" in report.splitlines()

    def test_no_codes_section_when_all_assigned(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        reset_responsible([make_client("2311111111"), make_client("")])

        report, _err = run()

        assert "Коды без менеджера" not in report
        assert "Ушло на резервное правило: 1" in report

    def test_foreign_manager_reassigned_and_counted(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("2311111111")
        User.objects.filter(pk=client.pk).update(responsible_manager=managers["other"])

        report, _err = run()

        client.refresh_from_db()
        assert client.responsible_manager == managers["region"]
        assert "Назначено по коду региона: 1" in report

    def test_second_run_is_idempotent(self, population):
        first_report, _err = run()

        report, _err = run()

        # Коды резерва считаются и у уже назначенных клиентов: список не пустеет.
        expected_codes = ["  24 — Красноярский край: 1", "  97 — г. Москва (ИНН с 2014 г.): 1"]
        assert codes_section(first_report) == expected_codes
        assert codes_section(report) == expected_codes
        assert "Назначено по коду региона: 0" in report
        assert "Назначено по стране: 0" in report
        assert "Ушло на резервное правило: 0" in report
        checked = counter(report, "Проверено клиентов")
        manual = counter(report, "Пропущено (назначен вручную)")
        assert counter(report, "Без изменений") == checked - manual
        assert_sum_matches(report)


class TestNoRegionKey:
    """Непустой ИНН без кода региона: резерв и в расчёте, и в условии записи (ревью R13)."""

    @pytest.mark.parametrize(
        "tax_id", ["7", "AB12345678", " 2312345678"], ids=["one_digit", "letters", "leading_space"]
    )
    def test_assigned_to_fallback(self, managers, tax_id):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client(tax_id)
        reset_responsible([client])

        report, _err = run()

        client.refresh_from_db()
        assert client.responsible_manager == managers["fallback"]
        assert "Ушло на резервное правило: 1" in report
        assert "изменились во время пересчёта" not in report
        assert CODES_HEADER not in report
        assert_sum_matches(report)


class TestEmptyCountry:
    """Пустая страна — это Россия и в расчёте, и в условии записи (ревью R19)."""

    @pytest.mark.parametrize(
        ("tax_id", "manager", "line"),
        [
            ("2311111111", "region", "Назначено по коду региона: 1"),
            ("", "fallback", "Ушло на резервное правило: 1"),
        ],
        ids=["region_inn", "no_key"],
    )
    def test_assigned_as_russia(self, managers, tax_id, manager, line):
        rule(INN_REGION, "23", managers["region"])
        rule(COUNTRY, "Беларусь", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client(tax_id, country="")
        reset_responsible([client])

        report, _err = run()

        client.refresh_from_db()
        assert client.country == ""
        assert client.responsible_manager == managers[manager]
        assert line in report
        assert "изменились во время пересчёта" not in report
        assert_sum_matches(report)


class TestDryRun:
    def test_report_matches_real_run_without_updates(self, population):
        clients, _staff = population

        with CaptureQueriesContext(connection) as ctx:
            dry_report, _err = run("--dry-run")

        assert not [q["sql"] for q in ctx.captured_queries if q["sql"].startswith('UPDATE "users"')]
        for client in clients.values():
            before = client.responsible_manager_id
            client.refresh_from_db()
            assert client.responsible_manager_id == before

        real_report, _err = run()

        dry_lines = dry_report.splitlines()
        real_lines = real_report.splitlines()
        assert dry_lines[0] == DRY_RUN_HEADER
        assert real_lines[0] == "Пересчёт ответственных менеджеров"
        assert dry_lines[1:] == real_lines[1:]


class TestNoFallback:
    @pytest.fixture
    def without_fallback(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default")  # резерв только с manager_email
        users = [make_client("2311111111"), make_client(""), make_client("9711111111")]
        reset_responsible(users)
        return users

    def test_real_run_raises_and_changes_nothing(self, without_fallback):
        with pytest.raises(CommandError, match=NO_FALLBACK):
            run()

        for user in without_fallback:
            user.refresh_from_db()
            assert user.responsible_manager is None

    def test_inactive_fallback_with_manager_is_not_enough(self, managers):
        rule(FALLBACK, "default", managers["fallback"], active=False)

        with pytest.raises(CommandError, match=NO_FALLBACK):
            run()

    def test_blocked_fallback_supervisor_is_named(self, managers):
        """Правило активно, но руководитель заблокирован — сообщение называет причину (стори 42.7)."""
        chief = managers["fallback"]
        rule(FALLBACK, "default", chief)
        chief.is_active = False
        chief.save(update_fields=["is_active", "updated_at"])

        with pytest.raises(CommandError, match=f"{NO_FALLBACK} или руководитель резервного правила заблокирован"):
            run()

    def test_dry_run_reports_and_warns(self, without_fallback, managers):
        report, err = run("--dry-run")

        assert report.splitlines()[0] == DRY_RUN_HEADER
        assert "Назначено по коду региона: 1" in report
        assert "Без ответственного (нет резервного правила с менеджером): 2" in report
        assert NO_FALLBACK in err
        assert_sum_matches(report)
        for user in without_fallback:
            user.refresh_from_db()
            assert user.responsible_manager is None


class TestPerformance:
    def _queries_for(self, count: int, previous: tuple[User, ...] = ()) -> int:
        """Запросы прогона по count клиентам кодов 23, 50, 77; previous — их прежние ответственные по кругу."""
        users = [make_client(f"{('23', '50', '77')[index % 3]}{index:08d}") for index in range(count)]
        reset_responsible(users)
        for offset, manager in enumerate(previous):
            User.objects.filter(pk__in=[user.pk for user in users[offset :: len(previous)]]).update(
                responsible_manager=manager
            )
        with CaptureQueriesContext(connection) as ctx:
            run()
        ids = [user.pk for user in users]
        assert not User.objects.filter(pk__in=ids, responsible_manager__isnull=True).exists()
        assert not User.objects.filter(pk__in=ids, responsible_manager__in=previous).exists()
        return len(ctx.captured_queries)

    def test_query_count_independent_of_clients(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(INN_REGION, "50", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])

        assert self._queries_for(5) == self._queries_for(50)

    def test_query_count_independent_of_previous_managers(self, managers):
        """Ревью R10: у клиентов одних и тех же трёх кодов один или два прежних ответственных."""
        rule(INN_REGION, "23", managers["region"])
        rule(INN_REGION, "50", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])

        one_previous = self._queries_for(5, (managers["other"],))
        two_previous = self._queries_for(50, (managers["other"], managers["manual"]))

        assert one_previous == two_previous


class TestChangesDuringRun:
    """Клиент или правило изменились после чтения, до записи (ревью R1–R4, R7)."""

    @pytest.fixture
    def region_client(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(INN_REGION, "77", managers["other"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("2311111111")
        reset_responsible([client])
        client.refresh_from_db()
        return client

    def test_region_change_keeps_new_assignment(self, region_client, managers):
        def change_tax_id():
            region_client.tax_id = "7711111111"
            region_client.save()  # хук 42.2 назначает менеджера кода 77

        report, _err = run_with_change_before_write(change_tax_id)

        region_client.refresh_from_db()
        assert region_client.responsible_manager == managers["other"]
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_region_change_to_current_managers_region_kept(self, region_client, managers):
        """Ответственный не сменился, сменился только ключ региона: решает проверка ключа."""
        User.objects.filter(pk=region_client.pk).update(responsible_manager=managers["other"])
        region_client.refresh_from_db()

        def change_tax_id():
            region_client.tax_id = "7711111111"
            region_client.save()  # менеджер кода 77 у клиента уже стоит

        report, _err = run_with_change_before_write(change_tax_id)

        region_client.refresh_from_db()
        assert region_client.responsible_manager == managers["other"]
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_country_change_keeps_current_manager(self, managers):
        """Ревью R12: ИНН и ответственный прежние, сменилась только страна — решает проверка страны."""
        rule(INN_REGION, "23", managers["region"])
        rule(COUNTRY, "Беларусь", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("2311111111")
        User.objects.filter(pk=client.pk).update(responsible_manager=managers["country"])
        client.refresh_from_db()

        def move_to_belarus():
            client.country = "Беларусь"
            client.save()  # хук 42.2: менеджер страны у клиента уже стоит

        report, _err = run_with_change_before_write(move_to_belarus)

        client.refresh_from_db()
        assert client.responsible_manager == managers["country"]
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_previous_manager_checked_per_client(self, managers):
        """Ревью R10: в одной пачке у каждого клиента сверяется его собственный прежний ответственный."""
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        unassigned, foreign = make_client("2311111111"), make_client("2322222222")
        reset_responsible([unassigned, foreign])
        User.objects.filter(pk=foreign.pk).update(responsible_manager=managers["other"])

        def give_neighbours_manager():
            # Прежний ответственный соседа по пачке: общий список прежних такую смену пропустил бы.
            User.objects.filter(pk=unassigned.pk).update(responsible_manager=managers["other"])

        report, _err = run_with_change_before_write(give_neighbours_manager)

        unassigned.refresh_from_db()
        foreign.refresh_from_db()
        assert unassigned.responsible_manager == managers["other"]
        assert foreign.responsible_manager == managers["region"]
        assert "Назначено по коду региона: 1" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_rule_change_keeps_signal_assignment(self, region_client, managers):
        def change_rule():
            region_rule = ManagerRoutingRule.objects.get(match_type=INN_REGION, match_value="23")
            region_rule.manager = managers["country"]
            region_rule.save()  # сигнал 42.2 переводит клиентов кода 23

        report, _err = run_with_change_before_write(change_rule)

        region_client.refresh_from_db()
        assert region_client.responsible_manager == managers["country"]
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_no_key_to_region_with_current_manager_kept(self, managers):
        """Ревью R15: ИНН был пуст (расчёт — резерв), стал «23…», ответственный прежний — решает проверка ключа."""
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("")
        User.objects.filter(pk=client.pk).update(responsible_manager=managers["region"])
        client.refresh_from_db()

        def set_region_tax_id():
            client.tax_id = "2311111111"
            client.save()  # хук 42.2: менеджер кода 23 у клиента уже стоит

        report, _err = run_with_change_before_write(set_region_tax_id)

        client.refresh_from_db()
        assert client.responsible_manager == managers["region"]
        assert "Ушло на резервное правило: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_foreign_client_moved_to_russia_kept(self, managers):
        """Ревью R16: расчёт — по правилу Беларуси, клиент перешёл в Россию, ответственный прежний."""
        rule(INN_REGION, "23", managers["region"])
        rule(COUNTRY, "Беларусь", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("2311111111", country="Беларусь")
        User.objects.filter(pk=client.pk).update(responsible_manager=managers["region"])
        client.refresh_from_db()

        def move_to_russia():
            client.country = User.COUNTRY_RUSSIA
            client.save()  # хук 42.2: менеджер кода 23 у клиента уже стоит

        report, _err = run_with_change_before_write(move_to_russia)

        client.refresh_from_db()
        assert client.responsible_manager == managers["region"]
        assert "Назначено по стране: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    @pytest.mark.parametrize(
        "transition",
        [{"is_staff": True}, {"is_superuser": True}, {"role": "admin"}, *STAFF_ROLE_GROUPS],
        ids=["is_staff", "is_superuser", "role_admin", *STAFF_ROLE_GROUPS],
    )
    def test_staff_transition_not_assigned(self, region_client, transition):
        def become_staff():
            if isinstance(transition, dict):
                User.objects.filter(pk=region_client.pk).update(**transition)
            else:
                region_client.groups.add(Group.objects.get_or_create(name=transition)[0])

        report, _err = run_with_change_before_write(become_staff)

        region_client.refresh_from_db()
        assert region_client.responsible_manager is None
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_manual_assignment_kept_and_reported(self, region_client, managers):
        def assign_manually():
            region_client.responsible_manager = managers["manual"]
            region_client.responsible_manager_manual = True
            region_client.save()

        report, _err = run_with_change_before_write(assign_manually)

        region_client.refresh_from_db()
        assert region_client.responsible_manager == managers["manual"]
        assert region_client.responsible_manager_manual is True
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (назначен вручную): 1" in report
        assert "изменились во время пересчёта" not in report
        assert_sum_matches(report)

    def test_current_manager_pinned_manually_kept(self, region_client, managers):
        """Флаг «назначен вручную» на прежнем менеджере: решает ручной гард UPDATE."""
        User.objects.filter(pk=region_client.pk).update(responsible_manager=managers["manual"])
        region_client.refresh_from_db()

        def pin_manually():
            region_client.responsible_manager_manual = True
            region_client.save()

        report, _err = run_with_change_before_write(pin_manually)

        region_client.refresh_from_db()
        assert region_client.responsible_manager == managers["manual"]
        assert region_client.responsible_manager_manual is True
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (назначен вручную): 1" in report
        assert_sum_matches(report)

    def test_skipped_fallback_client_leaves_codes_list(self, managers):
        rule(FALLBACK, "default", managers["fallback"])
        moscow, other = make_client("9711111111"), make_client("9722222222")
        reset_responsible([moscow, other])

        def assign_manually(user: User) -> Callable[[], None]:
            def change() -> None:
                User.objects.filter(pk=user.pk).update(
                    responsible_manager=managers["manual"], responsible_manager_manual=True
                )

            return change

        report, _err = run_with_change_before_write(assign_manually(moscow))

        assert codes_section(report) == ["  97 — г. Москва (ИНН с 2014 г.): 1"]
        assert "Ушло на резервное правило: 1" in report
        assert_sum_matches(report)

        User.objects.filter(pk=other.pk).update(responsible_manager=None)
        report, _err = run_with_change_before_write(assign_manually(other))

        assert CODES_HEADER not in report


def lock_probe(sql: str) -> str | None:
    """Выполнить sql из второго соединения: код ошибки PostgreSQL или None. Изменения откатываются."""
    other = connections.create_connection(DEFAULT_DB_ALIAS)
    try:
        with other.cursor() as cursor:
            cursor.execute("SET lock_timeout = '100ms'")
            cursor.execute("BEGIN")
            try:
                cursor.execute(sql)
            except OperationalError as exc:
                return exc.__cause__.pgcode
            finally:
                cursor.execute("ROLLBACK")
    finally:
        other.close()
    return None


def bulk_lock_free() -> bool:
    """Свободна ли общая блокировка импорта и пересчёта: проба из второго соединения, без ожидания."""
    other = connections.create_connection(DEFAULT_DB_ALIAS)
    try:
        with other.cursor() as cursor:
            cursor.execute("BEGIN")
            cursor.execute("SELECT pg_try_advisory_xact_lock(%s)", [BULK_CLIENTS_LOCK_ID])
            free = cursor.fetchone()[0]
            cursor.execute("ROLLBACK")
    finally:
        other.close()
    return free


RULES_TABLE = f'"{ManagerRoutingRule._meta.db_table}"'
RULE_WRITE_PROBES = {
    "create": f"INSERT INTO {RULES_TABLE} SELECT * FROM {RULES_TABLE} WHERE false",
    "update": f"UPDATE {RULES_TABLE} SET is_active = is_active WHERE id = -1",
    "delete": f"DELETE FROM {RULES_TABLE} WHERE id = -1",
}


class TestRulesLock:
    """Правила заблокированы от изменений с первого чтения до конца записи (ревью R1)."""

    @pytest.fixture
    def region_client_rules(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        reset_responsible([make_client("2311111111")])

    @pytest.mark.parametrize("dry_run", [False, True], ids=["real_run", "dry_run"])
    def test_rules_locked_from_first_read_to_write(self, region_client_rules, dry_run):
        """С --dry-run расчёт тоже идёт на одном состоянии правил (ревью R17): записи нет, но блокировка та же."""
        # Контроль: до запуска изменения правил из второго соединения проходят.
        assert {name: lock_probe(sql) for name, sql in RULE_WRITE_PROBES.items()} == dict.fromkeys(RULE_WRITE_PROBES)
        all_probes = {**RULE_WRITE_PROBES, "parallel_run": command_module.LOCK_RULES_SQL}
        probes: dict[str, dict[str, str | None]] = {}
        import_lock_held: dict[str, bool] = {}
        original_resolve = command_module.resolve_responsible_for_key
        original_collect = command_module.Command._collect
        original_apply = command_module.Command._apply

        def probe(stage: str) -> None:
            probes[stage] = {name: lock_probe(sql) for name, sql in all_probes.items()}
            # Общая блокировка с импортом контрагентов держится так же (ревью R18).
            import_lock_held[stage] = not bulk_lock_free()

        def resolve_with_probe(key):
            if "first_read" not in probes:
                probe("first_read")
            return original_resolve(key)

        def collect_with_probe(self, *args, **kwargs):
            result = original_collect(self, *args, **kwargs)
            probe("calculated")
            return result

        def apply_with_probe(self, *args, **kwargs):
            probe("write")
            return original_apply(self, *args, **kwargs)

        with (
            patch.object(command_module, "resolve_responsible_for_key", resolve_with_probe),
            patch.object(command_module.Command, "_collect", collect_with_probe),
            patch.object(command_module.Command, "_apply", apply_with_probe),
        ):
            run(*(["--dry-run"] if dry_run else []))

        expected = dict.fromkeys(all_probes, LOCK_NOT_AVAILABLE)
        stages = ["first_read", "calculated"] if dry_run else ["first_read", "calculated", "write"]
        assert probes == dict.fromkeys(stages, expected)
        assert import_lock_held == dict.fromkeys(stages, True)
        assert bulk_lock_free()


USERS_TABLE = f'"{User._meta.db_table}"'
USER_GROUPS_TABLE = f'"{User.groups.through._meta.db_table}"'
BLOCK_WAIT_SECONDS = 10


def wait_until_blocking(cursor, blocked_pid: int) -> bool:
    """Ждать, пока соединение blocked_pid не встанет на блокировке, которую держит соединение cursor."""
    cursor.execute("SELECT pg_backend_pid()")
    own_pid = cursor.fetchone()[0]
    deadline = time.monotonic() + BLOCK_WAIT_SECONDS
    while time.monotonic() < deadline:
        # pg_blocking_pids читает менеджер блокировок напрямую, снимка статистики у неё нет.
        cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [own_pid, blocked_pid])
        if cursor.fetchone()[0]:
            return True
        time.sleep(0.05)
    return False


class TestGroupMembershipRace:
    """Клиента добавили в группу сотрудников из другого соединения, пока команда пишет (ревью R11)."""

    @staticmethod
    def _run_while_added_to_group(client: User) -> tuple[str, dict[str, object]]:
        """Запуск команды, пока второе соединение держит строку клиента и добавляет его в «Менеджеры»."""
        group = Group.objects.get_or_create(name=MANAGERS_GROUP)[0]
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            command_pid = cursor.fetchone()[0]
        holding = threading.Event()
        outcome: dict[str, object] = {}

        def add_to_group_in_other_connection() -> None:
            other = connections.create_connection(DEFAULT_DB_ALIAS)
            try:
                with other.cursor() as cursor:
                    cursor.execute("BEGIN")
                    # Как сохранение в админке: строка пользователя и его группы в одной транзакции.
                    cursor.execute(f"UPDATE {USERS_TABLE} SET first_name = first_name WHERE id = %s", [client.pk])
                    cursor.execute(
                        f"INSERT INTO {USER_GROUPS_TABLE} (user_id, group_id) VALUES (%s, %s)", [client.pk, group.pk]
                    )
                    holding.set()
                    outcome["command_waited"] = wait_until_blocking(cursor, command_pid)
                    cursor.execute("COMMIT")
            except Exception as exc:  # ошибку потока проверяет тест после join
                outcome["error"] = exc
            finally:
                holding.set()
                other.close()

        thread = threading.Thread(target=add_to_group_in_other_connection)
        thread.start()
        try:
            assert holding.wait(BLOCK_WAIT_SECONDS)
            report, _err = run()
        finally:
            thread.join(2 * BLOCK_WAIT_SECONDS)
        return report, outcome

    def test_membership_committed_during_write_wait_not_assigned(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        client = make_client("2311111111")
        reset_responsible([client])

        report, outcome = self._run_while_added_to_group(client)

        assert "error" not in outcome
        # Команда прочитала клиента до коммита группы и ждала его транзакцию на записи.
        assert outcome["command_waited"] is True
        client.refresh_from_db()
        assert client.groups.filter(name=MANAGERS_GROUP).exists()
        assert client.responsible_manager is None
        assert "Назначено по коду региона: 0" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)

    def test_client_past_first_lock_chunk_not_assigned(self, managers):
        """
        Клиент за первой пачкой блокировки строк (ревью R22).

        Если _lock_clients оборвётся после первой пачки, команда дождётся
        строки последнего клиента уже в UPDATE, а его подзапрос по группам
        не увидит закоммиченное членство — сотруднику назначат менеджера.
        """
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        count = command_module.UPDATE_CHUNK_SIZE + 1
        suffix = get_unique_suffix()
        # bulk_create минует хук 42.2: клиенты остаются без ответственного.
        users = User.objects.bulk_create(
            User(email=f"race_{suffix}_{index}@example.com", role="wholesale_level1", tax_id=f"23{index:08d}")
            for index in range(count)
        )
        ids = sorted(user.pk for user in users)
        last = User.objects.get(pk=ids[-1])

        report, outcome = self._run_while_added_to_group(last)

        assert "error" not in outcome
        assert outcome["command_waited"] is True
        last.refresh_from_db()
        assert last.groups.filter(name=MANAGERS_GROUP).exists()
        assert last.responsible_manager is None
        assert User.objects.filter(pk__in=ids[:-1], responsible_manager=managers["region"]).count() == count - 1
        assert f"Назначено по коду региона: {count - 1}" in report
        assert "Пропущено (изменились во время пересчёта): 1" in report
        assert_sum_matches(report)


class TestLockOrder:
    """Строки клиентов блокируются в порядке id по всем группам записи сразу (ревью R14)."""

    def test_writer_locking_rows_in_id_order_does_not_deadlock(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(INN_REGION, "50", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])
        # id по возрастанию: группы записи — код 23 (первый и третий клиент) и код 50 (второй).
        first, second, third = make_client("2311111111"), make_client("5011111111"), make_client("2333333333")
        reset_responsible([first, second, third])
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            command_pid = cursor.fetchone()[0]
        holding = threading.Event()
        outcome: dict[str, object] = {}

        def update_in_id_order_in_other_connection() -> None:
            # Как импорт контрагентов 1С: несколько клиентов в одной транзакции, по возрастанию id.
            other = connections.create_connection(DEFAULT_DB_ALIAS)
            try:
                with other.cursor() as cursor:
                    cursor.execute("BEGIN")
                    cursor.execute(f"UPDATE {USERS_TABLE} SET first_name = first_name WHERE id = %s", [second.pk])
                    holding.set()
                    outcome["command_waited"] = wait_until_blocking(cursor, command_pid)
                    cursor.execute(f"UPDATE {USERS_TABLE} SET first_name = first_name WHERE id = %s", [third.pk])
                    cursor.execute("COMMIT")
            except Exception as exc:  # ошибку потока проверяет тест после join
                outcome["error"] = exc
            finally:
                holding.set()
                other.close()

        thread = threading.Thread(target=update_in_id_order_in_other_connection)
        thread.start()
        try:
            assert holding.wait(BLOCK_WAIT_SECONDS)
            report, _err = run()
        finally:
            thread.join(2 * BLOCK_WAIT_SECONDS)

        assert "error" not in outcome
        assert outcome["command_waited"] is True
        assert "Назначено по коду региона: 3" in report
        assert_sum_matches(report)
        assert User.objects.filter(pk__in=[first.pk, third.pk], responsible_manager=managers["region"]).count() == 2
        assert User.objects.filter(pk=second.pk, responsible_manager=managers["country"]).exists()


class TestImportSerialization:
    """Импорт контрагентов 1С и пересчёт сериализованы общей advisory-блокировкой (ревью R18)."""

    def test_import_in_reverse_id_order_does_not_deadlock(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        first, second = make_client("2311111111"), make_client("2322222222")
        reset_responsible([first, second])
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            command_pid = cursor.fetchone()[0]
        holding = threading.Event()
        outcome: dict[str, object] = {}

        def import_in_reverse_id_order_in_other_connection() -> None:
            # Как импорт контрагентов 1С: блокировка, затем клиенты в порядке файла — здесь по убыванию id.
            other = connections.create_connection(DEFAULT_DB_ALIAS)
            try:
                with other.cursor() as cursor:
                    cursor.execute("BEGIN")
                    cursor.execute("SELECT pg_advisory_xact_lock(%s)", [BULK_CLIENTS_LOCK_ID])
                    cursor.execute(f"UPDATE {USERS_TABLE} SET first_name = first_name WHERE id = %s", [second.pk])
                    holding.set()
                    outcome["command_waited"] = wait_until_blocking(cursor, command_pid)
                    # Команда ждёт до блокировки правил и строк: правила свободны для записи.
                    outcome["rules_probe"] = lock_probe(RULE_WRITE_PROBES["update"])
                    cursor.execute(f"UPDATE {USERS_TABLE} SET first_name = first_name WHERE id = %s", [first.pk])
                    cursor.execute("COMMIT")
            except Exception as exc:  # ошибку потока проверяет тест после join
                outcome["error"] = exc
            finally:
                holding.set()
                other.close()

        thread = threading.Thread(target=import_in_reverse_id_order_in_other_connection)
        thread.start()
        try:
            assert holding.wait(BLOCK_WAIT_SECONDS)
            report, _err = run()
        finally:
            thread.join(2 * BLOCK_WAIT_SECONDS)

        assert "error" not in outcome
        assert outcome["command_waited"] is True
        assert outcome["rules_probe"] is None
        assert "Назначено по коду региона: 2" in report
        assert_sum_matches(report)
        assert User.objects.filter(pk__in=[first.pk, second.pk], responsible_manager=managers["region"]).count() == 2

    @pytest.mark.parametrize("failure", ["no_fallback", "write_error"])
    def test_recalculation_releases_lock_on_error(self, managers, failure):
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", None if failure == "no_fallback" else managers["fallback"])
        reset_responsible([make_client("2311111111")])
        held: list[bool] = []
        original_resolve = command_module.resolve_responsible_for_key

        def resolve_with_probe(key):
            if not held:
                held.append(not bulk_lock_free())
            return original_resolve(key)

        def failing_lock_clients(_pending):
            raise RuntimeError("сбой записи")

        with (
            patch.object(command_module, "resolve_responsible_for_key", resolve_with_probe),
            patch.object(command_module.Command, "_lock_clients", staticmethod(failing_lock_clients)),
        ):
            with pytest.raises(CommandError if failure == "no_fallback" else RuntimeError):
                run()

        assert held == [True]
        assert bulk_lock_free()

    @pytest.fixture
    def import_dir(self, tmp_path):
        # Содержимое файла не читается: парсер подменён, проверяется только блокировка.
        (tmp_path / "contragents").mkdir()
        (tmp_path / "contragents" / "contragents_1.xml").write_text("", encoding="utf-8")
        return str(tmp_path)

    # Пробный импорт тоже пишет клиентов и лишь потом откатывает транзакцию файла,
    # поэтому обязан стоять в той же очереди, что и обычный.
    @pytest.mark.parametrize("dry_run", [False, True], ids=["real_run", "dry_run"])
    @pytest.mark.parametrize("fails", [False, True], ids=["success", "file_error"])
    def test_import_holds_lock_while_processing(self, import_dir, fails, dry_run):
        held: list[bool] = []

        def process_customers(_self, _customers_data, chunk_size=100):
            held.append(not bulk_lock_free())
            if fails:
                raise RuntimeError("сбой обработки файла")
            return {"created": 0, "updated": 0, "skipped": 0, "errors": 0}

        out = StringIO()
        with (
            patch.object(import_module.CustomerDataParser, "parse", return_value=[]),
            patch.object(import_module.CustomerDataProcessor, "process_customers", process_customers),
        ):
            call_command("import_customers_from_1c", data_dir=import_dir, dry_run=dry_run, stdout=out)

        assert held == [True]
        assert ("Ошибка обработки файла" in out.getvalue()) is fails
        assert bulk_lock_free()

    def test_lock_outside_transaction_refused(self):
        # Вне транзакции PostgreSQL снял бы блокировку сразу: тихо бесполезный вызов.
        with pytest.raises(RuntimeError, match="transaction.atomic"):
            acquire_bulk_clients_lock()


class TestBatches:
    def test_writes_every_chunk_past_read_and_update_boundaries(self, managers):
        """2001 клиент одного менеджера: две полные пачки записи и хвост, граница чтения 2000."""
        rule(INN_REGION, "23", managers["region"])
        rule(FALLBACK, "default", managers["fallback"])
        count = command_module.READ_CHUNK_SIZE + 1
        assert count > 2 * command_module.UPDATE_CHUNK_SIZE
        suffix = get_unique_suffix()
        # bulk_create минует хук 42.2: клиенты остаются без ответственного.
        users = User.objects.bulk_create(
            User(email=f"bulk_{suffix}_{index}@example.com", role="wholesale_level1", tax_id=f"23{index:08d}")
            for index in range(count)
        )

        with CaptureQueriesContext(connection) as ctx:
            report, _err = run()

        updates = [q["sql"] for q in ctx.captured_queries if q["sql"].startswith('UPDATE "users"')]
        assert len(updates) == 3
        assert f"Назначено по коду региона: {count}" in report
        ids = [user.pk for user in users]
        assert User.objects.filter(pk__in=ids, responsible_manager=managers["region"]).count() == count
        assert User.objects.filter(pk=max(ids), responsible_manager=managers["region"]).exists()


class TestAtomicity:
    def test_failure_after_first_update_rolls_back(self, managers):
        rule(INN_REGION, "23", managers["region"])
        rule(INN_REGION, "50", managers["country"])
        rule(FALLBACK, "default", managers["fallback"])
        users = [make_client("2311111111"), make_client("5011111111")]
        reset_responsible(users)
        ids = [user.pk for user in users]
        original_update = QuerySet.update
        written_before_failure: list[int] = []

        def update_failing_on_second(self, **kwargs):
            if written_before_failure:
                raise RuntimeError("сбой второй записи")
            result = original_update(self, **kwargs)
            written_before_failure.append(User.objects.filter(pk__in=ids, responsible_manager__isnull=False).count())
            return result

        with patch.object(QuerySet, "update", update_failing_on_second):
            with pytest.raises(RuntimeError, match="сбой второй записи"):
                run()

        assert written_before_failure == [1]
        assert not User.objects.filter(pk__in=ids, responsible_manager__isnull=False).exists()

"""
Integration-тесты списка правил маршрутизации в /admin/ (стори 42.3, AC3).

Покрывают колонку «Регион», блок «Не распределены» и стоимость страницы
по числу SQL-запросов.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import ManagerRoutingRule
from apps.common.regions import REGION_NAMES
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

CHANGELIST_URL = reverse("admin:common_managerroutingrule_changelist")
INN_REGION = ManagerRoutingRule.MATCH_INN_REGION


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    """Изолируем тесты от правил, засеянных data-миграцией common/0018."""
    ManagerRoutingRule.objects.all().delete()


@pytest.fixture
def superuser_client(client):
    admin_user = User.objects.create_superuser(
        email=f"root_{get_unique_suffix()}@freesportopt.ru",
        password="StrongPassword123!",
    )
    client.force_login(admin_user)
    return client


@pytest.fixture
def manager() -> User:
    user = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@freesportopt.ru",
        password="StrongPassword123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get_or_create(name=MANAGERS_GROUP)[0])
    return user


def rule(match_type: str, match_value: str, manager: User | None = None) -> ManagerRoutingRule:
    return ManagerRoutingRule.objects.create(
        match_type=match_type,
        match_value=match_value,
        manager=manager,
        manager_email="" if manager else f"rule_{get_unique_suffix()}@freesportopt.ru",
    )


def test_region_column_and_unassigned_block(superuser_client, manager):
    rule(INN_REGION, "23", manager)
    rule(ManagerRoutingRule.MATCH_COUNTRY, "Беларусь", manager)
    rule(ManagerRoutingRule.MATCH_FALLBACK, "default", manager)

    response = superuser_client.get(CHANGELIST_URL)

    assert response.status_code == 200
    html = response.content.decode()
    assert "Регион" in html
    assert '<td class="field-region_display">Краснодарский край</td>' in html
    assert '<td class="field-region_display">Беларусь</td>' in html
    assert '<td class="field-region_display">—</td>' in html
    assert "Не распределены (96):" in html
    assert "97 — г. Москва (ИНН с 2014 г.)" in html
    assert "23 — Краснодарский край" not in html
    assert [region.code for region in response.context["unassigned_regions"]][:2] == ["01", "02"]


def test_all_regions_assigned(superuser_client, manager):
    for code in REGION_NAMES:
        rule(INN_REGION, code, manager)

    response = superuser_client.get(CHANGELIST_URL)

    assert response.status_code == 200
    html = response.content.decode()
    assert "Все регионы распределены" in html
    assert "Не распределены" not in html


def _changelist_queries(client) -> int:
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(CHANGELIST_URL)
    assert response.status_code == 200
    return len(ctx.captured_queries)


def test_query_count_does_not_grow_with_rules(superuser_client, manager):
    codes = list(REGION_NAMES)
    for code in codes[:3]:
        rule(INN_REGION, code, manager)
    few = _changelist_queries(superuser_client)

    for code in codes[3:30]:
        rule(INN_REGION, code, manager)
    many = _changelist_queries(superuser_client)

    assert ManagerRoutingRule.objects.count() == 30
    assert few == many

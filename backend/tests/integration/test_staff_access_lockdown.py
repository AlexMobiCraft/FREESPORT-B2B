"""
Integration-тесты стори 42.1: сотрудник любой роли не попадает в служебную часть.

`is_staff` с эпика 42 означает «сотрудник» (менеджер, маркетинг, руководитель).
Основная `/admin/`, дашборд мониторинга, запуск импорта, API метрик синхронизации
и неактивные атрибуты каталога — только суперпользователю, обмен 1С — только по
праву `integrations.can_exchange_1c`. У каждой проверки — негативный тест для
каждой роли и позитивный для суперпользователя.
"""

from __future__ import annotations

import base64
import importlib
from types import SimpleNamespace

import pytest
from django.apps import apps as django_apps
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.models import Attribute
from apps.users.models import User
from apps.users.staff_roles import STAFF_ROLE_GROUPS
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

PASSWORD = "StrongPassword123!"
EXCHANGE_URL = "/api/integration/1c/exchange/"
IMPORT_API_URL = "/api/integration/import_1c/"
METRICS_URLS = (
    "/api/v1/monitoring/metrics/operations/",
    "/api/v1/monitoring/metrics/business/",
    "/api/v1/monitoring/metrics/realtime/",
    "/api/v1/monitoring/health/",
)
HEALTH_URL = "/api/v1/monitoring/health/"
FILTERS_URL = "/api/v1/catalog/filters/"

_migration = importlib.import_module("apps.users.migrations.0023_staff_role_groups")


@pytest.fixture(autouse=True)
def role_groups():
    """
    Группы ролей через функцию data-миграции: тест не зависит от того,
    остались ли они в тестовой БД после миграций или стёрты `flush`.
    """
    _migration.create_staff_role_groups(django_apps, SimpleNamespace(connection=connection))


def make_staff_member(group_name: str, *codenames: str) -> User:
    """Сотрудник роли: `is_staff=True`, член группы роли, не суперпользователь."""
    member = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@example.com",
        password=PASSWORD,
        first_name="Сотрудник",
        last_name="Тестов",
        is_staff=True,
    )
    member.groups.add(Group.objects.get(name=group_name))
    for codename in codenames:
        member.user_permissions.add(Permission.objects.get(content_type__app_label="users", codename=codename))
    return User.objects.get(pk=member.pk)


@pytest.fixture(params=STAFF_ROLE_GROUPS)
def staff_member(request) -> User:
    return make_staff_member(request.param)


@pytest.fixture
def superuser() -> User:
    return User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)


@pytest.fixture
def applicant() -> User:
    """B2B-заявитель с ожидающей заявкой — цель страниц карточки, подтверждения и пароля."""
    return User.objects.create_user(
        email=f"applicant_{get_unique_suffix()}@example.com",
        password=PASSWORD,
        first_name="Заявитель",
        last_name="Портальный",
        role="wholesale_level1",
        company_name="ООО Заявка",
        tax_id="7701234567",
        verification_status="pending",
        is_active=False,
    )


def admin_urls(target: User) -> list[str]:
    return [
        "/admin/",
        reverse("admin:users_user_changelist"),
        reverse("admin:users_user_change", args=[target.pk]),
        reverse("admin:users_user_verify", args=[target.pk]),
        reverse("admin:auth_user_password_change", args=[target.pk]),
        "/admin/monitoring/",
        "/admin/integrations/import_1c/",
    ]


def basic_auth(email: str, password: str = PASSWORD) -> str:
    return "Basic " + base64.b64encode(f"{email}:{password}".encode()).decode("ascii")


class TestAdminSiteSuperuserOnly:
    """AC2: `/admin/` только суперпользователю."""

    def test_staff_member_is_redirected_to_login(self, client, staff_member, applicant):
        client.force_login(staff_member)

        for url in admin_urls(applicant):
            response = client.get(url)
            assert response.status_code == 302, url
            assert "/admin/login/" in response.url, url

    def test_superuser_opens_admin_pages(self, client, superuser, applicant):
        client.force_login(superuser)

        for url in admin_urls(applicant):
            response = client.get(url)
            assert response.status_code == 200, url

    def test_anonymous_monitoring_dashboard_redirects_to_login(self, client):
        response = client.get("/admin/monitoring/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_inactive_superuser_is_redirected_to_login(self, client, superuser):
        client.force_login(superuser)
        User.objects.filter(pk=superuser.pk).update(is_active=False)

        response = client.get("/admin/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url


class TestAdminEscalationPost:
    """AC4: подделанный POST сотрудника через `/admin/` отсекается сайтом."""

    def test_forged_privilege_post_is_rejected(self, client):
        member = make_staff_member(STAFF_ROLE_GROUPS[0], "view_user", "change_user")
        foreign_group = Group.objects.create(name=f"Чужая {get_unique_suffix()}")
        foreign_perm = Permission.objects.get(content_type__app_label="users", codename="delete_user")
        client.force_login(member)

        response = client.post(
            reverse("admin:users_user_change", args=[member.pk]),
            {
                "email": member.email,
                "role": member.role,
                "is_active": "on",
                "is_staff": "on",
                "is_superuser": "on",
                "groups": [str(foreign_group.pk)],
                "user_permissions": [str(foreign_perm.pk)],
            },
        )

        assert response.status_code == 302
        assert "/admin/login/" in response.url
        member.refresh_from_db()
        assert member.is_superuser is False
        assert list(member.groups.values_list("name", flat=True)) == [STAFF_ROLE_GROUPS[0]]
        assert not member.user_permissions.filter(pk=foreign_perm.pk).exists()


class TestOnecExchangeAccess:
    """AC3: обмен 1С — только по праву `integrations.can_exchange_1c`."""

    def test_staff_member_without_permission_gets_403(self, staff_member):
        response = APIClient().get(
            EXCHANGE_URL, data={"mode": "checkauth"}, HTTP_AUTHORIZATION=basic_auth(staff_member.email)
        )

        assert response.status_code == 403

    def test_exchange_robot_without_staff_passes_checkauth(self):
        robot = User.objects.create_user(email=f"robot_{get_unique_suffix()}@example.com", password=PASSWORD)
        robot.user_permissions.add(
            Permission.objects.get(content_type__app_label="integrations", codename="can_exchange_1c")
        )

        response = APIClient().get(EXCHANGE_URL, data={"mode": "checkauth"}, HTTP_AUTHORIZATION=basic_auth(robot.email))

        assert response.status_code == 200
        assert response.content.decode("utf-8").splitlines()[0] == "success"

    def test_superuser_passes_checkauth(self, superuser):
        response = APIClient().get(
            EXCHANGE_URL, data={"mode": "checkauth"}, HTTP_AUTHORIZATION=basic_auth(superuser.email)
        )

        assert response.status_code == 200


class TestImportPageAccess:
    """AC3: страница запуска импорта по адресу API — только суперпользователю."""

    def test_staff_member_is_redirected_to_login(self, client, staff_member):
        client.force_login(staff_member)

        response = client.get(IMPORT_API_URL)

        assert response.status_code == 302
        assert response.url.startswith(reverse("admin:login"))

    def test_anonymous_is_redirected_to_login(self, client):
        response = client.get(IMPORT_API_URL)

        assert response.status_code == 302
        assert response.url.startswith(reverse("admin:login"))

    def test_superuser_opens_page(self, client, superuser):
        client.force_login(superuser)

        assert client.get(IMPORT_API_URL).status_code == 200


class TestMonitoringMetricsAccess:
    """AC3: API метрик синхронизации — только суперпользователю."""

    def test_staff_member_gets_403(self, staff_member):
        api_client = APIClient()
        api_client.force_authenticate(user=staff_member)

        for url in METRICS_URLS:
            assert api_client.get(url).status_code == 403, url

    def test_superuser_gets_metrics(self, superuser):
        api_client = APIClient()
        api_client.force_authenticate(user=superuser)

        for url in METRICS_URLS:
            response = api_client.get(url)
            if url == HEALTH_URL:
                # При нездоровой системе health честно отвечает 503 — важно, что не 403.
                assert response.status_code in (200, 503), url
            else:
                assert response.status_code == 200, url


class TestCatalogFiltersIncludeInactive:
    """AC3: `include_inactive=true` открывает неактивные атрибуты только суперпользователю."""

    @pytest.fixture
    def attributes(self) -> tuple[str, str]:
        active = Attribute.objects.create(name=f"Активный {get_unique_suffix()}", is_active=True)
        inactive = Attribute.objects.create(name=f"Неактивный {get_unique_suffix()}", is_active=False)
        return active.name, inactive.name

    @staticmethod
    def _names(user: User) -> list[str]:
        api_client = APIClient()
        api_client.force_authenticate(user=user)
        response = api_client.get(FILTERS_URL, {"include_inactive": "true"})
        assert response.status_code == 200
        data = response.json()
        results = data.get("results", data) if isinstance(data, dict) else data
        return [item["name"] for item in results]

    def test_staff_member_does_not_see_inactive(self, staff_member, attributes):
        active_name, inactive_name = attributes

        names = self._names(staff_member)

        assert active_name in names
        assert inactive_name not in names

    def test_superuser_sees_inactive(self, superuser, attributes):
        active_name, inactive_name = attributes

        names = self._names(superuser)

        assert active_name in names
        assert inactive_name in names

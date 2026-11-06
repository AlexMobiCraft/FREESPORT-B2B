"""
Integration-тесты раздела руководителя `/supervisor/` и руководителя в `/manager/` (стори 42.7).

Покрывает:
- AC1 — вход в раздел; руководитель по-прежнему входит в `/manager/` и `/marketing/`;
- AC2 — в `/manager/` руководитель видит всех клиентов и все мастер-заказы, включая заказ без клиента;
- AC3 — колонка и фильтр «Ответственный менеджер» только у руководителя;
- AC4 — ручное назначение ответственного в карточке клиента и журнал;
- AC5 — выбор менеджера в формах: только допустимые, текущий бывший не теряется;
- AC6–AC8 — сотрудники: создание, блокировка, пароль, отказы, смена группы;
- AC9 — таблица регионов, журнал правил, резервное правило только на руководителя;
- AC10 — заблокированный менеджер в правилах регионов (решение 17);
- AC11 — получатели уведомлений и бонусы; AC12 — ссылки и главная; AC13 — прямые URL;
- AC14 — число запросов списков не зависит от числа строк.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`):
группы ролей заново создаёт `role_groups`, правила регионов задаёт сам тест.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal
from typing import Any
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.contrib.messages.storage.cookie import CookieStorage
from django.db import connection
from django.http import HttpRequest
from django.test import Client, RequestFactory
from django.test.utils import CaptureQueriesContext

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.tests.utils import close_master, create_master_with_subs
from apps.common.models import AuditLog, ManagerRoutingRule, NotificationRecipient
from apps.common.regions import REGION_NAMES
from apps.users.manager_admin import ResponsibleManagerFilter
from apps.users.models import User
from apps.users.services.region_routing import resolve_manager_recipients
from apps.users.services.responsible_manager import reassign_clients_for_key
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from freesport.admin_site import supervisor_site
from tests.integration.test_manager_clients_section import (  # noqa: F401 — фикстуры подключаются импортом
    NEW_PASSWORD,
    PASSWORD,
    audit_records,
    form_payload,
    get_unique_suffix,
    make_1c_record,
    make_client,
    make_staff_member,
    manager,
    manager_client,
    message_texts,
    no_routing_rules,
    other_manager,
    region_tax_id,
    role_groups,
    verified_email_task,
)
from tests.integration.test_manager_orders_section import (  # noqa: F401 — фикстуры подключаются импортом
    ORDERS_URL,
    card_payload,
    csv_rows,
    listed_ids,
    make_master,
    order_audit,
    order_change_url,
    order_emails,
    post_order_action,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

INDEX_URL = "/supervisor/"
STAFF_URL = "/supervisor/users/user/"
STAFF_ADD_URL = "/supervisor/users/user/add/"
RULES_URL = "/supervisor/common/managerroutingrule/"
RULES_ADD_URL = "/supervisor/common/managerroutingrule/add/"
RECIPIENTS_URL = "/supervisor/common/notificationrecipient/"
SETTINGS_URL = "/supervisor/bonuses/bonusprogramsettings/"
TRANSACTIONS_URL = "/supervisor/bonuses/bonustransaction/"
CLIENTS_URL = "/manager/users/user/"
LOGIN_URL = "/supervisor/login/"

FORMER_MANAGER_ERROR = (
    "«{email}» больше не может быть ответственным менеджером: учётная запись заблокирована "
    "или выведена из групп «Менеджеры» и «Руководители». Выберите другого менеджера."
)
FALLBACK_ERROR = "Резервное правило назначает клиентов руководителю — выберите сотрудника из группы «Руководители»."
SKIPPED_MESSAGE = "Пропущено 1: руководителей и учётные записи с особыми правами меняет только владелец сайта"
# Ссылка на карточку пользователя в разделе сотрудников (тренер-клиент там — 404).
USER_CARD_LINK = re.compile(r"/supervisor/users/user/\d+/")
PRIVILEGE_INPUTS = ('name="is_staff"', 'name="is_superuser"', 'name="groups"', 'name="user_permissions"', 'name="role"')


@pytest.fixture
def supervisor() -> User:
    return make_staff_member(SUPERVISORS_GROUP, first_name="Роман", last_name="Руководителев")


@pytest.fixture
def supervisor_client(client, supervisor):
    client.force_login(supervisor)
    return client


def superuser_client() -> Client:
    superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
    browser = Client()
    browser.force_login(superuser)
    return browser


def logged_in(user: User) -> Client:
    browser = Client()
    browser.force_login(user)
    return browser


def client_change_url(user: User) -> str:
    return f"{CLIENTS_URL}{user.pk}/change/"


def staff_change_url(user: User) -> str:
    return f"{STAFF_URL}{user.pk}/change/"


def staff_password_url(user: User) -> str:
    return f"{STAFF_URL}{user.pk}/password/"


def rule_change_url(rule: ManagerRoutingRule) -> str:
    return f"{RULES_URL}{rule.pk}/change/"


def listed_pks(response) -> set[int]:
    return {obj.pk for obj in response.context["cl"].result_list}


def choice_pks(form, name: str) -> list[int]:
    return [int(str(value)) for value, _ in form.fields[name].choices if value]


def post_staff_action(browser: Client, action: str, *targets: User, follow: bool = True):
    payload = {"action": action, "_selected_action": [str(target.pk) for target in targets]}
    return browser.post(STAFF_URL, payload, follow=follow)


def action_request(author: User) -> HttpRequest:
    """
    Запрос действия списка для прямого вызова метода админки.

    Через тестовый клиент сбой отката не показал бы: `ATOMIC_REQUESTS` включён
    только в `settings/test.py`, на проде действия списка идут в autocommit.
    """
    request = RequestFactory().post("/")
    request.user = author
    request._messages = CookieStorage(request)  # type: ignore[attr-defined]
    return request


def failing_journal():
    return patch.object(AuditLog, "log_action", side_effect=RuntimeError("журнал недоступен"))


def rule(match_value: str, manager: User | None = None, **extra: Any) -> ManagerRoutingRule:
    match_type = extra.pop("match_type", ManagerRoutingRule.MATCH_INN_REGION)
    return ManagerRoutingRule.objects.create(match_type=match_type, match_value=match_value, manager=manager, **extra)


def rule_payload(**overrides: Any) -> dict[str, Any]:
    data = {
        "match_type": "inn_region",
        "match_value": "23",
        "manager": "",
        "manager_name": "",
        "manager_email": "",
        "federal_district": "",
        "is_active": "on",
        "_save": "Сохранить",
    }
    data.update({key: str(value) for key, value in overrides.items()})
    return data


def staff_create_payload(**overrides: Any) -> dict[str, Any]:
    data = {
        "email": f"new_{get_unique_suffix()}@freesportopt.ru",
        "first_name": "Новый",
        "last_name": "Сотрудник",
        "phone": "+79001234567",
        "password1": PASSWORD,
        "password2": PASSWORD,
        "role_group": MANAGERS_GROUP,
        "_save": "Сохранить",
    }
    data.update(overrides)
    return data


def rule_audit(action_filter: str | None = None):
    records = AuditLog.objects.filter(action="change_routing_rule", resource_type="ManagerRoutingRule").order_by("pk")
    if action_filter:
        records = records.filter(details__changes__operation=action_filter)
    return list(records)


def changelist_payload(response) -> dict[str, Any]:
    """POST сохранения строк `list_editable` из GET-ответа."""
    formset = response.context["cl"].formset
    data: dict[str, Any] = {"_save": "Сохранить"}
    for name in formset.management_form.fields:
        data[f"{formset.prefix}-{name}"] = formset.management_form[name].value()
    for row in formset.forms:
        for name in row.fields:
            value = row[name].value()
            if value is None or value is False:
                continue
            data[row.add_prefix(name)] = "on" if value is True else value
    return data


def row_prefix(response, obj: Any) -> str:
    for row in response.context["cl"].formset.forms:
        if row.instance.pk == obj.pk:
            return row.prefix
    raise AssertionError(f"строки {obj.pk} нет в списке")


# --------------------------------------------------------------------------
# AC1 — вход
# --------------------------------------------------------------------------


class TestEntry:
    def test_supervisor_enters(self, supervisor_client):
        for url in (INDEX_URL, STAFF_URL):
            response = supervisor_client.get(url)
            assert response.status_code == 200, url
            assert "OPTISPORT — Руководитель" in response.content.decode()

    def test_supervisor_keeps_manager_and_marketing(self, supervisor_client):
        assert supervisor_client.get("/manager/").status_code == 200
        assert supervisor_client.get("/marketing/").status_code == 200

    @pytest.mark.parametrize(
        "url",
        [
            "/manager/",
            "/manager/users/",
            "/manager/users/user/",
            "/marketing/",
            "/marketing/banners/",
            "/marketing/banners/banner/",
        ],
    )
    def test_supervisor_gets_link_back_from_sections(self, supervisor_client, url):
        response = supervisor_client.get(url)
        assert response.status_code == 200, url
        # Ссылка в шапке: она есть и на главной, и на страницах приложений, где нет бокового меню.
        assert re.search(r'<a id="supervisor-home-link" href="/supervisor/">', response.content.decode()), url

    def test_supervisor_section_has_no_link_to_itself(self, supervisor_client):
        assert 'id="supervisor-home-link"' not in supervisor_client.get(INDEX_URL).content.decode()

    @pytest.mark.parametrize(
        "group, urls",
        [
            pytest.param(MANAGERS_GROUP, ("/manager/", "/manager/users/", "/manager/users/user/"), id="manager"),
            pytest.param(
                MARKETING_GROUP, ("/marketing/", "/marketing/banners/", "/marketing/banners/banner/"), id="marketing"
            ),
        ],
    )
    def test_other_roles_get_no_link_to_supervisor(self, client, group, urls):
        client.force_login(make_staff_member(group))
        for url in urls:
            response = client.get(url)
            assert response.status_code == 200, url
            assert 'id="supervisor-home-link"' not in response.content.decode(), url
            assert 'id="supervisor-sections"' not in response.content.decode(), url
            assert "/supervisor/" not in response.content.decode(), url
        # Меню на главной включается только руководителю: у менеджера и маркетолога оно продублировало бы модели.
        assert 'id="nav-sidebar"' not in client.get(urls[0]).content.decode()
        assert 'id="nav-sidebar"' not in client.get(urls[1]).content.decode()

    def test_main_admin_has_no_link_to_supervisor(self):
        response = superuser_client().get("/admin/")
        assert response.status_code == 200
        assert 'id="supervisor-home-link"' not in response.content.decode()
        assert 'id="supervisor-sections"' not in response.content.decode()

    @pytest.mark.parametrize(
        "make_user",
        [
            pytest.param(lambda: make_staff_member(MANAGERS_GROUP), id="manager"),
            pytest.param(lambda: make_staff_member(MARKETING_GROUP), id="marketing"),
            pytest.param(lambda: make_staff_member(None), id="staff-without-group"),
            pytest.param(lambda: make_staff_member(SUPERVISORS_GROUP, is_active=False), id="blocked-supervisor"),
            pytest.param(lambda: make_staff_member(SUPERVISORS_GROUP, is_staff=False), id="supervisor-without-staff"),
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
        for url in (INDEX_URL, STAFF_URL):
            response = client.get(url)
            assert response.status_code == 302, url
            assert response["Location"] == f"{LOGIN_URL}?next={url}"


# Строка блока «Разделы» в боковом меню: (адрес, подпись, выделена ли как текущая).
SECTION_ROW = re.compile(
    r'<tr( class="current-model")?>\s*<th scope="row"><a href="([^"]+)"( aria-current="page")?>([^<]+)</a></th>'
)
SECTIONS = [
    ("/supervisor/", "Сводка"),
    ("/supervisor/journal/", "Журнал действий"),
    ("/manager/", "Клиенты и заказы"),
    ("/marketing/", "Маркетинг"),
]


def supervisor_sections(html: str) -> list[tuple[str, str, bool]]:
    """Блок «Разделы» бокового меню: (адрес, подпись, выделена) по порядку; пусто, если блока нет."""
    if 'id="supervisor-sections"' not in html:
        return []
    start = html.index('id="supervisor-sections"')
    block = html[start : html.index("</table>", start)]
    rows = SECTION_ROW.findall(block)
    # Класс и aria-current ставятся вместе: рассинхрон — дефект разметки.
    assert all(bool(row[0]) == bool(row[2]) for row in rows), block
    return [(url, name, bool(row_class)) for row_class, url, _, name in rows]


# --------------------------------------------------------------------------
# Навигация руководителя: блок «Разделы» в боковом меню
# --------------------------------------------------------------------------


class TestSectionsMenu:
    @pytest.mark.parametrize(
        "url, current",
        [
            pytest.param("/supervisor/", "Сводка", id="supervisor-index"),
            pytest.param("/supervisor/summary/", "Сводка", id="supervisor-summary"),
            pytest.param("/supervisor/summary/?date_from=2026-01-01&date_to=2026-01-31", "Сводка", id="with-period"),
            pytest.param("/supervisor/journal/", "Журнал действий", id="journal"),
            pytest.param("/manager/", "Клиенты и заказы", id="manager-index"),
            pytest.param("/manager/users/", "Клиенты и заказы", id="manager-app"),
            pytest.param("/manager/users/user/", "Клиенты и заказы", id="manager-list"),
            pytest.param("/marketing/", "Маркетинг", id="marketing-index"),
            pytest.param("/marketing/banners/", "Маркетинг", id="marketing-app"),
            pytest.param("/marketing/banners/banner/", "Маркетинг", id="marketing-list"),
            pytest.param("/supervisor/users/", None, id="supervisor-app"),
            pytest.param(STAFF_URL, None, id="supervisor-model"),
            pytest.param(RULES_URL, None, id="supervisor-model-rules"),
        ],
    )
    def test_all_sections_and_current_one(self, supervisor_client, url, current):
        response = supervisor_client.get(url)
        assert response.status_code == 200, url
        html = response.content.decode()

        assert 'id="nav-sidebar"' in html, url
        # Блок над фильтром и списком моделей; все четыре пункта остаются в списке всегда.
        assert html.index('id="supervisor-sections"') < html.index('id="nav-filter"'), url
        assert supervisor_sections(html) == [(href, name, name == current) for href, name in SECTIONS], url

    def test_index_opens_summary(self, supervisor_client):
        response = supervisor_client.get(INDEX_URL)
        html = response.content.decode()

        assert response.status_code == 200
        assert response.templates[0].name == "admin/supervisor/summary.html"
        for block in ("summary-period", "summary-pending", "summary-orders-by-manager", "summary-clients"):
            assert f'id="{block}"' in html
        assert response.context["title"] == "Сводка"
        # Витрины со списком моделей в области контента больше нет: модели живут в боковом меню.
        assert 'id="content-main"' not in html
        # Контекст главной AdminSite.index сохранён: app_list — готовые available_apps с моделями раздела.
        assert response.context["app_list"] is response.context["available_apps"]
        assert "Сотрудники" in [app["name"] for app in response.context["app_list"]]
        # Главная не ссылается сама на себя: хлебные крошки есть только у /supervisor/summary/.
        assert 'class="breadcrumbs"' not in html
        assert 'class="breadcrumbs"' in supervisor_client.get("/supervisor/summary/").content.decode()

    def test_index_and_summary_show_same_page(self, supervisor_client):
        period = {"date_from": "2026-01-01", "date_to": "2026-01-31"}
        index = supervisor_client.get(INDEX_URL, period)
        summary = supervisor_client.get("/supervisor/summary/", period)

        assert index.context["period"] == summary.context["period"]
        assert index.context["pending"] == summary.context["pending"]
        assert index.context["orders_by_manager"] == summary.context["orders_by_manager"]

    def test_invalid_period_shows_error_and_default_period(self, supervisor_client):
        response = supervisor_client.get(INDEX_URL, {"date_from": "2026-02-01", "date_to": "2026-01-01"})
        html = response.content.decode()

        assert response.status_code == 200
        assert "Период указан неверно" in html
        assert supervisor_sections(html)[0] == ("/supervisor/", "Сводка", True)

    def test_model_page_keeps_stock_current_model(self, supervisor_client):
        # На странице модели штатное выделение модели не пропадает рядом с блоком «Разделы».
        html = supervisor_client.get(STAFF_URL).content.decode()
        assert re.search(r'<tr class="model-user current-model">', html)
        assert not any(current for _, _, current in supervisor_sections(html))

    @pytest.mark.parametrize(
        "url, current",
        [
            pytest.param("/supervisor/", "Сводка", id="index"),
            pytest.param("/supervisor/summary/", "Сводка", id="summary"),
            pytest.param("/supervisor/journal/", "Журнал действий", id="journal"),
            pytest.param("/supervisor/users/", None, id="app"),
            pytest.param(STAFF_URL, None, id="model"),
            pytest.param(RULES_URL, None, id="model-rules"),
        ],
    )
    def test_supervisor_pages_have_header_links(self, supervisor_client, url, current):
        # Шапка видна на узких экранах и при свёрнутом меню: там блока «Разделы» нет.
        html = supervisor_client.get(url).content.decode()
        start = html.index('id="supervisor-header-links"')
        block = html[start : html.index("</span>", start)]

        assert re.findall(r'<a href="([^"]+)"><strong>([^<]+)</strong></a>', block) == [
            (href, name) for href, name in SECTIONS if name != current
        ]
        assert 'id="supervisor-home-link"' not in html

    def test_manager_and_marketing_mains_have_sidebar_and_header_link(self, supervisor_client):
        for url in ("/manager/", "/marketing/"):
            html = supervisor_client.get(url).content.decode()
            assert 'id="nav-sidebar"' in html, url
            assert re.search(r'<a id="supervisor-home-link" href="/supervisor/">', html), url
            assert 'id="supervisor-header-links"' not in html, url

    def test_menu_does_not_open_main_admin_or_recent_actions(self, supervisor_client):
        for url in (INDEX_URL, "/supervisor/journal/", "/manager/", "/marketing/", "/manager/users/", STAFF_URL):
            html = supervisor_client.get(url).content.decode()
            assert 'href="/admin/' not in html, url
            assert "Последние действия" not in html, url

    def test_other_roles_and_superuser_get_no_sections(self, client):
        for group, url in ((MANAGERS_GROUP, "/manager/users/user/"), (MARKETING_GROUP, "/marketing/banners/banner/")):
            client.force_login(make_staff_member(group))
            html = client.get(url).content.decode()
            assert supervisor_sections(html) == [], url
            assert 'id="supervisor-header-links"' not in html, url
            assert "/supervisor/" not in html, url
        html = superuser_client().get("/admin/users/user/").content.decode()
        assert supervisor_sections(html) == []
        assert 'id="supervisor-header-links"' not in html
        assert "/supervisor/" not in html


# --------------------------------------------------------------------------
# AC2 — руководитель видит отдел целиком
# --------------------------------------------------------------------------


class TestWholeDepartment:
    def test_clients(self, supervisor_client, manager, other_manager):
        own_a = make_client(manager)
        own_b = make_client(other_manager)
        nobody = make_client(None)
        unregistered = make_1c_record(region_tax_id("50"))
        staff = make_staff_member(MANAGERS_GROUP)
        User.objects.filter(pk=staff.pk).update(responsible_manager=manager)

        assert listed_pks(supervisor_client.get(CLIENTS_URL)) == {own_a.pk, own_b.pk, nobody.pk}
        assert listed_pks(supervisor_client.get(CLIENTS_URL, {"portal_account": "no"})) == {unregistered.pk}
        assert listed_pks(supervisor_client.get(CLIENTS_URL, {"q": own_b.email})) == {own_b.pk}
        assert supervisor_client.get(client_change_url(own_b)).status_code == 200
        assert supervisor_client.get(client_change_url(nobody)).status_code == 200
        assert supervisor_client.get(client_change_url(staff)).status_code == 404

    def test_orders(self, supervisor_client, manager, other_manager):
        master_a = make_master(make_client(manager))
        master_b = make_master(make_client(other_manager))
        orphan = make_master(None)
        sub = master_a.sub_orders.first()

        assert listed_ids(supervisor_client.get(ORDERS_URL)) == {master_a.pk, master_b.pk, orphan.pk}
        assert supervisor_client.get(order_change_url(orphan)).status_code == 200
        assert supervisor_client.get(order_change_url(master_b)).status_code == 200
        assert supervisor_client.get(order_change_url(sub)).status_code == 404

        response = post_order_action(supervisor_client, "export_orders_csv", master_a, select_across="1")
        assert response.status_code == 200
        assert len(csv_rows(response)) == 1 + 3

    def test_supervisor_saves_orphan_order(self, supervisor_client, supervisor):
        """Заказ без клиента сохраняется: `ManagerOrderForm.clean()` блокирует строку через ту же выборку (R42.7-6)."""
        orphan = make_master(None)

        response = supervisor_client.post(
            order_change_url(orphan),
            card_payload(supervisor_client, orphan, tracking_number="TRK-ORPHAN", delivery_date="2026-11-05"),
        )

        assert response.status_code == 302
        orphan.refresh_from_db()
        assert (orphan.tracking_number, orphan.delivery_date) == ("TRK-ORPHAN", date(2026, 11, 5))
        (record,) = order_audit(orphan)
        assert record.action == "update_order"
        assert record.user == supervisor
        assert record.details["changes"]["fields"] == {
            "tracking_number": {"old": None, "new": "TRK-ORPHAN"},
            "delivery_date": {"old": None, "new": "2026-11-05"},
        }

    def test_index_counts_whole_department(self, supervisor_client, manager, other_manager):
        for owner in (manager, other_manager, None):
            make_client(owner, verification_status="pending", is_verified=False, is_active=False)
            make_master(make_client(owner) if owner else None)

        texts = [item["text"] for item in supervisor_client.get("/manager/").context["manager_queue"]]

        assert texts[0].startswith("Заявки на верификацию: 3")
        assert texts[1] == "Новые заказы: 3"

    def test_manager_still_sees_only_own(self, manager_client, manager, other_manager):
        own = make_client(manager)
        foreign = make_client(other_manager)
        make_client(None)
        own_order = make_master(own)
        make_master(foreign)
        make_master(None)

        assert listed_pks(manager_client.get(CLIENTS_URL)) == {own.pk}
        assert listed_ids(manager_client.get(ORDERS_URL)) == {own_order.pk}
        assert manager_client.get(client_change_url(foreign)).status_code == 404


# --------------------------------------------------------------------------
# AC3 — колонка и фильтр «Ответственный менеджер»
# --------------------------------------------------------------------------


class TestResponsibleColumnAndFilter:
    def test_supervisor_has_column_and_filter(self, supervisor_client, manager, other_manager):
        blocked = make_staff_member(MANAGERS_GROUP, is_active=False, first_name="Борис", last_name="Блоков")
        own_a = make_client(manager)
        own_b = make_client(other_manager)
        own_blocked = make_client(blocked)
        nobody = make_client(None)

        response = supervisor_client.get(CLIENTS_URL)
        html = response.content.decode()
        spec = next(s for s in response.context["cl"].filter_specs if isinstance(s, ResponsibleManagerFilter))

        assert dict(spec.lookup_choices) == {
            str(manager.pk): f"Анна Менеджерова ({manager.email})",
            str(other_manager.pk): f"{other_manager.full_name} ({other_manager.email})",
            str(blocked.pk): f"Борис Блоков ({blocked.email}) — заблокирован",
            "none": "Без ответственного",
        }
        assert f'<td class="field-responsible_manager_display">Анна Менеджерова ({manager.email})</td>' in html
        assert listed_pks(supervisor_client.get(CLIENTS_URL, {"responsible": manager.pk})) == {own_a.pk}
        assert listed_pks(supervisor_client.get(CLIENTS_URL, {"responsible": blocked.pk})) == {own_blocked.pk}
        assert listed_pks(supervisor_client.get(CLIENTS_URL, {"responsible": "none"})) == {nobody.pk}
        assert own_b.pk in listed_pks(response)

    def test_manager_has_neither(self, manager_client, manager, other_manager):
        make_client(manager)
        foreign = make_client(other_manager)

        response = manager_client.get(CLIENTS_URL)
        assert "responsible_manager_display" not in response.context["cl"].list_display
        assert not any(isinstance(s, ResponsibleManagerFilter) for s in response.context["cl"].filter_specs)

        forged = manager_client.get(CLIENTS_URL, {"responsible": other_manager.pk})
        assert forged.status_code == 302
        assert forged["Location"].endswith("?e=1")
        assert foreign.email not in manager_client.get(forged["Location"]).content.decode()


# --------------------------------------------------------------------------
# AC4 — ручное назначение в карточке
# --------------------------------------------------------------------------


class TestManualAssignment:
    def test_assign_and_release(self, supervisor_client, supervisor, manager, other_manager):
        rule_50 = rule("50", manager)
        customer = make_client(manager, manual=False, tax_id=region_tax_id("50"))

        response = supervisor_client.get(client_change_url(customer))
        form = response.context["adminform"].form
        assert "responsible_manager" in form.fields
        assert "responsible_manager_manual" in form.fields

        data = form_payload(response)
        data["responsible_manager"] = str(other_manager.pk)
        data.pop("responsible_manager_manual", None)
        assert supervisor_client.post(client_change_url(customer), data).status_code == 302

        customer.refresh_from_db()
        assert customer.responsible_manager == other_manager
        assert customer.responsible_manager_manual is True
        records = list(audit_records(customer, "assign_responsible_manager"))
        assert len(records) == 1
        assert records[0].user == supervisor
        assert records[0].changes == {
            "email": customer.email,
            "old": manager.email,
            "new": other_manager.email,
            "manual": True,
            "source": "card",
        }

        # Смена ИНН и замена менеджера в правиле ручное назначение не уводят.
        third = make_staff_member(MANAGERS_GROUP)
        rule("23", third)
        customer.tax_id = region_tax_id("23")
        customer.save()
        rule_50.manager = third
        rule_50.save()
        customer.refresh_from_db()
        assert customer.responsible_manager == other_manager

        response = supervisor_client.get(client_change_url(customer))
        data = form_payload(response)
        data.pop("responsible_manager_manual")
        assert supervisor_client.post(client_change_url(customer), data).status_code == 302

        customer.refresh_from_db()
        assert customer.responsible_manager_manual is False
        assert customer.responsible_manager == third
        last = audit_records(customer, "assign_responsible_manager").order_by("-pk").first()
        assert last.changes["manual"] is False
        assert last.changes["old"] == other_manager.email
        assert last.changes["new"] == third.email
        assert audit_records(customer, "assign_responsible_manager").count() == 2

    def test_unchanged_card_writes_nothing(self, supervisor_client, manager):
        customer = make_client(manager)
        data = form_payload(supervisor_client.get(client_change_url(customer)))

        assert supervisor_client.post(client_change_url(customer), data).status_code == 302
        assert not audit_records(customer, "assign_responsible_manager").exists()

    def test_manager_card_has_no_fields_and_ignores_forged_post(self, manager_client, manager, other_manager):
        customer = make_client(manager, manual=False)

        response = manager_client.get(client_change_url(customer))
        form = response.context["adminform"].form
        assert "responsible_manager" not in form.fields
        assert "responsible_manager_manual" not in form.fields

        data = form_payload(response)
        data["responsible_manager"] = str(other_manager.pk)
        data["responsible_manager_manual"] = "on"
        assert manager_client.post(client_change_url(customer), data).status_code == 302

        customer.refresh_from_db()
        assert customer.responsible_manager == manager
        assert customer.responsible_manager_manual is False
        assert not audit_records(customer, "assign_responsible_manager").exists()

    def test_selector_has_no_links_into_section(self, supervisor_client, manager):
        customer = make_client(manager)
        html = supervisor_client.get(client_change_url(customer)).content.decode()

        assert f"/manager/users/user/{manager.pk}/" not in html
        assert "__fk__" not in html


# --------------------------------------------------------------------------
# AC5 — выбор менеджера в формах
# --------------------------------------------------------------------------


class TestManagerChoice:
    def test_only_allowed_once(self, supervisor_client, supervisor, manager):
        other_chief = make_staff_member(SUPERVISORS_GROUP)
        both = make_staff_member(MANAGERS_GROUP)
        both.groups.add(Group.objects.get(name=SUPERVISORS_GROUP))
        make_staff_member(MANAGERS_GROUP, is_active=False)
        make_staff_member(MARKETING_GROUP)
        make_staff_member(MANAGERS_GROUP, is_staff=False)
        customer = make_client(manager)
        expected = sorted([manager.pk, supervisor.pk, other_chief.pk, both.pk])

        card = supervisor_client.get(client_change_url(customer)).context["adminform"].form
        add_rule = supervisor_client.get(RULES_ADD_URL).context["adminform"].form

        assert sorted(choice_pks(card, "responsible_manager")) == expected
        assert sorted(choice_pks(add_rule, "manager")) == expected

    @pytest.mark.parametrize("how", ["moved-to-marketing", "blocked"])
    def test_former_manager_is_shown_and_must_be_replaced(self, supervisor_client, manager, other_manager, how):
        customer = make_client(manager)
        admin_customer = make_client(manager)
        region_rule = rule("61", manager)
        if how == "blocked":
            User.objects.filter(pk=manager.pk).update(is_active=False)
        else:
            manager.groups.set([Group.objects.get(name=MARKETING_GROUP)])
        error = FORMER_MANAGER_ERROR.format(email=manager.email)

        for browser, url, field in (
            (supervisor_client, client_change_url(customer), "responsible_manager"),
            (supervisor_client, rule_change_url(region_rule), "manager"),
            (superuser_client(), f"/admin/users/user/{admin_customer.pk}/change/", "responsible_manager"),
            (superuser_client(), f"/admin/common/managerroutingrule/{region_rule.pk}/change/", "manager"),
        ):
            response = browser.get(url)
            form = response.context["adminform"].form
            assert form[field].value() == manager.pk, url
            assert manager.pk in choice_pks(form, field), url

            data = form_payload(response)
            rejected = browser.post(url, data)
            assert rejected.status_code == 200, url
            assert rejected.context["adminform"].form.errors[field] == [error], url

        customer.refresh_from_db()
        admin_customer.refresh_from_db()
        region_rule.refresh_from_db()
        assert customer.responsible_manager == manager
        assert admin_customer.responsible_manager == manager
        assert region_rule.manager == manager

        data = form_payload(supervisor_client.get(client_change_url(customer)))
        data["responsible_manager"] = str(other_manager.pk)
        assert supervisor_client.post(client_change_url(customer), data).status_code == 302
        data = form_payload(supervisor_client.get(rule_change_url(region_rule)))
        data["manager"] = str(other_manager.pk)
        assert supervisor_client.post(rule_change_url(region_rule), data).status_code == 302

        customer.refresh_from_db()
        region_rule.refresh_from_db()
        assert customer.responsible_manager == other_manager
        assert region_rule.manager == other_manager


# --------------------------------------------------------------------------
# AC6 — сотрудники: создание, блокировка, пароль
# --------------------------------------------------------------------------


class TestStaffLifecycle:
    def test_create_block_unblock_password(self, supervisor_client, supervisor):
        response = supervisor_client.get(STAFF_ADD_URL)
        assert list(response.context["adminform"].form.fields["role_group"].choices) == [
            ("Менеджеры", "Менеджеры"),
            ("Маркетинг", "Маркетинг"),
        ]

        payload = staff_create_payload()
        assert supervisor_client.post(STAFF_ADD_URL, payload).status_code == 302
        member = User.objects.get(email=payload["email"])
        assert member.is_staff is True
        assert member.is_superuser is False
        assert list(member.groups.values_list("name", flat=True)) == ["Менеджеры"]
        assert not member.user_permissions.exists()
        assert member.role == "retail"
        assert member.responsible_manager is None
        created = audit_records(member, "create_staff").get()
        assert created.user == supervisor
        assert created.changes == {"email": member.email, "group": "Менеджеры"}

        browser = Client()
        assert browser.login(email=member.email, password=PASSWORD)
        assert browser.get("/manager/").status_code == 200
        assert browser.get(INDEX_URL).status_code == 302
        assert browser.get("/admin/").status_code == 302

        response = post_staff_action(supervisor_client, "block_staff", member)
        assert "Заблокировано сотрудников: 1" in message_texts(response)
        member.refresh_from_db()
        assert member.is_active is False
        assert browser.get("/manager/").status_code == 302
        assert not Client().login(email=member.email, password=PASSWORD)

        post_staff_action(supervisor_client, "unblock_staff", member)
        member.refresh_from_db()
        assert member.is_active is True
        assert Client().login(email=member.email, password=PASSWORD)

        assert supervisor_client.get(staff_password_url(member)).status_code == 200
        response = supervisor_client.post(
            staff_password_url(member),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )
        assert response.status_code == 302
        assert response["Location"] == staff_change_url(member)
        assert Client().login(email=member.email, password=NEW_PASSWORD)

        assert audit_records(member, "block_staff").count() == 1
        assert audit_records(member, "unblock_staff").count() == 1
        assert audit_records(member, "change_password").count() == 1
        assert audit_records(member, "block_staff").get().changes == {"email": member.email, "group": "Менеджеры"}

    def test_list_has_only_staff(self, supervisor_client, supervisor, manager):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        customer = make_client(manager)
        robot = User.objects.create_user(email=f"1c_{get_unique_suffix()}@example.com", password=PASSWORD, role="admin")
        marketer = make_staff_member(MARKETING_GROUP)

        listed = listed_pks(supervisor_client.get(STAFF_URL))

        assert listed == {supervisor.pk, manager.pk, marketer.pk}
        assert not {superuser.pk, customer.pk, robot.pk} & listed

    def test_list_columns_and_group_filter(self, supervisor_client, supervisor, manager):
        make_client(manager)
        make_client(manager)
        marketer = make_staff_member(MARKETING_GROUP)
        loner = make_staff_member(None)

        response = supervisor_client.get(STAFF_URL)
        html = response.content.decode()

        assert '<td class="field-role_group">Менеджеры</td>' in html
        assert '<td class="field-clients_count">2</td>' in html
        assert listed_pks(supervisor_client.get(STAFF_URL, {"role_group": "Маркетинг"})) == {marketer.pk}
        assert listed_pks(supervisor_client.get(STAFF_URL, {"role_group": "none"})) == {loner.pk}
        assert listed_pks(supervisor_client.get(STAFF_URL, {"role_group": "Руководители"})) == {supervisor.pk}

    def test_block_warns_about_manual_clients_and_rules(self, supervisor_client, manager):
        make_client(manager, manual=True)
        rule("23", manager)
        rule("61", manager)

        response = post_staff_action(supervisor_client, "block_staff", manager)

        assert (
            f"У {manager.email} остались 1 клиентов с ручным назначением и правила регионов: 23, 61 — "
            "назначьте клиентам другого менеджера в карточке и замените менеджера в таблице регионов"
        ) in message_texts(response)


class TestStaffEmail:
    """Email сотрудника хранится в нижнем регистре и уникален без учёта регистра."""

    def submit(self, browser: Client, form: str, email: str) -> tuple[Any, User | None]:
        if form == "create":
            return browser.post(STAFF_ADD_URL, staff_create_payload(email=email)), None
        member = make_staff_member(MANAGERS_GROUP)
        data = form_payload(browser.get(staff_change_url(member)))
        data["email"] = email
        return browser.post(staff_change_url(member), data), member

    @pytest.mark.parametrize("form", ["create", "change"])
    def test_mixed_case_is_saved_lowercase(self, supervisor_client, form):
        local = f"Ivan.Petrov_{get_unique_suffix()}"

        response, member = self.submit(supervisor_client, form, f"{local}@FreeSportOpt.RU")

        assert response.status_code == 302
        expected = f"{local.lower()}@freesportopt.ru"
        assert User.objects.filter(email=expected).count() == 1
        if member is not None:
            member.refresh_from_db()
            assert member.email == expected

    @pytest.mark.parametrize("form", ["create", "change"])
    def test_existing_email_in_other_case_is_refused(self, supervisor_client, form):
        # Локальную часть адреса `create_user` не приводит к нижнему регистру —
        # клиент с таким адресом в базе бывает.
        existing = User.objects.create_user(email=f"Ivan.Petrov_{get_unique_suffix()}@example.com", password=PASSWORD)

        response, member = self.submit(supervisor_client, form, existing.email.upper())

        assert response.status_code == 200
        assert response.context["adminform"].form.errors["email"] == ["Пользователь с таким email уже существует."]
        assert list(User.objects.filter(email__iexact=existing.email).values_list("pk", flat=True)) == [existing.pk]
        if member is not None:
            original = member.email
            member.refresh_from_db()
            assert member.email == original


# --------------------------------------------------------------------------
# AC7 — отказы руководителю
# --------------------------------------------------------------------------


def unmanageable(kind: str, supervisor: User) -> User:
    if kind == "self":
        return supervisor
    if kind == "other-supervisor":
        return make_staff_member(SUPERVISORS_GROUP)
    member = make_staff_member(MANAGERS_GROUP)
    if kind == "direct-permission":
        member.user_permissions.add(Permission.objects.get(codename="view_user"))
    else:
        member.groups.add(Group.objects.create(name=f"Склад {get_unique_suffix()}"))
    return member


class TestRefusals:
    def test_superuser_and_client_answer_404(self, supervisor_client, manager):
        superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)
        customer = make_client(manager)

        for target in (superuser, customer):
            assert supervisor_client.get(staff_change_url(target)).status_code == 404
            assert supervisor_client.get(staff_password_url(target)).status_code == 404
            assert supervisor_client.post(staff_password_url(target), {}).status_code == 404

    @pytest.mark.parametrize("kind", ["other-supervisor", "self", "direct-permission", "foreign-group"])
    def test_unmanageable_is_read_only(self, supervisor_client, supervisor, kind):
        target = unmanageable(kind, supervisor)
        before = User.objects.filter(pk=target.pk).values().get()

        response = supervisor_client.get(staff_change_url(target))
        html = response.content.decode()
        assert response.status_code == 200
        for name in ("email", "first_name", "last_name", "phone", "role_group", "_save"):
            assert f'name="{name}"' not in html, name

        payload = {"email": "hacked@example.com", "first_name": "Взлом", "role_group": MARKETING_GROUP}
        assert supervisor_client.post(staff_change_url(target), payload).status_code == 403
        assert supervisor_client.get(staff_password_url(target)).status_code == 403
        response = supervisor_client.post(
            staff_password_url(target),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )
        assert response.status_code == 403

        response = post_staff_action(supervisor_client, "block_staff", target)
        assert SKIPPED_MESSAGE in message_texts(response)
        assert User.objects.filter(pk=target.pk).values().get() == before
        assert not AuditLog.objects.filter(resource_type="User", resource_id=str(target.pk)).exists()

    # «self» нет: заблокированный руководитель в раздел не войдёт.
    @pytest.mark.parametrize("kind", ["other-supervisor", "direct-permission", "foreign-group"])
    def test_unblock_unmanageable_staff_is_refused(self, supervisor_client, supervisor, kind):
        target = unmanageable(kind, supervisor)
        target.is_active = False
        target.save(update_fields=["is_active", "updated_at"])

        response = post_staff_action(supervisor_client, "unblock_staff", target)

        assert SKIPPED_MESSAGE in message_texts(response)
        assert User.objects.get(pk=target.pk).is_active is False
        assert not AuditLog.objects.filter(resource_type="User", resource_id=str(target.pk)).exists()

    def test_forged_privileges_are_ignored(self, supervisor_client, manager, other_manager):
        foreign_group = Group.objects.create(name=f"Склад {get_unique_suffix()}")
        response = supervisor_client.get(staff_change_url(other_manager))
        html = response.content.decode()
        for marker in PRIVILEGE_INPUTS:
            assert marker not in html, marker

        data = form_payload(response)
        data.update(
            {
                "first_name": "Обновлён",
                "is_superuser": "on",
                "is_staff": "",
                "user_permissions": [str(Permission.objects.get(codename="delete_user").pk)],
                "groups": [str(foreign_group.pk)],
                "role": "admin",
                "responsible_manager": str(manager.pk),
                "is_active": "",
            }
        )
        assert supervisor_client.post(staff_change_url(other_manager), data).status_code == 302

        other_manager.refresh_from_db()
        assert other_manager.first_name == "Обновлён"
        assert other_manager.is_superuser is False
        assert other_manager.is_staff is True
        assert other_manager.is_active is True
        assert not other_manager.user_permissions.exists()
        assert list(other_manager.groups.values_list("name", flat=True)) == ["Менеджеры"]
        assert other_manager.role == "retail"
        assert other_manager.responsible_manager is None

    @pytest.mark.parametrize("group", ["Руководители", "Склад"])
    def test_forbidden_group_in_card_and_add_form(self, supervisor_client, other_manager, group):
        response = supervisor_client.get(staff_change_url(other_manager))
        data = form_payload(response)
        data["role_group"] = group
        rejected = supervisor_client.post(staff_change_url(other_manager), data)
        assert rejected.status_code == 200
        assert "role_group" in rejected.context["adminform"].form.errors
        assert list(other_manager.groups.values_list("name", flat=True)) == ["Менеджеры"]

        add_page = supervisor_client.get(STAFF_ADD_URL).content.decode()
        for marker in PRIVILEGE_INPUTS:
            assert marker not in add_page, marker
        payload = staff_create_payload(role_group=group)
        rejected = supervisor_client.post(STAFF_ADD_URL, payload)
        assert rejected.status_code == 200
        assert "role_group" in rejected.context["adminform"].form.errors
        assert not User.objects.filter(email=payload["email"]).exists()


# --------------------------------------------------------------------------
# AC8 — смена группы
# --------------------------------------------------------------------------


class TestGroupChange:
    def change_group(self, browser: Client, member: User, group: str):
        data = form_payload(browser.get(staff_change_url(member)))
        data["role_group"] = group
        return browser.post(staff_change_url(member), data)

    def test_manager_without_clients_moves_to_marketing(self, supervisor_client, supervisor):
        member = make_staff_member(MANAGERS_GROUP)

        assert self.change_group(supervisor_client, member, MARKETING_GROUP).status_code == 302

        assert list(member.groups.values_list("name", flat=True)) == ["Маркетинг"]
        record = audit_records(member, "change_staff_group").get()
        assert record.user == supervisor
        assert record.changes == {"email": member.email, "old": "Менеджеры", "new": "Маркетинг"}
        browser = logged_in(member)
        assert browser.get("/marketing/").status_code == 200
        assert browser.get("/manager/").status_code == 302

    def test_manager_with_clients_and_rules_is_refused(self, supervisor_client, other_manager):
        member = make_staff_member(MANAGERS_GROUP)
        region_rule = rule("23", member)
        by_rule = make_client(member, manual=False, tax_id=region_tax_id("23"))
        manual = make_client(member, manual=True)

        rejected = self.change_group(supervisor_client, member, MARKETING_GROUP)
        assert rejected.status_code == 200
        assert rejected.context["adminform"].form.errors["role_group"] == [
            f"У {member.email} есть клиенты (2) и правила регионов: 23. Замените менеджера в таблице регионов — "
            "клиенты по правилу перейдут сами, — а оставшимся клиентам назначьте другого менеджера в карточке."
        ]
        assert list(member.groups.values_list("name", flat=True)) == ["Менеджеры"]
        assert not audit_records(member, "change_staff_group").exists()

        data = form_payload(supervisor_client.get(rule_change_url(region_rule)))
        data["manager"] = str(other_manager.pk)
        assert supervisor_client.post(rule_change_url(region_rule), data).status_code == 302
        by_rule.refresh_from_db()
        assert by_rule.responsible_manager == other_manager

        data = form_payload(supervisor_client.get(client_change_url(manual)))
        data["responsible_manager"] = str(other_manager.pk)
        assert supervisor_client.post(client_change_url(manual), data).status_code == 302

        assert self.change_group(supervisor_client, member, MARKETING_GROUP).status_code == 302
        assert list(member.groups.values_list("name", flat=True)) == ["Маркетинг"]

    def test_card_offers_no_supervisors(self, supervisor_client, other_manager):
        form = supervisor_client.get(staff_change_url(other_manager)).context["adminform"].form

        assert [value for value, _ in form.fields["role_group"].choices] == ["Менеджеры", "Маркетинг"]
        assert form["role_group"].value() == "Менеджеры"


# --------------------------------------------------------------------------
# AC9 — таблица регионов
# --------------------------------------------------------------------------


class TestRegions:
    def test_create_replace_and_journal(self, supervisor_client, supervisor, manager, other_manager):
        by_rule = make_client(None, manual=False, tax_id=region_tax_id("23"))
        manual = make_client(other_manager, manual=True, tax_id=region_tax_id("23"))
        assert "23 — Краснодарский край" in supervisor_client.get(RULES_URL).content.decode()

        response = supervisor_client.post(RULES_ADD_URL, rule_payload(manager=manager.pk))
        assert response.status_code == 302
        assert response["Location"] == RULES_URL
        region_rule = ManagerRoutingRule.objects.get(match_value="23")
        html = supervisor_client.get(RULES_URL).content.decode()
        assert "23 — Краснодарский край" not in html
        assert '<td class="field-region_display">Краснодарский край</td>' in html
        by_rule.refresh_from_db()
        manual.refresh_from_db()
        assert by_rule.responsible_manager == manager
        assert manual.responsible_manager == other_manager

        data = form_payload(supervisor_client.get(rule_change_url(region_rule)))
        data["manager"] = str(other_manager.pk)
        assert supervisor_client.post(rule_change_url(region_rule), data).status_code == 302
        by_rule.refresh_from_db()
        assert by_rule.responsible_manager == other_manager

        created, updated = rule_audit()
        assert created.user == supervisor
        assert created.resource_id == str(region_rule.pk)
        assert created.changes["operation"] == "create"
        assert created.changes["fields"]["manager_id"] == {"old": None, "new": manager.pk}
        assert updated.changes["operation"] == "update"
        assert updated.changes["rule"] == str(ManagerRoutingRule.objects.get(pk=region_rule.pk))
        assert updated.changes["fields"] == {"manager_id": {"old": manager.pk, "new": other_manager.pk}}

    def test_unchanged_card_writes_nothing(self, supervisor_client, manager):
        region_rule = rule("23", manager)
        data = form_payload(supervisor_client.get(rule_change_url(region_rule)))

        assert supervisor_client.post(rule_change_url(region_rule), data).status_code == 302
        assert rule_audit() == []

    def test_list_save_and_deletes(self, supervisor_client, manager):
        first = rule("23", manager)
        second = rule("61", manager)
        third = rule("77", manager)

        page = supervisor_client.get(RULES_URL)
        data = changelist_payload(page)
        prefix = row_prefix(page, first)
        data.pop(f"{prefix}-is_active")
        data[f"{prefix}-manager_email"] = "region23@example.com"
        assert supervisor_client.post(RULES_URL, data).status_code == 302
        (updated,) = rule_audit("update")
        assert updated.changes["fields"] == {
            "is_active": {"old": True, "new": False},
            "manager_email": {"old": "", "new": "region23@example.com"},
        }

        assert supervisor_client.post(f"{RULES_URL}{second.pk}/delete/", {"post": "yes"}).status_code == 302
        response = supervisor_client.post(
            RULES_URL, {"action": "delete_selected", "_selected_action": [str(third.pk)], "post": "yes"}
        )
        assert response.status_code == 302
        deleted = rule_audit("delete")
        assert [record.resource_id for record in deleted] == [str(second.pk), str(third.pk)]
        assert deleted[0].changes["fields"]["manager_id"] == {"old": manager.pk, "new": None}
        assert not ManagerRoutingRule.objects.filter(pk__in=[second.pk, third.pk]).exists()

    def test_failed_journal_rolls_back_delete_selected(self, supervisor, manager):
        """«Удалить выбранные» — удаление, пересчёт клиентов и журнал одной транзакцией (R42.7-1)."""
        # Клиент — до правила: make_client ставит ответственного update() после создания.
        customer = make_client(None, manual=False, tax_id=region_tax_id("23"))
        target = rule("23", manager)
        assert responsible_ids([customer]) == {manager.pk}
        model_admin = supervisor_site._registry[ManagerRoutingRule]

        with failing_journal(), pytest.raises(RuntimeError):
            model_admin.delete_queryset(action_request(supervisor), ManagerRoutingRule.objects.filter(pk=target.pk))

        assert ManagerRoutingRule.objects.filter(pk=target.pk).exists()
        assert responsible_ids([customer]) == {manager.pk}

    def test_fallback_needs_supervisor(self, supervisor_client, supervisor, manager):
        payload = rule_payload(match_type="fallback", match_value="default", manager=manager.pk)

        rejected = supervisor_client.post(RULES_ADD_URL, payload)
        assert rejected.status_code == 200
        assert rejected.context["adminform"].form.errors["manager"] == [FALLBACK_ERROR]
        rejected = superuser_client().post("/admin/common/managerroutingrule/add/", payload)
        assert rejected.status_code == 200
        assert rejected.context["adminform"].form.errors["manager"] == [FALLBACK_ERROR]
        assert not ManagerRoutingRule.objects.exists()

        payload["manager"] = str(supervisor.pk)
        assert supervisor_client.post(RULES_ADD_URL, payload).status_code == 302
        fallback = ManagerRoutingRule.objects.get(match_type="fallback")

        data = form_payload(supervisor_client.get(rule_change_url(fallback)))
        data["manager"] = str(manager.pk)
        rejected = supervisor_client.post(rule_change_url(fallback), data)
        assert rejected.context["adminform"].form.errors["manager"] == [FALLBACK_ERROR]
        fallback.refresh_from_db()
        assert fallback.manager == supervisor


# --------------------------------------------------------------------------
# AC10 — заблокированный менеджер в правилах регионов (решение 17)
# --------------------------------------------------------------------------


# Значение правила менеджера A по типу: регион 23 или страна (R42.7-7).
BLOCKED_RULE_VALUES = {
    ManagerRoutingRule.MATCH_INN_REGION: "23",
    ManagerRoutingRule.MATCH_COUNTRY: "Беларусь",
}


def keyed_client_fields(match_type: str) -> dict[str, Any]:
    """Реквизиты клиента, которого назначает правило менеджера A: ИНН региона 23 или страна."""
    if match_type == ManagerRoutingRule.MATCH_COUNTRY:
        return {"country": BLOCKED_RULE_VALUES[match_type]}
    return {"tax_id": region_tax_id("23")}


@pytest.fixture
def blocked_rule_type() -> str:
    """Тип правила менеджера A; тест правила страны переопределяет его параметризацией."""
    return ManagerRoutingRule.MATCH_INN_REGION


@pytest.fixture
def blocked_setup(manager, blocked_rule_type):
    """Менеджер A с правилом региона 23 или страны, резерв — руководитель R; пять клиентов по правилу и один ручной."""
    chief = make_staff_member(SUPERVISORS_GROUP)
    by_rule = [make_client(None, manual=False, **keyed_client_fields(blocked_rule_type)) for _ in range(5)]
    manual = make_client(manager, manual=True, **keyed_client_fields(blocked_rule_type))
    rule(
        BLOCKED_RULE_VALUES[blocked_rule_type],
        manager,
        match_type=blocked_rule_type,
        manager_email="region23@example.com",
    )
    rule("default", chief, match_type="fallback", manager_email="fallback@example.com")
    return chief, by_rule, manual


def responsible_ids(clients: list[User]) -> set[int | None]:
    return set(User.objects.filter(pk__in=[c.pk for c in clients]).values_list("responsible_manager", flat=True))


def new_region_client(match_type: str = ManagerRoutingRule.MATCH_INN_REGION) -> User:
    return User.objects.create_user(
        email=f"new_{get_unique_suffix()}@example.com",
        password=PASSWORD,
        role="wholesale_level1",
        **keyed_client_fields(match_type),
    )


class TestBlockedManagerInRules:
    @pytest.mark.parametrize(
        "blocked_rule_type", [ManagerRoutingRule.MATCH_INN_REGION, ManagerRoutingRule.MATCH_COUNTRY]
    )
    def test_block_and_unblock_in_section(self, supervisor_client, manager, blocked_setup, blocked_rule_type):
        chief, by_rule, manual = blocked_setup
        assert responsible_ids(by_rule) == {manager.pk}

        response = post_staff_action(supervisor_client, "block_staff", manager)

        assert responsible_ids(by_rule) == {chief.pk}
        assert responsible_ids([manual]) == {manager.pk}
        assert (
            f"У {manager.email} остались 1 клиентов с ручным назначением и правила регионов: "
            f"{BLOCKED_RULE_VALUES[blocked_rule_type]} — "
            "назначьте клиентам другого менеджера в карточке и замените менеджера в таблице регионов"
        ) in message_texts(response)
        newcomer = new_region_client(blocked_rule_type)
        assert newcomer.responsible_manager == chief
        assert resolve_manager_recipients(newcomer.country, newcomer.tax_id) == [chief.email]

        post_staff_action(supervisor_client, "unblock_staff", manager)

        assert responsible_ids([*by_rule, newcomer]) == {manager.pk}
        assert responsible_ids([manual]) == {manager.pk}
        assert new_region_client(blocked_rule_type).responsible_manager == manager
        assert resolve_manager_recipients(newcomer.country, newcomer.tax_id) == [manager.email]

    @pytest.mark.parametrize("block_with", ["action", "card"])
    def test_superuser_in_admin(self, manager, blocked_setup, block_with):
        chief, by_rule, _ = blocked_setup
        browser = superuser_client()
        card_url = f"/admin/users/user/{manager.pk}/change/"

        if block_with == "action":
            response = browser.post(
                "/admin/users/user/", {"action": "block_users", "_selected_action": [str(manager.pk)]}
            )
            assert response.status_code == 302
        else:
            data = form_payload(browser.get(card_url))
            data.pop("is_active")
            assert browser.post(card_url, data).status_code == 302
        assert responsible_ids(by_rule) == {chief.pk}

        data = form_payload(browser.get(card_url))
        data["is_active"] = "on"
        assert browser.post(card_url, data).status_code == 302
        assert responsible_ids(by_rule) == {manager.pk}

    @pytest.mark.parametrize(
        "site, action",
        [(supervisor_site, "block_staff"), (supervisor_site, "unblock_staff"), (admin.site, "block_users")],
        ids=["block_staff", "unblock_staff", "block_users"],
    )
    def test_failed_journal_rolls_back_block(self, supervisor, manager, blocked_setup, site, action):
        """Блокировка, пересчёт клиентов сигналом и журнал — одной транзакцией (R42.7-1)."""
        chief, by_rule, _ = blocked_setup
        was_active = not action.startswith("unblock")
        if not was_active:
            manager.is_active = False
            manager.save(update_fields=["is_active", "updated_at"])
        owner = {chief.pk} if not was_active else {manager.pk}
        assert responsible_ids(by_rule) == owner
        author = supervisor
        if site is admin.site:
            author = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)

        with failing_journal(), pytest.raises(RuntimeError):
            getattr(site._registry[User], action)(action_request(author), User.objects.filter(pk=manager.pk))

        assert User.objects.get(pk=manager.pk).is_active is was_active
        assert responsible_ids(by_rule) == owner

    def test_failed_journal_rolls_back_unblock_users(self, manager):
        """Разблокировка клиента в `/admin/` — тоже одной транзакцией с журналом (R42.7-1)."""
        customer = make_client(manager, is_active=False)
        author = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password=PASSWORD)

        with failing_journal(), pytest.raises(RuntimeError):
            admin.site._registry[User].unblock_users(action_request(author), User.objects.filter(pk=customer.pk))

        assert User.objects.get(pk=customer.pk).is_active is False

    def test_fallback_change_reaches_clients_of_blocked_manager(self, manager, blocked_setup):
        """Регион заблокированного не считается покрытым: смена резерва уводит и его клиентов."""
        _, by_rule, _ = blocked_setup
        manager.is_active = False
        manager.save()
        new_chief = make_staff_member(SUPERVISORS_GROUP)

        fallback = ManagerRoutingRule.objects.get(match_type="fallback")
        fallback.manager = new_chief
        fallback.save()

        assert responsible_ids(by_rule) == {new_chief.pk}

    def test_save_without_activity_change_does_not_recalculate(self, manager, blocked_setup):
        _, by_rule, _ = blocked_setup
        customer = User.objects.get(pk=by_rule[0].pk)
        customer.phone = "+79009998877"

        with CaptureQueriesContext(connection) as captured:
            customer.save()

        assert not [q["sql"] for q in captured.captured_queries if "managerroutingrule" in q["sql"]]

    def test_blocked_fallback_supervisor_gives_nobody(self, blocked_setup):
        chief, _, _ = blocked_setup
        outside = make_client(None, manual=False, tax_id=region_tax_id("50"))
        reassign_clients_for_key(None)
        assert responsible_ids([outside]) == {chief.pk}

        chief.is_active = False
        chief.save()

        assert responsible_ids([outside]) == {None}


# --------------------------------------------------------------------------
# AC11 — уведомления и бонусы
# --------------------------------------------------------------------------


@pytest.fixture
def bonus_operations(supervisor):
    trainer = User.objects.create_user(
        email=f"trainer_{get_unique_suffix()}@example.com", password=PASSWORD, role="trainer", is_verified=True
    )
    master = create_master_with_subs(trainer, ["100000.00"])
    close_master(master)
    accrual = BonusTransaction.objects.get(order=master)
    payout = BonusTransaction.objects.create(
        user=trainer,
        transaction_type=BonusTransaction.PAYOUT,
        amount=Decimal("100.00"),
        comment="Выплата наличными",
        created_by=supervisor,
    )
    return accrual, payout


class TestNotificationsAndBonuses:
    def test_recipients(self, supervisor_client):
        assert supervisor_client.get(RECIPIENTS_URL).status_code == 200
        response = supervisor_client.post(
            f"{RECIPIENTS_URL}add/",
            {"email": "boss@example.com", "name": "Начальник", "is_active": "on", "notify_new_orders": "on"},
        )
        assert response.status_code == 302
        recipient = NotificationRecipient.objects.get(email="boss@example.com")

        page = supervisor_client.get(RECIPIENTS_URL)
        data = changelist_payload(page)
        data[f"{row_prefix(page, recipient)}-notify_low_stock"] = "on"
        assert supervisor_client.post(RECIPIENTS_URL, data).status_code == 302
        recipient.refresh_from_db()
        assert recipient.notify_low_stock is True
        assert recipient.notify_new_orders is True

    def test_settings(self, supervisor_client):
        # Пока записи нет, родитель разрешил бы добавление любому — раздел запрещает.
        assert not BonusProgramSettings.objects.exists()
        assert supervisor_client.get(f"{SETTINGS_URL}add/").status_code == 403
        settings_obj = BonusProgramSettings.load()
        url = f"{SETTINGS_URL}{settings_obj.pk}/change/"

        html = supervisor_client.get(url).content.decode()
        assert "deletelink" not in html
        # Ссылки «Добавить» других моделей есть в боковой навигации — ищем ссылку этой.
        assert f'href="{SETTINGS_URL}add/"' not in supervisor_client.get(SETTINGS_URL).content.decode()
        response = supervisor_client.post(
            url,
            {
                "is_active": "on",
                "percent": "7.00",
                "accrual_status": "delivered",
                "program_start_at_0": "2026-01-01",
                "program_start_at_1": "00:00:00",
            },
        )
        assert response.status_code == 302
        settings_obj.refresh_from_db()
        assert settings_obj.percent == Decimal("7.00")
        assert supervisor_client.get(f"{SETTINGS_URL}add/").status_code == 403
        assert supervisor_client.get(f"{SETTINGS_URL}{settings_obj.pk}/delete/").status_code == 403

    def test_transactions_are_read_only(self, supervisor_client, bonus_operations):
        html = supervisor_client.get(TRANSACTIONS_URL).content.decode()
        assert f'href="{TRANSACTIONS_URL}add/"' not in html
        assert 'href="/admin/' not in html
        assert not USER_CARD_LINK.search(html)

        for operation in bonus_operations:
            url = f"{TRANSACTIONS_URL}{operation.pk}/change/"
            html = supervisor_client.get(url).content.decode()
            for marker in ('name="amount"', 'name="comment"', 'name="_save"', "deletelink"):
                assert marker not in html, (operation.transaction_type, marker)
            assert 'href="/admin/' not in html
            assert not USER_CARD_LINK.search(html)
            assert supervisor_client.post(url, {"comment": "Подмена"}).status_code == 403
        assert supervisor_client.get(f"{TRANSACTIONS_URL}add/").status_code == 403
        accrual, payout = bonus_operations
        assert accrual.order.order_number_display in supervisor_client.get(TRANSACTIONS_URL).content.decode()


# --------------------------------------------------------------------------
# AC12 — ссылки и главная
# --------------------------------------------------------------------------


class TestLinksAndIndex:
    def test_index(self, supervisor_client):
        response = supervisor_client.get(INDEX_URL)
        html = response.content.decode()

        assert 'href="/manager/"' in html
        assert 'href="/marketing/"' in html
        names = [app["name"] for app in response.context["app_list"]]
        for block in ("Сотрудники", "Регионы и уведомления", "Бонусная программа"):
            assert block in names
        common = next(app for app in response.context["app_list"] if app["app_label"] == "common")
        assert "Правила регионов" in [model["name"] for model in common["models"]]
        assert "Последние действия" not in html
        assert 'href="/admin/' not in html

    def test_pages_have_no_admin_links(self, supervisor_client, manager, bonus_operations):
        region_rule = rule("23", manager)
        recipient = NotificationRecipient.objects.create(email="boss@example.com")
        settings_obj = BonusProgramSettings.load()
        data = form_payload(supervisor_client.get(staff_change_url(manager)))
        data["first_name"] = "Изменён"
        assert supervisor_client.post(staff_change_url(manager), data).status_code == 302

        urls = [
            INDEX_URL,
            STAFF_URL,
            STAFF_ADD_URL,
            staff_change_url(manager),
            f"{STAFF_URL}{manager.pk}/history/",
            staff_password_url(manager),
            RULES_URL,
            RULES_ADD_URL,
            rule_change_url(region_rule),
            RECIPIENTS_URL,
            f"{RECIPIENTS_URL}{recipient.pk}/change/",
            SETTINGS_URL,
            f"{SETTINGS_URL}{settings_obj.pk}/change/",
            TRANSACTIONS_URL,
            f"{TRANSACTIONS_URL}{bonus_operations[0].pk}/change/",
        ]
        for url in urls:
            response = supervisor_client.get(url)
            assert response.status_code == 200, url
            html = response.content.decode()
            assert 'href="/admin/' not in html, url
            assert "viewsitelink" not in html, url

    def test_redirects_stay_in_section(self, supervisor_client, manager):
        data = form_payload(supervisor_client.get(staff_change_url(manager)))
        assert supervisor_client.post(staff_change_url(manager), data)["Location"] == STAFF_URL
        data["_continue"] = "1"
        assert supervisor_client.post(staff_change_url(manager), data)["Location"] == staff_change_url(manager)

        response = supervisor_client.post(RULES_ADD_URL, {**rule_payload(manager=manager.pk), "_continue": "1"})
        region_rule = ManagerRoutingRule.objects.get(match_value="23")
        assert response["Location"] == rule_change_url(region_rule)

        payload = staff_create_payload()
        response = supervisor_client.post(STAFF_ADD_URL, payload)
        member = User.objects.get(email=payload["email"])
        assert response["Location"] == staff_change_url(member)


# --------------------------------------------------------------------------
# AC13 — отказ по прямым URL
# --------------------------------------------------------------------------


class TestDirectUrls:
    @pytest.mark.parametrize("group", [MANAGERS_GROUP, MARKETING_GROUP])
    def test_other_roles_are_redirected(self, client, other_manager, group):
        client.force_login(make_staff_member(group))
        settings_obj = BonusProgramSettings.load()
        region_rule = rule("23", other_manager)
        recipient = NotificationRecipient.objects.create(email="boss@example.com")

        for url in (
            INDEX_URL,
            STAFF_URL,
            staff_change_url(other_manager),
            staff_password_url(other_manager),
            RULES_URL,
            rule_change_url(region_rule),
            RECIPIENTS_URL,
            f"{RECIPIENTS_URL}{recipient.pk}/change/",
            SETTINGS_URL,
            f"{SETTINGS_URL}{settings_obj.pk}/change/",
            TRANSACTIONS_URL,
        ):
            response = client.get(url)
            assert response.status_code == 302, url
            assert response["Location"].startswith(f"{LOGIN_URL}?next="), url

    @pytest.mark.parametrize(
        "url",
        [
            "/supervisor/orders/order/",
            "/supervisor/products/product/",
            "/supervisor/common/auditlog/",
            "/supervisor/common/newsletter/",
            "/supervisor/auth/group/",
        ],
    )
    def test_unregistered_models_are_404(self, supervisor_client, url):
        assert supervisor_client.get(url).status_code == 404


# --------------------------------------------------------------------------
# AC14 — число запросов
# --------------------------------------------------------------------------


def count_queries(browser: Client, url: str) -> tuple[int, Any]:
    with CaptureQueriesContext(connection) as captured:
        response = browser.get(url)
    assert response.status_code == 200
    return len(captured), response


class TestQueryCount:
    def test_staff_list(self, supervisor_client, django_assert_num_queries):
        def add(count: int) -> None:
            for index in range(count):
                member = make_staff_member(MANAGERS_GROUP if index % 2 else MARKETING_GROUP)
                make_client(member)

        add(4)
        baseline, first = count_queries(supervisor_client, STAFF_URL)
        assert len(first.context["cl"].result_list) == 5
        add(25)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(STAFF_URL)
        assert len(response.context["cl"].result_list) == 30

    def test_department_clients(self, supervisor_client, django_assert_num_queries):
        def add(managers: int, clients: int) -> None:
            team = [make_staff_member(MANAGERS_GROUP) for _ in range(managers)]
            for index in range(clients):
                make_client(team[index % managers])

        add(2, 5)
        baseline, _ = count_queries(supervisor_client, CLIENTS_URL)
        add(8, 45)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(CLIENTS_URL)
        assert len(response.context["cl"].result_list) == 50

    def test_rules(self, supervisor_client, django_assert_num_queries):
        codes = sorted(REGION_NAMES)

        def add(start: int, count: int) -> None:
            for code in codes[start : start + count]:
                rule(code, make_staff_member(MANAGERS_GROUP))

        add(0, 5)
        baseline, _ = count_queries(supervisor_client, RULES_URL)
        add(5, 45)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(RULES_URL)
        assert len(response.context["cl"].result_list) == 50

    def test_bonus_transactions(self, supervisor_client, supervisor, django_assert_num_queries):
        trainers = [
            User.objects.create_user(email=f"t_{get_unique_suffix()}@example.com", password=PASSWORD, role="trainer")
            for _ in range(3)
        ]

        def add(count: int) -> None:
            for index in range(count):
                BonusTransaction.objects.create(
                    user=trainers[index % 3],
                    transaction_type=BonusTransaction.WRITEOFF,
                    amount=Decimal("10.00"),
                    comment="Списание",
                    created_by=supervisor,
                )

        add(5)
        baseline, _ = count_queries(supervisor_client, TRANSACTIONS_URL)
        add(45)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(TRANSACTIONS_URL)
        assert len(response.context["cl"].result_list) == 50

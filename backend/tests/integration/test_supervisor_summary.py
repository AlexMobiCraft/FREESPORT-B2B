"""
Integration-тесты сводки руководителя `/supervisor/summary/` (стори 42.8).

Покрывает:
- AC1 — вход и отказ, страницы нет на других сайтах, просмотр не пишет журнал;
- AC2 — заявки на верификацию по менеджерам, число = список по ссылке;
- AC3 — период по умолчанию, быстрые ссылки, границы суток, ошибки формы;
- AC4 — заказы и выручка по менеджерам, все действующие менеджеры с нулями;
- AC5 — заказы и выручка по регионам;
- AC6 — регистрации, верифицированные без заказов и фильтр «Заказы»;
- AC7 — ссылки страницы и главной, экранирование подписей;
- AC8 — число запросов не зависит от числа строк.

Тесты транзакционные (autouse `clear_db_before_test` в `tests/conftest.py`):
группы ролей заново создаёт `role_groups`, правила регионов задаёт сам тест.
Ожидаемые подписи, суммы, тексты и ссылки — литералами.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal
from html import unescape
from html.parser import HTMLParser
from typing import Any
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.db.models import Q

from apps.common.models import AuditLog
from apps.orders.models import Order
from apps.users.manager_admin import ClientOrdersFilter
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, SUPERVISORS_GROUP
from tests.factories import ProductFactory
from tests.integration.test_manager_clients_section import (  # noqa: F401 — фикстуры подключаются импортом
    PASSWORD,
    get_unique_suffix,
    make_1c_record,
    make_client,
    make_staff_member,
    manager,
    no_routing_rules,
    other_manager,
    region_tax_id,
    role_groups,
    verified_email_task,
)
from tests.integration.test_manager_orders_section import (  # noqa: F401 — фикстуры подключаются импортом
    local_noon,
    make_applicant,
    make_master,
    order_emails,
    set_created_at,
)
from tests.integration.test_supervisor_section import (  # noqa: F401 — фикстуры подключаются импортом
    count_queries,
    listed_pks,
    logged_in,
    supervisor,
    supervisor_client,
)

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

SUMMARY_URL = "/supervisor/summary/"
CLIENTS_URL = "/manager/users/user/"
LOGIN_URL = "/supervisor/login/"
MOSCOW = ZoneInfo("Europe/Moscow")
# «Сегодня» сводки в тестах периода по умолчанию.
TODAY_NOON = datetime(2026, 10, 17, 12, 0, tzinfo=MOSCOW)
PERIOD = {"date_from": "2026-10-10", "date_to": "2026-10-12"}
IN_PERIOD = datetime(2026, 10, 11, 12, 0, tzinfo=MOSCOW)


class _Tables(HTMLParser):
    """Строки таблиц блоков сводки (`div id="summary-…"`): тексты ячеек и ссылки."""

    def __init__(self) -> None:
        super().__init__()
        self.rows: dict[str, list[tuple[str, ...]]] = {}
        self.links: dict[str, list[list[str]]] = {}
        self._block: str | None = None
        self._in_head = False
        self._row: list[str] | None = None
        self._row_links: list[str] = []
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        block = values.get("id") or ""
        if tag == "div" and block.startswith("summary-"):
            self._block = block
            self.rows[block] = []
            self.links[block] = []
        elif tag == "thead":
            self._in_head = True
        elif tag == "tr" and self._block and not self._in_head:
            self._row, self._row_links = [], []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []
        elif tag == "a" and self._row is not None:
            self._row_links.append(values["href"] or "")

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "thead":
            self._in_head = False
        elif tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None and self._block:
            self.rows[self._block].append(tuple(self._row))
            self.links[self._block].append(self._row_links)
            self._row = None


def tables(response) -> _Tables:
    assert response.status_code == 200
    parser = _Tables()
    parser.feed(response.content.decode())
    return parser


def label(user: User, blocked: bool = False) -> str:
    text = f"{user.first_name} {user.last_name} ({user.email})"
    return text + " — заблокирован" if blocked else text


def set_order_created(order: Order, value: datetime) -> Order:
    # Мастер переносится вместе с субзаказами: в период они попадают все,
    # и второй раз субзаказы не складываются только из-за `is_master`.
    Order.objects.filter(Q(pk=order.pk) | Q(parent_order=order)).update(created_at=value)
    return order


def master_in_period(client: User | None, amount: str, **extra: Any) -> Order:
    extra.setdefault("subs", 0)
    return set_order_created(make_master(client, total_amount=Decimal(amount), **extra), IN_PERIOD)


# --------------------------------------------------------------------------
# AC1 — вход и отказ
# --------------------------------------------------------------------------


class TestEntry:
    def test_supervisor_opens_summary(self, supervisor_client, manager):
        make_applicant(manager)
        master_in_period(make_client(manager), "100.00")
        audit_before = AuditLog.objects.count()

        response = supervisor_client.get(SUMMARY_URL, PERIOD)

        assert response.status_code == 200
        html = response.content.decode()
        assert "OPTISPORT — Руководитель" in html
        assert "<h1>Сводка</h1>" in html
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

        response = client.get(SUMMARY_URL)

        assert response.status_code == 302
        assert response["Location"] == "/supervisor/login/?next=/supervisor/summary/"

    def test_no_summary_on_other_sites(self, supervisor_client):
        assert supervisor_client.get("/manager/summary/").status_code == 404
        assert supervisor_client.get("/marketing/summary/").status_code == 404


# --------------------------------------------------------------------------
# AC2 — заявки на верификацию
# --------------------------------------------------------------------------


class TestPending:
    def test_rows_order_and_links(self, supervisor_client):
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        b = make_staff_member(MANAGERS_GROUP, first_name="Борис", last_name="Второй")
        c = make_staff_member(MANAGERS_GROUP, first_name="Вера", last_name="Блокова", is_active=False)
        a_applicants = [make_applicant(a) for _ in range(3)]
        set_created_at(a_applicants[0], local_noon(5))
        set_created_at(a_applicants[1], local_noon(1))
        make_applicant(b)
        set_created_at(make_applicant(c), local_noon(2))
        unassigned = [make_applicant(None), make_applicant(None)]
        # Не считаются: запись 1С без аккаунта, верифицированный клиент, сотрудник.
        make_client(a, role=User.ROLE_UNREGISTERED, verification_status="pending", is_verified=False)
        make_client(a)
        staff = make_staff_member(MARKETING_GROUP, verification_status="pending")
        User.objects.filter(pk=staff.pk).update(responsible_manager=a)

        page = tables(supervisor_client.get(SUMMARY_URL))

        assert page.rows["summary-pending"] == [
            (label(a), "3", "5 дней"),
            (label(c, blocked=True), "1", "2 дня"),
            (label(b), "1", "сегодня"),
            ("Без ответственного", "2", "сегодня"),
            ("Итого", "7", ""),
        ]
        links = [row[0] for row in page.links["summary-pending"][:4]]
        assert links == [
            f"/manager/users/user/?verification_status__exact=pending&responsible={a.pk}",
            f"/manager/users/user/?verification_status__exact=pending&responsible={c.pk}",
            f"/manager/users/user/?verification_status__exact=pending&responsible={b.pk}",
            "/manager/users/user/?verification_status__exact=pending&responsible=none",
        ]
        # Число в строке = список по её ссылке.
        assert listed_pks(supervisor_client.get(links[0])) == {applicant.pk for applicant in a_applicants}
        assert supervisor_client.get(links[1]).context["cl"].result_count == 1
        assert supervisor_client.get(links[2]).context["cl"].result_count == 1
        assert listed_pks(supervisor_client.get(links[3])) == {applicant.pk for applicant in unassigned}

    def test_manager_name_links_to_his_pending_list(self, supervisor_client):
        tricky = make_staff_member(MANAGERS_GROUP, first_name="<b>X</b>", last_name="Тегов")
        applicants = [make_applicant(tricky) for _ in range(2)]
        make_client(tricky)
        make_applicant(None)

        response = supervisor_client.get(SUMMARY_URL)
        html = response.content.decode()
        url = f"/manager/users/user/?verification_status__exact=pending&responsible={tricky.pk}"

        # В атрибуте `&` экранируется Django, браузер отдаёт его обратно как `&`.
        assert f'<th scope="row"><a href="{url.replace("&", "&amp;")}">&lt;b&gt;X&lt;/b&gt; Тегов' in html
        assert (
            '<th scope="row"><strong><a href="/manager/users/user/?verification_status__exact=pending'
            '&amp;responsible=none">Без ответственного</a></strong></th>'
        ) in html
        assert listed_pks(supervisor_client.get(url)) == {applicant.pk for applicant in applicants}
        total = html[html.index('class="summary-total"') :]
        assert "<a " not in total[: total.index("</tr>")]

    def test_unassigned_row_is_always_shown(self, supervisor_client, manager):
        make_applicant(manager)

        response = supervisor_client.get(SUMMARY_URL)
        page = tables(response)

        assert page.rows["summary-pending"][-2:] == [("Без ответственного", "0", "—"), ("Итого", "1", "")]
        assert '<tr class="summary-unassigned">' in response.content.decode()
        assert re.search(r"<strong><a [^>]*>Без ответственного</a></strong>", response.content.decode())

    def test_empty_queue(self, supervisor_client):
        response = supervisor_client.get(SUMMARY_URL)
        page = tables(response)

        assert page.rows["summary-pending"] == [("Без ответственного", "0", "—"), ("Итого", "0", "")]
        # Блок стоит под формой периода, но от периода не зависит — страница это говорит.
        html = response.content.decode()
        block = html[html.index('id="summary-pending"') : html.index('id="summary-orders-by-manager"')]
        assert '<p class="help">Текущая очередь, от периода не зависит</p>' in block

    def test_queue_does_not_depend_on_period(self, supervisor_client):
        # Заявки поданы в разные периоды; очередь при любом периоде одна и та же.
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        set_created_at(make_applicant(a), datetime(2026, 10, 11, 12, 0, tzinfo=MOSCOW))
        set_created_at(make_applicant(a), datetime(2026, 9, 15, 12, 0, tzinfo=MOSCOW))
        set_created_at(make_applicant(None), TODAY_NOON)
        expected_rows = [
            (label(a), "2", "32 дня"),
            ("Без ответственного", "1", "сегодня"),
            ("Итого", "3", ""),
        ]
        # Имя менеджера и число в строке ведут в один и тот же список.
        a_url = f"/manager/users/user/?verification_status__exact=pending&responsible={a.pk}"
        none_url = "/manager/users/user/?verification_status__exact=pending&responsible=none"
        expected_links = [[a_url, a_url], [none_url, none_url], []]

        for params in (PERIOD, {"date_from": "2026-09-01", "date_to": "2026-09-30"}, {}):
            with patch("django.utils.timezone.now", return_value=TODAY_NOON):
                page = tables(supervisor_client.get(SUMMARY_URL, params))
            assert page.rows["summary-pending"] == expected_rows, params
            assert page.links["summary-pending"] == expected_links, params


# --------------------------------------------------------------------------
# AC3 — период
# --------------------------------------------------------------------------


class TestPeriod:
    def test_default_period_and_presets(self, supervisor_client):
        with patch("django.utils.timezone.now", return_value=TODAY_NOON):
            response = supervisor_client.get(SUMMARY_URL)

        html = response.content.decode()
        assert "Период: 01.10.2026 — 17.10.2026" in html
        assert 'name="date_from" value="2026-10-01"' in html
        assert 'name="date_to" value="2026-10-17"' in html
        for query, name in [
            ("date_from=2026-10-17&amp;date_to=2026-10-17", "Сегодня"),
            ("date_from=2026-10-11&amp;date_to=2026-10-17", "7 дней"),
            ("date_from=2026-09-18&amp;date_to=2026-10-17", "30 дней"),
            ("date_from=2026-09-01&amp;date_to=2026-09-30", "Прошлый месяц"),
        ]:
            assert f'<a href="?{query}">{name}</a>' in html
        assert '<strong><a href="?date_from=2026-10-01&amp;date_to=2026-10-17">Этот месяц</a></strong>' in html

    def test_selected_preset(self, supervisor_client):
        with patch("django.utils.timezone.now", return_value=TODAY_NOON):
            response = supervisor_client.get(SUMMARY_URL, {"date_from": "2026-10-11", "date_to": "2026-10-17"})

        html = response.content.decode()
        assert "Период: 11.10.2026 — 17.10.2026" in html
        assert '<strong><a href="?date_from=2026-10-11&amp;date_to=2026-10-17">7 дней</a></strong>' in html
        assert '<a href="?date_from=2026-10-01&amp;date_to=2026-10-17">Этот месяц</a>' in html

    def test_day_boundaries(self, supervisor_client, manager):
        client_user = make_client(manager)
        orders = {
            "last-minute": ("300.00", datetime(2026, 10, 12, 23, 59, tzinfo=MOSCOW)),
            "next-day": ("9999.00", datetime(2026, 10, 13, 0, 0, tzinfo=MOSCOW)),
            # 09.10 21:00 UTC — ровно 10.10 00:00 по Москве, нижняя граница входит.
            "utc-evening": ("50.00", datetime(2026, 10, 9, 21, 0, tzinfo=UTC)),
            "day-before": ("7.00", datetime(2026, 10, 9, 23, 59, tzinfo=MOSCOW)),
        }
        for amount, created in orders.values():
            set_order_created(make_master(client_user, total_amount=Decimal(amount), subs=0), created)

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"][0] == (label(manager), "2", "350,00\xa0₽", "0")

    @pytest.mark.parametrize(
        ("params", "error"),
        [
            pytest.param(
                {"date_from": "2026-10-12", "date_to": "2026-10-10"}, "Начало периода позже его конца.", id="reversed"
            ),
            pytest.param({"date_from": "2026-10-10"}, "Обязательное поле.", id="only-from"),
            pytest.param({"date_to": "2026-10-12"}, "Обязательное поле.", id="only-to"),
            pytest.param(
                {"date_from": "2026-10-10", "date_to": "9999-12-31"},
                "Конец периода вне допустимого диапазона.",
                id="date-max",
            ),
        ],
    )
    def test_invalid_period_falls_back_to_default(self, supervisor_client, manager, params, error):
        # Заказ 05.10 — вне 10.10–12.10, но в периоде по умолчанию.
        set_order_created(
            make_master(make_client(manager), total_amount=Decimal("100.00"), subs=0),
            datetime(2026, 10, 5, 12, 0, tzinfo=MOSCOW),
        )

        with patch("django.utils.timezone.now", return_value=TODAY_NOON):
            response = supervisor_client.get(SUMMARY_URL, params)

        html = response.content.decode()
        assert response.status_code == 200
        assert error in html
        assert html.index(error) < html.index('name="date_from"')
        assert "Период: 01.10.2026 — 17.10.2026" in html
        assert tables(response).rows["summary-orders-by-manager"][0] == (label(manager), "1", "100,00\xa0₽", "0")


# --------------------------------------------------------------------------
# AC4 — заказы и выручка по менеджерам
# --------------------------------------------------------------------------


class TestOrdersByManager:
    def test_rows_totals_and_period(self, supervisor_client, supervisor):
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        b = make_staff_member(MANAGERS_GROUP, first_name="Борис", last_name="Второй")
        client_a = make_client(a)
        client_b = make_client(b)
        master_in_period(client_a, "1000.00", subs=2)  # два субзаказа по 500 ₽
        master_in_period(client_a, "300.00")  # legacy-мастер без субзаказов
        master_in_period(client_a, "700.00", status="cancelled")
        master_in_period(client_b, "2000.00", status="refunded")
        master_in_period(client_b, "400.00")
        master_in_period(make_client(None), "150.00")
        master_in_period(None, "50.00")
        set_order_created(
            make_master(client_a, total_amount=Decimal("9999.00"), subs=0),
            datetime(2026, 9, 15, 12, 0, tzinfo=MOSCOW),
        )
        # Заказ учётной записи сотрудника (ответственный — A) в сводку не входит.
        staff = make_staff_member(MARKETING_GROUP)
        User.objects.filter(pk=staff.pk).update(responsible_manager=a)
        master_in_period(staff, "5000.00")

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"] == [
            (label(a), "2", "1\xa0300,00\xa0₽", "1"),
            (label(b), "1", "400,00\xa0₽", "1"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
            ("Без ответственного", "1", "150,00\xa0₽", "0"),
            ("Без клиента", "1", "50,00\xa0₽", "0"),
            ("Итого", "5", "1\xa0900,00\xa0₽", "2"),
        ]
        # Региональный итог тоже без субзаказов и заказа сотрудника.
        assert page.rows["summary-orders-by-region"][-1] == ("Итого", "5", "1\xa0900,00\xa0₽", "2")

        wider = tables(supervisor_client.get(SUMMARY_URL, {"date_from": "2026-09-01", "date_to": "2026-10-12"}))
        assert wider.rows["summary-orders-by-manager"][0] == (label(a), "3", "11\xa0299,00\xa0₽", "1")

        # Клиент A передан B: его заказы — в строке B (по текущему ответственному).
        User.objects.filter(pk=client_a.pk).update(responsible_manager=b)
        moved = tables(supervisor_client.get(SUMMARY_URL, PERIOD))
        assert moved.rows["summary-orders-by-manager"][:3] == [
            (label(b), "3", "1\xa0700,00\xa0₽", "2"),
            (label(a), "0", "0,00\xa0₽", "0"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
        ]

    def test_all_current_managers_are_listed(self, supervisor_client, supervisor):
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        d = make_staff_member(MANAGERS_GROUP, first_name="Дмитрий", last_name="Дмитриев")
        marketer = make_staff_member(MARKETING_GROUP, first_name="Мария", last_name="Маркетова")
        blocked_idle = make_staff_member(MANAGERS_GROUP, first_name="Егор", last_name="Простоев", is_active=False)
        f = make_staff_member(MANAGERS_GROUP, first_name="Фёдор", last_name="Блоков", is_active=False)
        master_in_period(make_client(a), "500.00")
        master_in_period(make_client(f), "200.00")

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"] == [
            (label(a), "1", "500,00\xa0₽", "0"),
            (label(f, blocked=True), "1", "200,00\xa0₽", "0"),
            (label(d), "0", "0,00\xa0₽", "0"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
            ("Итого", "2", "700,00\xa0₽", "0"),
        ]
        labels = {row[0] for row in page.rows["summary-orders-by-manager"]}
        assert not any(marketer.email in text or blocked_idle.email in text for text in labels)

    @pytest.mark.parametrize("status", ["confirmed", "processing", "shipped", "delivered"])
    def test_processed_orders_are_counted(self, supervisor_client, supervisor, status):
        # Учитываются все статусы, кроме «Отменен» и «Возвращен», а не только «Ожидает обработки».
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        master_in_period(make_client(a, tax_id=region_tax_id("23")), "400.00", status=status)
        master_in_period(make_client(a, tax_id=region_tax_id("23")), "100.00")

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"] == [
            (label(a), "2", "500,00\xa0₽", "0"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
            ("Итого", "2", "500,00\xa0₽", "0"),
        ]
        assert page.rows["summary-orders-by-region"] == [
            ("23 — Краснодарский край", "2", "500,00\xa0₽", "0"),
            ("Итого", "2", "500,00\xa0₽", "0"),
        ]

    def test_revenue_keeps_kopecks(self, supervisor_client, supervisor):
        # Копейки проходят агрегацию без округления: сумма и «Итого» обеих таблиц — до копейки.
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        b = make_staff_member(MANAGERS_GROUP, first_name="Борис", last_name="Второй")
        master_in_period(make_client(a, tax_id=region_tax_id("23")), "100.25")
        master_in_period(make_client(a, tax_id=region_tax_id("23")), "200.50")
        master_in_period(make_client(b, tax_id=region_tax_id("77")), "1.05")

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"] == [
            (label(a), "2", "300,75\xa0₽", "0"),
            (label(b), "1", "1,05\xa0₽", "0"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
            ("Итого", "3", "301,80\xa0₽", "0"),
        ]
        assert page.rows["summary-orders-by-region"] == [
            ("23 — Краснодарский край", "2", "300,75\xa0₽", "0"),
            ("77 — г. Москва", "1", "1,05\xa0₽", "0"),
            ("Итого", "3", "301,80\xa0₽", "0"),
        ]

    def test_groups_with_only_cancelled_orders(self, supervisor_client, supervisor):
        # У группы только отменённые заказы: сумма выручки пуста — строка с нулём, а не 500.
        a = make_staff_member(MANAGERS_GROUP, first_name="Анна", last_name="Первая")
        c = make_staff_member(MANAGERS_GROUP, first_name="Вера", last_name="Отменова")
        master_in_period(make_client(a, tax_id=region_tax_id("23")), "500.00")
        master_in_period(make_client(c, tax_id=region_tax_id("77")), "700.00", status="cancelled")
        master_in_period(make_client(c, tax_id=region_tax_id("77")), "300.00", status="refunded")

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-manager"] == [
            (label(a), "1", "500,00\xa0₽", "0"),
            (label(c), "0", "0,00\xa0₽", "2"),
            (label(supervisor), "0", "0,00\xa0₽", "0"),
            ("Итого", "1", "500,00\xa0₽", "2"),
        ]
        assert page.rows["summary-orders-by-region"] == [
            ("23 — Краснодарский край", "1", "500,00\xa0₽", "0"),
            ("77 — г. Москва", "0", "0,00\xa0₽", "2"),
            ("Итого", "1", "500,00\xa0₽", "2"),
        ]


# --------------------------------------------------------------------------
# AC5 — заказы и выручка по регионам
# --------------------------------------------------------------------------


class TestOrdersByRegion:
    def test_rows_and_totals(self, supervisor_client, manager):
        master_in_period(make_client(manager, tax_id=region_tax_id("23")), "600.00")
        master_in_period(make_client(manager, tax_id=region_tax_id("77")), "500.00")
        master_in_period(make_client(manager, tax_id=region_tax_id("96")), "400.00")
        master_in_period(make_client(manager, country="Беларусь", tax_id=region_tax_id("23")), "300.00")
        master_in_period(make_client(None, tax_id=""), "200.00")
        master_in_period(make_client(manager, tax_id=" " + region_tax_id("23")[:11]), "100.00")
        master_in_period(make_client(manager, tax_id=region_tax_id("23")), "900.00", status="cancelled")
        master_in_period(None, "50.00")
        # Вне периода: не меняют строку 77 и не дают строки 50.
        for tax_id in (region_tax_id("77"), region_tax_id("50")):
            set_order_created(
                make_master(make_client(manager, tax_id=tax_id), total_amount=Decimal("9999.00"), subs=0),
                datetime(2026, 9, 15, 12, 0, tzinfo=MOSCOW),
            )

        page = tables(supervisor_client.get(SUMMARY_URL, PERIOD))

        assert page.rows["summary-orders-by-region"] == [
            ("23 — Краснодарский край", "1", "600,00\xa0₽", "1"),
            ("77 — г. Москва", "1", "500,00\xa0₽", "0"),
            ("96", "1", "400,00\xa0₽", "0"),
            ("Беларусь", "1", "300,00\xa0₽", "0"),
            ("Регион не определён", "2", "300,00\xa0₽", "0"),
            ("Без клиента", "1", "50,00\xa0₽", "0"),
            ("Итого", "7", "2\xa0150,00\xa0₽", "1"),
        ]
        assert page.rows["summary-orders-by-manager"][-1] == ("Итого", "7", "2\xa0150,00\xa0₽", "1")


# --------------------------------------------------------------------------
# AC6 — клиенты
# --------------------------------------------------------------------------


class TestClients:
    def test_registrations_in_period(self, supervisor_client, manager):
        registered = [
            make_applicant(manager),
            make_client(manager),
            make_client(manager, verification_status="unverified", is_verified=False, is_active=False),
            make_client(None, role="retail", tax_id="", company_name=""),
        ]
        others = [make_client(manager), make_1c_record(region_tax_id("23")), make_staff_member(MANAGERS_GROUP)]
        for user in registered + others[1:]:
            set_created_at(user, IN_PERIOD)
        set_created_at(others[0], datetime(2026, 9, 1, 12, 0, tzinfo=MOSCOW))
        # Границы периода включительно: первая минута первого дня и последняя минута последнего.
        set_created_at(make_client(manager), datetime(2026, 10, 10, 0, 0, tzinfo=MOSCOW))
        set_created_at(make_client(manager), datetime(2026, 10, 12, 23, 59, tzinfo=MOSCOW))
        # Начало дня после периода — уже не в нём.
        set_created_at(make_client(manager), datetime(2026, 10, 13, 0, 0, tzinfo=MOSCOW))

        html = supervisor_client.get(SUMMARY_URL, PERIOD).content.decode()

        assert "Новые регистрации за период: 6" in html

    def test_verified_without_orders(self, supervisor_client, manager):
        idle = [make_client(manager), make_client(None)]
        # Регистрация давно, вне периода по умолчанию: дата регистрации числу не важна.
        set_created_at(idle[0], datetime(2025, 1, 15, 12, 0, tzinfo=MOSCOW))
        with_order = make_client(manager)
        # Заказ давно, вне периода по умолчанию: «без заказов» — за всё время.
        # Переносится и мастер, и его субзаказы.
        make_master(with_order)
        Order.objects.filter(user=with_order).update(created_at=datetime(2025, 1, 15, 12, 0, tzinfo=MOSCOW))
        only_cancelled = make_client(manager)
        make_master(only_cancelled, status="cancelled")
        make_client(manager, is_active=False)
        # Активные, без заказов, но не верифицированные: число их не включает.
        make_client(manager, verification_status="pending", is_verified=False)
        make_client(manager, verification_status="unverified", is_verified=False)
        make_applicant(manager)
        make_1c_record(region_tax_id("23"), verification_status="verified")
        make_staff_member(MANAGERS_GROUP, verification_status="verified")
        url = "/manager/users/user/?verification_status__exact=verified&is_active__exact=1&has_orders=no"

        page = tables(supervisor_client.get(SUMMARY_URL))

        assert page.rows["summary-clients"][1] == ("Верифицированы, но без заказов: 2 (за всё время)",)
        assert page.links["summary-clients"][1] == [url]
        assert listed_pks(supervisor_client.get(url)) == {user.pk for user in idle}

    def test_supervisor_orders_filter(self, supervisor_client, manager):
        make_client(manager)
        with_order = make_client(manager)
        make_master(with_order)
        only_cancelled = make_client(None)
        make_master(only_cancelled, status="cancelled", subs=0)

        response = supervisor_client.get(CLIENTS_URL)

        spec = next(s for s in response.context["cl"].filter_specs if isinstance(s, ClientOrdersFilter))
        assert spec.title == "Заказы"
        assert spec.lookup_choices == [("yes", "Есть"), ("no", "Нет")]
        with_orders = supervisor_client.get(CLIENTS_URL, {"has_orders": "yes"})
        # Список, а не множество: JOIN по заказам (мастер + два субзаказа) дал бы дубли строк клиента.
        listed = [user.pk for user in with_orders.context["cl"].result_list]
        assert with_orders.context["cl"].result_count == 2
        assert sorted(listed) == sorted([with_order.pk, only_cancelled.pk])

    def test_supervisor_orders_filter_rejects_unknown_value(self, supervisor_client):
        response = supervisor_client.get(CLIENTS_URL, {"has_orders": "maybe"})

        assert response.status_code == 302
        assert response["Location"].endswith("?e=1")

    def test_manager_has_no_orders_filter(self, manager, other_manager):
        own = make_client(manager)
        foreign = make_client(other_manager)
        browser = logged_in(manager)

        response = browser.get(CLIENTS_URL)
        filters = [
            getattr(spec, "field_path", None) or spec.parameter_name for spec in response.context["cl"].filter_specs
        ]
        assert filters == ["role", "verification_status", "has_1c_candidate", "is_active", "portal_account"]
        assert listed_pks(response) == {own.pk}

        forged = browser.get(CLIENTS_URL, {"has_orders": "no"})
        assert forged.status_code == 302
        assert forged["Location"].endswith("?e=1")
        assert foreign.email not in browser.get(forged["Location"]).content.decode()


# --------------------------------------------------------------------------
# AC7 — ссылки и главная
# --------------------------------------------------------------------------


SECTION_LINK = re.compile(r'<a href="([^"]+)"(?: aria-current="page")?>([^<]+)</a>')


class TestLinks:
    def test_index_is_summary_with_sections_in_sidebar(self, supervisor_client):
        html = supervisor_client.get("/supervisor/").content.decode()
        block = html[html.index('id="supervisor-sections"') : html.index("</table>", html.index("supervisor-sections"))]

        assert 'id="summary-period"' in html
        assert SECTION_LINK.findall(block) == [
            ("/supervisor/", "Сводка"),
            ("/supervisor/journal/", "Журнал действий"),
            ("/manager/", "Клиенты и заказы"),
            ("/marketing/", "Маркетинг"),
        ]

    def test_summary_links_stay_in_sections(self, supervisor_client):
        tricky = make_staff_member(MANAGERS_GROUP, first_name="<b>X</b>", last_name="Тегов")
        make_applicant(tricky)
        master_in_period(make_client(tricky, tax_id=region_tax_id("23")), "100.00")
        make_client(tricky)

        response = supervisor_client.get(SUMMARY_URL, PERIOD)
        html = response.content.decode()
        page = tables(response)

        assert 'href="/admin/' not in html
        assert re.search(r'<div class="breadcrumbs">\s*<a href="/supervisor/">', html)
        assert 'href="/supervisor/password_change/"' in html
        assert 'action="/supervisor/logout/"' in html
        row_links = [
            href for block in ("summary-pending", "summary-clients") for row in page.links[block] for href in row
        ]
        assert row_links
        assert all(href.startswith("/manager/users/user/?") for href in row_links)
        assert "<b>X</b>" not in html
        assert "&lt;b&gt;X&lt;/b&gt; Тегов" in html


HOME_LINK = re.compile(r'<a id="supervisor-home-link" href="([^"]*)">')
PERIOD_QUERY = "?date_from=2026-10-10&date_to=2026-10-12"


class TestReturnWithPeriod:
    """Ссылка «← Раздел руководителя» в /manager/ возвращает в сводку за тот же период."""

    def home_href(self, client) -> str:
        match = HOME_LINK.search(client.get("/manager/users/user/").content.decode())
        assert match
        return unescape(match.group(1))

    def test_period_is_remembered(self, supervisor_client):
        assert self.home_href(supervisor_client) == "/supervisor/"

        supervisor_client.get(SUMMARY_URL, PERIOD)

        assert self.home_href(supervisor_client) == "/supervisor/" + PERIOD_QUERY
        # Ссылка ведёт в сводку, и та показывает тот же период.
        page = supervisor_client.get("/supervisor/" + PERIOD_QUERY)
        assert page.context["period"].label == "10.10.2026 — 12.10.2026"

    def test_default_period_resets_it(self, supervisor_client):
        supervisor_client.get("/supervisor/", PERIOD)
        supervisor_client.get("/supervisor/")

        assert self.home_href(supervisor_client) == "/supervisor/"

    def test_invalid_period_keeps_it(self, supervisor_client):
        supervisor_client.get(SUMMARY_URL, PERIOD)
        supervisor_client.get(SUMMARY_URL, {"date_from": "2026-10-12", "date_to": "2026-10-10"})
        supervisor_client.get(SUMMARY_URL, {"date_from": "2026-10-12"})

        assert self.home_href(supervisor_client) == "/supervisor/" + PERIOD_QUERY

    def test_session_is_written_only_on_change(self, supervisor_client):
        supervisor_client.get(SUMMARY_URL, PERIOD)

        first, _ = count_queries(supervisor_client, SUMMARY_URL + PERIOD_QUERY)
        again, _ = count_queries(supervisor_client, SUMMARY_URL + PERIOD_QUERY)
        other, _ = count_queries(supervisor_client, SUMMARY_URL + "?date_from=2026-10-01&date_to=2026-10-02")

        assert first == again
        assert other > again

    def test_marketing_uses_remembered_period_too(self, supervisor_client):
        supervisor_client.get(SUMMARY_URL, PERIOD)

        html = supervisor_client.get("/marketing/").content.decode()

        assert f'<a id="supervisor-home-link" href="/supervisor/{PERIOD_QUERY.replace("&", "&amp;")}">' in html


# --------------------------------------------------------------------------
# AC8 — число запросов
# --------------------------------------------------------------------------


REGION_CODES = ["01", "02", "16", "23", "24", "25", "34", "47", "50", "52", "54", "61", "77"]
COUNTRIES = ["Беларусь", "Казахстан"]


class TestQueryCount:
    def test_index_costs_as_much_as_summary(self, supervisor_client):
        # Главная и /supervisor/summary/ — одна сводка: меню и шапка не добавляют запросов.
        supervisor_client.get(
            SUMMARY_URL
        )  # прогрев кэшей процесса (ContentType, права): не зависеть от порядка замеров
        index, _ = count_queries(supervisor_client, "/supervisor/")
        summary, _ = count_queries(supervisor_client, SUMMARY_URL)
        assert index == summary

    def test_summary(self, supervisor_client, django_assert_num_queries):
        product = ProductFactory()

        def add(managers: int, clients: int, orders: int, regions: list[dict[str, str]]) -> None:
            team = [make_staff_member(MANAGERS_GROUP) for _ in range(managers)]
            # Последний менеджер без клиентов и заказов — строка с нулями.
            owners = team[:-1] if managers > 1 else team
            people = []
            for index in range(clients):
                fields = regions[index % len(regions)]
                if index % 3 == 0:
                    people.append(make_applicant(owners[index % len(owners)], **fields))
                else:
                    people.append(make_client(owners[index % len(owners)], **fields))
            for index in range(orders):
                make_master(people[index % len(people)], product=product, total_amount=Decimal("100.00"))

        add(2, 5, 6, [{"tax_id": region_tax_id("23")}, {"tax_id": region_tax_id("77")}])
        baseline, first = count_queries(supervisor_client, SUMMARY_URL)
        assert first.context["orders_by_manager"]["total"].orders == 6

        regions = [{"tax_id": region_tax_id(code)} for code in REGION_CODES] + [
            {"country": country} for country in COUNTRIES
        ]
        add(28, 60, 90, regions)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(SUMMARY_URL)
        assert response.context["orders_by_manager"]["total"].orders == 96
        assert len(response.context["orders_by_region"]["rows"]) == 15
        assert len(response.context["orders_by_manager"]["rows"]) == 31

    def test_clients_without_orders(self, supervisor_client, manager, django_assert_num_queries):
        def add(count: int) -> None:
            for _ in range(count):
                make_client(manager)

        url = f"{CLIENTS_URL}?has_orders=no"
        add(5)
        baseline, _ = count_queries(supervisor_client, url)
        add(45)
        with django_assert_num_queries(baseline):
            response = supervisor_client.get(url)
        assert response.context["cl"].result_count == 50

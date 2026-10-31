"""
Unit-тесты сводки руководителя `/supervisor/summary/` (стори 42.8).

Паритет выражения региона `region_bucket()` с функцией `region_key()`,
быстрые ссылки периода, форма периода, формат денег, срок ожидания заявки
и маршрут страницы.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from django.urls import resolve, reverse

from apps.orders.manager_admin import waiting_age
from apps.orders.models import Order
from apps.orders.supervisor_summary import SummaryPeriodForm, format_money, period_presets, region_bucket
from apps.users.models import User
from apps.users.services.responsible_manager import region_key
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit]

MOSCOW = ZoneInfo("Europe/Moscow")


@pytest.fixture(autouse=True)
def no_order_emails():
    """Письма о новом заказе (`orders/signals.py`) — без брокера Celery."""
    with (
        patch("apps.orders.tasks.send_order_confirmation_to_customer"),
        patch("apps.orders.tasks.send_order_notification_email"),
    ):
        yield


def make_order(user: User | None) -> Order:
    return Order.objects.create(
        user=user,
        is_master=True,
        total_amount=Decimal("100.00"),
        delivery_address="Адрес",
        delivery_method="courier",
        payment_method="card",
    )


COUNTRIES = ["Россия", "", "Беларусь", "Казахстан"]
TAX_IDS = ["2300000000", "7700000000", "9600000000", " 2300000000", "2a00000000", "2", ""]


@pytest.mark.django_db
def test_region_bucket_matches_region_key():
    expected: dict[int, str] = {}
    for country in COUNTRIES:
        for tax_id in TAX_IDS:
            client = User.objects.create_user(
                email=f"region_{get_unique_suffix()}@example.com",
                password="StrongPassword123!",
                role="wholesale_level1",
                country=country,
                tax_id=tax_id,
            )
            key = region_key(country, tax_id)
            expected[make_order(client).pk] = f"{key[0]}:{key[1]}" if key else "unknown:"
    expected[make_order(None).pk] = "no_client:"

    actual = dict(Order.objects.annotate(bucket=region_bucket()).values_list("pk", "bucket"))

    assert actual == expected
    # Набор покрывает все ветки выражения.
    assert set(expected.values()) >= {
        "country:Беларусь",
        "country:Казахстан",
        "inn_region:23",
        "inn_region:77",
        "inn_region:96",
        "unknown:",
        "no_client:",
    }


def presets(today: date) -> dict[str, tuple[str, str]]:
    return {name: (f"{p.date_from:%d.%m.%Y}", f"{p.date_to:%d.%m.%Y}") for name, p in period_presets(today)}


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        pytest.param(
            date(2026, 10, 17),
            {
                "Сегодня": ("17.10.2026", "17.10.2026"),
                "7 дней": ("11.10.2026", "17.10.2026"),
                "30 дней": ("18.09.2026", "17.10.2026"),
                "Этот месяц": ("01.10.2026", "17.10.2026"),
                "Прошлый месяц": ("01.09.2026", "30.09.2026"),
            },
            id="mid-month",
        ),
        pytest.param(
            date(2026, 10, 1),
            {
                "Сегодня": ("01.10.2026", "01.10.2026"),
                "7 дней": ("25.09.2026", "01.10.2026"),
                "30 дней": ("02.09.2026", "01.10.2026"),
                "Этот месяц": ("01.10.2026", "01.10.2026"),
                "Прошлый месяц": ("01.09.2026", "30.09.2026"),
            },
            id="first-day",
        ),
        pytest.param(
            date(2026, 1, 15),
            {
                "Сегодня": ("15.01.2026", "15.01.2026"),
                "7 дней": ("09.01.2026", "15.01.2026"),
                "30 дней": ("17.12.2025", "15.01.2026"),
                "Этот месяц": ("01.01.2026", "15.01.2026"),
                "Прошлый месяц": ("01.12.2025", "31.12.2025"),
            },
            id="january",
        ),
    ],
)
def test_period_presets(today, expected):
    assert list(presets(today)) == ["Сегодня", "7 дней", "30 дней", "Этот месяц", "Прошлый месяц"]
    assert presets(today) == expected


class TestPeriodForm:
    def test_empty_form_requires_both_dates(self):
        form = SummaryPeriodForm({})

        assert not form.is_valid()
        assert form.errors == {"date_from": ["Обязательное поле."], "date_to": ["Обязательное поле."]}

    def test_full_form(self):
        form = SummaryPeriodForm({"date_from": "2026-10-10", "date_to": "2026-10-12"})

        assert form.is_valid()
        assert form.cleaned_data == {"date_from": date(2026, 10, 10), "date_to": date(2026, 10, 12)}

    def test_single_day(self):
        assert SummaryPeriodForm({"date_from": "2026-10-12", "date_to": "2026-10-12"}).is_valid()

    def test_reversed_period(self):
        form = SummaryPeriodForm({"date_from": "2026-10-12", "date_to": "2026-10-10"})

        assert not form.is_valid()
        assert form.non_field_errors() == ["Начало периода позже его конца."]

    def test_one_date(self):
        form = SummaryPeriodForm({"date_from": "2026-10-12"})

        assert not form.is_valid()
        assert form.errors == {"date_to": ["Обязательное поле."]}

    def test_last_possible_date(self):
        # Конец периода считается началом следующего дня, после 31.12.9999 его нет.
        form = SummaryPeriodForm({"date_from": "9999-12-31", "date_to": "9999-12-31"})

        assert not form.is_valid()
        assert form.errors == {"date_to": ["Конец периода вне допустимого диапазона."]}
        assert SummaryPeriodForm({"date_from": "2026-10-10", "date_to": "9999-12-30"}).is_valid()


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("1234567.8"), "1\xa0234\xa0567,80\xa0₽"),
        (Decimal("0"), "0,00\xa0₽"),
        (None, "0,00\xa0₽"),
        (Decimal("999.999"), "1\xa0000,00\xa0₽"),
        (Decimal("50"), "50,00\xa0₽"),
    ],
)
def test_format_money(value, expected):
    assert format_money(value) == expected


@pytest.mark.parametrize(
    ("oldest", "expected"),
    [
        pytest.param(datetime(2026, 10, 17, 0, 5, tzinfo=MOSCOW), "сегодня", id="today"),
        pytest.param(datetime(2026, 10, 16, 23, 50, tzinfo=MOSCOW), "1 день", id="yesterday-before-midnight"),
        # 21:30 UTC 16.10 — это уже 00:30 17.10 по Москве.
        pytest.param(datetime(2026, 10, 16, 21, 30, tzinfo=ZoneInfo("UTC")), "сегодня", id="utc-evening"),
        pytest.param(datetime(2026, 10, 12, 12, 0, tzinfo=MOSCOW), "5 дней", id="five-days"),
    ],
)
def test_waiting_age(oldest, expected):
    with patch("django.utils.timezone.now", return_value=datetime(2026, 10, 17, 0, 10, tzinfo=MOSCOW)):
        assert waiting_age(oldest) == expected


def test_summary_route():
    assert reverse("supervisor:summary") == "/supervisor/summary/"
    assert resolve("/supervisor/summary/").url_name == "summary"

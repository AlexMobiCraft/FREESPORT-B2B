"""
Сводка руководителя `/supervisor/summary/` (стори 42.8).

Что считается:
- заявки на верификацию по ответственным менеджерам — текущая очередь,
  от периода не зависит;
- заказы и выручка за период по менеджерам и по регионам — только
  мастер-заказы, поэтому субзаказы второй раз не складываются. Выручка —
  `total_amount` мастер-заказа без отменённых и возвращённых, они считаются
  отдельной колонкой;
- новые регистрации за период и верифицированные клиенты без заказов.

Выборки — только `scope_clients` и `scope_orders` раздела менеджера: для
руководителя это весь отдел, и каждое число совпадает со списком `/manager/`,
на который ведёт его ссылка. Заказы и выручка относятся к текущему
ответственному менеджеру и текущему региону клиента: истории назначений нет.

Всё считается агрегирующими запросами в БД, без кэша: число запросов
страницы не зависит от числа строк, а числа совпадают со списками сразу
после действия менеджера.

Модуль ничего не регистрирует и импортируется только из
`SupervisorAdminSite.summary_view`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Iterable

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import BooleanField, Case, CharField, Count, ExpressionWrapper, Min, Q, Sum, Value, When
from django.db.models.functions import Concat, Substr
from django.http import HttpRequest
from django.urls import reverse
from django.utils import timezone

from apps.common.models import ManagerRoutingRule
from apps.common.regions import REGION_NAMES
from apps.orders.manager_admin import scope_orders, waiting_age
from apps.orders.models import Order
from apps.users.manager_admin import client_has_orders, scope_clients
from apps.users.models import User
from apps.users.services.responsible_manager import RUSSIA_COUNTRY_VALUES
from apps.users.staff_roles import manager_label, responsible_manager_candidate_q

# Заказы в этих статусах не входят в «Заказов» и «Выручку», они — в «Отменено».
CANCELLED_STATUSES = ("cancelled", "refunded")

UNASSIGNED_LABEL = "Без ответственного"
NO_CLIENT_LABEL = "Без клиента"
UNKNOWN_REGION_LABEL = "Регион не определён"
BLOCKED_SUFFIX = " — заблокирован"

# Служебные ключи региона: «вид:значение». Виды страны и региона ИНН — те же,
# что у правил регионов и `region_key`.
BUCKET_NO_CLIENT = "no_client"
BUCKET_UNKNOWN = "unknown"
BUCKET_COUNTRY = ManagerRoutingRule.MATCH_COUNTRY
BUCKET_INN_REGION = ManagerRoutingRule.MATCH_INN_REGION


class SummaryPeriodForm(forms.Form):
    """Период сводки: обе даты включительно, в часовом поясе проекта."""

    date_from = forms.DateField(
        label="Начало периода",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        label="Конец периода",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_to == date.max:
            # Конец периода — начало следующего дня (`Period.end`), после date.max его нет.
            self.add_error("date_to", "Конец периода вне допустимого диапазона.")
        elif date_from and date_to and date_from > date_to:
            raise ValidationError("Начало периода позже его конца.")
        return cleaned


@dataclass(frozen=True)
class Period:
    date_from: date
    date_to: date

    @property
    def start(self) -> datetime:
        """Начало первого дня периода."""
        return timezone.make_aware(datetime.combine(self.date_from, time.min))

    @property
    def end(self) -> datetime:
        """Начало дня после периода: граница не входит — полуинтервал `[start, end)`."""
        return timezone.make_aware(datetime.combine(self.date_to + timedelta(days=1), time.min))

    @property
    def label(self) -> str:
        return f"{self.date_from:%d.%m.%Y} — {self.date_to:%d.%m.%Y}"

    @property
    def query(self) -> str:
        return f"?date_from={self.date_from.isoformat()}&date_to={self.date_to.isoformat()}"


def this_month(today: date) -> Period:
    return Period(today.replace(day=1), today)


def period_presets(today: date) -> list[tuple[str, Period]]:
    """Быстрые ссылки периода: подпись и период."""
    last_month_end = today.replace(day=1) - timedelta(days=1)
    return [
        ("Сегодня", Period(today, today)),
        ("7 дней", Period(today - timedelta(days=6), today)),
        ("30 дней", Period(today - timedelta(days=29), today)),
        ("Этот месяц", this_month(today)),
        ("Прошлый месяц", Period(last_month_end.replace(day=1), last_month_end)),
    ]


def resolve_period(request: HttpRequest) -> tuple[SummaryPeriodForm, Period]:
    """
    Форма и период из запроса.

    Без параметров — «Этот месяц». Неверная форма показывает свои ошибки,
    а данные считаются за период по умолчанию.
    """
    default = this_month(timezone.localdate())
    if not {"date_from", "date_to"} & set(request.GET):
        return SummaryPeriodForm(initial={"date_from": default.date_from, "date_to": default.date_to}), default
    form = SummaryPeriodForm(request.GET)
    if form.is_valid():
        return form, Period(form.cleaned_data["date_from"], form.cleaned_data["date_to"])
    return form, default


def format_money(value: Decimal | None) -> str:
    """Сумма в рублях: `1 234 567,80 ₽` с неразрывными пробелами, без локали."""
    amount = Decimal(value or 0)
    return f"{amount:,.2f}".replace(",", "\xa0").replace(".", ",") + "\xa0₽"


# ---------------------------------------------------------------------------
# Сгруппированные значения из БД
# ---------------------------------------------------------------------------


def pending_applications(request: HttpRequest) -> list[dict[str, Any]]:
    """
    Заявки на верификацию по ответственному: `responsible_manager`, `count`, `oldest`.

    Выборка — как у счётчика очереди менеджера: список клиентов по умолчанию
    скрывает записи 1С без аккаунта, поэтому они не считаются.
    """
    return list(
        scope_clients(request, User.objects.all())
        .exclude(role=User.ROLE_UNREGISTERED)
        .filter(verification_status="pending")
        .values("responsible_manager")
        .annotate(count=Count("pk"), oldest=Min("created_at"))
        .order_by()
    )


def _period_orders(request: HttpRequest, period: Period) -> Any:
    return scope_orders(request, Order.objects.all()).filter(created_at__gte=period.start, created_at__lt=period.end)


def _sales() -> dict[str, Any]:
    cancelled = Q(status__in=CANCELLED_STATUSES)
    return {
        "orders": Count("pk", filter=~cancelled),
        "revenue": Sum("total_amount", filter=~cancelled),
        "cancelled": Count("pk", filter=cancelled),
    }


def orders_by_manager(request: HttpRequest, period: Period) -> list[dict[str, Any]]:
    """
    Заказы периода по текущему ответственному клиента: `no_client`,
    `user__responsible_manager`, `orders`, `revenue`, `cancelled`.

    `no_client` отделяет заказы без клиента от заказов клиента без менеджера:
    у обоих ответственный пуст.
    """
    return list(
        _period_orders(request, period)
        .annotate(no_client=ExpressionWrapper(Q(user__isnull=True), output_field=BooleanField()))
        .values("no_client", "user__responsible_manager")
        .annotate(**_sales())
        .order_by()
    )


def region_bucket() -> Case:
    """
    Регион заказа — регион его клиента сейчас, правилом `region_key`, выражением SQL.

    Значение — служебный ключ «вид:значение». Ветка «без клиента» первая:
    отрицание по стране для заказа без клиента (LEFT JOIN, страна NULL)
    сработало бы и дало страну с пустым названием.
    """
    return Case(
        When(user__isnull=True, then=Value(f"{BUCKET_NO_CLIENT}:")),
        When(
            ~Q(user__country__in=RUSSIA_COUNTRY_VALUES),
            then=Concat(Value(f"{BUCKET_COUNTRY}:"), "user__country", output_field=CharField()),
        ),
        When(
            user__tax_id__regex=r"^[0-9]{2}",
            then=Concat(Value(f"{BUCKET_INN_REGION}:"), Substr("user__tax_id", 1, 2), output_field=CharField()),
        ),
        default=Value(f"{BUCKET_UNKNOWN}:"),
        output_field=CharField(),
    )


def split_bucket(bucket: str) -> tuple[str, str]:
    kind, _, value = bucket.partition(":")
    return kind, value


def region_label(bucket: str) -> str:
    kind, value = split_bucket(bucket)
    if kind == BUCKET_NO_CLIENT:
        return NO_CLIENT_LABEL
    if kind == BUCKET_COUNTRY:
        return value
    if kind == BUCKET_INN_REGION:
        name = REGION_NAMES.get(value)
        return f"{value} — {name}" if name else value
    return UNKNOWN_REGION_LABEL


def client_counts(request: HttpRequest, period: Period) -> dict[str, int]:
    """
    `registered` — регистрации портала за период; `verified_without_orders` —
    активные верифицированные клиенты без единого заказа за всё время.
    """
    return (
        scope_clients(request, User.objects.all())
        .exclude(role=User.ROLE_UNREGISTERED)
        .aggregate(
            registered=Count("pk", filter=Q(created_at__gte=period.start, created_at__lt=period.end)),
            verified_without_orders=Count(
                "pk", filter=Q(verification_status="verified", is_active=True) & Q(~client_has_orders())
            ),
        )
    )


# ---------------------------------------------------------------------------
# Таблицы страницы
# ---------------------------------------------------------------------------


@dataclass
class PendingRow:
    label: str
    count: int
    age: str
    url: str
    unassigned: bool = False


@dataclass
class SalesRow:
    label: str
    orders: int = 0
    revenue: Decimal = Decimal("0")
    cancelled: int = 0
    special: bool = False

    @property
    def revenue_text(self) -> str:
        return format_money(self.revenue)


def sales_total(rows: Iterable[SalesRow]) -> SalesRow:
    total = SalesRow("Итого")
    for row in rows:
        total.orders += row.orders
        total.revenue += row.revenue
        total.cancelled += row.cancelled
    return total


def _sales_row(label: str, group: dict[str, Any], special: bool = False) -> SalesRow:
    return SalesRow(
        label,
        orders=group["orders"],
        revenue=group["revenue"] or Decimal("0"),
        cancelled=group["cancelled"],
        special=special,
    )


def load_managers(ids: Iterable[int | None]) -> dict[int, User]:
    """
    Учётные записи менеджеров страницы одним запросом: из таблиц и все действующие.

    `is_candidate` — может отвечать за клиентов сейчас: такие менеджеры получают
    строку в таблице заказов и без заказов за период.
    """
    managers = User.objects.filter(
        Q(pk__in=[pk for pk in ids if pk is not None]) | responsible_manager_candidate_q()
    ).annotate(is_candidate=ExpressionWrapper(responsible_manager_candidate_q(), output_field=BooleanField()))
    return {manager.pk: manager for manager in managers}


def manager_row_label(manager: User) -> str:
    label = manager_label(manager)
    return label if manager.is_active else label + BLOCKED_SUFFIX


def pending_table(groups: list[dict[str, Any]], managers: dict[int, User]) -> dict[str, Any]:
    clients_url = reverse("manager:users_user_changelist") + "?verification_status__exact=pending&responsible="
    rows: list[tuple[datetime, PendingRow]] = []
    unassigned = PendingRow(UNASSIGNED_LABEL, 0, "—", clients_url + "none", unassigned=True)
    for group in groups:
        manager_id = group["responsible_manager"]
        if manager_id is None:
            unassigned.count = group["count"]
            unassigned.age = waiting_age(group["oldest"])
            continue
        row = PendingRow(
            manager_row_label(managers[manager_id]),
            group["count"],
            waiting_age(group["oldest"]),
            clients_url + str(manager_id),
        )
        rows.append((group["oldest"], row))
    # Дольше всех ждёт — выше.
    ordered = [row for _, row in sorted(rows, key=lambda item: (item[0], item[1].label))]
    ordered.append(unassigned)
    return {"rows": ordered, "total": sum(row.count for row in ordered)}


def manager_sales_table(groups: list[dict[str, Any]], managers: dict[int, User]) -> dict[str, Any]:
    # is_candidate — аннотация запроса load_managers, у модели такого поля нет.
    by_manager: dict[int, SalesRow] = {
        pk: SalesRow(manager_row_label(manager))
        for pk, manager in managers.items()
        if manager.is_candidate  # type: ignore[attr-defined]
    }
    unassigned: SalesRow | None = None
    no_client: SalesRow | None = None
    for group in groups:
        manager_id = group["user__responsible_manager"]
        if group["no_client"]:
            no_client = _sales_row(NO_CLIENT_LABEL, group, special=True)
        elif manager_id is None:
            unassigned = _sales_row(UNASSIGNED_LABEL, group, special=True)
        else:
            by_manager[manager_id] = _sales_row(manager_row_label(managers[manager_id]), group)
    rows = sorted(by_manager.values(), key=lambda row: (-row.revenue, row.label))
    rows += [row for row in (unassigned, no_client) if row is not None]
    return {"rows": rows, "total": sales_total(rows)}


def orders_by_region(request: HttpRequest, period: Period) -> dict[str, Any]:
    groups = _period_orders(request, period).values(bucket=region_bucket()).annotate(**_sales()).order_by()
    rows = sorted(
        (_sales_row(region_label(group["bucket"]), group) for group in groups),
        key=lambda row: (-row.revenue, row.label),
    )
    return {"rows": rows, "total": sales_total(rows)}


def build_summary(request: HttpRequest) -> dict[str, Any]:
    """Контекст шаблона сводки."""
    period_form, period = resolve_period(request)
    pending_groups = pending_applications(request)
    manager_groups = orders_by_manager(request, period)
    managers = load_managers(
        [group["responsible_manager"] for group in pending_groups]
        + [group["user__responsible_manager"] for group in manager_groups]
    )
    counts = client_counts(request, period)
    presets = [
        {"name": name, "url": preset.query, "selected": preset == period}
        for name, preset in period_presets(timezone.localdate())
    ]
    return {
        "period_form": period_form,
        "period": period,
        "presets": presets,
        "pending": pending_table(pending_groups, managers),
        "orders_by_manager": manager_sales_table(manager_groups, managers),
        "orders_by_region": orders_by_region(request, period),
        "clients": {
            **counts,
            "verified_without_orders_url": reverse("manager:users_user_changelist")
            + "?verification_status__exact=verified&is_active__exact=1&has_orders=no",
        },
    }

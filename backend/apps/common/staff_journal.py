"""
Журнал действий сотрудников `/supervisor/journal/` (стори 42.9).

Что попадает в ленту:
- записи `AuditLog` с кодом из перечня `STAFF_ACTIONS` — действия сотрудников
  в разделах и в `/admin/`; служебные коды (`role_from_1c` импорта 1С и
  любые будущие) в ленту не попадают;
- только записи с автором, который не суперпользователь: действия владельца
  сайта лентой не показываются, записи без автора (импорт, синхронизация) —
  тоже. Текущие `is_staff`, `is_active` и группы автора не учитываются:
  заблокированный и бывший сотрудник остаются авторами своих записей — ради
  разбора таких случаев лента и нужна. Клиент этот критерий не проходит:
  коды перечня пишут только разделы сотрудников и `/admin/`.

Строка ленты — «дата — сотрудник — действие — объект» и подробности из
`details["changes"]` по белому списку ключей. Сам JSON, IP и User-Agent не
выводятся никогда.

Ссылка на объект ведёт туда, где руководитель его видит: клиент — в карточку
`/manager/`, если клиент виден в разделе (`scope_clients`); сотрудник — в
карточку `/supervisor/`; заказ — в карточку `/manager/` (`scope_orders`);
правило — в карточку `/supervisor/`, если оно не удалено. Остальное — подпись
без ссылки. Число запросов страницы постоянное: по одному запросу на вид
объекта, а не на строку.

Модуль ничего не регистрирует и импортируется только из
`SupervisorAdminSite.journal_view`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Iterable, cast
from urllib.parse import urlencode

from django import forms
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q, QuerySet
from django.http import HttpRequest, QueryDict
from django.urls import reverse
from django.utils import timezone

from apps.common.models import AuditLog, ManagerRoutingRule
from apps.common.staff_actions import STAFF_ACTIONS
from apps.common.supervisor_admin import LOGGED_RULE_FIELDS
from apps.orders.manager_admin import EDITABLE_FIELDS, scope_orders
from apps.orders.models import Order
from apps.orders.services.order_numbering import format_order_number
from apps.orders.supervisor_summary import BLOCKED_SUFFIX, Period, period_presets
from apps.users.manager_admin import scope_clients
from apps.users.models import User
from apps.users.staff_roles import manager_label

PER_PAGE = 100
# Период по умолчанию — последние 30 дней, ровно как быстрая ссылка «30 дней».
DEFAULT_DAYS = 30

EMPTY = "—"
FORMER_STAFF_SUFFIX = " — бывший сотрудник"

VERIFY_LINK_ONLY_LABEL = "Подтверждение роли при привязке к 1С"
RULE_OPERATION_LABELS = {
    "create": "Создание правила региона",
    "update": "Изменение правила региона",
    "delete": "Удаление правила региона",
}
ORDER_FIELD_LABELS = {"tracking_number": "трек-номер", "delivery_date": "дата доставки"}
RULE_FIELD_LABELS = {
    "match_type": "тип",
    "match_value": "значение",
    "is_active": "активно",
    "manager_id": "менеджер",
    "manager_email": "email менеджера",
}
ROLE_LABELS = dict(User.ROLE_CHOICES)
MATCH_TYPE_LABELS = dict(ManagerRoutingRule.MATCH_TYPE_CHOICES)


# ---------------------------------------------------------------------------
# Фильтр
# ---------------------------------------------------------------------------


def staff_choices() -> QuerySet[User]:
    """
    Сотрудники для выбора: все `is_staff`, включая заблокированных, плюс бывшие
    сотрудники с записями ленты. Суперпользователя нет — его действий нет в ленте.
    """
    authors = AuditLog.objects.filter(action__in=STAFF_ACTIONS).values("user")
    return (
        User.objects.filter(is_superuser=False)
        .filter(Q(is_staff=True) | Q(pk__in=authors))
        .order_by("last_name", "first_name", "email")
    )


def staff_choice_label(user: User) -> str:
    label = manager_label(user)
    if not user.is_staff:
        label += FORMER_STAFF_SUFFIX
    if not user.is_active:
        label += BLOCKED_SUFFIX
    return label


class JournalFilterForm(forms.Form):
    """Сотрудник и период ленты: обе даты включительно, в часовом поясе проекта, любая может быть пустой."""

    staff = forms.ModelChoiceField(
        queryset=User.objects.none(),
        required=False,
        label="Сотрудник",
        empty_label="Все сотрудники",
    )
    date_from = forms.DateField(
        required=False,
        label="Начало периода",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    date_to = forms.DateField(
        required=False,
        label="Конец периода",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        staff = self.fields["staff"]
        staff.queryset = staff_choices()  # type: ignore[attr-defined]
        staff.label_from_instance = staff_choice_label  # type: ignore[attr-defined]

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        date_from, date_to = cleaned.get("date_from"), cleaned.get("date_to")
        if date_to == date.max:
            # Конец периода — начало следующего дня, после date.max его нет.
            self.add_error("date_to", "Конец периода вне допустимого диапазона.")
        elif date_from and date_to and date_from > date_to:
            raise ValidationError("Начало периода позже его конца.")
        return cleaned


def default_period(today: date) -> Period:
    return Period(today - timedelta(days=DEFAULT_DAYS - 1), today)


def journal_filter(request: HttpRequest) -> JournalFilterForm:
    """
    Форма фильтра, связанная с данными запроса.

    Без ключей `date_from` и `date_to` в запросе — период по умолчанию: обе
    даты дописываются в данные формы. Ключи есть, но пустые
    (`?date_from=&date_to=`) — «Всё время», период не ограничен. Ссылки
    страниц строятся из этих же данных, поэтому период по умолчанию попадает
    в них явно и после полуночи не съезжает.
    """
    data = request.GET.copy()
    if "date_from" not in data and "date_to" not in data:
        period = default_period(timezone.localdate())
        data["date_from"] = period.date_from.isoformat()
        data["date_to"] = period.date_to.isoformat()
    return JournalFilterForm(data)


def _day_start(day: date) -> datetime:
    return timezone.make_aware(datetime.combine(day, time.min))


def journal_records(form: JournalFilterForm) -> QuerySet[AuditLog]:
    """Записи ленты по фильтру, новые сверху. Неверный фильтр — ни одной записи."""
    if not form.is_valid():
        return AuditLog.objects.none()
    records = AuditLog.objects.filter(action__in=STAFF_ACTIONS, user__isnull=False, user__is_superuser=False)
    staff = form.cleaned_data.get("staff")
    date_from = form.cleaned_data.get("date_from")
    date_to = form.cleaned_data.get("date_to")
    if staff is not None:
        records = records.filter(user=staff)
    if date_from:
        records = records.filter(created_at__gte=_day_start(date_from))
    if date_to:
        # Граница — начало следующего дня: полуинтервал, как у `Period` сводки.
        records = records.filter(created_at__lt=_day_start(date_to + timedelta(days=1)))
    # `-pk` — стабильный порядок записей одной секунды между страницами.
    return records.select_related("user").order_by("-created_at", "-pk")


# ---------------------------------------------------------------------------
# Формулировки
# ---------------------------------------------------------------------------


@dataclass
class KnownUsers:
    """Учётные записи страницы из одного запроса: по pk и по email."""

    by_pk: dict[int, User] = field(default_factory=dict)
    by_email: dict[str, User] = field(default_factory=dict)

    @classmethod
    def of(cls, users: Iterable[User]) -> KnownUsers:
        known = cls()
        for user in users:
            known.by_pk[user.pk] = user
            if user.email:
                known.by_email[user.email] = user
        return known

    def label_by_email(self, email: Any) -> str:
        """«ФИО (email)» учётной записи с этой почтой; почты в базе нет — сама почта."""
        if not email:
            return EMPTY
        user = self.by_email.get(str(email))
        return manager_label(user) if user is not None else str(email)

    def label_by_pk(self, pk: Any) -> str:
        """«ФИО (email)» учётной записи; удалённой — `ID <n>`."""
        if pk is None or pk == "":
            return EMPTY
        user = self.by_pk.get(pk) if isinstance(pk, int) else None
        return manager_label(user) if user is not None else f"ID {pk}"


def _changes(record: AuditLog) -> dict[str, Any]:
    """`details["changes"]` записи; неожиданная форма старых записей — пустой словарь."""
    details = record.details if isinstance(record.details, dict) else {}
    changes = details.get("changes")
    return changes if isinstance(changes, dict) else {}


def _text(value: Any) -> str:
    return EMPTY if value is None or value == "" else str(value)


def _role(code: Any) -> str:
    if not code:
        return EMPTY
    return str(ROLE_LABELS.get(code, code)) if isinstance(code, str) else str(code)


def _date(value: Any) -> str:
    """ISO-дата журнала заказа → `ДД.ММ.ГГГГ`; не дата — как есть."""
    if not value:
        return EMPTY
    try:
        return date.fromisoformat(str(value)).strftime("%d.%m.%Y")
    except ValueError:
        return str(value)


def _flag(value: Any) -> str:
    if value is None:
        return EMPTY
    return "да" if value else "нет"


def _change(old: str, new: str) -> str:
    return f"{old} → {new}"


def _field_changes(fields: Any, order: Iterable[str]) -> list[tuple[str, Any, Any]]:
    """Изменённые поля `{имя: {old, new}}` в заданном порядке; лишнее и битое не выводится."""
    if not isinstance(fields, dict):
        return []
    result = []
    for name in order:
        value = fields.get(name)
        if isinstance(value, dict):
            result.append((name, value.get("old"), value.get("new")))
    return result


def _verify_details(changes: dict[str, Any]) -> list[str]:
    parts = []
    role_before, role_after = changes.get("role_before"), changes.get("role_after")
    if role_before != role_after:
        parts.append(f"роль: {_change(_role(role_before), _role(role_after))}")
    if changes.get("role_source") == "1c_price_type":
        parts.append("роль по виду цен 1С")
    if changes.get("linked_now"):
        parts.append("с привязкой к 1С")
    return parts


def _order_details(changes: dict[str, Any]) -> list[str]:
    parts = []
    for name, old, new in _field_changes(changes.get("fields"), EDITABLE_FIELDS):
        if name == "delivery_date":
            old, new = _date(old), _date(new)
        else:
            old, new = _text(old), _text(new)
        parts.append(f"{ORDER_FIELD_LABELS[name]}: {_change(old, new)}")
    return parts


def _rule_value(name: str, value: Any, users: KnownUsers) -> str:
    if name == "match_type" and isinstance(value, str):
        return _text(MATCH_TYPE_LABELS.get(value, value))
    if name == "is_active":
        return _flag(value)
    if name == "manager_id":
        return users.label_by_pk(value)
    return _text(value)


def _rule_details(changes: dict[str, Any], users: KnownUsers) -> list[str]:
    parts = []
    for name, old, new in _field_changes(changes.get("fields"), LOGGED_RULE_FIELDS):
        before, after = _rule_value(name, old, users), _rule_value(name, new, users)
        # Журнал правил различает "" и None (пустой адрес до и после создания),
        # в ленте оба — «—», и строка «— → —» ничего не сообщает.
        if before != after:
            parts.append(f"{RULE_FIELD_LABELS[name]}: {_change(before, after)}")
    return parts


def describe(record: AuditLog, users: KnownUsers) -> tuple[str, str]:
    """
    Действие и подробности записи.

    Действие — существительным («Блокировка клиента»): род сотрудника угадывать
    не нужно. Подробности — только из белого списка ключей `changes`;
    недостающее — «—», лишнее не выводится.
    """
    action = record.action
    changes = _changes(record)
    label = STAFF_ACTIONS.get(action, action)
    parts: list[str] = []

    if action == "verify_b2b":
        if changes.get("mode") == "link_only":
            label = VERIFY_LINK_ONLY_LABEL
        parts = _verify_details(changes)
    elif action == "change_password":
        if changes.get("usable_password") is False:
            parts = ["вход по паролю отключён"]
    elif action == "update_order":
        parts = _order_details(changes)
    elif action == "assign_responsible_manager":
        parts = [_change(users.label_by_email(changes.get("old")), users.label_by_email(changes.get("new")))]
        if changes.get("manual") is False:
            parts.append("по правилу региона")
    elif action == "change_user_role":
        parts = [_change(_role(changes.get("old")), _role(changes.get("new")))]
    elif action == "change_routing_rule":
        operation = changes.get("operation")
        if isinstance(operation, str):
            label = RULE_OPERATION_LABELS.get(operation, label)
        parts = _rule_details(changes, users)
    elif action == "create_staff":
        parts = [f"группа: {_text(changes.get('group'))}"]
    elif action in ("block_staff", "unblock_staff"):
        if changes.get("group"):
            parts = [f"группа: {changes['group']}"]
    elif action == "change_staff_group":
        parts = [_change(_text(changes.get("old")), _text(changes.get("new")))]

    return label, "; ".join(parts) or EMPTY


# ---------------------------------------------------------------------------
# Строки ленты
# ---------------------------------------------------------------------------


def _int_id(value: str) -> int | None:
    # `isdigit()` пропускает «²», на котором `int()` падает; не-ASCII цифры
    # («١٢») `int()` примет, но id от них не бывает — это не ссылка на pk 12.
    return int(value) if value.isascii() and value.isdecimal() else None


def _rule_manager_ids(changes: dict[str, Any]) -> set[int]:
    ids = set()
    for _, old, new in _field_changes(changes.get("fields"), ("manager_id",)):
        ids |= {value for value in (old, new) if isinstance(value, int)}
    return ids


def build_rows(request: HttpRequest, records: Iterable[AuditLog]) -> list[dict[str, Any]]:
    """
    Строки страницы ленты.

    Запросов — по одному на вид объекта (учётные записи, видимость клиентов,
    заказы, правила), а не на строку; вида нет на странице — нет и запроса.
    Учётные записи читаются одним запросом вместе с менеджерами из подробностей
    правил и назначений.
    """
    records = list(records)
    object_ids: dict[str, set[int]] = {"User": set(), "Order": set(), "ManagerRoutingRule": set()}
    label_ids: set[int] = set()
    emails: set[str] = set()
    for record in records:
        pk = _int_id(record.resource_id)
        if pk is not None and record.resource_type in object_ids:
            object_ids[record.resource_type].add(pk)
        changes = _changes(record)
        if record.action == "assign_responsible_manager":
            emails |= {str(changes[key]) for key in ("old", "new") if changes.get(key)}
        elif record.action == "change_routing_rule":
            label_ids |= _rule_manager_ids(changes)

    users = KnownUsers()
    if object_ids["User"] or label_ids or emails:
        users = KnownUsers.of(User.objects.filter(Q(pk__in=object_ids["User"] | label_ids) | Q(email__in=emails)))
    # Ссылка на клиента — только если он виден в /manager/: у руководителя
    # выборка раздела отсекает учётные записи сотрудников.
    visible_clients: set[int] = set()
    if object_ids["User"]:
        visible_clients = set(
            scope_clients(request, User.objects.filter(pk__in=object_ids["User"])).values_list("pk", flat=True)
        )
    visible_orders: set[int] = set()
    if object_ids["Order"]:
        visible_orders = set(
            scope_orders(request, Order.objects.filter(pk__in=object_ids["Order"])).values_list("pk", flat=True)
        )
    existing_rules: set[int] = set()
    if object_ids["ManagerRoutingRule"]:
        existing_rules = set(
            ManagerRoutingRule.objects.filter(pk__in=object_ids["ManagerRoutingRule"]).values_list("pk", flat=True)
        )

    rows = []
    for record in records:
        pk = _int_id(record.resource_id)
        changes = _changes(record)
        object_label, object_url = _object(record, pk, changes, users, visible_clients, visible_orders, existing_rules)
        action, details = describe(record, users)
        rows.append(
            {
                "date": timezone.localtime(record.created_at).strftime("%d.%m.%Y %H:%M"),
                # Записи без автора лента отсекает в journal_records.
                "author": manager_label(cast(User, record.user)),
                "action": action,
                "object_label": object_label,
                "object_url": object_url,
                "details": details,
            }
        )
    return rows


def _object(
    record: AuditLog,
    pk: int | None,
    changes: dict[str, Any],
    users: KnownUsers,
    visible_clients: set[int],
    visible_orders: set[int],
    existing_rules: set[int],
) -> tuple[str, str]:
    """Подпись объекта и ссылка на него; ссылки нет — пустая строка."""
    if record.resource_type == "User":
        user = users.by_pk.get(pk) if pk is not None else None
        if user is None:
            # Учётная запись удалена: подпись — почта из записи.
            return str(changes.get("email") or changes.get("target_email") or f"ID {record.resource_id}"), ""
        if pk in visible_clients:
            return manager_label(user), reverse("manager:users_user_change", args=[pk])
        if user.is_staff and not user.is_superuser:
            # Как выборка SupervisorStaffAdmin.
            return manager_label(user), reverse("supervisor:users_user_change", args=[pk])
        return manager_label(user), ""
    if record.resource_type == "Order":
        number = changes.get("order_number")
        label = f"Заказ {format_order_number(str(number))}" if number else f"Заказ ID {record.resource_id}"
        url = reverse("manager:orders_order_change", args=[pk]) if pk in visible_orders else ""
        return label, url
    if record.resource_type == "ManagerRoutingRule":
        label = str(changes.get("rule") or f"ID {record.resource_id}")
        url = reverse("supervisor:common_managerroutingrule_change", args=[pk]) if pk in existing_rules else ""
        return label, url
    return f"ID {record.resource_id}", ""


# ---------------------------------------------------------------------------
# Страница
# ---------------------------------------------------------------------------


def _period_label(date_from: date | None, date_to: date | None) -> str:
    if date_from and date_to:
        return f"Период: {date_from:%d.%m.%Y} — {date_to:%d.%m.%Y}"
    if date_from:
        return f"Период: с {date_from:%d.%m.%Y}"
    if date_to:
        return f"Период: по {date_to:%d.%m.%Y}"
    return "Период: всё время"


def _period_links(staff: User | None, date_from: date | None, date_to: date | None, valid: bool) -> list[dict]:
    """Быстрые ссылки периода; выбранный сотрудник сохраняется."""
    staff_param = [("staff", staff.pk)] if staff is not None else []
    links = [
        {
            "name": "Всё время",
            "url": "?" + urlencode([*staff_param, ("date_from", ""), ("date_to", "")]),
            "selected": valid and date_from is None and date_to is None,
        }
    ]
    for name, period in period_presets(timezone.localdate()):
        query = [*staff_param, ("date_from", period.date_from.isoformat()), ("date_to", period.date_to.isoformat())]
        links.append(
            {
                "name": name,
                "url": "?" + urlencode(query),
                "selected": valid and (date_from, date_to) == (period.date_from, period.date_to),
            }
        )
    return links


def build_journal(request: HttpRequest) -> dict[str, Any]:
    """Контекст страницы ленты."""
    form = journal_filter(request)
    valid = form.is_valid()
    # Неверная форма оставляет в `cleaned_data` верные поля: ссылки периода
    # сохраняют сотрудника, пока он выбран верно (неверный в `cleaned_data` не попадает).
    staff, date_from, date_to = (form.cleaned_data.get(name) for name in ("staff", "date_from", "date_to"))

    paginator = Paginator(journal_records(form), PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page"))

    def page_url(number: int) -> str:
        # Из данных формы, а не из request.GET: в них период по умолчанию.
        query = cast(QueryDict, form.data).copy()
        query["page"] = str(number)
        return "?" + query.urlencode()

    return {
        "filter_form": form,
        "filter_invalid": not valid,
        "period_links": _period_links(staff, date_from, date_to, valid),
        "period_label": _period_label(date_from, date_to) if valid else "",
        "paginator": paginator,
        "page_obj": page_obj,
        "rows": build_rows(request, page_obj.object_list),
        "newer_url": page_url(page_obj.previous_page_number()) if page_obj.has_previous() else "",
        "older_url": page_url(page_obj.next_page_number()) if page_obj.has_next() else "",
    }

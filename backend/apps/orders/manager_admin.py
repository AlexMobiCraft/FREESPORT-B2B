"""
Раздел менеджера `/manager/` — заказы своих клиентов и очередь главной (стори 42.5).

Урезанный `OrderAdmin` на сайте `manager_site`: только мастер-заказы клиентов
из `scope_clients`, карточка из белого списка полей, правятся только трек-номер
и дата доставки. Статус, состав и оплата приходят из 1С и в разделе не меняются.

Модуль импортируется из `OrdersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/orders/admin.py`.
"""

from __future__ import annotations

import csv
import unicodedata
from datetime import date, datetime
from typing import Any, cast

from django import forms
from django.contrib import admin
from django.contrib.admin import AdminSite
from django.core.exceptions import ValidationError
from django.db.models import Count, Min, Q, QuerySet
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from django.utils.safestring import SafeString

from apps.common.models import AuditLog
from apps.common.utils.consent_audit import get_client_ip
from apps.orders.admin import OrderAdmin
from apps.orders.models import Order
from apps.users.manager_admin import scope_clients
from apps.users.models import User
from apps.users.staff_roles import is_supervisor
from freesport.admin_site import manager_site

# Единственные поля заказа, которые меняет менеджер; остальное — из 1С и оформления.
EDITABLE_FIELDS = ("tracking_number", "delivery_date")

# Колонки и порядок — как у OrderAdmin.export_to_csv в /admin/, подписи по-русски.
MANAGER_CSV_HEADER = [
    "Номер заказа",
    "Номер (UI)",
    "Клиент",
    "Статус",
    "Оплата",
    "Сумма",
    "Способ доставки",
    "Дата создания",
]

# Символы, с которых Excel начинает формулу (OWASP «CSV Injection»), и их
# полноширинные варианты.
_FORMULA_PREFIXES = ("=", "+", "-", "@", "＝", "＋", "－", "＠")

STALE_CARD_MESSAGE = (
    "Трек-номер или дату доставки этого заказа изменили, пока карточка была открыта. "
    "Изменения не сохранены. Обновите страницу и внесите правку заново."
)


def csv_cell(value: Any) -> str:
    """
    Ячейка CSV, которую Excel не выполнит как формулу.

    Значение, у которого после ведущих пробелов и управляющих символов идёт
    `=`, `+`, `-` или `@`, а также начинающееся с табуляции или возврата
    каретки (`\\r`), получает в начало апостроф: Excel покажет его как текст.
    """
    text = str(value)
    meaningful = text.lstrip()
    while meaningful and unicodedata.category(meaningful[0]).startswith("C"):
        meaningful = meaningful[1:].lstrip()
    if text.startswith(("\t", "\r")) or meaningful.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def scope_orders(request: HttpRequest, queryset: QuerySet[Order]) -> QuerySet[Order]:
    """
    Единственное правило видимости заказов в разделе менеджера.

    Видны мастер-заказы, клиент которых виден в разделе (`scope_clients`):
    своего правила у заказов нет. Подзапрос `user__in` отсекает и заказы без
    клиента, и заказы учётных записей сотрудников. Субзаказы видны только
    внутри карточки мастера. Руководитель (стори 42.7) видит мастер-заказы
    всех клиентов и заказы без клиента (наследие `order_export`).
    """
    clients = Q(user__in=scope_clients(request, User.objects.all()))
    if is_supervisor(request):
        clients |= Q(user__isnull=True)
    return queryset.filter(clients, is_master=True)


def days_ru(n: int) -> str:
    """Число дней с согласованным словом: 1 день, 2 дня, 5 дней, 11 дней, 21 день."""
    tail = abs(n) % 100
    if tail % 10 == 1 and tail != 11:
        word = "день"
    elif 2 <= tail % 10 <= 4 and not 12 <= tail <= 14:
        word = "дня"
    else:
        word = "дней"
    return f"{n} {word}"


def waiting_age(oldest: datetime) -> str:
    """
    Срок ожидания заявки: «сегодня» или «N дней».

    Календарные дни в часовом поясе проекта: поданная вчера в 23:50
    в 00:10 — «1 день», а не 0 полных суток. Общая для очереди менеджера
    и сводки руководителя (стори 42.8).
    """
    age = (timezone.localdate() - timezone.localtime(oldest).date()).days
    return "сегодня" if age <= 0 else days_ru(age)


def manager_queue(request: HttpRequest, site: AdminSite) -> list[dict[str, Any]]:
    """
    Очередь главной раздела: заявки на верификацию и новые заказы своих клиентов.

    Каждый счётчик — один агрегирующий запрос (NFR-42-04). Выборки совпадают
    со списками по ссылкам: список клиентов по умолчанию скрывает записи
    `unregistered`, поэтому счётчик их тоже не считает. Счётчик показан, только
    если список по его ссылке открывается: без права просмотра модели нет ни
    числа, ни ссылки, ни запроса.
    """
    queue: list[dict[str, Any]] = []
    # get_model_admin есть с Django 5.0, в закреплённых django-stubs его ещё нет.
    users_admin = site.get_model_admin(User)  # type: ignore[attr-defined]
    orders_admin = site.get_model_admin(Order)  # type: ignore[attr-defined]

    if users_admin.has_view_or_change_permission(request):
        applications = (
            scope_clients(request, User.objects.all())
            .exclude(role=User.ROLE_UNREGISTERED)
            .filter(verification_status="pending")
            .aggregate(count=Count("pk"), oldest=Min("created_at"))
        )
        applications_text = f"Заявки на верификацию: {applications['count']}"
        oldest = applications["oldest"]
        if applications["count"] and oldest is not None:
            applications_text += ", старейшая — " + waiting_age(oldest)
        queue.append(
            {
                "text": applications_text,
                "count": applications["count"],
                "url": reverse(f"{site.name}:users_user_changelist") + "?verification_status__exact=pending",
            }
        )

    if orders_admin.has_view_or_change_permission(request):
        new_orders = scope_orders(request, Order.objects.all()).filter(status="pending").count()
        queue.append(
            {
                "text": f"Новые заказы: {new_orders}",
                "count": new_orders,
                "url": reverse(f"{site.name}:orders_order_changelist") + "?status__exact=pending",
            }
        )

    return queue


def _audit_value(value: Any) -> Any:
    """Значение поля для журнала: дата — ISO-строкой, пустое — None."""
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value.isoformat()
    return value


def _client_ip(request: HttpRequest) -> str:
    # Как UserAdmin._get_client_ip: наследовать UserAdmin ради него не стоит.
    ip_address = get_client_ip(cast(Any, request))
    return "0.0.0.0" if ip_address == "unknown" else ip_address


class ManagerOrderForm(forms.ModelForm):
    """
    Карточка заказа раздела: отклоняет форму, открытую до чужой правки.

    Значения правимых полей на момент открытия уходят в форму скрытыми полями
    (`show_hidden_initial`). По ним `changed_data` сравнивает POST с тем, что
    видел менеджер, а `clean()` — с текущей строкой: если трек-номер или дату
    успели изменить из другой карточки, форма не сохраняется и просит обновить
    страницу (решение Alex по R42.5-1). Правки 1С в другие поля карточку не
    делают устаревшей.
    """

    # Запрос раздела: проверка под блокировкой повторяет правило видимости
    # заказов. Ставит ManagerOrderAdmin.get_form на класс формы этого запроса.
    request: HttpRequest

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in EDITABLE_FIELDS:
            if name in self.fields:
                self.fields[name].show_hidden_initial = True
        # Значения строки под блокировкой — «старые» значения для журнала.
        self.locked_values: dict[str, Any] = {}

    def clean(self) -> dict[str, Any]:
        super().clean()
        cleaned_data = self.cleaned_data
        editable = [name for name in EDITABLE_FIELDS if name in self.fields]
        if not editable or self.instance.pk is None:
            return cleaned_data
        # Блокировка строки заказа до конца транзакции changeform_view: вторая
        # карточка дождётся сохранения первой и увидит её правку. Порядок
        # блокировок тот же, что у импорта статусов: orders, затем бонусы.
        # Строка читается через scope_orders: get_object её не блокирует, и до
        # блокировки заказ могли удалить или вывести из выборки раздела, сменив
        # в /admin/ клиента или is_master (R42.5-12, R42.5-15).
        locked = scope_orders(self.request, Order.objects.select_for_update())
        current = locked.filter(pk=self.instance.pk).values(*editable).first()
        if current is None:
            # Тот же ответ, что на несуществующий или чужой заказ (решение 3).
            raise Http404("Заказ не найден")
        for name in editable:
            bound = self[name]
            seen = bound.field.hidden_widget().value_from_datadict(self.data, self.files, bound.html_initial_name)
            # has_changed нормализует только присланное значение (CharField срезает
            # пробелы), поэтому значение строки приводится так же — как в changed_data
            # Django: иначе трек «TRK » из БД делал бы свежую карточку устаревшей.
            if bound.field.has_changed(bound.field.to_python(current[name]), seen):
                raise ValidationError(STALE_CARD_MESSAGE, code="stale")
        self.locked_values = current
        return cleaned_data


class SubOrderInline(admin.TabularInline):
    """Субзаказы мастера — только чтение: номер, статус, сумма."""

    model = Order
    fk_name = "parent_order"
    fields = ("sub_number", "status", "total_amount")
    readonly_fields = ("sub_number", "status", "total_amount")
    verbose_name = "Субзаказ"
    verbose_name_plural = "Субзаказы"
    extra = 0
    can_delete = False
    show_change_link = False

    @admin.display(description="Субзаказ")
    def sub_number(self, obj: Order) -> str:
        return obj.order_number_display

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False


class ManagerOrderAdmin(OrderAdmin):
    """Заказы менеджера: только свои мастер-заказы, правка трек-номера и даты доставки."""

    form = ManagerOrderForm
    list_display = [
        "order_number_ui",
        "customer",
        "status",
        "payment_status_ru",
        "total_amount",
        "positions",
        "created_at",
    ]
    list_display_links = ["order_number_ui"]
    list_filter = ["status", "payment_status", "delivery_method"]
    search_fields = ["order_number", "user__email", "customer_email", "tracking_number", "user__company_name"]
    actions = ["export_orders_csv"]
    inlines = [SubOrderInline]

    # Белый список полей: новое поле Order само в раздел не попадёт.
    fieldsets: Any = (
        ("Заказ", {"fields": ("order_number_ui", "order_number", "client_link", "status", "created_at", "updated_at")}),
        ("Контакты из заказа", {"fields": ("customer_name", "customer_email", "customer_phone")}),
        ("Состав и суммы", {"fields": ("items_table", "total_amount", "discount_amount", "delivery_cost")}),
        ("Доставка", {"fields": ("delivery_method", "delivery_address", "delivery_date", "tracking_number")}),
        ("Оплата", {"fields": ("payment_method", "payment_status", "paid_at", "shipped_at", "sent_to_1c_ru")}),
        # Комментарий клиента из оформления виден ему в ЛК — только чтение.
        ("Комментарий клиента", {"fields": ("notes",)}),
    )
    readonly_fields: Any = (
        "order_number_ui",
        "order_number",
        "client_link",
        "status",
        "created_at",
        "updated_at",
        "customer_name",
        "customer_email",
        "customer_phone",
        "items_table",
        "total_amount",
        "discount_amount",
        "delivery_cost",
        "delivery_method",
        "delivery_address",
        "payment_method",
        "payment_status",
        "paid_at",
        "shipped_at",
        "sent_to_1c_ru",
        "notes",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        return scope_orders(request, super().get_queryset(request))

    def _get_obj_does_not_exist_redirect(self, request: HttpRequest, opts: Any, object_id: str) -> HttpResponse:
        # Штатный ответ на объект вне queryset — 302 на главную с «не существует».
        # В разделе чужой заказ и субзаказ неотличимы от несуществующего: 404 на
        # карточке и истории. Метод приватный (Django 5.2), его контракт
        # страхуют тесты AC3 стори 42.5.
        raise Http404("Заказ не найден")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Order | None = None) -> bool:
        return False

    def get_form(self, request: HttpRequest, obj: Order | None = None, change: bool = False, **kwargs: Any) -> Any:
        form = super().get_form(request, obj, change, **kwargs)
        # modelform_factory строит новый класс на каждый вызов: запрос не
        # переходит в чужие запросы.
        cast(type[ManagerOrderForm], form).request = request
        return form

    def get_fieldsets(self, request: HttpRequest, obj: Order | None = None) -> Any:
        return self.fieldsets

    def get_readonly_fields(self, request: HttpRequest, obj: Order | None = None) -> list[str]:
        return list(self.readonly_fields)

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        extra_context = {**(extra_context or {}), "title": "Заказы"}
        return super().changelist_view(request, extra_context)

    # Подписи раздела по-русски: display-методы OrderAdmin подписаны по-английски.

    @admin.display(description="Номер", ordering="order_number")
    def order_number_ui(self, obj: Order) -> str:
        return obj.order_number_display

    @admin.display(description="Клиент", ordering="user__email")
    def customer(self, obj: Order) -> str:
        return self.customer_display(obj)

    @admin.display(description="Оплата")
    def payment_status_ru(self, obj: Order) -> str:
        return self.payment_status_display(obj)

    @admin.display(description="Позиций")
    def positions(self, obj: Order) -> int:
        return self.items_count(obj)

    @admin.display(description="Передан в 1С", boolean=True)
    def sent_to_1c_ru(self, obj: Order) -> bool:
        return obj.sent_to_1c

    @admin.display(description="Клиент")
    def client_link(self, obj: Order) -> str:
        # Ссылка в раздел, а не readonly-FK: заказ виден только при видимом
        # клиенте, поэтому карточка клиента не ответит 404.
        user = obj.user
        if user is None:
            return "—"
        label = f"{user.email} ({user.company_name})" if user.company_name else str(user.email)
        url = reverse(f"{self.admin_site.name}:users_user_change", args=[obj.user_id])
        return format_html('<a href="{}">{}</a>', url, label)

    @admin.display(description="Состав")
    def items_table(self, obj: Order) -> str:
        # Позиции живут в субзаказах; у legacy-мастера без субзаказов — свои.
        # Выборки — из prefetch get_queryset родителя, без новых запросов.
        sub_orders = list(obj.sub_orders.all())
        if sub_orders:
            rows = [(sub.order_number_display, item) for sub in sub_orders for item in sub.items.all()]
        else:
            rows = [("—", item) for item in obj.items.all()]
        if not rows:
            return "—"
        body = format_html_join(
            "",
            "<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
            (
                (number, item.product_name, item.product_sku, item.quantity, item.unit_price, item.total_price)
                for number, item in rows
            ),
        )
        return format_html(
            "<table><thead><tr><th>Субзаказ</th><th>Товар</th><th>Артикул</th><th>Количество</th>"
            "<th>Цена</th><th>Сумма</th></tr></thead><tbody>{}</tbody></table>",
            body,
        )

    @admin.action(description="Выгрузить выбранные заказы в CSV")
    def export_orders_csv(self, request: HttpRequest, queryset: QuerySet[Order]) -> HttpResponse:
        """Экспорт выбранных заказов раздела: русские заголовки, BOM и защита от формул для Excel."""
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'
        # Без BOM Excel на Windows читает UTF-8 как cp1251.
        response.write("\ufeff")

        writer = csv.writer(response)
        writer.writerow(MANAGER_CSV_HEADER)
        # Позиции в файл не идут: prefetch из OrderAdmin.get_queryset снят.
        for order in queryset.select_related("user").prefetch_related(None):
            row = [
                order.order_number,
                order.order_number_display,
                order.customer_display_name,
                order.get_status_display(),
                order.get_payment_status_display(),
                str(order.total_amount),
                order.get_delivery_method_display(),
                # Время проекта, как в карточке: в БД — UTC.
                timezone.localtime(order.created_at).strftime("%Y-%m-%d %H:%M"),
            ]
            # Имя клиента вводит он сам — ячейки не должны стать формулами Excel.
            writer.writerow([csv_cell(value) for value in row])
        return response

    def save_model(self, request: HttpRequest, obj: Order, form: ModelForm, change: bool) -> None:
        # Пишутся только изменённые правимые поля: подделанный POST не меняет
        # другие колонки, а правка не затирает статус, оплату и флаги 1С, которые
        # импорт статусов пишет параллельно. Без изменений save() не зовётся —
        # нет ни post_save, ни записи журнала. Устаревшую карточку отклонил
        # ManagerOrderForm.clean(), строка заказа заблокирована до конца транзакции.
        changed = [name for name in EDITABLE_FIELDS if name in form.changed_data]
        if not changed:
            return
        old_values = cast(ManagerOrderForm, form).locked_values
        obj.save(update_fields=[*changed, "updated_at"])
        AuditLog.log_action(
            user=request.user,
            action="update_order",
            resource_type="Order",
            resource_id=obj.pk,
            changes={
                "order_number": obj.order_number,
                "fields": {
                    name: {"old": _audit_value(old_values.get(name)), "new": _audit_value(getattr(obj, name))}
                    for name in changed
                },
            },
            ip_address=_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )


manager_site.register(Order, ManagerOrderAdmin)

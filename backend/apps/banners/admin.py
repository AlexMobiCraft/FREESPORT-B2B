"""
Django Admin для приложения banners
"""

from __future__ import annotations

import csv
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, cast
from urllib.parse import urlencode

from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import IntegerField, OuterRef, QuerySet, Subquery, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, URLResolver, path, reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString

from .models import Banner, BannerDailyStat

# Окно колонок статистики в списке баннеров: сегодня и 29 предыдущих дней.
STATS_WINDOW_DAYS = 30

ORD_CSV_HEADER = (
    "ERID",
    "Рекламодатель",
    "ИНН рекламодателя",
    "Баннер",
    "Начало периода",
    "Конец периода",
    "Показы",
    "Клики",
)
_FORMULA_PREFIXES = ("=", "+", "-", "@", "＝", "＋", "－", "＠")


def _csv_cell(value: Any) -> str:
    """
    Ячейка CSV, которую Excel не выполнит как формулу.

    Значение, у которого после ведущих пробелов и управляющих символов идёт
    `=`, `+`, `-` или `@`, а также начинающееся с табуляции или `\\r`,
    получает в начало апостроф. Та же логика, что у выгрузки заказов менеджера
    (`apps.orders.manager_admin.csv_cell`); импорт оттуда связал бы приложения.
    """
    text = str(value)
    meaningful = text.lstrip()
    while meaningful and unicodedata.category(meaningful[0]).startswith("C"):
        meaningful = meaningful[1:].lstrip()
    if text.startswith(("\t", "\r")) or meaningful.startswith(_FORMULA_PREFIXES):
        return "'" + text
    return text


def _csv_text(value: str) -> str:
    """
    Ячейка, которую Excel покажет текстом как есть: `="…"`.

    Без этого ИНН с ведущим нулём потерял бы его, а 12-значный ИНН ушёл бы
    в экспоненту. Кавычки внутри значения удваиваются по правилам формулы Excel.
    """
    return '="' + value.replace('"', '""') + '"'


def _format_date(value: date) -> str:
    return value.strftime("%d.%m.%Y")


def _ctr(views: int, clicks: int) -> str:
    """CTR в процентах; при нуле показов — «—»."""
    if not views:
        return "—"
    return f"{clicks * 100 / views:.2f} %".replace(".", ",")


def _stat_total(field: str, since: date) -> Coalesce:
    """Сумма `field` статистики баннера с даты `since` — подзапросом, без JOIN по обратному FK."""
    totals = (
        BannerDailyStat.objects.filter(banner_id=OuterRef("pk"), date__gte=since)
        .order_by()
        .values("banner_id")
        .annotate(total=Sum(field))
        .values("total")[:1]
    )
    return Coalesce(Subquery(totals, output_field=IntegerField()), 0)


@admin.register(Banner)
class BannerAdmin(admin.ModelAdmin):
    """Admin для модели Banner"""

    list_display = (
        "title",
        "type",
        "image_preview",
        "is_advertisement",
        "get_is_active_display",
        "priority",
        "target_groups_display",
        "start_date",
        "end_date",
        "views_30d",
        "clicks_30d",
        "ctr_30d",
    )
    list_filter = (
        "type",
        "is_active",
        "is_advertisement",
        "show_to_guests",
        "show_to_authenticated",
        "show_to_trainers",
        "show_to_wholesale",
        "show_to_federation",
    )
    search_fields = ("title", "subtitle", "advertiser_name", "advertiser_inn")
    readonly_fields = ("created_at", "updated_at", "image_preview", "mobile_image_preview")

    fieldsets = (
        (
            "Контент",
            {
                "fields": (
                    "type",
                    "title",
                    "subtitle",
                    "image",
                    "image_preview",
                    "mobile_image",
                    "mobile_image_preview",
                    "image_alt",
                    "cta_text",
                    "cta_link",
                ),
            },
        ),
        (
            "Таргетинг",
            {
                "fields": (
                    "show_to_guests",
                    "show_to_authenticated",
                    "show_to_trainers",
                    "show_to_wholesale",
                    "show_to_federation",
                ),
                "description": ("Выберите целевые группы пользователей для показа баннера"),
            },
        ),
        (
            "Маркировка рекламы",
            {
                "fields": (
                    "is_advertisement",
                    "advertiser_name",
                    "advertiser_inn",
                    "erid",
                ),
                "description": (
                    "Включите «Является рекламой», чтобы показать на баннере метку «Реклама» "
                    "с реквизитами. Наименование и ИНН обязательны при включённой маркировке. "
                    "Доступно только для маркетинговых баннеров. "
                    "Новый рекламодатель — заведите новый баннер: смена наименования и ИНН "
                    "перепишет их и в прошлой статистике баннера."
                ),
            },
        ),
        (
            "Управление",
            {
                "fields": (
                    "is_active",
                    "priority",
                    "start_date",
                    "end_date",
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Banner]:
        since = timezone.localdate() - timedelta(days=STATS_WINDOW_DAYS - 1)
        queryset = cast(QuerySet[Banner], super().get_queryset(request))
        return queryset.annotate(
            views_30d=_stat_total("views", since),
            clicks_30d=_stat_total("clicks", since),
        )

    # Статистика ведётся только по маркетинговым баннерам слайдера: у баннера шапки
    # колонки показывают «—», а не нули (и не строки времён, когда он был маркетинговым).
    @admin.display(description="Показы за 30 дней", ordering="views_30d")
    def views_30d(self, obj: Banner) -> int | str:
        if obj.type != Banner.BannerType.MARKETING:
            return "—"
        return int(getattr(obj, "views_30d", 0) or 0)

    @admin.display(description="Клики за 30 дней", ordering="clicks_30d")
    def clicks_30d(self, obj: Banner) -> int | str:
        if obj.type != Banner.BannerType.MARKETING:
            return "—"
        return int(getattr(obj, "clicks_30d", 0) or 0)

    @admin.display(description="CTR за 30 дней")
    def ctr_30d(self, obj: Banner) -> str:
        if obj.type != Banner.BannerType.MARKETING:
            return "—"
        return _ctr(int(getattr(obj, "views_30d", 0) or 0), int(getattr(obj, "clicks_30d", 0) or 0))

    @admin.display(description="Превью")
    def image_preview(self, obj: Banner) -> SafeString:
        """Отображает превью изображения в списке и детальном просмотре"""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 100px;" />',
                obj.image.url,
            )
        return format_html('<span style="color: #999;">{}</span>', "Нет изображения")

    @admin.display(description="Превью (мобильное)")
    def mobile_image_preview(self, obj: Banner) -> SafeString:
        """Превью мобильного изображения. Использует format_html() для экранирования."""
        if obj.mobile_image:
            return format_html(
                '<img src="{}" style="max-width: 200px; max-height: 100px;" />',
                obj.mobile_image.url,
            )
        return format_html('<span style="color: #999;">{}</span>', "Нет мобильного изображения")

    @admin.display(description="Целевые группы")
    def target_groups_display(self, obj: Banner) -> str:
        """Отображает список целевых групп пользователей"""
        groups = []
        if obj.show_to_guests:
            groups.append("Гости")
        if obj.show_to_authenticated:
            groups.append("Авторизованные")
        if obj.show_to_trainers:
            groups.append("Тренеры")
        if obj.show_to_wholesale:
            groups.append("Оптовики")
        if obj.show_to_federation:
            groups.append("Федерации")

        return ", ".join(groups) if groups else "Не настроено"

    @admin.display(description="Статус (с учетом дат)", boolean=True)
    def get_is_active_display(self, obj: Banner) -> bool:
        """Отображает реальный статус активности с учетом расписания"""
        return obj.is_scheduled_active


# ---------------------------------------------------------------------------
# Сводка статистики за период и выгрузка CSV для ОРД
# ---------------------------------------------------------------------------

PERIOD_ALL = "all"
PERIOD_ALL_LABEL = "За весь период"
PERIOD_ERROR = "Период указан неверно — показан период по умолчанию."

MONTHS_NOMINATIVE = (
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
)
MONTHS_GENITIVE = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)

# Только ASCII-цифры и не длиннее пяти: «²» и строка в тысячу цифр до int() не доходят.
_PERIOD_NUMBER = re.compile(r"[0-9]{1,5}")


class InvalidPeriod(Exception):
    """Значение параметра периода не из опций своего списка."""


@dataclass(frozen=True)
class StatPeriod:
    """
    Период сводки: год, месяц, день. `None` на уровне — «За весь период».

    Нижний уровень задан только при заданном верхнем: `StatPeriod(month=11)` не строится.
    """

    year: int | None = None
    month: int | None = None
    day: int | None = None

    def apply(self, queryset: QuerySet[BannerDailyStat]) -> QuerySet[BannerDailyStat]:
        # Поля даты, а не диапазон: верхняя граница date(year + 1, …) у 9999 года дала бы 500.
        lookups = {"date__year": self.year, "date__month": self.month, "date__day": self.day}
        return queryset.filter(**{key: value for key, value in lookups.items() if value is not None})

    def query(self) -> dict[str, str]:
        """Параметры URL этого периода — явные, чтобы ссылка несла показанный период."""
        params = {"year": str(self.year) if self.year else PERIOD_ALL}
        if self.year:
            params["month"] = str(self.month) if self.month else PERIOD_ALL
        if self.month:
            params["day"] = str(self.day) if self.day else PERIOD_ALL
        return params

    def label(self, today: date) -> str:
        if self.year is None:
            return "за весь период"
        if self.month is None:
            return f"{self.year} год"
        if self.day is not None:
            return f"{self.day} {MONTHS_GENITIVE[self.month - 1]} {self.year}"
        text = f"{MONTHS_NOMINATIVE[self.month - 1].lower()} {self.year}"
        if (self.year, self.month) == (today.year, today.month):
            text += f" (с 1 по {today.day} {MONTHS_GENITIVE[self.month - 1]})"
        return text


def default_period(today: date) -> StatPeriod:
    """Текущий месяц текущего года — с 1-го числа по сегодня."""
    return StatPeriod(today.year, today.month)


def year_options(today: date) -> list[int]:
    """Годы, за которые есть строки, и текущий год; будущих нет. Свежие — первыми."""
    years = {value.year for value in BannerDailyStat.objects.dates("date", "year")}
    years.add(today.year)
    return sorted((year for year in years if year <= today.year), reverse=True)


def month_options(year: int, today: date) -> list[int]:
    """Месяцы года со строками; у текущего года — и текущий месяц. Будущих нет."""
    months = {value.month for value in BannerDailyStat.objects.filter(date__year=year).dates("date", "month")}
    if year == today.year:
        months.add(today.month)
    return sorted(month for month in months if (year, month) <= (today.year, today.month))


def day_options(year: int, month: int, today: date) -> list[int]:
    """Дни месяца со строками; у текущего месяца — и сегодня. Будущих нет."""
    stats = BannerDailyStat.objects.filter(date__year=year, date__month=month)
    days = {value.day for value in stats.dates("date", "day")}
    if (year, month) == (today.year, today.month):
        days.add(today.day)
    return sorted(day for day in days if date(year, month, day) <= today)


def _period_choice(raw: str | None, options: list[int]) -> int | None:
    """Значение уровня; `None` — «За весь период» (параметра нет или он `all`)."""
    if not raw or raw == PERIOD_ALL:
        return None
    if not _PERIOD_NUMBER.fullmatch(raw) or int(raw) not in options:
        raise InvalidPeriod(raw)
    return int(raw)


def parse_period(params: Mapping[str, str], today: date) -> tuple[StatPeriod, bool]:
    """
    Период из параметров `year`/`month`/`day` и признак ошибки ввода.

    Нет `year` — период по умолчанию; `year=all` — весь период, нижние уровни
    игнорируются; нет или `all` у нижнего уровня — весь вышестоящий период.
    Значение не из опций своего списка (год без строк, будущий, `month=13`,
    `day=31` в ноябре, не число) — период по умолчанию и признак ошибки.
    """
    if not params.get("year"):
        return default_period(today), False
    try:
        year = _period_choice(params.get("year"), year_options(today))
        if year is None:
            return StatPeriod(), False
        month = _period_choice(params.get("month"), month_options(year, today))
        if month is None:
            return StatPeriod(year), False
        day = _period_choice(params.get("day"), day_options(year, month, today))
    except InvalidPeriod:
        return default_period(today), True
    return StatPeriod(year, month, day), False


def _select(name: str, label: str, selected: int | None, options: list[tuple[int, str]]) -> dict[str, Any]:
    choices = [{"value": PERIOD_ALL, "label": PERIOD_ALL_LABEL, "selected": selected is None}]
    choices += [{"value": str(value), "label": text, "selected": value == selected} for value, text in options]
    return {"name": name, "label": label, "options": choices}


def period_selects(period: StatPeriod, today: date) -> list[dict[str, Any]]:
    """Выпадающие списки каскада: месяц — при выбранном годе, день — при выбранном месяце."""
    selects = [_select("year", "Год", period.year, [(year, str(year)) for year in year_options(today)])]
    if period.year:
        months = [(month, MONTHS_NOMINATIVE[month - 1]) for month in month_options(period.year, today)]
        selects.append(_select("month", "Месяц", period.month, months))
    if period.year and period.month:
        days = [(day, str(day)) for day in day_options(period.year, period.month, today)]
        selects.append(_select("day", "День", period.day, days))
    return selects


def summary_rows(queryset: QuerySet[BannerDailyStat]) -> list[dict[str, Any]]:
    """
    Строка на баннер и ERID с суммами за период.

    Смена ERID посреди периода даёт у баннера две строки, как в CSV. Название и
    реквизиты — из самой поздней строки группы; у удалённого баннера это
    последний сохранённый снимок. Сортировка — по названию и ERID.
    """
    totals = queryset.order_by().values("banner_ref_id", "erid").annotate(views=Sum("views"), clicks=Sum("clicks"))
    # DISTINCT ON — только PostgreSQL; другие СУБД проект не поддерживает.
    latest = {
        (row["banner_ref_id"], row["erid"]): row
        for row in queryset.order_by("banner_ref_id", "erid", "-date", "-pk")
        .distinct("banner_ref_id", "erid")
        .values("banner_ref_id", "erid", "banner_title", "advertiser_name", "advertiser_inn")
    }
    rows = []
    for total in totals:
        snapshot = latest[(total["banner_ref_id"], total["erid"])]
        views, clicks = int(total["views"] or 0), int(total["clicks"] or 0)
        rows.append(
            {
                "banner_ref_id": total["banner_ref_id"],
                "banner_title": snapshot["banner_title"],
                "erid": total["erid"],
                "advertiser_name": snapshot["advertiser_name"],
                "advertiser_inn": snapshot["advertiser_inn"],
                "views": views,
                "clicks": clicks,
                "ctr": _ctr(views, clicks),
            }
        )
    rows.sort(key=lambda row: (row["banner_title"].casefold(), row["erid"], row["banner_ref_id"]))
    return rows


def ord_csv_response(queryset: QuerySet[BannerDailyStat]) -> HttpResponse:
    """
    CSV для ручного переноса в кабинет ОРД: строка на креатив (ERID), баннер и месяц.

    Только строки с ERID — нерекламные баннеры в ОРД не передаются. Период через
    границу месяца даёт по строке на каждый месяц. Реквизиты — из самой поздней
    строки группы, период — первая и последняя дата с показами среди строк
    месяца (если показов в группе нет — первая и последняя дата строк).
    """
    rows = (
        queryset.exclude(erid="")
        .annotate(month=TruncMonth("date"))
        .order_by("date", "pk")
        .values(
            "erid",
            "banner_ref_id",
            "month",
            "date",
            "banner_title",
            "advertiser_name",
            "advertiser_inn",
            "views",
            "clicks",
        )
    )
    groups: dict[tuple[date, str, int], dict[str, Any]] = {}
    for row in rows:
        key = (row["month"], row["erid"], row["banner_ref_id"])
        group = groups.setdefault(
            key,
            {"views": 0, "clicks": 0, "first_view": None, "last_view": None, "first": row["date"]},
        )
        group["views"] += row["views"]
        group["clicks"] += row["clicks"]
        group["last"] = row["date"]
        if row["views"]:
            group["first_view"] = group["first_view"] or row["date"]
            group["last_view"] = row["date"]
        # Строки идут по возрастанию даты — последняя перезаписывает реквизиты.
        group["banner_title"] = row["banner_title"]
        group["advertiser_name"] = row["advertiser_name"]
        group["advertiser_inn"] = row["advertiser_inn"]

    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="ord_banners_{timezone.localdate():%Y-%m-%d}.csv"'
    # Без BOM Excel на Windows читает UTF-8 как cp1251.
    response.write("﻿")
    writer = csv.writer(response, delimiter=";")
    writer.writerow(ORD_CSV_HEADER)
    for (_month, erid, _ref_id), group in sorted(groups.items(), key=lambda item: item[0]):
        writer.writerow(
            [
                _csv_text(erid),
                _csv_cell(group["advertiser_name"]),
                _csv_text(group["advertiser_inn"]),
                _csv_cell(group["banner_title"]),
                _format_date(group["first_view"] or group["first"]),
                _format_date(group["last_view"] or group["last"]),
                group["views"],
                group["clicks"],
            ]
        )
    return response


@admin.register(BannerDailyStat)
class BannerDailyStatAdmin(admin.ModelAdmin):
    """
    Статистика показов и кликов баннеров — сводка за период и выгрузка для ОРД.

    Вместо списка Django — своя страница-сводка: строка на баннер и ERID с суммами
    за выбранный период (агрегат `values().annotate()` ломает действия, ссылки на
    объекты и сортировку стандартного списка). Карточка отдельной строки
    (`/<pk>/change/`) остаётся для сверки. Строки пишет только счётчик сайта:
    добавлять, править и удалять их нельзя, иначе отчёт в ОРД разойдётся с фактом.
    """

    summary_template = "admin/banners/bannerdailystat/summary.html"
    fields = (
        "date",
        "banner",
        "banner_ref_id",
        "banner_title",
        "erid",
        "advertiser_name",
        "advertiser_inn",
        "views",
        "clicks",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: BannerDailyStat | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: BannerDailyStat | None = None) -> bool:
        return False

    def get_urls(self) -> list[URLPattern | URLResolver]:
        # Свой путь — до родительских: ModelAdmin ловит «<path:object_id>/»,
        # и «export-ord/» после него ушёл бы в карточку строки.
        return [
            path(
                "export-ord/",
                self.admin_site.admin_view(self.export_ord_view),
                name="banners_bannerdailystat_export_ord",
            ),
            *super().get_urls(),
        ]

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> TemplateResponse:
        if not self.has_view_permission(request):
            raise PermissionDenied
        # current_app — для reverse() и {% url 'admin:…' %}: без него ссылки вели бы в /admin/.
        request.current_app = self.admin_site.name
        today = timezone.localdate()
        period, period_error = parse_period(request.GET, today)
        rows = summary_rows(period.apply(BannerDailyStat.objects.all()))
        total_views = sum(row["views"] for row in rows)
        total_clicks = sum(row["clicks"] for row in rows)
        export_url = reverse("admin:banners_bannerdailystat_export_ord", current_app=self.admin_site.name)
        context = {
            **self.admin_site.each_context(request),
            "opts": self.model._meta,
            "title": "Статистика баннеров",
            "period": period,
            "period_label": period.label(today),
            "period_error": PERIOD_ERROR if period_error else "",
            "period_selects": period_selects(period, today),
            "rows": rows,
            "total": {"views": total_views, "clicks": total_clicks, "ctr": _ctr(total_views, total_clicks)},
            # Разобранный период явными параметрами, а не сырой querystring: страница по
            # умолчанию открыта без параметров, и клик после полуночи на границе месяца
            # выгрузил бы новый месяц. Явные параметры сохраняют показанный период; если он
            # к моменту клика выпал из опций, выгрузка вернёт на сводку с «Период указан
            # неверно», а не отдаст молча другой месяц.
            "export_url": f"{export_url}?{urlencode(period.query())}",
            **(extra_context or {}),
        }
        return TemplateResponse(request, self.summary_template, context)

    def export_ord_view(self, request: HttpRequest) -> HttpResponse:
        # admin_view проверяет только доступ к разделу, право на модель — здесь.
        if not self.has_view_permission(request):
            raise PermissionDenied
        period, period_error = parse_period(request.GET, timezone.localdate())
        if period_error:
            # CSV за период по умолчанию ушёл бы в ОРД как отчёт за другой период —
            # возвращаем на сводку с тем же querystring, она покажет ошибку.
            changelist_url = reverse("admin:banners_bannerdailystat_changelist", current_app=self.admin_site.name)
            return HttpResponseRedirect(f"{changelist_url}?{request.GET.urlencode()}")
        return ord_csv_response(period.apply(BannerDailyStat.objects.all()))

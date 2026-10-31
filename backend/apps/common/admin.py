"""
Django Admin конфигурация для моделей приложения common
"""

from __future__ import annotations

import csv
from datetime import timedelta
from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils import timezone

from apps.users.staff_roles import limit_manager_field

from .models import (
    AuditLog,
    BlogPost,
    Category,
    CustomerSyncLog,
    ManagerRoutingRule,
    News,
    Newsletter,
    NotificationRecipient,
    SyncConflict,
    SyncLog,
    UserConsent,
)
from .regions import region_name, unassigned_regions
from .rich_editor import RichContentAdminMixin
from .services import CustomerSyncMonitor


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    """Admin конфигурация для AuditLog"""

    list_display = ["created_at", "user", "action", "resource_type", "resource_id"]
    list_filter = ["action", "resource_type", "created_at"]
    search_fields = ["user__email", "resource_id", "ip_address"]
    readonly_fields = ["created_at"]
    date_hierarchy = "created_at"


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """Admin конфигурация для SyncLog"""

    list_display = [
        "started_at",
        "sync_type",
        "status",
        "records_processed",
        "errors_count",
    ]
    list_filter = ["sync_type", "status", "started_at"]
    readonly_fields = ["started_at", "completed_at"]
    date_hierarchy = "started_at"


@admin.register(CustomerSyncLog)
class CustomerSyncLogAdmin(admin.ModelAdmin):
    """
    Расширенный интерфейс Django Admin для просмотра и управления
    логами синхронизации клиентов
    """

    list_display = [
        "created_at",
        "operation_type",
        "status",
        "customer_email",
        "onec_id",
        "duration_ms",
        "correlation_id_short",
    ]

    list_filter = [
        "operation_type",
        "status",
        ("created_at", admin.DateFieldListFilter),
        "customer__role",
    ]

    search_fields = [
        "customer_email",
        "onec_id",
        "correlation_id",
        "error_message",
        "customer__email",
        "customer__first_name",
        "customer__last_name",
    ]

    readonly_fields = [
        "created_at",
        "updated_at",
        "correlation_id",
        "duration_ms",
        "session",
    ]

    date_hierarchy = "created_at"

    actions = ["export_to_csv", "mark_as_reviewed"]

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "operation_type",
                    "status",
                    "customer",
                    "customer_email",
                    "onec_id",
                )
            },
        ),
        (
            "Детали операции",
            {
                "fields": ("details", "error_message", "duration_ms", "correlation_id"),
                "classes": ("collapse",),
            },
        ),
        (
            "Служебные поля",
            {
                "fields": ("session", "user"),
                "classes": ("collapse",),
            },
        ),
        (
            "Временные метки",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    list_per_page = 50

    def correlation_id_short(self, obj: CustomerSyncLog) -> str:
        """Короткая версия correlation_id для списка"""
        if obj.correlation_id:
            return str(obj.correlation_id)[:8] + "..."
        return "-"

    correlation_id_short.short_description = "Correlation ID"  # type: ignore

    @admin.action(description="Экспортировать выбранные логи в CSV")
    def export_to_csv(self, _request: HttpRequest, queryset: QuerySet[CustomerSyncLog]) -> HttpResponse:
        """Экспорт выбранных логов в CSV файл"""
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = 'attachment; filename="sync_logs.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Дата",
                "Операция",
                "Статус",
                "Email",
                "ID в 1С",
                "Длительность (мс)",
                "Ошибка",
                "Correlation ID",
            ]
        )

        for log in queryset:
            writer.writerow(
                [
                    log.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                    self._resolve_operation_label(log.operation_type),
                    self._resolve_status_label(log.status),
                    log.customer_email,
                    log.onec_id,
                    log.duration_ms or "",
                    log.error_message[:100] if log.error_message else "",
                    log.correlation_id,
                ]
            )

        return response

    @admin.action(description="Отметить как просмотренные")
    def mark_as_reviewed(self, request: HttpRequest, queryset: QuerySet[CustomerSyncLog]) -> None:
        """Пометка логов как просмотренных (добавляет метку в details)"""
        count = 0
        user_email = getattr(request.user, "email", "unknown")

        for log in queryset:
            if not log.details:
                log.details = {}
            log.details["reviewed"] = True
            log.details["reviewed_by"] = user_email
            log.details["reviewed_at"] = timezone.now().isoformat()
            log.save()
            count += 1

        self.message_user(request, f"Отмечено как просмотренные: {count} лог(ов)", level="success")

    def _resolve_operation_label(self, operation_value: str) -> str:
        """Возвращает человеко-понятное название типа операции."""
        try:
            return operation_value
        except ValueError:
            return operation_value

    def _resolve_status_label(self, status_value: str) -> str:
        """Возвращает понятное название статуса."""
        try:
            return status_value
        except ValueError:
            return status_value


@admin.register(SyncConflict)
class SyncConflictAdmin(admin.ModelAdmin):
    """Admin конфигурация для SyncConflict"""

    list_display = [
        "created_at",
        "conflict_type",
        "customer",
        "resolution_strategy",
        "is_resolved",
    ]
    list_filter = [
        "conflict_type",
        "resolution_strategy",
        "is_resolved",
        "created_at",
    ]
    search_fields = ["customer__email", "customer__first_name", "customer__last_name"]
    readonly_fields = ["created_at", "resolved_at"]
    date_hierarchy = "created_at"


# ==================================================================
# Custom Admin Views
# ==================================================================


def monitoring_dashboard_view(request: HttpRequest) -> HttpResponse:
    """
    Дашборд мониторинга синхронизации для Django Admin.
    Доступен по URL: /admin/monitoring/
    """
    monitor = CustomerSyncMonitor()
    now = timezone.now()
    start_date = now - timedelta(hours=24)

    # Собираем все метрики
    context = {
        # Контекст сайта админки: шапка, user-tools и выход, как на остальных страницах /admin/.
        **admin.site.each_context(request),
        "title": "Дашборд мониторинга синхронизации",
        "health": monitor.get_system_health(),
        "realtime": monitor.get_real_time_metrics(),
        "operations": monitor.get_operation_metrics(start_date, now),
        "business": monitor.get_business_metrics(start_date, now),
        "now": now,
    }

    return render(request, "admin/monitoring_dashboard.html", context)


# ==================================================================
# Newsletter & News Admin
# ==================================================================


@admin.register(Newsletter)
class NewsletterAdmin(admin.ModelAdmin):
    """Admin интерфейс для подписок на рассылку."""

    list_display = [
        "email",
        "is_active",
        "subscribed_at",
        "unsubscribed_at",
    ]
    list_filter = [
        "is_active",
        "subscribed_at",
    ]
    search_fields = [
        "email",
    ]
    readonly_fields = [
        "subscribed_at",
        "unsubscribed_at",
        "ip_address",
        "user_agent",
    ]
    date_hierarchy = "subscribed_at"

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Только superuser может создавать подписки через admin."""
        return bool(getattr(request.user, "is_superuser", False))


@admin.register(UserConsent)
class UserConsentAdmin(admin.ModelAdmin):
    """Read-only admin для согласий пользователей."""

    # `source` и `consent_text_version` показаны в списке и вынесены в фильтры
    # (стори 41.9): оператор ПДн должен видеть, где человек дал согласие и какую
    # формулировку подтвердил, не открывая каждую запись.
    # Для `consent_text_version` свой SimpleListFilter не нужен: у CharField без
    # choices Django подставляет AllValuesFieldListFilter и сам собирает значения.
    list_display = [
        "user",
        "consent_type",
        "source",
        "consent_text_version",
        "given_at",
        "ip_address",
        "policy_version",
    ]
    list_filter = ["consent_type", "source", "consent_text_version", "given_at"]
    search_fields = ["user__email"]
    readonly_fields = [
        "user",
        "session_key",
        "consent_type",
        "source",
        "consent_text_version",
        "given_at",
        "ip_address",
        "user_agent",
        "policy_version",
    ]

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: object | None = None) -> bool:
        return False


@admin.register(News)
class NewsAdmin(RichContentAdminMixin, admin.ModelAdmin):
    """Admin интерфейс для новостей."""

    list_display = [
        "title",
        "category",
        "is_published",
        "published_at",
        "created_at",
    ]
    list_filter = [
        "is_published",
        "category",
        "published_at",
    ]
    search_fields = [
        "title",
        "excerpt",
        "content",
        "category__name",
    ]
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "published_at"

    # Улучшенное отображение поля категории с выпадающим списком
    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Настройка отображения поля category для удобного выбора категорий"""
        if db_field.name == "category":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_active=True)
            kwargs["empty_label"] = "Выберите категорию"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "title",
                    "slug",
                    "category",
                    "author",
                )
            },
        ),
        (
            "Контент",
            {
                "fields": (
                    "excerpt",
                    "content",
                    "image",
                )
            },
        ),
        (
            "Публикация",
            {
                "fields": (
                    "is_published",
                    "published_at",
                )
            },
        ),
        (
            "Метаданные",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(BlogPost)
class BlogPostAdmin(RichContentAdminMixin, admin.ModelAdmin):
    """Admin интерфейс для статей блога."""

    list_display = [
        "title",
        "category",
        "is_published",
        "published_at",
        "created_at",
    ]
    list_filter = [
        "is_published",
        "category",
        "published_at",
    ]
    search_fields = [
        "title",
        "subtitle",
        "excerpt",
        "content",
        "category__name",
        "meta_description",
    ]
    prepopulated_fields = {
        "slug": ("title",),
    }
    readonly_fields = [
        "created_at",
        "updated_at",
    ]
    date_hierarchy = "published_at"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Настройка отображения поля category для удобного выбора категорий"""
        if db_field.name == "category":
            kwargs["queryset"] = db_field.related_model.objects.filter(is_active=True)
            kwargs["empty_label"] = "Выберите категорию"
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "title",
                    "slug",
                    "subtitle",
                    "category",
                    "author",
                )
            },
        ),
        (
            "Контент",
            {
                "fields": (
                    "excerpt",
                    "content",
                    "image",
                )
            },
        ),
        (
            "SEO",
            {
                "fields": (
                    "meta_title",
                    "meta_description",
                )
            },
        ),
        (
            "Публикация",
            {
                "fields": (
                    "is_published",
                    "published_at",
                )
            },
        ),
        (
            "Метаданные",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(Category)
class ContentCategoryAdmin(admin.ModelAdmin):
    """
    Рубрики новостей и блога — в `/admin/` и в разделе маркетинга (стори 42.6).

    Рубрику с новостями или дочерними рубриками удалить нельзя: `News.category`
    и `Category.parent` — `CASCADE`, и штатное удаление молча снесло бы новости
    вместе с рубрикой. Статьи блога (`SET_NULL`) удалению не мешают.
    """

    list_display = ["name", "parent", "is_active", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
    # «Смотреть на сайте» вёл бы в get_absolute_url с несуществующим маршрутом.
    view_on_site = False

    def get_queryset(self, request: HttpRequest) -> QuerySet[Category]:
        # Колонка «Родительская категория» — без запроса на строку.
        return super().get_queryset(request).select_related("parent")

    def get_deleted_objects(self, objs: Any, request: HttpRequest) -> tuple[Any, Any, Any, list[Any]]:
        deleted, model_count, perms_needed, protected = super().get_deleted_objects(objs, request)
        protected = list(protected)
        selected = [obj.pk for obj in objs]
        # Новости удаляемых рубрик — в том числе дочерних, выбранных вместе с
        # родителем: их каскад сносит новости так же.
        for news in News.objects.filter(category__in=selected).order_by("title"):
            protected.append(f"Новость: {news.title}")
        # Дочерняя рубрика, выбранная вместе с родителем, сама по себе удалению
        # не мешает: её новости уже попали в список выше.
        for child in Category.objects.filter(parent__in=selected).exclude(pk__in=selected).order_by("name"):
            protected.append(f"Рубрика: {child.name}")
        return deleted, model_count, perms_needed, protected


# ==================================================================
# Notification Recipients Admin
# ==================================================================


@admin.register(NotificationRecipient)
class NotificationRecipientAdmin(admin.ModelAdmin):
    """Admin интерфейс для управления получателями уведомлений."""

    list_display = [
        "email",
        "name",
        "is_active",
        "notify_new_orders",
        "notify_order_cancelled",
        "notify_user_verification",
        "notify_pending_queue",
        "notify_low_stock",
        "notify_daily_summary",
        "created_at",
    ]
    list_filter = [
        "is_active",
        "notify_new_orders",
        "notify_user_verification",
        "notify_low_stock",
        "notify_daily_summary",
    ]
    search_fields = [
        "email",
        "name",
    ]
    list_editable = [
        "is_active",
        "notify_new_orders",
        "notify_order_cancelled",
        "notify_user_verification",
        "notify_pending_queue",
        "notify_low_stock",
        "notify_daily_summary",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Получатель",
            {
                "fields": (
                    "email",
                    "name",
                    "is_active",
                )
            },
        ),
        (
            "Уведомления о заказах",
            {
                "fields": (
                    "notify_new_orders",
                    "notify_order_cancelled",
                )
            },
        ),
        (
            "Уведомления о пользователях",
            {
                "fields": (
                    "notify_user_verification",
                    "notify_pending_queue",
                )
            },
        ),
        (
            "Уведомления о товарах и отчётах",
            {
                "fields": (
                    "notify_low_stock",
                    "notify_daily_summary",
                )
            },
        ),
        (
            "Метаданные",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )


# ==================================================================
# Manager Routing Rules Admin
# ==================================================================


@admin.register(ManagerRoutingRule)
class ManagerRoutingRuleAdmin(admin.ModelAdmin):
    """Admin интерфейс для правил маршрутизации заявок на менеджеров."""

    list_display = [
        "match_type",
        "match_value",
        "region_display",
        "manager",
        "manager_name",
        "manager_email",
        "federal_district",
        "is_active",
    ]
    list_select_related = ("manager",)
    list_filter = [
        "match_type",
        "is_active",
        "federal_district",
    ]
    search_fields = [
        "match_value",
        "manager_name",
        "manager_email",
        "federal_district",
    ]
    list_editable = [
        "manager_email",
        "is_active",
    ]
    readonly_fields = [
        "created_at",
        "updated_at",
    ]

    fieldsets = (
        (
            "Правило",
            {
                "fields": (
                    "match_type",
                    "match_value",
                    "is_active",
                )
            },
        ),
        (
            "Менеджер",
            {
                "fields": (
                    "manager",
                    "manager_name",
                    "manager_email",
                    "federal_district",
                ),
                "description": "Письма уходят на email выбранного менеджера; "
                "email ниже — только пока менеджер не выбран",
            },
        ),
        (
            "Метаданные",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    def get_form(
        self, request: HttpRequest, obj: ManagerRoutingRule | None = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form = super().get_form(request, obj, change=change, **kwargs)
        # Менеджер правила — только активный менеджер или руководитель; текущий
        # бывший менеджер виден выбранным, но сохранить его нельзя (стори 42.7).
        field = form.base_fields.get("manager")
        if field is not None:
            limit_manager_field(field, obj.manager_id if obj is not None else None)
        return form

    @admin.display(description="Регион")
    def region_display(self, obj: ManagerRoutingRule) -> str:
        if obj.match_type == ManagerRoutingRule.MATCH_INN_REGION:
            return region_name(obj.match_value)
        if obj.match_type == ManagerRoutingRule.MATCH_COUNTRY:
            return obj.match_value
        return "—"

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        """Над списком — коды регионов, которым ещё не назначен менеджер."""
        extra_context = {**(extra_context or {}), "unassigned_regions": unassigned_regions()}
        return super().changelist_view(request, extra_context=extra_context)

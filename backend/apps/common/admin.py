"""
Django Admin конфигурация для моделей приложения common
"""

from __future__ import annotations

import csv
import logging
from datetime import timedelta
from typing import Any

from django.contrib import admin, messages
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.options import IS_POPUP_VAR
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.contrib.admin.utils import unquote
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q, QuerySet
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseNotAllowed, HttpResponseRedirect
from django.shortcuts import render
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
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
from .services.newsletter_campaign import (
    CAP_REACHED_MESSAGE,
    NOT_PUBLISHED_MESSAGE,
    NewsletterCampaignError,
    article_label,
    is_published,
    log_campaign_start,
    recipients_to_send,
    remaining_daily_quota,
    send_test,
    start_campaign,
)

logger = logging.getLogger(__name__)


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


ONE_ARTICLE_MESSAGE = "Выберите один материал."
ALREADY_SENT_MESSAGE = "Материал уже отправлен всем активным подписчикам."
QUEUE_DOWN_MESSAGE = "Рассылка не запущена: очередь задач недоступна, повторите позже."
TEST_FAILED_MESSAGE = "Тестовое письмо не отправлено: ошибка почтового сервера."


class NewsletterMailingAdminMixin(admin.ModelAdmin):
    """
    Рассылка новости или статьи подписчикам из списка материалов и с формы.

    «Разослать подписчикам» — через страницу подтверждения «Отправить N
    подписчикам?», «Отправить тест мне» — сразу на email сотрудника. Те же два
    действия есть кнопками на форме материала («Сохранить и …»): тест уходит
    сразу после сохранения, рассылка — через редирект на GET-страницу
    подтверждения. Всё требует права на изменение материала. Колонка
    «Рассылка» — счётчики доставок, посчитанные в `get_queryset` одним запросом.
    """

    actions = ["send_newsletter", "send_newsletter_test"]
    change_form_template = "admin/common/newsletter_change_form.html"

    # Имена кнопок формы в POST.
    SEND_BUTTON = "_newsletter_send"
    TEST_BUTTON = "_newsletter_test"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Any]:
        deliveries = "newsletter_campaign__deliveries"
        return (
            super()
            .get_queryset(request)
            .annotate(
                newsletter_total=Count(deliveries),
                newsletter_sent=Count(deliveries, filter=Q(**{f"{deliveries}__status": "sent"})),
                newsletter_failed=Count(deliveries, filter=Q(**{f"{deliveries}__status": "failed"})),
                newsletter_queued=Count(deliveries, filter=Q(**{f"{deliveries}__status__in": ["pending", "sending"]})),
            )
        )

    @admin.display(description="Рассылка")
    def newsletter_status(self, obj: Any) -> str:
        if not getattr(obj, "newsletter_total", 0):
            return "—"
        return f"отправлено {obj.newsletter_sent} · ошибок {obj.newsletter_failed} · в очереди {obj.newsletter_queued}"

    # ------------------------------------------------------------------
    # Адреса
    # ------------------------------------------------------------------

    def _admin_url(self, name: str, *args: Any) -> str:
        opts = self.model._meta
        return reverse(f"{self.admin_site.name}:{opts.app_label}_{opts.model_name}_{name}", args=args)

    def _admin_url_with_filters(self, request: HttpRequest, name: str, *args: Any) -> str:
        """Адрес раздела с `_changelist_filters` запроса (для списка — развёрнутыми)."""
        context = {"preserved_filters": self.get_preserved_filters(request), "opts": self.model._meta}
        return str(add_preserved_filters(context, self._admin_url(name, *args)))

    def get_urls(self) -> list[URLPattern]:
        opts = self.model._meta
        # До родительских: иначе catch-all `<path:object_id>/` перехватит путь.
        return [
            path(
                "<path:object_id>/newsletter/confirm/",
                self.admin_site.admin_view(self.newsletter_confirm_view),
                name=f"{opts.app_label}_{opts.model_name}_newsletter_confirm",
            ),
            *super().get_urls(),
        ]

    # ------------------------------------------------------------------
    # Действия списка
    # ------------------------------------------------------------------

    def _single_article(self, request: HttpRequest, queryset: QuerySet[Any]) -> Any | None:
        pks = list(queryset.values_list("pk", flat=True)[:2])
        if len(pks) != 1:
            self.message_user(request, ONE_ARTICLE_MESSAGE, level=messages.ERROR)
            return None
        # Без аннотаций списка: материал перечитан как есть.
        return self.model._default_manager.get(pk=pks[0])

    @admin.action(description="Разослать подписчикам", permissions=["change"])
    def send_newsletter(self, request: HttpRequest, queryset: QuerySet[Any]) -> TemplateResponse | None:
        article = self._single_article(request, queryset)
        if article is None:
            return None
        if not is_published(article):
            self.message_user(request, NOT_PUBLISHED_MESSAGE, level=messages.ERROR)
            return None
        if request.POST.get("post") == "yes":
            self._start_newsletter(request, article)
            return None
        return self._confirmation_page(
            request, article, form_action="", cancel_url=self._admin_url("changelist"), from_list=True
        )

    def _confirmation_page(
        self, request: HttpRequest, article: Any, *, form_action: str, cancel_url: str, from_list: bool = False
    ) -> TemplateResponse | None:
        """Страница «Отправить N подписчикам?»; `None` — сообщение показано, спрашивать не о чем."""
        quota = remaining_daily_quota()
        if quota <= 0:
            self.message_user(request, CAP_REACHED_MESSAGE, level=messages.ERROR)
            return None
        recipients = recipients_to_send(article)
        if recipients == 0:
            self.message_user(request, ALREADY_SENT_MESSAGE, level=messages.INFO)
            return None
        # Как у delete_selected: reverse() и {% url 'admin:…' %} — в текущий раздел.
        request.current_app = self.admin_site.name
        context = {
            **self.admin_site.each_context(request),
            "title": "Рассылка подписчикам",
            "opts": self.model._meta,
            "article": article,
            "article_label": article_label(article),
            "recipients": recipients,
            "daily_quota": quota,
            "action_checkbox_name": ACTION_CHECKBOX_NAME,
            "form_action": form_action,
            "cancel_url": cancel_url,
            "from_list": from_list,
        }
        return TemplateResponse(request, "admin/common/newsletter_send_confirmation.html", context)

    def _start_newsletter(self, request: HttpRequest, article: Any) -> bool:
        """Запускает рассылку; `True` — задача поставлена, иначе сообщение уже показано."""
        # Импорт здесь: модуль задач тянет Celery и сервис рассылки, admin грузится раньше.
        from .tasks import send_newsletter_campaign

        quota = remaining_daily_quota()
        try:
            started = start_campaign(article, request.user)
        except NewsletterCampaignError as error:
            self.message_user(request, str(error), level=messages.ERROR)
            return False
        if started.queued == 0:
            self.message_user(request, ALREADY_SENT_MESSAGE, level=messages.INFO)
            return False
        # Постановка — после коммита start_campaign, явно и в try: сбой брокера
        # оставляет строки в pending до повторного запуска.
        try:
            send_newsletter_campaign.delay(started.campaign.pk)
        except Exception:  # noqa: BLE001 — любой сбой брокера даёт одно сообщение
            logger.exception("Рассылка campaign_id=%s не поставлена в очередь", started.campaign.pk)
            self.message_user(request, QUEUE_DOWN_MESSAGE, level=messages.ERROR)
            return False
        # Журнал — только о реально поставленной рассылке.
        log_campaign_start(article, request.user, started.queued)
        text = f"Рассылка запущена: {article_label(article)}, получателей — {started.queued}."
        if started.queued > quota:
            text += f" За сутки уйдёт не больше {quota} писем, остаток досылается повторным запуском" " через сутки."
        self.message_user(request, text, level=messages.SUCCESS)
        return True

    @admin.action(description="Отправить тест мне", permissions=["change"])
    def send_newsletter_test(self, request: HttpRequest, queryset: QuerySet[Any]) -> None:
        article = self._single_article(request, queryset)
        if article is None:
            return
        self._send_test_letter(request, article)

    def _send_test_letter(self, request: HttpRequest, article: Any, *, guard_errors: bool = False) -> None:
        """
        Тестовое письмо сотруднику.

        `guard_errors` — вызов с формы: сохранение материала уже выполнено внутри
        `atomic` формы, поэтому любое исключение транспорта гасится, а сам вызов
        идёт в savepoint (ошибка БД без него отравила бы транзакцию и потеряла
        сохранение).
        """
        try:
            if guard_errors:
                with transaction.atomic():
                    result = send_test(article, request.user)
            else:
                result = send_test(article, request.user)
        except NewsletterCampaignError as error:
            self.message_user(request, str(error), level=messages.ERROR)
            return
        except Exception:  # noqa: BLE001 — с формы любой сбой не должен терять сохранённый материал
            if not guard_errors:
                raise
            logger.exception("Тестовое письмо рассылки не отправлено: %s", article_label(article))
            self.message_user(request, TEST_FAILED_MESSAGE, level=messages.ERROR)
            return
        if result.status != "sent":
            logger.error("Тестовое письмо рассылки не отправлено: %s", result.error)
            self.message_user(request, TEST_FAILED_MESSAGE, level=messages.ERROR)
            return
        self.message_user(request, f"Тестовое письмо отправлено на {request.user.email}.", level=messages.SUCCESS)

    # ------------------------------------------------------------------
    # Кнопки формы материала
    # ------------------------------------------------------------------

    def response_add(self, request: HttpRequest, obj: Any, post_url_continue: str | None = None) -> HttpResponse:
        response = super().response_add(request, obj, post_url_continue)
        return self._newsletter_button_response(request, obj, response)

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        response = super().response_change(request, obj)
        return self._newsletter_button_response(request, obj, response)

    def _newsletter_button_response(self, request: HttpRequest, obj: Any, response: HttpResponse) -> HttpResponse:
        """После штатного сохранения выполняет действие нажатой кнопки рассылки."""
        test = self.TEST_BUTTON in request.POST
        if not (test or self.SEND_BUTTON in request.POST) or IS_POPUP_VAR in request.POST:
            return response
        # Право проверено и в шаблоне; здесь — на случай POST с именем кнопки от роли без `change`.
        if not self.has_change_permission(request, obj):
            return response
        form_url = self._admin_url_with_filters(request, "change", obj.pk)
        if test:
            self._send_test_letter(request, obj, guard_errors=True)
            return HttpResponseRedirect(form_url)
        if not is_published(obj):
            self.message_user(request, NOT_PUBLISHED_MESSAGE, level=messages.ERROR)
            return HttpResponseRedirect(form_url)
        # Подтверждение — отдельный GET: рассылка и `.delay()` идут вне `atomic` формы
        # и после коммита сохранения, F5 ничего не дублирует.
        return HttpResponseRedirect(self._admin_url_with_filters(request, "newsletter_confirm", obj.pk))

    def newsletter_confirm_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """GET — «Отправить N подписчикам?», POST «Да» — запуск и возврат в список."""
        if request.method not in ("GET", "POST"):
            return HttpResponseNotAllowed(["GET", "POST"])
        article = self.get_object(request, unquote(object_id))
        if article is None:
            raise Http404
        if not self.has_change_permission(request, article):
            raise PermissionDenied
        form_url = self._admin_url_with_filters(request, "change", article.pk)
        if not is_published(article):
            self.message_user(request, NOT_PUBLISHED_MESSAGE, level=messages.ERROR)
            return HttpResponseRedirect(form_url)
        if request.method == "POST":
            if self._start_newsletter(request, article):
                return HttpResponseRedirect(self._admin_url_with_filters(request, "changelist"))
            return HttpResponseRedirect(form_url)
        page = self._confirmation_page(
            request,
            article,
            form_action=self._admin_url_with_filters(request, "newsletter_confirm", article.pk),
            cancel_url=form_url,
        )
        if page is None:
            return HttpResponseRedirect(form_url)
        return page


@admin.register(News)
class NewsAdmin(NewsletterMailingAdminMixin, RichContentAdminMixin, admin.ModelAdmin):
    """Admin интерфейс для новостей."""

    list_display = [
        "title",
        "category",
        "is_published",
        "published_at",
        "newsletter_status",
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
class BlogPostAdmin(NewsletterMailingAdminMixin, RichContentAdminMixin, admin.ModelAdmin):
    """Admin интерфейс для статей блога."""

    list_display = [
        "title",
        "category",
        "is_published",
        "published_at",
        "newsletter_status",
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
        "notify_exchange_alerts",
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
        "notify_exchange_alerts",
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
            "Уведомления об обмене с 1С",
            {
                "fields": ("notify_exchange_alerts",),
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

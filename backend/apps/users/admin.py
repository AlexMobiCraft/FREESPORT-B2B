"""
Django Admin конфигурация для управления пользователями
Включает UserAdmin с поддержкой B2B верификации и интеграции с 1С
"""

from typing import Any
from urllib.parse import quote

from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q, QuerySet
from django.db.models.functions import Trim
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.html import format_html, format_html_join

from apps.common.models import AuditLog
from apps.common.utils.consent_audit import get_client_ip
from apps.users.services.link_1c_customer import (
    LinkCandidateError,
    find_link_candidates,
    link_target_q,
)
from apps.users.services.link_1c_customer import link_1c_customer as link_1c_customer_service

from .models import Address, Company, Favorite, User, matches_q


class CompanyInline(admin.StackedInline):
    """Inline для отображения информации о компании B2B пользователя"""

    model = Company
    can_delete = False
    verbose_name = "Информация о компании"
    verbose_name_plural = "Информация о компании"
    classes = ["collapse"]  # Скрыт по умолчанию

    fieldsets = (
        (
            None,
            {
                "fields": (
                    "legal_name",
                    "tax_id",
                    "kpp",
                    "legal_address",
                )
            },
        ),
        (
            "Банковские реквизиты",
            {
                "fields": (
                    "bank_name",
                    "bank_bik",
                    "account_number",
                ),
                "classes": ("collapse",),
            },
        ),
    )


class AddressInline(admin.TabularInline):
    """Inline для отображения адресов пользователя"""

    model = Address
    extra = 0
    fields = (
        "address_type",
        "full_name",
        "phone",
        "city",
        "street",
        "building",
        "building_section",
        "apartment",
        "is_default",
    )
    readonly_fields = ("created_at",)


def _company_legal_address(user: User) -> str:
    """Юридический адрес из связанной Company или прочерк."""
    company = getattr(user, "company", None)
    return (company.legal_address if company else "") or "—"


def has_1c_candidate_expression() -> ExpressionWrapper:
    """
    Индикатор «у заявки есть непривязанный контрагент 1С» одной аннотацией.

    Correlated subquery выполняется по строкам страницы changelist, а не по
    всей таблице, и не превращается в запрос на строку. Условия кандидата
    берутся из `User.objects.unlinked_1c_records()`, условия цели — из
    `link_target_q()`: те же наборы условий проверяются под блокировкой при
    самой привязке, поэтому показанный индикатор не расходится с действием.
    """
    # Trim — то же правило сравнения ИНН, что у normalize_tax_id в сервисе:
    # иначе заявка с ИНН в пробелах имела бы кандидата в карточке и пустую
    # колонку в списке, то есть постоянный носитель сигнала о ней бы молчал.
    # exclude(pk=OuterRef("pk")) не нужен: кандидат обязан иметь роль
    # `unregistered`, а внешняя строка — роль из B2B_ROLES, множества не
    # пересекаются. Лишний NOT-подзапрос внутри коррелированного EXISTS
    # ничего не отсекает и стоит запроса на каждую строку страницы.
    candidates = User.objects.unlinked_1c_records().filter(tax_id=Trim(OuterRef("tax_id")), is_active=True)
    return ExpressionWrapper(
        link_target_q() & ~Q(tax_id="") & Exists(candidates),
        output_field=BooleanField(),
    )


class Has1CCandidateFilter(admin.SimpleListFilter):
    """
    Фильтр «Есть кандидат 1С» — постоянный носитель сигнала.

    Всплывающее сообщение при одобрении исчезает после перезагрузки и тонет
    при массовых операциях, а фильтр превращает проблему в рабочую очередь.
    """

    title = "Кандидат в 1С"
    parameter_name = "has_1c_candidate"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [("yes", "Есть кандидат 1С"), ("no", "Нет кандидата 1С")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        if self.value() not in ("yes", "no"):
            return queryset

        # Обычно аннотацию уже навесил UserAdmin.get_queryset. Но фильтр
        # достижим и там, где этого не случилось (вторая AdminSite, сохранённая
        # ссылка `?has_1c_candidate=yes` из чужого контекста), и без страховки
        # это FieldError вместо списка. Выражение то же самое — копии условий нет.
        if "_has_1c_candidate" not in queryset.query.annotations:
            queryset = queryset.annotate(_has_1c_candidate=has_1c_candidate_expression())
        return queryset.filter(_has_1c_candidate=self.value() == "yes")


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Кастомный Admin для модели User с поддержкой:
    - B2B верификации
    - Интеграции с 1С
    - Массовых операций (approve, reject, block)
    - AuditLog для критичных действий
    """

    # Оптимизация N+1 queries
    list_select_related = ["company"]

    # Удобный выбор групп и разрешений (two-panel selector)
    filter_horizontal = ("groups", "user_permissions")

    # Отображение в списке
    list_display = [
        "email",
        "full_name",
        "customer_code",
        "role_display",
        "verification_status_display",
        "has_1c_candidate",
        "phone",
        "created_at",
    ]

    # Фильтры
    list_filter = [
        "role",
        "is_verified",
        "verification_status",
        Has1CCandidateFilter,
        "created_at",
        "is_active",
        "is_staff",
    ]

    # Поиск
    search_fields = [
        "email",
        "first_name",
        "last_name",
        "phone",
        "customer_code",
        "company_name",
        "tax_id",
    ]

    # Сортировка по умолчанию
    ordering = ["-created_at"]

    # Readonly поля (integration данные)
    readonly_fields = [
        "onec_id",
        "onec_guid",
        "onec_price_type_id",
        "onec_price_type_name",
        "onec_link_candidates",
        "last_sync_at",
        "last_sync_from_1c",
        "created_at",
        "updated_at",
        "company_legal_address",
    ]

    # Fieldsets для детального просмотра/редактирования
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "customer_code",
                    "phone",
                )
            },
        ),
        (
            "B2B данные",
            {
                "fields": (
                    "company_name",
                    "tax_id",
                    "company_legal_address",
                    "is_verified",
                    "verification_status",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Роль и статус",
            {
                "fields": (
                    "role",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        (
            "Права доступа",
            {
                "fields": (
                    "groups",
                    "user_permissions",
                ),
                "classes": ("collapse",),
                "description": "Группы определяют набор прав для пользователя. "
                "Пользователь получает все права, назначенные каждой из его групп.",
            },
        ),
        (
            "Интеграция с 1С",
            {
                "fields": (
                    "onec_id",
                    "onec_guid",
                    "onec_price_type_id",
                    "onec_price_type_name",
                    "onec_link_candidates",
                    "sync_status",
                    "created_in_1c",
                    "needs_1c_export",
                    "last_sync_at",
                    "last_sync_from_1c",
                    "sync_error_message",
                ),
                "classes": ("collapse",),
            },
        ),
        (
            "Временные метки",
            {
                "fields": (
                    "created_at",
                    "updated_at",
                    "last_login",
                ),
                "classes": ("collapse",),
            },
        ),
    )

    # Fieldsets для создания нового пользователя
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "email",
                    "first_name",
                    "last_name",
                    "customer_code",
                    "password1",
                    "password2",
                    "role",
                ),
            },
        ),
    )

    # Inlines
    inlines = [CompanyInline, AddressInline]

    # Admin actions
    actions = [
        "approve_b2b_users",
        "reject_b2b_users",
        "link_1c_customer",
        "block_users",
    ]

    # Queryset и fieldsets

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:
        queryset = super().get_queryset(request)
        # Аннотация нужна только списку: на карточке пользователя одна строка,
        # и лишний подзапрос там ничего не даёт.
        if self._is_changelist_request(request):
            queryset = queryset.annotate(_has_1c_candidate=has_1c_candidate_expression())
        return queryset

    def _is_changelist_request(self, request: HttpRequest) -> bool:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            return False
        return bool(resolver_match.url_name == f"{self.opts.app_label}_{self.opts.model_name}_changelist")

    def get_fieldsets(self, request: HttpRequest, obj: User | None = None) -> Any:
        fieldsets = super().get_fieldsets(request, obj)
        # Тот же критерий цели, что у колонки в списке и у проверки под
        # блокировкой: иначе карточка звала бы связать аккаунт, которому
        # действие всегда откажет (уже привязан либо не B2B).
        if obj is not None and matches_q(link_target_q(), obj) and find_link_candidates(obj):
            return fieldsets

        # Кандидатов нет — блок в карточке не выводится.
        return tuple(
            (
                name,
                {**options, "fields": tuple(f for f in options.get("fields", ()) if f != "onec_link_candidates")},
            )
            for name, options in fieldsets
        )

    # Custom display methods

    @admin.display(description="Кандидат 1С", boolean=True)
    def has_1c_candidate(self, obj: User) -> bool:
        """Индикатор из аннотации changelist'а — не запрос на строку."""
        return bool(getattr(obj, "_has_1c_candidate", False))

    @admin.display(description="Непривязанные контрагенты 1С с этим ИНН")
    def onec_link_candidates(self, obj: User) -> str:
        """
        Кандидаты на привязку в карточке заявки.

        Все значения приходят из 1С, поэтому экранируются через format_html;
        mark_safe на сырых данных недопустим.
        """
        candidates = find_link_candidates(obj)
        if not candidates:
            return "—"

        rows = format_html_join(
            "",
            "<li>ID в 1С: <b>{}</b> — {} — {}</li>",
            (
                (
                    candidate.onec_id or "—",
                    candidate.company_name or candidate.full_name or "—",
                    _company_legal_address(candidate),
                )
                for candidate in candidates
            ),
        )
        # Ссылка на список, отфильтрованный по этому же ИНН: без неё менеджеру
        # пришлось бы искать ту же строку среди 4606 пользователей вручную.
        changelist_url = f"{reverse('admin:users_user_changelist')}?q={quote(obj.tax_id or '')}"
        return format_html(
            '<ul style="margin: 0; padding-left: 18px;">{}</ul>'
            '<p style="margin-top: 6px;">Свяжите заявку действием '
            '«🔗 Связать с контрагентом 1С» в <a href="{}">списке пользователей с этим ИНН</a>.</p>',
            rows,
            changelist_url,
        )

    @admin.display(description="Вид цен из 1С")
    def onec_price_type_name(self, obj: User) -> str:
        """
        Человекочитаемое наименование вида цен по сохранённому GUID.

        Импорт PriceType локальный: приложение users не зависит от products
        на уровне модуля, и заводить эту связь ради одной подписи не нужно.
        Сравнение регистронезависимое — регистр onec_id в справочнике не
        нормализован (обнаружено в стори 40.2).
        """
        from apps.products.models import PriceType

        guid = (obj.onec_price_type_id or "").strip()
        if not guid:
            return "—"

        price_type = PriceType.objects.filter(onec_id__iexact=guid).values_list("onec_name", flat=True).first()
        return price_type or "—"

    @admin.display(description="Юридический адрес компании")
    def company_legal_address(self, obj: User) -> str:
        """Отображение юридического адреса из связанной компании"""
        if hasattr(obj, "company") and obj.company:
            return obj.company.legal_address or "-"
        return "-"

    @admin.display(description="ФИО")
    def full_name(self, obj: User) -> str:
        """Отображение полного имени пользователя"""
        return obj.full_name or "-"

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None):
        readonly_fields = list(super().get_readonly_fields(request, obj))
        if obj and obj.customer_code and obj.orders.exists() and "customer_code" not in readonly_fields:
            readonly_fields.append("customer_code")
        return readonly_fields

    @admin.display(description="Роль")
    def role_display(self, obj: User) -> str:
        """Отображение роли с цветовой индикацией"""
        role_colors = {
            "retail": "#6c757d",  # серый
            "wholesale_level1": "#0dcaf0",  # голубой
            "wholesale_level2": "#0d6efd",  # синий
            "wholesale_level3": "#6610f2",  # фиолетовый
            "wholesale_level4": "#d63384",  # розовый
            "trainer": "#198754",  # зеленый
            "federation_rep": "#fd7e14",  # оранжевый
            "admin": "#dc3545",  # красный
        }
        color = role_colors.get(obj.role, "#6c757d")
        return format_html(
            '<span style="color: {}; font-weight: bold;">●</span> {}',
            color,
            obj.get_role_display(),
        )

    @admin.display(description="Статус верификации")
    def verification_status_display(self, obj: User) -> str:
        """Отображение статуса верификации с иконками"""
        if obj.verification_status == "verified" or obj.is_verified:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> Верифицирован',
                "",
            )
        elif obj.verification_status == "pending":
            return format_html(
                '<span style="color: orange; font-weight: bold;">⏳</span> Ожидает',
                "",
            )
        else:
            return format_html(
                '<span style="color: gray;">○</span> Не верифицирован',
                "",
            )

    # Admin actions с permissions и AuditLog

    @admin.action(description="✓ Верифицировать выбранных B2B пользователей")
    def approve_b2b_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовая верификация B2B пользователей"""
        # Input validation: проверка наличия B2B пользователей
        b2b_users = queryset.filter(role__in=User.B2B_ROLES)

        if not b2b_users.exists():
            self.message_user(
                request,
                "Не выбрано ни одного B2B пользователя для верификации",
                level="warning",
            )
            return

        # Проверка на суперпользователей
        if b2b_users.filter(is_superuser=True).exists():
            self.message_user(
                request,
                "Нельзя изменять статус верификации суперпользователей",
                level="error",
            )
            return

        approved_ids: list[int] = []
        count = 0
        for user in b2b_users:
            approved_ids.append(user.pk)
            user.is_verified = True
            user.verification_status = "verified"
            # Регистрация создаёт B2B-заявку с is_active=False. Без активации
            # здесь пользователь проходит логин (блокируется только статус
            # "pending"), но получает отказ на каждом следующем запросе.
            user.is_active = True
            user.save(update_fields=["is_verified", "verification_status", "is_active", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="approve_b2b",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "verified": True,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(
            request,
            f"Успешно верифицировано {count} B2B пользователей",
            level="success",
        )
        self._warn_about_1c_candidates(request, approved_ids)

    def _warn_about_1c_candidates(self, request: HttpRequest, approved_ids: list[int]) -> None:
        """
        Одно агрегированное предупреждение на вызов действия, а не по одному
        на заявку: на пачке из 20 заявок 20 сообщений никто не читает.

        Само сообщение эфемерно — постоянный носитель сигнала — колонка
        «Кандидат 1С» и одноимённый фильтр в списке.
        """
        if not approved_ids:
            return

        # Одним запросом: аннотация вычисляется на стороне БД, а не по строке.
        flagged = list(
            User.objects.filter(pk__in=approved_ids)
            .annotate(_has_1c_candidate=has_1c_candidate_expression())
            .filter(_has_1c_candidate=True)
            .order_by("pk")
        )
        if not flagged:
            return

        links = format_html_join(
            ", ",
            '<a href="{}">{}</a>',
            (
                (
                    reverse("admin:users_user_change", args=[user.pk]),
                    user.email or f"ID {user.pk}",
                )
                for user in flagged
            ),
        )
        self.message_user(
            request,
            format_html(
                "Для {} из одобренных заявок найдены непривязанные контрагенты 1С: {}. "
                "Свяжите их действием «🔗 Связать с контрагентом 1С», иначе экспорт заказа "
                "заведёт в 1С нового контрагента. Найти все такие заявки можно фильтром «Кандидат 1С».",
                len(flagged),
                links,
            ),
            level="warning",
        )

    @admin.action(description="🔗 Связать с контрагентом 1С", permissions=["change"])
    def link_1c_customer(self, request: HttpRequest, queryset: QuerySet[User]) -> HttpResponse | None:
        """
        Привязка заявки к контрагенту 1С через страницу подтверждения.

        Выбор кандидата всегда явный: на один ИНН приходится до 74 записей,
        и «взять первого» здесь означало бы связать заявку со случайным
        филиалом. Сама логика переноса живёт в сервисе.
        """
        targets = list(queryset[:2])
        if len(targets) != 1:
            self.message_user(
                request,
                "Привязка выполняется по одной заявке: выберите ровно одного пользователя.",
                level="error",
            )
            return None

        target = targets[0]
        if target.role not in User.B2B_ROLES:
            self.message_user(
                request,
                f"Связывать с контрагентом 1С можно только B2B-аккаунт, "
                f"а роль заявителя — «{target.get_role_display()}».",
                level="error",
            )
            return None
        if target.onec_id or target.onec_guid:
            self.message_user(
                request,
                f"Аккаунт {target.email or target.pk} уже связан с 1С. " f"Перепривязка выполняется вручную.",
                level="error",
            )
            return None

        candidates = find_link_candidates(target)
        if not candidates:
            self.message_user(
                request,
                f"Непривязанных контрагентов 1С с ИНН {target.tax_id or '—'} не найдено.",
                level="warning",
            )
            return None

        if request.POST.get("apply"):
            return self._apply_link_1c_customer(request, target, candidates)

        return render(
            request,
            "admin/users/link_1c_customer.html",
            context={
                **self.admin_site.each_context(request),
                "title": "Связывание заявки с контрагентом 1С",
                "target": target,
                "candidates": candidates,
                "opts": self.model._meta,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    def _apply_link_1c_customer(
        self, request: HttpRequest, target: User, candidates: list[User]
    ) -> HttpResponseRedirect:
        """Обработка подтверждения: сверка выбора и вызов сервиса."""
        # Радиокнопка несёт пару «pk источника : показанный onec_id»: оба
        # значения проверяются повторно под блокировкой в сервисе, поэтому
        # двойная отправка и устаревшая вкладка отклоняются.
        raw_source_pk, _, expected_onec_id = (request.POST.get("candidate") or "").partition(":")

        allowed_pks = {str(candidate.pk) for candidate in candidates}
        if raw_source_pk not in allowed_pks:
            self.message_user(
                request,
                "Выберите контрагента 1С из списка — данные на странице могли устареть.",
                level="error",
            )
            return HttpResponseRedirect(request.get_full_path())

        source = next(candidate for candidate in candidates if str(candidate.pk) == raw_source_pk)
        source_code = source.customer_code

        try:
            linked = link_1c_customer_service(
                target_id=target.pk,
                source_id=int(raw_source_pk),
                expected_onec_id=expected_onec_id,
                actor=request.user if isinstance(request.user, User) else None,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except LinkCandidateError as exc:
            self.message_user(request, str(exc), level="error")
            return HttpResponseRedirect(request.get_full_path())

        self.message_user(
            request,
            f"Заявка {linked.email or linked.pk} связана с контрагентом 1С "
            f"(ID в 1С: {linked.onec_id}). Исходная запись деактивирована.",
            level="success",
        )
        if source_code and linked.customer_code and source_code != linked.customer_code:
            # Код заявителя уже вшит в номера его заказов и сменён быть не может.
            # Расхождение с 1С не ошибка привязки, но менеджер обязан его увидеть:
            # номера заказов портала и код контрагента в 1С разойдутся навсегда.
            self.message_user(
                request,
                f"Код клиента расходится с 1С: у заявителя {linked.customer_code}, "
                f"у контрагента {source_code}. Код заявителя не меняется — он уже "
                f"использован в номерах его заказов. Сверьте код в 1С вручную.",
                level="warning",
            )
        return HttpResponseRedirect(request.get_full_path())

    @admin.action(description="✗ Отклонить верификацию выбранных B2B пользователей")
    def reject_b2b_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовый отказ в верификации B2B пользователей"""
        # Input validation: проверка наличия B2B пользователей
        b2b_users = queryset.filter(role__in=User.B2B_ROLES)

        if not b2b_users.exists():
            self.message_user(
                request,
                "Не выбрано ни одного B2B пользователя для отклонения",
                level="warning",
            )
            return

        # Проверка на суперпользователей
        if b2b_users.filter(is_superuser=True).exists():
            self.message_user(
                request,
                "Нельзя изменять статус верификации суперпользователей",
                level="error",
            )
            return

        count = 0
        for user in b2b_users:
            user.is_verified = False
            user.verification_status = "unverified"
            user.save(update_fields=["is_verified", "verification_status", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="reject_b2b",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "verified": False,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(request, f"Отклонена верификация {count} B2B пользователей", level="warning")

    @admin.action(description="🚫 Заблокировать выбранных пользователей")
    def block_users(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        """Массовая блокировка пользователей"""
        # Input validation: проверка наличия пользователей для блокировки
        if not queryset.exists():
            self.message_user(
                request,
                "Не выбрано ни одного пользователя для блокировки",
                level="warning",
            )
            return

        # Фильтруем суперпользователей
        users_to_block = queryset.exclude(is_superuser=True)

        if not users_to_block.exists():
            self.message_user(
                request,
                "Нельзя блокировать суперпользователей",
                level="error",
            )
            return

        count = 0
        for user in users_to_block:
            if user.is_superuser:
                continue  # Дополнительная защита

            user.is_active = False
            user.save(update_fields=["is_active", "updated_at"])

            # AuditLog запись
            AuditLog.log_action(
                user=request.user,
                action="block_user",
                resource_type="User",
                resource_id=user.id,
                changes={
                    "email": str(user.email or ""),
                    "role": user.role,
                    "blocked": True,
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
            count += 1

        self.message_user(request, f"Заблокировано {count} пользователей", level="success")

    # Helper methods

    def _get_client_ip(self, request: HttpRequest) -> str:
        """Получение IP адреса клиента"""
        ip_address = get_client_ip(request)
        return "0.0.0.0" if ip_address == "unknown" else ip_address


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin для модели Company"""

    list_display = ["legal_name", "tax_id", "user", "created_at"]
    search_fields = ["legal_name", "tax_id", "user__email"]
    list_filter = ["created_at"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    """Admin для модели Address"""

    list_display = ["user", "address_type", "city", "is_default", "created_at"]
    list_filter = ["address_type", "is_default", "city"]
    search_fields = ["user__email", "full_name", "city", "street"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    """Admin для модели Favorite"""

    list_display = ["user", "product", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["user__email", "product__name"]
    readonly_fields = ["created_at"]

"""
Django Admin конфигурация для управления пользователями
Включает UserAdmin с поддержкой B2B верификации и интеграции с 1С
"""

from typing import TYPE_CHECKING, Any, Iterable, cast
from urllib.parse import quote

from django import forms
from django.contrib import admin
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.utils import unquote
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.core.exceptions import PermissionDenied
from django.db.models import BooleanField, Exists, ExpressionWrapper, OuterRef, Q, QuerySet
from django.db.models.functions import Lower, Trim
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html, format_html_join

from apps.common.models import AuditLog
from apps.common.utils.consent_audit import get_client_ip

if TYPE_CHECKING:
    from rest_framework.request import Request
from apps.users.services.link_1c_customer import (
    LinkCandidateError,
    find_link_candidates,
    link_target_q,
)
from apps.users.services.link_1c_customer import link_1c_customer as link_1c_customer_service
from apps.users.services.price_type_role import load_price_type_role_map
from apps.users.services.verify_b2b_application import (
    MODE_DECISION,
    VerificationError,
    eligible_link_candidates,
    is_awaiting_decision,
    reject_b2b_application,
    resolve_b2b_role,
    verification_mode,
    verify_b2b_application,
)

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


def _has_company(user: User) -> bool:
    """Есть ли Company — без запроса, если её подтянул select_related."""
    return getattr(user, "company", None) is not None


def _price_type_names(guids: Iterable[str | None]) -> dict[str, str]:
    """
    Наименования видов цен по набору GUID одним запросом.

    Ключ — GUID в нижнем регистре без пробелов: регистр onec_id в
    справочнике не нормализован (стори 40.2), сравнение регистронезависимое.
    """
    from apps.products.models import PriceType

    keys = {(guid or "").strip().lower() for guid in guids} - {""}
    if not keys:
        return {}
    rows = (
        PriceType.objects.annotate(_guid=Lower(Trim("onec_id")))
        .filter(_guid__in=keys)
        .order_by("-is_active", "pk")
        .values_list("_guid", "onec_name")
    )
    names: dict[str, str] = {}
    for guid, name in rows:
        names.setdefault(guid, name)
    return names


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


def _b2b_role_choices() -> list[tuple[str, str]]:
    labels = dict(User.ROLE_CHOICES)
    return [(role, labels.get(role, role)) for role in User.B2B_ROLES]


class VerifyB2BApplicationForm(forms.Form):
    """
    Форма страницы подтверждения заявки.

    Выбор кандидата явный и при одном кандидате: значение радиокнопки несёт
    пару «pk : показанный onec_id», и обе части сверяются под блокировкой
    в сервисе — двойная отправка и устаревшая вкладка отклоняются.
    """

    confirm = forms.BooleanField(required=False, label="Подтвердить")
    candidate = forms.CharField(required=False)
    confirm_without_1c = forms.BooleanField(required=False, label="Подтвердить без привязки к 1С")
    role = forms.ChoiceField(required=False, choices=_b2b_role_choices, label="Роль")

    def __init__(self, *args: Any, candidates: list[User], requires_without_1c: bool, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.candidates = candidates
        self.requires_without_1c = requires_without_1c

    def clean(self) -> dict[str, Any]:
        cleaned = super().clean() or {}
        if not cleaned.get("confirm"):
            self.add_error("confirm", "Отметьте «Подтвердить», чтобы подтвердить заявку.")

        cleaned["source_id"] = None
        cleaned["expected_onec_id"] = ""
        if self.candidates:
            raw_source_pk, _, expected_onec_id = (cleaned.get("candidate") or "").partition(":")
            source = next((c for c in self.candidates if str(c.pk) == raw_source_pk), None)
            if source is None:
                self.add_error("candidate", "Выберите контрагента 1С из списка.")
            else:
                cleaned["source_id"] = source.pk
                cleaned["expected_onec_id"] = expected_onec_id
        elif self.requires_without_1c and not cleaned.get("confirm_without_1c"):
            self.add_error(
                "confirm_without_1c",
                "Контрагент в 1С не найден: отметьте «Подтвердить без привязки к 1С».",
            )
        return cleaned


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Кастомный Admin для модели User с поддержкой:
    - B2B верификации
    - Интеграции с 1С
    - Массовых операций (approve, reject, block)
    - AuditLog для критичных действий
    """

    # Поля привилегий: их видит и меняет только суперпользователь (эпик 42).
    # Иначе любой с правом `users.change_user` мог бы выдать себе
    # `is_superuser`, группу или право. Атрибут класса — его переиспользуют
    # урезанные ModelAdmin разделов сотрудников (42.4+).
    PRIVILEGE_FIELDS = ("is_staff", "is_superuser", "groups", "user_permissions")

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
        "verify_b2b_link",
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
                    # Хеш пароля с кнопкой «Задать/Сбросить пароль»: без этого поля
                    # стандартная форма смены пароля BaseUserAdmin есть, но в
                    # карточке на неё нет ссылки.
                    "password",
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

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:  # type: ignore[override]
        queryset = super().get_queryset(request)
        # Аннотация нужна только списку: на карточке пользователя одна строка,
        # и лишний подзапрос там ничего не даёт.
        if self._is_changelist_request(request):
            queryset = queryset.annotate(_has_1c_candidate=has_1c_candidate_expression())
        return queryset  # type: ignore[return-value]

    def _is_changelist_request(self, request: HttpRequest) -> bool:
        resolver_match = getattr(request, "resolver_match", None)
        if resolver_match is None:
            return False
        return bool(resolver_match.url_name == f"{self.opts.app_label}_{self.opts.model_name}_changelist")

    def get_fieldsets(self, request: HttpRequest, obj: User | None = None) -> Any:  # type: ignore[override]
        fieldsets = super().get_fieldsets(request, obj)  # type: ignore[arg-type]
        # Тот же критерий цели, что у колонки в списке и у проверки под
        # блокировкой: иначе карточка звала бы связать аккаунт, которому
        # действие всегда откажет (уже привязан либо не B2B).
        if not (obj is not None and matches_q(link_target_q(), obj) and find_link_candidates(obj)):
            # Кандидатов нет — блок в карточке не выводится.
            fieldsets = tuple(
                (
                    name,
                    {**options, "fields": tuple(f for f in options.get("fields", ()) if f != "onec_link_candidates")},
                )
                for name, options in fieldsets
            )

        if request.user.is_superuser:
            return fieldsets

        # Не суперпользователь: поля привилегий убираются из fieldsets, а значит
        # и из формы (`get_form` берёт поля отсюда) — подделанный POST их не
        # тронет. Опустевший блок («Права доступа») выбрасывается целиком.
        return self._without_privilege_fields(fieldsets)

    @classmethod
    def _without_privilege_fields(cls, fieldsets: Any) -> tuple[Any, ...]:
        """Вычищает `PRIVILEGE_FIELDS` из fieldsets и выбрасывает опустевшие блоки."""
        result = []
        for name, options in fieldsets:
            fields = []
            for field in options.get("fields", ()):
                if isinstance(field, (list, tuple)):
                    row = tuple(f for f in field if f not in cls.PRIVILEGE_FIELDS)
                    if row:
                        fields.append(row)
                elif field not in cls.PRIVILEGE_FIELDS:
                    fields.append(field)
            if fields:
                result.append((name, {**options, "fields": tuple(fields)}))
        return tuple(result)

    def has_change_permission(self, request: HttpRequest, obj: User | None = None) -> bool:  # type: ignore[override]
        # Суперпользователя меняет (в т. ч. его пароль и заявку B2B) только
        # суперпользователь — иначе через смену пароля можно войти под ним.
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_change_permission(request, obj)  # type: ignore[arg-type]

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:  # type: ignore[override]
        if obj is not None and obj.is_superuser and not request.user.is_superuser:
            return False
        return super().has_delete_permission(request, obj)  # type: ignore[arg-type]

    def user_change_password(self, request: HttpRequest, id: str, form_url: str = "") -> HttpResponse:
        response = super().user_change_password(request, id, form_url)
        # Успех — единственный исход, который редиректит на карточку: ошибки
        # формы отдают 200, «конфликт данных» редиректит на саму форму пароля.
        if request.method != "POST" or not isinstance(response, HttpResponseRedirect):
            return response
        user = self.get_object(request, unquote(id))
        if user is None or response.url != reverse(f"{self.admin_site.name}:users_user_change", args=[user.pk]):
            return response

        AuditLog.log_action(
            user=request.user,
            action="change_password",
            resource_type="User",
            resource_id=user.pk,
            changes={
                "email": str(user.email or ""),
                "usable_password": user.has_usable_password(),
            },
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )
        return response

    # Страница подтверждения B2B-заявки

    def get_urls(self) -> list[URLPattern]:
        # Свой путь — перед super(): иначе общий `<path:object_id>/` поглотит
        # `<id>/verify/` и отдаст редирект на карточку.
        custom = [
            path(
                "<path:object_id>/verify/",
                self.admin_site.admin_view(self.verify_b2b_view),
                name=f"{self.opts.app_label}_{self.opts.model_name}_verify",
            ),
        ]
        return custom + super().get_urls()

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        extra_context = dict(extra_context or {})
        obj = cast("User | None", self.get_object(request, unquote(object_id)))
        extra_context["show_verify_b2b_button"] = (
            obj is not None and self.has_change_permission(request, obj) and self._verification_mode(obj) is not None
        )
        return super().change_view(request, object_id, form_url, extra_context)

    @staticmethod
    def _verification_mode(obj: User) -> str | None:
        """
        Условие доступа к странице подтверждения для одного аккаунта.

        Кандидатов ищем, только когда без них ответа нет: ждущей решения
        заявке страница доступна и так.
        """
        if obj.role not in User.B2B_ROLES or obj.is_superuser:
            return None
        if is_awaiting_decision(obj):
            return verification_mode(obj, [])
        return verification_mode(obj, eligible_link_candidates(obj))

    def verify_b2b_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """
        «Подтверждение заявки»: только данные заявки и контрагенты 1С с её ИНН.

        Подтверждение одной транзакцией связывает аккаунт с 1С, назначает роль,
        пишет AuditLog и верифицирует аккаунт (сервис verify_b2b_application).
        """
        obj = cast("User | None", self.get_object(request, unquote(object_id)))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(  # type: ignore[attr-defined,no-any-return]
                request, self.opts, object_id
            )
        # admin_view проверяет только доступ к сайту — право на изменение явно.
        if not self.has_change_permission(request, obj):
            raise PermissionDenied

        change_url = reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_change", args=[obj.pk])
        candidates = eligible_link_candidates(obj)
        mode = verification_mode(obj, candidates)
        if mode is None:
            self.message_user(
                request,
                f"Аккаунт {obj.email or obj.pk} не ждёт подтверждения: заявка уже обработана, "
                f"аккаунт не B2B или привязывать к 1С нечего.",
                level="warning",
            )
            return HttpResponseRedirect(change_url)

        requires_without_1c = matches_q(link_target_q(), obj) and not candidates

        if request.method == "POST" and request.POST.get("_reject"):
            if mode != MODE_DECISION:
                self.message_user(request, "Отклонить можно только заявку, ждущую решения.", level="error")
                return HttpResponseRedirect(request.get_full_path())
            return self._apply_reject_b2b(request, obj, change_url)

        if request.method == "POST":
            form = VerifyB2BApplicationForm(
                request.POST, candidates=candidates, requires_without_1c=requires_without_1c
            )
            if form.is_valid():
                return self._apply_verify_b2b(request, obj, form.cleaned_data, change_url)
        else:
            initial: dict[str, Any] = {"role": obj.role}
            if len(candidates) == 1:
                # Предвыбор только при единственном кандидате: из нескольких
                # контрагентов автоматически не выбирается никто.
                initial["candidate"] = f"{candidates[0].pk}:{candidates[0].onec_id or ''}"
            form = VerifyB2BApplicationForm(
                initial=initial, candidates=candidates, requires_without_1c=requires_without_1c
            )

        return render(
            request,
            "admin/users/verify_b2b_application.html",
            self._verify_page_context(request, obj, mode, candidates, form),
        )

    def _verify_page_context(
        self,
        request: HttpRequest,
        obj: User,
        mode: str,
        candidates: list[User],
        form: VerifyB2BApplicationForm,
    ) -> dict[str, Any]:
        """
        Контекст страницы подтверждения.

        Виды цен читаются фиксированным числом запросов независимо от числа
        кандидатов: маппинг ролей одним запросом и наименования одним
        запросом по набору GUID.
        """
        role_labels = dict(User.ROLE_CHOICES)
        role_map = load_price_type_role_map()
        is_linked = bool(obj.onec_id or obj.onec_guid)

        guid_sources = [c.onec_price_type_id for c in candidates]
        if is_linked:
            guid_sources.append(obj.onec_price_type_id)
        price_type_names = _price_type_names(guid_sources)

        def describe(price_type_id: str | None) -> tuple[str, str | None]:
            name = price_type_names.get((price_type_id or "").strip().lower(), "")
            return name or (price_type_id or "").strip(), resolve_b2b_role(price_type_id, role_map)

        selected = form["candidate"].value() or ""
        rows = []
        for candidate in candidates:
            price_type_name, resolved_role = describe(candidate.onec_price_type_id)
            value = f"{candidate.pk}:{candidate.onec_id or ''}"
            rows.append(
                {
                    "candidate": candidate,
                    "value": value,
                    "checked": value == selected,
                    "legal_address": _company_legal_address(candidate),
                    "kpp": candidate.company.kpp if _has_company(candidate) else "",
                    "price_type_name": price_type_name,
                    "role_label": role_labels.get(resolved_role, "") if resolved_role else "",
                }
            )

        # Роль из 1С показывается только для чтения, когда она известна
        # заранее. При нескольких кандидатах она зависит от выбора, поэтому
        # выбор менеджера применяется лишь к контрагенту без роли по виду цен.
        linked_price_type_name, linked_role = describe(obj.onec_price_type_id) if is_linked else ("", None)
        if candidates:
            single_resolved = len(rows) == 1 and bool(rows[0]["role_label"])
            fixed_role_label = rows[0]["role_label"] if single_resolved else ""
            fixed_price_type = rows[0]["price_type_name"] if single_resolved else ""
            role_choice_needed = any(not row["role_label"] for row in rows)
        else:
            fixed_role_label = role_labels.get(linked_role, "") if linked_role else ""
            fixed_price_type = linked_price_type_name if linked_role else ""
            role_choice_needed = not linked_role

        return {
            **self.admin_site.each_context(request),
            "title": "Подтверждение заявки",
            "opts": self.opts,
            "target": obj,
            "mode": mode,
            "is_decision": mode == MODE_DECISION,
            "form": form,
            "candidate_rows": rows,
            "is_linked": is_linked,
            "linked_price_type_name": linked_price_type_name,
            "requires_without_1c": form.requires_without_1c,
            "fixed_role_label": fixed_role_label,
            "fixed_price_type": fixed_price_type,
            "role_choice_needed": role_choice_needed,
            "change_url": reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_change", args=[obj.pk]),
        }

    def _apply_verify_b2b(
        self, request: HttpRequest, obj: User, cleaned: dict[str, Any], change_url: str
    ) -> HttpResponseRedirect:
        try:
            result = verify_b2b_application(
                target_id=obj.pk,
                source_id=cleaned["source_id"],
                expected_onec_id=cleaned["expected_onec_id"],
                role=cleaned.get("role") or None,
                confirm_without_1c=bool(cleaned.get("confirm_without_1c")),
                actor=request.user if isinstance(request.user, User) else None,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except (VerificationError, LinkCandidateError) as exc:
            self.message_user(request, str(exc), level="error")
            return HttpResponseRedirect(request.get_full_path())

        user = result.user
        role_label = dict(User.ROLE_CHOICES).get(result.role_after, result.role_after)
        if result.mode == MODE_DECISION:
            text = f"Заявка {user.email or user.pk} подтверждена: роль «{role_label}»"
        else:
            text = f"Аккаунт {user.email or user.pk} связан с 1С: роль «{role_label}»"
        if result.linked:
            text += f", связан с контрагентом 1С (ID в 1С: {user.onec_id})."
        elif user.onec_id or user.onec_guid:
            text += f", привязка к 1С прежняя (ID в 1С: {user.onec_id or user.onec_guid})."
        else:
            text += ", без привязки к 1С."
        self.message_user(request, text, level="success")

        if result.linked:
            self._warn_customer_code_mismatch(request, result.source_customer_code, user.customer_code)
        elif not user.onec_id and not user.onec_guid:
            self.message_user(
                request,
                "Аккаунт не связан с 1С: контрагент будет создан в 1С при первом заказе.",
                level="warning",
            )
        return HttpResponseRedirect(change_url)

    def _apply_reject_b2b(self, request: HttpRequest, obj: User, change_url: str) -> HttpResponseRedirect:
        try:
            user = reject_b2b_application(
                target_id=obj.pk,
                actor=request.user if isinstance(request.user, User) else None,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )
        except VerificationError as exc:
            self.message_user(request, str(exc), level="error")
            return HttpResponseRedirect(request.get_full_path())

        self.message_user(request, f"Заявка {user.email or user.pk} отклонена.", level="warning")
        return HttpResponseRedirect(change_url)

    # Custom display methods

    @admin.display(description="Кандидат 1С", boolean=True)
    def has_1c_candidate(self, obj: User) -> bool:
        """Индикатор из аннотации changelist'а — не запрос на строку."""
        return bool(getattr(obj, "_has_1c_candidate", False))

    @admin.display(description="Подтвердить")
    def verify_b2b_link(self, obj: User) -> str:
        """
        Ссылка на страницу подтверждения — только у подходящих строк.

        Строится по полям строки и аннотации `_has_1c_candidate`, без
        запросов: та же аннотация несёт условие (б) — «верифицирован, не
        связан, есть кандидаты».
        """
        if obj.role not in User.B2B_ROLES or obj.is_superuser:
            return ""
        if not is_awaiting_decision(obj) and not getattr(obj, "_has_1c_candidate", False):
            return ""
        return format_html(
            '<a href="{}">Подтвердить</a>',
            reverse(f"admin:{self.opts.app_label}_{self.opts.model_name}_verify", args=[obj.pk]),
        )

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

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:  # type: ignore[override]
        readonly_fields = list(super().get_readonly_fields(request, obj))  # type: ignore[arg-type]
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
        self._warn_customer_code_mismatch(request, source_code, linked.customer_code)
        return HttpResponseRedirect(request.get_full_path())

    def _warn_customer_code_mismatch(
        self, request: HttpRequest, source_code: str | None, linked_code: str | None
    ) -> None:
        if source_code and linked_code and source_code != linked_code:
            # Код заявителя уже вшит в номера его заказов и сменён быть не может.
            # Расхождение с 1С не ошибка привязки, но менеджер обязан его увидеть:
            # номера заказов портала и код контрагента в 1С разойдутся навсегда.
            self.message_user(
                request,
                f"Код клиента расходится с 1С: у заявителя {linked_code}, "
                f"у контрагента {source_code}. Код заявителя не меняется — он уже "
                f"использован в номерах его заказов. Сверьте код в 1С вручную.",
                level="warning",
            )

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
        ip_address = get_client_ip(cast("Request", request))
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

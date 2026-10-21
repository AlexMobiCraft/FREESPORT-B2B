"""
Раздел руководителя `/supervisor/` — сотрудники (стори 42.7).

Урезанный `UserAdmin` на сайте `supervisor_site`: в выборке только сотрудники
(`is_staff`, не суперпользователь), карточка из белого списка полей без
привилегий, группа роли — выбором из «Менеджеров» и «Маркетинга».
Руководителей назначает только владелец в `/admin/`.

Меняет руководитель только управляемых сотрудников (`manageable_staff_q`):
не руководителей, без прямых прав и без групп вне трёх ролей. Остальных он
видит, но карточка у них только для чтения, а страница пароля и действия —
недоступны: иначе через сброс пароля можно было бы войти под учётной
записью с особыми правами.

Модуль импортируется из `UsersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/users/admin.py`.
"""

from __future__ import annotations

from typing import Any, cast

from django import forms
from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, Prefetch, Q, QuerySet
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import URLPattern

from apps.common.models import AuditLog, ManagerRoutingRule
from apps.users.admin import UserAdmin
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, MARKETING_GROUP, STAFF_ROLE_GROUPS, SUPERVISORS_GROUP
from freesport.admin_site import supervisor_site

# Группы, которые назначает руководитель. «Руководители» — только владелец в /admin/.
ASSIGNABLE_GROUPS = (MANAGERS_GROUP, MARKETING_GROUP)


def _memberships() -> QuerySet[Any]:
    return cast("QuerySet[Any]", User.groups.through._default_manager.filter(user_id=OuterRef("pk")))


def manageable_staff_q() -> Q:
    """
    Сотрудник, которого меняет руководитель: не в «Руководителях», без прямых
    прав (`user_permissions`) и без групп вне трёх ролей. Условия — через
    `Exists`, без JOIN по группам.
    """
    return (
        ~Q(Exists(_memberships().filter(group__name=SUPERVISORS_GROUP)))
        & ~Q(Exists(User.user_permissions.through._default_manager.filter(user_id=OuterRef("pk"))))
        & ~Q(Exists(_memberships().exclude(group__name__in=STAFF_ROLE_GROUPS)))
    )


def role_group_names(user: User) -> list[str]:
    """Группы ролей сотрудника; в списке — из `Prefetch`, без запроса на строку."""
    groups = getattr(user, "role_groups", None)
    if groups is None:
        groups = list(user.groups.filter(name__in=STAFF_ROLE_GROUPS).order_by("name"))
    return [group.name for group in groups]


def _rule_labels(rules: QuerySet[ManagerRoutingRule]) -> str:
    """Ключи правил для сообщения: код региона, страна или «резерв»."""
    labels = []
    for match_type, match_value in rules.order_by("match_type", "match_value").values_list("match_type", "match_value"):
        labels.append("резерв" if match_type == ManagerRoutingRule.MATCH_FALLBACK else match_value)
    return ", ".join(labels)


class StaffGroupFilter(admin.SimpleListFilter):
    """Группа роли сотрудника: три роли и «Без группы»."""

    title = "Группа роли"
    parameter_name = "role_group"
    WITHOUT = "none"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [(name, name) for name in STAFF_ROLE_GROUPS] + [(self.WITHOUT, "Без группы")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        value = self.value()
        if value is None:
            return queryset
        if value == self.WITHOUT:
            return queryset.filter(~Q(Exists(_memberships().filter(group__name__in=STAFF_ROLE_GROUPS))))
        if value in STAFF_ROLE_GROUPS:
            return queryset.filter(Exists(_memberships().filter(group__name=value)))
        raise IncorrectLookupParameters(f"Неизвестная группа: {value!r}")


def _role_group_field() -> forms.ChoiceField:
    return forms.ChoiceField(
        label="Группа роли",
        choices=[(name, name) for name in ASSIGNABLE_GROUPS],
        widget=forms.RadioSelect,
        required=True,
        help_text="Руководителей назначает владелец сайта.",
    )


def _clean_staff_email(form: forms.ModelForm[Any]) -> str:
    """Email сотрудника — без пробелов, в нижнем регистре и уникален без учёта регистра."""
    email = (form.cleaned_data.get("email") or "").strip().lower()
    duplicates = User.objects.filter(email__iexact=email)
    if form.instance.pk is not None:
        duplicates = duplicates.exclude(pk=form.instance.pk)
    if duplicates.exists():
        raise forms.ValidationError("Пользователь с таким email уже существует.")
    return email


class StaffCreationForm(UserCreationForm):
    """
    Создание сотрудника: email, имя, телефон, пароль дважды и группа роли.

    Пароль обязателен (`UserCreationForm`, без «пароль не задан» формы админки).
    Сотрудник получает `is_staff=True`; роль клиента не задаётся — по умолчанию
    `retail`: роль `admin` открыла бы оптовые цены. Группа назначается в
    `SupervisorStaffAdmin.save_related`, после сохранения записи.
    """

    role_group = _role_group_field()

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # В карточке только для чтения полей ввода нет.
        if "email" in self.fields:
            self.fields["email"].required = True

    def clean_email(self) -> str:
        return _clean_staff_email(self)

    def save(self, commit: bool = True) -> User:
        self.instance.is_staff = True
        return super().save(commit=commit)  # type: ignore[no-any-return]


class StaffChangeForm(UserChangeForm):
    """
    Карточка сотрудника: группа роли — «Менеджеры» или «Маркетинг».

    Перевод в «Маркетинг» сотрудника, у которого есть клиенты или правила
    регионов, запрещён: они остались бы за учётной записью, которую нельзя
    выбрать ответственным.
    """

    role_group = _role_group_field()

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ("email",)
        field_classes: dict[str, Any] = {}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # В карточке только для чтения полей ввода нет.
        if "email" in self.fields:
            self.fields["email"].required = True
        if self.instance.pk is not None:
            current = [name for name in role_group_names(self.instance) if name in ASSIGNABLE_GROUPS]
            if current:
                self.fields["role_group"].initial = current[0]

    def clean_email(self) -> str:
        return _clean_staff_email(self)

    def clean(self) -> dict[str, Any] | None:
        cleaned = super().clean()
        group = self.cleaned_data.get("role_group")
        if group == MARKETING_GROUP and "role_group" in self.changed_data and self.instance.pk is not None:
            clients = User.objects.filter(responsible_manager=self.instance).count()
            rules = ManagerRoutingRule.objects.filter(manager=self.instance)
            parts = []
            if clients:
                parts.append(f"клиенты ({clients})")
            if rules.exists():
                parts.append(f"правила регионов: {_rule_labels(rules)}")
            if parts:
                self.add_error(
                    "role_group",
                    f"У {self.instance.email} есть {' и '.join(parts)}. Замените менеджера в таблице регионов — "
                    "клиенты по правилу перейдут сами, — а оставшимся клиентам назначьте другого менеджера "
                    "в карточке.",
                )
        return cleaned


class SupervisorStaffAdmin(UserAdmin):
    """Сотрудники руководителя: создание, группа роли, блокировка, пароль."""

    form = StaffChangeForm
    add_form = StaffCreationForm
    view_on_site = False

    list_display = [
        "email",
        "full_name",
        "role_group",
        "is_active",
        "clients_count",
        "last_login",
        "created_at",
    ]
    list_filter = [StaffGroupFilter, "is_active"]
    search_fields = ["email", "first_name", "last_name"]
    list_select_related: Any = False
    actions = ["block_staff", "unblock_staff"]
    filter_horizontal: Any = ()
    inlines: Any = []

    # Белый список полей: новое поле User само в раздел не попадёт.
    fieldsets: Any = (
        ("Сотрудник", {"fields": ("email", "password", "first_name", "last_name", "phone")}),
        ("Роль", {"fields": ("role_group",)}),
        ("Статус", {"fields": ("is_active", "last_login", "created_at")}),
    )
    add_fieldsets: Any = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "first_name", "last_name", "phone", "password1", "password2", "role_group"),
            },
        ),
    )
    # Блокируют действия: они пишут журнал и предупреждают об оставшихся клиентах.
    readonly_fields: Any = ("is_active", "last_login", "created_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:  # type: ignore[override]
        # Без аннотации кандидатов 1С из UserAdmin: у сотрудников её нет.
        queryset = (
            super(UserAdmin, self)
            .get_queryset(request)
            .filter(is_staff=True, is_superuser=False)
            .annotate(_clients_count=Count("managed_clients"))
            .prefetch_related(
                Prefetch(
                    "groups",
                    queryset=Group.objects.filter(name__in=STAFF_ROLE_GROUPS).order_by("name"),
                    to_attr="role_groups",
                )
            )
        )
        return cast("QuerySet[User]", queryset)

    def get_urls(self) -> list[URLPattern]:
        # Без страницы подтверждения B2B: у сотрудников заявок нет.
        return super(UserAdmin, self).get_urls()

    def _get_obj_does_not_exist_redirect(self, request: HttpRequest, opts: Any, object_id: str) -> HttpResponse:
        # Суперпользователь и клиент неотличимы от несуществующей записи (как 42.4).
        raise Http404("Сотрудник не найден")

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        # Без кнопки подтверждения B2B из UserAdmin.change_view.
        return super(UserAdmin, self).change_view(request, object_id, form_url, extra_context)

    def get_fieldsets(self, request: HttpRequest, obj: User | None = None) -> Any:  # type: ignore[override]
        return self.add_fieldsets if obj is None else self.fieldsets

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:  # type: ignore[override]
        return list(self.readonly_fields) if obj is not None else []

    @staticmethod
    def _is_manageable(obj: User) -> bool:
        cached = getattr(obj, "_is_manageable", None)
        if cached is None:
            cached = User.objects.filter(pk=obj.pk).filter(manageable_staff_q()).exists()
            obj._is_manageable = cached  # type: ignore[attr-defined]
        return bool(cached)

    def has_change_permission(self, request: HttpRequest, obj: User | None = None) -> bool:  # type: ignore[override]
        # Руководителя, учётную запись с прямыми правами или чужой группой
        # меняет только владелец: карточка только для чтения, пароль — 403.
        if not super().has_change_permission(request, obj):
            return False
        return obj is None or self._is_manageable(obj)

    @admin.display(description="Группа роли")
    def role_group(self, obj: User) -> str:
        return ", ".join(role_group_names(obj)) or "—"

    @admin.display(description="Клиентов", ordering="_clients_count")
    def clients_count(self, obj: User) -> int:
        return int(getattr(obj, "_clients_count", 0))

    def _log(self, request: HttpRequest, action: str, obj: User, changes: dict[str, Any]) -> None:
        AuditLog.log_action(
            user=request.user,
            action=action,
            resource_type="User",
            resource_id=obj.pk,
            changes={"email": str(obj.email or ""), **changes},
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    def save_related(self, request: HttpRequest, form: ModelForm, formsets: Any, change: bool) -> None:
        super().save_related(request, form, formsets, change)
        obj = form.instance
        group = form.cleaned_data["role_group"]
        if not change:
            obj.groups.set([Group.objects.get(name=group)])
            self._log(request, "create_staff", obj, {"group": group})
        elif "role_group" in form.changed_data:
            old = form.fields["role_group"].initial
            obj.groups.set([Group.objects.get(name=group)])
            self._log(request, "change_staff_group", obj, {"old": old, "new": group})

    def _split_manageable(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        """Управляемые из выбранных; о пропущенных — сообщение."""
        pks = list(queryset.values_list("pk", flat=True))
        targets = User.objects.filter(pk__in=pks).filter(manageable_staff_q())
        skipped = len(pks) - targets.count()
        if skipped:
            self.message_user(
                request,
                f"Пропущено {skipped}: руководителей и учётные записи с особыми правами меняет только "
                "владелец сайта",
                level="warning",
            )
        return targets.order_by("pk")

    def _remaining_warning(self, user: User) -> str | None:
        """Что осталось за заблокированным: клиенты с ручным назначением и правила регионов."""
        manual = User.objects.filter(responsible_manager=user, responsible_manager_manual=True).count()
        rules = ManagerRoutingRule.objects.filter(manager=user)
        has_rules = rules.exists()
        if not manual and not has_rules:
            return None
        left, todo = [], []
        if manual:
            left.append(f"{manual} клиентов с ручным назначением")
            todo.append("назначьте клиентам другого менеджера в карточке")
        if has_rules:
            left.append(f"правила регионов: {_rule_labels(rules)}")
            todo.append("замените менеджера в таблице регионов")
        return f"У {user.email} остались {' и '.join(left)} — {' и '.join(todo)}"

    @admin.action(description="🚫 Заблокировать выбранных сотрудников", permissions=["change"])
    def block_staff(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in self._split_manageable(request, queryset).filter(is_active=True):
            groups = ", ".join(role_group_names(user))
            # Сигнал User переводит клиентов его правил на резерв (решение 17).
            # Действия списка Django в транзакцию не оборачивает: блокировка,
            # пересчёт и журнал — одной транзакцией на сотрудника (R42.7-1).
            with transaction.atomic():
                user.is_active = False
                user.save(update_fields=["is_active", "updated_at"])
                self._log(request, "block_staff", user, {"group": groups})
            count += 1
            warning = self._remaining_warning(user)
            if warning:
                self.message_user(request, warning, level="warning")
        if count:
            self.message_user(request, f"Заблокировано сотрудников: {count}", level="success")

    @admin.action(description="🔓 Разблокировать выбранных сотрудников", permissions=["change"])
    def unblock_staff(self, request: HttpRequest, queryset: QuerySet[User]) -> None:
        count = 0
        for user in self._split_manageable(request, queryset).filter(is_active=False):
            groups = ", ".join(role_group_names(user))
            # Клиенты его правил возвращаются к нему (решение 17), одной
            # транзакцией с журналом, как в block_staff.
            with transaction.atomic():
                user.is_active = True
                user.save(update_fields=["is_active", "updated_at"])
                self._log(request, "unblock_staff", user, {"group": groups})
            count += 1
        if count:
            self.message_user(request, f"Разблокировано сотрудников: {count}", level="success")


supervisor_site.register(User, SupervisorStaffAdmin)

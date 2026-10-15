"""
Раздел менеджера `/manager/` — клиенты, за которых отвечает сотрудник (стори 42.4).

Урезанный `UserAdmin` на сайте `manager_site`: только свои клиенты
(`scope_clients`), карточка из белого списка полей без служебных данных
интеграции и привилегий, на чужого клиента — 404. Действия и страницы
подтверждения B2B, привязки к 1С и смены пароля — общие с `/admin/`.

Модуль импортируется из `UsersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/users/admin.py`.
"""

from __future__ import annotations

from typing import Any, Iterator

from django.contrib import admin
from django.contrib.admin.utils import unquote
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.common.models import AuditLog
from apps.users.admin import AddressInline, CompanyInline, Has1CCandidateFilter, UserAdmin, activation_locked
from apps.users.models import User
from apps.users.staff_roles import staff_accounts_q
from freesport.admin_site import manager_site


def scope_clients(request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
    """
    Единственное правило видимости клиентов в разделе менеджера.

    Видны клиенты, у которых сотрудник — ответственный менеджер, минус
    учётные записи сотрудников (`staff_accounts_q()`): их ответственный
    мог остаться от времени, когда запись ещё была клиентской. Руководитель
    в 42.4 тоже видит только своих; снятие фильтра для него (стори 42.7)
    правится только здесь.
    """
    return queryset.filter(responsible_manager=request.user).exclude(staff_accounts_q())


class PortalAccountFilter(admin.SimpleListFilter):
    """
    «Учётная запись на портале»: по умолчанию записи `unregistered` скрыты.

    Это контрагенты 1С без аккаунта на сайте (на проде их 4600+): они
    заполняют список, но менеджеру нечего с ними делать, пока клиент не
    зарегистрировался. Показать их — значение «Нет» или «Все».
    """

    title = "Учётная запись на портале"
    parameter_name = "portal_account"

    def __init__(self, request: HttpRequest, params: dict[str, Any], model: Any, model_admin: Any) -> None:
        super().__init__(request, params, model, model_admin)
        # Фильтр роли «Не зарегистрирован» без исключения по умолчанию всегда
        # давал бы пустой список: при нём записи без аккаунта видны, как во «Все».
        self.role_is_unregistered = request.GET.get("role__exact") == User.ROLE_UNREGISTERED

    def effective_value(self) -> str:
        value = self.value()
        if value is None:
            return "all" if self.role_is_unregistered else "yes"
        return value

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [("no", "Нет"), ("all", "Все")]

    def choices(self, changelist: ChangeList) -> Iterator[dict[str, Any]]:
        # Пункт по умолчанию — «Есть» без параметра; штатного «Все» с тем же
        # значением нет, иначе в фильтре было бы два пункта на одно состояние.
        # При фильтре роли «Не зарегистрирован» отсутствие параметра значит
        # «Все», поэтому «Есть» передаётся явным значением yes.
        value = self.effective_value()
        if self.role_is_unregistered:
            have_query = changelist.get_query_string({self.parameter_name: "yes"})
        else:
            have_query = changelist.get_query_string(remove=[self.parameter_name])
        yield {
            "selected": value not in ("no", "all"),
            "query_string": have_query,
            "display": "Есть",
        }
        for lookup, title in self.lookup_choices:
            yield {
                "selected": value == lookup,
                "query_string": changelist.get_query_string({self.parameter_name: lookup}),
                "display": title,
            }

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        value = self.effective_value()
        if value == "all":
            return queryset
        if value == "no":
            return queryset.filter(role=User.ROLE_UNREGISTERED)
        return queryset.exclude(role=User.ROLE_UNREGISTERED)


class ManagerClientAdmin(UserAdmin):
    """Клиенты менеджера: только свои, без служебных полей, без добавления и удаления."""

    list_display = [
        "email",
        "full_name",
        "company_name",
        "tax_id",
        "customer_code",
        "role_display",
        "verification_status_display",
        "has_1c_candidate",
        "verify_b2b_link",
        "phone",
        "created_at",
        "is_active",
    ]
    list_filter = ["role", "verification_status", Has1CCandidateFilter, "is_active", PortalAccountFilter]
    actions = ["approve_b2b_users", "reject_b2b_users", "link_1c_customer", "block_users", "unblock_users"]
    # Полей групп и прав в карточке раздела нет.
    filter_horizontal: Any = ()
    inlines = [CompanyInline, AddressInline]

    # Белый список полей: новое поле User само в раздел не попадёт.
    fieldsets: Any = (
        ("Контакты", {"fields": ("email", "password", "first_name", "last_name", "phone")}),
        ("B2B данные", {"fields": ("company_name", "tax_id", "country", "company_legal_address", "customer_code")}),
        ("Статус", {"fields": ("role", "verification_status", "is_verified", "is_active")}),
        ("1С и ответственный", {"fields": ("linked_to_1c", "onec_price_type_name", "responsible_manager_display")}),
        ("Даты", {"fields": ("created_at", "last_login"), "classes": ("collapse",)}),
    )
    # Статус верификации меняют только страница подтверждения и действия (они
    # пишут AuditLog); код клиента вшит в номера заказов и сверяется с 1С.
    readonly_fields: Any = (
        "customer_code",
        "role",
        "verification_status",
        "is_verified",
        "linked_to_1c",
        "onec_price_type_name",
        "responsible_manager_display",
        "company_legal_address",
        "created_at",
        "last_login",
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[User]:  # type: ignore[override]
        return scope_clients(request, super().get_queryset(request))

    def _get_obj_does_not_exist_redirect(self, request: HttpRequest, opts: Any, object_id: str) -> HttpResponse:
        # Штатный ответ на объект вне queryset — 302 на главную с «не существует».
        # В разделе чужой клиент неотличим от несуществующего: 404 на карточке,
        # истории и странице подтверждения. Метод приватный (Django 5.2), его
        # контракт страхуют тесты AC3 стори 42.4.
        raise Http404("Клиент не найден")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: User | None = None) -> bool:  # type: ignore[override]
        return False

    def get_fieldsets(self, request: HttpRequest, obj: User | None = None) -> Any:  # type: ignore[override]
        # Без логики UserAdmin: привилегий и кандидатов 1С в белом списке нет,
        # а find_link_candidates на каждом открытии карточки — лишний запрос.
        return self.fieldsets

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:  # type: ignore[override]
        fields = list(self.readonly_fields)
        # Флаг «активен» у заявки до подтверждения и у записи 1С — в обход
        # guard'а unblock_users: включённый у ожидающей заявки, он пережил бы
        # последующий отказ (R42.4-32). Им флаг меняют решение по заявке и
        # действие «Заблокировать».
        if obj is not None and activation_locked(obj):
            fields.append("is_active")
        return fields

    @admin.display(description="Связан с 1С", boolean=True)
    def linked_to_1c(self, obj: User) -> bool:
        return bool(obj.onec_id or obj.onec_guid)

    @admin.display(description="Ответственный менеджер")
    def responsible_manager_display(self, obj: User) -> str:
        # Текст без ссылки: readonly-FK Django рисует ссылкой на карточку
        # менеджера в этом же разделе, а менеджер — сотрудник вне scope_clients,
        # то есть ссылка вела бы в 404.
        manager = obj.responsible_manager
        if manager is None:
            return "—"
        name = manager.full_name
        return f"{name} ({manager.email})" if name else str(manager.email or "—")

    def changelist_view(self, request: HttpRequest, extra_context: dict[str, Any] | None = None) -> HttpResponse:
        extra_context = {**(extra_context or {}), "title": "Клиенты"}
        return super().changelist_view(request, extra_context)

    # Запись над клиентом: строка блокируется до чтения объекта.
    #
    # Иначе клиента могли передать другому менеджеру (или импорт 1С обновить
    # скрытые поля) между чтением и записью: полное save() устаревшего объекта
    # вернуло бы прежнего ответственного и затёрло импорт, а сервис записал бы
    # действие над уже чужим клиентом. Под блокировкой Django читает свежий
    # объект через get_queryset: переданный клиент — 404, а передача, начатая
    # посреди записи, ждёт конца транзакции и применяется после.

    @staticmethod
    def _to_pk(object_id: Any) -> Any:
        """pk из id адреса; None — невалидный id (get_object вернёт None, вью ответит 404)."""
        try:
            return User._meta.pk.to_python(unquote(str(object_id)))  # type: ignore[union-attr]
        except (ValidationError, ValueError):
            return None

    def _lock_rows(self, *object_ids: Any) -> None:
        """Блокирует строки пользователей по возрастанию pk — порядок пересчёта ответственных и привязки к 1С."""
        pks = {pk for pk in map(self._to_pk, object_ids) if pk is not None}
        if pks:
            list(User.objects.select_for_update().filter(pk__in=pks).order_by("pk").values_list("pk", flat=True))

    def _lock_client(self, request: HttpRequest, object_id: str) -> None:
        """
        Блокирует строку клиента, если запрос вправе его менять.

        Без права change блокировки нет: вью ответит 403. Цель берётся только
        из выборки раздела: строку чужого клиента запрос не трогает и не ждёт,
        пока её отпустит чужая транзакция. Передача, начатая после блокировки,
        ждёт конца транзакции.

        Пустая блокировка — сразу 404, а не продолжение вью: клиента могли
        передать менеджеру уже после неё, и get_object прочитал бы его строку,
        а save() записал бы её, так и не заблокировав.
        """
        if not self.has_change_permission(request):
            return
        pk = self._to_pk(object_id)
        scope = self.get_queryset(request).select_for_update(of=("self",))
        if pk is None or not list(scope.filter(pk=pk).values_list("pk", flat=True)):
            raise Http404("Клиент не найден")

    @staticmethod
    def _executed_action(request: HttpRequest) -> str | None:
        """
        Действие, которое выполнит ModelAdmin.response_action.

        Полей action в форме списка два (над и под таблицей), Django берёт
        значение по index, а при выходе за границы — последнее (так читает
        QueryDict). Решение о блокировке принимается по тому же значению.
        """
        actions = request.POST.getlist("action")
        try:
            index = int(request.POST.get("index", 0))
        except ValueError:
            index = 0
        try:
            return actions[index]
        except IndexError:
            return actions[-1] if actions else None

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        if request.method != "POST":
            return super().change_view(request, object_id, form_url, extra_context)
        # Блокировка держится до конца запроса, включая инлайны.
        with transaction.atomic():
            self._lock_client(request, object_id)
            return super().change_view(request, object_id, form_url, extra_context)

    def user_change_password(self, request: HttpRequest, id: str, form_url: str = "") -> HttpResponse:
        if request.method != "POST":
            return super().user_change_password(request, id, form_url)
        with transaction.atomic():
            self._lock_client(request, id)
            return super().user_change_password(request, id, form_url)

    def verify_b2b_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        if request.method != "POST":
            return super().verify_b2b_view(request, object_id)
        # Порядок прежний: сервис подтверждения тоже сначала блокирует заявку.
        with transaction.atomic():
            self._lock_client(request, object_id)
            return super().verify_b2b_view(request, object_id)

    def _apply_link_1c_customer(
        self, request: HttpRequest, target: User, candidates: list[User]
    ) -> HttpResponseRedirect:
        # Цель прочитана действием без блокировки (см. response_action) и
        # блокируется вместе с источником по возрастанию pk, как в сервисе.
        # Источник — только из показанных кандидатов: чужую строку по
        # подделанному pk не блокируем, сервис такой выбор всё равно отклонит.
        source_pk = (request.POST.get("candidate") or "").partition(":")[0]
        source_pks = [candidate.pk for candidate in candidates if str(candidate.pk) == source_pk]
        with transaction.atomic():
            self._lock_link_rows(request, target, source_pks)
            return super()._apply_link_1c_customer(request, target, candidates)

    def _lock_link_rows(self, request: HttpRequest, target: User, source_pks: list[Any]) -> None:
        """
        Блокирует цель привязки и источник 1С по возрастанию pk.

        Цель захватывается только из выборки раздела, тем же запросом, что и
        блокирует: уже переданного клиента запрос не трогает и его строку, даже
        занятую чужой транзакцией, не ждёт — сразу 404, как в _lock_client.
        Передача, начатая после захвата, ждёт конца транзакции. Источник
        выборкой не ограничен: запись 1С законно лежит вне её.

        Принадлежность цели проверяется ещё и до захвата строк, без блокировки:
        источник с меньшим pk захватывается раньше цели, и без этой проверки
        запрос к уже переданному клиенту ждал бы занятый источник.
        """
        if not self.get_queryset(request).filter(pk=target.pk).exists():
            raise Http404("Клиент не найден")
        scope = self.get_queryset(request).select_for_update(of=("self",))
        for pk in sorted({target.pk, *source_pks}):
            if pk != target.pk:
                self._lock_rows(pk)
            elif not list(scope.filter(pk=pk).values_list("pk", flat=True)):
                raise Http404("Клиент не найден")

    def response_action(self, request: HttpRequest, queryset: QuerySet[User]) -> HttpResponse | None:
        # Выбранные строки читаются под блокировкой в одной транзакции с записью:
        # клиент, переданный другому менеджеру до чтения, в выборку не попадёт,
        # а передать его, пока действие пишет, нельзя. Порядок блокировки — по pk,
        # как у пересчёта ответственных. Привязка к 1С блокирует цель вместе с
        # источником в _apply_link_1c_customer — блокировка одной цели здесь
        # перевернула бы порядок по pk.
        if self._executed_action(request) == "link_1c_customer":
            return super().response_action(request, queryset)
        with transaction.atomic():
            return super().response_action(request, queryset.select_for_update(of=("self",)).order_by("pk"))

    def save_model(  # type: ignore[override]
        self, request: HttpRequest, obj: User, form: ModelForm, change: bool
    ) -> None:
        super().save_model(request, obj, form, change)  # type: ignore[arg-type]
        # Блокировка и разблокировка флагом в карточке — тоже действие для журнала.
        if change and "is_active" in form.changed_data:
            AuditLog.log_action(
                user=request.user,
                action="unblock_user" if obj.is_active else "block_user",
                resource_type="User",
                resource_id=obj.pk,
                changes={
                    "email": str(obj.email or ""),
                    "role": obj.role,
                    "blocked": not obj.is_active,
                    "source": "card",
                },
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get("HTTP_USER_AGENT", ""),
            )

    def response_change(self, request: HttpRequest, obj: User) -> HttpResponse:  # type: ignore[override]
        # Смена ИНН или страны переназначает ответственного (хук 42.2), и клиент
        # может уйти к другому менеджеру. Штатный редирект на его карточку
        # ответил бы 404 — вместо этого список с объяснением.
        if not self.get_queryset(request).filter(pk=obj.pk).exists():
            manager = obj.responsible_manager
            self.message_user(
                request,
                f"Клиент {obj.email or obj.pk} передан менеджеру "
                f"{manager.email if manager else 'без ответственного'} по правилу региона.",
                level="warning",
            )
            return HttpResponseRedirect(reverse(f"{self.admin_site.name}:users_user_changelist"))
        return super().response_change(request, obj)  # type: ignore[arg-type]


manager_site.register(User, ManagerClientAdmin)

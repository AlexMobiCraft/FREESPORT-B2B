"""
Раздел менеджера `/manager/` — клиенты, за которых отвечает сотрудник (стори 42.4).

Урезанный `UserAdmin` на сайте `manager_site`: только свои клиенты
(`scope_clients`), карточка из белого списка полей без служебных данных
интеграции и привилегий, на чужого клиента — 404. Действия и страницы
подтверждения B2B, привязки к 1С и смены пароля — общие с `/admin/`.

Роль правится в карточке только у верифицированного B2B-клиента (FR-42-13):
первичное назначение — по-прежнему на странице подтверждения, а импорт 1С
вправе вернуть роль по виду цен соглашения.

Руководитель (стори 42.7) видит всех клиентов, колонку и фильтр
«Ответственный менеджер» и назначает ответственного вручную в карточке.
Фильтр «Заказы» (стори 42.8) — тоже только у руководителя: на него ведёт
число «Верифицированы, но без заказов» сводки `/supervisor/summary/`.

Модуль импортируется из `UsersConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/users/admin.py`.
"""

from __future__ import annotations

from typing import Any, Iterator

from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.utils import unquote
from django.contrib.admin.views.main import ChangeList
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Exists, OuterRef, QuerySet
from django.forms import ModelForm
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse

from apps.common.models import AuditLog
from apps.orders.models import Order
from apps.users.admin import AddressInline, CompanyInline, Has1CCandidateFilter, UserAdmin, activation_locked
from apps.users.models import User
from apps.users.staff_roles import is_supervisor, manager_label, staff_accounts_q
from freesport.admin_site import manager_site

# Выбор роли в карточке: служебные роли не назначаются ни формой, ни подделанным POST.
ASSIGNABLE_ROLE_CHOICES = [
    (role, label) for role, label in User.ROLE_CHOICES if role not in ("admin", User.ROLE_UNREGISTERED)
]
ROLE_1C_HINT = "Клиент связан с 1С: обмен может вернуть роль по виду цен соглашения."


def scope_clients(request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
    """
    Единственное правило видимости клиентов в разделе менеджера.

    Видны клиенты, у которых сотрудник — ответственный менеджер, минус
    учётные записи сотрудников (`staff_accounts_q()`): их ответственный
    мог остаться от времени, когда запись ещё была клиентской. Руководитель
    видит всех клиентов (стори 42.7) — тоже без учётных записей сотрудников.
    """
    if is_supervisor(request):
        return queryset.exclude(staff_accounts_q())
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


class ResponsibleManagerFilter(admin.SimpleListFilter):
    """
    «Ответственный менеджер» в списке клиентов руководителя (стори 42.7).

    Варианты — менеджеры, у которых в выборке раздела есть клиенты, в том
    числе заблокированные и выведенные из групп: так руководитель находит
    клиентов уволенного. Подпись «ФИО (email)», а не `str(user)` —
    `RelatedOnlyFieldListFilter` подписал бы «email (Розничный покупатель)».
    """

    title = "Ответственный менеджер"
    parameter_name = "responsible"
    WITHOUT = "none"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        managers = User.objects.filter(
            pk__in=scope_clients(request, User.objects.all()).values("responsible_manager")
        ).order_by("last_name", "first_name", "email")
        choices = []
        for manager in managers:
            label = manager_label(manager)
            if not manager.is_active:
                label += " — заблокирован"
            choices.append((str(manager.pk), label))
        choices.append((self.WITHOUT, "Без ответственного"))
        return choices

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        value = self.value()
        if value is None:
            return queryset
        if value == self.WITHOUT:
            return queryset.filter(responsible_manager__isnull=True)
        try:
            manager_id = int(value)
        except (TypeError, ValueError):
            raise IncorrectLookupParameters(f"Некорректный идентификатор менеджера: {value!r}")
        return queryset.filter(responsible_manager_id=manager_id)


def client_has_orders() -> Exists:
    """
    У клиента есть хотя бы один заказ — любой: мастер и его субзаказы принадлежат
    одному клиенту. Одно выражение на фильтр «Заказы» и сводку руководителя.
    """
    return Exists(Order.objects.filter(user=OuterRef("pk")))


def role_is_editable(obj: User | None) -> bool:
    """
    Роль правится только у верифицированного B2B-клиента.

    Розничному клиенту карточка B2B-роль не выдаёт, запись 1С и незавершённая
    заявка получают её на странице подтверждения. `is_verified` проверяется
    отдельно от статуса: без него цены остаются розничными и смена роли их не
    изменит (`resolve_pricing_role`). Решение принимается
    один раз на объект: `form.is_valid()` пишет выбранную роль в этот же
    объект, и при ошибке в другом поле выбор «Розница» убрал бы поле из
    перерисованной формы, а следующий POST упал бы на обязательном поле.
    """
    if obj is None:
        return False
    if not hasattr(obj, "_role_is_editable"):
        obj._role_is_editable = (  # type: ignore[attr-defined]
            obj.role in User.B2B_ROLES and not activation_locked(obj) and obj.is_verified
        )
    return bool(obj._role_is_editable)  # type: ignore[attr-defined]


class ClientOrdersFilter(admin.SimpleListFilter):
    """«Заказы» в списке клиентов руководителя (стори 42.8): есть ли у клиента заказы."""

    title = "Заказы"
    parameter_name = "has_orders"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[str, str]]:
        return [("yes", "Есть"), ("no", "Нет")]

    def queryset(self, request: HttpRequest, queryset: QuerySet[User]) -> QuerySet[User]:
        value = self.value()
        if value is None:
            return queryset
        if value == "yes":
            return queryset.filter(client_has_orders())
        if value == "no":
            return queryset.filter(~client_has_orders())
        raise IncorrectLookupParameters(f"Некорректное значение фильтра «Заказы»: {value!r}")


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
    # Роль здесь не указана: её правимость зависит от клиента (`role_is_editable`).
    readonly_fields: Any = (
        "customer_code",
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

    def get_list_display(self, request: HttpRequest) -> list[Any]:
        fields = list(super().get_list_display(request))
        # Руководитель видит клиентов всех менеджеров — без колонки не понять, чей клиент.
        if is_supervisor(request):
            fields.insert(fields.index("customer_code") + 1, "responsible_manager_display")
        return fields

    def get_list_filter(self, request: HttpRequest) -> list[Any]:
        filters = list(super().get_list_filter(request))
        if is_supervisor(request):
            filters += [ResponsibleManagerFilter, ClientOrdersFilter]
        return filters

    def get_list_select_related(self, request: HttpRequest) -> Any:
        # Колонка ответственного иначе читала бы менеджера запросом на строку.
        if is_supervisor(request):
            return ["company", "responsible_manager"]
        return super().get_list_select_related(request)

    def get_fieldsets(self, request: HttpRequest, obj: User | None = None) -> Any:  # type: ignore[override]
        # Без логики UserAdmin: привилегий и кандидатов 1С в белом списке нет,
        # а find_link_candidates на каждом открытии карточки — лишний запрос.
        if not is_supervisor(request):
            return self.fieldsets
        # Руководитель назначает ответственного вручную (стори 42.7): вместо
        # текста — выбор менеджера и флажок «Назначен вручную».
        editable = ("responsible_manager", "responsible_manager_manual")
        return tuple(
            (
                title,
                {
                    **options,
                    "fields": tuple(
                        name
                        for field in options["fields"]
                        for name in (editable if field == "responsible_manager_display" else (field,))
                    ),
                },
            )
            for title, options in self.fieldsets
        )

    def get_form(  # type: ignore[override]
        self, request: HttpRequest, obj: User | None = None, change: bool = False, **kwargs: Any
    ) -> Any:
        form = super().get_form(request, obj, change=change, **kwargs)
        field = form.base_fields.get("responsible_manager")
        if field is not None:
            # Ссылки «изменить/посмотреть» у выбора вели бы на карточку
            # менеджера в этом разделе, а сотрудник вне scope_clients — 404.
            widget = field.widget
            for flag in ("can_add_related", "can_change_related", "can_delete_related", "can_view_related"):
                if hasattr(widget, flag):
                    setattr(widget, flag, False)
        # Поля нет при роли только для чтения и у сотрудника без права change.
        role_field = form.base_fields.get("role")
        if role_field is not None and obj is not None:
            role_field.choices = ASSIGNABLE_ROLE_CHOICES
            # «Изменено» — от роли, увиденной сотрудником, а не от свежей строки:
            # иначе правка телефона в устаревшей карточке откатила бы роль импорта.
            role_field.show_hidden_initial = True
            # Поля могло не быть в открытой форме (карточка была только для
            # чтения, заявку подтвердили позже). Пустое значение — текущая роль,
            # и при сохранении, и в перерисовке: иначе select без выбранного
            # значения показал бы «Розницу», и повторное сохранение понизило бы клиента.
            role_field.required = False
            role_field.empty_value = obj.role
            role_field.bound_data = lambda data, initial: data or initial
            if self.linked_to_1c(obj):
                role_field.help_text = ROLE_1C_HINT
        return form

    def get_readonly_fields(self, request: HttpRequest, obj: User | None = None) -> list[str]:  # type: ignore[override]
        fields = list(self.readonly_fields)
        if not role_is_editable(obj):
            fields.append("role")
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
        # Выбранный руководителем менеджер — всегда ручное назначение: смена
        # ИНН и правил региона его больше не уводят (стори 42.7).
        manager_changed = "responsible_manager" in form.changed_data
        if manager_changed:
            obj.responsible_manager_manual = True
        # Сотрудник роль не менял: остаётся та, что в строке, а не из устаревшей формы.
        if "role" in form.fields and "role" not in form.changed_data:
            obj.role = form.initial["role"]
        super().save_model(request, obj, form, change)  # type: ignore[arg-type]
        if change and (manager_changed or "responsible_manager_manual" in form.changed_data):
            self._log_responsible_assignment(request, obj, form.initial.get("responsible_manager"))
        # Сравнение со строкой: при устаревшей форме выбор мог совпасть с ней.
        if change and "role" in form.changed_data and obj.role != form.initial.get("role"):
            self._log_role_change(request, obj, form.initial.get("role"))
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

    def _log_role_change(self, request: HttpRequest, obj: User, old_role: Any) -> None:
        """Журнал смены роли в карточке: «было» — значение формы, прочитанное под блокировкой строки."""
        AuditLog.log_action(
            user=request.user,
            action="change_user_role",
            resource_type="User",
            resource_id=obj.pk,
            changes={"email": str(obj.email or ""), "old": old_role, "new": obj.role, "source": "card"},
            ip_address=self._get_client_ip(request),
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    def _log_responsible_assignment(self, request: HttpRequest, obj: User, old_manager_id: Any) -> None:
        """
        Журнал ручного назначения в карточке (стори 42.7).

        «Было» — значение формы, прочитанное под блокировкой строки в
        `change_view`; «стало» — после `save()`: снятый флажок возвращает
        назначение по правилу региона прямо в `User.save`.
        """
        old_email = None
        if old_manager_id is not None:
            old_email = User.objects.filter(pk=old_manager_id).values_list("email", flat=True).first()
        new_manager = obj.responsible_manager
        AuditLog.log_action(
            user=request.user,
            action="assign_responsible_manager",
            resource_type="User",
            resource_id=obj.pk,
            changes={
                "email": str(obj.email or ""),
                "old": str(old_email) if old_email else None,
                "new": str(new_manager.email) if new_manager is not None else None,
                "manual": obj.responsible_manager_manual,
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

"""
Раздел руководителя `/supervisor/` — правила регионов и получатели уведомлений (стори 42.7).

Правила регионов — родительский `ManagerRoutingRuleAdmin` (колонка «Регион»,
блок «Не распределены»); пересчёт клиентов при смене менеджера, ключа или
активности делает сигнал правила (стори 42.2). Своё — запись каждого
изменения правила в `AuditLog`. Получатели уведомлений — родительский
`NotificationRecipientAdmin` как есть.

Модуль импортируется из `CommonConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/common/admin.py`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from django.db import transaction
from django.db.models import QuerySet
from django.forms import ModelForm
from django.http import HttpRequest

from apps.common.admin import ManagerRoutingRuleAdmin, NotificationRecipientAdmin
from apps.common.models import AuditLog, ManagerRoutingRule, NotificationRecipient
from apps.common.utils.consent_audit import get_client_ip
from freesport.admin_site import supervisor_site

if TYPE_CHECKING:
    from rest_framework.request import Request

# Поля правила в журнале: от первых четырёх зависит ответственный
# (`RULE_STATE_FIELDS` сервиса 42.2), от адреса — письмо о регистрации.
LOGGED_RULE_FIELDS = ("match_type", "match_value", "is_active", "manager_id", "manager_email")


def _rule_state(rule: ManagerRoutingRule) -> dict[str, Any]:
    return {field: getattr(rule, field) for field in LOGGED_RULE_FIELDS}


def _changed_fields(old: dict[str, Any] | None, new: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    """Изменившиеся поля правила: `{имя: {old, new}}`; нет состояния — значения `None`."""
    changed = {}
    for field in LOGGED_RULE_FIELDS:
        before = old.get(field) if old else None
        after = new.get(field) if new else None
        if before != after:
            changed[field] = {"old": before, "new": after}
    return changed


class SupervisorRoutingRuleAdmin(ManagerRoutingRuleAdmin):
    """Таблица регионов руководителя: родительский класс плюс журнал изменений."""

    view_on_site = False

    def _log(
        self, request: HttpRequest, rule_id: Any, operation: str, rule: str, fields: dict[str, dict[str, Any]]
    ) -> None:
        ip_address = get_client_ip(cast("Request", request))
        AuditLog.log_action(
            user=request.user,
            action="change_routing_rule",
            resource_type="ManagerRoutingRule",
            resource_id=rule_id,
            changes={"operation": operation, "rule": rule, "fields": fields},
            ip_address="0.0.0.0" if ip_address == "unknown" else ip_address,
            user_agent=request.META.get("HTTP_USER_AGENT", ""),
        )

    def save_model(self, request: HttpRequest, obj: ManagerRoutingRule, form: ModelForm, change: bool) -> None:
        # «Было» — из БД до сохранения, как у сигнала пересчёта: строка
        # list_editable и карточка сохраняются одним путём.
        old = ManagerRoutingRule.objects.filter(pk=obj.pk).values(*LOGGED_RULE_FIELDS).first() if change else None
        super().save_model(request, obj, form, change)
        fields = _changed_fields(old, _rule_state(obj))
        if change and not fields:
            return
        self._log(request, obj.pk, "update" if change else "create", str(obj), fields)

    def delete_model(self, request: HttpRequest, obj: ManagerRoutingRule) -> None:
        rule_id, rule, state = obj.pk, str(obj), _rule_state(obj)
        super().delete_model(request, obj)
        self._log(request, rule_id, "delete", rule, _changed_fields(state, None))

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[ManagerRoutingRule]) -> None:
        # «Удалить выбранные» — одна запись журнала на правило, как у карточки.
        # Действие Django в транзакцию не оборачивает (карточку — оборачивает):
        # удаление, пересчёт клиентов сигналом и журнал — одной транзакцией.
        with transaction.atomic():
            rules = [(rule.pk, str(rule), _rule_state(rule)) for rule in queryset.select_related("manager")]
            super().delete_queryset(request, queryset)
            for rule_id, rule, state in rules:
                self._log(request, rule_id, "delete", rule, _changed_fields(state, None))


NEW_ORDERS_FLAG_HINT = (
    "Выключение действует только на общий список получателей. Ответственный менеджер "
    "клиента получает письмо о каждом новом заказе своего клиента независимо от флага."
)


class SupervisorNotificationRecipientAdmin(NotificationRecipientAdmin):
    view_on_site = False

    def formfield_for_dbfield(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        # Подсказка в форме, а не `help_text` модели: он дал бы AlterField и миграцию.
        if db_field.name == "notify_new_orders":
            kwargs["help_text"] = NEW_ORDERS_FLAG_HINT
        return super().formfield_for_dbfield(db_field, request, **kwargs)


supervisor_site.register(ManagerRoutingRule, SupervisorRoutingRuleAdmin)
supervisor_site.register(NotificationRecipient, SupervisorNotificationRecipientAdmin)

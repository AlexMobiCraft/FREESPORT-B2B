"""
Раздел руководителя `/supervisor/` — бонусная программа (стори 42.7).

Настройки программы руководитель правит, но не создаёт и не удаляет: запись
одна. Операции бонусов — только просмотр (у группы одно право
`view_bonustransaction`). Ссылки родительского журнала ведут в закрытую
`/admin/` (`order_link`) или в раздел сотрудников, где тренер-клиент — 404
(readonly-FK `user`, `order`, `created_by`), поэтому карточка и список
показывают их текстом.

Модуль импортируется из `BonusesConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/bonuses/admin.py`.
"""

from __future__ import annotations

from typing import Any

from django.contrib import admin
from django.http import HttpRequest

from apps.bonuses.admin import BonusProgramSettingsAdmin, BonusTransactionAdmin
from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from freesport.admin_site import supervisor_site

# Поля карточки операции: display-методы и простые поля, без readonly-FK.
TRANSACTION_FIELDS = (
    "created_at",
    "trainer",
    "transaction_type",
    "amount",
    "order_number",
    "percent_applied",
    "base_amount",
    "comment",
    "created_by_display",
)


class SupervisorBonusSettingsAdmin(BonusProgramSettingsAdmin):
    view_on_site = False

    def has_add_permission(self, request: HttpRequest) -> bool:
        # Родитель разрешает добавление любому, пока записи нет, — без проверки прав.
        return False


class SupervisorBonusTransactionAdmin(BonusTransactionAdmin):
    view_on_site = False

    @admin.display(description="Заказ")
    def order_link(self, obj: BonusTransaction) -> str:
        # Текстом: родительская ссылка ведёт в /admin/, а заказов в разделе нет.
        return obj.order_display or "—"

    @admin.display(description="Заказ")
    def order_number(self, obj: BonusTransaction) -> str:
        return obj.order_display or "—"

    @admin.display(description="Создал")
    def created_by_display(self, obj: BonusTransaction) -> str:
        author = obj.created_by
        return str(author.email) if author is not None and author.email else "—"

    def get_fields(self, request: HttpRequest, obj: BonusTransaction | None = None) -> Any:
        return TRANSACTION_FIELDS

    def get_readonly_fields(self, request: HttpRequest, obj: BonusTransaction | None = None) -> tuple[str, ...]:
        return TRANSACTION_FIELDS

    # Только просмотр — явно, на случай если группе позже выдадут права.
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: BonusTransaction | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: BonusTransaction | None = None) -> bool:
        return False


supervisor_site.register(BonusProgramSettings, SupervisorBonusSettingsAdmin)
supervisor_site.register(BonusTransaction, SupervisorBonusTransactionAdmin)

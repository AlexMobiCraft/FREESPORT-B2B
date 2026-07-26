"""Админка бонусной программы.

История операций защищена от правок: начисления доступны только на чтение,
удаление запрещено для всех типов. Ошибочное начисление компенсируется
операцией «Списание», а не удалением — тренер должен видеть и начисление,
и исправление.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.admin.options import IncorrectLookupParameters
from django.db.models import DecimalField, OuterRef, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest
from django.urls import reverse
from django.utils.html import format_html

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.services.accrual import TRAINER_ROLE, get_balance


@admin.register(BonusProgramSettings)
class BonusProgramSettingsAdmin(admin.ModelAdmin):
    """Singleton-админка настроек программы."""

    list_display = ("__str__", "accrual_status", "program_start_at", "updated_at")
    fields = ("is_active", "percent", "accrual_status", "program_start_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Вторую запись настроек создать нельзя."""
        return not BonusProgramSettings.objects.exists()

    def has_delete_permission(self, request: HttpRequest, obj: BonusProgramSettings | None = None) -> bool:
        """Настройки программы не удаляются."""
        return False


class TrainerFilter(admin.SimpleListFilter):
    """Фильтр по тренеру — только те, у кого есть операции."""

    title = "Тренер"
    parameter_name = "trainer"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[Any, str]]:
        rows = (
            BonusTransaction.objects.filter(user__role=TRAINER_ROLE)
            .values_list("user_id", "user__email")
            .distinct()
            .order_by("user__email")
        )
        return [(user_id, email or f"ID {user_id}") for user_id, email in rows]

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet:
        value = self.value()
        if not value:
            return queryset
        try:
            user_id = int(value)
        except (TypeError, ValueError):
            # Произвольное значение в ?trainer= не должно ронять changelist
            raise IncorrectLookupParameters(f"Некорректный идентификатор тренера: {value!r}")
        return queryset.filter(user_id=user_id)


class ManualBonusTransactionForm(forms.ModelForm):
    """Форма ручной операции: менеджер вводит положительную сумму.

    Знак проставляет модель — здесь только выплаты и списания,
    начисления создаются автоматически.
    """

    class Meta:
        model = BonusTransaction
        fields = ("user", "transaction_type", "amount", "comment")

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        # Начисления и операции удалённых тренеров открываются в режиме просмотра:
        # `get_fields()` отдаёт только readonly-поля, и редактируемых полей у формы
        # не остаётся. Настраивать нечего — без этой проверки страница падает
        # с KeyError ещё до рендера.
        if "transaction_type" not in self.fields:
            return

        self.fields["transaction_type"].choices = [
            (value, label)
            for value, label in BonusTransaction.TRANSACTION_TYPES
            if value in BonusTransaction.MANUAL_TYPES
        ]
        self.fields["amount"].help_text = "Положительное число — знак проставится автоматически"
        self.fields["comment"].required = True

        # В журнале сумма хранится со знаком. При правке существующей операции
        # показываем её по модулю, иначе clean_amount отклонит своё же значение
        # и запись станет нередактируемой.
        instance = self.instance
        if instance.pk and instance.amount is not None:
            self.initial["amount"] = abs(instance.amount)

        # Роль тренера могла смениться после создания операции — сам владелец
        # операции обязан остаться в списке, иначе её нельзя будет сохранить.
        user_filter = Q(role=TRAINER_ROLE)
        if instance.pk and instance.user_id:
            user_filter |= Q(pk=instance.user_id)
        self.fields["user"].queryset = self.fields["user"].queryset.filter(user_filter)

    def clean_amount(self) -> Decimal:
        amount = self.cleaned_data["amount"]
        if amount is None or amount <= 0:
            raise forms.ValidationError("Введите положительную сумму.")
        return amount


@admin.register(BonusTransaction)
class BonusTransactionAdmin(admin.ModelAdmin):
    """Журнал бонусных операций."""

    form = ManualBonusTransactionForm
    list_display = (
        "created_at",
        "trainer",
        "transaction_type",
        "amount",
        "user_balance",
        "order_link",
        "short_comment",
    )
    list_filter = ("transaction_type", TrainerFilter, "created_at")
    search_fields = (
        "user__email",
        "user__first_name",
        "user__last_name",
        "user_email_snapshot",
        "user_name_snapshot",
        "order__order_number",
        "order_number_snapshot",
        "comment",
    )
    date_hierarchy = "created_at"
    list_select_related = ("user", "order")

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Баланс считается подзапросом в самом queryset.

        Экземпляр `ModelAdmin` живёт один на процесс, поэтому кэш на `self`
        протекал бы между одновременными запросами и показывал чужие суммы.
        """
        balance_subquery = (
            BonusTransaction.objects.filter(user_id=OuterRef("user_id"))
            .values("user_id")
            .annotate(total=Sum("amount"))
            .values("total")[:1]
        )
        return (
            super()
            .get_queryset(request)
            .annotate(
                trainer_balance=Coalesce(
                    Subquery(balance_subquery, output_field=DecimalField(max_digits=12, decimal_places=2)),
                    Value(Decimal("0"), output_field=DecimalField(max_digits=12, decimal_places=2)),
                )
            )
        )

    @admin.display(description="Баланс тренера", ordering="trainer_balance")
    def user_balance(self, obj: BonusTransaction) -> str:
        """Текущий баланс тренера (не остаток на момент операции)."""
        balance = getattr(obj, "trainer_balance", None)
        if balance is None:
            balance = get_balance(obj.user_id)
        return f"{balance} ₽"

    @admin.display(description="Тренер")
    def trainer(self, obj: BonusTransaction) -> str:
        """Тренер или снимок его данных, если учётная запись удалена."""
        return obj.trainer_display

    @admin.display(description="Заказ")
    def order_link(self, obj: BonusTransaction) -> str:
        order = obj.order
        if order is None:
            # Заказ удалён — остаётся снимок номера, ссылки уже нет
            return obj.order_number_snapshot or "—"
        url = reverse("admin:orders_order_change", args=[order.pk])
        return format_html('<a href="{}">{}</a>', url, order.order_number_display)

    @admin.display(description="Комментарий")
    def short_comment(self, obj: BonusTransaction) -> str:
        comment = obj.comment or ""
        return comment if len(comment) <= 60 else f"{comment[:60]}…"

    def _is_read_only(self, obj: BonusTransaction | None) -> bool:
        """Операция открывается только на чтение.

        Начисления не правятся никогда. Операции удалённого тренера — тоже:
        форма требует тренера, а восстановить ссылку на удалённую учётную
        запись нельзя, поэтому запись остаётся историческим документом.
        """
        if obj is None:
            return False
        return obj.transaction_type == BonusTransaction.ACCRUAL or obj.user_id is None

    def get_readonly_fields(self, request: HttpRequest, obj: BonusTransaction | None = None) -> tuple[str, ...]:
        """Начисления и операции удалённых тренеров открываются на чтение."""
        if self._is_read_only(obj):
            return (
                "user",
                "user_email_snapshot",
                "user_name_snapshot",
                "transaction_type",
                "amount",
                "order",
                "order_number_snapshot",
                "percent_applied",
                "base_amount",
                "comment",
                "created_by",
                "created_at",
            )
        return ()

    def get_fields(self, request: HttpRequest, obj: BonusTransaction | None = None) -> Any:
        if self._is_read_only(obj):
            return self.get_readonly_fields(request, obj)
        return super().get_fields(request, obj)

    def has_change_permission(self, request: HttpRequest, obj: BonusTransaction | None = None) -> bool:
        """Начисление правкам не подлежит — открывается в режиме просмотра."""
        if self._is_read_only(obj):
            return False
        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: BonusTransaction | None = None) -> bool:
        """История не удаляется — исправления оформляются списанием."""
        return False

    def save_model(
        self,
        request: HttpRequest,
        obj: BonusTransaction,
        form: forms.ModelForm,
        change: bool,
    ) -> None:
        """Проставляет автора операции. Валидация уже выполнена формой.

        Лимит выплаты проверяется в `BonusTransaction.clean()` под блокировкой
        счёта тренера. POST админки Django выполняет внутри `transaction.atomic()`
        (`ModelAdmin.changeform_view`), поэтому блокировка, взятая при валидации
        формы, держится до сохранения — вторая одновременная выплата ждёт
        коммита первой и видит уже уменьшенный баланс.
        """
        if obj.created_by_id is None:
            obj.created_by_id = request.user.pk
        super().save_model(request, obj, form, change)

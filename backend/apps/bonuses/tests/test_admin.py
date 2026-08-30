"""Unit-тесты админки бонусной программы: защита истории от правок."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.admin.options import IncorrectLookupParameters
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from apps.bonuses.admin import (
    BonusProgramSettingsAdmin,
    BonusTransactionAdmin,
    ManualBonusTransactionForm,
    TrainerFilter,
)
from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.tests.utils import close_master, create_master_with_subs, create_user


@pytest.fixture
def request_factory() -> RequestFactory:
    return RequestFactory()


def _accrual(trainer) -> BonusTransaction:
    master = create_master_with_subs(trainer, ["100000.00"])
    close_master(master)
    return BonusTransaction.objects.get(order=master)


@pytest.mark.unit
@pytest.mark.django_db
class TestSettingsAdmin:
    """Singleton-админка настроек."""

    def setup_method(self) -> None:
        self.admin = BonusProgramSettingsAdmin(BonusProgramSettings, AdminSite())

    def test_add_allowed_while_empty(self, request_factory: RequestFactory) -> None:
        assert self.admin.has_add_permission(request_factory.get("/")) is True

    def test_add_forbidden_once_created(self, request_factory: RequestFactory) -> None:
        BonusProgramSettings.load()

        assert self.admin.has_add_permission(request_factory.get("/")) is False

    def test_delete_forbidden(self, request_factory: RequestFactory) -> None:
        assert self.admin.has_delete_permission(request_factory.get("/")) is False


@pytest.mark.unit
@pytest.mark.django_db
class TestTransactionAdmin:
    """Журнал операций."""

    def setup_method(self) -> None:
        self.admin = BonusTransactionAdmin(BonusTransaction, AdminSite())

    def test_accrual_is_read_only(self, request_factory: RequestFactory) -> None:
        bonus = _accrual(create_user())
        request = request_factory.get("/")

        assert self.admin.has_change_permission(request, bonus) is False
        assert "amount" in self.admin.get_readonly_fields(request, bonus)
        assert "base_amount" in self.admin.get_fields(request, bonus)

    def test_manual_operation_stays_editable(self, request_factory: RequestFactory) -> None:
        trainer = create_user()
        writeoff = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("100.00"),
            comment="Исправление",
        )
        request = request_factory.get("/")
        request.user = create_user(role="admin")
        request.user.is_superuser = True

        assert self.admin.get_readonly_fields(request, writeoff) == ()
        assert self.admin.has_change_permission(request, writeoff) is True
        assert "comment" in self.admin.get_fields(request, writeoff)

    def test_delete_forbidden_for_any_type(self, request_factory: RequestFactory) -> None:
        bonus = _accrual(create_user())

        assert self.admin.has_delete_permission(request_factory.get("/"), bonus) is False

    def test_balance_is_annotated_not_cached_on_admin(self, request_factory: RequestFactory) -> None:
        """Баланс считается подзапросом, без разделяемого состояния на ModelAdmin."""
        trainer = create_user()
        _accrual(trainer)
        request = request_factory.get("/")
        request.user = create_user(role="admin")

        row = self.admin.get_queryset(request).first()

        assert row.trainer_balance == Decimal("5000.00")
        assert not hasattr(self.admin, "_balance_cache")
        assert self.admin.user_balance(row) == "5000.00 ₽"

    def test_balance_column_shows_current_balance(self) -> None:
        trainer = create_user()
        bonus = _accrual(trainer)

        assert self.admin.user_balance(bonus) == "5000.00 ₽"

    def test_order_link_renders_admin_url(self) -> None:
        bonus = _accrual(create_user())

        assert f"/admin/orders/order/{bonus.order_id}/change/" in self.admin.order_link(bonus)

    def test_order_link_is_dash_without_order(self) -> None:
        trainer = create_user()
        payout = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("10.00"),
            comment="Без заказа",
        )

        assert self.admin.order_link(payout) == "—"

    def test_long_comment_is_truncated(self) -> None:
        trainer = create_user()
        payout = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("10.00"),
            comment="д" * 100,
        )

        assert self.admin.short_comment(payout).endswith("…")
        assert len(self.admin.short_comment(payout)) == 61

    def test_save_model_sets_author(self, request_factory: RequestFactory) -> None:
        manager = create_user(role="admin")
        trainer = create_user()
        request = request_factory.post("/")
        request.user = manager

        operation = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("300.00"),
            comment="Возврат товара",
        )
        self.admin.save_model(request, operation, form=None, change=False)

        operation.refresh_from_db()
        assert operation.created_by_id == manager.pk
        assert operation.amount == Decimal("-300.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestTrainerFilter:
    """Фильтр по тренеру показывает только тех, у кого есть операции."""

    def test_lookups_list_trainers_with_operations(self, request_factory: RequestFactory) -> None:
        trainer = create_user()
        _accrual(trainer)
        create_user()  # тренер без операций

        admin = BonusTransactionAdmin(BonusTransaction, AdminSite())
        filter_instance = TrainerFilter(request_factory.get("/"), {}, BonusTransaction, admin)

        assert [user_id for user_id, _ in filter_instance.lookups(request_factory.get("/"), admin)] == [trainer.pk]

    def test_queryset_filters_by_selected_trainer(self, request_factory: RequestFactory) -> None:
        trainer = create_user()
        other = create_user()
        _accrual(trainer)
        _accrual(other)

        admin = BonusTransactionAdmin(BonusTransaction, AdminSite())
        filter_instance = TrainerFilter(
            request_factory.get("/"), {"trainer": [str(trainer.pk)]}, BonusTransaction, admin
        )
        result = filter_instance.queryset(request_factory.get("/"), BonusTransaction.objects.all())

        assert list(result.values_list("user_id", flat=True)) == [trainer.pk]

    def test_queryset_without_selection_is_untouched(self, request_factory: RequestFactory) -> None:
        trainer = create_user()
        _accrual(trainer)

        admin = BonusTransactionAdmin(BonusTransaction, AdminSite())
        filter_instance = TrainerFilter(request_factory.get("/"), {}, BonusTransaction, admin)
        result = filter_instance.queryset(request_factory.get("/"), BonusTransaction.objects.all())

        assert result.count() == 1

    def test_non_numeric_value_does_not_crash_changelist(self, request_factory: RequestFactory) -> None:
        """?trainer=abc должен дать штатную ошибку админки, а не 500."""
        admin = BonusTransactionAdmin(BonusTransaction, AdminSite())
        filter_instance = TrainerFilter(request_factory.get("/"), {"trainer": ["abc"]}, BonusTransaction, admin)

        with pytest.raises(IncorrectLookupParameters):
            filter_instance.queryset(request_factory.get("/"), BonusTransaction.objects.all())


@pytest.mark.unit
@pytest.mark.django_db
class TestManualForm:
    """Форма ручной операции."""

    def test_accrual_is_not_offered(self) -> None:
        form = ManualBonusTransactionForm()

        assert [value for value, _ in form.fields["transaction_type"].choices] == [
            BonusTransaction.PAYOUT,
            BonusTransaction.WRITEOFF,
        ]

    def test_only_trainers_are_selectable(self) -> None:
        trainer = create_user()
        create_user(role="retail")
        form = ManualBonusTransactionForm()

        assert list(form.fields["user"].queryset.values_list("id", flat=True)) == [trainer.pk]

    def test_negative_amount_is_rejected(self) -> None:
        trainer = create_user()
        form = ManualBonusTransactionForm(
            data={
                "user": trainer.pk,
                "transaction_type": BonusTransaction.WRITEOFF,
                "amount": "-100.00",
                "comment": "Минус вводить нельзя",
            }
        )

        assert form.is_valid() is False
        assert "amount" in form.errors

    def test_missing_comment_is_rejected(self) -> None:
        trainer = create_user()
        form = ManualBonusTransactionForm(
            data={
                "user": trainer.pk,
                "transaction_type": BonusTransaction.WRITEOFF,
                "amount": "100.00",
                "comment": "",
            }
        )

        assert form.is_valid() is False
        assert "comment" in form.errors

    def test_payout_above_balance_is_rejected_by_model_clean(self) -> None:
        trainer = create_user()
        form = ManualBonusTransactionForm(
            data={
                "user": trainer.pk,
                "transaction_type": BonusTransaction.PAYOUT,
                "amount": "100.00",
                "comment": "Баланс пуст",
            }
        )

        assert form.is_valid() is False
        assert "amount" in form.errors

    def test_existing_operation_is_editable(self) -> None:
        """Правка сохранённой операции не должна отклоняться собственным знаком.

        В журнале сумма хранится отрицательной; форма обязана показать её
        по модулю, иначе `clean_amount` забракует своё же значение.
        """
        trainer = create_user()
        operation = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("100.00"),
            comment="Исправление",
        )
        assert operation.amount == Decimal("-100.00")

        form = ManualBonusTransactionForm(instance=operation)
        assert form.initial["amount"] == Decimal("100.00")

        bound = ManualBonusTransactionForm(
            data={
                "user": trainer.pk,
                "transaction_type": BonusTransaction.WRITEOFF,
                "amount": "150.00",
                "comment": "Уточнили сумму",
            },
            instance=operation,
        )
        assert bound.is_valid() is True
        bound.save()

        operation.refresh_from_db()
        assert operation.amount == Decimal("-150.00")

    def test_owner_stays_selectable_after_role_change(self) -> None:
        """Смена роли владельца не должна делать операцию несохраняемой."""
        former_trainer = create_user()
        operation = BonusTransaction.objects.create(
            user=former_trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("100.00"),
            comment="Списание",
        )
        former_trainer.role = "retail"
        former_trainer.save(update_fields=["role"])

        form = ManualBonusTransactionForm(instance=operation)

        assert former_trainer.pk in list(form.fields["user"].queryset.values_list("id", flat=True))

    def test_valid_writeoff_passes(self) -> None:
        trainer = create_user()
        form = ManualBonusTransactionForm(
            data={
                "user": trainer.pk,
                "transaction_type": BonusTransaction.WRITEOFF,
                "amount": "100.00",
                "comment": "Заказ отменён",
            }
        )

        assert form.is_valid() is True

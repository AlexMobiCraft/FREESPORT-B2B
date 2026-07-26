"""Unit-тесты долговечности журнала бонусов.

Покрывают находки ревью спеки `spec-trainer-bonus-program`:
журнал переживает удаление тренера и заказа, ключ идемпотентности
не теряется вместе с заказом, лимит выплаты не обходится ни гонкой,
ни прямым `objects.create()`, а начисление нельзя настроить
на отменённые заказы.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.services.accrual import (
    accrue_for_order,
    create_manual_transaction,
    get_balance,
    lock_trainer_account,
)
from apps.bonuses.tests.utils import close_master, create_master_with_subs, create_user


@pytest.mark.unit
@pytest.mark.django_db
class TestJournalSurvivesUserDeletion:
    """Удаление тренера не стирает финансовую историю."""

    def test_accrual_records_trainer_snapshot(self) -> None:
        trainer = create_user()
        trainer.first_name = "Иван"
        trainer.last_name = "Петров"
        trainer.save(update_fields=["first_name", "last_name"])

        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)

        bonus = BonusTransaction.objects.get(transaction_type=BonusTransaction.ACCRUAL)
        assert bonus.user_email_snapshot == trainer.email
        assert bonus.user_name_snapshot == "Иван Петров"
        assert bonus.order_number_snapshot == master.order_number

    def test_deleting_trainer_keeps_transactions(self) -> None:
        """`SET_NULL` вместо `CASCADE`: выплаты остаются в журнале."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        create_manual_transaction(
            user=trainer,
            transaction_type=BonusTransaction.PAYOUT,
            amount=Decimal("2000.00"),
            comment="Перевод на карту",
        )
        email = trainer.email

        trainer.delete()

        rows = list(BonusTransaction.objects.order_by("transaction_type"))
        assert len(rows) == 2
        assert all(row.user_id is None for row in rows)
        assert all(row.user_email_snapshot == email for row in rows)

    def test_trainer_display_falls_back_to_snapshot(self) -> None:
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        email = trainer.email
        trainer.delete()

        bonus = BonusTransaction.objects.get(transaction_type=BonusTransaction.ACCRUAL)
        assert bonus.trainer_display == f"{email} (удалён)"


@pytest.mark.unit
@pytest.mark.django_db
class TestIdempotencySurvivesOrderDeletion:
    """Ключ идемпотентности живёт в снимке номера, а не в FK."""

    def test_deleted_order_keeps_order_number_snapshot(self) -> None:
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        order_number = master.order_number

        master.delete()

        bonus = BonusTransaction.objects.get(transaction_type=BonusTransaction.ACCRUAL)
        assert bonus.order_id is None
        assert bonus.order_number_snapshot == order_number
        assert bonus.order_display == order_number

    def test_second_accrual_for_same_order_number_is_rejected(self) -> None:
        """После удаления заказа NULL-ы в FK различны, снимок — нет."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        order_number = master.order_number
        master.delete()

        with pytest.raises(IntegrityError), transaction.atomic():
            BonusTransaction.objects.create(
                user=trainer,
                transaction_type=BonusTransaction.ACCRUAL,
                amount=Decimal("5000.00"),
                order_number_snapshot=order_number,
            )

    def test_repeated_accrual_is_skipped_by_snapshot(self) -> None:
        """Повторный вызов сервиса не создаёт вторую операцию."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)

        assert accrue_for_order(master) is None
        assert BonusTransaction.objects.filter(transaction_type=BonusTransaction.ACCRUAL).count() == 1

    def test_manual_operations_do_not_collide_on_empty_snapshot(self) -> None:
        """У выплат снимок заказа пуст — констрейнт их не затрагивает."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["200000.00"])
        close_master(master)

        for _ in range(2):
            create_manual_transaction(
                user=trainer,
                transaction_type=BonusTransaction.PAYOUT,
                amount=Decimal("1000.00"),
                comment="Частичная выплата",
            )

        assert BonusTransaction.objects.filter(transaction_type=BonusTransaction.PAYOUT).count() == 2


@pytest.mark.unit
@pytest.mark.django_db
class TestPayoutLimitCannotBeBypassed:
    """Лимит выплаты проверяется под блокировкой счёта и не обходится."""

    def test_direct_create_still_validates_limit(self) -> None:
        """`objects.create()` больше не обходит проверку баланса."""
        trainer = create_user()

        with pytest.raises(ValidationError) as exc:
            BonusTransaction.objects.create(
                user=trainer,
                transaction_type=BonusTransaction.PAYOUT,
                amount=Decimal("5000.00"),
                comment="Выплата без начислений",
            )

        assert "amount" in exc.value.message_dict
        assert BonusTransaction.objects.count() == 0

    def test_direct_create_requires_comment(self) -> None:
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)

        with pytest.raises(ValidationError) as exc:
            BonusTransaction.objects.create(
                user=trainer,
                transaction_type=BonusTransaction.WRITEOFF,
                amount=Decimal("100.00"),
            )

        assert "comment" in exc.value.message_dict

    def test_payout_validation_locks_trainer_row(self) -> None:
        """Проверка баланса выполняет SELECT ... FOR UPDATE по строке тренера."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)

        with CaptureQueriesContext(connection) as captured:
            create_manual_transaction(
                user=trainer,
                transaction_type=BonusTransaction.PAYOUT,
                amount=Decimal("1000.00"),
                comment="Перевод на карту",
            )

        locking = [q["sql"] for q in captured.captured_queries if "FOR UPDATE" in q["sql"] and '"users"' in q["sql"]]
        assert locking, "Ожидалась блокировка строки тренера при проверке лимита выплаты"

    def test_lock_outside_transaction_does_not_raise(self) -> None:
        """Вне транзакции блокировка пропускается, а не роняет валидацию."""
        trainer = create_user()

        # `in_atomic_block` в тестах всегда True, поэтому имитируем отсутствие
        # транзакции подменой флага соединения
        original = connection.in_atomic_block
        connection.in_atomic_block = False
        try:
            lock_trainer_account(trainer.pk)
        finally:
            connection.in_atomic_block = original

    def test_writeoff_is_not_limited_by_balance(self) -> None:
        """Списание уводит счёт в минус — асимметрия сохраняется."""
        trainer = create_user()

        bonus = create_manual_transaction(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("4000.00"),
            comment="Заказ закрыт с отменой",
        )

        assert bonus.amount == Decimal("-4000.00")
        assert get_balance(trainer) == Decimal("-4000.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestAccrualStatusIsNotTerminal:
    """Начисление нельзя настроить на отменённые заказы."""

    def test_terminal_status_rejected_by_validation(self) -> None:
        settings = BonusProgramSettings.load()
        settings.accrual_status = "cancelled"

        with pytest.raises(ValidationError) as exc:
            settings.full_clean()

        assert "accrual_status" in exc.value.message_dict

    def test_terminal_status_rejected_by_db_constraint(self) -> None:
        """CheckConstraint закрывает путь в обход `full_clean()`."""
        settings = BonusProgramSettings.load()
        settings.accrual_status = "refunded"

        with pytest.raises(IntegrityError), transaction.atomic():
            settings.save()

    def test_active_statuses_remain_available(self) -> None:
        settings = BonusProgramSettings.load()
        available = {value for value, _ in settings._meta.get_field("accrual_status").choices}

        assert available == {"pending", "confirmed", "processing", "shipped", "delivered"}

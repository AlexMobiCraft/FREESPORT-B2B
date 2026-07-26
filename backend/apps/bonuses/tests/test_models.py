"""Unit-тесты моделей бонусной программы: знак суммы, лимиты, комментарий."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.services.accrual import get_balance
from apps.bonuses.tests.utils import close_master, create_master_with_subs, create_user


def _accrue(trainer, total: str = "100000.00") -> BonusTransaction:
    """Создаёт начисление через штатный путь (закрытие мастер-заказа)."""
    master = create_master_with_subs(trainer, [total])
    close_master(master)
    return BonusTransaction.objects.get(order=master)


@pytest.mark.unit
@pytest.mark.django_db
class TestSettingsSingleton:
    """Настройки программы — ровно одна запись."""

    def test_load_creates_defaults(self) -> None:
        settings = BonusProgramSettings.load()

        assert settings.pk == 1
        assert settings.is_active is True
        assert settings.percent == Decimal("5.00")
        assert settings.accrual_status == "delivered"

    def test_second_instance_overwrites_the_first(self) -> None:
        """save() жёстко фиксирует pk=1 — второй записи не появится."""
        BonusProgramSettings.load()
        BonusProgramSettings(is_active=False, percent=Decimal("9.00")).save()

        assert BonusProgramSettings.objects.count() == 1
        assert BonusProgramSettings.load().percent == Decimal("9.00")

    def test_delete_is_forbidden(self) -> None:
        settings = BonusProgramSettings.load()

        with pytest.raises(ValidationError):
            settings.delete()

    def test_str_reflects_state(self) -> None:
        settings = BonusProgramSettings.load()

        assert "включена" in str(settings)


@pytest.mark.unit
@pytest.mark.django_db
class TestAmountSign:
    """Знак суммы определяется типом операции."""

    def test_payout_is_stored_negative(self) -> None:
        """Менеджер вводит положительное число — модель ставит минус."""
        trainer = create_user()
        _accrue(trainer)

        payout = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.PAYOUT,
            amount=Decimal("1000.00"),
            comment="Перевод на карту",
        )

        assert payout.amount == Decimal("-1000.00")

    def test_writeoff_is_stored_negative(self) -> None:
        trainer = create_user()

        writeoff = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("400.00"),
            comment="Заказ отменён",
        )

        assert writeoff.amount == Decimal("-400.00")

    def test_accrual_is_stored_positive(self) -> None:
        trainer = create_user()
        bonus = _accrue(trainer, "1000.00")

        assert bonus.amount == Decimal("50.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestManualOperationValidation:
    """Валидация ручных операций через clean()."""

    def test_payout_within_balance_passes(self) -> None:
        trainer = create_user()
        _accrue(trainer, "130000.00")  # 6 500 ₽

        payout = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.PAYOUT,
            amount=Decimal("5000.00"),
            comment="Выплата наличными",
        )
        payout.full_clean()
        payout.save()

        assert get_balance(trainer) == Decimal("1500.00")

    def test_payout_above_balance_is_rejected(self) -> None:
        """Защита от опечатки: выплатить больше накопленного нельзя."""
        trainer = create_user()
        _accrue(trainer, "30000.00")  # 1 500 ₽

        payout = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.PAYOUT,
            amount=Decimal("5000.00"),
            comment="Опечатка в сумме",
        )

        with pytest.raises(ValidationError) as exc:
            payout.full_clean()

        assert "amount" in exc.value.error_dict
        assert "1500" in str(exc.value)

    def test_writeoff_may_go_negative(self) -> None:
        """Списание уводит баланс в минус — это отражает долг тренера."""
        trainer = create_user()

        writeoff = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("4000.00"),
            comment="Бонус выплачен, заказ отменён",
        )
        writeoff.full_clean()
        writeoff.save()

        assert get_balance(trainer) == Decimal("-4000.00")

    def test_zero_amount_is_rejected(self) -> None:
        """Нулевая операция бессмысленна и нарушила бы CheckConstraint."""
        trainer = create_user()

        operation = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("0.00"),
            comment="Ноль",
        )

        with pytest.raises(ValidationError) as exc:
            operation.full_clean()

        assert "amount" in exc.value.error_dict

    def test_wrong_signed_accrual_is_not_silently_flipped(self) -> None:
        """Отрицательное начисление — ошибка вызывающего, а не повод молча инвертировать."""
        trainer = create_user()

        operation = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.ACCRUAL,
            amount=Decimal("-500.00"),
        )

        with pytest.raises(ValidationError):
            operation.full_clean()

    def test_manual_operation_requires_comment(self) -> None:
        trainer = create_user()

        operation = BonusTransaction(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("100.00"),
            comment="   ",
        )

        with pytest.raises(ValidationError) as exc:
            operation.full_clean()

        assert "comment" in exc.value.error_dict

    def test_editing_payout_excludes_itself_from_balance(self) -> None:
        """При правке выплаты её прежняя сумма не занижает лимит."""
        trainer = create_user()
        _accrue(trainer, "100000.00")  # 5 000 ₽

        payout = BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.PAYOUT,
            amount=Decimal("2000.00"),
            comment="Первая выплата",
        )

        payout.amount = Decimal("5000.00")
        payout.full_clean()  # не должно упасть: баланс без этой операции = 5 000 ₽

    def test_str_is_readable(self) -> None:
        trainer = create_user()
        bonus = _accrue(trainer, "1000.00")

        assert "Начисление" in str(bonus)


@pytest.mark.unit
@pytest.mark.django_db
class TestConstraints:
    """Ограничения уровня БД."""

    def test_second_accrual_for_order_is_rejected(self) -> None:
        """UniqueConstraint не даёт начислить дважды по одному заказу."""
        trainer = create_user()
        bonus = _accrue(trainer)

        with pytest.raises(IntegrityError), transaction.atomic():
            BonusTransaction.objects.create(
                user=trainer,
                transaction_type=BonusTransaction.ACCRUAL,
                amount=Decimal("10.00"),
                order=bonus.order,
            )

    def test_manual_operations_share_the_same_order(self) -> None:
        """Ограничение действует только на начисления."""
        trainer = create_user()
        bonus = _accrue(trainer, "100000.00")

        BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("100.00"),
            order=bonus.order,
            comment="Частичный возврат",
        )
        BonusTransaction.objects.create(
            user=trainer,
            transaction_type=BonusTransaction.WRITEOFF,
            amount=Decimal("50.00"),
            order=bonus.order,
            comment="Ещё один возврат",
        )

        assert BonusTransaction.objects.filter(order=bonus.order).count() == 3

    def test_balance_of_user_without_operations_is_zero(self) -> None:
        trainer = create_user()

        assert get_balance(trainer) == Decimal("0")

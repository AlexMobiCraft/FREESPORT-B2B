"""Unit-тесты начисления бонусов (сервис + сигнал).

Покрывают строки I/O-матрицы спецификации: начисление, идемпотентность,
частичное и полное закрытие субзаказов, роль и верификация тренера,
выключенная программа.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.db import IntegrityError, transaction
from django.db.models.signals import post_save
from django.utils import timezone

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.services.accrual import accrue_for_order, calculate_base, get_balance
from apps.bonuses.tests.utils import add_item, close_master, create_master_with_subs, create_order, create_user
from apps.orders.models import Order


@pytest.mark.unit
@pytest.mark.django_db
class TestCalculateBase:
    """База начисления — сумма позиций субзаказов, без доставки."""

    def test_base_sums_sub_order_items(self) -> None:
        """У мастера своих позиций нет — база собирается из субзаказов."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["50000.00", "30000.00"], delivery_cost="1500.00")

        assert master.items.count() == 0
        assert calculate_base(master) == Decimal("80000.00")

    def test_base_falls_back_to_own_items(self) -> None:
        """Legacy-мастер без субзаказов — база из собственных позиций."""
        trainer = create_user()
        master = create_order(trainer)
        add_item(master, "12000.00")

        assert calculate_base(master) == Decimal("12000.00")

    def test_base_is_zero_without_items(self) -> None:
        """Заказ без позиций даёт нулевую базу, а не падение."""
        trainer = create_user()
        master = create_order(trainer)

        assert calculate_base(master) == Decimal("0")

    def test_cancelled_sub_orders_are_excluded(self) -> None:
        """Отменённый субзаказ не входит в базу.

        Мастер со смешанными статусами агрегируется в `delivered`
        (у `cancelled` приоритет 0), поэтому без фильтра бонус
        начислялся бы за неотгруженный товар.
        """
        trainer = create_user()
        master = create_master_with_subs(
            trainer,
            ["100000.00", "100000.00"],
            sub_statuses=["delivered", "cancelled"],
        )

        assert calculate_base(master) == Decimal("100000.00")

    def test_refunded_sub_orders_are_excluded(self) -> None:
        """Возвращённый субзаказ тоже не входит в базу."""
        trainer = create_user()
        master = create_master_with_subs(
            trainer,
            ["50000.00", "20000.00"],
            sub_statuses=["delivered", "refunded"],
        )

        assert calculate_base(master) == Decimal("50000.00")

    def test_fully_cancelled_master_has_zero_base(self) -> None:
        """Все субзаказы отменены — начислять не за что.

        Fallback на позиции мастера здесь сработать не должен.
        """
        trainer = create_user()
        master = create_master_with_subs(
            trainer,
            ["10000.00", "10000.00"],
            sub_statuses=["cancelled", "cancelled"],
        )

        assert calculate_base(master) == Decimal("0")


@pytest.mark.unit
@pytest.mark.django_db
class TestAccrual:
    """Начисление по мастер-заказу."""

    def test_accrual_on_full_closure(self) -> None:
        """Товаров на 80 000 ₽, доставка 1 500 ₽, 5 % → 4 000 ₽."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["50000.00", "30000.00"], delivery_cost="1500.00")

        close_master(master)

        bonus = BonusTransaction.objects.get(order=master, transaction_type=BonusTransaction.ACCRUAL)
        assert bonus.amount == Decimal("4000.00")
        assert bonus.base_amount == Decimal("80000.00")
        assert bonus.percent_applied == Decimal("5.00")
        assert bonus.user_id == trainer.pk
        assert get_balance(trainer) == Decimal("4000.00")

    def test_partial_closure_gives_no_accrual(self) -> None:
        """Закрыт один субзаказ из трёх — мастер не в целевом статусе."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["10000.00", "10000.00", "10000.00"])

        sub = master.sub_orders.first()
        sub.status = "delivered"
        sub.save(update_fields=["status", "updated_at"])

        master.refresh_from_db()
        assert master.status != "delivered"
        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_repeated_import_is_idempotent(self) -> None:
        """Повторное сохранение мастера не создаёт вторую транзакцию."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])

        close_master(master)
        accrue_for_order(master)
        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 1
        assert get_balance(trainer) == Decimal("1000.00")

    def test_unverified_trainer_gets_nothing(self) -> None:
        """Неподтверждённому тренеру бонус не начисляется."""
        trainer = create_user(is_verified=False)
        master = create_master_with_subs(trainer, ["20000.00"])

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_non_trainer_gets_nothing(self) -> None:
        """Роль retail в программе не участвует."""
        customer = create_user(role="retail")
        master = create_master_with_subs(customer, ["20000.00"])

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_disabled_program_gives_nothing(self) -> None:
        """Выключенная программа не начисляет."""
        settings = BonusProgramSettings.load()
        settings.is_active = False
        settings.save()

        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_sub_order_never_accrues(self) -> None:
        """Начисление только по мастеру, даже если субзаказ закрыт."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        sub = master.sub_orders.first()

        assert accrue_for_order(sub) is None

    def test_guest_order_is_ignored(self) -> None:
        """Заказ без пользователя не приводит к начислению."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        master.user = None
        master.save(update_fields=["user", "updated_at"])

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_zero_base_gives_no_transaction(self) -> None:
        """Заказ без позиций не создаёт нулевую транзакцию."""
        trainer = create_user()
        master = create_order(trainer)

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_custom_accrual_status_is_respected(self) -> None:
        """Момент начисления настраивается без деплоя."""
        settings = BonusProgramSettings.load()
        settings.accrual_status = "shipped"
        settings.save()

        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])

        close_master(master, status="shipped")

        assert BonusTransaction.objects.filter(order=master).count() == 1

    def test_percent_change_does_not_touch_past(self) -> None:
        """Изменение % влияет только на новые начисления."""
        trainer = create_user()
        first = create_master_with_subs(trainer, ["10000.00"])
        close_master(first)

        settings = BonusProgramSettings.load()
        settings.percent = Decimal("7.00")
        settings.save()

        second = create_master_with_subs(trainer, ["10000.00"])
        close_master(second)

        old = BonusTransaction.objects.get(order=first)
        new = BonusTransaction.objects.get(order=second)
        assert old.amount == Decimal("500.00")
        assert old.percent_applied == Decimal("5.00")
        assert new.amount == Decimal("700.00")
        assert new.percent_applied == Decimal("7.00")

    def test_duplicate_insert_keeps_outer_transaction_alive(self) -> None:
        """Savepoint защищает объемлющую транзакцию импорта от реального дубля.

        Дубль вставляется настоящим SQL внутри внешнего `transaction.atomic()`,
        как в проде. Без savepoint PostgreSQL пометил бы транзакцию как
        aborted, и весь батч обновлений статусов умер бы.
        """
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        master.status = "delivered"

        with transaction.atomic():  # имитируем транзакцию батча импорта
            first = accrue_for_order(master)
            assert first is not None

            # Глушим предварительную проверку exists(), чтобы дубль ушёл
            # настоящим INSERT и упёрся в UniqueConstraint на уровне БД.
            # У мастера есть субзаказы, поэтому calculate_base до exists() не доходит.
            with mock.patch("django.db.models.query.QuerySet.exists", return_value=False):
                assert accrue_for_order(master) is None

            # Транзакция жива: запросы на том же соединении выполняются
            assert BonusTransaction.objects.filter(order=master).count() == 1
            assert Order.objects.filter(pk=master.pk).count() == 1

        assert BonusTransaction.objects.filter(order=master).count() == 1

    def test_settings_creation_race_does_not_poison_transaction(self) -> None:
        """Сбой на `load()` тоже прикрыт savepoint'ом, а не только `create()`."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        master.status = "delivered"

        with transaction.atomic():
            with mock.patch.object(
                BonusProgramSettings, "load", side_effect=IntegrityError("duplicate key value pk=1")
            ):
                assert accrue_for_order(master) is None

            # Внешняя транзакция не сломана — импорт продолжается
            assert Order.objects.filter(pk=master.pk).exists()

    def test_signal_never_breaks_order_save(self) -> None:
        """Сбой начисления не должен ронять сохранение заказа и импорт из 1С."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])

        with mock.patch(
            "apps.bonuses.services.accrual.accrue_for_order",
            side_effect=RuntimeError("сбой расчёта"),
        ):
            close_master(master)

        master.refresh_from_db()
        assert master.status == "delivered"

    def test_mixed_master_accrues_only_on_delivered_part(self) -> None:
        """Смешанный мастер: бонус за 100 000 ₽, а не за 200 000 ₽."""
        trainer = create_user()
        master = create_master_with_subs(
            trainer,
            ["100000.00", "100000.00"],
            sub_statuses=["delivered", "cancelled"],
        )

        close_master(master)

        bonus = BonusTransaction.objects.get(order=master)
        assert bonus.base_amount == Decimal("100000.00")
        assert bonus.amount == Decimal("5000.00")

    def test_order_created_before_program_start_is_skipped(self) -> None:
        """Заказы, закрытые до запуска программы, бонусов не получают."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])

        settings = BonusProgramSettings.load()
        settings.program_start_at = timezone.now() + timedelta(days=1)
        settings.save()

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_empty_program_start_disables_cutoff(self) -> None:
        """Пустая дата запуска отключает отсечку."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])

        settings = BonusProgramSettings.load()
        settings.program_start_at = None
        settings.save()

        close_master(master)

        assert BonusTransaction.objects.filter(order=master).count() == 1

    def test_fixture_load_does_not_accrue(self) -> None:
        """loaddata (raw=True) не должен создавать денежные операции."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["20000.00"])
        master.status = "delivered"

        post_save.send(sender=Order, instance=master, created=False, raw=True)

        assert BonusTransaction.objects.filter(order=master).count() == 0

    def test_rounding_is_half_up(self) -> None:
        """Копейки округляются арифметически, а не отбрасываются."""
        settings = BonusProgramSettings.load()
        settings.percent = Decimal("3.33")
        settings.save()

        trainer = create_user()
        master = create_master_with_subs(trainer, ["1000.05"])
        close_master(master)

        # 1000.05 * 3.33 / 100 = 33.301665 → 33.30
        assert BonusTransaction.objects.get(order=master).amount == Decimal("33.30")

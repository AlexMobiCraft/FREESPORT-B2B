"""Тесты страниц админки бонусной программы через реальный HTTP-рендер.

Остальные тесты админки дёргают методы `ModelAdmin` напрямую. Такой подход
пропустил падение страницы начисления: `has_change_permission` и
`get_readonly_fields` возвращали правильные значения, но сам рендер страницы
отдавал 500, потому что форма настраивала поля, которых в режиме просмотра
уже нет. Здесь запрашиваются настоящие URL админки.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from apps.bonuses.models import BonusTransaction
from apps.bonuses.services.accrual import create_manual_transaction, get_balance
from apps.bonuses.tests.utils import close_master, create_master_with_subs, create_user, unique_suffix


@pytest.fixture
def staff_client(django_user_model) -> Client:
    """Клиент, залогиненный суперпользователем админки."""
    admin = django_user_model.objects.create_superuser(
        email=f"admin-{unique_suffix()}@freesport.test",
        password="admin_password123",
    )
    client = Client()
    client.force_login(admin)
    return client


def _accrual_for_new_trainer() -> BonusTransaction:
    """Начисление по закрытому мастер-заказу нового тренера."""
    trainer = create_user()
    master = create_master_with_subs(trainer, ["100000.00"])
    close_master(master)
    return BonusTransaction.objects.get(order=master)


@pytest.mark.unit
@pytest.mark.django_db
class TestTransactionPages:
    """Страницы журнала операций отдают 200, а не 500."""

    def test_changelist_opens(self, staff_client: Client) -> None:
        _accrual_for_new_trainer()
        response = staff_client.get(reverse("admin:bonuses_bonustransaction_changelist"))
        assert response.status_code == 200

    def test_add_form_opens(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:bonuses_bonustransaction_add"))
        assert response.status_code == 200
        html = response.content.decode()
        # Начисления создаёт только сервис — вручную такой тип не выбирается
        assert 'value="accrual"' not in html
        assert 'value="payout"' in html
        assert 'value="writeoff"' in html

    def test_accrual_page_opens_read_only(self, staff_client: Client) -> None:
        """Начисление открывается на просмотр.

        Регрессия: форма ручной операции настраивала `transaction_type`,
        которого в режиме просмотра в форме нет, и страница падала с 500.
        """
        accrual = _accrual_for_new_trainer()

        response = staff_client.get(reverse("admin:bonuses_bonustransaction_change", args=[accrual.pk]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'name="amount"' not in html, "Начисление не должно быть редактируемым"
        assert 'name="_save"' not in html, "У начисления не должно быть кнопки сохранения"

    def test_page_of_deleted_trainer_operation_opens(self, staff_client: Client) -> None:
        """Операция удалённого тренера тоже открывается только на просмотр."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        payout = create_manual_transaction(
            user=trainer,
            transaction_type="payout",
            amount=Decimal("1000.00"),
            comment="Перевод на карту",
        )
        trainer.delete()
        payout.refresh_from_db()
        assert payout.user_id is None

        response = staff_client.get(reverse("admin:bonuses_bonustransaction_change", args=[payout.pk]))

        assert response.status_code == 200
        assert 'name="_save"' not in response.content.decode()

    def test_manual_operation_page_stays_editable(self, staff_client: Client) -> None:
        """Выплата живого тренера остаётся редактируемой, сумма — по модулю."""
        trainer = create_user()
        master = create_master_with_subs(trainer, ["100000.00"])
        close_master(master)
        payout = create_manual_transaction(
            user=trainer,
            transaction_type="payout",
            amount=Decimal("1000.00"),
            comment="Перевод на карту",
        )

        response = staff_client.get(reverse("admin:bonuses_bonustransaction_change", args=[payout.pk]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'name="amount"' in html
        # В журнале сумма хранится со знаком, в форме показывается положительной
        assert 'value="1000.00"' in html


@pytest.mark.unit
@pytest.mark.django_db
class TestManualOperationThroughAdmin:
    """Создание ручных операций через POST админки."""

    def test_payout_above_balance_is_rejected(self, staff_client: Client) -> None:
        accrual = _accrual_for_new_trainer()
        trainer = accrual.user
        balance = get_balance(trainer)

        response = staff_client.post(
            reverse("admin:bonuses_bonustransaction_add"),
            {
                "user": trainer.pk,
                "transaction_type": "payout",
                "amount": str(balance + Decimal("1000")),
                "comment": "Выплата сверх баланса",
            },
        )

        assert response.status_code == 200, "Форма должна вернуться с ошибкой, а не сохраниться"
        assert "превышает текущий баланс" in response.content.decode()
        assert get_balance(trainer) == balance

    def test_payout_without_comment_is_rejected(self, staff_client: Client) -> None:
        accrual = _accrual_for_new_trainer()

        response = staff_client.post(
            reverse("admin:bonuses_bonustransaction_add"),
            {
                "user": accrual.user.pk,
                "transaction_type": "payout",
                "amount": "100",
                "comment": "",
            },
        )

        assert response.status_code == 200
        assert not BonusTransaction.objects.filter(transaction_type="payout").exists()

    def test_valid_payout_is_saved_with_author(self, staff_client: Client) -> None:
        accrual = _accrual_for_new_trainer()
        trainer = accrual.user

        staff_client.post(
            reverse("admin:bonuses_bonustransaction_add"),
            {
                "user": trainer.pk,
                "transaction_type": "payout",
                "amount": "1000",
                "comment": "Перевод на карту",
            },
        )

        payout = BonusTransaction.objects.get(user=trainer, transaction_type="payout")
        assert payout.amount == Decimal("-1000.00")
        assert payout.created_by_id is not None
        assert get_balance(trainer) == Decimal("4000.00")

    def test_writeoff_may_drive_balance_negative(self, staff_client: Client) -> None:
        accrual = _accrual_for_new_trainer()
        trainer = accrual.user

        staff_client.post(
            reverse("admin:bonuses_bonustransaction_add"),
            {
                "user": trainer.pk,
                "transaction_type": "writeoff",
                "amount": "5500",
                "comment": "Заказ закрыт с отменой",
            },
        )

        assert BonusTransaction.objects.filter(user=trainer, transaction_type="writeoff").exists()
        assert get_balance(trainer) == Decimal("-500.00")


@pytest.mark.unit
@pytest.mark.django_db
class TestSettingsPages:
    """Singleton-страницы настроек программы."""

    def test_changelist_opens(self, staff_client: Client) -> None:
        response = staff_client.get(reverse("admin:bonuses_bonusprogramsettings_changelist"))
        assert response.status_code == 200

    def test_change_form_opens_without_terminal_statuses(self, staff_client: Client) -> None:
        from apps.bonuses.models import BonusProgramSettings

        settings_obj = BonusProgramSettings.load()

        response = staff_client.get(reverse("admin:bonuses_bonusprogramsettings_change", args=[settings_obj.pk]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'name="percent"' in html
        # Начисление за отменённый заказ не должно настраиваться в принципе
        assert 'value="cancelled"' not in html
        assert 'value="refunded"' not in html

    def test_second_settings_record_cannot_be_added(self, staff_client: Client) -> None:
        from apps.bonuses.models import BonusProgramSettings

        BonusProgramSettings.load()

        response = staff_client.get(reverse("admin:bonuses_bonusprogramsettings_add"))

        assert response.status_code == 403

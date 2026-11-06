"""Unit-тесты API бонусной программы в личном кабинете тренера."""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.bonuses.models import BonusTransaction
from apps.bonuses.tests.utils import close_master, create_master_with_subs, create_user

SUMMARY_URL = "/api/v1/users/bonuses/"
TRANSACTIONS_URL = "/api/v1/users/bonuses/transactions/"


@pytest.fixture
def client() -> APIClient:
    return APIClient()


def _trainer_with_history():
    """Тренер с начислением 5 000 ₽ и выплатой 2 000 ₽."""
    trainer = create_user()
    master = create_master_with_subs(trainer, ["100000.00"])
    close_master(master)
    BonusTransaction.objects.create(
        user=trainer,
        transaction_type=BonusTransaction.PAYOUT,
        amount=Decimal("2000.00"),
        comment="Перевод на карту",
    )
    return trainer, master


@pytest.mark.unit
@pytest.mark.django_db
class TestUrls:
    """Маршруты подключены под api/v1/."""

    def test_reverse_matches_expected_paths(self) -> None:
        assert reverse("bonuses:summary") == SUMMARY_URL
        assert reverse("bonuses:transactions") == TRANSACTIONS_URL


@pytest.mark.unit
@pytest.mark.django_db
class TestBonusSummary:
    """GET /api/v1/users/bonuses/"""

    def test_trainer_sees_summary(self, client: APIClient) -> None:
        trainer, _ = _trainer_with_history()
        client.force_authenticate(user=trainer)

        response = client.get(SUMMARY_URL)

        assert response.status_code == 200
        assert Decimal(response.data["balance"]) == Decimal("3000.00")
        assert Decimal(response.data["total_accrued"]) == Decimal("5000.00")
        assert Decimal(response.data["total_paid_out"]) == Decimal("2000.00")
        assert Decimal(response.data["current_percent"]) == Decimal("5.00")
        assert response.data["is_active"] is True

    def test_trainer_without_history_gets_zeros(self, client: APIClient) -> None:
        client.force_authenticate(user=create_user())

        response = client.get(SUMMARY_URL)

        assert response.status_code == 200
        assert Decimal(response.data["balance"]) == Decimal("0")
        assert Decimal(response.data["total_accrued"]) == Decimal("0")

    def test_non_trainer_is_forbidden(self, client: APIClient) -> None:
        client.force_authenticate(user=create_user(role="retail"))

        response = client.get(SUMMARY_URL)

        assert response.status_code == 403

    def test_unverified_trainer_is_forbidden(self, client: APIClient) -> None:
        """Условие доступа совпадает с условием начисления и с пунктом меню.

        Неподтверждённый тренер в программе не участвует, поэтому получает
        403 с объяснением, а не 200 с нулями, похожими на пропажу бонусов.
        """
        client.force_authenticate(user=create_user(is_verified=False))

        response = client.get(SUMMARY_URL)

        assert response.status_code == 403
        assert "не подтверждена" in response.data["detail"]

    def test_anonymous_is_unauthorized(self, client: APIClient) -> None:
        response = client.get(SUMMARY_URL)

        assert response.status_code == 401


@pytest.mark.unit
@pytest.mark.django_db
class TestBonusTransactionList:
    """GET /api/v1/users/bonuses/transactions/"""

    def test_trainer_sees_own_history(self, client: APIClient) -> None:
        trainer, master = _trainer_with_history()
        client.force_authenticate(user=trainer)

        response = client.get(TRANSACTIONS_URL)

        assert response.status_code == 200
        assert response.data["count"] == 2
        types = {row["transaction_type"] for row in response.data["results"]}
        assert types == {BonusTransaction.ACCRUAL, BonusTransaction.PAYOUT}

    def test_accrual_row_carries_order_and_snapshot(self, client: APIClient) -> None:
        trainer, master = _trainer_with_history()
        client.force_authenticate(user=trainer)

        response = client.get(f"{TRANSACTIONS_URL}?type={BonusTransaction.ACCRUAL}")

        assert response.data["count"] == 1
        row = response.data["results"][0]
        assert row["order_id"] == master.pk
        assert row["order_number"] == master.order_number_display
        assert Decimal(row["percent_applied"]) == Decimal("5.00")
        assert Decimal(row["base_amount"]) == Decimal("100000.00")

    def test_filter_by_type(self, client: APIClient) -> None:
        trainer, _ = _trainer_with_history()
        client.force_authenticate(user=trainer)

        response = client.get(f"{TRANSACTIONS_URL}?type={BonusTransaction.PAYOUT}")

        assert response.data["count"] == 1
        assert response.data["results"][0]["comment"] == "Перевод на карту"

    def test_foreign_history_is_not_exposed(self, client: APIClient) -> None:
        """Тренер видит только свои операции."""
        _trainer_with_history()
        other_trainer = create_user()
        client.force_authenticate(user=other_trainer)

        response = client.get(TRANSACTIONS_URL)

        assert response.data["count"] == 0

    def test_pagination_is_applied(self, client: APIClient) -> None:
        trainer = create_user()
        for index in range(3):
            BonusTransaction.objects.create(
                user=trainer,
                transaction_type=BonusTransaction.WRITEOFF,
                amount=Decimal("10.00"),
                comment=f"Списание {index}",
            )
        client.force_authenticate(user=trainer)

        response = client.get(f"{TRANSACTIONS_URL}?page_size=2")

        assert response.data["count"] == 3
        assert len(response.data["results"]) == 2
        assert response.data["next"] is not None

    def test_non_trainer_is_forbidden(self, client: APIClient) -> None:
        client.force_authenticate(user=create_user(role="retail"))

        response = client.get(TRANSACTIONS_URL)

        assert response.status_code == 403

    def test_unverified_trainer_is_forbidden(self, client: APIClient) -> None:
        client.force_authenticate(user=create_user(is_verified=False))

        response = client.get(TRANSACTIONS_URL)

        assert response.status_code == 403
        assert "не подтверждена" in response.data["detail"]

    def test_anonymous_is_unauthorized(self, client: APIClient) -> None:
        response = client.get(TRANSACTIONS_URL)

        assert response.status_code == 401

    def test_deleted_order_still_shows_number_from_snapshot(self, client: APIClient) -> None:
        """Иначе начисление в истории осталось бы без указания, за что оно."""
        trainer, master = _trainer_with_history()
        order_number = master.order_number_display
        master.delete()
        client.force_authenticate(user=trainer)

        response = client.get(f"{TRANSACTIONS_URL}?type=accrual")

        assert response.status_code == 200
        assert response.data["results"][0]["order_number"] == order_number

    def test_invalid_type_returns_400(self, client: APIClient) -> None:
        """Опечатка в типе не должна выглядеть как «бонусы пропали»."""
        trainer, _ = _trainer_with_history()
        client.force_authenticate(user=trainer)

        response = client.get(f"{TRANSACTIONS_URL}?type=accruals")

        assert response.status_code == 400
        assert "type" in response.data

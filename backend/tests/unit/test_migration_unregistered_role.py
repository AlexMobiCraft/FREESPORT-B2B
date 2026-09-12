"""
Unit-тесты data-миграции 0018: перевод контрагентов 1С в роль unregistered.

Функции миграции вызываются напрямую с реальной моделью: тестовая БД строится
без миграций (--nomigrations), поэтому migrate-раннер здесь неприменим, а
проверить нужно именно логику выборки и обратимость.
"""

from __future__ import annotations

import importlib

import pytest
from django.contrib.auth import get_user_model

# Имя модуля начинается с цифры, поэтому обычный import невозможен
migration_module = importlib.import_module("apps.users.migrations.0018_migrate_1c_users_to_unregistered")

User = get_user_model()

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


class _AppsStub:
    """Подменяет apps.get_model — миграция работает с исторической моделью."""

    def get_model(self, app_label: str, model_name: str):
        return User


def _run_forward():
    migration_module.set_unregistered_role(_AppsStub(), None)


def _run_reverse():
    migration_module.restore_retail_role(_AppsStub(), None)


def _make_1c_record(**overrides) -> User:
    defaults = {
        "email": None,
        "first_name": "Контрагент",
        "company_name": "ООО Тест",
        "role": "retail",
        "created_in_1c": True,
        "verification_status": "unverified",
    }
    defaults.update(overrides)
    user = User(**defaults)
    # Импорт 1С не задаёт пароль — остаётся пустая строка
    user.save()
    return user


class TestForwardMigration:
    def test_converts_1c_record_without_password(self):
        record = _make_1c_record(onec_id="1C-MIGR-001")

        _run_forward()

        record.refresh_from_db()
        assert record.role == "unregistered"

    def test_keeps_portal_retail_user(self):
        portal_user = User.objects.create_user(
            email="portal@example.com",
            password="StrongPassword123!",
            role="retail",
        )

        _run_forward()

        portal_user.refresh_from_db()
        assert portal_user.role == "retail"

    def test_keeps_1c_record_that_has_password(self):
        """Запись с паролем уже принадлежит человеку — не трогаем."""
        linked = _make_1c_record(onec_id="1C-MIGR-002", email="linked@example.com")
        linked.set_password("StrongPassword123!")
        linked.save(update_fields=["password"])

        _run_forward()

        linked.refresh_from_db()
        assert linked.role == "retail"

    def test_keeps_verified_1c_record(self):
        verified = _make_1c_record(onec_id="1C-MIGR-003", verification_status="verified")

        _run_forward()

        verified.refresh_from_db()
        assert verified.role == "retail"

    def test_is_idempotent(self):
        record = _make_1c_record(onec_id="1C-MIGR-004")

        _run_forward()
        _run_forward()

        record.refresh_from_db()
        assert record.role == "unregistered"


class TestReverseMigration:
    def test_restores_retail_for_converted_record(self):
        record = _make_1c_record(onec_id="1C-MIGR-005")
        _run_forward()

        _run_reverse()

        record.refresh_from_db()
        assert record.role == "retail"

    def test_round_trip_preserves_other_fields(self):
        record = _make_1c_record(
            onec_id="1C-MIGR-006",
            company_name="ООО Инвариант",
            tax_id="7707083893",
        )

        _run_forward()
        _run_reverse()

        record.refresh_from_db()
        assert record.role == "retail"
        assert record.company_name == "ООО Инвариант"
        assert record.tax_id == "7707083893"
        assert record.created_in_1c is True
        assert record.verification_status == "unverified"

    def test_does_not_touch_pending_application(self):
        """
        Заявка, поданная после миграции, не понижается обратным переходом.

        Reverse повторяет фильтр forward, поэтому запись с паролем и статусом
        pending остаётся нетронутой.
        """
        applicant = User.objects.create_user(
            email="applicant@example.com",
            password="StrongPassword123!",
            role="unregistered",
            verification_status="pending",
        )

        _run_reverse()

        applicant.refresh_from_db()
        assert applicant.role == "unregistered"

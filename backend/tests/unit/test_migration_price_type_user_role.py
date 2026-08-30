"""
Unit-тесты data-миграции 0054: роль портала для видов цен (стори 40.2).

Функции миграции вызываются напрямую с реальной моделью: тестовая БД может
строиться без миграций (--nomigrations), поэтому migrate-раннер здесь
неприменим, а проверить нужно именно логику выборки, идемпотентность и
обратимость.
"""

from __future__ import annotations

import importlib

import pytest
from django.conf import settings

from apps.products.models import PriceType

migration_module = importlib.import_module("apps.products.migrations.0054_price_type_user_role")

pytestmark = [pytest.mark.django_db]

BY_ROLE = settings.ONEC_EXCHANGE["PRICE_TYPE_BY_ROLE"]
ID_BY_NAME = settings.ONEC_EXCHANGE["PRICE_TYPE_ID_BY_NAME"]

# Шесть исходных видов цен прода + «Опт 4», засеянный миграцией 0053
PRICE_TYPE_SEED = [
    ("РРЦ", "retail_price"),
    ("Опт 1 (300-600 тыс.руб в квартал)", "opt1_price"),
    ("Опт 2 (150-300 тыс.руб в квартал)", "opt2_price"),
    ("Опт 3 (50-150 тыс.руб в квартал)", "opt3_price"),
    ("Опт 4 (до 50 тыс.руб в квартал)", "opt4_price"),
    ("Тренерская", "trainer_price"),
    ("МРЦ", "msrp"),
]

ROLELESS_NAMES = ("РРЦ", "МРЦ")


@pytest.fixture(autouse=True)
def clean_price_types(db):
    """
    Тест начинает с пустого справочника.

    Тестовая БД может строиться и с миграциями (тогда 0053 засеяла «Опт 4»,
    а 0054 проставила роли), и без них — тесты не должны зависеть от способа.
    """
    PriceType.objects.all().delete()


class _AppsStub:
    """Подменяет apps.get_model — миграция работает с реальной моделью."""

    def get_model(self, app_label: str, model_name: str):
        return PriceType


def _run_forward():
    migration_module.set_user_roles(_AppsStub(), None)


def _run_reverse():
    migration_module.clear_user_roles(_AppsStub(), None)


def _seed(opt4_role: str = "wholesale_level4"):
    """
    Заводит справочник в состоянии прода до прогона 0054.

    «Опт 4» приходит уже с ролью — её выставила миграция 0053 вместе с
    самой записью.
    """
    for onec_name, product_field in PRICE_TYPE_SEED:
        role = opt4_role if product_field == "opt4_price" else ""
        PriceType.objects.create(
            onec_id=ID_BY_NAME[onec_name],
            onec_name=onec_name,
            product_field=product_field,
            user_role=role,
            is_active=True,
        )


def _role_of(onec_name: str) -> str:
    return PriceType.objects.get(onec_id=ID_BY_NAME[onec_name]).user_role


class TestForwardMigration:
    def test_assigns_roles_to_five_price_types(self):
        """AC1: пять видов цен получают роль."""
        _seed()

        _run_forward()

        assert _role_of("Опт 1 (300-600 тыс.руб в квартал)") == "wholesale_level1"
        assert _role_of("Опт 2 (150-300 тыс.руб в квартал)") == "wholesale_level2"
        assert _role_of("Опт 3 (50-150 тыс.руб в квартал)") == "wholesale_level3"
        assert _role_of("Опт 4 (до 50 тыс.руб в квартал)") == "wholesale_level4"
        assert _role_of("Тренерская") == "trainer"

    def test_leaves_rrc_and_mrc_empty(self):
        """
        AC1: у «РРЦ» и «МРЦ» роль остаётся пустой.

        Иначе контрагенты-маркетплейсы на виде цен РРЦ уедут в retail.
        """
        _seed()

        _run_forward()

        for onec_name in ROLELESS_NAMES:
            assert _role_of(onec_name) == "", f"{onec_name} не должен получать роль"

    def test_matches_by_guid_when_name_renamed_in_1c(self):
        """Основной ключ поиска — GUID: наименование в 1С могли переименовать."""
        PriceType.objects.create(
            onec_id=ID_BY_NAME["Тренерская"],
            onec_name="Тренерская (архив 2026)",
            product_field="trainer_price",
            user_role="",
        )

        _run_forward()

        assert _role_of("Тренерская") == "trainer"

    def test_matches_by_name_when_guid_differs(self):
        """Запасной ключ — наименование: запись могли завести руками."""
        record = PriceType.objects.create(
            onec_id="manual-guid-trainer",
            onec_name=BY_ROLE["trainer"],
            product_field="trainer_price",
            user_role="",
        )

        _run_forward()

        record.refresh_from_db()
        assert record.user_role == "trainer"

    def test_is_idempotent(self):
        """AC2: повторный прогон не создаёт дублей и не меняет значений."""
        _seed()
        count_before = PriceType.objects.count()

        _run_forward()
        first_pass = {pt.onec_id: pt.user_role for pt in PriceType.objects.all()}
        _run_forward()
        second_pass = {pt.onec_id: pt.user_role for pt in PriceType.objects.all()}

        assert first_pass == second_pass
        assert PriceType.objects.count() == count_before

    def test_does_not_overwrite_manual_role(self):
        """
        AC2: ручная настройка менеджера из админки не затирается.

        «Опт 3» с ролью trainer — правдоподобная ручная правка; слепой
        update() затёр бы её.
        """
        _seed()
        PriceType.objects.filter(onec_id=ID_BY_NAME["Опт 3 (50-150 тыс.руб в квартал)"]).update(user_role="trainer")

        _run_forward()

        assert _role_of("Опт 3 (50-150 тыс.руб в квартал)") == "trainer"

    def test_no_op_on_empty_table(self):
        """Task 5.6: на чистой dev-БД миграция ничего не делает и не падает."""
        assert PriceType.objects.count() == 0

        _run_forward()

        assert PriceType.objects.count() == 0


class TestReverseMigration:
    def test_clears_roles_set_by_this_migration(self):
        """AC2: reverse гасит роли четырёх видов цен, проставленные 0054."""
        _seed()
        _run_forward()

        _run_reverse()

        assert _role_of("Опт 1 (300-600 тыс.руб в квартал)") == ""
        assert _role_of("Опт 2 (150-300 тыс.руб в квартал)") == ""
        assert _role_of("Опт 3 (50-150 тыс.руб в квартал)") == ""
        assert _role_of("Тренерская") == ""

    def test_keeps_opt4_role_seeded_by_0053(self):
        """AC2: роль «Опт 4» поставила миграция 0053 — reverse её не трогает."""
        _seed()
        _run_forward()

        _run_reverse()

        assert _role_of("Опт 4 (до 50 тыс.руб в квартал)") == "wholesale_level4"

    def test_does_not_touch_manual_role(self):
        """Reverse гасит только совпадающую с ожидаемой роль."""
        _seed()
        PriceType.objects.filter(onec_id=ID_BY_NAME["Опт 3 (50-150 тыс.руб в квартал)"]).update(user_role="trainer")
        _run_forward()

        _run_reverse()

        assert _role_of("Опт 3 (50-150 тыс.руб в квартал)") == "trainer"

    def test_clears_manual_role_that_matches_expected_value(self):
        """
        Осознанно ослабленный контракт обратимости (review-находка 40.2).

        Происхождение значения нигде не хранится: поля-маркера у PriceType
        нет, а заводить его — схемная миграция, которую стори запрещает.
        Поэтому reverse гасит и роль, выставленную менеджером вручную, если
        она СОВПАЛА с ожидаемой. Цена ошибки мала: reverse запускается только
        при откате на 0053, а повторное применение 0054 вернёт то же самое
        значение. Роль, отличную от ожидаемой, reverse по-прежнему не трогает
        (см. test_does_not_touch_manual_role).
        """
        _seed()
        # Менеджер выставил ровно ту же роль руками — до прогона миграции
        PriceType.objects.filter(onec_id=ID_BY_NAME["Опт 1 (300-600 тыс.руб в квартал)"]).update(
            user_role="wholesale_level1"
        )
        _run_forward()

        _run_reverse()

        assert _role_of("Опт 1 (300-600 тыс.руб в квартал)") == ""

    def test_round_trip_keeps_record_count(self):
        _seed()
        count_before = PriceType.objects.count()

        _run_forward()
        _run_reverse()

        assert PriceType.objects.count() == count_before

    def test_no_op_on_empty_table(self):
        _run_reverse()

        assert PriceType.objects.count() == 0

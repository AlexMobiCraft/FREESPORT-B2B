"""
Unit-тесты резолвера роли портала по виду цен из соглашения 1С (стори 40.2).

Покрывают все четыре значения ``reason``, случай «GUID известен, роль пуста»,
однократность чтения справочника (NFR-3940-09) и сторож согласованности
прямого и обратного маппинга (FR-40-13).
"""

from __future__ import annotations

import importlib

import pytest
from django.conf import settings

from apps.products.models import PriceType
from apps.users.services.price_type_role import (
    REASON_AMBIGUOUS,
    REASON_NO_AGREEMENT,
    REASON_NO_DATA,
    REASON_RESOLVED,
    REASON_UNKNOWN,
    load_price_type_role_map,
    resolve_role_from_price_types,
)

pytestmark = [pytest.mark.django_db]

GUID_OPT1 = "90d2c899-b3f2-11ea-81c3-00155d3cae02"
GUID_OPT2 = "a91bdb02-b3f2-11ea-81c3-00155d3cae02"
GUID_RRC = "3d1482c4-bd77-11e4-afc8-20cf3073dde3"
GUID_UNKNOWN = "00000000-0000-0000-0000-000000000000"


class _AppsStub:
    """Подменяет apps.get_model — функция миграции вызывается напрямую."""

    def get_model(self, app_label: str, model_name: str):
        return PriceType


def _make_price_type(onec_id: str, onec_name: str, product_field: str, user_role: str = "", is_active: bool = True):
    return PriceType.objects.create(
        onec_id=onec_id,
        onec_name=onec_name,
        product_field=product_field,
        user_role=user_role,
        is_active=is_active,
    )


@pytest.fixture(autouse=True)
def clean_price_types(db):
    """
    Тест начинает с пустого справочника.

    Тестовая БД может строиться и с миграциями (тогда 0053 засеяла «Опт 4»,
    а 0054 проставила роли), и без них — тесты не должны зависеть от способа.
    """
    PriceType.objects.all().delete()


@pytest.fixture
def price_types(clean_price_types):
    """Три вида цен: два оптовых с ролями и РРЦ с намеренно пустой ролью."""
    _make_price_type(GUID_OPT1, "Опт 1 (300-600 тыс.руб в квартал)", "opt1_price", "wholesale_level1")
    _make_price_type(GUID_OPT2, "Опт 2 (150-300 тыс.руб в квартал)", "opt2_price", "wholesale_level2")
    _make_price_type(GUID_RRC, "РРЦ", "retail_price", "")


class TestResolveRoleFromPriceTypes:
    """AC6-AC11: ветвление резолвера."""

    def test_no_agreement_status_wins(self, price_types):
        """AC6: 1С сообщила об отсутствии соглашения — роль не определяется."""
        result = resolve_role_from_price_types([], agreement_status="НетСоглашения")

        assert result.role is None
        assert result.reason == REASON_NO_AGREEMENT
        assert result.matched == []

    def test_no_agreement_wins_over_non_empty_guids(self, price_types):
        """
        AC6 + Task 4.3: противоречивый вход «НетСоглашения + непустой GUID».

        Ветка статуса безусловно приоритетна: выдавать роль по такому входу
        опаснее, чем не выдавать никакой.
        """
        result = resolve_role_from_price_types([GUID_OPT1], agreement_status="НетСоглашения")

        assert result.role is None
        assert result.reason == REASON_NO_AGREEMENT
        assert result.matched == []

    def test_empty_guids_without_status_is_no_data(self, price_types):
        """AC7: данных нет вовсе — причина отличается от no_agreement."""
        result = resolve_role_from_price_types([])

        assert result.role is None
        assert result.reason == REASON_NO_DATA
        assert result.matched == []

    def test_blank_guids_are_treated_as_no_data(self, price_types):
        """AC7: пустые строки в списке равнозначны отсутствию данных."""
        result = resolve_role_from_price_types(["", "   "])

        assert result.role is None
        assert result.reason == REASON_NO_DATA

    def test_unknown_guid_is_unknown_price_type(self, price_types):
        """AC8: GUID не найден в справочнике."""
        result = resolve_role_from_price_types([GUID_UNKNOWN])

        assert result.role is None
        assert result.reason == REASON_UNKNOWN
        assert result.matched == []

    def test_known_guid_with_empty_role_is_unknown_price_type(self, price_types):
        """
        AC9: РРЦ известен порталу, но роли не несёт.

        Трактуется наравне с неизвестным — иначе контрагенты-маркетплейсы
        на виде цен РРЦ уехали бы в retail.
        """
        result = resolve_role_from_price_types([GUID_RRC])

        assert result.role is None
        assert result.reason == REASON_UNKNOWN
        assert result.matched == []

    def test_inactive_price_type_is_unknown(self, price_types):
        """Деактивированный вид цен в маппинг не попадает."""
        _make_price_type(
            "b86fb8c5-ea2d-11eb-81f3-00155d3cae02",
            "Тренерская",
            "trainer_price",
            "trainer",
            is_active=False,
        )

        result = resolve_role_from_price_types(["b86fb8c5-ea2d-11eb-81f3-00155d3cae02"])

        assert result.role is None
        assert result.reason == REASON_UNKNOWN

    def test_two_guids_with_roles_are_ambiguous(self, price_types):
        """AC10: два вида цен с ролями — два соглашения, однозначности нет."""
        result = resolve_role_from_price_types([GUID_OPT1, GUID_OPT2])

        assert result.role is None
        assert result.reason == REASON_AMBIGUOUS
        assert set(result.matched) == {GUID_OPT1, GUID_OPT2}

    def test_two_guids_with_same_role_are_still_ambiguous(self, price_types):
        """
        AC10: совпадение ролей сегодня не делает вход однозначным —
        маппинг редактируем из админки и может разойтись завтра.
        """
        twin_guid = "11111111-1111-1111-1111-111111111111"
        _make_price_type(twin_guid, "Опт 1 (копия)", "opt1_price", "wholesale_level1")

        result = resolve_role_from_price_types([GUID_OPT1, twin_guid])

        assert result.role is None
        assert result.reason == REASON_AMBIGUOUS
        assert set(result.matched) == {GUID_OPT1, twin_guid}

    def test_single_role_bearing_guid_resolves(self, price_types):
        """AC11: ровно один GUID несёт роль — она и возвращается."""
        result = resolve_role_from_price_types([GUID_OPT1])

        assert result.role == "wholesale_level1"
        assert result.reason == REASON_RESOLVED
        assert result.matched == [GUID_OPT1]

    def test_role_bearing_guid_among_roleless_resolves(self, price_types):
        """AC11: соседство с РРЦ и неизвестным GUID не мешает разрешению."""
        result = resolve_role_from_price_types([GUID_RRC, GUID_OPT2, GUID_UNKNOWN])

        assert result.role == "wholesale_level2"
        assert result.reason == REASON_RESOLVED
        assert result.matched == [GUID_OPT2]

    def test_guid_case_is_ignored(self, price_types):
        """Task 4.4: GUID из 1С может прийти в верхнем регистре."""
        result = resolve_role_from_price_types([GUID_OPT1.upper()])

        assert result.role == "wholesale_level1"
        assert result.reason == REASON_RESOLVED
        assert result.matched == [GUID_OPT1]

    def test_agreement_status_whitespace_and_case_ignored(self, price_types):
        """Значение реквизита приходит как есть — пробелы не должны ломать ветку."""
        result = resolve_role_from_price_types([GUID_OPT1], agreement_status="  нетсоглашения ")

        assert result.reason == REASON_NO_AGREEMENT


class TestPriceTypeRoleMapLoading:
    """AC12: справочник читается один раз на сессию импорта."""

    def test_load_map_uses_single_query(self, price_types, django_assert_num_queries):
        with django_assert_num_queries(1):
            mapping = load_price_type_role_map()

        # РРЦ с пустой ролью в маппинг не попадает
        assert mapping == {
            GUID_OPT1: "wholesale_level1",
            GUID_OPT2: "wholesale_level2",
        }

    def test_resolver_with_ready_map_does_not_touch_db(self, price_types, django_assert_num_queries):
        mapping = load_price_type_role_map()

        with django_assert_num_queries(0):
            resolve_role_from_price_types([GUID_OPT1], role_map=mapping)
            resolve_role_from_price_types([GUID_OPT2], role_map=mapping)
            resolve_role_from_price_types([GUID_UNKNOWN], role_map=mapping)

    def test_resolver_reads_db_when_map_not_passed(self, price_types, django_assert_num_queries):
        with django_assert_num_queries(1):
            resolve_role_from_price_types([GUID_OPT1])

    def test_loader_is_not_cached(self):
        """
        AC12: прямой запрет lru_cache.

        Маппинг правится менеджером из админки, а Celery-воркер живёт долго
        и с кэшем продолжил бы отдавать отменённое значение.
        """
        assert not hasattr(load_price_type_role_map, "cache_clear")
        assert not hasattr(resolve_role_from_price_types, "cache_clear")

    def test_map_reflects_admin_edit_without_restart(self, price_types):
        """Правка справочника видна следующему вызову без перезапуска процесса."""
        assert resolve_role_from_price_types([GUID_OPT1]).role == "wholesale_level1"

        PriceType.objects.filter(onec_id=GUID_OPT1).update(user_role="")

        result = resolve_role_from_price_types([GUID_OPT1])
        assert result.role is None
        assert result.reason == REASON_UNKNOWN


class TestGuidCaseCollisions:
    """
    Review-находка 40.2: ключ маппинга приводится к нижнему регистру, а
    уникальность ``PriceType.onec_id`` в PostgreSQL регистрозависима.

    Значит, две записи с одним GUID в разном регистре — легальное состояние
    БД (данные до нормализации формы, импорт priceLists). Если роли у них
    расходятся, победитель определялся бы порядком выборки, то есть
    произвольно. Роль в такой ситуации не выдаётся вовсе.
    """

    def test_conflicting_roles_on_case_variants_are_not_resolved(self, clean_price_types):
        """Расхождение ролей у регистровых двойников — роль не выдаётся."""
        _make_price_type(GUID_OPT1, "Опт 1 (300-600 тыс.руб в квартал)", "opt1_price", "wholesale_level1")
        _make_price_type(GUID_OPT1.upper(), "Опт 1 (двойник в верхнем регистре)", "opt2_price", "wholesale_level2")

        result = resolve_role_from_price_types([GUID_OPT1])

        assert result.role is None
        assert result.reason == REASON_UNKNOWN
        assert result.matched == []

    def test_conflicting_pair_does_not_hide_other_price_types(self, clean_price_types):
        """Конфликт гасит только свой GUID, остальной справочник работает."""
        _make_price_type(GUID_OPT1, "Опт 1 (300-600 тыс.руб в квартал)", "opt1_price", "wholesale_level1")
        _make_price_type(GUID_OPT1.upper(), "Опт 1 (двойник в верхнем регистре)", "opt2_price", "wholesale_level2")
        _make_price_type(GUID_OPT2, "Опт 2 (150-300 тыс.руб в квартал)", "opt2_price", "wholesale_level2")

        assert load_price_type_role_map() == {GUID_OPT2: "wholesale_level2"}
        assert resolve_role_from_price_types([GUID_OPT2]).role == "wholesale_level2"

    def test_same_role_on_case_variants_still_resolves(self, clean_price_types):
        """
        Одинаковая роль у двойников неоднозначности не создаёт: какой бы
        записью ни разрешился GUID, ответ один и тот же.
        """
        _make_price_type(GUID_OPT1, "Опт 1 (300-600 тыс.руб в квартал)", "opt1_price", "wholesale_level1")
        _make_price_type(GUID_OPT1.upper(), "Опт 1 (двойник в верхнем регистре)", "opt1_price", "wholesale_level1")

        result = resolve_role_from_price_types([GUID_OPT1])

        assert result.role == "wholesale_level1"
        assert result.reason == REASON_RESOLVED

    def test_collision_detection_keeps_single_query(self, clean_price_types, django_assert_num_queries):
        """AC12 не нарушен: выявление конфликтов идёт по той же выборке."""
        _make_price_type(GUID_OPT1, "Опт 1 (300-600 тыс.руб в квартал)", "opt1_price", "wholesale_level1")
        _make_price_type(GUID_OPT1.upper(), "Опт 1 (двойник в верхнем регистре)", "opt2_price", "wholesale_level2")

        with django_assert_num_queries(1):
            load_price_type_role_map()


class TestForwardBackwardMappingConsistency:
    """
    AC13 (FR-40-13): сторож согласованности прямого и обратного маппинга.

    Цепочка PRICE_TYPE_BY_ROLE → PRICE_TYPE_ID_BY_NAME → PriceType.user_role
    обязана возвращать исходную роль.

    Роли исключены намеренно:
      retail, admin  — обе отображаются на «РРЦ», у которого user_role
                       намеренно пуст (иначе маркетплейсы уедут в retail);
      federation_rep — вид цен «Партнер» на портал не выгружается и записи
                       PriceType не имеет.
    """

    ROLES_WITH_PRICE_TYPE = (
        "wholesale_level1",
        "wholesale_level2",
        "wholesale_level3",
        "wholesale_level4",
        "trainer",
    )

    PRODUCT_FIELD_BY_ROLE = {
        "wholesale_level1": "opt1_price",
        "wholesale_level2": "opt2_price",
        "wholesale_level3": "opt3_price",
        "wholesale_level4": "opt4_price",
        "trainer": "trainer_price",
    }

    def _seed_from_settings(self):
        """Заводит записи справочника с ПУСТОЙ ролью — её проставит миграция."""
        by_role = settings.ONEC_EXCHANGE["PRICE_TYPE_BY_ROLE"]
        id_by_name = settings.ONEC_EXCHANGE["PRICE_TYPE_ID_BY_NAME"]

        seeded = {}
        for role in self.ROLES_WITH_PRICE_TYPE:
            onec_name = by_role[role]
            guid = id_by_name[onec_name]
            _make_price_type(guid, onec_name, self.PRODUCT_FIELD_BY_ROLE[role], user_role="")
            seeded[role] = guid
        return seeded

    def test_round_trip_returns_original_role(self):
        seeded = self._seed_from_settings()

        migration = importlib.import_module("apps.products.migrations.0054_price_type_user_role")
        migration.set_user_roles(_AppsStub(), None)

        for role, guid in seeded.items():
            result = resolve_role_from_price_types([guid])
            assert result.reason == REASON_RESOLVED, f"роль {role} не разрешилась"
            assert result.role == role, f"роль {role} разрешилась в {result.role}"

    def test_settings_cover_all_expected_roles(self):
        """Настройки не должны потерять вид цен для роли из списка."""
        by_role = settings.ONEC_EXCHANGE["PRICE_TYPE_BY_ROLE"]
        id_by_name = settings.ONEC_EXCHANGE["PRICE_TYPE_ID_BY_NAME"]

        for role in self.ROLES_WITH_PRICE_TYPE:
            assert role in by_role, f"нет вида цен для роли {role}"
            assert by_role[role] in id_by_name, f"нет GUID для вида цен {by_role[role]}"

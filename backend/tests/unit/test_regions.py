"""
Unit-тесты справочника регионов (стори 42.3).

Покрывает:
- REGION_NAMES и region_name — названия кодов, коды вне справочника (AC1);
- unassigned_regions — коды без активного правила inn_region с активным менеджером
  (AC2; заблокированный менеджер — стори 42.7, решение 17).
"""

from __future__ import annotations

import importlib

import pytest
from django.contrib.auth.models import Group

from apps.common.models import ManagerRoutingRule
from apps.common.regions import REGION_NAMES, Region, region_name, unassigned_regions
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

INN_REGION = ManagerRoutingRule.MATCH_INN_REGION
COUNTRY = ManagerRoutingRule.MATCH_COUNTRY
FALLBACK = ManagerRoutingRule.MATCH_FALLBACK


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    """Изолируем тесты от правил, засеянных data-миграцией common/0018."""
    ManagerRoutingRule.objects.all().delete()


@pytest.fixture
def manager() -> User:
    user = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@freesportopt.ru",
        password="StrongPassword123!",
        is_staff=True,
    )
    user.groups.add(Group.objects.get_or_create(name=MANAGERS_GROUP)[0])
    return user


def rule(match_type: str, match_value: str, manager: User | None = None, active: bool = True) -> ManagerRoutingRule:
    return ManagerRoutingRule.objects.create(
        match_type=match_type,
        match_value=match_value,
        manager=manager,
        manager_email="" if manager else f"rule_{get_unique_suffix()}@freesportopt.ru",
        is_active=active,
    )


class TestRegionNames:
    def test_directory_has_97_two_digit_codes(self):
        assert len(REGION_NAMES) == 97
        assert all(len(code) == 2 and code.isdigit() for code in REGION_NAMES)
        assert list(REGION_NAMES) == sorted(REGION_NAMES)

    @pytest.mark.parametrize("code", ["01", "79", "80", "85", "89", "90", "91", "92", "93", "94", "95", "97"])
    def test_known_code_has_name(self, code):
        assert region_name(code) == REGION_NAMES[code]
        assert region_name(code) != code

    def test_codes_96_and_98_absent(self):
        assert "96" not in REGION_NAMES
        assert "98" not in REGION_NAMES

    def test_largest_taxpayers(self):
        assert region_name("99") == "Крупнейшие налогоплательщики"

    def test_moscow_new_inn(self):
        assert region_name("97") == "г. Москва (ИНН с 2014 г.)"

    @pytest.mark.parametrize("code", ["96", "00", "7", "ab"])
    def test_unknown_code_returned_as_is(self, code):
        assert region_name(code) == code

    @pytest.mark.parametrize("code", [None, ""])
    def test_empty_code(self, code):
        assert region_name(code) == ""

    def test_every_seed_code_in_directory(self):
        seed = importlib.import_module("apps.common.migrations.0018_seed_manager_routing_rules")
        seed_codes = {code for _district, _manager, codes in seed.REGION_GROUPS for code in codes}
        assert seed_codes
        assert seed_codes - set(REGION_NAMES) == set()


class TestUnassignedRegions:
    def test_no_rules_all_codes(self):
        regions = unassigned_regions()
        assert [region.code for region in regions] == list(REGION_NAMES)
        assert regions[0] == Region(code="01", name="Республика Адыгея")

    def test_rule_with_manager_covers_code(self, manager):
        rule(INN_REGION, "23", manager)
        codes = [region.code for region in unassigned_regions()]
        assert "23" not in codes
        assert len(codes) == 96

    def test_rule_with_email_only_not_covering(self):
        rule(INN_REGION, "24")
        assert "24" in [region.code for region in unassigned_regions()]

    def test_inactive_rule_not_covering(self, manager):
        rule(INN_REGION, "25", manager, active=False)
        assert "25" in [region.code for region in unassigned_regions()]

    def test_rule_with_blocked_manager_not_covering(self, manager):
        """Клиенты региона заблокированного менеджера уходят на резерв (стори 42.7, решение 17)."""
        rule(INN_REGION, "26", manager)
        manager.is_active = False
        manager.save(update_fields=["is_active", "updated_at"])
        assert "26" in [region.code for region in unassigned_regions()]

    def test_country_and_fallback_rules_ignored(self, manager):
        rule(COUNTRY, "Беларусь", manager)
        rule(FALLBACK, "default", manager)
        assert [region.code for region in unassigned_regions()] == list(REGION_NAMES)

    def test_all_codes_covered(self, manager):
        for code in REGION_NAMES:
            rule(INN_REGION, code, manager)
        assert unassigned_regions() == []

    def test_sorted_by_code_with_names(self, manager):
        for code in ("01", "50", "97"):
            rule(INN_REGION, code, manager)
        regions = unassigned_regions()
        codes = [region.code for region in regions]
        assert codes == sorted(codes)
        assert all(region.name == REGION_NAMES[region.code] for region in regions)

    def test_single_query(self, manager, django_assert_num_queries):
        rule(INN_REGION, "23", manager)
        rule(INN_REGION, "77", manager)
        with django_assert_num_queries(1):
            unassigned_regions()

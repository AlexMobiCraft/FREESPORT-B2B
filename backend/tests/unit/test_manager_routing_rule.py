"""
Unit-тесты модели ManagerRoutingRule (стори 42.2, AC2).

Покрывает:
- одно активное правило на код региона и на страну (full_clean и ограничение БД);
- несколько резервных правил без менеджера, но одно резервное с менеджером;
- clean(): менеджер или email обязателен, формат кода региона, Россия как страна;
- __str__ с менеджером и без;
- правка полей, не влияющих на ответственного, не пересчитывает клиентов.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

from apps.common.models import ManagerRoutingRule
from apps.users.models import User
from apps.users.staff_roles import MANAGERS_GROUP, SUPERVISORS_GROUP
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

INN_REGION = ManagerRoutingRule.MATCH_INN_REGION
COUNTRY = ManagerRoutingRule.MATCH_COUNTRY
FALLBACK = ManagerRoutingRule.MATCH_FALLBACK

DUPLICATE_KEY_MESSAGE = "Для этого кода региона или страны уже есть активное правило. Выключите его или измените."
DUPLICATE_FALLBACK_MESSAGE = (
    "Ответственного по резервному правилу может давать только одно активное правило с менеджером."
)


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    """Изолируем тесты от правил, засеянных data-миграцией common/0018."""
    ManagerRoutingRule.objects.all().delete()


def make_staff(group: str = MANAGERS_GROUP) -> User:
    user = User.objects.create_user(
        email=f"staff_{get_unique_suffix()}@freesportopt.ru", password="StrongPassword123!", is_staff=True
    )
    user.groups.add(Group.objects.get_or_create(name=group)[0])
    return user


def build(match_type=INN_REGION, match_value="23", manager=None, email="m@freesportopt.ru", active=True):
    return ManagerRoutingRule(
        match_type=match_type, match_value=match_value, manager=manager, manager_email=email, is_active=active
    )


def error_messages(exc: ValidationError) -> list[str]:
    return exc.messages


class TestOneActiveRulePerKey:
    @pytest.mark.parametrize("match_type,value", [(INN_REGION, "23"), (COUNTRY, "Беларусь")])
    def test_second_active_rejected(self, match_type, value):
        build(match_type, value).save()
        duplicate = build(match_type, value, email="other@freesportopt.ru")
        with pytest.raises(ValidationError) as exc:
            duplicate.full_clean()
        assert DUPLICATE_KEY_MESSAGE in error_messages(exc.value)
        with pytest.raises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_inactive_duplicate_allowed(self):
        build().save()
        duplicate = build(active=False, email="other@freesportopt.ru")
        duplicate.full_clean()
        duplicate.save()
        assert ManagerRoutingRule.objects.filter(match_value="23").count() == 2

    def test_two_fallbacks_without_manager_allowed(self):
        chief = make_staff(SUPERVISORS_GROUP)
        build(FALLBACK, "default", manager=chief, email="").save()
        for email in ("admin@freesportopt.ru", "boss@freesportopt.ru"):
            extra = build(FALLBACK, "default", email=email)
            extra.full_clean()
            extra.save()
        assert ManagerRoutingRule.objects.filter(match_type=FALLBACK).count() == 3

    def test_second_fallback_with_manager_rejected(self):
        build(FALLBACK, "default", manager=make_staff(SUPERVISORS_GROUP), email="").save()
        duplicate = build(FALLBACK, "default", manager=make_staff(SUPERVISORS_GROUP), email="")
        with pytest.raises(ValidationError) as exc:
            duplicate.full_clean()
        assert DUPLICATE_FALLBACK_MESSAGE in error_messages(exc.value)
        with pytest.raises(IntegrityError), transaction.atomic():
            duplicate.save()

    def test_inactive_fallback_with_manager_allowed(self):
        build(FALLBACK, "default", manager=make_staff(SUPERVISORS_GROUP), email="").save()
        extra = build(FALLBACK, "default", manager=make_staff(SUPERVISORS_GROUP), email="", active=False)
        extra.full_clean()
        extra.save()


class TestClean:
    def test_requires_manager_or_email(self):
        with pytest.raises(ValidationError) as exc:
            build(email="").full_clean()
        assert "Укажите менеджера или email для писем" in error_messages(exc.value)

    def test_manager_without_email_is_valid(self):
        build(manager=make_staff(), email="").full_clean()

    @pytest.mark.parametrize("code", ["7", "2a", "123"])
    def test_region_code_two_digits(self, code):
        with pytest.raises(ValidationError) as exc:
            build(match_value=code).full_clean()
        assert exc.value.message_dict["match_value"] == ["Код региона — две цифры, например 23"]

    def test_russia_as_country_rejected(self):
        with pytest.raises(ValidationError) as exc:
            build(COUNTRY, "Россия").full_clean()
        assert exc.value.message_dict["match_value"] == ["Для России правило задаётся кодом региона"]

    @pytest.mark.parametrize("value", ["", "   "])
    def test_country_requires_value(self, value):
        """Пустая страна: пересчёт отдал бы правило клиентам без страны, а разрешение считает их Россией."""
        with pytest.raises(ValidationError) as exc:
            build(COUNTRY, value).full_clean()
        assert exc.value.message_dict["match_value"] == ["Укажите страну"]

    def test_normalizes_email_and_value(self):
        rule = build(match_value=" 23 ", email="Manager@FreeSportOpt.RU")
        rule.full_clean()
        assert (rule.match_value, rule.manager_email) == ("23", "manager@freesportopt.ru")


class TestStr:
    def test_with_manager(self):
        manager = make_staff()
        assert str(build(manager=manager, email="old@freesportopt.ru")) == (
            f"Код субъекта РФ (по ИНН):23 → {manager.email}"
        )

    def test_without_manager(self):
        assert str(build()) == "Код субъекта РФ (по ИНН):23 → m@freesportopt.ru"

    def test_manager_without_email_shows_manager_email(self):
        # Письмо в этом случае уходит на manager_email (region_routing._rule_emails).
        manager = make_staff()
        manager.email = ""
        assert str(build(manager=manager, email="old@freesportopt.ru")) == (
            "Код субъекта РФ (по ИНН):23 → old@freesportopt.ru"
        )


class TestSignalCost:
    def test_email_only_change_does_not_touch_users(self):
        rule = build(manager=make_staff())
        rule.save()
        rule.manager_email = "new@freesportopt.ru"
        rule.manager_name = "Новое имя"
        rule.federal_district = "ЮФО"
        with CaptureQueriesContext(connection) as ctx:
            rule.save()
        assert not [q for q in ctx.captured_queries if 'UPDATE "users"' in q["sql"]]
        # Чтение прежнего состояния правила и сам UPDATE правила — и только.
        assert len(ctx.captured_queries) == 2

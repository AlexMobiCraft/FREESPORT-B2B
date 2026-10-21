"""
Unit-тесты `Is1CExchangeUser` (стори 42.1, AC3): обмен 1С только по праву
`integrations.can_exchange_1c`, `is_staff` доступа не даёт.
"""

from __future__ import annotations

import pytest
from django.contrib.auth.models import AnonymousUser, Permission
from django.test import RequestFactory

from apps.integrations.onec_exchange.permissions import Is1CExchangeUser
from apps.users.models import User
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def check(user) -> bool:
    request = RequestFactory().get("/api/integration/1c/exchange/")
    request.user = user
    return Is1CExchangeUser().has_permission(request, view=None)


def make_user(**extra) -> User:
    return User.objects.create_user(email=f"exchange_{get_unique_suffix()}@example.com", password="pass123", **extra)


def grant_exchange(user: User) -> User:
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="integrations", codename="can_exchange_1c")
    )
    # Свежий объект: кэш прав пользователя не должен помнить состояние до выдачи.
    return User.objects.get(pk=user.pk)


def test_anonymous_is_denied():
    assert check(AnonymousUser()) is False


def test_staff_without_permission_is_denied():
    assert check(make_user(is_staff=True)) is False


def test_regular_user_without_permission_is_denied():
    assert check(make_user()) is False


def test_permission_without_staff_is_allowed():
    assert check(grant_exchange(make_user())) is True


def test_superuser_is_allowed():
    superuser = User.objects.create_superuser(email=f"su_{get_unique_suffix()}@example.com", password="pass123")

    assert check(superuser) is True


def test_inactive_user_with_permission_is_denied():
    assert check(grant_exchange(make_user(is_active=False))) is False

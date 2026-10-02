"""
Эквивалентность queryset-предиката и property «непривязанная запись 1С».

`User.objects.unlinked_1c_records()` показывает менеджеру кандидатов, а
`user.is_unlinked_1c_record` проверяет их под блокировкой при привязке и
пропускает регистрацию по чужому ИНН. Расхождение между ними означает, что
показанный кандидат не пройдёт проверку — либо наоборот, что регистрация
заблокирована по записи, которую список считает свободной.

Один параметризованный тест вместо дюжины отдельных: матрица состояний
password × created_in_1c × verification_status.
"""

from __future__ import annotations

import itertools
import time

import pytest
from django.db.models import Exists, Q

from apps.users.models import User, matches_q

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

_counter = itertools.count()

# Пароли: пустая строка (оставляет импорт), unusable-хеш (create_user(None)),
# обычный usable-хеш и None (недостижим в БД — колонка NOT NULL).
PASSWORD_STATES = {
    "empty": "",
    "unusable": "!8sJk2mQpZx0Lw1",
    "usable": "pbkdf2_sha256$720000$abc$def=",
    "none": None,
}
VERIFICATION_STATES = ["unverified", "verified", "pending"]


def unique_email() -> str:
    return f"predicate_{time.time_ns()}_{next(_counter)}@example.com"


@pytest.mark.parametrize("password_state", list(PASSWORD_STATES))
@pytest.mark.parametrize("created_in_1c", [True, False])
@pytest.mark.parametrize("verification_status", VERIFICATION_STATES)
@pytest.mark.parametrize("role", [User.ROLE_UNREGISTERED, "wholesale_level1"])
def test_property_matches_queryset_predicate(password_state, created_in_1c, verification_status, role):
    password = PASSWORD_STATES[password_state]
    user = User(
        email=unique_email(),
        first_name="Предикат",
        last_name="Тестов",
        role=role,
        created_in_1c=created_in_1c,
        verification_status=verification_status,
        password=password,
    )

    # Роль варьируется вместе с остальными осями: предикат, ошибочно
    # связавший роль и пароль через OR, прошёл бы раздельные параметризации
    # и сделал живой B2B-аккаунт валидным источником привязки.
    expected = (
        role == User.ROLE_UNREGISTERED
        and created_in_1c
        and verification_status == "unverified"
        and password_state in {"empty", "unusable", "none"}
    )
    assert user.is_unlinked_1c_record is expected

    if password is None:
        # Колонка password объявлена NOT NULL: такая строка в БД недостижима,
        # сравнивать с queryset нечего. Property при этом обязана отвечать,
        # потому что вызывается и на несохранённых экземплярах.
        return

    user.save()
    in_queryset = User.objects.unlinked_1c_records().filter(pk=user.pk).exists()
    assert in_queryset is user.is_unlinked_1c_record


@pytest.mark.parametrize("role", [role for role, _ in User.ROLE_CHOICES])
def test_role_condition_matches_queryset_predicate(role):
    """Непривязанной может быть только запись с ролью unregistered."""
    user = User(
        email=unique_email(),
        first_name="Роль",
        last_name="Тестов",
        role=role,
        created_in_1c=True,
        verification_status="unverified",
        password="",
    )
    user.save()

    in_queryset = User.objects.unlinked_1c_records().filter(pk=user.pk).exists()
    assert in_queryset is user.is_unlinked_1c_record
    assert in_queryset is (role == User.ROLE_UNREGISTERED)


def test_matches_q_refuses_conditions_it_cannot_evaluate():
    """
    Молча вернуть False на незнакомом условии значит вернуть не то множество,
    что вернёт SQL, — ровно то расхождение, ради которого написана matches_q.
    """
    user = User(role="wholesale_level1")

    with pytest.raises(ValueError):
        matches_q(Q(role="wholesale_level1") ^ Q(created_in_1c=True), user)

    with pytest.raises(ValueError):
        matches_q(Q(role="wholesale_level1") & Q(role__icontains="wholesale"), user)

    with pytest.raises(ValueError):
        matches_q(Q(Exists(User.objects.all())), user)


def test_b2b_roles_constant_drives_is_b2b_user():
    """Список B2B-ролей имеет один источник истины."""
    for role, _ in User.ROLE_CHOICES:
        user = User(role=role)
        assert user.is_b2b_user is (role in User.B2B_ROLES)

    assert "admin" not in User.B2B_ROLES
    assert User.ROLE_UNREGISTERED not in User.B2B_ROLES

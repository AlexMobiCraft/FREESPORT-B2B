"""
Ответственный менеджер клиента по правилу региона (эпик 42, стори 42.2).

Единственный источник логики назначения. Ключ региона клиента вычисляется
так же, как для письма о регистрации (``region_routing``): страна, если она
не Россия, иначе первые две цифры ИНН. Ответственного даёт активное правило
этого ключа с выбранным ``manager``, иначе — резервное правило с
``manager``. Правило без учётной записи ответственного не даёт.

Ручное назначение (``responsible_manager_manual``) и учётные записи
сотрудников автоматика не трогает.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.db.models.functions import Substr

from apps.common.models import ManagerRoutingRule
from apps.users.models import User
from apps.users.staff_roles import STAFF_ROLE_GROUPS, staff_accounts_q

logger = logging.getLogger(__name__)

SOURCE_REGION = ManagerRoutingRule.MATCH_INN_REGION
SOURCE_COUNTRY = ManagerRoutingRule.MATCH_COUNTRY
SOURCE_FALLBACK = ManagerRoutingRule.MATCH_FALLBACK
SOURCE_NONE = "none"

# Пустая страна приравнивается к России — и в region_key, и в массовом пересчёте.
RUSSIA_COUNTRY_VALUES = (User.COUNTRY_RUSSIA, "")

RegionKey = tuple[str, str]


@dataclass(frozen=True)
class ResponsibleResolution:
    manager: User | None
    source: str  # одна из SOURCE_*


def region_key(country: str | None, tax_id: str | None) -> RegionKey | None:
    """
    Ключ правила для клиента: ``("country", страна)``, ``("inn_region", код)`` или ``None``.

    ИНН не нормализуется: импорт 1С пишет его без ``strip()``, и ИНН с
    пробелом в начале региона не даёт — так же, как в письме о регистрации.
    """
    if country and country != User.COUNTRY_RUSSIA:
        return (ManagerRoutingRule.MATCH_COUNTRY, country)
    code = (tax_id or "")[:2]
    if len(code) == 2 and code.isdigit():
        return (ManagerRoutingRule.MATCH_INN_REGION, code)
    return None


def resolve_responsible_for_key(key: RegionKey | None) -> ResponsibleResolution:
    """Ответственный для ключа региона; ``None`` — ключа нет, сразу резерв."""
    active_with_manager = ManagerRoutingRule.objects.filter(is_active=True, manager__isnull=False).select_related(
        "manager"
    )
    if key is not None:
        rule = active_with_manager.filter(match_type=key[0], match_value=key[1]).first()
        if rule is not None:
            return ResponsibleResolution(manager=rule.manager, source=key[0])
    fallback = active_with_manager.filter(match_type=ManagerRoutingRule.MATCH_FALLBACK).order_by("pk").first()
    if fallback is not None:
        return ResponsibleResolution(manager=fallback.manager, source=SOURCE_FALLBACK)
    return ResponsibleResolution(manager=None, source=SOURCE_NONE)


def resolve_responsible(country: str | None, tax_id: str | None) -> ResponsibleResolution:
    return resolve_responsible_for_key(region_key(country, tax_id))


def is_staff_account(user: User) -> bool:
    """Сотрудник: is_staff, суперпользователь, role="admin" или член группы роли."""
    if user.is_staff or user.is_superuser or user.role == "admin":
        return True
    # У несохранённой записи групп нет.
    if not user.pk:
        return False
    return user.groups.filter(name__in=STAFF_ROLE_GROUPS).exists()


def assign_responsible_manager(user: User) -> bool:
    """
    Назначить ответственного по правилу региона в памяти, без сохранения.

    Возвращает ``True``, если значение изменилось. Ручное назначение и
    учётные записи сотрудников не трогает.
    """
    if user.responsible_manager_manual or is_staff_account(user):
        return False
    manager = resolve_responsible(user.country, user.tax_id).manager
    new_id = manager.pk if manager is not None else None
    if user.responsible_manager_id == new_id:
        return False
    user.responsible_manager = manager
    return True


def reassign_clients_for_key(key: RegionKey | None) -> int:
    """
    Пересчитать ответственного у клиентов ключа одним ``UPDATE``.

    ``key=None`` — резерв: клиенты, чей ключ не покрыт активным правилом с
    ``manager``. Возвращает число клиентов, у которых ответственный сменился.
    """
    target = resolve_responsible_for_key(key).manager
    clients = User.objects.filter(responsible_manager_manual=False).exclude(staff_accounts_q())
    russian = Q(country__in=RUSSIA_COUNTRY_VALUES)

    if key is None:
        covered_codes: set[str] = set()
        covered_countries: set[str] = set()
        covered = ManagerRoutingRule.objects.filter(
            is_active=True,
            manager__isnull=False,
            match_type__in=[ManagerRoutingRule.MATCH_INN_REGION, ManagerRoutingRule.MATCH_COUNTRY],
        ).values_list("match_type", "match_value")
        for match_type, match_value in covered:
            if match_type == ManagerRoutingRule.MATCH_INN_REGION:
                covered_codes.add(match_value)
            else:
                covered_countries.add(match_value)
        clients = clients.annotate(region=Substr("tax_id", 1, 2)).filter(
            (russian & ~Q(region__in=covered_codes)) | (~russian & ~Q(country__in=covered_countries))
        )
    elif key[0] == ManagerRoutingRule.MATCH_INN_REGION:
        clients = clients.filter(russian).annotate(region=Substr("tax_id", 1, 2)).filter(region=key[1])
    else:
        clients = clients.filter(country=key[1])

    updated = clients.exclude(responsible_manager=target).update(responsible_manager=target)
    logger.info(
        "Ответственный менеджер пересчитан по правилу региона: ключ %s, переведено клиентов %s",
        key,
        updated,
        extra={
            "action": "responsible_manager_reassign",
            "key": key,
            "manager_id": target.pk if target is not None else None,
            "updated": updated,
        },
    )
    return updated


# Поля правила, от которых зависит назначение ответственного.
RULE_STATE_FIELDS = ("match_type", "match_value", "is_active", "manager_id")


def _rule_effect(state: dict[str, Any] | None) -> tuple[RegionKey | None, int] | None:
    """Что правило даёт ответственному: ``(ключ, manager_id)``; ключ ``None`` — резерв."""
    if not state or not state["is_active"] or state["manager_id"] is None:
        return None
    if state["match_type"] == ManagerRoutingRule.MATCH_FALLBACK:
        return (None, state["manager_id"])
    return ((state["match_type"], state["match_value"]), state["manager_id"])


def affected_keys(old: dict[str, Any] | None, new: dict[str, Any] | None) -> set[RegionKey | None]:
    """
    Ключи, клиентов которых надо пересчитать после изменения правила.

    Правило влияет на ответственного, только пока оно активно и у него
    выбран ``manager``. Пересчёт ключа охватывает всех его клиентов, в том
    числе ушедших на резерв, поэтому изменение регионального правила
    резерв не затрагивает: затронут резерв (``None``) только изменением
    резервного правила с менеджером.
    """
    old_effect, new_effect = _rule_effect(old), _rule_effect(new)
    if old_effect == new_effect:
        return set()
    return {effect[0] for effect in (old_effect, new_effect) if effect is not None}

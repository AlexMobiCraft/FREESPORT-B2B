"""
Подтверждение и отклонение B2B-заявки одной транзакцией.

До этого сервиса менеджер верифицировал заявку галочками в полной карточке,
а привязку к 1С выполнял отдельным действием списка. 05.10.2026 три заявки
прошли верификацию без привязки и без записи в AuditLog. Здесь привязка, роль,
AuditLog и флаги верификации — один атомарный шаг.

Логика живёт в сервисе, а не во view админки: тот же путь нужен для ручного
разбора из shell, и он должен тестироваться без HTTP.
"""

from __future__ import annotations

import logging
from typing import Mapping, NamedTuple

from django.db import transaction

from apps.common.models import AuditLog
from apps.users.models import User, matches_q
from apps.users.services.link_1c_customer import find_link_candidates, link_1c_customer, link_target_q
from apps.users.services.price_type_role import load_price_type_role_map, resolve_role_from_price_types
from apps.users.services.responsible_manager import assign_responsible_manager

logger = logging.getLogger(__name__)

# Режимы страницы подтверждения (условие доступа из спеки).
# DECISION — заявка ждёт решения: подтверждение верифицирует и активирует
# аккаунт, отклонение доступно.
MODE_DECISION = "decision"
# LINK_ONLY — аккаунт уже верифицирован, но не связан с 1С, а кандидаты есть:
# подтверждение только связывает и применяет роль. is_active и флаги не
# трогаются, иначе заблокированный клиент разблокировался бы привязкой.
MODE_LINK_ONLY = "link_only"

# Источник роли после подтверждения — пишется в AuditLog verify_b2b.
ROLE_SOURCE_1C = "1c_price_type"
ROLE_SOURCE_MANAGER = "manager"

# Значение onec_id в AuditLog, когда подтверждение прошло без привязки к 1С.
NO_1C_LINK = "без привязки"


class VerificationError(Exception):
    """Подтверждение или отклонение не выполнено, данные не изменены."""


class VerificationResult(NamedTuple):
    user: User
    mode: str
    linked: bool
    role_before: str
    role_after: str
    role_source: str
    source_customer_code: str | None


def is_awaiting_decision(user: User) -> bool:
    """
    «Заявка ждёт решения».

    Проверяется только verification_status: на проде is_verified и статус
    расходятся, и флаг в условие не входит намеренно.
    """
    return user.verification_status != "verified"


def eligible_link_candidates(user: User) -> list[User]:
    """
    Кандидаты 1С для страницы подтверждения.

    Только для цели, проходящей link_target_q: у уже связанного аккаунта
    кандидатов нет, и подтверждение идёт без привязки и без второй галочки.
    """
    if not matches_q(link_target_q(), user):
        return []
    return find_link_candidates(user)


def verification_mode(user: User, candidates: list[User]) -> str | None:
    """
    Условие доступа к странице подтверждения.

    Args:
        user: аккаунт заявителя
        candidates: результат eligible_link_candidates(user) — передаётся
            параметром, чтобы страница не искала кандидатов дважды.

    Returns:
        MODE_DECISION, MODE_LINK_ONLY или None (оснований нет).
    """
    if user.role not in User.B2B_ROLES or user.is_superuser:
        return None
    if is_awaiting_decision(user):
        return MODE_DECISION
    if candidates and matches_q(link_target_q(), user):
        return MODE_LINK_ONLY
    return None


def resolve_b2b_role(price_type_id: str | None, role_map: Mapping[str, str] | None = None) -> str | None:
    """
    Роль из вида цен 1С, если он разрешился в B2B-роль (FR-40-12), иначе None.

    Не-B2B роль из справочника не применяется — то же правило, что у
    link_1c_customer: retail/admin выбили бы аккаунт из B2B-сценариев.
    """
    resolution = resolve_role_from_price_types([price_type_id or ""], role_map=role_map)
    if resolution.role in User.B2B_ROLES:
        return resolution.role
    return None


def _lock_target(target_id: int) -> User:
    target = User.objects.select_for_update().filter(pk=target_id).first()
    if target is None:
        raise VerificationError("Аккаунт заявителя не найден.")
    return target


def verify_b2b_application(
    *,
    target_id: int,
    source_id: int | None,
    expected_onec_id: str = "",
    role: str | None = None,
    confirm_without_1c: bool = False,
    actor: User | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> VerificationResult:
    """
    Подтверждает B2B-заявку: привязка к 1С, роль, AuditLog, флаги.

    Порядок внутри транзакции неслучаен. Сигнал
    `check_verification_status_change` ставит письмо в очередь через `.delay`
    без `on_commit`, поэтому флаги верификации сохраняются последней записью:
    любой сбой до них откатывает всё, и письмо в очередь не уходит.

    Args:
        target_id: аккаунт заявителя
        source_id: выбранный контрагент 1С или None (подтверждение без привязки)
        expected_onec_id: onec_id кандидата, показанный менеджеру
        role: роль, выбранная менеджером. Применяется, только если вид цен
            1С не разрешился в B2B-роль (FR-40-12). None — оставить текущую.
        confirm_without_1c: явное согласие подтвердить несвязанную заявку,
            у которой в 1С нет кандидатов
        actor, ip_address, user_agent: для AuditLog

    Raises:
        VerificationError: условие доступа не выполняется, страница устарела,
            не дано согласие без привязки, недопустимая роль
        LinkCandidateError: отказ сервиса привязки
    """
    with transaction.atomic():
        target = _lock_target(target_id)
        # Роль фиксируется до link_1c_customer: привязка сама выводит роль из
        # вида цен, и после неё «что было» уже не восстановить.
        role_before = target.role

        # Проверки повторяются под блокировкой цели: страница могла устареть
        # между рендером и отправкой (двойная отправка, вторая вкладка, импорт).
        candidates = eligible_link_candidates(target)
        mode = verification_mode(target, candidates)
        if mode is None:
            raise VerificationError(
                f"Заявка {target.email or target.pk} уже обработана или не подлежит подтверждению. "
                f"Откройте карточку заново."
            )

        source_customer_code: str | None = None
        role_map = load_price_type_role_map()

        if source_id is None:
            if candidates:
                raise VerificationError(
                    "Данные на странице устарели: в 1С появились контрагенты с этим ИНН. "
                    "Откройте страницу подтверждения заново и выберите контрагента."
                )
            if matches_q(link_target_q(), target) and not confirm_without_1c:
                raise VerificationError(
                    "Контрагент в 1С не найден. Отметьте «Подтвердить без привязки к 1С», "
                    "чтобы подтвердить заявку без привязки."
                )
            linked = False
            # Связанный ранее аккаунт: вид цен из 1С уже на нём, и импорт
            # всё равно пересчитает по нему роль (FR-40-12).
            is_linked = bool(target.onec_id or target.onec_guid)
            resolved_role = resolve_b2b_role(target.onec_price_type_id, role_map) if is_linked else None
        else:
            source = next((candidate for candidate in candidates if candidate.pk == source_id), None)
            if source is None:
                raise VerificationError(
                    "Выбранный контрагент 1С больше не подходит для привязки. Откройте страницу заново."
                )
            source_customer_code = source.customer_code
            target = link_1c_customer(
                target_id=target.pk,
                source_id=source_id,
                expected_onec_id=expected_onec_id,
                actor=actor,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            linked = True
            # Вид цен источника перечитывается после привязки: link_1c_customer
            # держит блокировку источника, и это ровно то значение, из которого
            # он сам выводил роль. onec_price_type_id у источника не очищается.
            source_price_type = User.objects.filter(pk=source_id).values_list("onec_price_type_id", flat=True).get()
            resolved_role = resolve_b2b_role(source_price_type, role_map)

        if resolved_role is not None:
            role_after = resolved_role
            role_source = ROLE_SOURCE_1C
        else:
            role_after = role_before if role is None else role
            role_source = ROLE_SOURCE_MANAGER
            if role_after not in User.B2B_ROLES:
                raise VerificationError(f"Роль «{role_after}» не является B2B-ролью — подтверждение отменено.")

        if target.role != role_after:
            target.role = role_after
            target.save(update_fields=["role", "updated_at"])

        AuditLog.log_action(
            user=actor,
            action="verify_b2b",
            resource_type="User",
            resource_id=target.pk,
            changes={
                "email": str(target.email or ""),
                "mode": mode,
                "role_before": role_before,
                "role_after": role_after,
                "role_source": role_source,
                # Цель может нести только onec_guid — это тоже привязка.
                "onec_id": target.onec_id or (str(target.onec_guid) if target.onec_guid else "") or NO_1C_LINK,
                "linked_now": linked,
                "verified": mode == MODE_DECISION,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        if mode == MODE_DECISION:
            # Последняя запись транзакции: post_save-сигнал ставит письмо
            # пользователю в очередь сразу, без on_commit.
            target.is_verified = True
            target.verification_status = "verified"
            target.is_active = True
            update_fields = ["is_verified", "verification_status", "is_active", "updated_at"]
            # ИНН при подтверждении обычно не меняется, и хук User.save() не
            # сработает — назначаем ответственного явно (FR-42-08).
            if assign_responsible_manager(target):
                update_fields.append("responsible_manager")
            target.save(update_fields=update_fields)

    logger.info(
        "B2B-заявка %s подтверждена (режим=%s, привязка=%s, роль %s → %s, источник роли=%s)",
        target.pk,
        mode,
        linked,
        role_before,
        role_after,
        role_source,
    )
    return VerificationResult(
        user=target,
        mode=mode,
        linked=linked,
        role_before=role_before,
        role_after=role_after,
        role_source=role_source,
        source_customer_code=source_customer_code,
    )


def reject_b2b_application(
    *,
    target_id: int,
    actor: User | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> User:
    """
    Отклоняет B2B-заявку — как действие списка reject_b2b_users.

    is_verified=False, verification_status="unverified", AuditLog reject_b2b.
    Роль, привязка и is_active не меняются. Отклонить можно только заявку,
    ждущую решения: верифицированный аккаунт здесь не «отзывается».

    Raises:
        VerificationError: заявка не ждёт решения, не B2B или суперпользователь
    """
    with transaction.atomic():
        target = _lock_target(target_id)
        if verification_mode(target, []) != MODE_DECISION:
            raise VerificationError(
                f"Заявка {target.email or target.pk} уже обработана или не подлежит отклонению. "
                f"Откройте карточку заново."
            )

        AuditLog.log_action(
            user=actor,
            action="reject_b2b",
            resource_type="User",
            resource_id=target.pk,
            changes={
                "email": str(target.email or ""),
                "role": target.role,
                "verified": False,
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

        target.is_verified = False
        target.verification_status = "unverified"
        target.save(update_fields=["is_verified", "verification_status", "updated_at"])

    logger.info("B2B-заявка %s отклонена", target.pk)
    return target

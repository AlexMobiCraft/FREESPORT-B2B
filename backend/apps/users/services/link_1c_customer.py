"""
Связывание B2B-заявки с контрагентом 1С.

Автопривязка при регистрации отключена (spec-1c-unregistered-role): ИНН публичен
и сам по себе правом на контрагента не является. Поэтому регистрация с ИНН,
известным 1С, создаёт заявку рядом с записью 1С, и связать их может только
менеджер, сверив реквизиты вне портала.

Логика живёт в сервисе, а не в методе админки: тот же путь нужен для ручного
разбора из shell, и он должен тестироваться без HTTP.
"""

from __future__ import annotations

import logging

from django.db import models, transaction

from apps.common.models import AuditLog
from apps.users.models import Company, User, matches_q
from apps.users.services.price_type_role import resolve_role_from_price_types

logger = logging.getLogger(__name__)

# Поля User, переносимые с контрагента 1С на аккаунт заявителя.
# email, password, verification_status и is_active не переносятся намеренно:
# email — логин заявителя. role не переносится тоже, но по другой причине:
# у записи 1С она всегда unregistered, а роль аккаунта ВЫВОДИТСЯ из
# перенесённого вида цен через resolve_role_from_price_types (FR-40-11).
# Кортеж документирует поведение и переносом не управляет — фактический
# список полей собирается ниже по факту изменения значений.
TRANSFERRED_USER_FIELDS = ("onec_id", "onec_guid", "company_name", "tax_id", "onec_price_type_id")

# Поля Company, заполняемые импортом 1С (_create_or_update_company).
TRANSFERRED_COMPANY_FIELDS = ("legal_name", "tax_id", "kpp", "legal_address")


class LinkCandidateError(Exception):
    """Общий предок ошибок привязки: привязка не выполнена, данные не изменены."""


class TargetAlreadyLinkedError(LinkCandidateError):
    """Аккаунт заявителя уже несёт идентичность 1С — это перепривязка."""


class SourceNotLinkableError(LinkCandidateError):
    """Выбранный контрагент 1С занят, деактивирован или больше не подходит."""


def link_target_q() -> models.Q:
    """
    Единственный источник истины для критерия «аккаунт может быть целью привязки».

    Через него выражаются и проверка под блокировкой в `link_1c_customer`, и
    аннотация-индикатор в changelist админки.

    Целью может быть только B2B-аккаунт (`User.B2B_ROLES`), ещё не несущий
    идентичность 1С. Признак «уже несёт» — **любой** из onec_id и onec_guid:
    оба уникальны и оба являются якорями идентичности, поэтому цель с непустым
    onec_guid при пустом onec_id либо упрётся в constraint при переносе, либо
    получит пару идентификаторов от разных контрагентов.
    """
    return (
        models.Q(role__in=User.B2B_ROLES)
        & (models.Q(onec_id__isnull=True) | models.Q(onec_id=""))
        & models.Q(onec_guid__isnull=True)
    )


def normalize_tax_id(tax_id: str | None) -> str:
    """
    Единое правило сравнения ИНН для поиска кандидатов и сверки под блокировкой.

    Импорт 1С пишет `tax_id` без `strip()` (`_update_customer`), поэтому два
    разных правила означали бы заявку, которой кандидат показан, но привязать
    её нельзя.
    """
    return (tax_id or "").strip()


def find_link_candidates(user: User) -> list[User]:
    """
    Непривязанные записи 1С с тем же ИНН, кроме самого user. Пустой ИНН → [].

    Кандидат обязан быть активным: деактивированная запись — это уже
    отработанный источник, повторно использовать его нельзя.

    `Company` тянется сразу: на один ИНН приходится до 74 контрагентов, и
    юр. адрес каждого выводится и в карточке, и на странице подтверждения.
    """
    tax_id = normalize_tax_id(user.tax_id)
    if not tax_id:
        return []

    return list(
        User.objects.unlinked_1c_records()
        .select_related("company")
        .filter(tax_id=tax_id, is_active=True)
        .exclude(pk=user.pk)
        .order_by("id")
    )


def link_1c_customer(
    *,
    target_id: int,
    source_id: int,
    expected_onec_id: str,
    actor: User | None = None,
    ip_address: str | None = None,
    user_agent: str = "",
) -> User:
    """
    Переносит идентификаторы и реквизиты с контрагента 1С на аккаунт заявителя.

    Вместе с реквизитами переносится вид цен из соглашения 1С
    (`onec_price_type_id`), а роль аккаунта ВЫВОДИТСЯ из него справочником
    `PriceType.user_role` — сама роль не переносится: у записи 1С она всегда
    `unregistered` (FR-40-11). Клиент видит свои цены с первого входа, не
    дожидаясь ближайшего обмена. Роль меняется только когда вид цен разрешился
    в B2B-роль; отсутствие вида цен, неизвестный GUID и не-B2B роль привязку
    не отменяют — она выполняется, роль остаётся прежней.

    Принимает id, а не инстансы: объекты, прочитанные до транзакции, устарели
    по определению — актуальные строки берутся уже под select_for_update().

    Args:
        target_id: Аккаунт заявителя (цель привязки)
        source_id: Непривязанная запись 1С (источник идентификаторов)
        expected_onec_id: onec_id, показанный менеджеру на странице подтверждения.
            Сверяется под блокировкой: двойная отправка формы и устаревшая
            вкладка отклоняются, а не выполняются повторно.
        actor: Кто выполняет действие (для AuditLog)
        ip_address: IP инициатора (для AuditLog)
        user_agent: User-Agent инициатора (для AuditLog)

    Returns:
        User: обновлённый аккаунт заявителя

    Raises:
        TargetAlreadyLinkedError: цель уже несёт onec_id/onec_guid
        SourceNotLinkableError: источник занят, деактивирован или не подходит
        LinkCandidateError: прочие отказы (не-B2B цель, записи не найдены)
    """
    if target_id == source_id:
        raise LinkCandidateError("Нельзя связать запись саму с собой.")

    with transaction.atomic():
        # Захват в порядке возрастания pk, а не «источник, затем цель»:
        # фиксированный порядок снимает класс взаимных блокировок целиком,
        # а не снижает их вероятность.
        locked = list(User.objects.select_for_update().filter(pk__in=[source_id, target_id]).order_by("pk"))
        by_pk = {user.pk: user for user in locked}

        target = by_pk.get(target_id)
        source = by_pk.get(source_id)
        if target is None:
            raise LinkCandidateError("Аккаунт заявителя не найден.")
        if source is None:
            raise SourceNotLinkableError("Выбранный контрагент 1С не найден.")

        # Повторная проверка условий под блокировкой: состояние, показанное
        # менеджеру, могло измениться между рендером страницы и отправкой.
        if target.onec_id or target.onec_guid:
            raise TargetAlreadyLinkedError(
                f"Аккаунт {target.email or target.pk} уже связан с 1С "
                f"(ID в 1С: {target.onec_id or '—'}). Перепривязка выполняется вручную."
            )
        if not matches_q(link_target_q(), target):
            raise LinkCandidateError(
                f"Связывать с контрагентом 1С можно только B2B-аккаунт, "
                f"а роль заявителя — «{target.get_role_display()}»."
            )
        if not source.is_active or not matches_q(User.objects.unlinked_1c_record_q(), source):
            raise SourceNotLinkableError(
                "Выбранный контрагент 1С больше не свободен: запись уже привязана или деактивирована."
            )
        if not source.onec_id and not source.onec_guid:
            raise SourceNotLinkableError("У выбранной записи нет идентификаторов 1С — переносить нечего.")
        if (source.onec_id or "") != (expected_onec_id or ""):
            raise SourceNotLinkableError(
                "Данные на странице устарели: ID контрагента в 1С изменился. Откройте карточку заново."
            )
        # Сравнение стриптованных значений — то же правило, по которому ИНН
        # искался в find_link_candidates. Сырое сравнение делало бы заявку с
        # ИНН в пробелах (импорт пишет tax_id без strip) вечным тупиком:
        # кандидат показан, а привязка отвергается без внятной причины.
        if not normalize_tax_id(source.tax_id) or normalize_tax_id(source.tax_id) != normalize_tax_id(target.tax_id):
            raise SourceNotLinkableError("ИНН контрагента 1С не совпадает с ИНН заявителя.")

        onec_id = source.onec_id
        onec_guid = source.onec_guid
        previous: dict[str, str | None] = {
            "company_name": target.company_name,
            "tax_id": target.tax_id,
            "customer_code": target.customer_code,
            # Прежняя роль и вид цен пишутся безусловно — как три ключа выше:
            # привязка необратима, и разбор ошибочного случая строится на «что было».
            "role": target.role,
            "onec_price_type_id": target.onec_price_type_id,
        }
        transferred: list[str] = ["onec_id", "onec_guid"]

        source_fields = ["onec_id", "onec_guid", "is_active", "updated_at"]
        source.onec_id = None
        source.onec_guid = None
        source.is_active = False

        # customer_code заявителя неприкосновенен, если заполнен: он уже вшит
        # в номера его заказов, и save() запрещает смену после их появления.
        # Переносится только когда у источника он есть, а у заявителя пуст.
        # У источника код снимается, поэтому его заказы (если они есть) тоже
        # блокируют перенос — save() отвергнет смену кода после заказа.
        transfer_customer_code = bool(source.customer_code) and not target.customer_code and not source.orders.exists()
        if transfer_customer_code:
            customer_code = source.customer_code
            source.customer_code = None
            source_fields.append("customer_code")

        # Сначала освободить unique-поля у источника, иначе присвоение цели
        # упрётся в constraint: onec_id, onec_guid и customer_code уникальны.
        source.save(update_fields=source_fields)

        target.onec_id = onec_id
        target.onec_guid = onec_guid
        target_fields = ["onec_id", "onec_guid", "updated_at"]
        if source.company_name and source.company_name != target.company_name:
            target.company_name = source.company_name
            target_fields.append("company_name")
            transferred.append("company_name")
        if source.tax_id and source.tax_id != target.tax_id:
            target.tax_id = source.tax_id
            target_fields.append("tax_id")
            transferred.append("tax_id")
        if transfer_customer_code:
            target.customer_code = customer_code
            target_fields.append("customer_code")
            transferred.append("customer_code")

        # Вид цен переносится по тому же правилу, что и прочие реквизиты:
        # пустое значение источника ничего не затирает (привязка необратима).
        if source.onec_price_type_id and source.onec_price_type_id != target.onec_price_type_id:
            target.onec_price_type_id = source.onec_price_type_id
            target_fields.append("onec_price_type_id")
            transferred.append("onec_price_type_id")

        # Роль не переносится, а выводится: у записи 1С она всегда
        # unregistered (§5 задания). Источник GUID — именно source: при
        # пустом значении источника поле цели не менялось (правило выше).
        # Статус соглашения на портале не хранится — параметр не передаётся.
        resolution = resolve_role_from_price_types([source.onec_price_type_id or ""])
        # Проверять role is None, а не reason: перечисление причин сломалось
        # бы молча, если резолвер заведёт шестую.
        if resolution.role is not None and resolution.role != target.role:
            # Вид цен, дающий не-B2B роль, применять нельзя: PriceTypeAdminForm
            # предлагает менеджеру весь ROLE_CHOICES, а retail/admin выбили бы
            # аккаунт из link_target_q(), is_b2b_user и B2B-сценариев целиком.
            if resolution.role in User.B2B_ROLES:
                target.role = resolution.role
                target_fields.append("role")
                transferred.append("role")
        target.save(update_fields=target_fields)

        company_fields, company_previous = _transfer_company(source, target)
        transferred.extend(company_fields)
        previous.update(company_previous)

        AuditLog.log_action(
            user=actor,
            action="link_1c_customer",
            resource_type="User",
            resource_id=target.pk,
            changes={
                "target_id": target.pk,
                "target_email": str(target.email or ""),
                "source_id": source.pk,
                "onec_id": onec_id,
                "onec_guid": str(onec_guid) if onec_guid else None,
                # Только фактически изменённые поля: список из констант
                # утверждал бы перенос там, где значение осталось прежним.
                "transferred_fields": transferred,
                # Прежние значения цели — операция объявлена необратимой,
                # и без них разбор ошибочной привязки не на чем строить.
                "previous_values": {key: str(value) if value else "" for key, value in previous.items()},
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )

    logger.info(
        "Заявка %s связана с контрагентом 1С %s (onec_id=%s), исходная запись деактивирована, роль=%s",
        target.pk,
        source.pk,
        onec_id,
        target.role,
    )
    return target


def _transfer_company(source: User, target: User) -> tuple[list[str], dict[str, str]]:
    """
    Копирует реквизиты Company с записи 1С на аккаунт заявителя.

    Реквизиты копируются сразу, хотя ближайший импорт освежил бы их сам через
    `_update_customer`: менеджер должен видеть результат в момент действия,
    а не после следующей синхронизации.

    Пустые значения источника не переносятся. Выгрузка 1С не заполняет `КПП` и
    адрес для ИП и физлиц, а привязка объявлена необратимой: затирать ими
    реквизиты, введённые заявителем при регистрации, значит терять данные без
    возможности восстановления.

    Company источника не удаляется — исходная запись остаётся аудиторским следом.

    Returns:
        Список фактически изменённых полей и прежние значения цели по ним.
    """
    source_company = Company.objects.filter(user=source).first()
    if source_company is None:
        return [], {}

    values = {
        field: value for field in TRANSFERRED_COMPANY_FIELDS if (value := getattr(source_company, field, "") or "")
    }
    if not values:
        return [], {}

    target_company = Company.objects.filter(user=target).first()
    if target_company is None:
        Company.objects.create(user=target, **values)
        return [f"company.{field}" for field in values], {f"company.{field}": "" for field in values}

    changed = {field: value for field, value in values.items() if getattr(target_company, field) != value}
    if not changed:
        return [], {}

    previous = {f"company.{field}": getattr(target_company, field) for field in changed}
    for field, value in changed.items():
        setattr(target_company, field, value)
    target_company.save(update_fields=[*changed, "updated_at"])

    return [f"company.{field}" for field in changed], previous

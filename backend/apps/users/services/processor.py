"""
Процессор данных клиентов для импорта в систему
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, NamedTuple

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.common.models import AuditLog, CustomerSyncLog
from apps.users.models import Company, User, matches_q
from apps.users.services.price_type_role import (
    AGREEMENT_STATUS_NONE,
    REASON_AMBIGUOUS,
    REASON_NO_AGREEMENT,
    REASON_NO_DATA,
    REASON_UNKNOWN,
    RoleResolution,
    load_price_type_role_map,
    resolve_role_from_price_types,
)

if TYPE_CHECKING:
    from apps.products.models import ImportSession


logger = logging.getLogger(__name__)


# Ключи ролевых счётчиков сессии импорта. Единственный источник истины:
# команда import_customers_from_1c суммирует ТОЛЬКО объявленные у себя ключи,
# поэтому она импортирует этот кортеж, а не перечисляет имена заново.
ROLE_STATS_KEYS = (
    "roles_updated",
    "roles_updated_from_unregistered",
    "roles_updated_from_assigned",
    "roles_already_actual",
    "roles_skipped_unlinked_record",
    "roles_skipped_no_data",
    "roles_skipped_no_agreement",
    "roles_skipped_unknown_price_type",
    "roles_skipped_ambiguous",
)

# Причина отказа резолвера → счётчик отчёта. Словарь, а не цепочка if:
# добавление шестой причины в price_type_role.py обязано падать здесь
# явным KeyError, а не молча теряться в отчёте.
SKIP_COUNTER_BY_REASON = {
    REASON_NO_DATA: "roles_skipped_no_data",
    REASON_NO_AGREEMENT: "roles_skipped_no_agreement",
    REASON_UNKNOWN: "roles_skipped_unknown_price_type",
    REASON_AMBIGUOUS: "roles_skipped_ambiguous",
}


class RoleChange(NamedTuple):
    """
    Исход разрешения роли для одной записи.

    Отдаётся вызывающему через ``CustomerDataProcessor.last_role_outcome``,
    а не возвращаемым значением ``_update_customer``: смена сигнатуры
    расширила бы blast radius на ``process_customer`` и тесты.
    """

    outcome: str  # ключ из ROLE_STATS_KEYS
    applied: bool  # роль реально меняется
    previous_role: str
    new_role: str
    resolution: RoleResolution | None


class CustomerDataProcessor:
    """
    Процессор данных клиентов для импорта в систему
    Обрабатывает данные из парсера и создает/обновляет пользователей
    """

    # Значение <Роль> в выгрузке контрагентов CommerceML, которое подлежит
    # импорту. Поставщики, конкуренты и прочие контрагенты клиентами портала
    # не являются и пропускаются.
    ONEC_BUYER_ROLE = "Покупатель"

    # Новая запись 1С портального аккаунта ещё не имеет, и роль ей не
    # разрешается ни при каком виде цен (§5 задания эпика 40): роль,
    # отличная от unregistered, выбила бы запись из выборки кандидатов на
    # привязку. Вид цен из выгрузки при этом сохраняется (стори 40.3), а
    # роль по нему приезжает при первом же импорте ПОСЛЕ привязки.
    IMPORTED_CUSTOMER_ROLE = User.ROLE_UNREGISTERED

    def __init__(self, session_id: int):
        """
        Инициализирует процессор с ID сессии импорта.

        Args:
            session_id: ID объекта ImportSession
        """
        from apps.products.models import ImportSession

        self.session = ImportSession.objects.get(pk=session_id)
        # Справочник видов цен читается один раз на сессию импорта (NFR-3940-09).
        # Кэш живёт на экземпляре, а не на модуле: lru_cache пережил бы правку
        # user_role в админке внутри долгоживущего Celery-воркера.
        self._role_map: dict[str, str] | None = None
        self._role_stats: dict[str, int] = {}
        # Исход разрешения роли для последнего обработанного контрагента.
        # Пустая строка — роль не разрешалась (создание, пропуск, ошибка).
        self.last_role_outcome: str = ""

    def is_buyer(self, customer_data: dict[str, Any]) -> bool:
        """
        Является ли контрагент покупателем.

        Регистр и пробелы игнорируются, значение из нескольких ролей через
        запятую разбирается поэлементно: выгрузка формируется на стороне 1С,
        и строгое сравнение отсекло бы всех контрагентов разом при малейшем
        изменении формата.

        Args:
            customer_data: Словарь с данными клиента из парсера

        Returns:
            bool: True, если среди <Роль> контрагента есть "Покупатель"
        """
        raw_role = str(customer_data.get("role") or "")
        roles = {part.strip().casefold() for part in raw_role.split(",")}

        return self.ONEC_BUYER_ROLE.casefold() in roles

    def process_customer(self, customer_data: dict[str, Any]) -> User | None:
        """
        Обрабатывает данные одного клиента: создает или обновляет.

        Args:
            customer_data: Словарь с данными клиента из парсера

        Returns:
            Optional[User]: Созданный/обновленный пользователь или None при ошибке
        """
        # Исход прошлого контрагента не должен протечь: create/skip/error
        # ролевых счётчиков не трогают вовсе.
        self.last_role_outcome = ""

        onec_id = customer_data.get("onec_id")
        if not onec_id:
            logger.error("Отсутствует onec_id в данных клиента")
            return None

        # Поставщики и прочие не-покупатели портальными клиентами не становятся
        if not self.is_buyer(customer_data):
            logger.info(
                "Контрагент %s пропущен: роль в 1С '%s', ожидается '%s'",
                onec_id,
                customer_data.get("role", ""),
                self.ONEC_BUYER_ROLE,
            )
            # Без этой записи process_customers засчитает пропуск как ошибку:
            # он отличает skipped от errors только по логу.
            self._log_operation(
                user=None,
                onec_id=onec_id,
                operation_type="skipped",
                status="success",
                details={"reason": "not_buyer", "role": customer_data.get("role", "")},
            )
            return None

        try:
            with transaction.atomic():
                # Поиск дубликатов
                existing_user = self._find_duplicate(customer_data)

                # Валидация email
                email = customer_data.get("email", "").strip()
                if email:
                    if not self._validate_email(email):
                        logger.warning(f"Невалидный email для клиента {onec_id}: {email}")
                        self._log_operation(
                            user=None,
                            onec_id=onec_id,
                            operation_type="error",
                            status="failed",
                            error_message=f"Невалидный формат email: {email}",
                        )
                        return None
                else:
                    # Email отсутствует - логируем warning но продолжаем
                    logger.info(f"Клиент {onec_id} не имеет email адреса")

                if existing_user:
                    # Обновление существующего клиента. Роль привязанного
                    # аккаунта теперь приезжает из 1С (FR-40-12); запись 1С
                    # без портального аккаунта роли по-прежнему не получает.
                    user = self._update_customer(existing_user, customer_data)
                    self._log_operation(
                        user=user,
                        onec_id=onec_id,
                        operation_type="updated",
                        status="success",
                        details={
                            "role": user.role,
                            "role_outcome": self.last_role_outcome,
                            # Флаг перестал быть константой: у привязанного
                            # аккаунта роль теперь приезжает из 1С (FR-40-12).
                            "role_preserved": self.last_role_outcome
                            not in ("roles_updated_from_unregistered", "roles_updated_from_assigned"),
                        },
                    )
                else:
                    # Создание нового клиента
                    user = self._create_customer(customer_data, self.IMPORTED_CUSTOMER_ROLE)
                    self._log_operation(
                        user=user,
                        onec_id=onec_id,
                        operation_type="created",
                        status="success",
                        details={
                            "role": self.IMPORTED_CUSTOMER_ROLE,
                            "has_email": bool(email),
                            "customer_type": customer_data.get("customer_type"),
                        },
                    )

                    # Warning если нет email
                    if not email:
                        self._log_operation(
                            user=user,
                            onec_id=onec_id,
                            operation_type="created",
                            status="warning",
                            details={"notes": "Клиент создан без email адреса"},
                        )

                return user

        except Exception as e:
            logger.error(f"Ошибка обработки клиента {onec_id}: {e}", exc_info=True)
            self._log_operation(
                user=None,
                onec_id=onec_id,
                operation_type="error",
                status="failed",
                error_message=str(e),
            )
            return None

    def process_customers(self, customers_data: list[dict[str, Any]], chunk_size: int = 100) -> dict[str, int]:
        """
        Обрабатывает список клиентов пакетами.

        Args:
            customers_data: Список словарей с данными клиентов
            chunk_size: Размер пакета для обработки

        Returns:
            Dict: Статистика обработки — total, created, updated, skipped,
                errors, счётчики здоровья выгрузки attributes_block_present
                и attributes_block_missing, а также ролевые счётчики
                ROLE_STATS_KEYS (roles_updated и его два слагаемых,
                roles_already_actual, roles_skipped_unlinked_record,
                roles_skipped_no_data, roles_skipped_no_agreement,
                roles_skipped_unknown_price_type, roles_skipped_ambiguous).
                Сумма ролевых исходов равна числу обновлённых записей.
        """
        # Счётчики пофайловые: команда суммирует результаты по файлам сама.
        self._role_stats = {key: 0 for key in ROLE_STATS_KEYS}

        stats = {
            "total": len(customers_data),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
            # Детектор регресса выгрузки: блок <ЗначенияРеквизитов> формирует
            # патч тиражного расширения БУС и теряется при его обновлении.
            # Отказ тихий — файлы приходят, блока в них нет.
            "attributes_block_present": 0,
            "attributes_block_missing": 0,
        }

        for i, customer_data in enumerate(customers_data, 1):
            logger.debug(f"Обработка клиента {i}/{len(customers_data)}")

            # Считаем по всем разобранным контрагентам, включая не-покупателей:
            # детектор измеряет здоровье выгрузки, а не результат импорта.
            if customer_data.get("price_type_ids") or customer_data.get("agreement_status"):
                stats["attributes_block_present"] += 1
            else:
                stats["attributes_block_missing"] += 1

            # Получаем onec_id перед обработкой для логирования
            onec_id = customer_data.get("onec_id", f"unknown-{i}")

            # Проверяем, существует ли уже пользователь
            existing_user = self._find_duplicate(customer_data)

            result = self.process_customer(customer_data)

            if result:
                # Инкремент вне transaction.atomic() процессора: откат внутри
                # process_customer не должен оставлять фантомный счётчик.
                if self.last_role_outcome:
                    self._role_stats[self.last_role_outcome] += 1

                # Определяем, была ли это операция создания или обновления
                if existing_user:
                    stats["updated"] += 1
                else:
                    stats["created"] += 1
            else:
                # Проверяем логи на наличие записи с типом SKIPPED
                skipped_log = CustomerSyncLog.objects.filter(
                    session=str(self.session.pk),
                    onec_id=onec_id,
                    operation_type="skipped",
                ).exists()

                if skipped_log:
                    stats["skipped"] += 1
                else:
                    stats["errors"] += 1

        logger.info(
            f"Обработка завершена. Статистика: "
            f"создано={stats['created']}, обновлено={stats['updated']}, "
            f"пропущено={stats['skipped']}, ошибок={stats['errors']}"
        )

        self._role_stats["roles_updated"] = (
            self._role_stats["roles_updated_from_unregistered"] + self._role_stats["roles_updated_from_assigned"]
        )
        stats.update(self._role_stats)

        return stats

    def _find_duplicate(self, customer_data: dict[str, Any]) -> User | None:
        """
        Ищет дубликаты клиента по onec_id и email.

        Args:
            customer_data: Словарь с данными клиента

        Returns:
            Optional[User]: Найденный пользователь или None
        """
        onec_id = customer_data.get("onec_id")
        email = customer_data.get("email", "").strip()

        # Поиск по onec_id (основной метод)
        if onec_id:
            user = User.objects.filter(onec_id=onec_id).first()
            if user:
                logger.debug(f"Найден пользователь по onec_id: {onec_id}")
                return user

        # Поиск по email (вторичный метод)
        if email:
            user = User.objects.filter(email=email).first()
            if user:
                logger.debug(f"Найден пользователь по email: {email}")
                return user

        return None

    def _validate_email(self, email: str) -> bool:
        """
        Валидирует формат email.

        Args:
            email: Email для проверки

        Returns:
            bool: True если email валиден
        """
        if not email:
            return False

        try:
            validate_email(email)
            return True
        except ValidationError:
            return False

    def _normalize_phone(self, phone: str) -> str:
        """
        Нормализует телефон из формата 1С в формат приложения.

        Извлекает только цифры и берет первый телефон если их несколько.
        Конвертирует в формат +7XXXXXXXXXX.

        Args:
            phone: Телефон в любом формате (например, "8-982-911-00-98",
                   "8-961-205-46-21")

        Returns:
            str: Нормализованный телефон в формате +7XXXXXXXXXX или пустая строка
        """
        if not phone:
            return ""

        # Берем первый телефон если их несколько (разделены запятой)
        first_phone = phone.split(",")[0].strip()

        # Извлекаем только цифры
        digits = "".join(c for c in first_phone if c.isdigit())

        # Если номер начинается с 8 и имеет 11 цифр, конвертируем в +7
        if digits.startswith("8") and len(digits) == 11:
            return f"+7{digits[1:]}"

        # Если номер начинается с 7 и имеет 11 цифр, добавляем +
        if digits.startswith("7") and len(digits) == 11:
            return f"+{digits}"

        # Если 10 цифр, добавляем +7
        if len(digits) == 10:
            return f"+7{digits}"

        # Если не удалось нормализовать, возвращаем пустую строку
        # Это предотвратит ошибку валидации
        logger.warning(f"Не удалось нормализовать телефон: {phone}")
        return ""

    def _price_type_id_to_store(self, customer_data: dict[str, Any], current: str) -> str:
        """
        Определяет, каким должно стать поле onec_price_type_id.

        Роль здесь НЕ разрешается и справочник PriceType НЕ читается: поле
        обязано заполняться и для видов цен, роли не несущих (РРЦ, «Детский
        мир Залоговая»), — иначе накопление данных, ради которого стори
        выкатывается отдельно, потеряет часть контрагентов.

        Args:
            customer_data: словарь из парсера (ключи price_type_ids и
                agreement_status кладёт _extract_attribute_values, стори 40.1).
            current: сохранённое значение поля; возвращается без изменений,
                когда данных для решения нет.

        Returns:
            str: новое значение поля.
        """
        agreement_status = str(customer_data.get("agreement_status") or "")
        if agreement_status.strip().casefold() == AGREEMENT_STATUS_NONE.casefold():
            # 1С подтвердила, что действующего соглашения нет. Прежний вид цен
            # хранить нельзя: по нему привязка (стори 40.5) выдала бы роль по
            # соглашению, снятому в 1С месяцы назад, без единой ошибки в логах.
            return ""

        guids = {str(guid).strip().lower() for guid in (customer_data.get("price_type_ids") or []) if str(guid).strip()}

        if len(guids) == 1:
            return next(iter(guids))

        # Два и более различных вида цен — два разных соглашения. Сохранить один
        # из них означает солгать: стори 40.5 разрешает роль по единственному
        # сохранённому GUID и выдала бы роль там, где резолвер обязан ответить
        # ambiguous. Пустой список без статуса — признак поломки выгрузки
        # (после второй редакции патча блок приходит у каждого контрагента),
        # и обнуление уничтожило бы данные у всех разом.
        return current

    @property
    def role_map(self) -> dict[str, str]:
        """Маппинг GUID вида цен → роль портала, один запрос на сессию импорта."""
        if self._role_map is None:
            self._role_map = load_price_type_role_map()
        return self._role_map

    def _resolve_role_change(self, user: User, customer_data: dict[str, Any]) -> RoleChange:
        """
        Решает, менять ли роль существующего пользователя по данным из 1С.

        Пользователя НЕ сохраняет и AuditLog НЕ пишет — это делает
        _update_customer, чтобы запись в журнал не опередила сохранение.

        Непривязанная запись 1С роли не получает никогда (§5 задания):
        unlinked_1c_record_q() включает role='unregistered', и смена роли
        выбила бы запись из выборки кандидатов на привязку — вернулся бы
        баг, чинившийся миграцией 0018.

        Args:
            user: существующая запись (поля роли ещё не тронуты).
            customer_data: словарь из парсера.

        Returns:
            RoleChange: исход для счётчика отчёта и решение о применении.
        """
        current_role = user.role

        # Предикат в памяти, а не запрос: тот же Q, что и у queryset-фильтра.
        if matches_q(User.objects.unlinked_1c_record_q(), user):
            return RoleChange("roles_skipped_unlinked_record", False, current_role, current_role, None)

        resolution = resolve_role_from_price_types(
            customer_data.get("price_type_ids") or [],
            str(customer_data.get("agreement_status") or ""),
            role_map=self.role_map,
        )

        # Проверять именно role is None, а не reason != REASON_RESOLVED:
        # резолвер отдаёт непустую роль ровно при reason="resolved", и
        # сравнение по reason дало бы KeyError на несуществующей комбинации.
        if resolution.role is None:
            return RoleChange(
                SKIP_COUNTER_BY_REASON[resolution.reason],
                False,
                current_role,
                current_role,
                resolution,
            )

        if resolution.role == current_role:
            # Роль уже актуальна: перезапись породила бы запись AuditLog на
            # каждом обмене и сделала бы журнал нечитаемым (NFR-3940-08).
            return RoleChange("roles_already_actual", False, current_role, current_role, resolution)

        outcome = (
            "roles_updated_from_unregistered"
            if current_role == User.ROLE_UNREGISTERED
            else "roles_updated_from_assigned"
        )
        return RoleChange(outcome, True, current_role, resolution.role, resolution)

    def _create_customer(self, customer_data: dict[str, Any], role: str) -> User:
        """
        Создает нового пользователя из данных клиента.

        Args:
            customer_data: Словарь с данными клиента
            role: Роль пользователя

        Returns:
            User: Созданный пользователь
        """
        email = customer_data.get("email", "").strip()
        first_name = customer_data.get("first_name", "").strip()
        last_name = customer_data.get("last_name", "").strip()
        phone = self._normalize_phone(customer_data.get("phone", ""))  # Нормализация телефона
        company_name = customer_data.get("company_name", "").strip()
        tax_id = customer_data.get("tax_id", "").strip()
        onec_id = customer_data.get("onec_id")

        # Если first_name и last_name пусты, используем name
        if not first_name and not last_name:
            name = customer_data.get("name", "")
            parts = name.split()
            if len(parts) >= 2:
                last_name = parts[0]
                first_name = " ".join(parts[1:])
            else:
                last_name = name

        user = User.objects.create(
            email=email or None,  # None для пустого email (уникальность)
            first_name=first_name,
            last_name=last_name,
            role=role,
            phone=phone,
            company_name=company_name,
            tax_id=tax_id,
            onec_id=onec_id,
            onec_price_type_id=self._price_type_id_to_store(customer_data, ""),
            created_in_1c=True,
            sync_status="synced",
            last_sync_at=timezone.now(),
        )

        # Создаем объект Company для B2B клиентов (юр.лиц и ИП)
        customer_type = customer_data.get("customer_type", "")
        if customer_type in ["legal_entity", "individual_entrepreneur"]:
            self._create_or_update_company(user, customer_data)

        logger.info(f"Создан новый пользователь: {str(user.email or onec_id)} (role={role})")
        return user

    def _update_customer(self, user: User, customer_data: dict[str, Any]) -> User:
        """
        Обновляет существующего пользователя данными из 1С.

        Роль привязанного аккаунта приезжает из 1С: источник истины по
        уровню цен — соглашение в 1С, а не значение, выданное менеджером
        вручную (FR-40-07, FR-40-12). Смена роли пишется в AuditLog.
        Непривязанная запись 1С роли не получает никогда — решение
        принимает _resolve_role_change.

        Вид цен (onec_price_type_id) обновляется всегда — и у привязанных
        аккаунтов, и у непривязанных записей 1С (стори 40.3).

        Args:
            user: Существующий пользователь
            customer_data: Словарь с данными клиента

        Returns:
            User: Обновленный пользователь
        """
        # Обновляем поля из 1С
        user.first_name = customer_data.get("first_name", user.first_name)
        user.last_name = customer_data.get("last_name", user.last_name)
        # Нормализуем телефон перед обновлением
        phone = customer_data.get("phone", "")
        if phone:
            user.phone = self._normalize_phone(phone)
        user.company_name = customer_data.get("company_name", user.company_name)
        user.tax_id = customer_data.get("tax_id", user.tax_id)
        # Обновляем onec_id если его не было (дубликат найден по email)
        if not user.onec_id:
            user.onec_id = customer_data.get("onec_id")
        # Решение о роли принимается ДО присвоения user.role: предикат
        # «непривязанная запись 1С» опирается в том числе на текущую роль.
        role_change = self._resolve_role_change(user, customer_data)
        if role_change.applied:
            user.role = role_change.new_role
        # Вид цен пишется всегда — и привязанным аккаунтам, и записям 1С.
        user.onec_price_type_id = self._price_type_id_to_store(customer_data, user.onec_price_type_id)
        user.sync_status = "synced"
        user.last_sync_at = timezone.now()

        user.save()

        # Журнал строго после сохранения: запись о смене роли, которой не
        # случилось, хуже отсутствия записи.
        if role_change.applied:
            self._log_role_change(user, role_change, customer_data)
        self.last_role_outcome = role_change.outcome

        # Создаем/обновляем объект Company для B2B клиентов
        customer_type = customer_data.get("customer_type", "")
        if customer_type in ["legal_entity", "individual_entrepreneur"]:
            self._create_or_update_company(user, customer_data)

        logger.info(
            f"Обновлен пользователь: {str(user.email or user.onec_id)} "
            f"(role={user.role}, исход разрешения роли={role_change.outcome})"
        )
        return user

    def _log_role_change(self, user: User, change: RoleChange, customer_data: dict[str, Any]) -> None:
        """
        Пишет AuditLog о смене роли по данным 1С (FR-40-08).

        Наименования вида цен и соглашения берутся из price_type_meta
        парсера, а не запросом в PriceType: в пакете тысячи контрагентов,
        и запрос за подписью свёл бы на нет экономию role_map.

        actor отсутствует: смену выполняет импорт, а не человек.
        """
        guid = change.resolution.matched[0] if change.resolution and change.resolution.matched else ""
        # Резолвер отдаёт GUID в нижнем регистре, парсер — как в выгрузке.
        # Регистрозависимое сравнение молча вернуло бы пустые наименования.
        meta = next(
            (
                item
                for item in (customer_data.get("price_type_meta") or [])
                if str(item.get("price_type_id") or "").strip().lower() == guid
            ),
            {},
        )

        AuditLog.log_action(
            user=None,
            action="role_from_1c",
            resource_type="User",
            resource_id=user.pk,
            details={
                "source": "import_1c",
                "session_id": str(self.session.pk),
                "onec_id": user.onec_id or "",
            },
            changes={
                "previous_role": change.previous_role,
                "new_role": change.new_role,
                "price_type_id": guid,
                "price_type_name": str(meta.get("price_type_name") or ""),
                "agreement_name": str(meta.get("agreement_name") or ""),
            },
        )

    def _log_operation(
        self,
        user: User | None,
        onec_id: str,
        operation_type: str,
        status: str,
        error_message: str = "",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Создает запись в CustomerSyncLog.

        Args:
            user: Пользователь (может быть None при ошибке)
            onec_id: ID клиента в 1С
            operation_type: Тип операции (created/updated/skipped/error)
            status: Статус (success/failed/warning)
            error_message: Сообщение об ошибке
            details: Дополнительные детали операции
        """
        import uuid

        CustomerSyncLog.objects.create(
            session=str(self.session.pk),  # CharField - преобразуем ID в строку
            customer=user,  # Поле называется customer, не user
            onec_id=onec_id,
            operation_type=operation_type,
            status=status,
            error_message=error_message,
            details=details or {},
            correlation_id=uuid.uuid4(),  # Обязательное поле UUID
        )

    def _create_or_update_company(self, user: User, customer_data: dict[str, Any]) -> Company:
        """
        Создает или обновляет объект Company для B2B клиента.

        Args:
            user: Пользователь-владелец компании
            customer_data: Словарь с данными клиента из парсера

        Returns:
            Company: Созданный или обновленный объект компании
        """
        # Получаем данные компании из customer_data
        legal_name = customer_data.get("full_name", "") or customer_data.get("name", "")
        tax_id = customer_data.get("tax_id", "").strip()
        kpp = customer_data.get("kpp", "").strip()
        legal_address = customer_data.get("address", "").strip()

        # Пытаемся найти существующую компанию
        try:
            company = Company.objects.get(user=user)
            # Обновляем данные компании
            company.legal_name = legal_name
            company.tax_id = tax_id
            company.kpp = kpp
            company.legal_address = legal_address
            company.save()
            logger.debug(f"Обновлена компания для пользователя {user.onec_id}")
        except Company.DoesNotExist:
            # Создаем новую компанию
            company = Company.objects.create(
                user=user,
                legal_name=legal_name,
                tax_id=tax_id,
                kpp=kpp,
                legal_address=legal_address,
            )
            logger.info(f"Создана компания '{legal_name}' для пользователя {user.onec_id}")

        return company

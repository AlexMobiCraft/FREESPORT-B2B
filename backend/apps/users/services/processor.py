"""
Процессор данных клиентов для импорта в систему
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.users.models import Company, User

if TYPE_CHECKING:
    from apps.products.models import ImportSession


logger = logging.getLogger(__name__)


class CustomerDataProcessor:
    """
    Процессор данных клиентов для импорта в систему
    Обрабатывает данные из парсера и создает/обновляет пользователей
    """

    # Маппинг ролей 1С → роли платформы (утверждено PO 22.09.2025)
    ROLE_MAPPING = {
        "Опт 1": "wholesale_level1",
        "Опт 2": "wholesale_level2",
        "Опт 3": "wholesale_level3",
        "Тренерская": "trainer",
        "РРЦ": "retail",
    }

    def __init__(self, session_id: int):
        """
        Инициализирует процессор с ID сессии импорта.

        Args:
            session_id: ID объекта ImportSession
        """
        from apps.products.models import ImportSession

        self.session = ImportSession.objects.get(pk=session_id)

    def map_role(self, onec_role: str) -> str:
        """
        Маппинг роли из 1С на роль платформы.

        Args:
            onec_role: Тип клиента из 1С

        Returns:
            str: Роль в системе платформы
        """
        return self.ROLE_MAPPING.get(onec_role, "retail")  # fallback к retail

    def process_customer(self, customer_data: dict[str, Any]) -> User | None:
        """
        Обрабатывает данные одного клиента: создает или обновляет.

        Args:
            customer_data: Словарь с данными клиента из парсера

        Returns:
            Optional[User]: Созданный/обновленный пользователь или None при ошибке
        """
        onec_id = customer_data.get("onec_id")
        if not onec_id:
            logger.error("Отсутствует onec_id в данных клиента")
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

                # Определение роли
                customer_type_from_1c = customer_data.get("customer_type", "")
                role = self.map_role(customer_type_from_1c)

                if existing_user:
                    # Обновление существующего клиента
                    user = self._update_customer(existing_user, customer_data, role)
                    self._log_operation(
                        user=user,
                        onec_id=onec_id,
                        operation_type="updated",
                        status="success",
                        details={
                            "previous_role": existing_user.role,
                            "new_role": role,
                        },
                    )
                else:
                    # Создание нового клиента
                    user = self._create_customer(customer_data, role)
                    self._log_operation(
                        user=user,
                        onec_id=onec_id,
                        operation_type="created",
                        status="success",
                        details={
                            "role": role,
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
            Dict: Статистика обработки (total, created, updated, skipped, errors)
        """
        stats = {
            "total": len(customers_data),
            "created": 0,
            "updated": 0,
            "skipped": 0,
            "errors": 0,
        }

        for i, customer_data in enumerate(customers_data, 1):
            logger.debug(f"Обработка клиента {i}/{len(customers_data)}")

            # Получаем onec_id перед обработкой для логирования
            onec_id = customer_data.get("onec_id", f"unknown-{i}")

            # Проверяем, существует ли уже пользователь
            existing_user = self._find_duplicate(customer_data)

            result = self.process_customer(customer_data)

            if result:
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

    def _update_customer(self, user: User, customer_data: dict[str, Any], role: str) -> User:
        """
        Обновляет существующего пользователя данными из 1С.

        Args:
            user: Существующий пользователь
            customer_data: Словарь с данными клиента
            role: Новая роль пользователя

        Returns:
            User: Обновленный пользователь
        """
        # Обновляем поля из 1С
        user.first_name = customer_data.get("first_name", user.first_name)
        user.last_name = customer_data.get("last_name", user.last_name)
        user.role = role
        # Нормализуем телефон перед обновлением
        phone = customer_data.get("phone", "")
        if phone:
            user.phone = self._normalize_phone(phone)
        user.company_name = customer_data.get("company_name", user.company_name)
        user.tax_id = customer_data.get("tax_id", user.tax_id)
        # Обновляем onec_id если его не было (дубликат найден по email)
        if not user.onec_id:
            user.onec_id = customer_data.get("onec_id")
        user.sync_status = "synced"
        user.last_sync_at = timezone.now()

        user.save()

        # Создаем/обновляем объект Company для B2B клиентов
        customer_type = customer_data.get("customer_type", "")
        if customer_type in ["legal_entity", "individual_entrepreneur"]:
            self._create_or_update_company(user, customer_data)

        logger.info(f"Обновлен пользователь: {str(user.email or user.onec_id)} (role={role})")
        return user

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

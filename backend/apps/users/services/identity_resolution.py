"""
Сервис детерминированной идентификации клиентов между порталом и 1С
"""

import logging
import re
from typing import Optional, Tuple

from apps.common.models import CustomerSyncLog
from apps.users.models import User

logger = logging.getLogger(__name__)


class CustomerIdentityResolver:
    """
    Сервис детерминированной идентификации клиентов между порталом и 1С.

    Использует приоритетную систему идентификации:
    1. onec_id - точное совпадение ID из 1С
    2. onec_guid - точное совпадение GUID из 1С
    3. tax_id - ИНН для B2B клиентов
    4. email - email для B2C клиентов
    """

    IDENTIFICATION_METHODS = [
        "onec_id",  # Приоритет 1: точное совпадение ID из 1С
        "onec_guid",  # Приоритет 2: точное совпадение GUID из 1С
        "tax_id",  # Приоритет 3: ИНН для B2B клиентов
        "email",  # Приоритет 4: email для B2C клиентов
    ]

    def identify_customer(self, onec_customer_data: dict) -> Tuple[Optional[User], Optional[str]]:
        """
        Главный метод идентификации клиента.

        Args:
            onec_customer_data: Данные клиента из 1С

        Returns:
            tuple: (User|None, str|None) - найденный клиент и метод идентификации
        """
        # Приоритет 1: Поиск по onec_id
        if onec_id := onec_customer_data.get("onec_id"):
            customer = self._find_by_onec_id(onec_id)
            if customer:
                self._log_identification("onec_id", customer, onec_customer_data)
                return customer, "onec_id"

        # Приоритет 2: Поиск по onec_guid
        if onec_guid := onec_customer_data.get("onec_guid"):
            customer = self._find_by_onec_guid(onec_guid)
            if customer:
                self._log_identification("onec_guid", customer, onec_customer_data)
                return customer, "onec_guid"

        # Приоритет 3: Поиск B2B по ИНН
        if tax_id := onec_customer_data.get("tax_id"):
            normalized_inn = self.normalize_inn(tax_id)
            if normalized_inn and self._validate_inn(normalized_inn):
                customer = self._find_by_tax_id(normalized_inn)
                if customer:
                    self._log_identification("tax_id", customer, onec_customer_data)
                    return customer, "tax_id"

        # Приоритет 4: Поиск B2C по email
        if email := onec_customer_data.get("email"):
            normalized_email = self.normalize_email(email)
            if normalized_email:
                customer = self._find_by_email(normalized_email)
                if customer:
                    self._log_identification("email", customer, onec_customer_data)
                    return customer, "email"

        # Клиент не найден
        self._log_identification("not_found", None, onec_customer_data)
        return None, None

    def _find_by_onec_id(self, onec_id: str) -> Optional[User]:
        """Точный поиск по onec_id"""
        try:
            return User.objects.get(onec_id=onec_id)
        except User.DoesNotExist:
            return None

    def _find_by_onec_guid(self, onec_guid: str) -> Optional[User]:
        """Точный поиск по onec_guid"""
        try:
            return User.objects.get(onec_guid=onec_guid)
        except User.DoesNotExist:
            return None

    def _find_by_tax_id(self, tax_id: str) -> Optional[User]:
        """Точный поиск по ИНН (B2B клиенты)"""
        try:
            return User.objects.get(tax_id=tax_id)
        except User.DoesNotExist:
            return None

    def _find_by_email(self, email: str) -> Optional[User]:
        """Точный поиск по email (B2C клиенты)"""
        try:
            return User.objects.get(email=email)
        except User.DoesNotExist:
            return None

    def normalize_inn(self, inn: str) -> Optional[str]:
        """
        Нормализация ИНН.

        Args:
            inn: ИНН в любом формате

        Returns:
            Нормализованный ИНН (только цифры) или None
        """
        if not inn:
            return None

        # Убираем все нецифровые символы
        digits_only = re.sub(r"[^\d]", "", str(inn))

        # ИНН должен быть 10 или 12 цифр
        if len(digits_only) not in [10, 12]:
            logger.warning(f"Invalid INN format: {inn}")
            return None

        return digits_only

    def _validate_inn(self, inn: str) -> bool:
        """
        Валидация формата ИНН.

        Args:
            inn: Нормализованный ИНН

        Returns:
            True если формат корректен
        """
        if not inn:
            return False

        # Базовая проверка: только цифры и корректная длина
        if not inn.isdigit() or len(inn) not in [10, 12]:
            return False

        return True

    def normalize_email(self, email: str) -> Optional[str]:
        """
        Нормализация email.

        Args:
            email: Email в любом формате

        Returns:
            Нормализованный email (lowercase, trimmed) или None
        """
        if not email:
            return None

        # Приводим к lowercase и удаляем пробелы
        normalized = email.strip().lower()

        # Базовая валидация формата
        if "@" not in normalized or "." not in normalized.split("@")[1]:
            logger.warning(f"Invalid email format: {email}")
            return None

        return normalized

    def _log_identification(self, method: str, customer: Optional[User], onec_data: dict) -> None:
        """
        Логирование попытки идентификации.

        Args:
            method: Метод идентификации
            customer: Найденный клиент или None
            onec_data: Данные из 1С
        """
        # Получаем session из onec_data если есть
        session = onec_data.get("session")

        # Если нет session, не логируем (для unit-тестов)
        if not session:
            logger.debug(
                f"Identification attempt: method={method}, " f"customer={'found' if customer else 'not_found'}"
            )
            return

        CustomerSyncLog.objects.create(
            session=session,
            customer=customer,
            onec_id=onec_data.get("onec_id", ""),
            operation_type="identify_customer",
            status="success" if customer else "not_found",
            details={
                "identification_method": method,
                "onec_guid": (str(onec_data.get("onec_guid")) if onec_data.get("onec_guid") else None),
                "tax_id": onec_data.get("tax_id"),
                "email": onec_data.get("email"),
            },
        )

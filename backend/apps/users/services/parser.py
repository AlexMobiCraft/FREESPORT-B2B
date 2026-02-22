"""
Парсер данных клиентов из файлов 1С (CommerceML 3.1)
"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class CustomerDataParser:
    """
    Парсер данных клиентов из XML файлов 1С (CommerceML 3.1)
    Обрабатывает файл contragents.xml и извлекает данные контрагентов
    """

    # Namespace для CommerceML 3.1
    COMMERCEML_NS = {"cml": "urn:1C.ru:commerceml_3"}

    def parse(self, file_path: str) -> list[dict[str, Any]]:
        """
        Парсит XML файл contragents.xml и возвращает список клиентов.

        Args:
            file_path: Путь к файлу contragents.xml

        Returns:
            List[Dict]: Список словарей с данными клиентов

        Raises:
            FileNotFoundError: Если файл не найден
            ValidationError: Если структура XML некорректна
        """
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Файл не найден: {file_path}")

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Найти узел <Контрагенты>
            contragents_node = root.find("cml:Контрагенты", self.COMMERCEML_NS)
            if contragents_node is None:
                # Попробуем без namespace
                contragents_node = root.find("Контрагенты")

            if contragents_node is None:
                logger.warning(f"Узел <Контрагенты> не найден в {file_path}")
                return []

            customers = []
            # Парсим каждого контрагента
            for customer_node in contragents_node.findall(
                "cml:Контрагент", self.COMMERCEML_NS
            ) or contragents_node.findall("Контрагент"):
                try:
                    customer_data = self._parse_customer_node(customer_node)
                    if self._validate_customer_data(customer_data):
                        customers.append(customer_data)
                except Exception as e:
                    logger.error(f"Ошибка парсинга контрагента: {e}")
                    continue

            logger.info(f"Успешно распознано {len(customers)} контрагентов")
            return customers

        except ET.ParseError as e:
            raise ValidationError(f"Некорректный XML файл: {e}") from e
        except Exception as e:
            raise ValidationError(f"Ошибка при парсинге файла: {e}") from e

    def _parse_customer_node(self, customer_node: ET.Element) -> dict[str, Any]:
        """
        Парсит узел <Контрагент> и извлекает данные клиента.

        Args:
            customer_node: XML элемент <Контрагент>

        Returns:
            Dict: Словарь с данными клиента
        """
        # Извлечение базовых полей
        onec_id = self._get_text(customer_node, "Ид")
        name = self._get_text(customer_node, "Наименование")
        full_name = (
            self._get_text(customer_node, "ПолноеНаименование")
            or self._get_text(customer_node, "ОфициальноеНаименование")
            or name
        )
        role = self._get_text(customer_node, "Роль", default="Покупатель")
        tax_id = self._get_text(customer_node, "ИНН")
        kpp = self._get_text(customer_node, "КПП")

        # Извлечение контактной информации
        contact_info = self._extract_contact_info(customer_node)

        # Извлечение адреса
        address_node = customer_node.find("cml:АдресРегистрации", self.COMMERCEML_NS)
        if address_node is None:
            address_node = customer_node.find("АдресРегистрации")

        address = ""
        if address_node is not None:
            address = self._get_text(address_node, "Представление")

        # Определение типа клиента
        customer_type = self._determine_customer_type({"full_name": full_name, "tax_id": tax_id, "kpp": kpp})

        # Извлечение первого и последнего имени для физ.лиц
        first_name, last_name = self._parse_name(name, customer_type)

        # Определение компании для юр.лиц и ИП
        company_name = ""
        if customer_type in ["legal_entity", "individual_entrepreneur"]:
            company_name = name

        customer_data = {
            "onec_id": onec_id,
            "name": name,
            "full_name": full_name,
            "first_name": first_name,
            "last_name": last_name,
            "role": role,
            "tax_id": tax_id,
            "kpp": kpp,
            "email": contact_info.get("email", ""),
            "phone": contact_info.get("phone", ""),
            "address": address,
            "customer_type": customer_type,
            "company_name": company_name,
        }

        return customer_data

    def _extract_contact_info(self, customer_node: ET.Element) -> dict[str, str]:
        """
        Извлекает контактную информацию из узла <Контакты>.

        Args:
            customer_node: XML элемент <Контрагент>

        Returns:
            Dict: Словарь с email, phone и другими контактами
        """
        contacts_node = customer_node.find("cml:Контакты", self.COMMERCEML_NS)
        if contacts_node is None:
            contacts_node = customer_node.find("Контакты")

        contact_info: dict[str, str] = {"email": "", "phone": ""}

        if contacts_node is not None:
            # Парсим контакты
            for contact_node in contacts_node.findall("cml:Контакт", self.COMMERCEML_NS) or contacts_node.findall(
                "Контакт"
            ):
                contact_type = self._get_text(contact_node, "Тип")
                contact_value = self._get_text(contact_node, "Значение")

                if contact_type and contact_value:
                    if "email" in contact_type.lower() or "почта" in contact_type.lower():
                        contact_info["email"] = contact_value
                    elif "телефон" in contact_type.lower() or "phone" in contact_type.lower():
                        contact_info["phone"] = contact_value

        return contact_info

    def _determine_customer_type(self, customer_data: dict[str, Any]) -> str:
        """
        Определяет тип клиента (legal_entity, individual_entrepreneur, individual).

        Args:
            customer_data: Словарь с данными клиента

        Returns:
            str: Тип клиента
        """
        full_name = customer_data.get("full_name", "")
        tax_id = customer_data.get("tax_id", "")
        kpp = customer_data.get("kpp", "")

        # Юридическое лицо: есть КПП
        if kpp:
            return "legal_entity"

        # ИП: есть ИНН и в наименовании есть "ИП"
        if tax_id and ("ИП " in full_name or full_name.startswith("ИП")):
            return "individual_entrepreneur"

        # Физическое лицо: все остальные
        return "individual"

    def _validate_customer_data(self, customer_data: dict[str, Any]) -> bool:
        """
        Валидирует данные клиента перед обработкой.

        Args:
            customer_data: Словарь с данными клиента

        Returns:
            bool: True если данные валидны

        Raises:
            ValidationError: Если данные не проходят валидацию
        """
        # Обязательные поля
        required_fields = ["onec_id", "name"]

        for field in required_fields:
            if not customer_data.get(field):
                logger.warning(f"Пропуск клиента: отсутствует обязательное поле '{field}'")
                return False

        return True

    def _get_text(self, node: ET.Element, tag_name: str, default: str = "") -> str:
        """
        Безопасно извлекает текстовое содержимое из XML узла.

        Args:
            node: XML элемент
            tag_name: Имя тега
            default: Значение по умолчанию

        Returns:
            str: Текстовое содержимое или default
        """
        # Пробуем с namespace
        element = node.find(f"cml:{tag_name}", self.COMMERCEML_NS)
        if element is None:
            # Пробуем без namespace
            element = node.find(tag_name)

        if element is not None and element.text:
            return element.text.strip()

        return default

    def _parse_name(self, name: str, customer_type: str) -> tuple[str, str]:
        """
        Извлекает first_name и last_name из строки имени.

        Args:
            name: Полное имя
            customer_type: Тип клиента

        Returns:
            Tuple[str, str]: (first_name, last_name)
        """
        # Для юр.лиц и ИП - оставляем пустыми
        if customer_type in ["legal_entity", "individual_entrepreneur"]:
            return ("", "")

        # Для физ.лиц - пытаемся разбить имя
        parts = name.split()
        if len(parts) >= 2:
            # Предполагаем формат: Фамилия Имя Отчество
            last_name = parts[0]
            first_name = " ".join(parts[1:])
            return (first_name, last_name)
        elif len(parts) == 1:
            # Только одно слово - считаем фамилией
            return ("", parts[0])

        return ("", "")

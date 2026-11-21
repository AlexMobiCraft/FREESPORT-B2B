"""
AttributeImportService - сервис для импорта атрибутов из 1С

Парсит XML файлы propertiesGoods/*.xml и propertiesOffers/*.xml,
создает/обновляет записи Attribute и AttributeValue.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import defusedxml.ElementTree as ET
from django.conf import settings
from django.db import transaction

if TYPE_CHECKING:
    from xml.etree.ElementTree import Element

    from apps.products.models import Attribute, AttributeValue

logger = logging.getLogger(__name__)


class AttributeImportService:
    """
    Сервис импорта атрибутов из XML файлов 1С (CommerceML 3.1)

    Обрабатывает файлы propertiesGoods/*.xml и propertiesOffers/*.xml,
    извлекает определения свойств (Attribute) и их значения (AttributeValue),
    сохраняет в БД с дедупликацией по onec_id.
    """

    NAMESPACE = {"ns": "urn:1C.ru:commerceml_3"}
    MAX_FILE_SIZE = getattr(settings, "IMPORT_MAX_FILE_SIZE", 100) * 1024 * 1024  # MB to bytes

    def __init__(self, source: str = "goods", dry_run: bool = False) -> None:
        """
        Инициализация сервиса с дедупликацией

        Args:
            source: Источник импорта ('goods' или 'offers')
            dry_run: Режим тестирования без записи в БД
        """
        from apps.products.models import Attribute, Attribute1CMapping, AttributeValue, AttributeValue1CMapping

        self.attribute_model: type[Attribute] = Attribute
        self.attribute_mapping_model: type[Attribute1CMapping] = Attribute1CMapping
        self.attribute_value_model: type[AttributeValue] = AttributeValue
        self.attribute_value_mapping_model: type[AttributeValue1CMapping] = AttributeValue1CMapping

        self.source = source
        self.dry_run = dry_run

        self.stats = {
            "attributes_created": 0,
            "mappings_created": 0,
            "attributes_deduplicated": 0,
            "values_created": 0,
            "value_mappings_created": 0,
            "values_deduplicated": 0,
            "errors": 0,
        }

    def import_from_directory(self, directory_path: str) -> dict[str, int]:
        """
        Импортировать атрибуты из всех XML файлов в директории

        Args:
            directory_path: Путь к директории с XML файлами

        Returns:
            Статистика импорта (created, updated, errors)
        """
        if not os.path.exists(directory_path):
            logger.error(f"Directory not found: {directory_path}")
            raise FileNotFoundError(f"Directory not found: {directory_path}")

        if not os.path.isdir(directory_path):
            logger.error(f"Path is not a directory: {directory_path}")
            raise ValueError(f"Path is not a directory: {directory_path}")

        xml_files = [f for f in os.listdir(directory_path) if f.endswith(".xml")]

        if not xml_files:
            logger.warning(f"No XML files found in {directory_path}")
            return self.stats

        logger.info(f"Found {len(xml_files)} XML files in {directory_path}")

        for filename in xml_files:
            file_path = os.path.join(directory_path, filename)
            try:
                self.import_from_file(file_path)
            except Exception as e:
                logger.error(f"Error processing file {filename}: {e}")
                self.stats["errors"] += 1

        logger.info(f"Import completed. Stats: {self.stats}")
        return self.stats

    def import_from_file(self, file_path: str) -> None:
        """
        Импортировать атрибуты из одного XML файла

        Args:
            file_path: Путь к XML файлу
        """
        self._validate_file(file_path)

        try:
            tree = ET.parse(file_path)
            root = tree.getroot()

            # Парсинг свойств из <Классификатор><Свойства>
            properties = self._parse_properties(root)

            # Сохранение в БД с транзакцией
            self._save_properties(properties)

            logger.info(f"Successfully processed file: {file_path}")

        except ET.ParseError as e:
            logger.error(f"XML parse error in {file_path}: {e}")
            self.stats["errors"] += 1
            raise
        except Exception as e:
            logger.error(f"Unexpected error processing {file_path}: {e}")
            self.stats["errors"] += 1
            raise

    def _validate_file(self, file_path: str) -> None:
        """Валидация файла перед парсингом"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size > self.MAX_FILE_SIZE:
            raise ValueError(
                f"File {file_path} is too large: "
                f"{file_size / (1024 * 1024):.2f} MB "
                f"(max: {self.MAX_FILE_SIZE / (1024 * 1024):.2f} MB)"
            )

        if file_size == 0:
            raise ValueError(f"File {file_path} is empty")

    def _parse_properties(self, root: Element) -> list[dict[str, Any]]:
        """
        Парсинг свойств из XML

        Args:
            root: Корневой элемент XML дерева

        Returns:
            Список словарей с данными свойств
        """
        properties: list[dict[str, Any]] = []

        # Поиск всех элементов <Свойство> внутри <Классификатор><Свойства>
        classifier = root.find(".//ns:Классификатор", self.NAMESPACE)
        if classifier is None:
            logger.warning("No <Классификатор> found in XML")
            return properties

        properties_section = classifier.find("ns:Свойства", self.NAMESPACE)
        if properties_section is None:
            logger.warning("No <Свойства> section found in XML")
            return properties

        for prop_elem in properties_section.findall("ns:Свойство", self.NAMESPACE):
            try:
                property_data = self._parse_property_element(prop_elem)
                if property_data:
                    properties.append(property_data)
            except Exception as e:
                logger.error(f"Error parsing property element: {e}")
                continue

        logger.info(f"Parsed {len(properties)} properties from XML")
        return properties

    def _parse_property_element(self, prop_elem: Element) -> dict[str, Any] | None:
        """
        Парсинг одного элемента <Свойство>

        Args:
            prop_elem: XML элемент <Свойство>

        Returns:
            Словарь с данными свойства или None если парсинг не удался
        """
        # Обязательные поля
        onec_id_elem = prop_elem.find("ns:Ид", self.NAMESPACE)
        name_elem = prop_elem.find("ns:Наименование", self.NAMESPACE)
        type_elem = prop_elem.find("ns:ТипЗначений", self.NAMESPACE)

        if onec_id_elem is None or name_elem is None:
            logger.warning("Property missing required fields (Ид or Наименование)")
            return None

        onec_id = onec_id_elem.text
        name = name_elem.text
        attr_type = type_elem.text if type_elem is not None else ""

        if not onec_id or not name:
            logger.warning("Property has empty Ид or Наименование")
            return None

        # Парсинг значений (если есть <ВариантыЗначений>)
        values = []
        values_section = prop_elem.find("ns:ВариантыЗначений", self.NAMESPACE)
        if values_section is not None:
            for value_elem in values_section.findall("ns:Справочник", self.NAMESPACE):
                value_id_elem = value_elem.find("ns:ИдЗначения", self.NAMESPACE)
                value_text_elem = value_elem.find("ns:Значение", self.NAMESPACE)

                if value_id_elem is not None and value_text_elem is not None:
                    value_id = value_id_elem.text
                    value_text = value_text_elem.text

                    if value_id and value_text:
                        values.append({"onec_id": value_id, "value": value_text.strip()})

        return {
            "onec_id": onec_id,
            "name": name.strip(),
            "type": attr_type,
            "values": values,
        }

    @transaction.atomic
    def _save_properties(self, properties: list[dict[str, Any]]) -> None:
        """
        Сохранение свойств в БД с дедупликацией по normalized_name

        Алгоритм:
        1. Проверить существующий маппинг по onec_id
        2. Если нет маппинга - искать атрибут по normalized_name
        3. Если найден - использовать существующий (дедупликация)
        4. Если не найден - создать новый (is_active=False)
        5. Создать маппинг 1С ID → Attribute
        6. Аналогично обработать значения атрибутов

        Args:
            properties: Список словарей с данными свойств
        """
        from apps.products.utils.attributes import normalize_attribute_name, normalize_attribute_value

        if self.dry_run:
            logger.info(f"DRY-RUN: Would process {len(properties)} properties from " f"{self.source}")
            return

        for prop_data in properties:
            try:
                onec_id = prop_data["onec_id"]
                onec_name = prop_data["name"]
                attr_type = prop_data["type"]
                normalized = normalize_attribute_name(onec_name)

                # Шаг 1: Проверяем существующий маппинг
                existing_mapping = self.attribute_mapping_model.objects.filter(onec_id=onec_id).first()

                if existing_mapping:
                    # Используем существующий атрибут через маппинг
                    attribute = existing_mapping.attribute
                    logger.debug(f"Found existing mapping: {onec_name} → {attribute.name}")

                    # Обновляем поля атрибута если изменились
                    if attribute.name != onec_name or attribute.type != attr_type:
                        attribute.name = onec_name
                        attribute.type = attr_type
                        attribute.save()
                        self.stats["attributes_updated"] = self.stats.get("attributes_updated", 0) + 1
                else:
                    # Шаг 2: Ищем атрибут по normalized_name для дедупликации
                    existing_attr = self.attribute_model.objects.filter(normalized_name=normalized).first()

                    if existing_attr:
                        # Дедупликация: используем существующий атрибут
                        attribute = existing_attr
                        self.stats["attributes_deduplicated"] += 1
                        logger.info(
                            f"Attribute deduplicated: '{onec_name}' → "
                            f"'{attribute.name}' (normalized: '{normalized}')"
                        )
                    else:
                        # Шаг 3: Создаем новый атрибут (is_active=False)
                        attribute = self.attribute_model.objects.create(
                            name=onec_name,
                            type=attr_type,
                            is_active=False,  # Требует ручной активации
                        )
                        self.stats["attributes_created"] += 1
                        logger.debug(f"Created new attribute: {attribute.name} " f"(id={attribute.id})")

                    # Шаг 4: Создаем маппинг 1С ID → Attribute
                    self.attribute_mapping_model.objects.create(
                        attribute=attribute,
                        onec_id=onec_id,
                        onec_name=onec_name,
                        source=self.source,
                    )
                    self.stats["mappings_created"] += 1
                    logger.debug(f"Created mapping for {onec_name} ({onec_id})")

                # Шаг 5: Обработка значений атрибута
                for value_data in prop_data["values"]:
                    try:
                        self._save_attribute_value(
                            attribute=attribute,
                            value_onec_id=value_data["onec_id"],
                            value_text=value_data["value"],
                        )
                    except Exception as e:
                        logger.error(
                            f"Error saving value '{value_data['value']}' " f"for attribute '{attribute.name}': {e}"
                        )
                        self.stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error saving property {prop_data.get('name')}: {e}")
                self.stats["errors"] += 1
                # Не пробрасываем исключение, продолжаем обработку других свойств

    def _save_attribute_value(self, attribute: Attribute, value_onec_id: str, value_text: str) -> None:
        """
        Сохранение значения атрибута с дедупликацией по normalized_value

        Args:
            attribute: Атрибут, к которому относится значение
            value_onec_id: ID значения из 1С
            value_text: Текст значения
        """
        from apps.products.utils.attributes import normalize_attribute_value

        normalized_value = normalize_attribute_value(value_text)

        # Шаг 1: Проверяем существующий маппинг значения
        existing_value_mapping = self.attribute_value_mapping_model.objects.filter(onec_id=value_onec_id).first()

        if existing_value_mapping:
            # Используем существующее значение через маппинг
            logger.debug(
                f"Found existing value mapping: {value_text} → " f"{existing_value_mapping.attribute_value.value}"
            )
            return

        # Шаг 2: Ищем значение по (attribute, normalized_value)
        existing_value = self.attribute_value_model.objects.filter(
            attribute=attribute, normalized_value=normalized_value
        ).first()

        if existing_value:
            # Дедупликация: используем существующее значение
            value_obj = existing_value
            self.stats["values_deduplicated"] += 1
            logger.info(
                f"Value deduplicated: '{value_text}' → '{value_obj.value}' " f"for attribute '{attribute.name}'"
            )
        else:
            # Создаем новое значение
            value_obj = self.attribute_value_model.objects.create(attribute=attribute, value=value_text)
            self.stats["values_created"] += 1
            logger.debug(f"Created new value: {value_obj.value} for {attribute.name}")

        # Создаем маппинг 1С ID → AttributeValue
        self.attribute_value_mapping_model.objects.create(
            attribute_value=value_obj,
            onec_id=value_onec_id,
            onec_value=value_text,
            source=self.source,
        )
        self.stats["value_mappings_created"] += 1
        logger.debug(f"Created value mapping for {value_text} ({value_onec_id})")

    def get_stats(self) -> dict[str, int]:
        """Получить статистику импорта"""
        return self.stats.copy()

    def reset_stats(self) -> None:
        """Сбросить статистику"""
        self.stats = {
            "attributes_created": 0,
            "mappings_created": 0,
            "attributes_deduplicated": 0,
            "values_created": 0,
            "value_mappings_created": 0,
            "values_deduplicated": 0,
            "errors": 0,
        }

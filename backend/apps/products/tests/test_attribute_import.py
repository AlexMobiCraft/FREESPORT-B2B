"""
Тесты для AttributeImportService

Story 14.2: Import Attributes from 1C (Reference Data) & Admin UI

Тестирование импорта атрибутов из XML файлов:
- Unit тесты: парсинг XML (мокирование)
- Integration тесты: создание/обновление записей в БД
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest
from django.db import IntegrityError

from apps.products.models import Attribute, AttributeValue
from apps.products.services.attribute_import import AttributeImportService

if TYPE_CHECKING:
    pass


# ============================================================================
# UNIT TESTS - Парсинг XML (без БД)
# ============================================================================


@pytest.mark.unit
class TestAttributeImportServiceParsing:
    """Unit тесты для парсинга XML (мокирование файлов)"""

    def test_parse_property_with_values(self):
        """Тест парсинга свойства с вариантами значений"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <Ид>511f0999-7fbe-11ea-81c1-00155d3cae02</Ид>
                        <Наименование>Цвет</Наименование>
                        <ТипЗначений>Справочник</ТипЗначений>
                        <ВариантыЗначений>
                            <Справочник>
                                <ИдЗначения>8d71abe5-8f3b-11ea-81c1-00155d3cae02</ИдЗначения>
                                <Значение>Белый</Значение>
                            </Справочник>
                            <Справочник>
                                <ИдЗначения>8d71abe4-8f3b-11ea-81c1-00155d3cae02</ИдЗначения>
                                <Значение>Желтый</Значение>
                            </Справочник>
                        </ВариантыЗначений>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        root = ET.fromstring(xml_data)
        service = AttributeImportService()
        properties = service._parse_properties(root)

        assert len(properties) == 1
        prop = properties[0]
        assert prop["onec_id"] == "511f0999-7fbe-11ea-81c1-00155d3cae02"
        assert prop["name"] == "Цвет"
        assert prop["type"] == "Справочник"
        assert len(prop["values"]) == 2
        assert prop["values"][0]["onec_id"] == "8d71abe5-8f3b-11ea-81c1-00155d3cae02"
        assert prop["values"][0]["value"] == "Белый"
        assert prop["values"][1]["value"] == "Желтый"

    def test_parse_property_without_values(self):
        """Тест парсинга свойства без значений (например, числовое)"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <Ид>ea034d96-b7aa-11ed-9805-fa163edba792</Ид>
                        <Наименование>Высота (см)</Наименование>
                        <ТипЗначений>Число</ТипЗначений>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        root = ET.fromstring(xml_data)
        service = AttributeImportService()
        properties = service._parse_properties(root)

        assert len(properties) == 1
        prop = properties[0]
        assert prop["onec_id"] == "ea034d96-b7aa-11ed-9805-fa163edba792"
        assert prop["name"] == "Высота (см)"
        assert prop["type"] == "Число"
        assert len(prop["values"]) == 0

    def test_parse_empty_xml(self):
        """Тест парсинга XML без свойств"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        root = ET.fromstring(xml_data)
        service = AttributeImportService()
        properties = service._parse_properties(root)

        assert len(properties) == 0

    def test_parse_malformed_xml(self):
        """Тест обработки некорректного XML"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <!-- Отсутствует обязательное поле Ид -->
                        <Наименование>Цвет</Наименование>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        root = ET.fromstring(xml_data)
        service = AttributeImportService()
        properties = service._parse_properties(root)

        # Свойство без Ид должно быть пропущено
        assert len(properties) == 0

    def test_validate_file_not_found(self):
        """Тест валидации: файл не найден"""
        service = AttributeImportService()

        with pytest.raises(FileNotFoundError, match="File not found"):
            service._validate_file("/nonexistent/path/file.xml")

    def test_validate_file_too_large(self):
        """Тест валидации: файл слишком большой"""
        service = AttributeImportService()

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_file:
            # Создаем большой файл (превышает MAX_FILE_SIZE)
            large_data = b"x" * (service.MAX_FILE_SIZE + 1)
            tmp_file.write(large_data)
            tmp_file_path = tmp_file.name

        try:
            with pytest.raises(ValueError, match="is too large"):
                service._validate_file(tmp_file_path)
        finally:
            Path(tmp_file_path).unlink()

    def test_validate_empty_file(self):
        """Тест валидации: пустой файл"""
        service = AttributeImportService()

        with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp_file:
            tmp_file_path = tmp_file.name
            # Файл создан, но пустой

        try:
            with pytest.raises(ValueError, match="is empty"):
                service._validate_file(tmp_file_path)
        finally:
            Path(tmp_file_path).unlink()


# ============================================================================
# INTEGRATION TESTS - Работа с БД
# ============================================================================


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeImportServiceIntegration:
    """Integration тесты для импорта с реальной БД"""

    def test_import_creates_attribute_and_values(self):
        """Тест создания атрибута и его значений"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <Ид>test-attr-001</Ид>
                        <Наименование>Тестовый атрибут</Наименование>
                        <ТипЗначений>Справочник</ТипЗначений>
                        <ВариантыЗначений>
                            <Справочник>
                                <ИдЗначения>test-val-001</ИдЗначения>
                                <Значение>Значение 1</Значение>
                            </Справочник>
                        </ВариантыЗначений>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(xml_data)
            tmp_file_path = tmp_file.name

        try:
            service = AttributeImportService()
            service.import_from_file(tmp_file_path)

            # Проверяем что атрибут создан
            attribute = Attribute.objects.get(onec_mappings__onec_id="test-attr-001")
            assert attribute.name == "Тестовый атрибут"
            assert attribute.type == "Справочник"
            assert attribute.slug  # slug должен быть сгенерирован

            # Проверяем что значение создано
            value = AttributeValue.objects.get(onec_mappings__onec_id="test-val-001")
            assert value.value == "Значение 1"
            assert value.attribute == attribute
            assert value.slug  # slug должен быть сгенерирован

            # Проверяем статистику
            stats = service.get_stats()
            assert stats["attributes_created"] == 1
            assert stats["values_created"] == 1
            assert stats["mappings_created"] == 1
            assert stats["value_mappings_created"] == 1
            assert stats["errors"] == 0

        finally:
            Path(tmp_file_path).unlink()

    def test_import_idempotency(self):
        """Тест идемпотентности: повторный импорт не создает дубликатов"""
        import defusedxml.ElementTree as ET

        xml_data = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <Ид>test-idempotent-001</Ид>
                        <Наименование>Идемпотентный атрибут</Наименование>
                        <ТипЗначений>Справочник</ТипЗначений>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(xml_data)
            tmp_file_path = tmp_file.name

        try:
            service1 = AttributeImportService()
            service1.import_from_file(tmp_file_path)

            count_after_first = Attribute.objects.filter(onec_mappings__onec_id="test-idempotent-001").count()
            assert count_after_first == 1

            # Второй импорт того же файла
            service2 = AttributeImportService()
            service2.import_from_file(tmp_file_path)

            count_after_second = Attribute.objects.filter(onec_mappings__onec_id="test-idempotent-001").count()
            assert count_after_second == 1  # Не должно быть дубликатов

            # Проверяем статистику второго импорта
            stats2 = service2.get_stats()
            assert stats2.get("attributes_updated", 0) == 0  # Service doesn't count "updated" if no changes
            assert stats2["attributes_deduplicated"] == 0
            assert stats2["attributes_created"] == 0

        finally:
            Path(tmp_file_path).unlink()

    def test_import_updates_existing_attribute(self):
        """Тест обновления существующего атрибута"""
        import defusedxml.ElementTree as ET

        # Первый импорт
        xml_data_1 = """<?xml version="1.0" encoding="UTF-8"?>
        <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
            <Классификатор>
                <Свойства>
                    <Свойство>
                        <Ид>test-update-001</Ид>
                        <Наименование>Старое название</Наименование>
                        <ТипЗначений>Справочник</ТипЗначений>
                    </Свойство>
                </Свойства>
            </Классификатор>
        </КоммерческаяИнформация>
        """

        with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp_file:
            tmp_file.write(xml_data_1)
            tmp_file_path = tmp_file.name

        try:
            service1 = AttributeImportService()
            service1.import_from_file(tmp_file_path)

            # Второй импорт с обновленными данными
            xml_data_2 = """<?xml version="1.0" encoding="UTF-8"?>
            <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
                <Классификатор>
                    <Свойства>
                        <Свойство>
                            <Ид>test-update-001</Ид>
                            <Наименование>Новое название</Наименование>
                            <ТипЗначений>Строка</ТипЗначений>
                        </Свойство>
                    </Свойства>
                </Классификатор>
            </КоммерческаяИнформация>
            """

            with tempfile.NamedTemporaryFile(mode="w", suffix=".xml", delete=False, encoding="utf-8") as tmp_file2:
                tmp_file2.write(xml_data_2)
                tmp_file_path2 = tmp_file2.name

            service2 = AttributeImportService()
            service2.import_from_file(tmp_file_path2)

            # Проверяем что данные обновились (через маппинг)
            attribute = Attribute.objects.get(onec_mappings__onec_id="test-update-001")
            assert attribute.name == "Новое название"
            assert attribute.type == "Строка"

            # Проверяем что запись одна (не создано дубликатов)
            count = Attribute.objects.filter(onec_mappings__onec_id="test-update-001").count()
            assert count == 1

            Path(tmp_file_path2).unlink()

        finally:
            Path(tmp_file_path).unlink()

    def test_import_from_directory(self):
        """Тест импорта из директории с несколькими XML файлами"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Создаем несколько XML файлов
            xml_data_1 = """<?xml version="1.0" encoding="UTF-8"?>
            <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
                <Классификатор>
                    <Свойства>
                        <Свойство>
                            <Ид>test-dir-001</Ид>
                            <Наименование>Атрибут 1</Наименование>
                            <ТипЗначений>Справочник</ТипЗначений>
                        </Свойство>
                    </Свойства>
                </Классификатор>
            </КоммерческаяИнформация>
            """

            xml_data_2 = """<?xml version="1.0" encoding="UTF-8"?>
            <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
                <Классификатор>
                    <Свойства>
                        <Свойство>
                            <Ид>test-dir-002</Ид>
                            <Наименование>Атрибут 2</Наименование>
                            <ТипЗначений>Число</ТипЗначений>
                        </Свойство>
                    </Свойства>
                </Классификатор>
            </КоммерческаяИнформация>
            """

            file1_path = Path(tmp_dir) / "file1.xml"
            file2_path = Path(tmp_dir) / "file2.xml"

            file1_path.write_text(xml_data_1, encoding="utf-8")
            file2_path.write_text(xml_data_2, encoding="utf-8")

            service = AttributeImportService()
            stats = service.import_from_directory(tmp_dir)

            # Проверяем что оба атрибута созданы
            assert Attribute.objects.filter(onec_mappings__onec_id="test-dir-001").exists()
            assert Attribute.objects.filter(onec_mappings__onec_id="test-dir-002").exists()

            # Проверяем статистику
            assert stats["attributes_created"] == 2
            assert stats["errors"] == 0

    def test_import_from_nonexistent_directory(self):
        """Тест импорта из несуществующей директории"""
        service = AttributeImportService()

        with pytest.raises(FileNotFoundError, match="Directory not found"):
            service.import_from_directory("/nonexistent/directory")


# ============================================================================
# ADMIN UI INTEGRATION TESTS
# ============================================================================


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeAdminUI:
    """Integration тесты для админ интерфейса атрибутов"""

    def test_attribute_admin_values_count(self):
        """Тест отображения количества значений в админке"""
        from django.contrib.admin.sites import AdminSite

        from apps.products.admin import AttributeAdmin
        from apps.products.models import Attribute1CMapping, AttributeValue1CMapping

        # Создаем атрибут с несколькими значениями
        attribute = Attribute.objects.create(name="Тестовый атрибут", type="Справочник")
        Attribute1CMapping.objects.create(attribute=attribute, onec_id="test-admin-001", onec_name="Тест")

        val1 = AttributeValue.objects.create(attribute=attribute, value="Значение 1")
        AttributeValue1CMapping.objects.create(attribute_value=val1, onec_id="test-admin-val-001")

        val2 = AttributeValue.objects.create(attribute=attribute, value="Значение 2")
        AttributeValue1CMapping.objects.create(attribute_value=val2, onec_id="test-admin-val-002")

        val3 = AttributeValue.objects.create(attribute=attribute, value="Значение 3")
        AttributeValue1CMapping.objects.create(attribute_value=val3, onec_id="test-admin-val-003")

        # Создаем инстанс AdminSite и AttributeAdmin
        site = AdminSite()
        admin_instance = AttributeAdmin(Attribute, site)

        # Проверяем метод values_count
        count = admin_instance.values_count(attribute)
        assert count == 3

    def test_attribute_admin_list_display(self):
        """Тест конфигурации list_display в админке"""
        from apps.products.admin import AttributeAdmin

        expected_fields = [
            "name",
            "slug",
            "normalized_name",
            "is_active",
            "type",
            "values_count",
            "mappings_count",
            "created_at",
        ]
        assert AttributeAdmin.list_display == tuple(expected_fields)

    def test_attribute_value_admin_list_display(self):
        """Тест конфигурации list_display для AttributeValue в админке"""
        from apps.products.admin import AttributeValueAdmin

        expected_fields = [
            "value",
            "attribute",
            "slug",
            "normalized_value",
            "mappings_count",
            "created_at",
        ]
        assert AttributeValueAdmin.list_display == tuple(expected_fields)

    def test_attribute_admin_has_inline(self):
        """Тест наличия inline для AttributeValue в AttributeAdmin"""
        from apps.products.admin import AttributeAdmin, AttributeValueInline

        # Проверяем что inline настроен
        assert len(AttributeAdmin.inlines) == 2
        assert AttributeValueInline in AttributeAdmin.inlines

    def test_attribute_value_inline_configuration(self):
        """Тест конфигурации AttributeValueInline"""
        from apps.products.admin import AttributeValueInline

        # Проверяем настройки inline
        assert AttributeValueInline.model == AttributeValue
        assert AttributeValueInline.extra == 0
        assert AttributeValueInline.can_delete is True
        assert AttributeValueInline.show_change_link is True
        assert "value" in AttributeValueInline.fields
        assert "slug" in AttributeValueInline.fields
        # onec_id removed from fields in favor of inline mappings
        # checking logic or explicit mapping inline

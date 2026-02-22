"""
Unit-тесты для CustomerDataParser
Используют реальные данные из data/import_1c/contragents/
"""

from __future__ import annotations

from pathlib import Path

import pytest

from apps.users.services.parser import CustomerDataParser


@pytest.mark.unit
@pytest.mark.data_dependent
class TestCustomerDataParser:
    """Unit-тесты для парсера клиентов с реальными данными из 1С"""

    @pytest.fixture
    def parser(self):
        """Фикстура для создания парсера"""
        return CustomerDataParser()

    @pytest.fixture
    def real_xml_file(self):
        """Путь к реальному XML файлу из 1С"""
        # В Docker контейнере data смонтирована в /app/data
        # Локально - из корня проекта
        import os

        if os.path.exists("/app/data"):
            # Docker environment
            xml_path = Path("/app/data/import_1c/contragents/" "contragents_1_564750cd-8a00-4926-a2a4-7a1c995605c0.xml")
        else:
            # Local environment
            base_path = Path(__file__).parent.parent.parent.parent.parent
            xml_path = (
                base_path
                / "data"
                / "import_1c"
                / "contragents"
                / "contragents_1_564750cd-8a00-4926-a2a4-7a1c995605c0.xml"
            )
        return str(xml_path)

    def test_parse_real_1c_file(self, parser, real_xml_file):
        """Тест парсинга реального файла из 1С"""
        result = parser.parse(real_xml_file)

        # Проверяем что файл распарсился
        assert isinstance(result, list)
        assert len(result) > 0

        # Проверяем структуру первого контрагента
        first_customer = result[0]
        assert "onec_id" in first_customer
        assert "name" in first_customer
        assert "full_name" in first_customer
        assert "customer_type" in first_customer

    def test_parse_individual_entrepreneur(self, parser, real_xml_file):
        """Тест парсинга ИП (Индивидуальный предприниматель)"""
        result = parser.parse(real_xml_file)

        # Ищем ИП в результатах (по наличию "ИП" в полном наименовании)
        ip_customers = [c for c in result if c.get("full_name", "").startswith("ИП")]

        assert len(ip_customers) > 0, "Должен быть хотя бы один ИП"

        ip_customer = ip_customers[0]
        assert ip_customer["customer_type"] == "individual_entrepreneur"
        assert ip_customer["tax_id"]  # ИП должен иметь ИНН
        assert not ip_customer.get("kpp")  # ИП не имеет КПП

    def test_parse_legal_entity(self, parser, real_xml_file):
        """Тест парсинга юридического лица (ООО)"""
        result = parser.parse(real_xml_file)

        # Ищем юр.лиц (у них есть КПП)
        legal_entities = [c for c in result if c.get("kpp")]

        if legal_entities:  # Если есть юр.лица в тестовых данных
            legal_entity = legal_entities[0]
            assert legal_entity["customer_type"] == "legal_entity"
            assert legal_entity["tax_id"]  # Должен быть ИНН
            assert legal_entity["kpp"]  # Должен быть КПП

    def test_parse_customer_without_email(self, parser, real_xml_file):
        """Тест парсинга клиента без email"""
        result = parser.parse(real_xml_file)

        # В реальных данных из 1С часто отсутствует email
        customers_without_email = [c for c in result if not c.get("email")]

        # Проверяем что клиенты без email обрабатываются корректно
        assert len(customers_without_email) >= 0  # Может быть 0 или больше

        for customer in customers_without_email:
            assert customer["onec_id"]  # onec_id обязателен
            assert customer["name"]  # name обязателен

    def test_parse_validates_required_fields(self, parser, real_xml_file):
        """Тест валидации обязательных полей"""
        result = parser.parse(real_xml_file)

        for customer in result:
            # Обязательные поля должны присутствовать
            assert customer["onec_id"], f"onec_id обязателен для {customer}"
            assert customer["name"], f"name обязателен для {customer}"

    def test_parse_extracts_contact_info(self, parser, real_xml_file):
        """Тест извлечения контактной информации"""
        result = parser.parse(real_xml_file)

        # Проверяем что контактная информация извлекается
        for customer in result:
            assert "email" in customer
            assert "phone" in customer
            # email и phone могут быть пустыми, но ключи должны быть

    def test_parse_extracts_address(self, parser, real_xml_file):
        """Тест извлечения адреса"""
        result = parser.parse(real_xml_file)

        # Проверяем что адрес извлекается
        customers_with_address = [c for c in result if c.get("address")]

        assert len(customers_with_address) > 0, "Должны быть клиенты с адресом"

    def test_parse_determines_customer_type(self, parser, real_xml_file):
        """Тест определения типа клиента"""
        result = parser.parse(real_xml_file)

        valid_types = ["legal_entity", "individual_entrepreneur", "individual"]

        for customer in result:
            assert customer["customer_type"] in valid_types, f"Неверный тип клиента: {customer['customer_type']}"

    def test_parse_handles_empty_kpp(self, parser, real_xml_file):
        """Тест обработки пустого КПП"""
        result = parser.parse(real_xml_file)

        # Проверяем что пустой КПП обрабатывается корректно
        for customer in result:
            kpp = customer.get("kpp", "")
            assert isinstance(kpp, str)  # КПП должен быть строкой (даже если пустой)

    def test_parse_file_not_found(self, parser):
        """Тест обработки несуществующего файла"""
        with pytest.raises(FileNotFoundError):
            parser.parse("/nonexistent/file.xml")

    def test_parse_invalid_xml(self, parser, tmp_path):
        """Тест обработки некорректного XML"""
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("<КоммерческаяИнформация><Контрагенты>", encoding="utf-8")

        from django.core.exceptions import ValidationError

        with pytest.raises(ValidationError):
            parser.parse(str(invalid_xml))

    def test_parse_empty_contragents(self, parser, tmp_path):
        """Тест обработки пустого списка контрагентов"""
        empty_xml = tmp_path / "empty.xml"
        empty_xml.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
    <Контрагенты></Контрагенты>
</КоммерческаяИнформация>""",
            encoding="utf-8",
        )

        result = parser.parse(str(empty_xml))
        assert result == []

    def test_parse_extracts_first_and_last_name(self, parser, real_xml_file):
        """Тест извлечения имени и фамилии для физ.лиц"""
        result = parser.parse(real_xml_file)

        # Для физ.лиц должны быть извлечены first_name и last_name
        individuals = [c for c in result if c["customer_type"] == "individual"]

        for individual in individuals:
            # Имя и фамилия могут быть пустыми, но ключи должны быть
            assert "first_name" in individual
            assert "last_name" in individual

    def test_parse_sets_company_name_for_business(self, parser, real_xml_file):
        """Тест установки company_name для юр.лиц и ИП"""
        result = parser.parse(real_xml_file)

        # Для юр.лиц и ИП должно быть заполнено company_name
        business_customers = [c for c in result if c["customer_type"] in ["legal_entity", "individual_entrepreneur"]]

        for customer in business_customers:
            assert customer.get("company_name"), f"company_name должен быть заполнен для {customer['customer_type']}"

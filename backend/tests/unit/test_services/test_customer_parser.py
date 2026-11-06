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
        """Путь к реальному XML файлу из 1С.

        Docker: data смонтирована в /app/data.
        Локально/CI: backend/data/import_1c/ (BASE_DIR = backend/).
        """
        import os

        if os.path.exists("/app/data"):
            xml_path = Path("/app/data/import_1c/contragents/contragents_1_564750cd-8a00-4926-a2a4-7a1c995605c0.xml")
        else:
            # backend/tests/unit/test_services/test_customer_parser.py → parents[3] = backend/
            xml_path = (
                Path(__file__).resolve().parents[3]
                / "data"
                / "import_1c"
                / "contragents"
                / "contragents_1_564750cd-8a00-4926-a2a4-7a1c995605c0.xml"
            )
        if not xml_path.exists():
            pytest.skip(f"Реальный dataset 1С не найден: {xml_path}")
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

    @pytest.mark.django_db
    def test_role_extracted_for_every_real_contragent(self, parser, real_xml_file):
        """
        Все контрагенты реальной выгрузки проходят фильтр импорта.

        Фильтр по <Роль> отсекает не-покупателей, поэтому ошибка в разборе
        тега привела бы к пропуску всей базы контрагентов разом.
        """
        from apps.products.models import ImportSession
        from apps.users.services.processor import CustomerDataProcessor

        result = parser.parse(real_xml_file)
        assert all(customer["role"] for customer in result)

        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CUSTOMERS,
            status=ImportSession.ImportStatus.STARTED,
        )
        processor = CustomerDataProcessor(session_id=session.pk)

        skipped = [customer for customer in result if not processor.is_buyer(customer)]
        assert skipped == [], f"Фильтр отсеял {len(skipped)} реальных контрагентов"

    def test_multiple_role_elements_are_all_collected(self, parser, tmp_path):
        """
        Несколько <Роль> у одного контрагента собираются целиком.

        CommerceML повторяет элемент, а не перечисляет роли в одном теге:
        чтение только первого пропустило бы покупателя, у которого первой
        указана роль поставщика.
        """
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3" ВерсияСхемы="3.1">'
            "<Контрагенты><Контрагент>"
            "<Ид>test-multi-role</Ид>"
            "<Наименование>ООО Смешанная роль</Наименование>"
            "<Роль>Поставщик</Роль><Роль>Покупатель</Роль>"
            "<ИНН>7707083893</ИНН><КПП>770701001</КПП>"
            "</Контрагент></Контрагенты></КоммерческаяИнформация>"
        )
        xml_file = tmp_path / "multi_role.xml"
        xml_file.write_text(xml, encoding="utf-8")

        result = parser.parse(str(xml_file))

        assert len(result) == 1
        assert "Покупатель" in result[0]["role"]
        assert "Поставщик" in result[0]["role"]

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


def _import_1c_dir() -> Path:
    """
    Каталог реальных выгрузок 1С.

    Путь считается от settings.BASE_DIR (каталог backend/), а не от
    расположения тестового файла: локально и в контейнере это единственный
    вариант, дающий один и тот же каталог.
    """
    from django.conf import settings

    return Path(settings.BASE_DIR) / "data" / "import_1c"


def _parse_dir(directory: Path) -> list[dict]:
    """Разбирает все файлы contragents*.xml каталога одним списком.

    Имена файлов задаёт 1С (шаблон contragents_<пакет>_<GUID>.xml, GUID
    новый при каждой выгрузке) — поэтому только глоб, никаких зашитых имён.
    """
    files = sorted(directory.glob("contragents*.xml"))
    if not files:
        pytest.skip(f"Реальный dataset 1С не найден: {directory}")

    parser = CustomerDataParser()
    customers: list[dict] = []
    for file_path in files:
        customers.extend(parser.parse(str(file_path)))
    return customers


@pytest.fixture(scope="module")
def pricetype_customers() -> list[dict]:
    """Контрагенты снимка со второй редакцией патча (разбор один раз на модуль)."""
    return _parse_dir(_import_1c_dir() / "contragents_pricetype")


@pytest.fixture(scope="module")
def legacy_customers() -> list[dict]:
    """Контрагенты старого снимка — блока реквизитов нет ни у кого."""
    return _parse_dir(_import_1c_dir() / "contragents")


@pytest.mark.unit
@pytest.mark.data_dependent
class TestCustomerParserPriceType:
    """
    Разбор блока <ЗначенияРеквизитов> — вид цен из соглашения об условиях продаж.

    Блок формирует патч тиражного расширения БУС; тесты идут только на
    реальных выгрузках (NFR-3940-01), синтетический XML под эти проверки
    запрещён.
    """

    def test_price_type_id_and_meta_extracted(self, pricetype_customers):
        """AC2: GUID вида цен и диагностическая четвёрка попадают в customer_data."""
        with_price_type = [c for c in pricetype_customers if c["price_type_ids"]]
        assert with_price_type, "В снимке нет ни одного контрагента с ТипЦенId"

        for customer in with_price_type:
            for guid in customer["price_type_ids"]:
                assert guid == guid.lower(), f"GUID не приведён к нижнему регистру: {guid}"
                assert guid == guid.strip()
            assert customer["price_type_meta"], "Есть GUID, но нет диагностической четвёрки"
            for meta in customer["price_type_meta"]:
                assert set(meta) == {
                    "price_type_id",
                    "price_type_name",
                    "agreement_name",
                    "agreement_is_standard",
                }
                assert isinstance(meta["agreement_is_standard"], bool)
                assert meta["price_type_id"] in customer["price_type_ids"]

        # Наименование вида цен и признак типового соглашения реально читаются,
        # а не остаются значениями по умолчанию.
        assert any(m["price_type_name"] for c in with_price_type for m in c["price_type_meta"])
        assert any(m["agreement_is_standard"] is True for c in with_price_type for m in c["price_type_meta"])

    def test_duplicate_price_type_id_deduplicated(self, pricetype_customers):
        """
        AC4: один вид цен на двух соглашениях даёт один GUID, но обе четвёрки.

        У маркетплейсов соглашения «Выкуп …» и «Комиссионное …» висят на
        РРЦ. Без дедупликации в парсере такой контрагент получил бы ложный
        ambiguous при разрешении роли (стори 40.2).
        """
        duplicated = [c for c in pricetype_customers if len(c["price_type_meta"]) > len(c["price_type_ids"])]
        assert duplicated, "В снимке нет контрагентов с повторяющимся ТипЦенId"

        for customer in duplicated:
            ids = customer["price_type_ids"]
            assert len(ids) == len(set(ids)), f"Повтор GUID в price_type_ids: {ids}"

        # Эталонный случай снимка: один GUID, две четвёрки.
        marketplace = [c for c in duplicated if len(c["price_type_ids"]) == 1 and len(c["price_type_meta"]) == 2]
        assert marketplace, "Не найден контрагент с одним видом цен на двух соглашениях"

    def test_keys_present_when_attributes_block_absent(self, legacy_customers):
        """AC5: старая выгрузка без блока разбирается без исключений, ключи есть и пусты."""
        assert legacy_customers

        for customer in legacy_customers:
            assert customer["price_type_ids"] == []
            assert customer["price_type_meta"] == []
            assert customer["agreement_status"] == ""

    def test_agreement_status_no_agreement(self, pricetype_customers):
        """
        AC3: контрагент без действующего соглашения помечается статусом.

        Слово-маркер живёт в отдельном реквизите: ТипЦенId остаётся полем
        под GUID, иначе «НетСоглашения» ушло бы в разрешение роли как
        неизвестный вид цен.
        """
        without_agreement = [c for c in pricetype_customers if c["agreement_status"] == "НетСоглашения"]
        assert without_agreement, "В снимке нет контрагентов со статусом НетСоглашения — снимок первой редакции?"

        for customer in without_agreement:
            assert customer["price_type_ids"] == []

        for customer in pricetype_customers:
            for guid in customer["price_type_ids"]:
                assert "соглашен" not in guid.lower(), f"Слово-маркер попало в price_type_ids: {guid}"

    def test_role_parsing_not_affected(self, pricetype_customers):
        """AC6 (регресс): разбор <Роль> не тронут — роль есть у каждого контрагента."""
        assert all(customer["role"] for customer in pricetype_customers)
        assert any("Покупатель" in customer["role"] for customer in pricetype_customers)

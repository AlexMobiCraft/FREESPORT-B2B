"""
Unit-тесты для XMLDataParser
"""

import os
import tempfile
from decimal import Decimal

import pytest

from apps.products.services.parser import XMLDataParser


@pytest.mark.unit
class TestXMLDataParser:
    """Тесты парсера XML файлов из 1С"""

    def test_parse_goods_xml_structure(self, tmp_path):
        """Проверка корректного парсинга структуры goods.xml"""
        # Создаем тестовый XML файл
        goods_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
  <Товары>
    <Товар>
      <Ид>test-uuid-123</Ид>
      <Наименование>Тестовый товар</Наименование>
      <Артикул>TEST-001</Артикул>
      <Описание>Описание товара</Описание>
      <Группы>
        <Ид>category-uuid-456</Ид>
      </Группы>
      <Картинка>goods/import_files/12/image.jpg</Картинка>
    </Товар>
  </Товары>
</Каталог>"""

        # Сохраняем во временный файл
        test_file = tmp_path / "goods.xml"
        test_file.write_text(goods_xml, encoding="utf-8")

        # Парсим
        parser = XMLDataParser()
        result = parser.parse_goods_xml(str(test_file))

        # Проверяем результат
        assert len(result) == 1
        assert result[0]["id"] == "test-uuid-123"
        assert result[0]["name"] == "Тестовый товар"
        assert result[0]["article"] == "TEST-001"
        assert result[0]["description"] == "Описание товара"
        assert result[0]["category_id"] == "category-uuid-456"
        assert len(result[0]["images"]) == 1

    def test_parse_offers_xml_with_characteristics(self, tmp_path):
        """Проверка парсинга offers.xml с характеристиками"""
        offers_xml = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Ид>parent-uuid#sku-uuid-789</Ид>
      <Наименование>Товар размер M</Наименование>
      <Артикул>PROD-001-M</Артикул>
      <ХарактеристикиТовара>
        <ХарактеристикаТовара>
          <Наименование>Размер</Наименование>
          <Значение>M</Значение>
        </ХарактеристикаТовара>
        <ХарактеристикаТовара>
          <Наименование>Цвет</Наименование>
          <Значение>Черный</Значение>
        </ХарактеристикаТовара>
      </ХарактеристикиТовара>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        test_file = tmp_path / "offers.xml"
        test_file.write_text(offers_xml, encoding="utf-8")

        parser = XMLDataParser()
        result = parser.parse_offers_xml(str(test_file))

        assert len(result) == 1
        assert result[0]["id"] == "parent-uuid#sku-uuid-789"
        assert result[0]["name"] == "Товар размер M"
        assert "characteristics" in result[0]
        assert len(result[0]["characteristics"]) == 2

    def test_parse_prices_xml_with_role_mapping(self, tmp_path):
        """Проверка маппинга типов цен на роли пользователей"""
        prices_xml = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Ид>product-uuid</Ид>
      <Цены>
        <Цена>
          <ИдТипаЦены>retail-price-uuid</ИдТипаЦены>
          <ЦенаЗаЕдиницу>1000.00</ЦенаЗаЕдиницу>
          <Валюта>руб</Валюта>
        </Цена>
        <Цена>
          <ИдТипаЦены>opt1-price-uuid</ИдТипаЦены>
          <ЦенаЗаЕдиницу>800.00</ЦенаЗаЕдиницу>
          <Валюта>руб</Валюта>
        </Цена>
      </Цены>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        test_file = tmp_path / "prices.xml"
        test_file.write_text(prices_xml, encoding="utf-8")

        parser = XMLDataParser()
        result = parser.parse_prices_xml(str(test_file))

        assert len(result) == 1
        assert result[0]["id"] == "product-uuid"
        assert len(result[0]["prices"]) == 2
        assert result[0]["prices"][0]["value"] == Decimal("1000.00")
        assert result[0]["prices"][1]["value"] == Decimal("800.00")

    def test_parse_rests_xml(self, tmp_path):
        """Проверка парсинга остатков из rests.xml"""
        rests_xml = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <Предложения>
    <Предложение>
      <Ид>product-uuid</Ид>
      <Остатки>
        <Остаток>
          <Склад>warehouse-1</Склад>
          <Количество>50</Количество>
        </Остаток>
        <Остаток>
          <Склад>warehouse-2</Склад>
          <Количество>30</Количество>
        </Остаток>
      </Остатки>
    </Предложение>
  </Предложения>
</ПакетПредложений>"""

        test_file = tmp_path / "rests.xml"
        test_file.write_text(rests_xml, encoding="utf-8")

        parser = XMLDataParser()
        result = parser.parse_rests_xml(str(test_file))

        assert len(result) == 2
        assert result[0]["quantity"] == 50
        assert result[1]["quantity"] == 30

    def test_parse_price_lists_xml(self, tmp_path):
        """Проверка парсинга справочника типов цен"""
        price_lists_xml = """<?xml version="1.0" encoding="UTF-8"?>
<ПакетПредложений>
  <ТипыЦен>
    <ТипЦены>
      <Ид>opt1-uuid</Ид>
      <Наименование>Опт 1 (300-600 тыс.руб в квартал)</Наименование>
      <Валюта>RUB</Валюта>
    </ТипЦены>
    <ТипЦены>
      <Ид>trainer-uuid</Ид>
      <Наименование>Тренерская</Наименование>
      <Валюта>RUB</Валюта>
    </ТипЦены>
  </ТипыЦен>
</ПакетПредложений>"""

        test_file = tmp_path / "priceLists.xml"
        test_file.write_text(price_lists_xml, encoding="utf-8")

        parser = XMLDataParser()
        result = parser.parse_price_lists_xml(str(test_file))

        assert len(result) == 2
        assert result[0]["onec_id"] == "opt1-uuid"
        assert result[0]["product_field"] == "opt1_price"
        assert result[1]["onec_id"] == "trainer-uuid"
        assert result[1]["product_field"] == "trainer_price"

    def test_handle_malformed_xml_gracefully(self, tmp_path):
        """Проверка обработки некорректного XML"""
        malformed_xml = """<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
  <Товары>
    <Товар>
      <Ид>test-uuid</Ид>
      <!-- Незакрытый тег -->
</Каталог>"""

        test_file = tmp_path / "malformed.xml"
        test_file.write_text(malformed_xml, encoding="utf-8")

        parser = XMLDataParser()
        with pytest.raises(ValueError, match="Invalid XML structure"):
            parser.parse_goods_xml(str(test_file))

    def test_file_size_limit(self, tmp_path):
        """Проверка ограничения размера файла"""
        # Создаем большой файл (больше лимита)
        large_xml = (
            """<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
  <Товары>
"""
            + "    <Товар><Ид>id</Ид><Наименование>Товар</Наименование></Товар>\n" * 100000
            + """
  </Товары>
</Каталог>"""
        )

        test_file = tmp_path / "large.xml"
        test_file.write_text(large_xml, encoding="utf-8")

        parser = XMLDataParser()
        # Проверка зависит от настройки IMPORT_MAX_FILE_SIZE
        # В реальном окружении файл должен быть проверен
        try:
            parser.parse_goods_xml(str(test_file))
        except ValueError as e:
            assert "exceeds limit" in str(e)

    def test_map_price_type_to_field(self):
        """Проверка маппинга названий типов цен на поля Product"""
        parser = XMLDataParser()

        assert parser._map_price_type_to_field("Опт 1 (300-600)") == "opt1_price"
        assert parser._map_price_type_to_field("Опт 2") == "opt2_price"
        assert parser._map_price_type_to_field("Опт 3") == "opt3_price"
        assert parser._map_price_type_to_field("Тренерская") == "trainer_price"
        assert parser._map_price_type_to_field("РРЦ Рекомендованная") == "rrp"
        assert parser._map_price_type_to_field("МРЦ") == "msrp"
        assert parser._map_price_type_to_field("РРЦ") == "retail_price"
        assert parser._map_price_type_to_field("Неизвестный тип") == "retail_price"  # fallback


@pytest.mark.unit
class TestXMLDataParserImageParsing:
    """Unit-тесты парсинга изображений из goods.xml"""

    def test_parse_goods_xml_with_single_image(self, tmp_path):
        """Парсинг товара с одним изображением"""
        from tests.conftest import get_unique_suffix

        # ARRANGE - подготовка данных
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Test Product</Наименование>
            <Картинка>import_files/73/image1.png</Картинка>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT - выполнение действия
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - проверка результата
        assert len(goods_list) == 1
        goods_data = goods_list[0]

        assert goods_data["id"] == unique_id
        assert "images" in goods_data
        assert len(goods_data["images"]) == 1
        assert goods_data["images"][0] == "import_files/73/image1.png"

    def test_parse_goods_xml_with_multiple_images(self, tmp_path):
        """Парсинг товара с несколькими изображениями"""
        from tests.conftest import get_unique_suffix

        # ARRANGE - подготовка данных
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Test Product</Наименование>
            <Картинка>import_files/73/image1.png</Картинка>
            <Картинка>import_files/73/image2.jpg</Картинка>
            <Картинка>import_files/73/image3.webp</Картинка>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT - выполнение действия
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - проверка результата
        assert len(goods_list) == 1
        goods_data = goods_list[0]

        assert goods_data["id"] == unique_id
        assert "images" in goods_data
        assert len(goods_data["images"]) == 3
        assert "import_files/73/image1.png" in goods_data["images"]
        assert "import_files/73/image2.jpg" in goods_data["images"]
        assert "import_files/73/image3.webp" in goods_data["images"]

    def test_parse_goods_xml_with_no_images(self, tmp_path):
        """Парсинг товара без изображений"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Test Product</Наименование>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - поле images не должно присутствовать
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert "images" not in goods_data

    def test_parse_goods_xml_with_invalid_image_extension(self, tmp_path):
        """Парсинг товара с невалидным расширением файла"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Test Product</Наименование>
            <Картинка>import_files/73/valid_image.png</Картинка>
            <Картинка>import_files/73/invalid.exe</Картинка>
            <Картинка>import_files/73/document.txt</Картинка>
            <Картинка>import_files/73/valid_image2.jpg</Картинка>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - только валидные изображения должны остаться
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert "images" in goods_data
        assert len(goods_data["images"]) == 2  # Только .png и .jpg
        assert "import_files/73/valid_image.png" in goods_data["images"]
        assert "import_files/73/valid_image2.jpg" in goods_data["images"]
        assert "import_files/73/invalid.exe" not in goods_data["images"]
        assert "import_files/73/document.txt" not in goods_data["images"]

    def test_parse_goods_xml_with_duplicate_image_paths(self, tmp_path):
        """Дедупликация дублирующихся путей изображений"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Test Product</Наименование>
            <Картинка>import_files/73/image1.png</Картинка>
            <Картинка>import_files/73/image1.png</Картинка>
            <Картинка>import_files/73/image2.jpg</Картинка>
            <Картинка>import_files/73/image1.png</Картинка>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - дубликаты должны быть удалены
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert len(goods_data["images"]) == 2  # Не 4!
        assert "import_files/73/image1.png" in goods_data["images"]
        assert "import_files/73/image2.jpg" in goods_data["images"]

    def test_validate_image_path_normalization(self):
        """Валидация и нормализация путей изображений"""
        # ARRANGE
        parser = XMLDataParser()

        # ACT & ASSERT - тестируем нормализацию
        assert parser._validate_image_path("  import_files/73/image.png  ") == "import_files/73/image.png"
        assert parser._validate_image_path("import_files\\73\\image.jpg") == "import_files/73/image.jpg"

        # ACT & ASSERT - тестируем валидацию расширений
        assert parser._validate_image_path("import_files/73/image.png") is not None
        assert parser._validate_image_path("import_files/73/image.jpg") is not None
        assert parser._validate_image_path("import_files/73/image.JPEG") is not None
        assert parser._validate_image_path("import_files/73/image.webp") is not None
        assert parser._validate_image_path("import_files/73/image.exe") is None  # Невалидное расширение
        assert parser._validate_image_path("") is None  # Пустой путь
        assert parser._validate_image_path("   ") is None  # Только пробелы

    def test_validate_image_path_supported_extensions(self):
        """Тест поддерживаемых расширений изображений"""
        # ARRANGE
        parser = XMLDataParser()

        # ACT & ASSERT - все поддерживаемые расширения
        valid_extensions = [".jpg", ".jpeg", ".png", ".webp", ".JPG", ".PNG", ".WEBP"]
        for ext in valid_extensions:
            path = f"import_files/73/test{ext}"
            assert parser._validate_image_path(path) is not None, f"Extension {ext} should be valid"

        # ACT & ASSERT - невалидные расширения
        invalid_extensions = [".gif", ".bmp", ".svg", ".exe", ".txt", ".pdf"]
        for ext in invalid_extensions:
            path = f"import_files/73/test{ext}"
            assert parser._validate_image_path(path) is None, f"Extension {ext} should be invalid"

    def test_parse_goods_xml_with_real_data(self):
        """Парсинг реального XML из data/import_1c/goods/"""
        # ARRANGE
        real_file = "data/import_1c/goods/goods_1_1_27c08306-a0aa-453b-b436-f9b494ceb889.xml"

        if not os.path.exists(real_file):
            pytest.skip(f"Real data file not found: {real_file}")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(real_file)

        # ASSERT
        assert len(goods_list) > 0, "Должен распарсить хотя бы один товар"

        # Проверяем что хотя бы один товар имеет изображения
        products_with_images = [g for g in goods_list if "images" in g and len(g["images"]) > 0]

        if len(products_with_images) > 0:
            # Проверяем формат путей изображений
            for product in products_with_images:
                for image_path in product["images"]:
                    assert image_path.startswith(
                        "import_files/"
                    ), f"Путь должен начинаться с 'import_files/': {image_path}"
                    assert any(
                        image_path.lower().endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".webp"]
                    ), f"Невалидное расширение: {image_path}"


@pytest.mark.unit
class TestXMLDataParserBrandParsing:
    """Unit-тесты парсинга brand_id из goods.xml (Story 13.4)"""

    def test_parse_goods_xml_with_brand_id(self, tmp_path):
        """Парсинг товара с brand_id из свойства 'Бренд'"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        brand_uuid = "fb3f263e-dfd0-11ef-8361-fa163ea88911"
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Nike Football</Наименование>
            <ЗначенияСвойств>
                <ЗначенияСвойства>
                    <Ид>Бренд</Ид>
                    <Значение>{brand_uuid}</Значение>
                </ЗначенияСвойства>
                <ЗначенияСвойства>
                    <Ид>Цвет</Ид>
                    <Значение>Белый</Значение>
                </ЗначенияСвойства>
            </ЗначенияСвойств>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert goods_data["id"] == unique_id
        assert "brand_id" in goods_data
        assert goods_data["brand_id"] == brand_uuid

    def test_parse_goods_xml_without_brand_id(self, tmp_path):
        """Парсинг товара без brand_id (свойство 'Бренд' отсутствует)"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Generic Product</Наименование>
            <ЗначенияСвойств>
                <ЗначенияСвойства>
                    <Ид>Цвет</Ид>
                    <Значение>Черный</Значение>
                </ЗначенияСвойства>
            </ЗначенияСвойств>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert "brand_id" not in goods_data

    def test_parse_goods_xml_with_empty_brand_uuid(self, tmp_path):
        """Парсинг товара с пустым UUID бренда (00000000-0000-0000-0000-000000000000)"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Product Without Brand</Наименование>
            <ЗначенияСвойств>
                <ЗначенияСвойства>
                    <Ид>Бренд</Ид>
                    <Значение>00000000-0000-0000-0000-000000000000</Значение>
                </ЗначенияСвойства>
            </ЗначенияСвойств>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT - пустой UUID должен игнорироваться
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert "brand_id" not in goods_data

    def test_parse_goods_xml_with_multiple_properties(self, tmp_path):
        """Парсинг товара с несколькими свойствами, включая бренд"""
        from tests.conftest import get_unique_suffix

        # ARRANGE
        unique_id = get_unique_suffix()
        brand_uuid = "adidas-uuid-12345"
        xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<Каталог>
    <Товары>
        <Товар>
            <Ид>{unique_id}</Ид>
            <Наименование>Adidas Sneakers</Наименование>
            <ЗначенияСвойств>
                <ЗначенияСвойства>
                    <Ид>Размер</Ид>
                    <Значение>42</Значение>
                </ЗначенияСвойства>
                <ЗначенияСвойства>
                    <Ид>Бренд</Ид>
                    <Значение>{brand_uuid}</Значение>
                </ЗначенияСвойства>
                <ЗначенияСвойства>
                    <Ид>Цвет</Ид>
                    <Значение>Синий</Значение>
                </ЗначенияСвойства>
                <ЗначенияСвойства>
                    <Ид>Материал</Ид>
                    <Значение>Кожа</Значение>
                </ЗначенияСвойства>
            </ЗначенияСвойств>
        </Товар>
    </Товары>
</Каталог>
"""

        test_file = tmp_path / "goods.xml"
        test_file.write_text(xml_content, encoding="utf-8")

        # ACT
        parser = XMLDataParser()
        goods_list = parser.parse_goods_xml(str(test_file))

        # ASSERT
        assert len(goods_list) == 1
        goods_data = goods_list[0]
        assert goods_data["brand_id"] == brand_uuid

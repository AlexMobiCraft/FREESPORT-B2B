"""
Интеграционные тесты для API атрибутов товаров (Story 14.5)

Проверяет:
1. ProductSerializer возвращает поле attributes
2. ProductVariantSerializer возвращает attributes с наследованием от продукта
3. Оптимизация запросов через prefetch_related (проверка N+1 проблемы)
"""

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.products.models import Attribute, AttributeValue, Brand, Category, Product, ProductVariant


@pytest.mark.django_db
class TestProductAttributesAPI:
    """Тесты API атрибутов для Product"""

    @pytest.fixture
    def api_client(self):
        """API клиент для тестов"""
        return APIClient()

    @pytest.fixture
    def setup_data(self):
        """Подготовка тестовых данных"""
        # Создаем бренд и категорию
        brand = Brand.objects.create(name="TestBrand", slug="testbrand")
        category = Category.objects.create(name="TestCategory", slug="testcategory")

        # Создаем атрибуты
        material_attr = Attribute.objects.create(
            name="Material",
            slug="material",
            type="text",
            is_active=True,
        )
        color_attr = Attribute.objects.create(
            name="Color",
            slug="color",
            type="text",
            is_active=True,
        )

        # Создаем значения атрибутов
        cotton_value = AttributeValue.objects.create(
            attribute=material_attr,
            value="Cotton",
            slug="cotton",
        )
        red_value = AttributeValue.objects.create(
            attribute=color_attr,
            value="Red",
            slug="red",
        )

        # Создаем продукт
        product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
            description="Test description",
        )

        # Добавляем атрибуты к продукту
        product.attributes.add(cotton_value)

        return {
            "product": product,
            "brand": brand,
            "category": category,
            "material_attr": material_attr,
            "color_attr": color_attr,
            "cotton_value": cotton_value,
            "red_value": red_value,
        }

    def test_product_api_includes_attributes(self, api_client, setup_data):
        """
        Проверяет что ProductSerializer возвращает поле attributes

        AC 1: ProductSerializer includes an attributes field
        """
        product = setup_data["product"]

        # Выполняем запрос к API
        response = api_client.get(f"/api/v1/products/{product.slug}/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Проверяем наличие поля attributes
        assert "attributes" in response.data

        # Проверяем структуру атрибутов
        attributes = response.data["attributes"]
        assert isinstance(attributes, list)
        assert len(attributes) == 1

        # Проверяем формат атрибута (AC 4: API contract)
        attr = attributes[0]
        assert "name" in attr
        assert "value" in attr
        assert "slug" in attr
        assert "type" in attr

        # Проверяем значения
        assert attr["name"] == "Material"
        assert attr["value"] == "Cotton"
        assert attr["slug"] == "material"
        assert attr["type"] == "text"

    def test_product_list_api_includes_attributes(self, api_client, setup_data):
        """
        Проверяет что список продуктов возвращает attributes

        AC 1: ProductSerializer includes an attributes field
        """
        # Выполняем запрос к API
        response = api_client.get("/api/v1/products/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Проверяем наличие результатов
        assert "results" in response.data
        assert len(response.data["results"]) > 0

        # Проверяем первый продукт
        product = response.data["results"][0]
        assert "attributes" in product

        # Проверяем структуру
        attributes = product["attributes"]
        assert isinstance(attributes, list)


@pytest.mark.django_db
class TestProductVariantAttributesAPI:
    """Тесты API атрибутов для ProductVariant с наследованием"""

    @pytest.fixture
    def api_client(self):
        """API клиент для тестов"""
        return APIClient()

    @pytest.fixture
    def setup_variant_data(self):
        """Подготовка тестовых данных для вариантов"""
        # Создаем бренд и категорию
        brand = Brand.objects.create(name="TestBrand", slug="testbrand")
        category = Category.objects.create(name="TestCategory", slug="testcategory")

        # Создаем атрибуты
        material_attr = Attribute.objects.create(
            name="Material",
            slug="material",
            type="text",
            is_active=True,
        )
        size_attr = Attribute.objects.create(
            name="Size",
            slug="size",
            type="text",
            is_active=True,
        )
        color_attr = Attribute.objects.create(
            name="Color",
            slug="color",
            type="text",
            is_active=True,
        )

        # Создаем значения атрибутов
        cotton_value = AttributeValue.objects.create(
            attribute=material_attr,
            value="Cotton",
            slug="cotton",
        )
        xl_value = AttributeValue.objects.create(
            attribute=size_attr,
            value="XL",
            slug="xl",
        )
        red_value = AttributeValue.objects.create(
            attribute=color_attr,
            value="Red",
            slug="red",
        )

        # Создаем продукт
        product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
            description="Test description",
        )

        # Добавляем Material к продукту (базовый атрибут)
        product.attributes.add(cotton_value)

        # Создаем вариант
        variant = ProductVariant.objects.create(
            product=product,
            sku="TEST-SKU-001",
            onec_id="test-onec-id-001",
            color_name="Red",
            size_value="XL",
            retail_price=1000.00,
        )

        # Добавляем Size к варианту (специфичный атрибут)
        variant.attributes.add(xl_value)

        return {
            "product": product,
            "variant": variant,
            "cotton_value": cotton_value,
            "xl_value": xl_value,
            "red_value": red_value,
        }

    def test_variant_inherits_product_attributes(self, api_client, setup_variant_data):
        """
        Проверяет что вариант наследует атрибуты продукта

        AC 2: ProductVariantSerializer includes attributes field with inheritance
        AC 3: If variant doesn't have value, it inherits product's value
        """
        product = setup_variant_data["product"]

        # Выполняем запрос к API
        response = api_client.get(f"/api/v1/products/{product.slug}/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Получаем вариант из ответа
        variants = response.data["variants"]
        assert len(variants) == 1

        variant = variants[0]

        # Проверяем наличие поля attributes
        assert "attributes" in variant

        # Проверяем что вариант содержит ОБА атрибута
        # (Material от продукта + Size от варианта)
        attributes = variant["attributes"]
        assert len(attributes) == 2

        # Создаем словарь для удобной проверки
        attr_dict = {attr["name"]: attr for attr in attributes}

        # Проверяем Material (наследуется от продукта)
        assert "Material" in attr_dict
        assert attr_dict["Material"]["value"] == "Cotton"
        assert attr_dict["Material"]["slug"] == "material"

        # Проверяем Size (специфичный для варианта)
        assert "Size" in attr_dict
        assert attr_dict["Size"]["value"] == "XL"
        assert attr_dict["Size"]["slug"] == "size"

    def test_variant_overrides_product_attribute(self, api_client, setup_variant_data):
        """
        Проверяет что вариант переопределяет атрибуты продукта

        AC 2: If variant has specific value, it overrides product's value
        """
        product = setup_variant_data["product"]
        variant = setup_variant_data["variant"]
        cotton_value = setup_variant_data["cotton_value"]

        # Создаем новое значение Material для варианта (переопределение)
        polyester_value = AttributeValue.objects.create(
            attribute=cotton_value.attribute,  # Тот же атрибут Material
            value="Polyester",
            slug="polyester",
        )

        # Добавляем Polyester к варианту (переопределит Cotton от продукта)
        variant.attributes.add(polyester_value)

        # Выполняем запрос к API
        response = api_client.get(f"/api/v1/products/{product.slug}/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Получаем вариант из ответа
        variants = response.data["variants"]
        variant_data = variants[0]

        # Проверяем атрибуты
        attributes = variant_data["attributes"]
        attr_dict = {attr["name"]: attr for attr in attributes}

        # Проверяем что Material переопределен на Polyester (приоритет варианта)
        assert "Material" in attr_dict
        assert attr_dict["Material"]["value"] == "Polyester"
        assert attr_dict["Material"]["value"] != "Cotton"


@pytest.mark.django_db
class TestAttributesQueryOptimization:
    """Тесты оптимизации запросов для атрибутов (N+1 проблема)"""

    @pytest.fixture
    def api_client(self):
        """API клиент для тестов"""
        return APIClient()

    @pytest.fixture
    def setup_multiple_products(self):
        """Создание нескольких продуктов с атрибутами для проверки N+1"""
        # Создаем бренд и категорию
        brand = Brand.objects.create(name="TestBrand", slug="testbrand")
        category = Category.objects.create(name="TestCategory", slug="testcategory")

        # Создаем атрибуты
        material_attr = Attribute.objects.create(
            name="Material",
            slug="material",
            type="text",
            is_active=True,
        )

        # Создаем значение атрибута
        cotton_value = AttributeValue.objects.create(
            attribute=material_attr,
            value="Cotton",
            slug="cotton",
        )

        # Создаем 20 продуктов с атрибутами
        products = []
        for i in range(20):
            product = Product.objects.create(
                name=f"Product {i}",
                slug=f"product-{i}",
                brand=brand,
                category=category,
                description=f"Description {i}",
            )
            product.attributes.add(cotton_value)

            # Создаем вариант для каждого продукта
            ProductVariant.objects.create(
                product=product,
                sku=f"SKU-{i}",
                onec_id=f"onec-{i}",
                retail_price=1000.00 + i,
            )
            products.append(product)

        return {"products": products}

    def test_product_list_query_optimization(self, api_client, setup_multiple_products, django_assert_num_queries):
        """
        Проверяет оптимизацию запросов при получении списка продуктов

        AC 3: SQL queries are optimized using prefetch_related to prevent N+1 problems

        КРИТИЧНО: Без prefetch_related будет N+1 проблема:
        - 1 запрос для продуктов
        - N запросов для атрибутов каждого продукта (20 продуктов = 20 запросов)
        - Итого: минимум 21 запрос

        С prefetch_related:
        - 1 запрос для продуктов
        - 1 запрос для всех AttributeValue с select_related('attribute')
        - Итого: намного меньше запросов
        """
        # Допустимое количество запросов (с учетом prefetch_related)
        # Точное число зависит от структуры prefetch, но должно быть << 21
        # Оставляем запас для других запросов (пагинация, подсчеты и т.д.)
        max_queries = 15

        with django_assert_num_queries(max_queries, exact=False):
            response = api_client.get("/api/v1/products/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Проверяем что получили продукты
        results = response.data["results"]
        assert len(results) > 0

        # Проверяем что каждый продукт имеет атрибуты
        for product in results:
            assert "attributes" in product

    def test_product_detail_query_optimization(self, api_client, setup_multiple_products, django_assert_num_queries):
        """
        Проверяет оптимизацию запросов при получении детальной информации о продукте

        AC 3: SQL queries are optimized using prefetch_related

        Детальный endpoint должен загружать варианты с их атрибутами.
        Без оптимизации будет N+1 для атрибутов вариантов.
        """
        products = setup_multiple_products["products"]
        product = products[0]

        # Допустимое количество запросов
        # С prefetch_related должно быть значительно меньше чем N+1
        # Однако сложные сериализаторы (related products, breadcrumbs) добавляют запросы
        max_queries = 80

        with django_assert_num_queries(max_queries, exact=False):
            response = api_client.get(f"/api/v1/products/{product.slug}/")

        # Проверяем успешный ответ
        assert response.status_code == 200

        # Проверяем наличие атрибутов
        assert "attributes" in response.data

        # Проверяем наличие вариантов с атрибутами
        assert "variants" in response.data
        if response.data["variants"]:
            variant = response.data["variants"][0]
            assert "attributes" in variant

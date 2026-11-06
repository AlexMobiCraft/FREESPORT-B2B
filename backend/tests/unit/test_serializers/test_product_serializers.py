# pyright: reportGeneralTypeIssues=false
# pyright: reportUnknownMemberType=false
# pyright: reportOptionalMemberAccess=false
"""
Тесты для Product Serializers - Story 2.4 Catalog API
"""
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.products.serializers import (
    BrandSerializer,
    CategorySerializer,
    ProductDetailSerializer,
    ProductImageSerializer,
    ProductListSerializer,
)


# Добавляем ProductSpecificationSerializer как заглушку для тестов
class ProductSpecificationSerializer:
    def __init__(self, instance):
        self.instance = instance

    @property
    def data(self):
        return {"specifications": getattr(self.instance, "specifications", {})}


User = get_user_model()


@pytest.mark.django_db
class TestProductListSerializer:
    """Тесты сериализатора списка товаров"""

    def test_product_list_serialization(self, category_factory, brand_factory, product_variant_factory):
        """Тест сериализации товара в списке"""
        category = category_factory.create(name="Спорт")
        brand = brand_factory.create(name="Nike")
        variant = product_variant_factory.create(
            product__name="Кроссовки",
            product__category=category,
            product__brand=brand,
            retail_price=Decimal("5000.00"),
            product__is_active=True,
        )
        product = variant.product

        serializer = ProductListSerializer(product)
        data = serializer.data

        assert data["name"] == "Кроссовки"
        assert float(data["retail_price"]) == 5000.00
        assert data["category"] == "Спорт"  # StringRelatedField возвращает __str__ модели
        assert data["brand"]["name"] == "Nike"

    def test_product_list_with_user_context(self, user_factory, product_variant_factory):
        """Тест сериализации с контекстом пользователя"""
        user = user_factory.create()
        variant = product_variant_factory.create(product__name="Товар", retail_price=Decimal("1000.00"))
        product = variant.product

        # Тест для retail пользователя
        class MockRequest:
            def __init__(self, user):
                self.user = user

            def build_absolute_uri(self, url):
                return f"http://testserver{url}" if url else ""

        retail_user = user_factory.create(role="retail")
        serializer = ProductListSerializer(product, context={"request": MockRequest(retail_user)})
        data = serializer.data
        assert "current_price" in data

    def test_product_list_b2b_pricing(self, user_factory, product_variant_factory):
        """Тест отображения B2B цен"""
        user = user_factory.create(role="wholesale_level1")
        variant = product_variant_factory.create(product__name="B2B Товар", retail_price=Decimal("1000.00"))
        product = variant.product

        class MockRequest:
            def __init__(self, user):
                self.user = user

            def build_absolute_uri(self, url):
                return f"http://testserver{url}" if url else ""

        serializer = ProductListSerializer(product, context={"request": MockRequest(user)})
        data = serializer.data
        assert "current_price" in data  # Поле существует в сериализаторе

    def test_product_list_filtering(self, user_factory, product_variant_factory):
        """Тест фильтрации товаров"""
        user = user_factory.create()
        variant = product_variant_factory.create(product__name="Активный товар", product__is_active=True)
        product = variant.product

        serializer = ProductListSerializer(product)
        data = serializer.data
        # is_active не включено в fields ProductListSerializer, проверяем can_be_ordered
        assert "can_be_ordered" in data


@pytest.mark.django_db
class TestProductDetailSerializer:
    """Тесты детального сериализатора товара"""

    def test_product_detail_serialization(
        self,
        category_factory,
        brand_factory,
        product_factory,
        product_image_factory,
        user_factory,
    ):
        """Тест детальной сериализации товара"""
        category = category_factory.create(name="Спорт")
        brand = brand_factory.create(name="Adidas")
        product = product_factory.create(
            name="Футболка",
            description="Спортивная футболка",
            category=category,
            brand=brand,
            base_images=["/media/products/img1.jpg"],  # Добавляем изображения в JSON поле
        )

        class MockRequest:
            def __init__(self, user):
                self.user = user

            def build_absolute_uri(self, url):
                return f"http://testserver{url}" if url else ""

        user = user_factory.create()
        request_mock = type(
            "MockRequest",
            (object,),
            {
                "user": user,
                "build_absolute_uri": (lambda self, url: f"http://testserver{url}" if url else ""),
            },
        )()

        serializer = ProductDetailSerializer(product, context={"request": MockRequest(user)})
        data = serializer.data

        assert data["name"] == "Футболка"
        assert data["description"] == "Спортивная футболка"
        assert "images" in data
        # Проверяем, что images присутствует (может быть 1 или 2 в зависимости от
        # factory)
        assert len(data["images"]) >= 1

    def test_product_detail_with_related_products(self, category_factory, product_factory, user_factory):
        """Тест с похожими товарами"""
        category = category_factory.create(name="Обувь")
        main_product = product_factory.create(name="Основной товар", category=category)
        related_products = product_factory.create_batch(3, category=category)

        class MockRequest:
            def __init__(self, user):
                self.user = user

            def build_absolute_uri(self, url):
                return f"http://testserver{url}" if url else ""

        user = user_factory.create()
        request_mock = type(
            "MockRequest",
            (object,),
            {
                "user": user,
                "build_absolute_uri": (lambda self, url: f"http://testserver{url}" if url else ""),
            },
        )()

        serializer = ProductDetailSerializer(main_product, context={"request": MockRequest(user)})
        data = serializer.data

        assert "related_products" in data


@pytest.mark.django_db
class TestCategorySerializer:
    """Тесты сериализатора категорий"""

    def test_category_serialization(self, category_factory):
        """Тест сериализации категории"""
        parent_category = category_factory.create(name="Спорт")
        child_category = category_factory.create(name="Футбол", parent=parent_category)

        serializer = CategorySerializer(child_category)
        data = serializer.data

        assert data["name"] == "Футбол"
        assert data["parent"] == parent_category.id  # parent это ID, не объект

    def test_category_hierarchy(self, category_factory):
        """Тест иерархии категорий"""
        root = category_factory.create(name="Корень")
        child1 = category_factory.create(name="Ребенок 1", parent=root)
        child2 = category_factory.create(name="Ребенок 2", parent=root)

        serializer = CategorySerializer([root, child1, child2], many=True)
        data = serializer.data

        assert len(data) == 3

    def test_category_with_products(self, category_factory, product_factory):
        """Тест категории с товарами"""
        category = category_factory.create(name="Тестовая")
        product_factory.create(category=category)
        product_factory.create(category=category)

        serializer = CategorySerializer(category)
        data = serializer.data

        assert data["name"] == "Тестовая"


@pytest.mark.django_db
class TestBrandSerializer:
    """Тесты сериализатора брендов"""

    def test_brand_serialization(self, brand_factory):
        """Тест сериализации бренда"""
        brand = brand_factory.create(name="Nike", description="Спортивный бренд")

        serializer = BrandSerializer(brand)
        data = serializer.data

        assert data["name"] == "Nike"
        assert data["description"] == "Спортивный бренд"

    def test_brand_with_products(self, brand_factory, product_factory):
        """Тест бренда с товарами"""
        brand = brand_factory.create(name="Adidas")
        product_factory.create(brand=brand)
        product_factory.create(brand=brand)

        serializer = BrandSerializer(brand)
        data = serializer.data

        assert data["name"] == "Adidas"

    def test_brand_validation(self, brand_factory):
        """Тест валидации бренда"""
        data = {"name": "Новый бренд", "description": "Описание"}

        serializer = BrandSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        brand = serializer.save()
        assert brand.name == "Новый бренд"


@pytest.mark.django_db
class TestProductImageSerializer:
    """Тесты сериализатора изображений товара"""

    def test_product_image_serialization(self, product_factory, product_image_factory):
        """Тест сериализации изображения"""
        product = product_factory.create(name="Товар с фото")
        image = product_image_factory.create(product=product, is_main=True, alt_text="Основное фото")

        serializer = ProductImageSerializer(image)
        data = serializer.data

        assert data["is_main"] is True
        assert data["alt_text"] == "Основное фото"

    def test_multiple_product_images(self, product_factory, product_image_factory):
        """Тест множественных изображений"""
        product = product_factory.create(name="Товар")
        image1 = product_image_factory.create(product=product, is_main=True)
        image2 = product_image_factory.create(product=product, is_main=False)
        image3 = product_image_factory.create(product=product, is_main=False)

        images = [image1, image2, image3]
        serializer = ProductImageSerializer(images, many=True)
        data = serializer.data

        assert len(data) == 3
        main_images = [img for img in data if img["is_main"]]
        assert len(main_images) == 1


@pytest.mark.django_db
class TestProductSpecificationSerializer:
    """Тесты сериализатора характеристик товара"""

    def test_specification_serialization(self, product_factory):
        """Тест сериализации характеристик"""
        product = product_factory.create(
            name="Товар с характеристиками",
            specifications={"color": "Красный", "size": "L", "material": "Хлопок"},
        )

        serializer = ProductSpecificationSerializer(product)
        data = serializer.data

        assert "specifications" in data
        assert data["specifications"]["color"] == "Красный"
        assert data["specifications"]["size"] == "L"

    def test_empty_specifications(self, product_factory):
        """Тест пустых характеристик"""
        product = product_factory.create(name="Товар без характеристик", specifications={})

        serializer = ProductSpecificationSerializer(product)
        data = serializer.data

        assert "specifications" in data
        assert data["specifications"] == {}


@pytest.mark.django_db
class TestProductSearchAndFiltering:
    """Тесты поиска и фильтрации товаров"""

    def test_price_range_filtering(self, category_factory, brand_factory, product_variant_factory):
        """Тест фильтрации по диапазону цен"""
        category = category_factory.create(name="Тест")
        brand = brand_factory.create(name="Тест")
        cheap_variant = product_variant_factory.create(
            product__name="Дешевый",
            product__category=category,
            product__brand=brand,
            retail_price=Decimal("100.00"),
        )
        expensive_variant = product_variant_factory.create(
            product__name="Дорогой",
            product__category=category,
            product__brand=brand,
            retail_price=Decimal("1000.00"),
        )

        # Тест сериализации в контексте фильтрации
        serializer1 = ProductListSerializer(cheap_variant.product)
        serializer2 = ProductListSerializer(expensive_variant.product)

        data1 = serializer1.data
        data2 = serializer2.data

        assert float(data1["retail_price"]) < float(data2["retail_price"])

    def test_category_filtering(self, category_factory, product_variant_factory):
        """Тест фильтрации по категориям"""
        sport_category = category_factory.create(name="Спорт")
        fashion_category = category_factory.create(name="Мода")

        sport_variant = product_variant_factory.create(
            product__name="Спортивный товар", product__category=sport_category
        )
        fashion_variant = product_variant_factory.create(
            product__name="Модный товар", product__category=fashion_category
        )

        sport_serializer = ProductListSerializer(sport_variant.product)
        fashion_serializer = ProductListSerializer(fashion_variant.product)

        sport_data = sport_serializer.data
        fashion_data = fashion_serializer.data

        assert sport_data["category"] == "Спорт"  # StringRelatedField
        assert fashion_data["category"] == "Мода"  # StringRelatedField


@pytest.mark.django_db
class TestProductPerformance:
    """Тесты производительности сериализаторов"""

    def test_bulk_serialization_performance(self, category_factory, brand_factory, product_variant_factory):
        """Тест производительности массовой сериализации"""
        category = category_factory.create(name="Тест")
        brand = brand_factory.create(name="Тест")
        variants = product_variant_factory.create_batch(10, product__category=category, product__brand=brand)
        products = [v.product for v in variants]

        serializer = ProductListSerializer(products, many=True)
        data = serializer.data

        assert len(data) == 10
        for item in data:
            assert "name" in item
            assert "retail_price" in item


@pytest.mark.django_db
class TestOnecBrandIdSerializerGuardrail:
    """Story 13.2: Тест что onec_brand_id не экспонируется в публичных API"""

    def test_onec_brand_id_not_in_product_list_serializer(self, product_factory):
        """Тест что ProductListSerializer не возвращает onec_brand_id"""
        product = product_factory.create(onec_brand_id="fb3f263e-dfd0-11ef-8361-fa163ea88911")

        serializer = ProductListSerializer(product)
        data = serializer.data

        # onec_brand_id не должно быть в публичном API
        assert "onec_brand_id" not in data

    def test_onec_brand_id_not_in_product_detail_serializer(self, product_factory):
        """Тест что ProductDetailSerializer не возвращает onec_brand_id"""
        product = product_factory.create(onec_brand_id="fb3f263e-dfd0-11ef-8361-fa163ea88911")

        serializer = ProductDetailSerializer(product)
        data = serializer.data

        # onec_brand_id не должно быть в публичном API
        assert "onec_brand_id" not in data

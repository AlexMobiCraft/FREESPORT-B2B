"""
Factory классы для создания тестовых данных

КРИТИЧНО: Использует LazyFunction с get_unique_suffix() для полной изоляции тестов
"""

import time
import uuid
from decimal import Decimal

import factory
from django.utils.text import slugify
from factory import fuzzy

from apps.products.models import Brand, Brand1CMapping, Category, ColorMapping, Product, ProductVariant

# Глобальный счетчик для обеспечения уникальности
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс"""
    global _unique_counter
    _unique_counter += 1
    return f"{int(time.time() * 1000)}-{_unique_counter}-{uuid.uuid4().hex[:6]}"


class BrandFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых брендов"""

    class Meta:
        model = Brand

    name = factory.LazyFunction(lambda: f"Brand-{get_unique_suffix()}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
    description = factory.Faker("text", max_nb_chars=200)
    is_active = True


class Brand1CMappingFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых маппингов брендов из 1С"""

    class Meta:
        model = Brand1CMapping

    brand = factory.SubFactory(BrandFactory)
    onec_id = factory.LazyFunction(lambda: f"brand-1c-{get_unique_suffix()}")
    onec_name = factory.LazyAttribute(lambda obj: obj.brand.name)


class CategoryFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых категорий"""

    class Meta:
        model = Category

    name = factory.LazyFunction(lambda: f"Category-{get_unique_suffix()}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
    onec_id = factory.LazyFunction(lambda: f"cat-1c-{get_unique_suffix()}")
    description = factory.Faker("text", max_nb_chars=200)
    is_active = True


class ProductFactory(factory.django.DjangoModelFactory):
    """
    Factory для создания тестовых товаров.
    Автоматически создает вариант (ProductVariant) с ценами и остатками.
    Параметры retail_price, stock_quantity и др. передаются в вариант.
    """

    class Meta:
        model = Product
        skip_postgeneration_save = True

    name = factory.LazyFunction(lambda: f"Product-{get_unique_suffix()}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))
    onec_id = factory.LazyFunction(lambda: f"1c-{get_unique_suffix()}")
    description = factory.Faker("text", max_nb_chars=500)
    short_description = factory.Faker("text", max_nb_chars=200)
    is_active = True

    # Связи
    category = factory.SubFactory(CategoryFactory)
    brand = factory.SubFactory(BrandFactory)

    # Параметры для варианта (Transient)
    # Используем post_generation для создания варианта после сохранения продукта
    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Извлекаем поля варианта перед созданием продукта"""
        variant_fields = [
            "retail_price",
            "opt1_price",
            "opt2_price",
            "opt3_price",
            "trainer_price",
            "federation_price",
            "stock_quantity",
            "reserved_quantity",
            "sku",
            "create_variant",
            "main_image",
            "onec_id",  # Принимаем onec_id для варианта
        ]
        variant_params = {}
        for field in variant_fields:
            if field in kwargs:
                variant_params[field] = kwargs.pop(field)

        product = super()._create(model_class, *args, **kwargs)

        # Создаем вариант если не отключено
        if variant_params.get("create_variant", True):
            variant_params.pop("create_variant", None)
            ProductVariantFactory.create(product=product, **variant_params)

        return product


class ColorMappingFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых маппингов цветов"""

    class Meta:
        model = ColorMapping

    name = factory.LazyFunction(lambda: f"Color-{get_unique_suffix()}")
    hex_code = fuzzy.FuzzyChoice(["#FF0000", "#00FF00", "#0000FF", "#FFFF00", "#FF00FF"])


class ProductVariantFactory(factory.django.DjangoModelFactory):
    """Factory для создания тестовых вариантов товаров"""

    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory, create_variant=False)
    sku = factory.LazyFunction(lambda: f"SKU-{get_unique_suffix().upper()}")
    onec_id = factory.LazyFunction(lambda: f"variant-1c-{get_unique_suffix()}")
    color_name = factory.LazyFunction(lambda: f"Color-{get_unique_suffix()}")
    size_value = fuzzy.FuzzyChoice(["XS", "S", "M", "L", "XL", "XXL", "38", "40", "42", "44"])

    # Цены для различных ролей
    retail_price = fuzzy.FuzzyDecimal(100.0, 10000.0, 2)
    opt1_price = fuzzy.FuzzyDecimal(80.0, 8000.0, 2)
    opt2_price = fuzzy.FuzzyDecimal(60.0, 6000.0, 2)
    opt3_price = fuzzy.FuzzyDecimal(50.0, 5000.0, 2)
    trainer_price = fuzzy.FuzzyDecimal(40.0, 4000.0, 2)
    federation_price = fuzzy.FuzzyDecimal(45.0, 4500.0, 2)

    # Остатки
    stock_quantity = fuzzy.FuzzyInteger(0, 100)
    reserved_quantity = fuzzy.FuzzyInteger(0, 10)

    is_active = True

"""Тесты для моделей атрибутов FREESPORT Platform"""

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase

from apps.products.models import (
    Attribute,
    Attribute1CMapping,
    AttributeValue,
    AttributeValue1CMapping,
    Brand,
    Category,
    Product,
    ProductVariant,
)
from tests.conftest import get_unique_suffix
from tests.factories import BrandFactory, CategoryFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestAttributeModel:
    """Тесты модели Attribute"""

    def test_attribute_creation_with_cyrillic_name(self) -> None:
        """Тест: создание атрибута с кириллическим названием."""
        # ARRANGE
        suffix = get_unique_suffix()
        name = f"Цвет {suffix}"

        # ACT
        attribute = Attribute.objects.create(name=name, type="color")

        # ASSERT
        assert attribute.name == name
        assert attribute.type == "color"
        assert attribute.slug is not None
        assert attribute.normalized_name is not None

    def test_attribute_slug_generation(self) -> None:
        """Тест: автоматическая генерация slug из кириллического имени."""
        # ARRANGE
        suffix = get_unique_suffix()
        name = f"Материал {suffix}"

        # ACT
        attribute = Attribute.objects.create(name=name)

        # ASSERT
        assert attribute.slug.startswith("material")

    def test_attribute_str_representation(self) -> None:
        """Тест: строковое представление модели."""
        # ARRANGE
        suffix = get_unique_suffix()
        name = f"Размер {suffix}"
        attribute = Attribute.objects.create(name=name)

        # ASSERT
        assert str(attribute) == name

    def test_attribute_onec_id_uniqueness(self) -> None:
        """Тест: onec_id в маппинге должен быть уникальным."""
        # ARRANGE
        suffix = get_unique_suffix()
        onec_id = f"attr-duplicate-{suffix}"
        attr1 = Attribute.objects.create(name=f"Атрибут 1 {suffix}")
        Attribute1CMapping.objects.create(attribute=attr1, onec_id=onec_id, onec_name="Attr 1", source="goods")

        attr2 = Attribute.objects.create(name=f"Атрибут 2 {suffix}")

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            Attribute1CMapping.objects.create(attribute=attr2, onec_id=onec_id, onec_name="Attr 2", source="goods")


@pytest.mark.django_db
class TestAttributeValueModel:
    """Тесты модели AttributeValue"""

    def test_attribute_value_creation_with_cyrillic(self) -> None:
        """Тест: создание значения атрибута с кириллицей."""
        # ARRANGE
        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(name=f"Цвет {suffix}")
        value = f"Красный {suffix}"

        # ACT
        attr_value = AttributeValue.objects.create(attribute=attribute, value=value)

        # ASSERT
        assert attr_value.value == value
        assert attr_value.attribute == attribute
        assert attr_value.slug is not None
        assert attr_value.normalized_value is not None

    def test_attribute_value_slug_generation(self) -> None:
        """Тест: автоматическая генерация slug из кириллического значения."""
        # ARRANGE
        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(name=f"Материал {suffix}")
        value = f"Хлопок {suffix}"

        # ACT
        attr_value = AttributeValue.objects.create(attribute=attribute, value=value)

        # ASSERT
        assert attr_value.slug.startswith("hlopok")

    def test_attribute_value_foreign_key_relationship(self) -> None:
        """Тест: FK связь с Attribute."""
        # ARRANGE
        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(name=f"Размер {suffix}")
        value = f"XL {suffix}"

        # ACT
        attr_value = AttributeValue.objects.create(attribute=attribute, value=value)

        # ASSERT
        assert attr_value in attribute.values.all()

    def test_attribute_value_str_representation(self) -> None:
        """Тест: строковое представление модели."""
        # ARRANGE
        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(name=f"Цвет {suffix}")
        value = f"Синий {suffix}"
        attr_value = AttributeValue.objects.create(attribute=attribute, value=value)

        # ASSERT
        assert str(attr_value) == f"{attribute.name}: {value}"

    def test_attribute_value_onec_id_uniqueness(self) -> None:
        """Тест: onec_id в маппинге значения должен быть уникальным."""
        # ARRANGE
        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(name=f"Атрибут {suffix}")
        onec_id = f"val-duplicate-{suffix}"

        val1 = AttributeValue.objects.create(attribute=attribute, value=f"Val 1 {suffix}")
        AttributeValue1CMapping.objects.create(
            attribute_value=val1, onec_id=onec_id, onec_value="Val 1", source="goods"
        )

        val2 = AttributeValue.objects.create(attribute=attribute, value=f"Val 2 {suffix}")

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            AttributeValue1CMapping.objects.create(
                attribute_value=val2,
                onec_id=onec_id,
                onec_value="Val 2",
                source="goods",
            )


@pytest.mark.django_db
class TestProductAttributeRelationship:
    """Тесты связи M2M между Product и AttributeValue."""

    def test_product_can_add_attribute_values(self, brand_factory, category_factory) -> None:
        """Тест: можно добавить атрибуты к Product."""
        # ARRANGE
        suffix = get_unique_suffix()
        brand = brand_factory.create()
        category = category_factory.create()
        product = Product.objects.create(
            name=f"Товар {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            category=category,
            description="Test product",
            onec_id=f"prod-{suffix}",
        )
        attribute = Attribute.objects.create(name=f"Цвет {suffix}")
        attr_value = AttributeValue.objects.create(attribute=attribute, value=f"Красный {suffix}")

        # ACT
        product.attributes.add(attr_value)

        # ASSERT
        assert attr_value in product.attributes.all()
        assert product in attr_value.products.all()

    def test_product_can_have_multiple_attributes(self, brand_factory, category_factory) -> None:
        """Тест: Product может иметь несколько атрибутов."""
        # ARRANGE
        suffix = get_unique_suffix()
        brand = brand_factory.create()
        category = category_factory.create()
        product = Product.objects.create(
            name=f"Товар {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            category=category,
            description="Test product",
            onec_id=f"prod-{suffix}",
        )
        color_attr = Attribute.objects.create(name=f"Цвет {suffix}")
        size_attr = Attribute.objects.create(name=f"Размер {suffix}")

        color_value = AttributeValue.objects.create(attribute=color_attr, value=f"Черный {suffix}")
        size_value = AttributeValue.objects.create(attribute=size_attr, value=f"L {suffix}")

        # ACT
        product.attributes.add(color_value, size_value)

        # ASSERT
        assert product.attributes.count() == 2
        assert color_value in product.attributes.all()
        assert size_value in product.attributes.all()


@pytest.mark.django_db
class TestProductVariantAttributeRelationship:
    """Тесты связи M2M между ProductVariant и AttributeValue."""

    def test_variant_can_add_attribute_values(self, brand_factory, category_factory) -> None:
        """Тест: можно добавить атрибуты к ProductVariant."""
        # ARRANGE
        suffix = get_unique_suffix()
        brand = brand_factory.create()
        category = category_factory.create()
        product = Product.objects.create(
            name=f"Товар {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            category=category,
            description="Test product",
            onec_id=f"prod-{suffix}",
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku=f"SKU-{suffix}",
            onec_id=f"variant-{suffix}",
            retail_price=100.00,
        )
        attribute = Attribute.objects.create(name=f"Цвет {suffix}")
        attr_value = AttributeValue.objects.create(attribute=attribute, value=f"Зеленый {suffix}")

        # ACT
        variant.attributes.add(attr_value)

        # ASSERT
        assert attr_value in variant.attributes.all()
        assert variant in attr_value.variants.all()

    def test_variant_can_have_multiple_attributes(self, brand_factory, category_factory) -> None:
        """Тест: ProductVariant может иметь несколько атрибутов."""
        # ARRANGE
        suffix = get_unique_suffix()
        brand = brand_factory.create()
        category = category_factory.create()
        product = Product.objects.create(
            name=f"Товар {suffix}",
            slug=f"product-{suffix}",
            brand=brand,
            category=category,
            description="Test product",
            onec_id=f"prod-{suffix}",
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku=f"SKU-{suffix}",
            onec_id=f"variant-{suffix}",
            retail_price=100.00,
        )
        color_attr = Attribute.objects.create(name=f"Цвет {suffix}")
        size_attr = Attribute.objects.create(name=f"Размер {suffix}")

        color_value = AttributeValue.objects.create(attribute=color_attr, value=f"Белый {suffix}")
        size_value = AttributeValue.objects.create(attribute=size_attr, value=f"M {suffix}")

        # ACT
        variant.attributes.add(color_value, size_value)

        # ASSERT
        assert variant.attributes.count() == 2
        assert color_value in variant.attributes.all()
        assert size_value in variant.attributes.all()

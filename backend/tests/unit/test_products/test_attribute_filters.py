"""
Unit тесты для фильтрации товаров по атрибутам

Story 14.6: Filtering & Facets API
"""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import RequestFactory
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.filters import ProductFilter
from apps.products.models import Attribute, AttributeValue, Product, ProductVariant
from apps.products.services.facets import AttributeFacetService
from tests.factories import (
    AttributeFactory,
    AttributeValueFactory,
    BrandFactory,
    CategoryFactory,
    ProductFactory,
    ProductVariantFactory,
)
from tests.utils import get_unique_suffix


@pytest.mark.django_db
@pytest.mark.unit
class TestAttributeFilters:
    """Тесты для динамических фильтров атрибутов"""

    @pytest.fixture(autouse=True)
    def clear_attribute_cache(self):
        cache.delete("active_attributes_for_filters")

    def test_filter_by_single_attribute_value(self):
        """AC1: Фильтр по одному значению атрибута ?attr_color=red"""
        suffix = get_unique_suffix()

        # Создаем атрибут Цвет
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )

        # Создаем значения атрибутов
        red_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Красный {suffix}",
            slug=f"red-{suffix}",
        )
        blue_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Синий {suffix}",
            slug=f"blue-{suffix}",
        )

        # Создаем товары
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")

        red_product = ProductFactory(
            name=f"Red Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        red_variant = ProductVariantFactory(product=red_product)
        red_product.attributes.add(red_value)

        blue_product = ProductFactory(
            name=f"Blue Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        blue_variant = ProductVariantFactory(product=blue_product)
        blue_product.attributes.add(blue_value)

        # Создаем фильтр с параметром attr_color=red-{suffix}
        factory = RequestFactory()
        request = factory.get(f"/?attr_color-{suffix}={red_value.slug}")
        request.user = None

        filter_instance = ProductFilter(
            data=request.GET,
            queryset=Product.objects.filter(is_active=True),
            request=request,
        )

        # Проверяем, что отфильтрованы только красные товары
        filtered_qs = filter_instance.qs
        assert red_product in filtered_qs
        assert blue_product not in filtered_qs

    def test_filter_by_multiple_values_or_logic(self):
        """AC3: Множественные значения (OR) ?attr_color=red,blue"""
        suffix = get_unique_suffix()

        # Создаем атрибут Цвет
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )

        # Создаем значения
        red_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Красный {suffix}",
            slug=f"red-{suffix}",
        )
        blue_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Синий {suffix}",
            slug=f"blue-{suffix}",
        )
        green_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Зелёный {suffix}",
            slug=f"green-{suffix}",
        )

        # Создаем товары
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")

        red_product = ProductFactory(
            name=f"Red Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        red_variant = ProductVariantFactory(product=red_product)
        red_product.attributes.add(red_value)

        blue_product = ProductFactory(
            name=f"Blue Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        blue_variant = ProductVariantFactory(product=blue_product)
        blue_product.attributes.add(blue_value)

        green_product = ProductFactory(
            name=f"Green Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        green_variant = ProductVariantFactory(product=green_product)
        green_product.attributes.add(green_value)

        # Фильтр: attr_color=red,blue (OR логика)
        factory = RequestFactory()
        request = factory.get(f"/?attr_color-{suffix}={red_value.slug},{blue_value.slug}")
        request.user = None

        filter_instance = ProductFilter(
            data=request.GET,
            queryset=Product.objects.filter(is_active=True),
            request=request,
        )

        # Проверяем: красный и синий есть, зелёного нет
        filtered_qs = filter_instance.qs
        assert red_product in filtered_qs
        assert blue_product in filtered_qs
        assert green_product not in filtered_qs

    def test_filter_by_multiple_attributes_and_logic(self):
        """AC4: Множественные атрибуты (AND) ?attr_color=red&attr_size=xl"""
        suffix = get_unique_suffix()

        # Создаем атрибуты
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )
        size_attr = AttributeFactory(
            name=f"Размер {suffix}",
            slug=f"size-{suffix}",
            is_active=True,
        )

        # Создаем значения
        red_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Красный {suffix}",
            slug=f"red-{suffix}",
        )
        blue_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Синий {suffix}",
            slug=f"blue-{suffix}",
        )
        xl_value = AttributeValueFactory(
            attribute=size_attr,
            value=f"XL {suffix}",
            slug=f"xl-{suffix}",
        )
        l_value = AttributeValueFactory(
            attribute=size_attr,
            value=f"L {suffix}",
            slug=f"l-{suffix}",
        )

        # Создаем товары
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")

        # Red XL - должен остаться
        red_xl_product = ProductFactory(
            name=f"Red XL Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        red_xl_variant = ProductVariantFactory(product=red_xl_product)
        red_xl_product.attributes.add(red_value, xl_value)

        # Red L - не должен остаться (нет XL)
        red_l_product = ProductFactory(
            name=f"Red L Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        red_l_variant = ProductVariantFactory(product=red_l_product)
        red_l_product.attributes.add(red_value, l_value)

        # Blue XL - не должен остаться (нет Red)
        blue_xl_product = ProductFactory(
            name=f"Blue XL Product {suffix}",
            brand=brand,
            category=category,
            is_active=True,
        )
        blue_xl_variant = ProductVariantFactory(product=blue_xl_product)
        blue_xl_product.attributes.add(blue_value, xl_value)

        # Фильтр: attr_color=red AND attr_size=xl
        factory = RequestFactory()
        request = factory.get(f"/?attr_color-{suffix}={red_value.slug}&attr_size-{suffix}={xl_value.slug}")
        request.user = None

        filter_instance = ProductFilter(
            data=request.GET,
            queryset=Product.objects.filter(is_active=True),
            request=request,
        )

        # Проверяем: только Red XL
        filtered_qs = filter_instance.qs
        assert red_xl_product in filtered_qs
        assert red_l_product not in filtered_qs
        assert blue_xl_product not in filtered_qs

    def test_filter_ignores_inactive_attributes(self):
        """Фильтр игнорирует неактивные атрибуты"""
        suffix = get_unique_suffix()

        # Создаем неактивный атрибут
        inactive_attr = AttributeFactory(
            name=f"Inactive Attr {suffix}",
            slug=f"inactive-{suffix}",
            is_active=False,
        )

        factory = RequestFactory()
        request = factory.get(f"/?attr_inactive-{suffix}=value")
        request.user = None

        filter_instance = ProductFilter(
            data=request.GET,
            queryset=Product.objects.filter(is_active=True),
            request=request,
        )

        # Проверяем, что фильтр для неактивного атрибута не создан
        assert f"attr_inactive-{suffix}" not in filter_instance.filters


@pytest.mark.django_db
@pytest.mark.unit
class TestAttributeFacets:
    """Тесты для генерации facets (фасетов)"""

    def test_facets_structure_and_counts(self):
        """AC2: Facets содержат правильную структуру и counts"""
        suffix = get_unique_suffix()

        # Создаем атрибуты
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )

        # Создаем значения
        red_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Красный {suffix}",
            slug=f"red-{suffix}",
        )
        blue_value = AttributeValueFactory(
            attribute=color_attr,
            value=f"Синий {suffix}",
            slug=f"blue-{suffix}",
        )

        # Создаем товары
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")

        # 3 красных товара
        for i in range(3):
            product = ProductFactory(
                name=f"Red Product {i} {suffix}",
                brand=brand,
                category=category,
                is_active=True,
            )
            variant = ProductVariantFactory(product=product)
            product.attributes.add(red_value)

        # 2 синих товара
        for i in range(2):
            product = ProductFactory(
                name=f"Blue Product {i} {suffix}",
                brand=brand,
                category=category,
                is_active=True,
            )
            variant = ProductVariantFactory(product=product)
            product.attributes.add(blue_value)

        # Получаем facets
        queryset = Product.objects.filter(is_active=True)
        facets = AttributeFacetService.get_facets(queryset)

        # Проверяем структуру facets
        assert f"color-{suffix}" in facets
        color_facets = facets[f"color-{suffix}"]

        # Проверяем counts
        assert len(color_facets) == 2

        # Находим красный и синий
        red_facet = next(f for f in color_facets if f["slug"] == f"red-{suffix}")
        blue_facet = next(f for f in color_facets if f["slug"] == f"blue-{suffix}")

        assert red_facet["value"] == f"Красный {suffix}"
        assert red_facet["count"] == 3

        assert blue_facet["value"] == f"Синий {suffix}"
        assert blue_facet["count"] == 2

    def test_facets_respect_filtered_queryset(self):
        """Facets учитывают только товары из отфильтрованного queryset"""
        suffix = get_unique_suffix()

        # Создаем атрибуты
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )
        size_attr = AttributeFactory(
            name=f"Размер {suffix}",
            slug=f"size-{suffix}",
            is_active=True,
        )

        # Создаем значения
        red_value = AttributeValueFactory(attribute=color_attr, value=f"Красный {suffix}", slug=f"red-{suffix}")
        xl_value = AttributeValueFactory(attribute=size_attr, value=f"XL {suffix}", slug=f"xl-{suffix}")
        l_value = AttributeValueFactory(attribute=size_attr, value=f"L {suffix}", slug=f"l-{suffix}")

        # Создаем товары
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")

        # Red XL - входит в queryset
        red_xl = ProductFactory(name=f"Red XL {suffix}", brand=brand, category=category, is_active=True)
        red_xl_variant = ProductVariantFactory(product=red_xl)
        red_xl.attributes.add(red_value, xl_value)

        # Red L - входит в queryset
        red_l = ProductFactory(name=f"Red L {suffix}", brand=brand, category=category, is_active=True)
        red_l_variant = ProductVariantFactory(product=red_l)
        red_l.attributes.add(red_value, l_value)

        # Фильтруем только по цвету Red
        queryset = Product.objects.filter(is_active=True, attributes__slug=f"red-{suffix}").distinct()

        facets = AttributeFacetService.get_facets(queryset)

        # Проверяем, что facets для размера учитывают только красные товары
        size_facets = facets.get(f"size-{suffix}", [])

        # Должны быть оба размера (XL и L) с count=1 каждый
        assert len(size_facets) == 2

    def test_facets_exclude_inactive_attributes(self):
        """Facets исключают неактивные атрибуты"""
        suffix = get_unique_suffix()

        # Создаем неактивный атрибут
        inactive_attr = AttributeFactory(
            name=f"Inactive {suffix}",
            slug=f"inactive-{suffix}",
            is_active=False,
        )
        inactive_value = AttributeValueFactory(
            attribute=inactive_attr,
            value=f"Value {suffix}",
            slug=f"value-{suffix}",
        )

        # Создаем товар с неактивным атрибутом
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")
        product = ProductFactory(name=f"Product {suffix}", brand=brand, category=category, is_active=True)
        variant = ProductVariantFactory(product=product)
        product.attributes.add(inactive_value)

        # Получаем facets
        queryset = Product.objects.filter(is_active=True)
        facets = AttributeFacetService.get_facets(queryset)

        # Проверяем, что неактивный атрибут не появился в facets
        assert f"inactive-{suffix}" not in facets

    def test_facets_empty_for_empty_queryset(self):
        """Facets пустые для пустого queryset"""
        # Пустой queryset
        queryset = Product.objects.none()
        facets = AttributeFacetService.get_facets(queryset)

        # Должен вернуть пустой словарь
        assert facets == {}


@pytest.mark.django_db
@pytest.mark.unit
class TestAttributeFiltersAPI:
    """Интеграционные тесты API с фильтрами атрибутов"""

    @pytest.fixture(autouse=True)
    def clear_attribute_cache(self):
        cache.delete("active_attributes_for_filters")

    def test_api_filter_by_attribute(self):
        """API: Фильтрация через GET параметр ?attr_<slug>=<value>"""
        suffix = get_unique_suffix()

        # Создаем атрибут и значения
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )
        red_value = AttributeValueFactory(attribute=color_attr, value=f"Красный {suffix}", slug=f"red-{suffix}")

        # Создаем товар
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")
        product = ProductFactory(name=f"Red Product {suffix}", brand=brand, category=category, is_active=True)
        variant = ProductVariantFactory(product=product)
        product.attributes.add(red_value)

        # API запрос
        client = APIClient()
        response = client.get(
            reverse("products:product-list"),
            {f"attr_color-{suffix}": red_value.slug},
        )

        assert response.status_code == 200
        assert response.data["count"] >= 1

    def test_api_facets_in_response(self):
        """API: Response содержит facets секцию"""
        suffix = get_unique_suffix()

        # Создаем атрибут и значения
        color_attr = AttributeFactory(
            name=f"Цвет {suffix}",
            slug=f"color-{suffix}",
            is_active=True,
        )
        red_value = AttributeValueFactory(attribute=color_attr, value=f"Красный {suffix}", slug=f"red-{suffix}")

        # Создаем товар
        brand = BrandFactory(name=f"Brand {suffix}")
        category = CategoryFactory(name=f"Category {suffix}")
        product = ProductFactory(name=f"Red Product {suffix}", brand=brand, category=category, is_active=True)
        variant = ProductVariantFactory(product=product)
        product.attributes.add(red_value)

        # API запрос
        client = APIClient()
        response = client.get(reverse("products:product-list"))

        assert response.status_code == 200
        assert "facets" in response.data
        assert isinstance(response.data["facets"], dict)

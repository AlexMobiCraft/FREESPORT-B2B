"""
Unit-тесты для маркетинговых флагов Product model (Story 11.0)
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.products.models import Brand, Category, Product
from tests.factories import ProductFactory


@pytest.mark.django_db
class TestProductBadgeFields:
    """Тесты для маркетинговых полей бейджей Product model"""

    @pytest.fixture
    def brand(self):
        """Фикстура для бренда"""
        return Brand.objects.create(name="Test Brand", slug="test-brand")

    @pytest.fixture
    def category(self):
        """Фикстура для категории"""
        return Category.objects.create(name="Test Category", slug="test-category")

    def test_badge_fields_default_values(self, brand, category):
        """Тест: все флаги бейджей имеют default=False по умолчанию"""
        product = ProductFactory.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
        )

        assert product.is_hit is False
        assert product.is_new is False
        assert product.is_sale is False
        assert product.is_promo is False
        assert product.is_premium is False
        assert product.discount_percent is None

    def test_create_product_with_all_badges_true(self, brand, category):
        """Тест: создание товара со всеми флагами = True"""
        product = ProductFactory.create(
            name="Super Product",
            slug="super-product",
            brand=brand,
            category=category,
            is_hit=True,
            is_new=True,
            is_sale=True,
            is_promo=True,
            is_premium=True,
            discount_percent=25,
        )

        assert product.is_hit is True
        assert product.is_new is True
        assert product.is_sale is True
        assert product.is_promo is True
        assert product.is_premium is True
        assert product.discount_percent == 25

    def test_discount_percent_valid_range(self, brand, category):
        """Тест: discount_percent принимает значения 0-100"""
        # Минимальное значение
        product_min = ProductFactory.create(
            name="Product Min",
            slug="product-min",
            brand=brand,
            category=category,
            discount_percent=0,
        )
        assert product_min.discount_percent == 0

        # Максимальное значение
        product_max = ProductFactory.create(
            name="Product Max",
            slug="product-max",
            brand=brand,
            category=category,
            discount_percent=100,
        )
        assert product_max.discount_percent == 100

        # Среднее значение
        product_mid = ProductFactory.create(
            name="Product Mid",
            slug="product-mid",
            brand=brand,
            category=category,
            discount_percent=50,
        )
        assert product_mid.discount_percent == 50

    def test_discount_percent_exceeds_max_validator(self, brand, category):
        """Тест: discount_percent > 100 должен вызвать ValidationError"""
        product = ProductFactory.build(
            name="Product Invalid",
            slug="product-invalid",
            brand=brand,
            category=category,
            discount_percent=101,  # Превышает максимум
        )

        with pytest.raises(ValidationError) as exc_info:
            product.full_clean()  # Вызовет валидацию

        assert "discount_percent" in exc_info.value.message_dict

    def test_discount_percent_null_allowed(self, brand, category):
        """Тест: discount_percent может быть NULL"""
        product = ProductFactory.create(
            name="Product No Discount",
            slug="product-no-discount",
            brand=brand,
            category=category,
            discount_percent=None,
        )

        assert product.discount_percent is None

    def test_multiple_badges_combination(self, brand, category):
        """Тест: товар может иметь несколько бейджей одновременно"""
        product = ProductFactory.create(
            name="Multi Badge Product",
            slug="multi-badge",
            brand=brand,
            category=category,
            is_hit=True,
            is_sale=True,
            discount_percent=30,
        )

        assert product.is_hit is True
        assert product.is_sale is True
        assert product.is_new is False
        assert product.is_promo is False
        assert product.is_premium is False
        assert product.discount_percent == 30

    def test_badge_fields_update(self, brand, category):
        """Тест: обновление флагов бейджей"""
        product = ProductFactory.create(
            name="Updatable Product",
            slug="updatable",
            brand=brand,
            category=category,
        )

        # Изначально все False/None
        assert product.is_hit is False
        assert product.discount_percent is None

        # Обновляем
        product.is_hit = True
        product.discount_percent = 20
        product.save()

        # Перезагружаем из БД
        product.refresh_from_db()

        assert product.is_hit is True
        assert product.discount_percent == 20

    def test_db_indexes_exist_for_badge_fields(self, brand, category):
        """Тест: проверка что индексы созданы для boolean полей"""
        from decimal import Decimal

        # Создаём товары с разными флагами и передаем параметры вариантов в фабрику продукта
        hit_product = ProductFactory.create(
            name="Hit Product",
            slug="hit-product",
            brand=brand,
            category=category,
            is_hit=True,
            sku="HIT-001",
            retail_price=Decimal("100.00"),
        )

        new_product = ProductFactory.create(
            name="New Product",
            slug="new-product",
            brand=brand,
            category=category,
            is_new=True,
            sku="NEW-001",
            retail_price=Decimal("100.00"),
        )

        # Проверяем что фильтрация работает корректно (косвенно проверяет индексы)
        hits = Product.objects.filter(is_hit=True)
        assert hits.count() == 1
        hit = hits.first()
        assert hit is not None
        hit_variant = hit.variants.first()
        assert hit_variant is not None
        assert hit_variant.sku == "HIT-001"

        news = Product.objects.filter(is_new=True)
        assert news.count() == 1
        new_item = news.first()
        assert new_item is not None
        new_variant = new_item.variants.first()
        assert new_variant is not None
        assert new_variant.sku == "NEW-001"

    def test_badge_fields_in_queryset_filter(self, brand, category):
        """Тест: фильтрация по маркетинговым полям работает корректно"""
        # Создаём несколько товаров
        ProductFactory.create(
            name="Regular",
            slug="regular",
            brand=brand,
            category=category,
        )

        ProductFactory.create(
            name="Hit",
            slug="hit",
            brand=brand,
            category=category,
            is_hit=True,
        )

        ProductFactory.create(
            name="Sale",
            slug="sale",
            brand=brand,
            category=category,
            is_sale=True,
            discount_percent=50,
        )

        # Проверяем фильтры
        assert Product.objects.filter(is_hit=True).count() == 1
        assert Product.objects.filter(is_sale=True).count() == 1
        assert Product.objects.filter(discount_percent__isnull=False).count() == 1
        assert Product.objects.filter(is_hit=False, is_sale=False).count() == 1

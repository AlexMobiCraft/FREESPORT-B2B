"""
Unit тесты для ProductVariantSerializer (Story 13.3)
Покрытие >= 90% для ProductVariantSerializer
"""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import Mock

import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from apps.products.factories import ColorMappingFactory, ProductFactory, ProductVariantFactory
from apps.products.models import ColorMapping, ProductVariant
from apps.products.serializers import ProductVariantSerializer
from apps.users.models import User


@pytest.mark.django_db
class TestProductVariantSerializer:
    """Тесты ProductVariantSerializer"""

    @pytest.fixture
    def api_factory(self):
        """Fixture для создания API request factory"""
        return APIRequestFactory()

    @pytest.fixture
    def retail_user(self, db):
        """Fixture для создания retail пользователя"""
        return User.objects.create_user(
            email="retail@test.com",
            password="testpass123",
            role="retail",
        )

    @pytest.fixture
    def wholesale_user(self, db):
        """Fixture для создания wholesale пользователя"""
        return User.objects.create_user(
            email="wholesale@test.com",
            password="testpass123",
            role="wholesale_level1",
        )

    @pytest.fixture
    def variant(self, db):
        """Fixture для создания ProductVariant"""
        product = ProductFactory()
        return ProductVariantFactory(
            product=product,
            color_name="Красный",
            size_value="L",
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            opt2_price=Decimal("800.00"),
            stock_quantity=10,
            reserved_quantity=2,
        )

    def test_serializer_contains_expected_fields(self, variant, api_factory):
        """Тест: serializer содержит все ожидаемые поля"""
        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})

        data = serializer.data

        assert "id" in data
        assert "sku" in data
        assert "color_name" in data
        assert "size_value" in data
        assert "current_price" in data
        assert "color_hex" in data
        assert "stock_quantity" in data
        assert "is_in_stock" in data
        assert "available_quantity" in data
        assert "main_image" in data
        assert "gallery_images" in data

    def test_get_current_price_for_retail_user(self, variant, retail_user, api_factory):
        """Тест: current_price возвращает retail_price для retail пользователя"""
        request = api_factory.get("/")
        request.user = retail_user

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["current_price"] == str(variant.retail_price)

    def test_get_current_price_for_wholesale_user(self, variant, wholesale_user, api_factory):
        """Тест: current_price для wholesale_level1 пользователя = opt1_price"""
        request = api_factory.get("/")
        request.user = wholesale_user

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["current_price"] == str(variant.opt1_price)

    def test_get_current_price_for_anonymous_user(self, variant, api_factory):
        """Тест: current_price возвращает retail_price для анонимного пользователя"""
        from django.contrib.auth.models import AnonymousUser

        request = api_factory.get("/")
        request.user = AnonymousUser()

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["current_price"] == str(variant.retail_price)

    def test_get_current_price_without_request_context(self, variant):
        """
        Тест: current_price работает без request в context (fallback на retail_price)
        """
        serializer = ProductVariantSerializer(variant, context={})
        data = serializer.data

        assert data["current_price"] == str(variant.retail_price)

    def test_get_color_hex_with_existing_mapping(self, variant, api_factory):
        """Тест: color_hex возвращает hex-код из ColorMapping"""
        # Создаем ColorMapping для цвета варианта
        from apps.products.models import ColorMapping

        ColorMapping.objects.update_or_create(name=variant.color_name, defaults={"hex_code": "#FF0000"})

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["color_hex"] == "#FF0000"

    def test_get_color_hex_without_mapping(self, variant, api_factory):
        """Тест: color_hex возвращает None если ColorMapping не найден"""
        # Убедимся что ColorMapping не существует
        ColorMapping.objects.filter(name=variant.color_name).delete()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["color_hex"] is None

    def test_get_color_hex_with_empty_color_name(self, variant, api_factory):
        """Тест: color_hex возвращает None если color_name пустой"""
        variant.color_name = ""
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["color_hex"] is None

    def test_is_in_stock_property(self, variant, api_factory):
        """Тест: is_in_stock корректно отображает наличие товара"""
        variant.stock_quantity = 5
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["is_in_stock"] is True

    def test_is_in_stock_false_when_no_stock(self, variant, api_factory):
        """Тест: is_in_stock = False когда stock_quantity = 0"""
        variant.stock_quantity = 0
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["is_in_stock"] is False

    def test_available_quantity_calculation(self, variant, api_factory):
        """Тест: available_quantity вычисляется с учетом резерва"""
        variant.stock_quantity = 10
        variant.reserved_quantity = 3
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["available_quantity"] == 7  # 10 - 3

    def test_available_quantity_never_negative(self, variant, api_factory):
        """Тест: available_quantity не может быть отрицательным"""
        variant.stock_quantity = 5
        variant.reserved_quantity = 10  # Больше чем stock_quantity
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["available_quantity"] == 0  # max(0, 5 - 10) = 0

    def test_all_fields_are_read_only(self, variant, api_factory):
        """Тест: все поля помечены как read_only"""
        serializer = ProductVariantSerializer(variant)

        for field_name in serializer.Meta.fields:
            assert field_name in serializer.Meta.read_only_fields

    def test_serializer_with_multiple_variants(self, db, api_factory):
        """Тест: serializer корректно обрабатывает несколько вариантов"""
        product = ProductFactory()
        variants = ProductVariantFactory.create_batch(3, product=product)

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variants, many=True, context={"request": request})
        data = serializer.data

        assert len(data) == 3
        assert all("sku" in item for item in data)
        assert all("current_price" in item for item in data)

    def test_serializer_with_trainer_user(self, variant, api_factory, db):
        """Тест: current_price возвращает trainer_price для trainer пользователя"""
        trainer_user = User.objects.create_user(
            email="trainer@test.com",
            password="testpass123",
            role="trainer",
        )
        variant.trainer_price = Decimal("700.00")
        variant.save()

        request = api_factory.get("/")
        request.user = trainer_user

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["current_price"] == "700.00"

    def test_serializer_with_federation_user(self, variant, api_factory, db):
        """
        Тест: current_price возвращает federation_price для federation_rep пользователя
        """
        federation_user = User.objects.create_user(
            email="federation@test.com",
            password="testpass123",
            role="federation_rep",
        )
        variant.federation_price = Decimal("750.00")
        variant.save()

        request = api_factory.get("/")
        request.user = federation_user

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert data["current_price"] == "750.00"

    def test_current_price_decimal_to_string_conversion(self, variant, api_factory):
        """Тест: current_price корректно конвертирует Decimal в строку"""
        variant.retail_price = Decimal("1234.56")
        variant.save()

        request = api_factory.get("/")
        request.user = Mock(is_authenticated=False)

        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert isinstance(data["current_price"], str)
        assert data["current_price"] == "1234.56"

    def test_gallery_images_field(self, variant, api_factory):
        """Тест: gallery_images сериализуется как список"""
        variant.gallery_images = [
            "/media/variants/img1.jpg",
            "/media/variants/img2.jpg",
        ]
        variant.save()

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})
        data = serializer.data

        assert isinstance(data["gallery_images"], list)
        assert len(data["gallery_images"]) == 2

    def test_stock_range_field(self, variant, api_factory):
        """Тест: stock_range возвращает правильный диапазон"""
        cases = [
            (0, None),
            (3, "1 - 5"),
            (5, "1 - 5"),
            (6, "6 - 19"),
            (10, "6 - 19"),
            (19, "6 - 19"),
            (20, "20 - 49"),
            (30, "20 - 49"),
            (49, "20 - 49"),
            (50, "50 и более"),
            (100, "50 и более"),
        ]

        request = api_factory.get("/")
        serializer = ProductVariantSerializer(variant, context={"request": request})

        for qty, expected_range in cases:
            variant.stock_quantity = qty
            variant.reserved_quantity = 0  # Reset reserved to keep it clean
            variant.save()

            # Refresh from DB to ensure computed property available_quantity is updated?
            # Actually serializer uses model property.
            variant.refresh_from_db()

            data = serializer.to_representation(variant)
            assert data.get("stock_range") == expected_range, f"Failed for quantity {qty}"

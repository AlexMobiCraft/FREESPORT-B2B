"""
Serializers для корзины покупок
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict

from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.products.utils.images import product_main_image_url

from .models import Cart, CartItem

if TYPE_CHECKING:
    from apps.products.models import ProductVariant

User = get_user_model()


class CartItemSerializer(serializers.ModelSerializer):
    """
    Serializer для элемента корзины с ценовой информацией.
    Работает с ProductVariant вместо Product.
    """

    # Информация о товаре и варианте
    product = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()

    # Цены
    unit_price = serializers.SerializerMethodField()
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = [
            "id",
            "variant_id",
            "product",
            "variant",
            "quantity",
            "unit_price",
            "total_price",
            "added_at",
        ]
        read_only_fields = ["id", "added_at", "unit_price", "total_price"]

    def get_product(self, obj: CartItem) -> Dict[str, Any]:
        """Получить информацию о товаре"""
        product = obj.variant.product

        # Главное изображение — как в каталоге (ProductListSerializer.get_main_image).
        # ВАЖНО: Возвращаем относительный URL для проксирования через Next.js
        image_url = product_main_image_url(product, obj.variant)

        return {
            "id": product.id,
            "name": product.name,
            "slug": product.slug,
            "image": image_url,
        }

    def get_variant(self, obj: CartItem) -> Dict[str, Any]:
        """Получить информацию о варианте"""
        return {
            "sku": obj.variant.sku,
            "color_name": obj.variant.color_name,
            "size_value": obj.variant.size_value,
        }

    def get_unit_price(self, obj: CartItem) -> str:
        """Получить цену из снимка"""
        return str(obj.price_snapshot)


class CartItemCreateSerializer(serializers.ModelSerializer):
    """
    Serializer для создания элемента корзины.
    Принимает variant_id вместо product_id.
    """

    variant_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = CartItem
        fields = ["variant_id", "quantity"]

    def validate_variant_id(self, value: int) -> int:
        """Валидация варианта товара"""
        from apps.products.models import ProductVariant

        try:
            variant = ProductVariant.objects.select_related("product").get(pk=value)
        except ProductVariant.DoesNotExist:
            raise serializers.ValidationError("Вариант товара не найден")

        # Проверяем активность товара и варианта
        if not variant.product.is_active:
            raise serializers.ValidationError("Товар неактивен")

        if not variant.is_active:
            raise serializers.ValidationError("Вариант товара неактивен")

        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Дополнительная валидация количества"""
        from apps.products.models import ProductVariant

        variant_id = attrs["variant_id"]
        quantity = attrs["quantity"]

        # Получаем вариант для валидации
        variant = ProductVariant.objects.select_related("product").get(pk=variant_id)

        # Проверяем наличие на складе
        if quantity > variant.stock_quantity:
            msg = f"Недостаточно товара на складе. Доступно: {variant.stock_quantity}"
            raise serializers.ValidationError({"quantity": msg})

        return attrs


class CartItemUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer для обновления количества в элементе корзины
    """

    if TYPE_CHECKING:
        instance: CartItem | None

    class Meta:
        model = CartItem
        fields = ["quantity"]

    def validate_quantity(self, value: int) -> int:
        """Валидация количества"""
        if value < 1:
            raise serializers.ValidationError("Количество должно быть больше 0")
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация остатков на складе"""
        # Проверяем, что instance установлен
        if not self.instance:
            raise serializers.ValidationError("Элемент корзины не найден")

        quantity = attrs["quantity"]
        variant = self.instance.variant

        # Проверяем наличие на складе
        if quantity > variant.stock_quantity:
            raise serializers.ValidationError(f"Недостаточно товара на складе. Доступно: {variant.stock_quantity}")

        return attrs


class CartSerializer(serializers.ModelSerializer):
    """
    Serializer для корзины с полной информацией
    """

    items = CartItemSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    total_amount = serializers.SerializerMethodField()

    class Meta:
        model = Cart
        fields = [
            "id",
            "items",
            "total_items",
            "total_amount",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_total_amount(self, obj):
        """Получить общую стоимость корзины в виде строки"""
        return f"{obj.total_amount:.2f}"

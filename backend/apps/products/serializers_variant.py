"""
Serializer для ProductVariant с роле-ориентированным ценообразованием
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from rest_framework import serializers

from .models import ColorMapping, ProductVariant

if TYPE_CHECKING:
    from apps.users.models import User


class ProductVariantSerializer(serializers.ModelSerializer):
    """
    Serializer для ProductVariant с роле-ориентированной ценой

    Поля:
    - current_price: цена для текущего пользователя (роле-ориентированная)
    - color_hex: hex-код цвета из ColorMapping
    - is_in_stock: computed property из модели
    - available_quantity: computed property из модели
    """

    current_price = serializers.SerializerMethodField()
    color_hex = serializers.SerializerMethodField()
    is_in_stock = serializers.BooleanField(read_only=True)
    available_quantity = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "sku",
            "color_name",
            "size_value",
            "current_price",
            "color_hex",
            "stock_quantity",
            "is_in_stock",
            "available_quantity",
            "main_image",
            "gallery_images",
        ]
        read_only_fields = fields  # Все поля read-only

    def get_current_price(self, obj: ProductVariant) -> str:
        """
        Получить роле-ориентированную цену для текущего пользователя

        Args:
            obj: ProductVariant instance

        Returns:
            str: Цена как строка (сериализация Decimal)
        """
        request = self.context.get("request")
        user: User | None = request.user if request else None

        price: Decimal = obj.get_price_for_user(user)
        return str(price)  # Сериализация Decimal → str

    def get_color_hex(self, obj: ProductVariant) -> str | None:
        """
        Получить hex-код цвета из ColorMapping

        Args:
            obj: ProductVariant instance

        Returns:
            str | None: Hex-код цвета или None если маппинг не найден
        """
        if not obj.color_name:
            return None

        try:
            mapping = ColorMapping.objects.get(name=obj.color_name)
            return mapping.hex_code
        except ColorMapping.DoesNotExist:
            return None  # Fallback на None (frontend покажет текст)

"""
Сериализаторы для API способов доставки.
"""

from __future__ import annotations

from rest_framework import serializers

from .models import DeliveryMethod


class DeliveryMethodSerializer(serializers.ModelSerializer):
    """Сериализатор для способа доставки."""

    class Meta:
        model = DeliveryMethod
        fields = ["id", "name", "description", "icon", "is_available"]
        read_only_fields = fields

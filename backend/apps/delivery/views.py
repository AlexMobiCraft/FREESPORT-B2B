"""
ViewSets для API способов доставки.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import permissions, viewsets

from .models import DeliveryMethod
from .serializers import DeliveryMethodSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet


@extend_schema_view(
    list=extend_schema(
        summary="Список способов доставки",
        description="Возвращает список доступных способов доставки",
        tags=["Delivery"],
    ),
    retrieve=extend_schema(
        summary="Получить способ доставки",
        description="Возвращает детали конкретного способа доставки по ID",
        tags=["Delivery"],
    ),
)
class DeliveryMethodViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для получения списка способов доставки.
    Только чтение - управление через Django Admin.
    """

    queryset = DeliveryMethod.objects.filter(is_available=True)
    serializer_class = DeliveryMethodSerializer
    permission_classes = [permissions.AllowAny]  # Доступно без авторизации

    def get_queryset(self) -> QuerySet[DeliveryMethod]:
        """Возвращает только доступные способы доставки."""
        return DeliveryMethod.objects.filter(is_available=True)

    pagination_class = None  # Возвращаем простой список, без пагинации

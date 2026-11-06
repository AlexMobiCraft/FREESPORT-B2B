"""
Views для личного кабинета пользователя
"""

from dataclasses import dataclass
from typing import Any

from django.db.models import Avg, Count, Sum
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order

from ..models import Address, Favorite, User
from ..serializers import (
    AddressSerializer,
    FavoriteCreateSerializer,
    FavoriteSerializer,
    OrderHistorySerializer,
    UserDashboardSerializer,
)


@dataclass
class DashboardData:
    """
    Структура данных для дашборда пользователя
    """

    user_info: User
    orders_count: int
    favorites_count: int
    addresses_count: int
    total_order_amount: float | None = None
    avg_order_amount: float | None = None
    verification_status: str | None = None


class UserDashboardView(APIView):
    """
    Персональный дашборд пользователя
    """

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="Получение дашборда пользователя",
        description="Возвращает основные метрики и статистику пользователя",
        responses={
            200: UserDashboardSerializer,
            401: "Пользователь не авторизован",
        },
    )
    def get(self, request):
        """Получение данных дашборда"""
        user = request.user

        # Базовые счетчики
        favorites_count = user.favorites.count()
        addresses_count = user.addresses.count()

        # Статистика заказов пользователя
        order_stats = self._get_order_statistics(user)
        orders_count = order_stats["count"]
        total_order_amount = order_stats["total_amount"]
        avg_order_amount = order_stats["avg_amount"]

        # Дополнительная статистика для B2B пользователей
        verification_status = None
        if user.is_b2b_user:
            verification_status = "verified" if user.is_verified else "pending"

        dashboard_data = DashboardData(
            user_info=user,
            orders_count=orders_count,
            favorites_count=favorites_count,
            addresses_count=addresses_count,
            total_order_amount=total_order_amount,
            avg_order_amount=avg_order_amount,
            verification_status=verification_status,
        )

        serializer = UserDashboardSerializer(dashboard_data)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _get_order_statistics(self, user: User) -> dict:
        """
        Получение статистики заказов пользователя

        Args:
            user: Пользователь для которого получаем статистику

        Returns:
            dict: Словарь со статистикой заказов
        """
        # Получаем QuerySet заказов пользователя
        user_orders = Order.objects.filter(user=user)

        # Получаем агрегированную статистику заказов
        stats = user_orders.aggregate(
            orders_count=Count("id"),
            total_sum=Sum("total_amount"),
            average_amount=Avg("total_amount"),
        )

        return {
            "count": stats["orders_count"] or 0,
            "total_amount": (float(stats["total_sum"]) if stats["total_sum"] else None),
            "avg_amount": (float(stats["average_amount"]) if stats["average_amount"] else None),
        }


class AddressViewSet(viewsets.ModelViewSet):
    """ViewSet для управления адресами пользователя"""

    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Address.objects.filter(user=user).order_by("-created_at", "-id")
        return Address.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(tags=["Users"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def update(self, request, *args, **kwargs):
        return super().update(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def partial_update(self, request, *args, **kwargs):
        return super().partial_update(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class FavoriteViewSet(viewsets.ModelViewSet):
    """ViewSet для управления избранными товарами"""

    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return FavoriteCreateSerializer
        return FavoriteSerializer

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated:
            return Favorite.objects.filter(user=user)
        return Favorite.objects.none()

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)

    @extend_schema(tags=["Users"])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)

    @extend_schema(tags=["Users"])
    def destroy(self, request, *args, **kwargs):
        return super().destroy(request, *args, **kwargs)


class OrderHistoryView(APIView):
    """История заказов пользователя"""

    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        summary="История заказов",
        description="Получение истории заказов пользователя с пагинацией",
        responses={200: OrderHistorySerializer(many=True)},
        tags=["Users"],
    )
    def get(self, request):
        """
        Получение истории заказов пользователя

        Args:
            request: HTTP запрос

        Returns:
            Response: Список заказов пользователя с пагинацией
        """
        # Получаем заказы пользователя, отсортированные по дате создания
        orders = Order.objects.filter(user=request.user).order_by("-created_at")

        # Применяем фильтрацию по статусу, если указан
        status_filter = request.query_params.get("status")
        if status_filter:
            orders = orders.filter(status=status_filter)

        # Сериализуем данные
        serializer = OrderHistorySerializer(orders, many=True)

        # Возвращаем ответ в формате совместимом с пагинацией
        return Response(
            {"count": orders.count(), "results": serializer.data},
            status=status.HTTP_200_OK,
        )


class CompanyView(APIView):
    """
    View для получения и редактирования реквизитов компании B2B пользователя.

    GET: Получение реквизитов компании
    PUT: Обновление реквизитов компании

    Доступ: только для B2B пользователей (is_b2b_user=True)
    """

    permission_classes = [permissions.IsAuthenticated]

    def _check_b2b_access(self, user: User) -> Response | None:
        """Проверка доступа для B2B пользователей"""
        if not user.is_b2b_user:
            return Response(
                {"detail": "Доступ только для B2B пользователей"},
                status=status.HTTP_403_FORBIDDEN,
            )
        return None

    def _get_or_create_company(self, user: User) -> Any:
        """Получить или создать Company для пользователя"""
        from ..models import Company

        company, created = Company.objects.get_or_create(
            user=user,
            defaults={
                "legal_name": user.company_name or "",
                "tax_id": user.tax_id or "",
            },
        )
        return company

    @extend_schema(
        summary="Получение реквизитов компании",
        description="Возвращает реквизиты компании для B2B пользователя",
        responses={
            200: "CompanySerializer",
            403: "Доступ только для B2B пользователей",
            401: "Пользователь не авторизован",
        },
        tags=["Users"],
    )
    def get(self, request):
        """Получение реквизитов компании"""
        user = request.user

        # Проверка B2B доступа
        error_response = self._check_b2b_access(user)
        if error_response:
            return error_response

        company = self._get_or_create_company(user)

        from ..serializers import CompanySerializer

        serializer = CompanySerializer(company)
        return Response(serializer.data, status=status.HTTP_200_OK)

    @extend_schema(
        summary="Обновление реквизитов компании",
        description="Обновляет реквизиты компании для B2B пользователя",
        request="CompanySerializer",
        responses={
            200: "CompanySerializer",
            400: "Ошибка валидации",
            403: "Доступ только для B2B пользователей",
            401: "Пользователь не авторизован",
        },
        tags=["Users"],
    )
    def put(self, request):
        """Обновление реквизитов компании"""
        user = request.user

        # Проверка B2B доступа
        error_response = self._check_b2b_access(user)
        if error_response:
            return error_response

        company = self._get_or_create_company(user)

        from ..serializers import CompanySerializer

        serializer = CompanySerializer(company, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()

            # Синхронизируем company_name и tax_id в User
            user.company_name = serializer.validated_data.get("legal_name", user.company_name)
            user.tax_id = serializer.validated_data.get("tax_id", user.tax_id)
            user.save(update_fields=["company_name", "tax_id"])

            return Response(serializer.data, status=status.HTTP_200_OK)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

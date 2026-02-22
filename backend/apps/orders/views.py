"""
API Views для заказов FREESPORT
Поддерживает создание заказов из корзины и просмотр деталей
"""

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Order
from .serializers import OrderCreateSerializer, OrderDetailSerializer, OrderListSerializer


class OrderViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления заказами
    """

    filter_backends = [DjangoFilterBackend]
    filterset_fields = ["status"]

    def get_permissions(self):
        """
        Настройка прав доступа:
        - create: Доступно всем (включая гостей)
        - остальные: Только авторизованные пользователи
        """
        if self.action == "create":
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        """Выбор сериализатора в зависимости от действия"""
        if self.action == "create":
            return OrderCreateSerializer
        elif self.action == "list":
            return OrderListSerializer
        return OrderDetailSerializer

    def get_queryset(self):
        """Получить заказы пользователя"""
        user = self.request.user
        if user.is_authenticated:
            return (
                Order.objects.filter(user=user)
                .select_related("user")
                .prefetch_related("items__product")
                .order_by("-created_at")
            )
        return Order.objects.none()

    @extend_schema(
        summary="Список заказов",
        description="Получение списка заказов пользователя с базовой информацией",
        responses={
            200: OrderListSerializer(many=True),
            401: OpenApiResponse(description="Пользователь не авторизован"),
        },
        tags=["Orders"],
    )
    def list(self, request, *args, **kwargs):
        """Получить список заказов пользователя"""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Детали заказа",
        description="Получение детальной информации о заказе с товарами",
        responses={
            200: OrderDetailSerializer,
            401: OpenApiResponse(description="Пользователь не авторизован"),
            404: OpenApiResponse(description="Заказ не найден"),
        },
        tags=["Orders"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Получить детали заказа"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Создание заказа",
        description="Создание нового заказа из корзины пользователя",
        request=OrderCreateSerializer,
        responses={
            201: OrderDetailSerializer,
            400: OpenApiResponse(
                description="Ошибки валидации или пустая корзина",
                examples=[
                    OpenApiExample(
                        "Пустая корзина",
                        value={"non_field_errors": ["Корзина пуста"]},
                        media_type="application/json",
                    )
                ],
            ),
            401: OpenApiResponse(description="Пользователь не авторизован"),
        },
        tags=["Orders"],
    )
    def create(self, request, *args, **kwargs):
        """Создать новый заказ из корзины"""
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()

        # Возвращаем детализированную информацию о созданном заказе
        detail_serializer = OrderDetailSerializer(order, context={"request": request})
        return Response(detail_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Отмена заказа",
        description=("Отмена заказа пользователем (только для статусов pending, " "confirmed)"),
        responses={
            200: OrderDetailSerializer,
            400: OpenApiResponse(
                description="Заказ не может быть отменен",
                examples=[
                    OpenApiExample(
                        "Неверный статус",
                        value={"error": "Заказ не может быть отменен в текущем статусе"},
                        media_type="application/json",
                    )
                ],
            ),
            401: OpenApiResponse(description="Пользователь не авторизован"),
            404: OpenApiResponse(description="Заказ не найден"),
        },
        tags=["Orders"],
    )
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Отменить заказ"""
        order = self.get_object()

        self.check_object_permissions(request, order)

        if pk is not None and str(pk) != str(order.pk):
            return Response(
                {"error": "Идентификатор заказа не совпадает с найденным объектом"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if order.status not in ["pending", "confirmed"]:
            order_identifier = f" {pk}" if pk is not None else ""
            return Response(
                {"error": (f"Заказ{order_identifier} не может быть отменен " f"в текущем статусе")},
                status=status.HTTP_400_BAD_REQUEST,
            )

        order.status = "cancelled"
        order.save()

        serializer = self.get_serializer(order)
        return Response(serializer.data)

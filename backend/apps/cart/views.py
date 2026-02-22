"""
Views для корзины покупок
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

if TYPE_CHECKING:
    pass  # Пока не используем TYPE_CHECKING импорты

from .models import Cart, CartItem
from .serializers import CartItemCreateSerializer, CartItemSerializer, CartItemUpdateSerializer, CartSerializer


class CartViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    ViewSet для управления корзиной пользователя
    Использует GenericViewSet + ListModelMixin
    так как корзина имеет специфичную логику
    """

    # Поддерживаем гостевые корзины
    permission_classes = [permissions.AllowAny]
    serializer_class = CartSerializer
    queryset = Cart.objects.all()  # Базовый queryset для Pylance

    def get_queryset(self):
        """Получить корзину текущего пользователя или гостя"""
        if self.request.user.is_authenticated:
            return Cart.objects.filter(user=self.request.user)
        else:
            # Для гостевых пользователей
            session_key = self.request.session.session_key
            if session_key:
                return Cart.objects.filter(session_key=session_key)
            return Cart.objects.none()

    def get_or_create_cart(self):
        """Получить или создать корзину для пользователя/гостя"""
        if self.request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=self.request.user)
        else:
            # Для гостевых пользователей
            if not self.request.session.session_key:
                self.request.session.create()
            session_key = self.request.session.session_key
            cart, created = Cart.objects.get_or_create(session_key=session_key)
        return cart

    @extend_schema(
        summary="Получить корзину",
        description="Получение содержимого корзины пользователя с ценами",
        tags=["Cart"],
    )
    def list(self, request, *args, **kwargs):
        """Получить содержимое корзины"""
        cart = self.get_or_create_cart()
        serializer = self.get_serializer(cart)
        return Response(serializer.data)

    @extend_schema(
        summary="Очистить корзину",
        description="Удаление всех товаров из корзины",
        tags=["Cart"],
    )
    @action(detail=False, methods=["delete"])
    def clear(self, request):
        """Очистить корзину"""
        cart = self.get_or_create_cart()
        cart.clear()
        return Response(status=status.HTTP_204_NO_CONTENT)


class CartItemViewSet(viewsets.ModelViewSet):
    """
    ViewSet для управления элементами корзины
    """

    permission_classes = [permissions.AllowAny]
    queryset = CartItem.objects.all()  # Базовый queryset для Pylance
    serializer_class = CartItemSerializer

    if TYPE_CHECKING:
        cart_item: CartItem  # Для типизации динамически создаваемого атрибута

    def get_queryset(self):
        """Получить элементы корзины текущего пользователя"""
        if self.request.user.is_authenticated:
            try:
                cart = Cart.objects.get(user=self.request.user)
                return CartItem.objects.filter(cart=cart).select_related("variant__product")
            except Cart.DoesNotExist:
                return CartItem.objects.none()
        else:
            session_key = self.request.session.session_key
            if session_key:
                try:
                    cart = Cart.objects.get(session_key=session_key)
                    return CartItem.objects.filter(cart=cart).select_related("variant__product")
                except Cart.DoesNotExist:
                    return CartItem.objects.none()
            return CartItem.objects.none()

    def get_serializer_class(self):
        """Выбор serializer в зависимости от действия"""
        if self.action == "create":
            return CartItemCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return CartItemUpdateSerializer
        return CartItemSerializer

    def get_or_create_cart(self):
        """Получить или создать корзину для пользователя/гостя"""
        if self.request.user.is_authenticated:
            cart, created = Cart.objects.get_or_create(user=self.request.user)
        else:
            if not self.request.session.session_key:
                self.request.session.create()
            session_key = self.request.session.session_key
            cart, created = Cart.objects.get_or_create(session_key=session_key)
        return cart

    def perform_create(self, serializer):
        """Добавить вариант товара в корзину с логикой объединения"""
        from apps.products.models import ProductVariant

        cart = self.get_or_create_cart()
        variant_id = serializer.validated_data["variant_id"]
        quantity = serializer.validated_data["quantity"]

        # Получаем вариант товара
        variant = ProductVariant.objects.select_related("product").get(pk=variant_id)

        # Получаем цену для текущего пользователя
        user = self.request.user if self.request.user.is_authenticated else None
        price = variant.get_price_for_user(user)

        # Проверяем, есть ли уже такой вариант в корзине
        try:
            cart_item = CartItem.objects.get(cart=cart, variant=variant)
            # Если есть, увеличиваем количество
            cart_item.quantity += quantity
            cart_item.save()
            self.cart_item = cart_item
        except CartItem.DoesNotExist:
            # Если нет, создаем новый элемент с снимком цены
            self.cart_item = CartItem.objects.create(
                cart=cart,
                variant=variant,
                quantity=quantity,
                price_snapshot=price,
            )

    @extend_schema(
        summary="Список товаров в корзине",
        description="Получение списка всех товаров в корзине пользователя",
        responses={200: CartItemSerializer(many=True)},
        tags=["Cart Items"],
    )
    def list(self, request, *args, **kwargs):
        """Получить список товаров в корзине"""
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Детали товара в корзине",
        description="Получение детальной информации о товаре в корзине",
        responses={
            200: CartItemSerializer,
            404: OpenApiResponse(description="Товар в корзине не найден"),
        },
        tags=["Cart Items"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Получить детали товара в корзине"""
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Добавить вариант товара в корзину",
        description=(
            "Добавление варианта товара (variant_id) в корзину с автоматическим "
            "объединением одинаковых вариантов. Цена фиксируется в момент добавления."
        ),
        tags=["Cart Items"],
    )
    def create(self, request, *args, **kwargs):
        """Добавить товар в корзину"""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)

        # Возвращаем сериализованный cart_item
        response_serializer = CartItemSerializer(self.cart_item, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_201_CREATED)

    @extend_schema(
        summary="Обновить количество товара",
        description="Полное изменение товара в корзине",
        request=CartItemUpdateSerializer,
        responses={
            200: CartItemSerializer,
            400: OpenApiResponse(description="Ошибки валидации"),
            404: OpenApiResponse(description="Товар в корзине не найден"),
        },
        tags=["Cart Items"],
    )
    def update(self, request, *args, **kwargs):
        """Обновить количество товара в корзине"""
        return super().update(request, *args, **kwargs)

    @extend_schema(
        summary="Частичное обновление товара",
        description="Частичное изменение количества товара в корзине",
        request=CartItemUpdateSerializer,
        responses={
            200: CartItemSerializer,
            400: OpenApiResponse(description="Ошибки валидации"),
            404: OpenApiResponse(description="Товар в корзине не найден"),
        },
        tags=["Cart Items"],
    )
    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление товара в корзине"""
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)

        # Возвращаем полный CartItem (не только quantity)
        # Frontend ожидает полный объект с id, product, variant и т.д.
        response_serializer = CartItemSerializer(instance, context={"request": request})
        return Response(response_serializer.data)

    @extend_schema(
        summary="Удалить товар из корзины",
        description="Удаление товара из корзины",
        tags=["Cart Items"],
    )
    def destroy(self, request, *args, **kwargs):
        """Удалить товар из корзины"""
        return super().destroy(request, *args, **kwargs)

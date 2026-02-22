"""
Сериализаторы для заказов FREESPORT
Поддерживает создание заказов из корзины с транзакционной логикой
"""

from decimal import Decimal
from typing import cast

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import F
from django.db.models.manager import BaseManager
from rest_framework import serializers

from apps.cart.models import Cart
from apps.products.models import Product, ProductVariant

from .models import Order, OrderItem


class OrderItemSerializer(serializers.ModelSerializer):
    """Сериализатор для элементов заказа"""

    class Meta:
        """Мета-класс для OrderItemSerializer"""

        model = OrderItem
        fields = [
            "id",
            "product",
            "variant",
            "product_name",
            "product_sku",
            "variant_info",
            "quantity",
            "unit_price",
            "total_price",
        ]
        read_only_fields = [
            "id",
            "product_name",
            "product_sku",
            "variant_info",
            "total_price",
        ]
        depth = 1


class OrderDetailSerializer(serializers.ModelSerializer):
    """Детальный сериализатор заказа"""

    items = OrderItemSerializer(many=True, read_only=True)
    customer_display_name = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    total_items = serializers.IntegerField(read_only=True)
    calculated_total = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)
    can_be_cancelled = serializers.BooleanField(read_only=True)

    class Meta:
        """Мета-класс для OrderDetailSerializer"""

        model = Order
        fields = [
            "id",
            "order_number",
            "user",
            "customer_display_name",
            "customer_name",
            "customer_email",
            "customer_phone",
            "status",
            "total_amount",
            "discount_amount",
            "delivery_cost",
            "delivery_address",
            "delivery_method",
            "delivery_date",
            "tracking_number",
            "payment_method",
            "payment_status",
            "payment_id",
            "notes",
            "sent_to_1c",
            "sent_to_1c_at",
            "status_1c",
            "created_at",
            "updated_at",
            "items",
            "subtotal",
            "total_items",
            "calculated_total",
            "can_be_cancelled",
        ]
        read_only_fields = [
            "id",
            "order_number",
            "user",
            "customer_display_name",
            "created_at",
            "updated_at",
            "items",
            "subtotal",
            "total_items",
            "calculated_total",
            "can_be_cancelled",
            "sent_to_1c",
            "sent_to_1c_at",
            "status_1c",
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания заказа из корзины"""

    class Meta:
        """Мета-класс для OrderCreateSerializer"""

        model = Order
        fields = [
            "delivery_address",
            "delivery_method",
            "delivery_date",
            "payment_method",
            "notes",
            "customer_name",
            "customer_email",
            "customer_phone",
        ]

    def validate(self, attrs):
        """Валидация данных заказа"""
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Контекст запроса обязателен")

        user = request.user if request.user.is_authenticated else None

        # Получаем корзину
        cart = self._get_user_cart(request, user)
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Корзина пуста")

        # Проверяем наличие товаров
        for item in cart.items.select_related("variant__product"):
            variant = item.variant
            product = variant.product if variant else None

            if not product or not product.is_active:
                raise serializers.ValidationError(
                    f"Товар '{product.name if product else 'неизвестен'}' " "больше недоступен"
                )

            if not variant or not variant.is_active:
                raise serializers.ValidationError(f"Вариант товара '{product.name}' больше недоступен")

            available_stock = variant.stock_quantity
            if item.quantity > available_stock:
                raise serializers.ValidationError(
                    f"Недостаточно товара '{product.name}' на складе. "
                    f"Доступно: {available_stock} штук, "
                    f"запрошено: {item.quantity} штук"
                )

            # Проверка минимального количества заказа
            if product.min_order_quantity > 1 and item.quantity < product.min_order_quantity:
                raise serializers.ValidationError(
                    f"Минимальное количество для заказа товара '{product.name}': " f"{product.min_order_quantity} шт."
                )

        # Валидация способов доставки и оплаты
        payment_method = attrs.get("payment_method")

        # Проверка совместимости для B2B/B2C
        if user and hasattr(user, "role"):
            if user.role.startswith("wholesale") and payment_method not in [
                "bank_transfer",
                "payment_on_delivery",
            ]:
                raise serializers.ValidationError(
                    ("Для оптовых покупателей доступны только банковский перевод и " "оплата при получении")
                )

        attrs["_cart"] = cart
        return attrs

    def _get_user_cart(self, request, user):
        """Получение корзины пользователя"""
        if user:
            return getattr(user, "cart", None)
        else:
            # Гостевая корзина по session
            session_key = request.session.session_key
            if session_key:
                cart_manager = cast(BaseManager[Cart], getattr(Cart, "objects"))
                try:
                    return cart_manager.get(session_key=session_key, user__isnull=True)
                except ObjectDoesNotExist:
                    pass
        return None

    @transaction.atomic
    def create(self, validated_data):
        """Создание заказа из корзины с транзакционной логикой"""
        cart = validated_data.pop("_cart")
        request = self.context.get("request")
        user = None
        if request and request.user and request.user.is_authenticated:
            user = request.user

        # Расчет стоимости доставки (пока статичная)
        delivery_cost = self.calculate_delivery_cost(validated_data["delivery_method"])

        # Создаем заказ
        order_data = {"user": user, "delivery_cost": delivery_cost, **validated_data}

        # Для гостевых заказов сохраняем контактные данные
        if not user:
            if request and hasattr(request, "data"):
                order_data.update(
                    {
                        "customer_name": validated_data.get("customer_name", ""),
                        "customer_email": validated_data.get("customer_email", ""),
                        "customer_phone": validated_data.get("customer_phone", ""),
                    }
                )

        order = Order(**order_data)

        # Рассчитываем общую сумму заказа
        total_amount = 0
        order_items = []

        variant_updates: list[tuple[int, int]] = []

        for cart_item in cart.items.select_related("variant__product"):
            variant = cart_item.variant
            product = variant.product if variant else None

            # Если по какой-то причине вариант потерян, валимся с понятной ошибкой
            if not variant or not product:
                raise serializers.ValidationError("Некорректный товар в корзине. Обновите корзину и попробуйте снова.")

            user_price = variant.get_price_for_user(user)
            item_total = user_price * cart_item.quantity
            total_amount += item_total

            # Формируем информацию о варианте (размер, цвет)
            variant_info_parts = []
            if variant.size_value:
                variant_info_parts.append(f"Размер: {variant.size_value}")
            if variant.color_name:
                variant_info_parts.append(f"Цвет: {variant.color_name}")
            variant_info_str = ", ".join(variant_info_parts)

            order_items.append(
                OrderItem(
                    order=order,
                    product=product,
                    variant=variant,
                    quantity=cart_item.quantity,
                    unit_price=user_price,
                    total_price=item_total,
                    product_name=product.name,
                    product_sku=variant.sku,
                    variant_info=variant_info_str,
                )
            )

            # Накопим данные для списания остатков по варианта
            variant_updates.append((variant.pk, cart_item.quantity))

        order.total_amount = total_amount + Decimal(delivery_cost)
        order.save()

        # Создаем элементы заказа
        order_item_manager = cast(BaseManager[OrderItem], getattr(OrderItem, "objects"))
        order_item_manager.bulk_create(order_items)

        # Списываем физические остатки со склада
        variant_manager = cast(BaseManager[ProductVariant], getattr(ProductVariant, "objects"))
        for variant_pk, quantity in variant_updates:
            variant_manager.filter(pk=variant_pk).update(stock_quantity=F("stock_quantity") - quantity)

        # Очищаем корзину (это вызовет сигнал для уменьшения reserved_quantity)
        cart.clear()

        return order

    def calculate_delivery_cost(self, delivery_method):
        """Расчет стоимости доставки"""
        delivery_costs = {
            "pickup": 0,
            "courier": 500,
            "post": 300,
            "transport_company": 1000,
            "transport_schedule": 1000,
        }
        return delivery_costs.get(delivery_method, 0)

    def to_representation(self, instance):
        """Возвращаем детальный вид созданного заказа"""
        return OrderDetailSerializer(instance, context=self.context).data


class OrderListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка заказов"""

    customer_display_name = serializers.CharField(read_only=True)
    total_items = serializers.IntegerField(read_only=True)

    class Meta:
        """Мета-класс для OrderListSerializer"""

        model = Order
        fields = [
            "id",
            "user",
            "order_number",
            "customer_display_name",
            "status",
            "total_amount",
            "delivery_method",
            "payment_method",
            "payment_status",
            "sent_to_1c",
            "created_at",
            "total_items",
        ]
        read_only_fields = [
            "id",
            "user",
            "order_number",
            "customer_display_name",
            "status",
            "total_amount",
            "delivery_method",
            "payment_method",
            "payment_status",
            "sent_to_1c",
            "created_at",
            "total_items",
        ]

"""
Сериализаторы для заказов FREESPORT
Поддерживает создание заказов из корзины с транзакционной логикой
"""

from decimal import Decimal
from typing import Any, cast

from django.core.exceptions import ObjectDoesNotExist
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
    """Детальный сериализатор заказа.

    Для мастер-заказов items/subtotal/total_items/calculated_total агрегируются
    из субзаказов (sub_orders). Для субзаказов — собственные items.
    """

    items = serializers.SerializerMethodField()
    customer_display_name = serializers.CharField(read_only=True)
    subtotal = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    calculated_total = serializers.SerializerMethodField()
    can_be_cancelled = serializers.BooleanField(read_only=True)

    def _collect_sub_items(self, obj: Order) -> list:
        """Собрать OrderItem из всех субзаказов (список, использующий prefetch cache)."""
        return [item for sub in obj.sub_orders.all() for item in sub.items.all()]

    def get_items(self, obj: Order) -> list[Any]:
        if obj.is_master:
            sub_items = self._collect_sub_items(obj)
            if sub_items:
                return cast(list[Any], OrderItemSerializer(sub_items, many=True).data)
            # Legacy master (до VAT-split): позиции лежат на самом мастере
        qs = obj.items.select_related("product", "variant")
        return cast(list[Any], OrderItemSerializer(qs, many=True).data)

    def get_subtotal(self, obj: Order) -> Decimal:
        if obj.is_master:
            sub_items = self._collect_sub_items(obj)
            if sub_items:
                return Decimal(sum(item.total_price for item in sub_items))
        return obj.subtotal

    def get_total_items(self, obj: Order) -> int:
        if obj.is_master:
            sub_items = self._collect_sub_items(obj)
            if sub_items:
                return sum(item.quantity for item in sub_items)
        return obj.total_items

    def get_calculated_total(self, obj: Order) -> Decimal:
        if obj.is_master:
            sub_items = self._collect_sub_items(obj)
            if sub_items:
                items_total = Decimal(sum(item.total_price for item in sub_items))
                delivery_cost = Decimal(obj.delivery_cost or Decimal("0"))
                discount_amount = Decimal(obj.discount_amount or Decimal("0"))
                return items_total + delivery_cost - discount_amount
        return obj.calculated_total

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
            "is_master",
            "vat_group",
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
            "can_be_cancelled",
            "sent_to_1c",
            "sent_to_1c_at",
            "status_1c",
            "is_master",
            "vat_group",
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """Сериализатор создания заказа из корзины"""

    # discount_amount принимается от клиента, но сервер всегда устанавливает его в 0
    # (promo-система не реализована). Поле присутствует в схеме, чтобы:
    # a) OpenAPI/frontend знали о его существовании
    # b) отрицательные значения явно отклонялись с 400 (min_value=0)
    discount_amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        default=Decimal("0"),
    )

    # promo_code — заглушка под будущую promo-систему (Story 34-2 [Review][Patch]).
    # Поле принимается от клиента, но на текущем этапе игнорируется сервером;
    # discount_amount остаётся 0 до реализации PromoCode.validate(cart, user).
    promo_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=100,
    )

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
            "discount_amount",
            "promo_code",
        ]

    def validate(self, attrs):
        """Валидация данных заказа"""
        request = self.context.get("request")
        if not request:
            raise serializers.ValidationError("Контекст запроса обязателен")

        request_user = getattr(request, "user", None)
        if not request_user or not request_user.is_authenticated:
            raise serializers.ValidationError("Для оформления заказа требуется авторизация")

        user = request_user
        if not getattr(user, "customer_code", ""):
            raise serializers.ValidationError("Для оформления заказа требуется customer_code")

        # Получаем корзину
        cart = self._get_user_cart(user)
        if not cart or not cart.items.exists():
            raise serializers.ValidationError("Корзина пуста")

        # Проверяем наличие товаров; заодно считаем сумму по snapshot-ценам
        total_items_sum = Decimal("0")
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

            total_items_sum += Decimal(str(item.total_price))

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

    def _get_user_cart(self, user):
        """Получение корзины пользователя"""
        if user:
            return getattr(user, "cart", None)
        return None

    def create(self, validated_data):
        """Создание заказа из корзины — делегирует OrderCreateService."""
        from apps.orders.services.order_create import OrderCreateService

        cart = validated_data.pop("_cart")
        request = self.context.get("request")
        user = None
        if request and request.user and request.user.is_authenticated:
            user = request.user

        delivery_cost = Decimal(str(self.calculate_delivery_cost(validated_data["delivery_method"])))

        service = OrderCreateService(
            cart=cart,
            user=user,
            validated_data=validated_data,
            delivery_cost=delivery_cost,
        )
        return service.create()

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
    """Сериализатор для списка заказов.

    Для мастер-заказов `total_items` агрегируется из субзаказов: direct items
    мастера всегда пусты (все позиции живут в sub_orders), поэтому использовать
    Order.total_items напрямую нельзя — это даст 0 и сломает клиентский контракт.
    """

    customer_display_name = serializers.CharField(read_only=True)
    total_items = serializers.SerializerMethodField()

    def get_total_items(self, obj: Order) -> int:
        if obj.is_master:
            sub_items = [item for sub in obj.sub_orders.all() for item in sub.items.all()]
            if sub_items:
                return sum(item.quantity for item in sub_items)
            # Legacy master (до VAT-split): позиции лежат на самом мастере
        return obj.total_items

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
            "is_master",
            "vat_group",
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
            "is_master",
            "vat_group",
            "sent_to_1c",
            "created_at",
            "total_items",
        ]

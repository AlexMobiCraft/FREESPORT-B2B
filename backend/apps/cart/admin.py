"""
Админ панель для корзины покупок
"""

from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    """
    Inline для отображения элементов корзины
    """

    model = CartItem
    extra = 0
    readonly_fields = ("total_price", "added_at", "updated_at")
    fields = ("variant", "quantity", "price_snapshot", "total_price", "added_at")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    """
    Админ панель для корзин
    """

    list_display = (
        "id",
        "user_display",
        "total_items",
        "total_amount",
        "created_at",
        "updated_at",
    )
    list_filter = ("created_at", "updated_at")
    search_fields = ("user__email", "session_key")
    readonly_fields = ("total_items", "total_amount", "created_at", "updated_at")
    inlines = [CartItemInline]

    @admin.display(description="Пользователь")
    def user_display(self, obj):
        """Отображение пользователя или гостя"""
        if obj.user:
            return f"{obj.user.email}"
        return f"Гость ({obj.session_key[:10]}...)"


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    """
    Админ панель для элементов корзины
    """

    list_display = (
        "id",
        "cart_user",
        "variant_display",
        "quantity",
        "price_snapshot",
        "total_price",
        "added_at",
    )
    list_filter = ("added_at", "updated_at")
    search_fields = (
        "variant__product__name",
        "variant__sku",
        "cart__user__email",
    )
    readonly_fields = ("total_price", "added_at", "updated_at")

    @admin.display(description="Владелец корзины")
    def cart_user(self, obj):
        """Отображение владельца корзины"""
        if obj.cart.user:
            return f"{obj.cart.user.email}"
        return f"Гость ({obj.cart.session_key[:10]}...)"

    @admin.display(description="Вариант товара")
    def variant_display(self, obj):
        """Отображение варианта товара с характеристиками"""
        variant_info = []
        if obj.variant.color_name:
            variant_info.append(obj.variant.color_name)
        if obj.variant.size_value:
            variant_info.append(obj.variant.size_value)
        variant_str = f" ({', '.join(variant_info)})" if variant_info else ""
        return f"{obj.variant.product.name}{variant_str}"

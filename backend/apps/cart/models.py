"""
Модели корзины покупок для платформы FREESPORT
Поддерживает как авторизованных, так и гостевых пользователей
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q

if TYPE_CHECKING:
    from django.db.models import QuerySet

User = get_user_model()


class Cart(models.Model):
    """
    Модель корзины покупок
    Поддерживает как авторизованных пользователей, так и гостей (по session_key)
    """

    if TYPE_CHECKING:
        items: QuerySet["CartItem"]  # Hint для Pylance о related_name

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="cart",
        verbose_name="Пользователь",
    )
    session_key = models.CharField(
        "Ключ сессии",
        max_length=100,
        blank=True,
        help_text="Для гостевых пользователей",
    )
    created_at = models.DateTimeField("Дата создания", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Корзина"
        verbose_name_plural = "Корзины"
        db_table = "carts"
        constraints = [
            # Корзина должна иметь либо пользователя, либо session_key
            models.CheckConstraint(
                check=Q(user__isnull=False) | Q(session_key__isnull=False),
                name="cart_must_have_user_or_session",
            )
        ]

    def __str__(self):
        if self.user:
            return f"Корзина пользователя {str(self.user.email or '')}"
        return f"Гостевая корзина {self.session_key[:10]}..."

    @property
    def total_items(self):
        """Общее количество товаров в корзине"""
        from django.db.models import Sum

        result = self.items.aggregate(total=Sum("quantity"))["total"]
        return result or 0

    @property
    def total_amount(self) -> "Decimal":
        """Общая стоимость товаров в корзине на основе снимков цен"""
        total = Decimal("0")
        for item in self.items.all():
            total += item.total_price
        return total

    def clear(self):
        """Очистить корзину"""
        self.items.all().delete()
        # Обновляем только updated_at без лишнего save()
        self.save(update_fields=["updated_at"])


class CartItem(models.Model):
    """
    Элемент корзины - вариант товара (ProductVariant) с количеством
    """

    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items", verbose_name="Корзина")
    variant = models.ForeignKey(
        "products.ProductVariant",
        on_delete=models.CASCADE,
        verbose_name="Вариант товара",
        help_text="SKU-вариант товара с конкретными характеристиками (цвет, размер)",
    )
    quantity = models.PositiveIntegerField("Количество", default=1, validators=[MinValueValidator(1)])
    price_snapshot = models.DecimalField(
        "Снимок цены",
        max_digits=10,
        decimal_places=2,
        help_text="Цена варианта на момент добавления в корзину",
    )
    added_at = models.DateTimeField("Дата добавления", auto_now_add=True)
    updated_at = models.DateTimeField("Дата обновления", auto_now=True)

    class Meta:
        verbose_name = "Элемент корзины"
        verbose_name_plural = "Элементы корзины"
        db_table = "cart_items"
        unique_together = ("cart", "variant")
        indexes = [
            models.Index(fields=["cart", "added_at"]),
        ]

    def __str__(self) -> str:
        product_name = self.variant.product.name
        variant_info = []
        if self.variant.color_name:
            variant_info.append(self.variant.color_name)
        if self.variant.size_value:
            variant_info.append(self.variant.size_value)
        variant_str = f" ({', '.join(variant_info)})" if variant_info else ""
        return f"{product_name}{variant_str} x{self.quantity} в корзине"

    @property
    def total_price(self) -> "Decimal":
        """Стоимость этого элемента корзины на основе снимка цены"""
        return self.price_snapshot * self.quantity

    def clean(self) -> None:
        """Валидация элемента корзины"""
        from django.core.exceptions import ValidationError

        # Проверяем, что товар и вариант активны
        if not self.variant.product.is_active:
            raise ValidationError("Товар неактивен")

        if not self.variant.is_active:
            raise ValidationError("Вариант товара неактивен")

        # Проверяем наличие на складе
        if self.quantity > self.variant.stock_quantity:
            raise ValidationError(f"Недостаточно товара на складе. " f"Доступно: {self.variant.stock_quantity}")

    def save(self, *args, **kwargs):
        # Используем getattr для обхода проверки типов mypy, так как поле не null=True в модели,
        # но может быть None до сохранения
        if getattr(self, "price_snapshot", None) is None:
            user = self.cart.user
            self.price_snapshot = self.variant.get_price_for_user(user)
        self.full_clean()
        super().save(*args, **kwargs)
        # Обновляем время модификации корзины
        self.cart.save(update_fields=["updated_at"])

"""
Отладочный тест для проблемы с очисткой корзины
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError

from apps.cart.models import Cart, CartItem
from tests.conftest import CartFactory, CartItemFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestDebugCart:
    def test_cart_clear_debug(self):
        print("\n--- Starting test_cart_clear_debug ---")

        # Переопределяем методы для отладки через патч, чтобы они не текли в другие тесты
        def new_clean(self):
            print(
                f"[DEBUG] Cleaning CartItem {self.id} for product " f"{self.variant.product.id} (qty: {self.quantity})"
            )
            # ... упрощенная логика clean ...
            if not self.variant.product.is_active:
                raise ValidationError("Товар неактивен")
            if self.quantity > self.variant.stock_quantity:
                raise ValidationError(f"Недостаточно товара на складе. " f"Доступно: {self.variant.stock_quantity}")

        def new_save(self, *args, **kwargs):
            print(
                f"[DEBUG] Saving CartItem {self.id or 'new'} for product "
                f"{self.variant.product.id} (qty: {self.quantity})"
            )
            self.full_clean()
            super(CartItem, self).save(*args, **kwargs)
            self.cart.save(update_fields=["updated_at"])

        def new_delete(self, *args, **kwargs):
            print(
                f"[DEBUG] Deleting CartItem {self.id} for product " f"{self.variant.product.id} (qty: {self.quantity})"
            )
            super(CartItem, self).delete(*args, **kwargs)

        with patch.object(CartItem, "clean", new_clean), patch.object(CartItem, "save", new_save), patch.object(
            CartItem, "delete", new_delete
        ):
            # Логика теста
            product = ProductFactory.create(stock_quantity=10)
            variant = product.variants.first()
            print(f"Product {product.id} created with " f"variant stock={variant.stock_quantity}")

            cart = CartFactory.create()
            print(f"Cart {cart.id} created.")

            print("Creating CartItem 1...")
            item1 = CartItemFactory.create(cart=cart, product=product, quantity=2)
            variant.refresh_from_db()
            print(
                f"CartItem 1 ({item1.id}) created. Variant stock: "
                f"{variant.stock_quantity}, reserved: {variant.reserved_quantity}"
            )

            print("Creating CartItem 2...")
            product2 = ProductFactory.create(stock_quantity=5)
            variant2 = product2.variants.first()
            print(f"Product {product2.id} created with " f"variant stock={variant2.stock_quantity}")
            item2 = CartItemFactory.create(cart=cart, product=product2, quantity=3)
            variant2.refresh_from_db()
            print(
                f"CartItem 2 ({item2.id}) created. Variant2 stock: "
                f"{variant2.stock_quantity}, reserved: {variant2.reserved_quantity}"
            )

            assert cart.items.count() == 2
            print("\n--- Calling cart.clear() ---")
            cart.clear()
            print("--- cart.clear() finished ---")

            assert cart.items.count() == 0
            print("Test finished successfully.")

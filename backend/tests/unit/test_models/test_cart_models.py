"""
Тесты для моделей корзины FREESPORT Platform
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.cart.models import Cart, CartItem
from tests.conftest import CartFactory, CartItemFactory, ProductFactory, UserFactory


@pytest.mark.django_db
class TestCartModel:
    """Тесты модели Cart"""

    def test_cart_creation_with_user(self):
        """Тест создания корзины с пользователем"""
        user = UserFactory.create()
        cart = CartFactory.create(user=user)

        assert cart.user == user
        assert cart.session_key == ""
        assert str(cart) == f"Корзина пользователя {user.email}"

    def test_cart_creation_guest(self):
        """Тест создания корзины для гостя"""
        cart = CartFactory.create(user=None, session_key="guest123")

        assert cart.user is None
        assert cart.session_key == "guest123"
        assert "Гостевая корзина guest123" in str(cart)

    def test_cart_total_items(self):
        """Тест подсчета общего количества товаров в корзине"""
        cart = CartFactory.create()
        CartItemFactory.create(cart=cart, quantity=2)
        CartItemFactory.create(cart=cart, quantity=3)

        assert cart.total_items == 5

    def test_cart_total_amount(self):
        """Тест подсчета общей стоимости корзины"""
        user = UserFactory.create(role="retail")
        cart = CartFactory.create(user=user)

        # Создаем товары. Цены теперь в вариантах
        product1 = ProductFactory.create(retail_price=Decimal("1000.00"))
        product2 = ProductFactory.create(retail_price=Decimal("500.00"))
        variant1 = product1.variants.first()
        variant2 = product2.variants.first()

        CartItemFactory.create(cart=cart, variant=variant1, quantity=2)
        CartItemFactory.create(cart=cart, variant=variant2, quantity=1)

        expected_total = Decimal("1000.00") * 2 + Decimal("500.00") * 1
        assert cart.total_amount == expected_total

    def test_cart_total_amount_different_user_roles(self):
        """Тест стоимости корзины для разных ролей пользователей"""
        # Оптовый пользователь
        wholesale_user = UserFactory.create(role="wholesale_level1")
        cart = CartFactory.create(user=wholesale_user)

        product = ProductFactory.create(retail_price=Decimal("1000.00"), opt1_price=Decimal("900.00"))
        variant = product.variants.first()

        # Обычно цена фиксируется в price_snapshot при добавлении в корзину
        # Логика определения цены лежит в сервисе корзины, но фабрика эмулирует это
        item = CartItemFactory.create(cart=cart, variant=variant, quantity=1, price_snapshot=Decimal("900.00"))

        # Проверяем, что snapshot сохранился корректно
        assert item.price_snapshot == Decimal("900.00"), (
            f"Snapshot is {item.price_snapshot}, expected 900.00. " f"Variant retail: {variant.retail_price}"
        )

        # Должна использоваться цена из snapshot (оптовая)
        assert cart.total_amount == Decimal("900.00")

    def test_cart_clear(self):
        """Тест очистки корзины"""
        cart = CartFactory.create()
        CartItemFactory.create(cart=cart)
        CartItemFactory.create(cart=cart)

        assert cart.items.count() == 2

        cart.clear()
        assert cart.items.count() == 0

    def test_cart_meta_configuration(self):
        """Тест настроек Meta класса Cart"""
        assert Cart._meta.verbose_name == "Корзина"
        assert Cart._meta.verbose_name_plural == "Корзины"
        assert Cart._meta.db_table == "carts"


@pytest.mark.django_db
class TestCartItemModel:
    """Тесты модели CartItem"""

    def test_cart_item_creation(self):
        """Тест создания элемента корзины"""
        cart = CartFactory.create()
        product = ProductFactory.create(name="Тестовый товар")
        variant = product.variants.first()
        item = CartItemFactory.create(cart=cart, variant=variant, quantity=2)

        assert item.cart == cart
        assert item.variant == variant
        assert item.variant.product == product
        assert item.quantity == 2

        # Проверяем строковое представление, которое обычно содержит имя продукта
        assert "Тестовый товар" in str(item)

    def test_cart_item_total_price(self):
        """Тест подсчета стоимости элемента корзины"""
        user = UserFactory.create(role="retail")
        cart = CartFactory.create(user=user)
        product = ProductFactory.create(retail_price=Decimal("1000.00"))
        variant = product.variants.first()

        item = CartItemFactory.create(cart=cart, variant=variant, quantity=3)

        assert item.total_price == Decimal("3000.00")

    def test_cart_item_total_price_with_user_role(self):
        """Тест стоимости элемента для разных ролей пользователей"""
        trainer_user = UserFactory.create(role="trainer")
        cart = CartFactory.create(user=trainer_user)
        product = ProductFactory.create(retail_price=Decimal("1000.00"), trainer_price=Decimal("850.00"))
        variant = product.variants.first()

        # Эмулируем добавление с ценой тренера
        item = CartItemFactory.create(cart=cart, variant=variant, quantity=2, price_snapshot=Decimal("850.00"))

        # Должна использоваться цена тренера
        assert item.total_price == Decimal("1700.00")

    def test_cart_item_unique_constraint(self):
        """Тест уникальности товара в корзине"""
        cart = CartFactory.create()
        product = ProductFactory.create()
        variant = product.variants.first()

        CartItemFactory.create(cart=cart, variant=variant)

        # Попытка добавить тот же вариант в ту же корзину должна вызвать ошибку
        with pytest.raises((IntegrityError, ValidationError)):
            CartItemFactory.create(cart=cart, variant=variant)

    def test_cart_item_validation_inactive_product(self):
        """Тест валидации неактивного товара"""
        inactive_product = ProductFactory.create(is_active=False)
        variant = inactive_product.variants.first()
        cart = CartFactory.create()

        with pytest.raises(ValidationError):
            item = CartItemFactory.build(cart=cart, variant=variant, quantity=1)
            item.full_clean()

    def test_cart_item_validation_inactive_variant(self):
        """Тест валидации неактивного варианта"""
        product = ProductFactory.create(is_active=True)
        # Создаем неактивный вариант вручную или меняем существующий
        variant = product.variants.first()
        variant.is_active = False
        variant.save()

        cart = CartFactory.create()

        with pytest.raises(ValidationError):
            item = CartItemFactory.build(cart=cart, variant=variant, quantity=1)
            item.full_clean()

    def test_cart_item_validation_insufficient_stock(self):
        """Тест валидации недостаточного количества на складе"""
        product = ProductFactory.create(stock_quantity=5)
        variant = product.variants.first()
        cart = CartFactory.create()

        with pytest.raises(ValidationError):
            item = CartItemFactory.build(cart=cart, variant=variant, quantity=10)
            item.full_clean()

    @pytest.mark.skip(reason="Validation for min_order_quantity not implemented in CartItem model yet")
    def test_cart_item_validation_min_order_quantity(self):
        """Тест валидации минимального количества заказа"""
        # min_order_quantity находится в Product, но проверяется для варианта
        product = ProductFactory.create(min_order_quantity=5)
        variant = product.variants.first()
        cart = CartFactory.create()

        # Тест требует реализации логики в модели CartItem
        with pytest.raises(ValidationError):
            item = CartItemFactory.build(cart=cart, variant=variant, quantity=3)
            item.full_clean()

    def test_cart_item_validation_positive_quantity(self):
        """Тест валидации положительного количества"""
        cart = CartFactory.create()
        product = ProductFactory.create()
        variant = product.variants.first()

        with pytest.raises(ValidationError):
            item = CartItemFactory.build(cart=cart, variant=variant, quantity=0)
            item.full_clean()

    def test_cart_item_updates_cart_timestamp(self):
        """Тест обновления времени модификации корзины при добавлении товара"""
        cart = CartFactory.create()
        original_updated_at = cart.updated_at

        # Небольшая задержка
        import time

        time.sleep(0.01)

        CartItemFactory.create(cart=cart)
        cart.refresh_from_db()

        assert cart.updated_at > original_updated_at

    def test_cart_item_meta_configuration(self):
        """Тест настроек Meta класса CartItem"""
        assert CartItem._meta.verbose_name == "Элемент корзины"
        assert CartItem._meta.verbose_name_plural == "Элементы корзины"
        assert CartItem._meta.db_table == "cart_items"

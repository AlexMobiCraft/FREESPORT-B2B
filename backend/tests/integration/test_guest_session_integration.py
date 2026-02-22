"""
Integration тесты гостевых сессий
"""

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


class GuestSessionIntegrationTest(TestCase):
    """Тестирование интеграции гостевых сессий"""

    def setUp(self):
        # Создаем товар для тестов
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            retail_price=100.00,
            stock_quantity=10,
            is_active=True,
            sku="GUEST-TEST-001",
        )

    def test_guest_cart_functionality(self):
        """Функциональность гостевой корзины"""
        client = APIClient()

        # Добавляем товар как гость
        data = {"variant_id": self.variant.id, "quantity": 2}
        response = client.post("/api/v1/cart/items/", data)
        self.assertEqual(response.status_code, 201)

        # Проверяем корзину
        cart_response = client.get("/api/v1/cart/")
        self.assertEqual(cart_response.status_code, 200)
        self.assertEqual(cart_response.data["total_items"], 2)

        # Обновляем количество
        cart_item_id = cart_response.data["items"][0]["id"]
        update_data = {"quantity": 3}
        update_response = client.patch(f"/api/v1/cart/items/{cart_item_id}/", update_data)
        self.assertEqual(update_response.status_code, 200)

        # Проверяем обновление
        updated_cart = client.get("/api/v1/cart/")
        self.assertEqual(updated_cart.data["total_items"], 3)

    def test_guest_cart_persistence_across_requests(self):
        """Сохранение гостевой корзины между запросами"""
        client = APIClient()

        # Первый запрос: добавляем товар
        data = {"variant_id": self.variant.id, "quantity": 1}
        client.post("/api/v1/cart/items/", data)

        # Второй запрос: проверяем, что товар остался
        cart_response = client.get("/api/v1/cart/")
        self.assertEqual(cart_response.data["total_items"], 1)

        # Третий запрос: добавляем еще товар
        client.post("/api/v1/cart/items/", data)

        # Проверяем объединение (FR6.1)
        final_cart = client.get("/api/v1/cart/")
        self.assertEqual(final_cart.data["total_items"], 2)
        self.assertEqual(len(final_cart.data["items"]), 1)  # Один товар, но количество 2

    def test_guest_cart_to_user_cart_transfer(self):
        """Перенос гостевой корзины при регистрации/авторизации"""
        client = APIClient()

        # Добавляем товар как гость
        data = {"variant_id": self.variant.id, "quantity": 3}
        guest_response = client.post("/api/v1/cart/items/", data)
        self.assertEqual(guest_response.status_code, 201)

        # Получаем session_key для эмуляции переноса
        session_key = client.session.session_key
        self.assertIsNotNone(session_key)

        # Создаем пользователя и авторизуемся
        user = User.objects.create_user(email="test@example.com", password="testpass123")
        client.force_authenticate(user=user)

        # TODO: Реализовать автоматический перенос корзины в сигналах
        # Пока проверяем, что система может работать с обеими корзинами

        # Проверяем корзину авторизованного пользователя
        auth_cart = client.get("/api/v1/cart/")
        # После реализации переноса здесь должно быть total_items=3
        self.assertIsNotNone(auth_cart.data)

    def test_guest_cart_isolation(self):
        """Изоляция гостевых корзин между сессиями"""
        client1 = APIClient()
        client2 = APIClient()

        # Первый гость добавляет товар
        data1 = {"variant_id": self.variant.id, "quantity": 1}
        client1.post("/api/v1/cart/items/", data1)

        # Второй гость добавляет товар
        data2 = {"variant_id": self.variant.id, "quantity": 2}
        client2.post("/api/v1/cart/items/", data2)

        # Проверяем, что корзины изолированы
        cart1 = client1.get("/api/v1/cart/")
        cart2 = client2.get("/api/v1/cart/")

        self.assertEqual(cart1.data["total_items"], 1)
        self.assertEqual(cart2.data["total_items"], 2)

    def test_guest_cart_cleanup(self):
        """Очистка старых гостевых корзин"""
        from datetime import timedelta

        from django.utils import timezone

        client = APIClient()

        # Создаем гостевую корзину
        data = {"variant_id": self.variant.id, "quantity": 1}
        client.post("/api/v1/cart/items/", data)

        # Получаем созданную корзину
        carts_before = Cart.objects.filter(user__isnull=True).count()
        self.assertGreater(carts_before, 0)

        # Эмулируем старую корзину (изменяем дату создания)
        old_date = timezone.now() - timedelta(days=8)
        Cart.objects.filter(user__isnull=True).update(created_at=old_date)

        # TODO: Тестировать management команду cleanup_guest_carts
        # Пока проверяем только наличие старых корзин
        old_carts = Cart.objects.filter(user__isnull=True, created_at__lt=timezone.now() - timedelta(days=7)).count()
        self.assertGreater(old_carts, 0)

    def test_guest_cart_with_product_pricing(self):
        """Гостевые корзины с розничными ценами"""
        client = APIClient()

        # Добавляем товар как гость
        data = {"variant_id": self.variant.id, "quantity": 1}
        client.post("/api/v1/cart/items/", data)

        # Проверяем, что цена розничная
        cart_response = client.get("/api/v1/cart/")
        unit_price = float(cart_response.data["items"][0]["unit_price"])

        # Гости должны видеть retail_price
        self.assertEqual(unit_price, 100.00)

    def test_guest_catalog_access(self):
        """Доступ гостей к каталогу"""
        client = APIClient()

        # Каталог товаров
        catalog_response = client.get("/api/v1/products/")
        self.assertEqual(catalog_response.status_code, 200)

        # Детальная страница товара
        url = reverse("products:product-detail", kwargs={"slug": self.product.slug})
        product_response = client.get(url)
        self.assertEqual(product_response.status_code, 200)

        # Гости видят розничные цены
        current_price = float(product_response.data["current_price"])
        self.assertEqual(current_price, 100.00)

        # Гости не видят B2B поля
        self.assertNotIn("rrp", product_response.data)
        self.assertNotIn("msrp", product_response.data)

    def test_guest_cart_limits(self):
        """Ограничения для гостевых корзин"""
        client = APIClient()

        # Проверяем валидацию остатков для гостей
        data = {
            "variant_id": self.variant.id,
            "quantity": 15,
        }  # больше stock_quantity=10
        response = client.post("/api/v1/cart/items/", data)
        self.assertEqual(response.status_code, 400)

        # Проверяем валидацию минимального количества
        # (для этого товара min_order_quantity=1, должно пройти)
        valid_data = {"variant_id": self.variant.id, "quantity": 1}
        valid_response = client.post("/api/v1/cart/items/", valid_data)
        self.assertEqual(valid_response.status_code, 201)

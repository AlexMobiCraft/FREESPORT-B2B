"""
Интеграционные тесты для Orders API
"""

from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestOrderAPI:
    """Интеграционные тесты для Orders API"""

    def setup_method(self):
        """Настройка данных для тестов"""
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass",
            first_name="John",
            last_name="Doe",
            role="retail",
            customer_code="04620",
        )
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=self.brand,
            category=self.category,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="TEST001",
            onec_id="1C-TEST001",
            retail_price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
        )

    def test_create_order_from_cart_success(self, db):
        """Тест успешного создания заказа из корзины"""
        # Авторизуемся
        self.client.force_authenticate(user=self.user)

        # Создаем корзину с товаром
        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=2,
            price_snapshot=self.variant.retail_price,
        )

        # Данные для создания заказа
        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
            "notes": "Тестовый заказ",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_201_CREATED
        assert "order_number" in response.data

        # Проверяем, что заказ создался (мастер-заказ по контракту Story 34-2)
        order = Order.objects.get(order_number=response.data["order_number"])
        assert order.user == self.user
        assert order.is_master is True
        assert order.status == "pending"
        assert order.total_amount == Decimal("700.00")  # 2 * 100 + 500 доставка
        assert order.delivery_cost == Decimal("500.00")
        assert order.order_number.startswith("04620")
        assert len(order.order_number) == 10
        assert order.customer_code_snapshot == "04620"
        assert order.customer_year_sequence == 1
        assert order.order_year is not None

        # После VAT-split позиции живут на субзаказах, а не на мастере
        assert order.items.count() == 0
        sub_orders = list(order.sub_orders.all())
        assert len(sub_orders) == 1  # однородная корзина (одна vat_rate=None)
        sub = sub_orders[0]
        assert sub.is_master is False
        assert sub.order_number == f"{order.order_number}1"
        assert sub.suborder_sequence == 1
        assert sub.customer_code_snapshot == "04620"
        assert sub.items.count() == 1
        order_item = sub.items.first()
        assert order_item.variant == self.variant
        assert order_item.quantity == 2
        assert order_item.unit_price == Decimal("100.00")
        assert order_item.product_name == "Test Product"
        assert order_item.product_sku == "TEST001"

        # В API-ответе items агрегированы из субзаказов — клиентский контракт сохранён
        assert len(response.data["items"]) == 1
        assert response.data["items"][0]["product_name"] == "Test Product"

        # Проверяем, что корзина очистилась
        assert not cart.items.exists()

    def test_create_order_empty_cart_failure(self, db):
        """Тест создания заказа с пустой корзиной"""
        self.client.force_authenticate(user=self.user)

        # Создаем пустую корзину
        Cart.objects.create(user=self.user)

        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Корзина пуста" in str(response.data)

    def test_create_order_user_without_customer_code_failure(self, db):
        user_without_customer_code = User.objects.create_user(
            email="no-code@example.com",
            password="testpass",
            first_name="No",
            last_name="Code",
            role="retail",
            customer_code="",
        )
        self.client.force_authenticate(user=user_without_customer_code)

        cart = Cart.objects.create(user=user_without_customer_code)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=self.variant.retail_price,
        )

        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "customer_code" in str(response.data)

    def test_create_order_insufficient_stock_failure(self, db):
        """Тест создания заказа при недостатке товара"""
        self.client.force_authenticate(user=self.user)

        # Создаем корзину с количеством больше чем на складе
        cart = Cart.objects.create(user=self.user)
        # Временно увеличим stock для создания CartItem
        original_stock = self.variant.stock_quantity
        self.variant.stock_quantity = 20
        self.variant.save()
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=15,
            price_snapshot=self.variant.retail_price,
        )
        # Вернем исходный stock для теста
        self.variant.stock_quantity = original_stock
        self.variant.save()

        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Недостаточно товара" in str(response.data)

    def test_create_order_anonymous_returns_401(self, db):
        """Анонимный запрос POST /orders/ должен возвращать 401 (не 400)."""
        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_checkout_queues_exactly_one_email_task_for_master(self, db):
        """При checkout с субзаказами email-задачи ставятся только для master (1 раз каждая)."""
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=self.variant.retail_price,
        )

        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
        }

        url = reverse("orders:order-list")
        with patch("apps.orders.tasks.send_order_confirmation_to_customer") as mock_customer, \
             patch("apps.orders.tasks.send_order_notification_email") as mock_admin:
            response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_201_CREATED
        assert mock_customer.delay.call_count == 1
        assert mock_admin.delay.call_count == 1

    def test_create_order_guest_with_session_cart_is_rejected(self, db):
        """Гостевой checkout через session-корзину запрещён новой схемой нумерации."""
        self.client.post(
            reverse("cart:cart-items-list"),
            {"variant_id": self.variant.id, "quantity": 1},
        )
        session_key = self.client.session.session_key
        assert session_key is not None
        guest_cart = Cart.objects.get(session_key=session_key, user__isnull=True)
        assert guest_cart.items.count() == 1

        order_data = {
            "delivery_address": "Guest addr 1",
            "delivery_method": "pickup",
            "payment_method": "card",
            "customer_email": "guest@example.com",
            "customer_phone": "+79990000000",
            "customer_name": "Guest User",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        guest_cart.refresh_from_db()
        assert guest_cart.items.count() == 1

    def test_legacy_master_with_direct_items_backward_compat(self, db):
        """Regression (Story 34-2 Third Follow-up): legacy мастер-заказ с direct items
        (без sub_orders) должен корректно сериализоваться — items/subtotal/total_items/
        calculated_total читаются по direct items, а не возвращают пустые значения.
        """
        self.client.force_authenticate(user=self.user)

        # Legacy master: is_master=True (default), но sub_orders нет, items живут на самом заказе
        order = Order.objects.create(
            user=self.user,
            delivery_address="legacy",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("700.00"),
            delivery_cost=Decimal("500.00"),
        )
        assert order.is_master is True
        assert order.sub_orders.count() == 0
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant,
            quantity=2,
            unit_price=Decimal("100.00"),
            product_name=self.product.name,
            product_sku=self.variant.sku,
        )

        # Detail endpoint: items/агрегаты корректно читаются по direct items
        url = reverse("orders:order-detail", kwargs={"pk": order.pk})
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["items"]) == 1
        assert response.data["items"][0]["product_name"] == "Test Product"
        assert response.data["total_items"] == 2
        assert Decimal(str(response.data["subtotal"])) == Decimal("200.00")
        # Legacy calculated_total = сумма позиций (поведение Order.calculated_total
        # до Story 34-2 — delivery не включалась); AC12 backward compat.
        assert Decimal(str(response.data["calculated_total"])) == Decimal("200.00")

        # List endpoint: total_items также корректен для legacy master
        list_url = reverse("orders:order-list")
        list_response = self.client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data["results"][0]["total_items"] == 2

    def test_get_order_detail_success(self, db):
        """Тест получения детальной информации о заказе"""
        self.client.force_authenticate(user=self.user)

        # Создаем заказ
        order = Order.objects.create(
            user=self.user,
            delivery_address="г. Москва, ул. Тестовая, д. 1",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("600.00"),
            delivery_cost=Decimal("500.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            variant=self.variant,
            quantity=1,
            unit_price=Decimal("100.00"),
            product_name=self.product.name,
            product_sku=self.variant.sku,
        )

        url = reverse("orders:order-detail", kwargs={"pk": order.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["order_number"] == order.order_number
        assert response.data["customer_display_name"] == "John Doe"
        assert len(response.data["items"]) == 1
        assert response.data["items"][0]["product_name"] == "Test Product"

    def test_get_order_detail_access_denied(self, db):
        """Тест доступа к чужому заказу"""
        # Создаем другого пользователя
        other_user = User.objects.create_user(
            email="other@example.com",
            password="testpass",
            customer_code="04621",
        )

        # Создаем заказ от имени другого пользователя
        order = Order.objects.create(
            user=other_user,
            delivery_address="г. Москва, ул. Тестовая, д. 1",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("600.00"),
        )

        # Пытаемся получить доступ к заказу
        self.client.force_authenticate(user=self.user)
        url = reverse("orders:order-detail", kwargs={"pk": order.pk})
        response = self.client.get(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_list_user_orders(self, db):
        """Тест получения списка заказов пользователя"""
        self.client.force_authenticate(user=self.user)

        # Создаем несколько заказов с разными временными метками
        import time

        order1 = Order.objects.create(
            user=self.user,
            delivery_address="Адрес 1",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("600.00"),
        )
        time.sleep(0.01)  # Небольшая пауза для различия времени создания
        order2 = Order.objects.create(
            user=self.user,
            delivery_address="Адрес 2",
            delivery_method="pickup",
            payment_method="cash",
            total_amount=Decimal("300.00"),
        )

        url = reverse("orders:order-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2
        # Проверяем сортировку по дате создания (новые первые)
        # order2 создан позже, поэтому должен быть первым
        orders_ids = [order["id"] for order in response.data["results"]]
        assert order2.id in orders_ids
        assert order1.id in orders_ids
        assert orders_ids[0] == order2.id

    def test_delivery_cost_calculation(self, db):
        """Тест расчета стоимости доставки для разных способов"""
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=self.variant.retail_price,
        )

        delivery_methods = [
            ("pickup", Decimal("0")),
            ("courier", Decimal("500")),
            ("post", Decimal("300")),
            ("transport_company", Decimal("1000")),
        ]

        for method, expected_cost in delivery_methods:
            order_data = {
                "delivery_address": "г. Москва, ул. Тестовая, д. 1",
                "delivery_method": method,
                "payment_method": "card",
            }

            url = reverse("orders:order-list")
            response = self.client.post(url, order_data)

            assert response.status_code == status.HTTP_201_CREATED

            order = Order.objects.get(order_number=response.data["order_number"])
            assert order.delivery_cost == expected_cost
            assert order.total_amount == Decimal("100.00") + expected_cost

            # Удаляем заказ для следующей итерации
            order.delete()

            # Воссоздаем товар в корзине
            CartItem.objects.create(
                cart=cart,
                variant=self.variant,
                quantity=1,
                price_snapshot=self.variant.retail_price,
            )

    def test_b2b_minimum_quantity_validation(self, db):
        """Тест валидации минимального количества для B2B пользователей"""
        # Создаем B2B пользователя
        b2b_user = User.objects.create_user(
            email="b2b@example.com",
            password="testpass",
            role="wholesale_level1",
            customer_code="04622",
        )
        self.client.force_authenticate(user=b2b_user)

        # Устанавливаем минимальное количество для заказа
        self.product.min_order_quantity = 5
        self.product.save()

        # Создаем корзину с количеством меньше минимального
        cart = Cart.objects.create(user=b2b_user)
        # Временно сбросим минимальное количество для создания CartItem
        self.product.min_order_quantity = 1
        self.product.save()
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=2,
            price_snapshot=self.variant.retail_price,
        )
        # Теперь установим реальное минимальное количество
        self.product.min_order_quantity = 5
        self.product.save()

        order_data = {
            "delivery_address": "г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "bank_transfer",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Минимальное количество для заказа" in str(response.data)

    def test_filter_orders_by_status(self, db):
        """Тест фильтрации заказов по статусу"""
        self.client.force_authenticate(user=self.user)

        # Create orders with different statuses
        Order.objects.create(
            user=self.user,
            status="pending",
            delivery_address="Pending Order",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
        )
        Order.objects.create(
            user=self.user,
            status="shipped",
            delivery_address="Shipped Order",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("200.00"),
        )

        url = reverse("orders:order-list")

        # Filter by pending
        response = self.client.get(url, {"status": "pending"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["status"] == "pending"

        # Filter by shipped
        response = self.client.get(url, {"status": "shipped"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["status"] == "shipped"

        # Filter by all (no filter)
        response = self.client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 2

    def test_create_order_accepts_customer_field_names(self, db):
        """Regression (Story 34-2 Ninth Follow-up / AC12): POST /api/v1/orders/ принимает
        customer_name/customer_email/customer_phone/notes — поля OrderCreateSerializer.
        Проверяем, что данные корректно сохраняются в Order (synchronization frontend contract).
        """
        self.client.force_authenticate(user=self.user)

        cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=cart,
            variant=self.variant,
            quantity=1,
            price_snapshot=self.variant.retail_price,
        )

        order_data = {
            "delivery_address": "123456, г. Москва, ул. Тестовая, д. 1",
            "delivery_method": "courier",
            "payment_method": "card",
            "customer_name": "Иван Петров",
            "customer_email": "ivan@example.com",
            "customer_phone": "+79001234567",
            "notes": "Позвоните за час до доставки",
        }

        url = reverse("orders:order-list")
        response = self.client.post(url, order_data)

        assert response.status_code == status.HTTP_201_CREATED
        order = Order.objects.get(order_number=response.data["order_number"])
        assert order.customer_name == "Иван Петров"
        assert order.customer_email == "ivan@example.com"
        assert order.customer_phone == "+79001234567"
        assert order.notes == "Позвоните за час до доставки"
        assert order.is_master is True

    def test_list_endpoint_returns_list_serializer_contract(self, db):
        """Regression (Story 34-2 Ninth Follow-up / AC12): GET /api/v1/orders/ возвращает
        набор полей OrderListSerializer — contract test для синхронизации с frontend OrderListItem.
        """
        self.client.force_authenticate(user=self.user)

        Order.objects.create(
            user=self.user,
            delivery_address="Contract Test Address",
            delivery_method="courier",
            payment_method="card",
            total_amount=Decimal("100.00"),
            customer_name="Test User",
            customer_email="test@example.com",
        )

        url = reverse("orders:order-list")
        response = self.client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        item = response.data["results"][0]

        # Обязательные поля OrderListSerializer / frontend OrderListItem
        expected_fields = {
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
        }
        assert expected_fields.issubset(set(item.keys())), f"Отсутствующие поля: {expected_fields - set(item.keys())}"

        # Поля detail-только НЕ должны присутствовать в list
        list_only_contract = {
            "items",
            "subtotal",
            "calculated_total",
            "delivery_cost",
            "discount_amount",
            "can_be_cancelled",
        }
        overlap = list_only_contract.intersection(set(item.keys()))
        assert not overlap, f"List endpoint не должен отдавать detail-поля: {overlap}"

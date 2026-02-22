"""Unit тесты для административного интерфейса заказов."""

from decimal import Decimal

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory, TestCase

from apps.common.models import AuditLog
from apps.orders.admin import OrderAdmin, OrderItemInline
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product
from apps.users.models import User
from tests.factories import ProductFactory


@pytest.mark.django_db
class TestOrderAdminMethods(TestCase):
    """Тесты для кастомных методов OrderAdmin."""

    def setUp(self) -> None:
        self.site = AdminSite()
        self.admin = OrderAdmin(Order, self.site)

    def test_items_count(self) -> None:
        """Тест подсчета количества позиций в заказе."""
        order = Order.objects.create(
            total_amount=Decimal("300.00"),
            delivery_address="Test Address",
            delivery_method="courier",
            payment_method="card",
        )
        # Создаем 3 позиции с разными продуктами через фабрику
        for i in range(3):
            product = ProductFactory(
                name=f"Test Product {i}",
                sku=f"TEST-00{i}",
                retail_price=Decimal("100.00"),
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                variant=product.variants.first(),
                quantity=1,
                unit_price=Decimal("100.00"),
                product_name=product.name,
                product_sku=product.variants.first().sku,
                total_price=Decimal("100.00"),
            )

        self.assertEqual(self.admin.items_count(order), 3)

    def test_total_items_quantity(self) -> None:
        """Тест подсчета общего количества товаров."""
        order = Order.objects.create(
            total_amount=Decimal("300.00"),
            delivery_address="Test Address",
            delivery_method="courier",
            payment_method="card",
        )
        # Создаем 2 позиции с разными продуктами
        product1 = ProductFactory(
            name="Test Product 1",
            sku="TEST-001",
            retail_price=Decimal("100.00"),
        )
        product2 = ProductFactory(
            name="Test Product 2",
            sku="TEST-002",
            retail_price=Decimal("100.00"),
        )

        OrderItem.objects.create(
            order=order,
            product=product1,
            variant=product1.variants.first(),
            quantity=2,
            unit_price=Decimal("100.00"),
            product_name=product1.name,
            product_sku=product1.variants.first().sku,
            total_price=Decimal("200.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=product2,
            variant=product2.variants.first(),
            quantity=3,
            unit_price=Decimal("100.00"),
            product_name=product2.name,
            product_sku=product2.variants.first().sku,
            total_price=Decimal("300.00"),
        )

        self.assertEqual(self.admin.total_items_quantity(order), 5)


@pytest.mark.django_db
class TestOrderItemInline:
    """Тесты для OrderItemInline."""

    def test_inline_model(self) -> None:
        """Проверка модели в инлайне."""
        inline = OrderItemInline(Order, AdminSite())
        assert inline.model == OrderItem

    def test_inline_readonly_fields(self) -> None:
        """Проверка readonly полей в инлайне."""
        inline = OrderItemInline(Order, AdminSite())
        assert "total_price" in inline.readonly_fields


@pytest.mark.django_db
class TestOrderAdminQuerysetOptimization:
    """Тесты оптимизации запросов в OrderAdmin."""

    @pytest.mark.django_db
    def test_n_plus_one_queries_prevention(self, django_assert_max_num_queries) -> None:
        """Тест отсутствия N+1 queries при отображении списка заказов."""
        # Создаем тестовые данные
        user = User.objects.create_user(email=f"user{User.objects.count()}@example.com", password="testpass123")
        product = ProductFactory(
            name="Test Product",
            sku="TEST-001",
            retail_price=Decimal("100.00"),
        )

        # Создаем 5 заказов с позициями
        for i in range(5):
            order = Order.objects.create(
                user=user,
                total_amount=Decimal("100.00"),
                delivery_address="Test",
                delivery_method="courier",
                payment_method="card",
            )
            OrderItem.objects.create(
                order=order,
                product=product,
                variant=product.variants.first(),
                quantity=1,
                unit_price=Decimal("100.00"),
                product_name=product.name,
                product_sku=product.variants.first().sku,
                total_price=Decimal("100.00"),
            )

        site = AdminSite()
        admin = OrderAdmin(Order, site)
        request = RequestFactory().get("/admin/orders/order/")
        request.user = User.objects.create_superuser(email="admin@test.com", password="password")

        # Проверяем количество запросов для получения списка
        # Должно быть фиксированное количество вне зависимости от числа заказов
        with django_assert_max_num_queries(10):
            list(admin.get_queryset(request))

"""
Integration тесты интеграции корзины и заказов
"""

import threading

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, TransactionTestCase
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class CartOrderIntegrationTest(TestCase):
    """Тестирование интеграции корзины и заказов"""

    def setUp(self):
        self.client = APIClient()

        self.user = User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            role="retail",
            customer_code="10001",
        )

        # Создаем товары
        self.category = Category.objects.create(name="Test Category", slug="test-category")
        self.brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        self.product1 = Product.objects.create(
            name="Test Product 1",
            slug="test-product-1",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant1 = ProductVariant.objects.create(
            product=self.product1,
            sku="VAR1",
            onec_id="1C-VAR1",
            retail_price=100.00,
            stock_quantity=10,
            is_active=True,
        )

        self.product2 = Product.objects.create(
            name="Test Product 2",
            slug="test-product-2",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant2 = ProductVariant.objects.create(
            product=self.product2,
            sku="VAR2",
            onec_id="1C-VAR2",
            retail_price=50.00,
            stock_quantity=5,
            is_active=True,
        )

    def test_full_cart_to_order_workflow(self):
        """Полный workflow от корзины до заказа.
        После Story 34-2: items видны через агрегацию из субзаказов.
        """
        self.client.force_authenticate(user=self.user)

        # 1. Добавляем товары в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 2})
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant2.id, "quantity": 1})

        # 2. Проверяем корзину
        cart_response = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_response.data["total_items"], 3)
        expected_total = (100.00 * 2) + (50.00 * 1)  # 250.00
        self.assertEqual(float(cart_response.data["total_amount"]), expected_total)

        # 3. Создаем заказ
        order_data = {
            "delivery_address": "Test Address 123",
            "delivery_method": "courier",
            "payment_method": "card",
            "notes": "Test order",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # 4. Проверяем, что заказ создался правильно
        order_id = order_response.data["id"]
        order_detail_response = self.client.get(f"/api/v1/orders/{order_id}/")

        # items агрегируются из субзаказов через OrderDetailSerializer.get_items()
        self.assertEqual(len(order_detail_response.data["items"]), 2)
        self.assertEqual(order_detail_response.data["total_items"], 3)
        self.assertTrue(order_response.data["is_master"])

        # 5. Проверяем, что корзина очистилась
        cart_after_order = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_after_order.data["total_items"], 0)

        # 6. Проверяем снимок данных в OrderItem (items в субзаказах)
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.items.count(), 0)  # master не содержит direct items
        sub_items = OrderItem.objects.filter(order__parent_order=order)
        self.assertEqual(sub_items.count(), 2)
        for item in sub_items:
            self.assertIsNotNone(item.product_name)
            self.assertIsNotNone(item.product_sku)
            self.assertGreater(item.unit_price, 0)

    def test_order_creation_preserves_cart_prices(self):
        """Создание заказа сохраняет цены из корзины"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Получаем цену из корзины
        cart_response = self.client.get("/api/v1/cart/")
        cart_price = float(cart_response.data["items"][0]["unit_price"])

        # Создаем заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)

        # Проверяем, что цена в заказе соответствует цене из корзины
        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")
        order_price = float(order_detail.data["items"][0]["unit_price"])

        self.assertEqual(cart_price, order_price)

    def test_order_creation_uses_cart_price_snapshot_on_price_change(self):
        """Regression: цена в заказе берётся из snapshot корзины, а не из текущего каталога.

        Сценарий: товар добавлен в корзину по цене 100 руб., затем
        цена в каталоге изменилась до 999 руб. Заказ должен сохранять
        цену snapshot (100 руб.), зафиксированную при добавлении.
        """
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину (snapshot фиксирует retail_price=100)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 2})

        # Изменяем цену в каталоге ПОСЛЕ добавления в корзину
        self.variant1.retail_price = 999.00
        self.variant1.save()

        # Создаём заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        order_id = order_response.data["id"]
        order_detail = self.client.get(f"/api/v1/orders/{order_id}/")
        item = order_detail.data["items"][0]

        # unit_price должен быть snapshot (100.00), а не новой ценой (999.00)
        self.assertEqual(float(item["unit_price"]), 100.00)
        self.assertEqual(float(item["total_price"]), 200.00)  # 100 * 2

        # total_amount мастера тоже по snapshot (без delivery_cost для pickup)
        self.assertEqual(float(order_response.data["total_amount"]), 200.00)

    def test_cart_validation_before_order_creation(self):
        """Валидация корзины перед созданием заказа"""
        self.client.force_authenticate(user=self.user)

        # Пытаемся создать заказ с пустой корзиной
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        self.assertEqual(response.status_code, 400)
        self.assertIn("Корзина пуста", str(response.data))

    def test_stock_validation_during_order_creation(self):
        """Валидация остатков при создании заказа"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 2})

        # Уменьшаем остаток товара
        self.variant1.stock_quantity = 1
        self.variant1.save()

        # Пытаемся создать заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        # Заказ должен быть отклонен из-за недостатка товара
        self.assertEqual(response.status_code, 400)

    def test_transactional_integrity(self):
        """Транзакционная целостность при создании заказа"""
        self.client.force_authenticate(user=self.user)

        # Добавляем товар в корзину
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Получаем начальное количество заказов
        initial_orders_count = Order.objects.count()
        initial_cart_items = CartItem.objects.filter(cart__user=self.user).count()

        # Деактивируем товар (эмуляция ошибки)
        self.product1.is_active = False
        self.product1.save()

        # Пытаемся создать заказ
        order_data = {
            "delivery_address": "Test Address",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        response = self.client.post("/api/v1/orders/", order_data)

        # Заказ должен быть отклонен
        self.assertEqual(response.status_code, 400)

        # Проверяем, что ничего не изменилось
        final_orders_count = Order.objects.count()
        final_cart_items = CartItem.objects.filter(cart__user=self.user).count()

        self.assertEqual(initial_orders_count, final_orders_count)
        self.assertEqual(initial_cart_items, final_cart_items)

    def test_order_item_vat_rate_captured_via_api(self):
        """[AI-Review][Medium] vat_rate снимается при создании заказа через API endpoint (bulk_create path)"""
        from decimal import Decimal

        self.client.force_authenticate(user=self.user)

        # Устанавливаем vat_rate у варианта
        self.variant1.vat_rate = Decimal("5.00")
        self.variant1.save()

        # Добавляем товар в корзину через API
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Создаём заказ через API endpoint
        order_data = {
            "delivery_address": "Ул. Тестовая, 1",
            "delivery_method": "pickup",
            "payment_method": "card",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # После Story 34-2: items находятся в субзаказах
        order_id = order_response.data["id"]
        order = Order.objects.get(id=order_id)
        self.assertTrue(order.is_master)

        sub_items = list(OrderItem.objects.filter(order__parent_order=order))
        self.assertEqual(len(sub_items), 1)
        self.assertEqual(
            sub_items[0].vat_rate,
            Decimal("5.00"),
            "vat_rate должен быть снят из variant при создании заказа через API (bulk_create path)",
        )

    def test_order_item_vat_rate_null_via_api_when_no_variant_vat(self):
        """[AI-Review][Medium] vat_rate остаётся None, если у variant нет vat_rate — проверка через API"""
        self.client.force_authenticate(user=self.user)

        # Убеждаемся, что у варианта нет vat_rate
        self.variant1.vat_rate = None
        self.variant1.save()

        # Добавляем товар в корзину через API
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant1.id, "quantity": 1})

        # Создаём заказ через API endpoint
        order_data = {
            "delivery_address": "Ул. Тестовая, 2",
            "delivery_method": "pickup",
            "payment_method": "cash",
        }
        order_response = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(order_response.status_code, 201)

        # После Story 34-2: items находятся в субзаказах
        order_id = order_response.data["id"]
        order = Order.objects.get(id=order_id)
        self.assertTrue(order.is_master)

        sub_items = list(OrderItem.objects.filter(order__parent_order=order))
        self.assertEqual(len(sub_items), 1)
        self.assertIsNone(
            sub_items[0].vat_rate,
            "vat_rate должен быть None, если у variant нет vat_rate",
        )


@pytest.mark.integration
@pytest.mark.django_db
class VATSplitAPITest(TestCase):
    """API-тесты разбивки заказов по VAT-группам (Story 34-2, Tasks 7.1-7.7)."""

    def setUp(self):
        from decimal import Decimal

        self.client = APIClient()
        self.user = User.objects.create_user(
            email="vat_test@example.com",
            password="testpass123",
            role="retail",
            customer_code="10002",
        )

        self.category = Category.objects.create(name="VAT Category", slug="vat-category")
        self.brand = Brand.objects.create(name="VAT Brand", slug="vat-brand")

        # Товар со ставкой НДС 5%
        self.product_vat5 = Product.objects.create(
            name="Product VAT 5%",
            slug="product-vat-5",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant_vat5 = ProductVariant.objects.create(
            product=self.product_vat5,
            sku="VAT5-001",
            onec_id="1C-VAT5-001",
            retail_price=Decimal("100.00"),
            stock_quantity=10,
            is_active=True,
            vat_rate=Decimal("5.00"),
        )

        # Товар со ставкой НДС 22%
        self.product_vat22 = Product.objects.create(
            name="Product VAT 22%",
            slug="product-vat-22",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant_vat22 = ProductVariant.objects.create(
            product=self.product_vat22,
            sku="VAT22-001",
            onec_id="1C-VAT22-001",
            retail_price=Decimal("200.00"),
            stock_quantity=10,
            is_active=True,
            vat_rate=Decimal("22.00"),
        )

    def _create_order_with_multi_vat_cart(self):
        """Создаёт заказ из мульти-VAT корзины, возвращает response."""
        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 2})
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat22.id, "quantity": 1})
        return self.client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Test Address",
                "delivery_method": "pickup",
                "payment_method": "card",
            },
        )

    def test_multi_vat_creates_master_and_two_sub_orders(self):
        """7.1: POST /orders/ с мульти-VAT → 201, 1 master + 2 sub-orders в БД, items в ответе."""
        response = self._create_order_with_multi_vat_cart()
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_master"])

        master = Order.objects.get(id=response.data["id"])
        sub_orders = list(Order.objects.filter(parent_order=master))
        self.assertEqual(len(sub_orders), 2)

        vat_groups = {sub.vat_group for sub in sub_orders}
        from decimal import Decimal

        self.assertIn(Decimal("5.00"), vat_groups)
        self.assertIn(Decimal("22.00"), vat_groups)

        # Ответ содержит все позиции агрегировано
        self.assertEqual(len(response.data["items"]), 2)

    def test_multi_vat_master_calculated_total_includes_delivery(self):
        """AC4/AC11: API response мастера — calculated_total = items всех субзаказов + delivery_cost."""
        from decimal import Decimal

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 2})
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat22.id, "quantity": 1})

        # delivery_method=courier → delivery_cost=500
        response = self.client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Test Address",
                "delivery_method": "courier",
                "payment_method": "card",
            },
        )
        self.assertEqual(response.status_code, 201)

        # 100*2 + 200*1 + 500 = 900
        expected_total = Decimal("900.00")
        self.assertEqual(Decimal(str(response.data["calculated_total"])), expected_total)
        self.assertEqual(
            Decimal(str(response.data["calculated_total"])),
            Decimal(str(response.data["total_amount"])),
            "calculated_total должен совпадать с total_amount мастера",
        )

        # Повторная проверка через GET retrieve
        master_id = response.data["id"]
        retrieve_response = self.client.get(f"/api/v1/orders/{master_id}/")
        self.assertEqual(retrieve_response.status_code, 200)
        self.assertEqual(
            Decimal(str(retrieve_response.data["calculated_total"])),
            expected_total,
        )

    def test_list_returns_only_masters(self):
        """7.2: GET /orders/ возвращает только мастер-заказы."""
        self._create_order_with_multi_vat_cart()

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/orders/")
        self.assertEqual(response.status_code, 200)

        results = response.data["results"] if "results" in response.data else response.data
        for order_data in results:
            self.assertTrue(order_data["is_master"])

    def test_list_master_total_items_aggregates_from_sub_orders(self):
        """AC12/AC13: total_items мастер-заказа в list endpoint корректно агрегируется из субзаказов.

        Без агрегации Order.total_items возвращал бы 0 (у мастера нет direct items),
        что ломает клиентский list-contract после VAT-split.
        """
        response_create = self._create_order_with_multi_vat_cart()
        self.assertEqual(response_create.status_code, 201)

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/orders/")
        self.assertEqual(response.status_code, 200)

        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        # корзина: variant_vat5 x2 + variant_vat22 x1 → 3 позиции суммарно
        self.assertEqual(results[0]["total_items"], 3)

    def test_retrieve_sub_order_returns_404(self):
        """7.3: GET /orders/<sub_order_id>/ → 404."""
        self._create_order_with_multi_vat_cart()

        master = Order.objects.filter(user=self.user, is_master=True).first()
        sub = Order.objects.filter(parent_order=master).first()

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/orders/{sub.id}/")
        self.assertEqual(response.status_code, 404)

    def test_cancel_master_cascades_to_sub_orders(self):
        """7.4: POST /orders/<master_id>/cancel/ → мастер + субзаказы в статусе cancelled."""
        self._create_order_with_multi_vat_cart()

        master = Order.objects.filter(user=self.user, is_master=True).first()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(f"/api/v1/orders/{master.id}/cancel/")
        self.assertEqual(response.status_code, 200)

        master.refresh_from_db()
        self.assertEqual(master.status, "cancelled")

        sub_statuses = list(Order.objects.filter(parent_order=master).values_list("status", flat=True))
        self.assertTrue(all(s == "cancelled" for s in sub_statuses))

    def test_cancel_sub_order_returns_404(self):
        """7.5: POST /orders/<sub_order_id>/cancel/ → 404."""
        self._create_order_with_multi_vat_cart()

        master = Order.objects.filter(user=self.user, is_master=True).first()
        sub = Order.objects.filter(parent_order=master).first()

        self.client.force_authenticate(user=self.user)
        response = self.client.post(f"/api/v1/orders/{sub.id}/cancel/")
        self.assertEqual(response.status_code, 404)

    def test_api_rollback_on_concurrent_stock_depletion(self):
        """Task 6.6 (API): conditional update ловит race condition при checkout.

        Симулируется, что параллельный покупатель забрал stock между валидацией и
        списанием остатков (вешаем pre_save signal, который обнуляет stock в момент
        создания мастера). Ожидаем 400 + полный rollback (ни мастер, ни субзаказы
        не сохранены, корзина не очищена).
        """
        from django.db.models.signals import pre_save

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 2})

        initial_orders = Order.objects.count()
        initial_cart_items = CartItem.objects.filter(cart__user=self.user).count()
        variant_id = self.variant_vat5.id

        def deplete_stock(sender, instance, **kwargs):
            # Имитируем параллельный checkout: когда создаётся master (pk=None, is_master=True),
            # сторонний процесс обнуляет stock ДО того, как сервис выполнит conditional update.
            if getattr(instance, "is_master", False) and instance.pk is None:
                ProductVariant.objects.filter(pk=variant_id).update(stock_quantity=0)

        pre_save.connect(deplete_stock, sender=Order)
        try:
            response = self.client.post(
                "/api/v1/orders/",
                {
                    "delivery_address": "Test Address",
                    "delivery_method": "pickup",
                    "payment_method": "card",
                },
            )
        finally:
            pre_save.disconnect(deplete_stock, sender=Order)

        self.assertEqual(response.status_code, 400)
        # Rollback: ни мастер, ни субзаказы не созданы, корзина не очищена
        self.assertEqual(Order.objects.count(), initial_orders)
        self.assertEqual(
            CartItem.objects.filter(cart__user=self.user).count(),
            initial_cart_items,
        )

    def test_homogeneous_cart_regression(self):
        """7.6: Регрессия — однородная корзина (без vat_rate) работает как раньше.
        Клиентский контракт не сломан: items в ответе, корзина очищена.
        """
        self.client.force_authenticate(user=self.user)

        # Используем вариант без vat_rate (из setUp базового теста)
        category = Category.objects.create(name="Regression Cat", slug="regression-cat")
        brand = Brand.objects.create(name="Regression Brand", slug="regression-brand")
        product = Product.objects.create(
            name="Regression Product",
            slug="regression-product",
            category=category,
            brand=brand,
            is_active=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="REG-001",
            onec_id="1C-REG-001",
            retail_price=100.00,
            stock_quantity=10,
            is_active=True,
        )

        self.client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 1})

        response = self.client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Test",
                "delivery_method": "pickup",
                "payment_method": "cash",
            },
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["is_master"])
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["quantity"], 1)

        # Корзина очищена
        cart_response = self.client.get("/api/v1/cart/")
        self.assertEqual(cart_response.data["total_items"], 0)

    def test_list_serializer_exposes_vat_group(self):
        """Fifth follow-up: list endpoint должен отдавать поле vat_group у мастера.

        Клиентский контракт Story 34-1 добавил vat_group в OrderListSerializer;
        AC12 Story 34-2 требует сохранения этого поля в list-ответе.
        """
        self._create_order_with_multi_vat_cart()

        self.client.force_authenticate(user=self.user)
        response = self.client.get("/api/v1/orders/")
        self.assertEqual(response.status_code, 200)

        results = response.data["results"] if "results" in response.data else response.data
        self.assertEqual(len(results), 1)
        self.assertIn("vat_group", results[0])
        # У мастера vat_group=None (VAT живёт на субзаказах)
        self.assertIsNone(results[0]["vat_group"])

    def test_create_response_exposes_vat_group(self):
        """Fifth follow-up: POST /orders/ response должен содержать vat_group."""
        response = self._create_order_with_multi_vat_cart()
        self.assertEqual(response.status_code, 201)
        self.assertIn("vat_group", response.data)
        self.assertIsNone(response.data["vat_group"])

    def test_retrieve_response_exposes_vat_group(self):
        """Fifth follow-up: GET /orders/<id>/ должен содержать vat_group у мастера."""
        response_create = self._create_order_with_multi_vat_cart()
        master_id = response_create.data["id"]

        self.client.force_authenticate(user=self.user)
        response = self.client.get(f"/api/v1/orders/{master_id}/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("vat_group", response.data)
        self.assertIsNone(response.data["vat_group"])

    def test_cancel_atomic_rollback_on_sub_orders_failure(self):
        """Fifth follow-up: cascade cancel должен быть атомарным.

        Если sub_orders.update() падает, мастер не должен остаться в cancelled —
        transaction.atomic в OrderViewSet.cancel() откатывает master.save().
        """
        from unittest.mock import patch

        from django.db.models.query import QuerySet

        self._create_order_with_multi_vat_cart()
        master = Order.objects.filter(user=self.user, is_master=True).first()
        self.assertEqual(master.status, "pending")

        self.client.force_authenticate(user=self.user)

        original_update = QuerySet.update

        def failing_update(self, *args, **kwargs):
            if self.model is Order and kwargs.get("status") == "cancelled":
                raise Exception("Simulated DB error on cascade cancel")
            return original_update(self, *args, **kwargs)

        # Отключаем raise_request_exception, чтобы получить Response вместо исключения
        self.client.raise_request_exception = False

        with patch.object(QuerySet, "update", failing_update):
            response = self.client.post(f"/api/v1/orders/{master.id}/cancel/")

        # Endpoint должен вернуть ошибку (не 200 OK)
        self.assertGreaterEqual(response.status_code, 500)

        master.refresh_from_db()
        # При откате транзакции master остаётся в исходном статусе
        self.assertEqual(master.status, "pending")
        # Субзаказы тоже не затронуты
        sub_statuses = list(Order.objects.filter(parent_order=master).values_list("status", flat=True))
        self.assertTrue(all(s != "cancelled" for s in sub_statuses))

    def test_order_creation_discount_zeroed_by_server_security_fix(self):
        """Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        клиентский discount_amount игнорируется сервером (promo-система не реализована).

        master.discount_amount = 0 (не переданные 50).
        master.total_amount = items + delivery - 0 = 400.
        Субзаказы discount_amount=0.
        """
        from decimal import Decimal

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 2})  # 100*2=200
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat22.id, "quantity": 1})  # 200*1=200

        response = self.client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Test Address",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "50.00",  # будет проигнорирован сервером
            },
        )
        self.assertEqual(response.status_code, 201)

        master = Order.objects.get(id=response.data["id"])
        # discount zeroed by server
        self.assertEqual(master.discount_amount, Decimal("0.00"))
        # total_amount = 200 + 200 + 0 (pickup) - 0 = 400
        self.assertEqual(master.total_amount, Decimal("400.00"))
        # API response отражает server-override
        self.assertEqual(Decimal(str(response.data["discount_amount"])), Decimal("0.00"))

        sub_orders = list(Order.objects.filter(parent_order=master))
        self.assertEqual(len(sub_orders), 2)
        for sub in sub_orders:
            self.assertEqual(sub.discount_amount, Decimal("0.00"))

    def test_calculated_total_equals_total_amount_discount_zeroed_in_api_response(self):
        """AC4/AC11 regression + Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        API response: calculated_total == total_amount; discount_amount == 0 (server override).
        Клиентское discount_amount=75 игнорируется — promo-система не реализована.
        """
        from decimal import Decimal

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 2})  # 100*2=200
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat22.id, "quantity": 1})  # 200*1=200

        # items_sum=400, delivery pickup=0, discount zeroed → total_amount = 400
        response = self.client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Test Address",
                "delivery_method": "pickup",
                "payment_method": "card",
                "discount_amount": "75.00",  # будет проигнорирован сервером
            },
        )
        self.assertEqual(response.status_code, 201)

        total_amount = Decimal(str(response.data["total_amount"]))
        calculated_total = Decimal(str(response.data["calculated_total"]))
        discount_amount = Decimal(str(response.data["discount_amount"]))

        self.assertEqual(total_amount, Decimal("400.00"))
        self.assertEqual(discount_amount, Decimal("0.00"))
        self.assertEqual(
            calculated_total,
            total_amount,
            msg=f"calculated_total={calculated_total} != total_amount={total_amount}: "
            "serializer calculated_total должен совпадать с total_amount",
        )

    def test_double_submit_same_cart_creates_only_one_order(self):
        """Security fix [Story 34-2, Twenty-Seventh Follow-up, High]:
        Повторный POST /api/v1/orders/ из той же (уже пустой) корзины возвращает 400.

        После первого успешного checkout корзина очищена — select_for_update() + cart.clear()
        делают повторный запрос невозможным (корзина пуста).
        В БД остаётся ровно один мастер-заказ.
        """
        from decimal import Decimal

        self.client.force_authenticate(user=self.user)
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat5.id, "quantity": 1})
        self.client.post("/api/v1/cart/items/", {"variant_id": self.variant_vat22.id, "quantity": 1})

        order_data = {
            "delivery_address": "Test Double Submit",
            "delivery_method": "pickup",
            "payment_method": "card",
        }

        # Первый запрос — создаёт заказ
        response1 = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(response1.status_code, 201, f"First order failed: {response1.data}")

        master_count_after_first = Order.objects.filter(is_master=True).count()
        self.assertEqual(master_count_after_first, 1)

        # Второй запрос — корзина уже пуста, должен вернуть 400
        response2 = self.client.post("/api/v1/orders/", order_data)
        self.assertEqual(response2.status_code, 400, f"Expected 400 on double submit, got {response2.status_code}")

        # В БД остаётся ровно один мастер-заказ
        master_count_final = Order.objects.filter(is_master=True).count()
        self.assertEqual(master_count_final, 1, "Double submit created duplicate master order")


@pytest.mark.integration
class ConcurrentCartCheckoutTests(TransactionTestCase):
    """Тесты конкурентного double-submit одной корзины с реальными транзакциями.

    TransactionTestCase используется вместо TestCase, так как select_for_update()
    требует реальных commit/rollback транзакций для корректной работы между потоками.
    """

    def setUp(self):
        from decimal import Decimal

        self.user = User.objects.create_user(
            email="concurrent_checkout@test.com",
            password="testpass123",
            role="retail",
            customer_code="10003",
        )
        self.category = Category.objects.create(name="Concurrent Cat", slug="concurrent-cat")
        self.brand = Brand.objects.create(name="Concurrent Brand", slug="concurrent-brand")

        self.product = Product.objects.create(
            name="Concurrent Product",
            slug="concurrent-product",
            category=self.category,
            brand=self.brand,
            is_active=True,
        )
        self.variant = ProductVariant.objects.create(
            product=self.product,
            sku="CONC-001",
            onec_id="1C-CONC-001",
            retail_price=Decimal("100.00"),
            stock_quantity=50,
            is_active=True,
            vat_rate=Decimal("5.00"),
        )

    def _fill_cart(self):
        """Добавляет товар в корзину пользователя через API."""
        client = APIClient()
        client.force_authenticate(user=self.user)
        client.post("/api/v1/cart/items/", {"variant_id": self.variant.id, "quantity": 1})

    def test_concurrent_double_submit_creates_only_one_order(self):
        """[Medium] Два параллельных checkout-запроса на одну корзину создают ровно один мастер.

        Оба потока запускаются одновременно (Barrier) и конкурируют за блокировку корзины.
        select_for_update() в OrderCreateService.create() гарантирует, что второй поток
        увидит пустую корзину после того, как первый очистит её, и получит 400.
        Тест явно проверяет, что проигравший поток возвращает 400, а не 500 —
        это подтверждает, что select_for_update() отрабатывает без исключений сервера.
        """
        self._fill_cart()

        order_data = {
            "delivery_address": "Concurrent Test Address",
            "delivery_method": "pickup",
            "payment_method": "card",
        }

        results = []
        errors = []
        results_lock = threading.Lock()
        barrier = threading.Barrier(2, timeout=10)

        def checkout():
            from django.db import connections

            client = APIClient()
            client.force_authenticate(user=self.user)
            barrier.wait()  # Оба потока стартуют одновременно
            try:
                response = client.post("/api/v1/orders/", order_data)
                with results_lock:
                    results.append(response.status_code)
            except Exception as exc:
                with results_lock:
                    errors.append(str(exc))
            finally:
                # Явно закрываем DB-соединение потока, чтобы не блокировать teardown
                for conn in connections.all():
                    conn.close()

        t1 = threading.Thread(target=checkout)
        t2 = threading.Thread(target=checkout)
        t1.start()
        t2.start()
        t1.join(timeout=30)
        t2.join(timeout=30)

        # Ошибки внутри потоков означают проблемы тестовой инфраструктуры, не бизнес-логики
        self.assertEqual(errors, [], f"Thread(s) raised unexpected exceptions: {errors}")
        self.assertEqual(len(results), 2, f"Not all threads completed: results={results}, errors={errors}")
        self.assertIn(201, results, f"No successful checkout: {results}")

        # Проигравший поток ДОЛЖЕН вернуть 400, а не 500:
        # 500 означал бы, что select_for_update() не сработал и транзакция упала с ошибкой сервера.
        non_201 = [r for r in results if r != 201]
        self.assertEqual(len(non_201), 1, f"Expected exactly one non-201 result, got: {results}")
        self.assertEqual(
            non_201[0],
            400,
            f"Losing thread returned HTTP {non_201[0]} instead of expected 400. "
            f"Results: {results}. "
            "A 500 indicates select_for_update() did not prevent double-submit cleanly.",
        )

        master_count = Order.objects.filter(is_master=True, user=self.user).count()
        self.assertEqual(
            master_count,
            1,
            f"Expected 1 master order, got {master_count}. "
            f"Results: {results}. "
            "select_for_update() may not be preventing double-checkout.",
        )

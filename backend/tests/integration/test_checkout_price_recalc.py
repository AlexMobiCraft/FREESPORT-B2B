"""
Пересчёт цены позиций при оформлении заказа (spec-checkout-price-recalc).

Цена каждой позиции считается заново в момент оформления. Разошлась со снимком
корзины — заказа нет, снимки обновлены, ответ 409 `prices_changed` с изменившимися
строками и новой суммой; нулевая цена — 400 `price_unavailable`, корзина не тронута.
"""

import threading
import time
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.db import connection, connections, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.models import CustomerCodeSequence, CustomerOrderSequence, Order, OrderItem
from apps.products.factories import ProductVariantFactory
from apps.products.models import PriceType
from apps.products.services import promo
from tests.conftest import get_unique_suffix

User = get_user_model()

ORDERS_URL = "/api/v1/orders/"
RETAIL_ORDER = {
    "delivery_address": "г. Москва, ул. Тестовая, д. 1",
    "delivery_method": "pickup",
    "payment_method": "card",
}
B2B_ORDER = {**RETAIL_ORDER, "payment_method": "bank_transfer"}


def _user(role="retail", is_verified=True):
    return User.objects.create_user(
        email=f"recalc-{get_unique_suffix()}@example.com",
        password="testpass123",
        role=role,
        is_verified=is_verified,
    )


def _variant(**prices):
    """Вариант с явными ценами: незаданные цены ролей пусты, акции нет."""
    defaults = {
        "retail_price": Decimal("1000.00"),
        "opt1_price": None,
        "opt2_price": None,
        "opt3_price": None,
        "opt4_price": None,
        "trainer_price": None,
        "federation_price": None,
        "promo_price": None,
        "stock_quantity": 100,
        "reserved_quantity": 0,
    }
    return ProductVariantFactory(**{**defaults, **prices})


def _add(cart, variant, snapshot, quantity=1):
    return CartItem.objects.create(cart=cart, variant=variant, quantity=quantity, price_snapshot=Decimal(snapshot))


def _snapshot(item):
    return CartItem.objects.get(pk=item.pk).price_snapshot


@pytest.fixture
def api():
    return APIClient()


@pytest.mark.django_db
class TestCheckoutPriceRecalc:
    def _post(self, api, user, data=RETAIL_ORDER):
        api.force_authenticate(user=user)
        return api.post(ORDERS_URL, data, format="json")

    def test_unchanged_prices_create_order(self, api):
        user = _user()
        cart = Cart.objects.create(user=user)
        _add(cart, _variant(retail_price=Decimal("1000.00")), "1000.00", quantity=2)

        response = self._post(api, user)

        assert response.status_code == 201, response.data
        master = Order.objects.get(pk=response.data["id"])
        assert master.total_amount == Decimal("2000.00")
        item = OrderItem.objects.get(order__parent_order=master)
        assert (item.unit_price, item.total_price) == (Decimal("1000.00"), Decimal("2000.00"))

    def test_promo_ended_returns_conflict_with_role_price(self, api):
        user = _user("wholesale_level2")
        cart = Cart.objects.create(user=user)
        variant = _variant(opt2_price=Decimal("900.00"), promo_price=Decimal("700.00"))
        item = _add(cart, variant, "700.00", quantity=2)
        # Акцию снимает только импорт 1С: полное save() поле не пишет
        variant.promo_price = None
        variant.save(update_fields=["promo_price"])

        response = self._post(api, user, B2B_ORDER)

        assert response.status_code == 409
        assert response.data["code"] == "prices_changed"
        assert response.data["detail"] == "Цены изменились. Проверьте сумму заказа"
        assert response.data["items"] == [
            {
                "variant_id": variant.pk,
                "product_name": variant.product.name,
                "quantity": 2,
                "old_price": "700.00",
                "new_price": "900.00",
            }
        ]
        assert response.data["items_total"] == "1800.00"
        assert _snapshot(item) == Decimal("900.00")
        assert not Order.objects.filter(user=user).exists()

    def test_role_price_changed_returns_conflict(self, api):
        user = _user("wholesale_level2")
        cart = Cart.objects.create(user=user)
        variant = _variant(opt2_price=Decimal("900.00"))
        item = _add(cart, variant, "900.00")
        variant.opt2_price = Decimal("950.00")
        variant.save()

        response = self._post(api, user, B2B_ORDER)

        assert response.status_code == 409
        assert _snapshot(item) == Decimal("950.00")
        assert not Order.objects.filter(user=user).exists()

    def test_price_decrease_after_verification_also_conflicts(self, api):
        """B2B верифицирован после добавления в корзину: цена «Опт» ниже снимка"""
        user = _user("wholesale_level1", is_verified=False)
        cart = Cart.objects.create(user=user)
        variant = _variant(retail_price=Decimal("1000.00"), opt1_price=Decimal("800.00"))
        item = _add(cart, variant, "1000.00")
        user.is_verified = True
        user.save(update_fields=["is_verified"])

        response = self._post(api, user, B2B_ORDER)

        assert response.status_code == 409
        assert response.data["items"][0]["new_price"] == "800.00"
        assert _snapshot(item) == Decimal("800.00")

    def test_retry_after_conflict_creates_order_at_new_price(self, api):
        user = _user()
        cart = Cart.objects.create(user=user)
        variant = _variant(retail_price=Decimal("1200.00"))
        _add(cart, variant, "1000.00", quantity=3)

        assert self._post(api, user).status_code == 409
        response = self._post(api, user)

        assert response.status_code == 201, response.data
        master = Order.objects.get(pk=response.data["id"])
        assert master.total_amount == Decimal("3600.00")
        item = OrderItem.objects.get(order__parent_order=master)
        assert (item.unit_price, item.total_price) == (Decimal("1200.00"), Decimal("3600.00"))
        assert not CartItem.objects.filter(cart=cart).exists()

    def test_equal_role_and_promo_price_creates_order(self, api):
        user = _user("wholesale_level2")
        cart = Cart.objects.create(user=user)
        _add(cart, _variant(opt2_price=Decimal("800.00"), promo_price=Decimal("800.00")), "800.00")

        response = self._post(api, user, B2B_ORDER)

        assert response.status_code == 201, response.data
        assert Order.objects.get(pk=response.data["id"]).total_amount == Decimal("800.00")

    def test_zero_price_is_rejected_and_cart_untouched(self, api):
        user = _user()
        cart = Cart.objects.create(user=user)
        variant = _variant(retail_price=Decimal("1000.00"))
        item = _add(cart, variant, "1000.00")
        variant.retail_price = Decimal("0.00")
        variant.save()

        response = self._post(api, user)

        assert response.status_code == 400
        assert response.data == {
            "code": "price_unavailable",
            "detail": f"{variant.product.name} сейчас недоступен для заказа",
        }
        assert _snapshot(item) == Decimal("1000.00")
        assert not Order.objects.filter(user=user).exists()

    @pytest.mark.parametrize("zero_first", [True, False], ids=["zero-first", "zero-after-positive"])
    def test_zero_price_wins_over_price_change(self, api, zero_first):
        """
        Одна позиция без цены, другая подорожала: 400, снимки обеих не тронуты.

        Сервис обходит позиции по `pk`; вариант «ноль после положительной цены»
        ловит проверку только первой позиции.
        """
        user = _user()
        cart = Cart.objects.create(user=user)
        zero = _variant(retail_price=Decimal("500.00"))
        pricier = _variant(retail_price=Decimal("1000.00"))
        if zero_first:
            zero_item = _add(cart, zero, "500.00")
            pricier_item = _add(cart, pricier, "1000.00")
        else:
            pricier_item = _add(cart, pricier, "1000.00")
            zero_item = _add(cart, zero, "500.00")
        zero.retail_price = Decimal("0.00")
        zero.save()
        pricier.retail_price = Decimal("1100.00")
        pricier.save()

        response = self._post(api, user)

        assert response.status_code == 400
        assert response.data["code"] == "price_unavailable"
        assert _snapshot(zero_item) == Decimal("500.00")
        assert _snapshot(pricier_item) == Decimal("1000.00")

    def test_two_of_three_changed(self, api, django_capture_on_commit_callbacks):
        """AC: в `items` ровно две разошедшиеся позиции, сумма — по всем трём, писем нет"""
        user = _user()
        cart = Cart.objects.create(user=user)
        up = _variant(retail_price=Decimal("1000.00"))
        down = _variant(retail_price=Decimal("2000.00"))
        same = _variant(retail_price=Decimal("300.00"))
        up_item = _add(cart, up, "1000.00", quantity=2)
        down_item = _add(cart, down, "2000.00")
        same_item = _add(cart, same, "300.00", quantity=3)
        up.retail_price = Decimal("1100.00")
        up.save()
        down.retail_price = Decimal("1500.00")
        down.save()

        with patch("apps.orders.tasks.send_order_confirmation_to_customer") as customer, patch(
            "apps.orders.tasks.send_order_notification_email"
        ) as recipients:
            with django_capture_on_commit_callbacks(execute=True):
                response = self._post(api, user)

        assert response.status_code == 409
        # Список целиком: длина, отсутствие дублей и все поля строки.
        rows = sorted((dict(row) for row in response.data["items"]), key=lambda row: row["variant_id"])
        assert rows == sorted(
            [
                {
                    "variant_id": up.pk,
                    "product_name": up.product.name,
                    "quantity": 2,
                    "old_price": "1000.00",
                    "new_price": "1100.00",
                },
                {
                    "variant_id": down.pk,
                    "product_name": down.product.name,
                    "quantity": 1,
                    "old_price": "2000.00",
                    "new_price": "1500.00",
                },
            ],
            key=lambda row: row["variant_id"],
        )
        # 1100 × 2 + 1500 × 1 + 300 × 3
        assert response.data["items_total"] == "4600.00"
        assert _snapshot(up_item) == Decimal("1100.00")
        assert _snapshot(down_item) == Decimal("1500.00")
        assert _snapshot(same_item) == Decimal("300.00")
        assert not Order.objects.filter(user=user).exists()
        customer.delay.assert_not_called()
        recipients.delay.assert_not_called()

    def test_conflict_does_not_consume_order_number(self, api):
        """409 не трогает счётчики номеров; успешный повтор расходует ровно один номер"""
        user = _user()
        cart = Cart.objects.create(user=user)
        _add(cart, _variant(retail_price=Decimal("1200.00")), "1000.00")
        code_counter_before = CustomerCodeSequence.objects.filter(pk=1).values_list("last_value", flat=True).first()

        assert self._post(api, user).status_code == 409

        user.refresh_from_db()
        assert not user.customer_code
        assert (
            CustomerCodeSequence.objects.filter(pk=1).values_list("last_value", flat=True).first()
            == code_counter_before
        )
        assert not CustomerOrderSequence.objects.exists()

        response = self._post(api, user)

        assert response.status_code == 201, response.data
        user.refresh_from_db()
        year = timezone.localdate().year
        counter = CustomerOrderSequence.objects.get()
        assert (counter.customer_code, counter.year, counter.last_sequence) == (user.customer_code, year, 1)
        assert Order.objects.get(pk=response.data["id"]).order_number == f"{user.customer_code}{str(year)[-2:]}001"


class _BackgroundCheckout:
    """
    Оформление заказа из второго соединения PostgreSQL.

    `start()` возвращается, когда запрос завершился или встал в очередь на
    блокировку, — без угадывания задержек.
    """

    def __init__(self, user, data):
        self.user = user
        self.data = data
        self.pid: int | None = None
        self.outcome: dict = {}
        self.ready = threading.Event()
        # daemon: поток, зависший на блокировке после проваленной проверки,
        # не держит процесс pytest.
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                self.pid = cursor.fetchone()[0]
            self.ready.set()
            client = APIClient()
            client.force_authenticate(user=self.user)
            self.outcome["response"] = client.post(ORDERS_URL, self.data, format="json")
        except BaseException as exc:  # noqa: BLE001 — исключение возвращается в тест
            self.outcome["error"] = exc
        finally:
            self.ready.set()
            connections.close_all()

    def _waits_for_lock(self) -> bool:
        with connection.cursor() as cursor:
            # Статистика активности кэшируется на транзакцию — сбросить снимок.
            cursor.execute("SELECT pg_stat_clear_snapshot()")
            cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [self.pid])
            row = cursor.fetchone()
        return bool(row) and row[0] == "Lock"

    def start(self) -> bool:
        """True — запрос ждёт блокировку, False — успел завершиться."""
        self.thread.start()
        assert self.ready.wait(timeout=10), "второе соединение не открылось"
        deadline = time.monotonic() + 10
        while self.thread.is_alive() and time.monotonic() < deadline:
            if self._waits_for_lock():
                return True
            time.sleep(0.01)
        assert not self.thread.is_alive(), "оформление не завершилось и не ждёт блокировку"
        return False

    def join(self):
        self.thread.join(timeout=30)
        assert not self.thread.is_alive(), "оформление зависло"
        if "error" in self.outcome:
            raise self.outcome["error"]
        return self.outcome["response"]


@pytest.mark.django_db(transaction=True)
class TestCheckoutWaitsForPromoReset:
    def test_checkout_waits_for_promo_reset_and_reads_new_prices(self):
        """
        Сброс акции идёт в другом соединении: оформление ждёт его коммита и видит
        цену без акции. Без общей блокировки оно прочитало бы ещё не сброшенную
        акцию и создало заказ по ней.
        """
        promo_type = PriceType.objects.create(
            onec_id=f"promo-{get_unique_suffix()}",
            onec_name="АКЦИЯ НОЯБРЬ-26",
            product_field="promo_price",
            is_active=True,
        )
        user = _user()
        cart = Cart.objects.create(user=user)
        variant = _variant(retail_price=Decimal("1000.00"), promo_price=Decimal("700.00"))
        item = _add(cart, variant, "700.00", quantity=2)
        checkout = _BackgroundCheckout(user, RETAIL_ORDER)

        with transaction.atomic():
            assert promo.deactivate_promo(promo_type) is True
            assert checkout.start(), "оформление не ждало сброса акции"

        response = checkout.join()

        assert response.status_code == 409, response.data
        assert response.data["items"] == [
            {
                "variant_id": variant.pk,
                "product_name": variant.product.name,
                "quantity": 2,
                "old_price": "700.00",
                "new_price": "1000.00",
            }
        ]
        assert _snapshot(item) == Decimal("1000.00")
        assert not Order.objects.filter(user=user).exists()

"""
Тест-сторож утечки оптовых цен через публичный каталог.

Стори `security-wholesale-price-visibility`, AC7. Сторож формулируется по
всем ключам вида `opt*_price`, а не перечислением трёх имён, — чтобы
`opt4_price` (стори 39.3) и любые будущие уровни попадали под проверку
автоматически.

Два условия, без которых сторож проходит вхолостую:

1. Фикстура заполняет НЕнулевым значением **каждое** поле из
   `WHOLESALE_PRICE_FIELDS`. Пустая цена даёт тот же `0.0`, что и
   закрытая гейтом, — на пустом поле утечку не отличить от нормы.
2. Набор `opt*_price`-ключей в ответе сверяется с `WHOLESALE_PRICE_FIELDS`,
   а не просто «список не пуст». Иначе удаление ключей из ответа
   (отклонённый вариант A) сделает `all(...)` истинным на пустом списке.

Если этот файл начал падать после снятия гейта в `to_representation` —
это не «устаревший тест», а сработавшая защита: оптовая ценовая сетка
снова уходит анонимам (см. `tech-debt.md` п. 18).
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.orders.models import OrderItem
from apps.products.models import Brand, Category, Product, ProductVariant
from apps.products.pricing_policy import WHOLESALE_PRICE_FIELDS
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

User = get_user_model()

RETAIL_PRICE = Decimal("1000.00")

# Каждое гейтируемое поле — с НЕнулевой ценой (см. условие 1 в docstring модуля).
# Добавили новый уровень в WHOLESALE_PRICE_FIELDS — добавьте цену и сюда;
# рассинхрон ловит test_fixture_fills_every_gated_field.
WHOLESALE_PRICES = {
    "opt1_price": Decimal("900.00"),
    "opt2_price": Decimal("800.00"),
    "opt3_price": Decimal("700.00"),
    "opt4_price": Decimal("600.00"),
}

OPT1_PRICE = WHOLESALE_PRICES["opt1_price"]
OPT2_PRICE = WHOLESALE_PRICES["opt2_price"]
OPT3_PRICE = WHOLESALE_PRICES["opt3_price"]

# Роли из AC7 и AC2, которым оптовая сетка не видна ни при каких условиях.
# None — анонимный запрос; кортеж — (role, is_verified).
UNAUTHORIZED_ROLES = [
    pytest.param(None, id="anonymous"),
    pytest.param(("retail", True), id="retail"),
    pytest.param(("unregistered", False), id="unregistered"),
    pytest.param(("wholesale_level1", False), id="unverified-wholesale1"),
    pytest.param(("wholesale_level3", False), id="unverified-wholesale3"),
    pytest.param(("trainer", False), id="unverified-trainer"),
]


def _wholesale_keys(payload: dict) -> set[str]:
    """Все ключи вида opt*_price, фактически присутствующие в ответе"""
    return {key for key in payload if key.startswith("opt") and key.endswith("_price")}


def _assert_wholesale_hidden(payload: dict, where: str) -> None:
    """Ключи оптовых цен на месте (вариант B), но все значения нулевые"""
    keys = _wholesale_keys(payload)
    assert keys == set(WHOLESALE_PRICE_FIELDS), (
        f"{where}: набор оптовых ключей ответа {sorted(keys)} разошёлся с политикой "
        f"{sorted(WHOLESALE_PRICE_FIELDS)}. Вариант B требует, чтобы ключи оставались "
        f"в ответе (required в openapi.yaml), а гейт закрывал каждое поле."
    )
    leaked = {key: payload[key] for key in keys if float(payload[key] or 0) != 0}
    assert not leaked, f"{where}: утечка оптовых цен: {leaked}"


def _assert_wholesale_visible(payload: dict, where: str) -> None:
    """Обратная сторона гейта: верифицированный B2B видит сетку целиком"""
    keys = _wholesale_keys(payload)
    assert keys == set(WHOLESALE_PRICE_FIELDS), f"{where}: набор оптовых ключей {sorted(keys)} неполон"
    for field, expected in WHOLESALE_PRICES.items():
        assert float(payload[field]) == float(expected), f"{where}: {field} = {payload[field]}, ожидалось {expected}"


def _make_variant(product: Product, suffix: str, stock: int = 50) -> ProductVariant:
    """Вариант с полностью заполненной оптовой сеткой"""
    return ProductVariant.objects.create(
        product=product,
        sku=f"SKU-{suffix}",
        onec_id=f"var-{suffix}",
        color_name="Чёрный",
        size_value="L",
        retail_price=RETAIL_PRICE,
        rrp=Decimal("1200.00"),
        msrp=Decimal("1300.00"),
        stock_quantity=stock,
        is_active=True,
        **WHOLESALE_PRICES,
    )


@pytest.fixture
def product(db):
    """Товар с заполненной оптовой сеткой"""
    suffix = get_unique_suffix()
    category = Category.objects.create(name=f"Кат-{suffix}", slug=f"cat-{suffix}")
    brand = Brand.objects.create(name=f"Бренд-{suffix}", slug=f"brand-{suffix}")
    product = Product.objects.create(
        name=f"Товар-{suffix}",
        slug=f"product-{suffix}",
        category=category,
        brand=brand,
        onec_id=f"1c-{suffix}",
        is_active=True,
    )
    _make_variant(product, suffix)
    return product


@pytest.fixture
def related_product(db, product):
    """Второй товар той же категории — попадёт в related_products карточки"""
    suffix = get_unique_suffix()
    related = Product.objects.create(
        name=f"Связанный-{suffix}",
        slug=f"related-{suffix}",
        category=product.category,
        brand=product.brand,
        onec_id=f"1c-rel-{suffix}",
        is_active=True,
    )
    _make_variant(related, f"REL-{suffix}", stock=10)
    return related


@pytest.fixture
def api_client():
    return APIClient()


def _make_user(role: str, *, is_verified: bool):
    suffix = get_unique_suffix()
    return User.objects.create_user(
        email=f"{role}-{suffix}@visibility.test",
        password="TestPass123!",
        role=role,
        is_verified=is_verified,
    )


def _authenticate(api_client, role_spec) -> None:
    """None — оставить запрос анонимным; кортеж — залогинить (role, is_verified)"""
    if role_spec is not None:
        role, is_verified = role_spec
        api_client.force_authenticate(user=_make_user(role, is_verified=is_verified))


def _list_item(api_client, product) -> dict:
    """Найти товар в ответе списочного endpoint'а"""
    response = api_client.get("/api/v1/products/", {"search": product.name})
    assert response.status_code == 200, response.data
    results = response.data.get("results", response.data)
    items = [item for item in results if item["slug"] == product.slug]
    assert items, f"Товар {product.slug} не найден в ответе каталога"
    return items[0]


class TestWholesalePricesHiddenFromUnauthorized:
    """AC7: анонимы, розница, unregistered и неверифицированный B2B не видят оптовых цен"""

    def test_fixture_fills_every_gated_field(self):
        """Сторож самого сторожа: незаполненное поле сделал бы проверку холостой"""
        assert set(WHOLESALE_PRICES) == set(WHOLESALE_PRICE_FIELDS), (
            "WHOLESALE_PRICES разошёлся с WHOLESALE_PRICE_FIELDS: добавьте цену для нового "
            "уровня, иначе сторож пропустит его утечку (поле останется пустым → 0.0)."
        )
        assert all(price > 0 for price in WHOLESALE_PRICES.values())

    @pytest.mark.parametrize("role_spec", UNAUTHORIZED_ROLES)
    def test_list_has_no_wholesale_prices(self, api_client, product, role_spec):
        """GET /api/v1/products/ — все opt*_price нулевые, ключи на месте"""
        _authenticate(api_client, role_spec)

        item = _list_item(api_client, product)

        _assert_wholesale_hidden(item, "список каталога")
        assert float(item["current_price"]) == float(RETAIL_PRICE)

    @pytest.mark.parametrize("role_spec", UNAUTHORIZED_ROLES)
    def test_detail_has_no_wholesale_prices(self, api_client, product, role_spec):
        """GET /api/v1/products/{slug}/ — то же для карточки товара"""
        _authenticate(api_client, role_spec)

        response = api_client.get(f"/api/v1/products/{product.slug}/")

        assert response.status_code == 200
        _assert_wholesale_hidden(response.data, "карточка товара")
        assert float(response.data["current_price"]) == float(RETAIL_PRICE)

    @pytest.mark.parametrize("role_spec", UNAUTHORIZED_ROLES)
    def test_related_products_have_no_wholesale_prices(self, api_client, product, related_product, role_spec):
        """Вложенный список related_products тоже под гейтом (context пробрасывается)"""
        _authenticate(api_client, role_spec)

        response = api_client.get(f"/api/v1/products/{product.slug}/")

        assert response.status_code == 200
        assert response.data["related_products"], "Ожидался хотя бы один связанный товар"
        for item in response.data["related_products"]:
            _assert_wholesale_hidden(item, f"related_products[{item['slug']}]")

    @pytest.mark.parametrize("role_spec", UNAUTHORIZED_ROLES)
    def test_detail_has_no_info_prices(self, api_client, product, role_spec):
        """AC6: РРЦ/МРЦ закрыты для тех же ролей"""
        _authenticate(api_client, role_spec)

        response = api_client.get(f"/api/v1/products/{product.slug}/")

        assert response.status_code == 200
        assert "rrp" not in response.data
        assert "msrp" not in response.data


class TestWholesalePricesVisibleForVerifiedB2B:
    """AC3: обратная сторона гейта — верифицированный B2B видит сетку целиком"""

    def test_verified_wholesale_user_sees_wholesale_prices(self, api_client, product):
        """Верифицированный wholesale_level1 получает фактические оптовые цены"""
        api_client.force_authenticate(user=_make_user("wholesale_level1", is_verified=True))

        item = _list_item(api_client, product)

        _assert_wholesale_visible(item, "список каталога")
        assert float(item["current_price"]) == float(OPT1_PRICE)

    def test_verified_wholesale_level2_sees_full_grid(self, api_client, product):
        """AC3, решение 4: wholesale_level2 видит всю сетку, а не только свой уровень"""
        api_client.force_authenticate(user=_make_user("wholesale_level2", is_verified=True))

        response = api_client.get(f"/api/v1/products/{product.slug}/")

        assert response.status_code == 200
        _assert_wholesale_visible(response.data, "карточка товара")
        assert float(response.data["current_price"]) == float(OPT2_PRICE)
        assert response.data["rrp"] == 1200.0

    def test_verified_b2b_sees_wholesale_in_related_products(self, api_client, product, related_product):
        """Гейт снимается и во вложенном списке — context один и тот же"""
        api_client.force_authenticate(user=_make_user("wholesale_level3", is_verified=True))

        response = api_client.get(f"/api/v1/products/{product.slug}/")

        assert response.status_code == 200
        assert response.data["related_products"]
        for item in response.data["related_products"]:
            _assert_wholesale_visible(item, f"related_products[{item['slug']}]")
            assert float(item["current_price"]) == float(OPT3_PRICE)


class TestUnverifiedB2BOrderPrice:
    """AC4: гейт достаёт до корзины и транзитом через price_snapshot — до заказа"""

    @staticmethod
    def _checkout(api_client):
        """Оформление заказа B2B-способом оплаты (для wholesale-ролей card запрещён)"""
        return api_client.post(
            "/api/v1/orders/",
            {
                "delivery_address": "Тестовый адрес, 1",
                "delivery_method": "transport_company",
                "payment_method": "bank_transfer",
                "notes": "AC4: транзит цены из корзины в заказ",
            },
        )

    @staticmethod
    def _order_items(order_id):
        """Позиции лежат в субзаказах, master прямых items не содержит"""
        return list(OrderItem.objects.filter(order__parent_order_id=order_id))

    def test_unverified_b2b_cart_price_is_retail(self, api_client, product):
        """Неверифицированный оптовик кладёт товар — price_snapshot розничный"""
        api_client.force_authenticate(user=_make_user("wholesale_level1", is_verified=False))
        variant = product.variants.first()

        response = api_client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2})

        assert response.status_code == 201, response.data
        cart = api_client.get("/api/v1/cart/")
        assert float(cart.data["total_amount"]) == float(RETAIL_PRICE) * 2

    def test_verified_b2b_cart_price_is_wholesale(self, api_client, product):
        """Контрольный кейс: верифицированный оптовик получает оптовую цену"""
        api_client.force_authenticate(user=_make_user("wholesale_level1", is_verified=True))
        variant = product.variants.first()

        response = api_client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2})

        assert response.status_code == 201, response.data
        cart = api_client.get("/api/v1/cart/")
        assert float(cart.data["total_amount"]) == float(OPT1_PRICE) * 2

    def test_unverified_b2b_order_unit_price_is_retail(self, api_client, product):
        """Сквозной AC4: CartItem.price_snapshot → OrderItem.unit_price остаётся розничным"""
        api_client.force_authenticate(user=_make_user("wholesale_level1", is_verified=False))
        variant = product.variants.first()
        add = api_client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2})
        assert add.status_code == 201, add.data

        order = self._checkout(api_client)

        assert order.status_code == 201, order.data
        items = self._order_items(order.data["id"])
        assert len(items) == 1, f"Ожидалась одна позиция заказа, получено {len(items)}"
        assert items[0].unit_price == RETAIL_PRICE, (
            f"Неверифицированный оптовик оформил заказ по цене {items[0].unit_price} "
            f"вместо розничной {RETAIL_PRICE}"
        )
        assert items[0].total_price == RETAIL_PRICE * 2

    def test_verified_b2b_order_unit_price_is_wholesale(self, api_client, product):
        """Контрольный кейс: верифицированный оптовик оформляет заказ по опту"""
        api_client.force_authenticate(user=_make_user("wholesale_level1", is_verified=True))
        variant = product.variants.first()
        add = api_client.post("/api/v1/cart/items/", {"variant_id": variant.id, "quantity": 2})
        assert add.status_code == 201, add.data

        order = self._checkout(api_client)

        assert order.status_code == 201, order.data
        items = self._order_items(order.data["id"])
        assert len(items) == 1
        assert items[0].unit_price == OPT1_PRICE
        assert items[0].total_price == OPT1_PRICE * 2

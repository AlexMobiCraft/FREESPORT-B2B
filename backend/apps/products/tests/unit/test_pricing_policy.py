"""
Тесты политики видимости цен (`apps.products.pricing_policy`).

Стори `security-wholesale-price-visibility`: оптовые и инфо-цены доступны
только верифицированному B2B; все остальные видят розничную цену.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory

from apps.products.factories import ProductFactory, ProductVariantFactory
from apps.products.pricing_policy import (
    INFO_PRICE_FIELDS,
    WHOLESALE_PRICE_FIELDS,
    can_see_info_prices,
    can_see_wholesale_prices,
    resolve_pricing_role,
)
from apps.products.serializers import ProductDetailSerializer, ProductListSerializer
from apps.users.models import User

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

# Роли, дающие B2B-уровень цен при наличии верификации
B2B_ROLES = User.B2B_ROLES


def _make_user(role: str, *, is_verified: bool) -> User:
    """Пользователь с заданной ролью и флагом верификации"""
    return User.objects.create_user(
        email=f"{role}-{'ver' if is_verified else 'unver'}@pricing-policy.test",
        password="testpass123",
        role=role,
        is_verified=is_verified,
    )


@pytest.fixture
def api_factory():
    return APIRequestFactory()


@pytest.fixture
def product():
    """Товар с заполненными оптовыми и инфо-ценами"""
    product = ProductFactory(create_variant=False)
    ProductVariantFactory(
        product=product,
        retail_price=Decimal("1000.00"),
        opt1_price=Decimal("900.00"),
        opt2_price=Decimal("800.00"),
        opt3_price=Decimal("700.00"),
        trainer_price=Decimal("600.00"),
        federation_price=Decimal("650.00"),
        rrp=Decimal("1200.00"),
        msrp=Decimal("1300.00"),
        stock_quantity=10,
        reserved_quantity=0,
    )
    return product


def _serialize_list(product, api_factory, user=None) -> dict:
    """Сериализовать товар списочным сериализатором от имени пользователя"""
    request = api_factory.get("/api/v1/products/")
    if user is not None:
        request.user = user
    return ProductListSerializer(product, context={"request": request}).data


class TestResolvePricingRole:
    """resolve_pricing_role: понижение неверифицированного B2B до retail"""

    def test_anonymous_resolves_to_retail(self, api_factory):
        """AC1: None и AnonymousUser считаются розницей"""
        from django.contrib.auth.models import AnonymousUser

        assert resolve_pricing_role(None) == "retail"
        assert resolve_pricing_role(AnonymousUser()) == "retail"

    @pytest.mark.parametrize("role", B2B_ROLES)
    def test_unverified_b2b_resolves_to_retail(self, role):
        """AC1, AC4: B2B-роль без верификации понижается до retail"""
        user = _make_user(role, is_verified=False)

        assert resolve_pricing_role(user) == "retail"

    @pytest.mark.parametrize("role", B2B_ROLES)
    def test_verified_b2b_keeps_role(self, role):
        """AC1, AC3: верифицированный B2B сохраняет свою роль"""
        user = _make_user(role, is_verified=True)

        assert resolve_pricing_role(user) == role

    def test_unregistered_never_sees_wholesale(self):
        """AC2: запись 1С без портального аккаунта — не B2B"""
        user = _make_user("unregistered", is_verified=True)

        assert resolve_pricing_role(user) == "unregistered"
        assert can_see_wholesale_prices(user) is False
        assert can_see_info_prices(user) is False

    def test_retail_user_sees_nothing_wholesale(self):
        """AC2: розница не видит ни оптовых, ни инфо-цен"""
        user = _make_user("retail", is_verified=True)

        assert can_see_wholesale_prices(user) is False
        assert can_see_info_prices(user) is False

    def test_anonymous_sees_nothing_wholesale(self):
        """AC2: аноним не видит ни оптовых, ни инфо-цен"""
        assert can_see_wholesale_prices(None) is False
        assert can_see_info_prices(None) is False

    def test_admin_sees_wholesale_and_info(self):
        """AC3, AC6: админ видит и оптовые, и инфо-цены"""
        user = _make_user("admin", is_verified=True)

        assert can_see_wholesale_prices(user) is True
        assert can_see_info_prices(user) is True

    def test_federation_rep_sees_wholesale_but_not_info(self):
        """AC6: federation_rep намеренно не входит в белый список РРЦ/МРЦ"""
        user = _make_user("federation_rep", is_verified=True)

        assert can_see_wholesale_prices(user) is True
        assert can_see_info_prices(user) is False

    @pytest.mark.parametrize("role", ["wholesale_level1", "wholesale_level2", "wholesale_level3", "trainer"])
    def test_unverified_b2b_loses_info_prices(self, role):
        """AC6: неверифицированный оптовик не видит РРЦ/МРЦ"""
        user = _make_user(role, is_verified=False)

        assert can_see_info_prices(user) is False
        assert can_see_wholesale_prices(user) is False

    @pytest.mark.parametrize("role", ["wholesale_level1", "wholesale_level2", "wholesale_level3", "trainer"])
    def test_verified_b2b_gets_info_prices(self, role):
        """AC6: верифицированный оптовик видит РРЦ/МРЦ"""
        user = _make_user(role, is_verified=True)

        assert can_see_info_prices(user) is True

    def test_field_constants(self):
        """AC1: константы полей — единственный источник истины"""
        # opt4_price добавлено стори 39.3 — новое оптовое поле обязано быть
        # под гейтом, иначе оно единственное уедет анонимному запросу
        assert WHOLESALE_PRICE_FIELDS == ("opt1_price", "opt2_price", "opt3_price", "opt4_price")
        assert INFO_PRICE_FIELDS == ("rrp", "msrp")


class TestSerializerWholesaleGate:
    """Гейт сырых оптовых полей в ответе каталога"""

    def test_serializer_zeroes_wholesale_for_anonymous(self, product, api_factory):
        """AC2, AC8: для анонима поля остаются в ответе, но равны 0.0"""
        data = _serialize_list(product, api_factory)

        for field in WHOLESALE_PRICE_FIELDS:
            assert field in data, f"Ключ {field} должен остаться в ответе (вариант B)"
            assert data[field] == 0.0

    def test_serializer_zeroes_wholesale_for_retail(self, product, api_factory):
        """AC2: аутентифицированная розница тоже не видит оптовых цен"""
        user = _make_user("retail", is_verified=True)

        data = _serialize_list(product, api_factory, user)

        assert all(data[field] == 0.0 for field in WHOLESALE_PRICE_FIELDS)

    def test_serializer_zeroes_wholesale_for_unverified_b2b(self, product, api_factory):
        """AC2: неверифицированный оптовик не видит оптовых цен"""
        user = _make_user("wholesale_level1", is_verified=False)

        data = _serialize_list(product, api_factory, user)

        assert all(data[field] == 0.0 for field in WHOLESALE_PRICE_FIELDS)
        assert data["current_price"] == "1000.00"

    def test_serializer_keeps_wholesale_for_verified(self, product, api_factory):
        """AC3, AC4: верифицированный B2B видит всю оптовую сетку"""
        user = _make_user("wholesale_level2", is_verified=True)

        data = _serialize_list(product, api_factory, user)

        assert data["opt1_price"] == 900.0
        assert data["opt2_price"] == 800.0
        assert data["opt3_price"] == 700.0
        assert data["current_price"] == "800.00"

    def test_serializer_keeps_wholesale_for_admin(self, product, api_factory):
        """AC3: админ видит оптовую сетку"""
        user = _make_user("admin", is_verified=True)

        data = _serialize_list(product, api_factory, user)

        assert data["opt1_price"] == 900.0

    def test_info_prices_hidden_for_unverified_b2b(self, product, api_factory):
        """AC6: у неверифицированного оптовика ключи rrp/msrp вырезаны"""
        user = _make_user("wholesale_level1", is_verified=False)

        data = _serialize_list(product, api_factory, user)

        assert "rrp" not in data
        assert "msrp" not in data

    def test_info_prices_visible_for_verified_b2b(self, product, api_factory):
        """AC6: верифицированный оптовик видит РРЦ/МРЦ"""
        user = _make_user("wholesale_level1", is_verified=True)

        data = _serialize_list(product, api_factory, user)

        assert data["rrp"] == 1200.0
        assert data["msrp"] == 1300.0

    def test_related_products_are_gated(self, product, api_factory):
        """AC2: гейт действует и во вложенном списке related_products"""
        related = ProductFactory(
            create_variant=False,
            category=product.category,
            brand=product.brand,
        )
        ProductVariantFactory(
            product=related,
            retail_price=Decimal("500.00"),
            opt1_price=Decimal("400.00"),
            opt2_price=Decimal("300.00"),
            opt3_price=Decimal("200.00"),
            stock_quantity=5,
            reserved_quantity=0,
        )

        request = api_factory.get(f"/api/v1/products/{product.slug}/")
        data = ProductDetailSerializer(product, context={"request": request}).data

        assert data["related_products"], "Ожидается хотя бы один связанный товар"
        for item in data["related_products"]:
            for field in WHOLESALE_PRICE_FIELDS:
                assert item[field] == 0.0


class TestGetPriceForUser:
    """Вторая половина инварианта: get_price_for_user"""

    @pytest.fixture
    def variant(self):
        return ProductVariantFactory(
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            opt2_price=Decimal("800.00"),
            opt3_price=Decimal("700.00"),
            trainer_price=Decimal("600.00"),
            federation_price=Decimal("650.00"),
        )

    @pytest.mark.parametrize("role", B2B_ROLES)
    def test_unverified_b2b_gets_retail_price(self, variant, role):
        """AC4: неверифицированный B2B получает розничную цену"""
        user = _make_user(role, is_verified=False)

        assert variant.get_price_for_user(user) == variant.retail_price

    def test_verified_b2b_gets_wholesale_price(self, variant):
        """AC3: верифицированный оптовик получает свою оптовую цену"""
        user = _make_user("wholesale_level1", is_verified=True)

        assert variant.get_price_for_user(user) == variant.opt1_price

    def test_anonymous_gets_retail_price(self, variant):
        """AC4: гость получает розничную цену (ранняя ветка поглощена)"""
        from django.contrib.auth.models import AnonymousUser

        assert variant.get_price_for_user(None) == variant.retail_price
        assert variant.get_price_for_user(AnonymousUser()) == variant.retail_price

    def test_admin_gets_retail_price(self, variant):
        """Поведение не меняется: у admin нет собственной цены"""
        user = _make_user("admin", is_verified=True)

        assert variant.get_price_for_user(user) == variant.retail_price

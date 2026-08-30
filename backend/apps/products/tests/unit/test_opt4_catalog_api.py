"""
Каталог, админка и API отдают цену уровня 4 (стори 39.3).

Покрывает AC2 (поле `opt4_price` в ответе), AC3 (вариант, у которого
заполнена только `opt4_price`, находится и в списке, и в детальной карточке),
AC4 (РРЦ/МРЦ доступны роли уровня 4) и AC5 (поле в fieldset админки).

Мина, зафиксированная стори `security-wholesale-price-visibility`:
B2B-роль без `is_verified=True` понижается до `retail`, поэтому любой
пользователь `wholesale_level4` здесь создаётся верифицированным — иначе
тест проверил бы розничную ветку и «доказал» отсутствие фичи.
"""

from decimal import Decimal

import pytest
from rest_framework.test import APIRequestFactory

from apps.products.admin import ProductVariantAdmin
from apps.products.factories import ProductFactory, ProductVariantFactory, get_unique_suffix
from apps.products.models import Product
from apps.products.serializers import ProductListSerializer
from apps.products.views import ProductViewSet
from apps.users.models import User

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


def _make_user(role: str, is_verified: bool = True) -> User:
    """Пользователь с заданной ролью; B2B — верифицированный по умолчанию"""
    return User.objects.create_user(
        email=f"{role}-{get_unique_suffix()}@example.com",
        password="TestPass123!",
        role=role,
        is_verified=is_verified,
    )


def _serialize(product: Product, user: User | None = None) -> dict:
    """Данные ProductListSerializer с request-контекстом от имени пользователя"""
    request = APIRequestFactory().get("/")
    if user is not None:
        request.user = user
    return ProductListSerializer(product, context={"request": request}).data


def _opt4_only_variant(product: Product):
    """
    Вариант, у которого из ценовых полей заполнена ТОЛЬКО opt4_price.

    Дефолты фабрики заполняют все цены, поэтому остальные поля гасятся явно.
    """
    return ProductVariantFactory(
        product=product,
        retail_price=Decimal("0"),
        opt1_price=None,
        opt2_price=None,
        opt3_price=None,
        opt4_price=Decimal("777.00"),
        trainer_price=None,
        federation_price=None,
    )


class TestOpt4PriceInCatalogApi:
    """AC2: сырое поле opt4_price присутствует в ответе каталога."""

    def test_serializer_exposes_opt4_price(self):
        """Оптовик уровня 4 получает значение opt4_price своего варианта"""
        product = ProductFactory(create_variant=False)
        ProductVariantFactory(product=product, opt4_price=Decimal("543.21"))

        data = _serialize(product, _make_user("wholesale_level4"))

        assert data["opt4_price"] == 543.21

    def test_get_opt4_price_returns_zero_when_empty(self):
        """Пустая opt4_price даёт 0.0, а не None — поведение как у get_opt3_price"""
        product = ProductFactory(create_variant=False)
        ProductVariantFactory(product=product, opt4_price=None)

        data = _serialize(product, _make_user("wholesale_level4"))

        assert data["opt4_price"] == 0.0

    def test_anonymous_does_not_see_opt4_price(self):
        """
        Сторож утечки: анониму поле обнуляется наравне с opt1-3.

        Пропуск "opt4_price" в WHOLESALE_PRICE_FIELDS оставил бы новое поле
        единственным неприкрытым (tech-debt.md п. 18).
        """
        product = ProductFactory(create_variant=False)
        ProductVariantFactory(product=product, opt4_price=Decimal("543.21"))

        data = _serialize(product)

        assert data["opt4_price"] == 0.0


class TestOpt4OnlyVariantVisibility:
    """AC3: вариант с единственной заполненной ценой уровня 4 не теряется."""

    def test_variant_with_only_opt4_price_is_found(self):
        """_get_first_variant находит вариант по fallback-запросу без prefetch"""
        product = ProductFactory(create_variant=False)
        variant = _opt4_only_variant(product)

        found = ProductListSerializer()._get_first_variant(Product.objects.get(pk=product.pk))

        assert found is not None
        assert found.pk == variant.pk

    def test_catalog_queryset_prefetches_opt4_only_variant(self):
        """Тот же вариант попадает в first_variant_list каталожного queryset"""
        product = ProductFactory(create_variant=False)
        variant = _opt4_only_variant(product)

        prefetched = ProductViewSet().get_queryset().get(pk=product.pk)

        assert [v.pk for v in prefetched.first_variant_list] == [variant.pk]


class TestInfoPricesForWholesaleLevel4:
    """AC4: инфо-цены РРЦ/МРЦ видны четвёртому уровню наравне с 1-3."""

    @staticmethod
    def _product_with_info_prices() -> Product:
        product = ProductFactory(create_variant=False)
        ProductVariantFactory(product=product, rrp=Decimal("1500.00"), msrp=Decimal("1400.00"))
        return product

    def test_wholesale_level4_sees_rrp_and_msrp(self):
        """Роль уровня 4 получает rrp и msrp с фактическими значениями"""
        data = _serialize(self._product_with_info_prices(), _make_user("wholesale_level4"))

        assert data["rrp"] == 1500.0
        assert data["msrp"] == 1400.0

    def test_unverified_wholesale_level4_hides_rrp(self):
        """Неверифицированный уровень 4 понижается до retail и инфо-цен не видит"""
        user = _make_user("wholesale_level4", is_verified=False)

        data = _serialize(self._product_with_info_prices(), user)

        assert "rrp" not in data
        assert "msrp" not in data

    def test_retail_user_still_hides_rrp(self):
        """Сторож обратной стороны: розница по-прежнему инфо-цен не видит"""
        data = _serialize(self._product_with_info_prices(), _make_user("retail"))

        assert "rrp" not in data
        assert "msrp" not in data


class TestProductVariantAdminPricingFieldset:
    """AC5: opt4_price выведено в fieldset «Ценообразование»."""

    def test_admin_price_fieldset_contains_opt4(self):
        """Поле стоит в блоке цен сразу после opt3_price"""
        pricing_fields = next(
            options["fields"] for title, options in ProductVariantAdmin.fieldsets if title == "Ценообразование"
        )

        assert "opt4_price" in pricing_fields
        assert pricing_fields.index("opt4_price") == pricing_fields.index("opt3_price") + 1

    def test_admin_list_display_has_no_wholesale_prices(self):
        """list_display оптовых цен не показывает вовсе — opt4_price туда не добавляется"""
        assert not [field for field in ProductVariantAdmin.list_display if str(field).startswith("opt")]

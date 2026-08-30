"""
Ценовые фильтры каталога согласованы с ценой, которую видит пользователь.

Стори `security-wholesale-price-visibility`, AC5 + находка ревью 2026-08-04.

Инвариант, который защищает файл: товар попадает в выдачу по `min_price` /
`max_price` тогда и только тогда, когда в эту границу укладывается его
`current_price` из того же ответа. Ловушка — нулевая специальная цена:
`get_price_for_user` считает `opt*_price = 0.00` отсутствующей ценой и
показывает розничную, а фильтр раньше откатывался на розницу только при
`NULL`. В результате запрос «до 600 ₽» возвращал товар, стоящий 1000 ₽.

Матрица идёт по `ROLE_PRICE_FIELDS`: роль, добавленная в политику цен без
поддержки в фильтрах, ломает этот файл сразу.
"""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.products.factories import ProductFactory
from apps.products.pricing_policy import ROLE_PRICE_FIELDS
from tests.conftest import get_unique_suffix

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

User = get_user_model()

RETAIL_PRICE = Decimal("1000.00")
SPECIAL_PRICE = Decimal("500.00")

# Границы подобраны так, чтобы розничная и специальная цены оказались
# по разные стороны от каждой из них.
BELOW_RETAIL = 900  # 500 < 900 <= 1000
ABOVE_SPECIAL = 600  # 500 <= 600 < 1000

ROLE_MATRIX = [pytest.param(role, field, id=role) for role, field in sorted(ROLE_PRICE_FIELDS.items())]


@pytest.fixture
def api_client():
    return APIClient()


def _authenticate(api_client, role: str) -> None:
    """Верифицированный пользователь заданной B2B-роли"""
    suffix = get_unique_suffix()
    api_client.force_authenticate(
        user=User.objects.create_user(
            email=f"{role}-{suffix}@filters.test",
            password="TestPass123!",
            role=role,
            is_verified=True,
        )
    )


def _product_with_price(price_field: str, special_price):
    """Товар с розничной ценой 1000 и заданной специальной ценой роли"""
    return ProductFactory(
        retail_price=RETAIL_PRICE,
        stock_quantity=50,
        **{price_field: special_price},
    )


def _slugs(api_client, product, **params) -> set[str]:
    """Слаги товаров в выдаче каталога с заданными параметрами фильтра"""
    response = api_client.get("/api/v1/products/", {"search": product.name, **params})
    assert response.status_code == 200, response.data
    results = response.data.get("results", response.data)
    return {item["slug"] for item in results}


def _current_price(api_client, product) -> float:
    """Цена, которую каталог показывает в карточке товара"""
    response = api_client.get(f"/api/v1/products/{product.slug}/")
    assert response.status_code == 200, response.data
    return float(response.data["current_price"])


class TestZeroSpecialPriceFilters:
    """Нулевая специальная цена: фильтр обязан работать по розничной цене"""

    @pytest.mark.parametrize("role,price_field", ROLE_MATRIX)
    def test_zero_special_price_is_shown_as_retail(self, api_client, role, price_field):
        """Опора всей матрицы: с нулевой спеццена карточка показывает розничную"""
        product = _product_with_price(price_field, Decimal("0.00"))
        _authenticate(api_client, role)

        assert _current_price(api_client, product) == float(RETAIL_PRICE)

    @pytest.mark.parametrize("role,price_field", ROLE_MATRIX)
    def test_zero_special_price_passes_min_price(self, api_client, role, price_field):
        """Товар стоит 1000 — запрос «от 900 ₽» обязан его вернуть"""
        product = _product_with_price(price_field, Decimal("0.00"))
        _authenticate(api_client, role)

        assert product.slug in _slugs(api_client, product, min_price=BELOW_RETAIL), (
            f"{role}: товар с {price_field}=0.00 показывается по {RETAIL_PRICE}, "
            f"но выпал из выдачи min_price={BELOW_RETAIL}"
        )

    @pytest.mark.parametrize("role,price_field", ROLE_MATRIX)
    def test_zero_special_price_is_excluded_by_max_price(self, api_client, role, price_field):
        """Обратная сторона: «до 600 ₽» не должен показывать товар за 1000"""
        product = _product_with_price(price_field, Decimal("0.00"))
        _authenticate(api_client, role)

        assert product.slug not in _slugs(api_client, product, max_price=ABOVE_SPECIAL), (
            f"{role}: товар с {price_field}=0.00 стоит {RETAIL_PRICE}, "
            f"выдача max_price={ABOVE_SPECIAL} обещает цену, которой в карточке нет"
        )


class TestFilledSpecialPriceFilters:
    """Контрольная сторона: заполненная специальная цена фильтрует по себе"""

    @pytest.mark.parametrize("role,price_field", ROLE_MATRIX)
    def test_special_price_is_shown_and_filtered(self, api_client, role, price_field):
        """Показанная цена — специальная, обе границы согласованы с ней"""
        product = _product_with_price(price_field, SPECIAL_PRICE)
        _authenticate(api_client, role)

        assert _current_price(api_client, product) == float(SPECIAL_PRICE)
        assert product.slug in _slugs(api_client, product, max_price=ABOVE_SPECIAL)
        assert product.slug not in _slugs(api_client, product, min_price=BELOW_RETAIL)

    @pytest.mark.parametrize("role,price_field", ROLE_MATRIX)
    def test_empty_special_price_filters_by_retail(self, api_client, role, price_field):
        """Пустая специальная цена — прежнее поведение, откат на розницу"""
        product = _product_with_price(price_field, None)
        _authenticate(api_client, role)

        assert _current_price(api_client, product) == float(RETAIL_PRICE)
        assert product.slug in _slugs(api_client, product, min_price=BELOW_RETAIL)
        assert product.slug not in _slugs(api_client, product, max_price=ABOVE_SPECIAL)


class TestUnverifiedB2BPriceFilters:
    """AC5: неверифицированный оптовик фильтруется по розничной цене"""

    def test_unverified_wholesale_filters_by_retail(self, api_client):
        """Специальная цена 500 не влияет на выдачу — роль понижена до retail"""
        product = _product_with_price("opt1_price", SPECIAL_PRICE)
        suffix = get_unique_suffix()
        api_client.force_authenticate(
            user=User.objects.create_user(
                email=f"unverified-{suffix}@filters.test",
                password="TestPass123!",
                role="wholesale_level1",
                is_verified=False,
            )
        )

        assert _current_price(api_client, product) == float(RETAIL_PRICE)
        assert product.slug in _slugs(api_client, product, min_price=BELOW_RETAIL)
        assert product.slug not in _slugs(api_client, product, max_price=ABOVE_SPECIAL)

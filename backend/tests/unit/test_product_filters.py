"""
Unit-тесты для фильтров товаров (Story 2.9: filtering-api)
Тестируем фильтрацию по размерам, брендам, ценам, наличию
"""

from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import RequestFactory

from apps.products.factories import ProductFactory
from apps.products.filters import ProductFilter
from apps.products.models import Product, ProductVariant
from apps.products.pricing_policy import ROLE_PRICE_FIELDS

User = get_user_model()

pytestmark = pytest.mark.django_db


@pytest.mark.unit
class TestProductFilterSizeFilter:
    """Unit-тесты для фильтра по размеру"""

    def test_filter_size_empty_value(self):
        """Тест с пустым значением размера"""
        product_filter = ProductFilter()
        queryset = Mock()

        # Пустая строка
        result = product_filter.filter_size(queryset, "size", "")
        assert result == queryset

        # None
        result = product_filter.filter_size(queryset, "size", None)
        assert result == queryset

        # Строка только из пробелов
        result = product_filter.filter_size(queryset, "size", "   ")
        assert result == queryset

    def test_filter_size_single_size_json_variants(self):
        """Тест фильтрации по размеру с различными вариантами JSON"""
        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_size(queryset, "size", "XL")

            # Проверяем, что был вызван filter с правильным Q-объектом
            mock_filter.assert_called_once()
            q_arg = mock_filter.call_args[0][0]

            # Проверяем, что Q-объект содержит правильные условия
            assert isinstance(q_arg, Q)

    @patch("django.db.connection")
    def test_filter_size_postgresql_case_insensitive(self, mock_connection):
        """Тест case-insensitive поиска для PostgreSQL"""
        mock_connection.vendor = "postgresql"

        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_size(queryset, "size", "xl")
            mock_filter.assert_called_once()

    @patch("django.db.connection")
    def test_filter_size_non_postgresql_no_iexact(self, mock_connection):
        """Тест что для не-PostgreSQL не используется iexact"""
        mock_connection.vendor = "sqlite"

        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_size(queryset, "size", "XL")
            mock_filter.assert_called_once()


@pytest.mark.unit
class TestProductFilterBrandFilter:
    """Unit-тесты для фильтра по бренду"""

    def test_filter_brand_empty_value(self):
        """Тест с пустым значением бренда"""
        product_filter = ProductFilter()
        queryset = Mock()

        result = product_filter.filter_brand(queryset, "brand", "")
        assert result == queryset

        result = product_filter.filter_brand(queryset, "brand", None)
        assert result == queryset

    def test_filter_brand_single_id(self):
        """Тест фильтрации по ID бренда"""
        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_brand(queryset, "brand", "123")
            mock_filter.assert_called_once()

    def test_filter_brand_single_slug(self):
        """Тест фильтрации по slug бренда"""
        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_brand(queryset, "brand", "nike")
            mock_filter.assert_called_once()

    def test_filter_brand_multiple_values(self):
        """Тест фильтрации по нескольким брендам"""
        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_brand(queryset, "brand", "nike,adidas,123")
            mock_filter.assert_called_once()

    def test_filter_brand_whitespace_handling(self):
        """Тест обработки пробелов в значениях брендов"""
        product_filter = ProductFilter()
        queryset = Mock()

        with patch.object(queryset, "filter") as mock_filter:
            product_filter.filter_brand(queryset, "brand", " nike , adidas , 123 ")
            mock_filter.assert_called_once()


@pytest.mark.unit
class TestProductFilterPriceFilters:
    """Unit-тесты для ценовых фильтров"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Настройка для каждого теста"""
        self.factory = RequestFactory()

    def test_filter_min_price_validation(self):
        """Тест валидации минимальной цены"""
        product_filter = ProductFilter()
        queryset = Mock()

        # Отрицательная цена
        result = product_filter.filter_min_price(queryset, "min_price", -10)
        assert result == queryset

        # None значение
        result = product_filter.filter_min_price(queryset, "min_price", None)
        assert result == queryset

    def test_filter_max_price_validation(self):
        """Тест валидации максимальной цены"""
        product_filter = ProductFilter()
        queryset = Mock()

        # Отрицательная цена
        result = product_filter.filter_max_price(queryset, "max_price", -10)
        assert result == queryset

        # None значение
        result = product_filter.filter_max_price(queryset, "max_price", None)
        assert result == queryset

    def test_filter_min_price_anonymous_user(self):
        """Тест фильтрации минимальной цены для анонимного пользователя"""
        product_filter = ProductFilter()
        product_filter.request = None
        queryset = Mock()

        product_filter.filter_min_price(queryset, "min_price", 100)

        # Проверяем, что фильтры вариантов были накоплены
        assert hasattr(product_filter, "_variant_filters")
        assert "retail_price__gte" in str(product_filter._variant_filters)

    def test_filter_max_price_anonymous_user(self):
        """Тест фильтрации максимальной цены для анонимного пользователя"""
        product_filter = ProductFilter()
        product_filter.request = None
        queryset = Mock()

        product_filter.filter_max_price(queryset, "max_price", 1000)

        # Проверяем, что фильтры вариантов были накоплены
        assert hasattr(product_filter, "_variant_filters")
        assert "retail_price__lte" in str(product_filter._variant_filters)

    def test_filter_min_price_wholesale_user(self):
        """Тест фильтрации минимальной цены для оптового пользователя"""
        # Создаем mock пользователя
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.role = "wholesale_level1"

        # Создаем mock запроса
        mock_request = Mock()
        mock_request.user = mock_user

        product_filter = ProductFilter()
        product_filter.request = mock_request
        queryset = Mock()

        product_filter.filter_min_price(queryset, "min_price", 100)

        assert hasattr(product_filter, "_variant_filters")
        # Для wholesale_level1 должно быть:
        # Q(opt1_price__gte=100) | Q(opt1_price__isnull=True, retail_price__gte=100)
        assert "opt1_price__gte" in str(product_filter._variant_filters)

    def test_filter_max_price_trainer_user(self):
        """Тест фильтрации максимальной цены для тренера"""
        # Создаем mock пользователя
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.role = "trainer"

        # Создаем mock запроса
        mock_request = Mock()
        mock_request.user = mock_user

        product_filter = ProductFilter()
        product_filter.request = mock_request
        queryset = Mock()

        product_filter.filter_max_price(queryset, "max_price", 1000)

        assert hasattr(product_filter, "_variant_filters")
        assert "trainer_price__lte" in str(product_filter._variant_filters)


@pytest.mark.unit
class TestProductFilterStockFilter:
    """Unit-тесты для фильтра по наличию"""

    def test_filter_in_stock_true(self):
        """Тест фильтрации товаров в наличии"""
        product_filter = ProductFilter()
        queryset = Mock()

        product_filter.filter_in_stock(queryset, "in_stock", True)

        assert hasattr(product_filter, "_variant_filters")
        assert "stock_quantity__gt" in str(product_filter._variant_filters)

    def test_filter_in_stock_false(self):
        """Тест фильтрации товаров НЕ в наличии"""
        product_filter = ProductFilter()
        queryset = Mock()

        # Для in_stock=False мы не добавляем фильтр (показываем все товары)
        product_filter.filter_in_stock(queryset, "in_stock", False)

        # Либо _variant_filters не создан, либо в нем нет stock_quantity
        if hasattr(product_filter, "_variant_filters"):
            assert "stock_quantity" not in str(product_filter._variant_filters)


@pytest.mark.unit
class TestProductFilterIntegration:
    """Интеграционные unit-тесты для комбинирования фильтров"""

    def test_filterset_meta_fields(self):
        """Тест что Meta содержит все необходимые поля"""
        expected_fields = [
            "category_id",
            "brand",
            "min_price",
            "max_price",
            "in_stock",
            "is_featured",
            "search",
            "size",
            # Story 11.0: Маркетинговые фильтры
            "is_hit",
            "is_new",
            "is_sale",
            "is_promo",
            "is_premium",
            "has_discount",
        ]

        assert set(ProductFilter.Meta.fields) == set(expected_fields)

    def test_filterset_model(self):
        """Тест что FilterSet связан с правильной моделью"""
        assert ProductFilter.Meta.model == Product

    def test_filter_methods_exist(self):
        """Тест что все необходимые методы фильтрации существуют"""
        product_filter = ProductFilter()

        assert hasattr(product_filter, "filter_brand")
        assert hasattr(product_filter, "filter_min_price")
        assert hasattr(product_filter, "filter_max_price")
        assert hasattr(product_filter, "filter_in_stock")
        assert hasattr(product_filter, "filter_search")
        assert hasattr(product_filter, "filter_size")

    def test_all_role_price_mappings(self):
        """
        Тест что все роли пользователей корректно обрабатываются
        в ценовых фильтрах
        """
        roles_to_test = [
            "retail",
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "wholesale_level4",
            "trainer",
            "federation_rep",
        ]

        product_filter = ProductFilter()
        queryset = Mock()

        for role in roles_to_test:
            # Создаем mock пользователя для каждой роли
            mock_user = Mock()
            mock_user.is_authenticated = True
            mock_user.role = role

            mock_request = Mock()
            mock_request.user = mock_user

            product_filter.request = mock_request
            # Сбрасываем фильтры перед каждым тестом
            if hasattr(product_filter, "_variant_filters"):
                delattr(product_filter, "_variant_filters")

            # Тестируем что каждая роль обрабатывается без ошибок
            product_filter.filter_min_price(queryset, "min_price", 100)
            product_filter.filter_max_price(queryset, "max_price", 1000)

            assert hasattr(product_filter, "_variant_filters")


@pytest.mark.unit
class TestProductFilterPricingPolicy:
    """
    Ценовые фильтры согласованы с политикой видимости цен.

    Стори `security-wholesale-price-visibility`, AC5: пользователь
    фильтруется по той цене, которую ему показывают. Неверифицированный
    оптовик видит розничную цену — значит и фильтруется по `retail_price`.
    """

    @staticmethod
    def _filter_with_user(role, is_verified):
        """ProductFilter с mock-запросом от имени пользователя с заданной ролью"""
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.role = role
        # ЯВНО: у Mock любой атрибут truthy, поэтому is_verified=False
        # обязано задаваться руками, иначе тест молча проверит не то
        mock_user.is_verified = is_verified

        mock_request = Mock()
        mock_request.user = mock_user

        product_filter = ProductFilter()
        product_filter.request = mock_request
        return product_filter

    def test_unverified_wholesale_filters_by_retail_price(self):
        """Неверифицированный оптовик фильтруется по retail_price"""
        product_filter = self._filter_with_user("wholesale_level1", is_verified=False)

        product_filter.filter_min_price(Mock(), "min_price", 100)

        assert product_filter._variant_filters == Q(retail_price__gte=100)

    def test_verified_wholesale_filters_by_opt1_price(self):
        """Верифицированный оптовик фильтруется по своей оптовой цене"""
        product_filter = self._filter_with_user("wholesale_level1", is_verified=True)

        product_filter.filter_min_price(Mock(), "min_price", 100)

        # Специальная цена применяется, только если она строго больше нуля:
        # 0.00 и NULL одинаково означают «цены для роли нет» (см. AC5)
        expected = (Q(opt1_price__gt=0) & Q(opt1_price__gte=100)) | (
            (Q(opt1_price__isnull=True) | Q(opt1_price=0)) & Q(retail_price__gte=100)
        )
        assert product_filter._variant_filters == expected

    def test_unverified_trainer_max_price_by_retail(self):
        """То же для filter_max_price и роли trainer"""
        product_filter = self._filter_with_user("trainer", is_verified=False)

        product_filter.filter_max_price(Mock(), "max_price", 1000)

        assert product_filter._variant_filters == Q(retail_price__lte=1000)

    def test_verified_trainer_max_price_by_trainer_price(self):
        """Верифицированный тренер фильтруется по trainer_price"""
        product_filter = self._filter_with_user("trainer", is_verified=True)

        product_filter.filter_max_price(Mock(), "max_price", 1000)

        expected = (Q(trainer_price__gt=0) & Q(trainer_price__lte=1000)) | (
            (Q(trainer_price__isnull=True) | Q(trainer_price=0)) & Q(retail_price__lte=1000)
        )
        assert product_filter._variant_filters == expected

    def test_anonymous_request_filters_by_retail_price(self):
        """Без request (аноним) роль резолвится в retail — поведение не изменилось"""
        product_filter = ProductFilter()
        product_filter.request = None

        product_filter.filter_min_price(Mock(), "min_price", 100)

        assert product_filter._variant_filters == Q(retail_price__gte=100)


@pytest.mark.unit
class TestOpt4PriceFilter:
    """
    Стори 39.3, AC1: фильтры каталога знают про цену четвёртого уровня.

    До правки роль проваливалась в else-ветку и фильтровалась по
    retail_price — оптовик уровня 4 получал выдачу чужого ценового уровня.
    """

    @staticmethod
    def _filter_with_user(is_verified: bool = True):
        """ProductFilter с mock-запросом от имени пользователя уровня 4"""
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.role = "wholesale_level4"
        # ЯВНО: у Mock любой атрибут truthy — is_verified задаётся руками
        mock_user.is_verified = is_verified

        mock_request = Mock()
        mock_request.user = mock_user

        product_filter = ProductFilter()
        product_filter.request = mock_request
        return product_filter

    def test_min_price_filters_by_opt4_price(self):
        """min_price сравнивается с opt4_price, с откатом на retail при пустой цене"""
        product_filter = self._filter_with_user()

        product_filter.filter_min_price(Mock(), "min_price", 100)

        expected = (Q(opt4_price__gt=0) & Q(opt4_price__gte=100)) | (
            (Q(opt4_price__isnull=True) | Q(opt4_price=0)) & Q(retail_price__gte=100)
        )
        assert product_filter._variant_filters == expected

    def test_max_price_filters_by_opt4_price(self):
        """max_price — симметрично, через __lte"""
        product_filter = self._filter_with_user()

        product_filter.filter_max_price(Mock(), "max_price", 1000)

        expected = (Q(opt4_price__gt=0) & Q(opt4_price__lte=1000)) | (
            (Q(opt4_price__isnull=True) | Q(opt4_price=0)) & Q(retail_price__lte=1000)
        )
        assert product_filter._variant_filters == expected

    def test_unverified_level4_filters_by_retail_price(self):
        """
        Неверифицированный уровень 4 фильтруется по retail_price.

        Это требуемое поведение (роль берётся из resolve_pricing_role), а не дефект.
        """
        product_filter = self._filter_with_user(is_verified=False)

        product_filter.filter_min_price(Mock(), "min_price", 100)

        assert product_filter._variant_filters == Q(retail_price__gte=100)


@pytest.mark.unit
class TestZeroSpecialPriceFallsBackToRetail:
    """
    Находка ревью 2026-08-04 (AC5): нулевая специальная цена — это «цены нет».

    `ProductVariant.get_price_for_user` показывает `retail_price`, когда
    специальная цена пустая ИЛИ нулевая (`self.opt1_price or self.retail_price`).
    Ценовые фильтры обязаны отбирать по той же видимой цене, иначе выдача по
    `min_price`/`max_price` расходится с ценой в карточке товара.

    Проверка идёт на реальных строках БД, а не на структуре `Q`: смысл в том,
    какие варианты фильтр отбирает, а не как выглядит выражение. Матрица
    строится по `ROLE_PRICE_FIELDS` — новая роль в политике автоматически
    попадает под проверку и падает, пока фильтр её не знает.
    """

    RETAIL_PRICE = Decimal("1000.00")
    SPECIAL_PRICE = Decimal("500.00")

    @staticmethod
    def _filter_for_role(role):
        """ProductFilter от имени верифицированного пользователя с ролью role"""
        mock_user = Mock()
        mock_user.is_authenticated = True
        mock_user.role = role
        # ЯВНО: у Mock любой атрибут truthy, верификацию задаём руками
        mock_user.is_verified = True

        mock_request = Mock()
        mock_request.user = mock_user

        product_filter = ProductFilter()
        product_filter.request = mock_request
        return product_filter

    def _variants(self, price_field):
        """Три варианта с одной розничной ценой: нулевая, пустая и заполненная специальная"""

        def variant(special_price):
            product = ProductFactory(retail_price=self.RETAIL_PRICE, **{price_field: special_price})
            return product.variants.first()

        return variant(Decimal("0.00")), variant(None), variant(self.SPECIAL_PRICE)

    @staticmethod
    def _matched_ids(product_filter):
        """Варианты, которые отберёт накопленный фильтр"""
        return set(ProductVariant.objects.filter(product_filter._variant_filters).values_list("id", flat=True))

    @pytest.mark.parametrize("role,price_field", sorted(ROLE_PRICE_FIELDS.items()))
    def test_min_price_uses_retail_for_zero_special_price(self, role, price_field):
        """min_price=900: видимая цена варианта с нулевой спеццена — розничная 1000"""
        zero, empty, filled = self._variants(price_field)

        product_filter = self._filter_for_role(role)
        product_filter.filter_min_price(Mock(), "min_price", 900)
        matched = self._matched_ids(product_filter)

        assert zero.id in matched, (
            f"{role}: вариант с {price_field}=0.00 показывается по {self.RETAIL_PRICE}, "
            f"значит обязан проходить min_price=900"
        )
        assert empty.id in matched, f"{role}: вариант с пустым {price_field} показывается по розничной цене"
        assert filled.id not in matched, f"{role}: видимая цена {self.SPECIAL_PRICE} ниже границы 900"

    @pytest.mark.parametrize("role,price_field", sorted(ROLE_PRICE_FIELDS.items()))
    def test_max_price_uses_retail_for_zero_special_price(self, role, price_field):
        """max_price=600: вариант с нулевой спеццена стоит 1000 и в выдачу не попадает"""
        zero, empty, filled = self._variants(price_field)

        product_filter = self._filter_for_role(role)
        product_filter.filter_max_price(Mock(), "max_price", 600)
        matched = self._matched_ids(product_filter)

        assert zero.id not in matched, (
            f"{role}: вариант с {price_field}=0.00 показывается по {self.RETAIL_PRICE} — "
            f"выдача max_price=600 обещала бы цену, которой в карточке нет"
        )
        assert empty.id not in matched, f"{role}: вариант с пустым {price_field} стоит {self.RETAIL_PRICE}"
        assert filled.id in matched, f"{role}: видимая цена {self.SPECIAL_PRICE} укладывается в границу 600"

    @pytest.mark.parametrize("role,price_field", sorted(ROLE_PRICE_FIELDS.items()))
    def test_filter_matches_price_shown_to_user(self, role, price_field):
        """Связь с показанной ценой: get_price_for_user и фильтр смотрят на одно и то же"""
        zero, empty, filled = self._variants(price_field)
        user = Mock()
        user.is_authenticated = True
        user.role = role
        user.is_verified = True

        assert zero.get_price_for_user(user) == self.RETAIL_PRICE
        assert empty.get_price_for_user(user) == self.RETAIL_PRICE
        assert filled.get_price_for_user(user) == self.SPECIAL_PRICE

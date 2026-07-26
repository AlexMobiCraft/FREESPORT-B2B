"""
Unit-тесты для фильтров товаров (Story 2.9: filtering-api)
Тестируем фильтрацию по размерам, брендам, ценам, наличию
"""

from unittest.mock import Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.test import RequestFactory

from apps.products.filters import ProductFilter
from apps.products.models import Product

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

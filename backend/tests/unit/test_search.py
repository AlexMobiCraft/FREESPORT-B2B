"""
Unit тесты для search functionality (Story 2.8)
"""

from unittest.mock import Mock

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from apps.products.filters import ProductFilter
from apps.products.models import Product
from tests.factories import ProductFactory

User = get_user_model()


@pytest.mark.unit
class SearchFilterTest(TestCase):
    """Unit тесты для ProductFilter.filter_search"""

    def setUp(self):
        """Настройка тестовых данных"""
        # Товары для тестирования поиска
        self.products = [
            ProductFactory(
                name="Nike Phantom GT2 Elite FG",
                sku="NikePhantom001",
                short_description="Футбольные бутсы для профессионалов",
                description=("Высокотехнологичные футбольные бутсы Nike Phantom GT2 " "Elite FG"),
                retail_price=18999.00,
                stock_quantity=15,
                is_active=True,
            ),
            ProductFactory(
                name="Adidas Predator Freak",
                sku="AdidasPred001",
                short_description="Футбольная обувь Adidas",
                description="Adidas Predator Freak футбольные бутсы",
                retail_price=15999.00,
                stock_quantity=8,
                is_active=True,
            ),
            ProductFactory(
                name="Перчатки вратарские",
                sku="GKGloves001",
                short_description="Вратарские перчатки Nike",
                description="Профессиональные вратарские перчатки",
                retail_price=3999.00,
                stock_quantity=25,
                is_active=True,
            ),
        ]

    def test_search_validation_empty_query(self):
        """Тест валидации пустого поискового запроса"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "")

        self.assertEqual(list(result), list(queryset))

    def test_search_validation_short_query(self):
        """Тест валидации коротких запросов (< 2 символов)"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "N")

        self.assertEqual(list(result), list(queryset))

    def test_search_validation_long_query(self):
        """Тест валидации слишком длинных запросов (> 100 символов)"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        long_query = "x" * 101
        result = product_filter.filter_search(queryset, "search", long_query)

        self.assertEqual(list(result), [])

    def test_search_validation_xss_protection(self):
        """Тест защиты от XSS атак в поисковых запросах"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        xss_query = '<script>alert("xss")</script>'
        result = product_filter.filter_search(queryset, "search", xss_query)

        self.assertEqual(list(result), [])

    def test_search_by_name(self):
        """Тест поиска по названию товара"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "Nike")

        # Должны найтись товары с Nike в названии или описании
        result_names = [p.name for p in result]
        self.assertIn("Nike Phantom GT2 Elite FG", result_names)
        self.assertIn("Перчатки вратарские", result_names)  # Nike в описании

    def test_search_by_sku(self):
        """Тест поиска по артикулу (SKU)"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "Phantom")

        # Должен найтись товар с Phantom в артикуле или названии
        # У продуктов нет поля sku, проверяем через варианты
        result_has_sku = any(p.variants.filter(sku__icontains="Phantom").exists() for p in result)
        self.assertTrue(result_has_sku)

    def test_search_by_description(self):
        """Тест поиска по описанию"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "профессионалов")

        # Должен найтись товар с этим словом в описании
        result_names = [p.name for p in result]
        self.assertIn("Nike Phantom GT2 Elite FG", result_names)

    def test_search_case_insensitive(self):
        """Тест регистронезависимого поиска"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)

        # Поиск в разных регистрах должен давать одинаковые результаты
        result1 = list(product_filter.filter_search(queryset, "search", "nike"))
        result2 = list(product_filter.filter_search(queryset, "search", "NIKE"))
        result3 = list(product_filter.filter_search(queryset, "search", "Nike"))

        self.assertEqual(len(result1), len(result2))
        self.assertEqual(len(result2), len(result3))

    def test_search_russian_text(self):
        """Тест поиска русскоязычного текста"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "футбольные")

        # Должны найтись товары с русским текстом
        self.assertGreater(len(result), 0)
        result_descriptions = [p.short_description for p in result]
        self.assertTrue(any("футбольн" in desc.lower() for desc in result_descriptions))

    def test_search_no_results(self):
        """Тест поиска без результатов"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "несуществующий")

        self.assertEqual(len(result), 0)

    def test_search_inactive_products_excluded(self):
        """Тест исключения неактивных товаров из поиска"""
        # Деактивируем один товар
        self.products[0].is_active = False
        self.products[0].save()

        queryset = Product.objects.filter(is_active=True)
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = product_filter.filter_search(queryset, "search", "Nike")

        # Неактивный товар не должен попасть в результаты
        result_names = [p.name for p in result]
        self.assertNotIn("Nike Phantom GT2 Elite FG", result_names)
        self.assertIn("Перчатки вратарские", result_names)  # Активный товар

    def test_search_priority_ordering(self):
        """Тест приоритизации результатов поиска"""
        queryset = Product.objects.all()
        request = Mock()

        product_filter = ProductFilter(request=request)
        result = list(product_filter.filter_search(queryset, "search", "Nike"))

        # Результаты должны быть отсортированы по релевантности
        # Товары с Nike в названии должны быть выше, чем в описании
        self.assertGreater(len(result), 0)

        # Проверяем, что есть какая-то сортировка
        nike_in_name = [p for p in result if "Nike" in p.name]
        nike_in_desc_only = [p for p in result if "Nike" not in p.name and "Nike" in p.short_description]

        if nike_in_name and nike_in_desc_only:
            # Если есть товары обоих типов, товары с Nike в названии должны быть первыми
            first_nike_name_index = result.index(nike_in_name[0])
            first_desc_only_index = result.index(nike_in_desc_only[0])
            self.assertLess(first_nike_name_index, first_desc_only_index)

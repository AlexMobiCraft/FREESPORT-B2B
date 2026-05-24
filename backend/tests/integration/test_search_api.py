"""
Integration тесты для Search API (Story 2.8)
"""

import json

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.factories import ProductFactory, ProductVariantFactory
from apps.products.models import Brand, Category, Product

User = get_user_model()


@pytest.mark.integration
class SearchAPITest(TestCase):
    """Integration тесты для Search API endpoints"""

    def setUp(self):
        """Настройка тестовых данных"""
        self.client = APIClient()

        # Создаем тестовые объекты
        self.category1 = Category.objects.create(name="Футбольная обувь", slug="football-shoes", is_active=True)

        self.category2 = Category.objects.create(name="Спортивная одежда", slug="sports-clothing", is_active=True)

        self.brand_nike = Brand.objects.create(name="Nike", slug="nike", is_active=True)

        self.brand_adidas = Brand.objects.create(name="Adidas", slug="adidas", is_active=True)

        # Создаем тестовые товары для поиска
        self.products = [
            ProductVariantFactory.create(
                product__name="Nike Phantom GT2 Elite FG",
                sku="NIKE-PHT-001",
                product__short_description=("Футбольные бутсы для профессиональных игроков"),
                product__description=(
                    "Высокотехнологичные футбольные бутсы Nike Phantom " "GT2 Elite FG для профессионалов"
                ),
                product__brand=self.brand_nike,
                product__category=self.category1,
                retail_price=18999.00,
                opt1_price=15999.00,
                trainer_price=12999.00,
                stock_quantity=15,
                product__is_active=True,
            ).product,
            ProductVariantFactory.create(
                product__name="Adidas Predator Freak.1 FG",
                sku="ADIDAS-PRED-001",
                product__short_description="Футбольная обувь Adidas для атаки",
                product__description=("Adidas Predator Freak.1 FG футбольные бутсы с технологией " "Demonskin"),
                product__brand=self.brand_adidas,
                product__category=self.category1,
                retail_price=15999.00,
                opt1_price=13999.00,
                trainer_price=11999.00,
                stock_quantity=8,
                product__is_active=True,
            ).product,
            ProductVariantFactory.create(
                product__name="Футболка Nike Dri-FIT",
                sku="NIKE-SHIRT-001",
                product__short_description="Спортивная футболка Nike",
                product__description=("Легкая спортивная футболка Nike Dri-FIT для тренировок"),
                product__brand=self.brand_nike,
                product__category=self.category2,
                retail_price=3499.00,
                stock_quantity=50,
                product__is_active=True,
            ).product,
            ProductVariantFactory.create(
                product__name="Перчатки вратарские Nike",
                sku="NIKE-GK-001",
                product__short_description="Вратарские перчатки Nike Vapor Grip3",
                product__description=("Профессиональные вратарские перчатки Nike Vapor Grip3"),
                product__brand=self.brand_nike,
                product__category=self.category1,
                retail_price=4999.00,
                stock_quantity=25,
                product__is_active=True,
            ).product,
        ]

        # Создаем тестовых пользователей
        self.retail_user = User.objects.create_user(email="retail@test.com", password="testpass123", role="retail")

        self.trainer_user = User.objects.create_user(email="trainer@test.com", password="testpass123", role="trainer")

    def test_search_basic_functionality(self):
        """Тест базовой функциональности поиска"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Nike"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем структуру ответа
        self.assertIn("results", data)
        self.assertGreater(len(data["results"]), 0)

        # Проверяем, что все результаты содержат Nike
        for product in data["results"]:
            product_text = (
                product["name"] + " " + product.get("short_description", "") + " " + product.get("sku", "")
            ).lower()
            self.assertIn("nike", product_text)

    def test_search_by_name(self):
        """Тест поиска по названию товара"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Phantom"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["name"], "Nike Phantom GT2 Elite FG")

    def test_search_by_sku(self):
        """Тест поиска по артикулу (SKU)"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "PRED-001"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["sku"], "ADIDAS-PRED-001")

    def test_search_by_description(self):
        """Тест поиска по описанию"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "профессиональн"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertGreater(len(data["results"]), 0)
        # Проверяем, что найденные товары содержат слово в описании
        found_products = [p["name"] for p in data["results"]]
        self.assertIn("Nike Phantom GT2 Elite FG", found_products)

    def test_search_russian_language(self):
        """Тест поиска на русском языке"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "футбольные"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertGreater(len(data["results"]), 0)
        # Проверяем, что найдены товары с русскими словами
        for product in data["results"]:
            desc_text = (product.get("short_description", "") + " " + product.get("description", "")).lower()
            self.assertTrue("футбольн" in desc_text or "бутс" in desc_text)

    def test_search_case_insensitive(self):
        """Тест регистронезависимого поиска"""
        url = reverse("products:product-list")

        # Поиск в разных регистрах
        response1 = self.client.get(url, {"search": "nike"})
        response2 = self.client.get(url, {"search": "NIKE"})
        response3 = self.client.get(url, {"search": "Nike"})

        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response3.status_code, status.HTTP_200_OK)

        # Количество результатов должно быть одинаковым
        data1 = response1.json()
        data2 = response2.json()
        data3 = response3.json()

        self.assertEqual(len(data1["results"]), len(data2["results"]))
        self.assertEqual(len(data2["results"]), len(data3["results"]))

    def test_search_with_category_filter(self):
        """Тест комбинирования поиска с фильтром по категории"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Nike", "category_id": self.category1.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Должны найтись только Nike товары из категории "Футбольная обувь"
        expected_products = ["Nike Phantom GT2 Elite FG", "Перчатки вратарские Nike"]
        found_products = [p["name"] for p in data["results"]]

        for product_name in expected_products:
            self.assertIn(product_name, found_products)

        # Футболка Nike не должна попасть (другая категория)
        self.assertNotIn("Футболка Nike Dri-FIT", found_products)

    def test_search_with_brand_filter(self):
        """Тест комбинирования поиска с фильтром по бренду"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "футбольные", "brand": "adidas"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Должен найтись только Adidas товар
        self.assertEqual(len(data["results"]), 1)
        self.assertEqual(data["results"][0]["brand"]["slug"], "adidas")

    def test_search_with_price_filter(self):
        """Тест комбинирования поиска с фильтром по цене"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Nike", "min_price": 5000, "max_price": 20000})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем, что все найденные товары в ценовом диапазоне
        for product in data["results"]:
            price = float(product["current_price"])
            self.assertGreaterEqual(price, 5000)
            self.assertLessEqual(price, 20000)

    def test_search_role_based_pricing(self):
        """Тест ролевого ценообразования в результатах поиска"""
        url = reverse("products:product-list")

        # Поиск как retail пользователь
        response_retail = self.client.get(url, {"search": "Phantom"})

        # Поиск как trainer
        self.client.force_authenticate(user=self.trainer_user)
        response_trainer = self.client.get(url, {"search": "Phantom"})

        self.assertEqual(response_retail.status_code, status.HTTP_200_OK)
        self.assertEqual(response_trainer.status_code, status.HTTP_200_OK)

        retail_price = float(response_retail.json()["results"][0]["current_price"])
        trainer_price = float(response_trainer.json()["results"][0]["current_price"])

        # Цена для тренера должна быть ниже розничной
        self.assertLess(trainer_price, retail_price)

    def test_search_validation_empty_query(self):
        """Тест валидации пустого поискового запроса"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # При пустом запросе должны вернуться все активные товары
        self.assertEqual(len(data["results"]), 4)

    def test_search_validation_short_query(self):
        """Тест валидации коротких запросов"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "N"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # При коротком запросе должны вернуться все активные товары
        self.assertEqual(len(data["results"]), 4)

    def test_search_validation_long_query(self):
        """Тест валидации слишком длинных запросов"""
        url = reverse("products:product-list")
        long_query = "x" * 101
        response = self.client.get(url, {"search": long_query})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # При слишком длинном запросе не должно быть результатов
        self.assertEqual(len(data["results"]), 0)

    def test_search_xss_protection(self):
        """Тест защиты от XSS в поисковых запросах"""
        url = reverse("products:product-list")
        xss_query = '<script>alert("xss")</script>'
        response = self.client.get(url, {"search": xss_query})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # XSS запрос не должен вернуть результатов
        self.assertEqual(len(data["results"]), 0)

    def test_search_no_results(self):
        """Тест поиска без результатов"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "несуществующий_товар"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertEqual(len(data["results"]), 0)

    def test_search_inactive_products_excluded(self):
        """Тест исключения неактивных товаров из поиска"""
        # Деактивируем один товар
        self.products[0].is_active = False
        self.products[0].save()

        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Phantom"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Неактивный товар не должен найтись
        self.assertEqual(len(data["results"]), 0)

    def test_search_pagination(self):
        """Тест пагинации результатов поиска"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Nike", "page_size": 2})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем пагинацию
        self.assertIn("next", data)
        self.assertIn("previous", data)
        self.assertIn("count", data)
        self.assertLessEqual(len(data["results"]), 2)

    def test_search_performance(self):
        """Тест производительности поиска (базовая проверка)"""
        import time

        url = reverse("products:product-list")

        start_time = time.time()
        response = self.client.get(url, {"search": "Nike"})
        end_time = time.time()

        response_time = end_time - start_time

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Базовая проверка, что запрос выполняется быстро (< 1 сек для тестовых данных)
        self.assertLess(response_time, 1.0)

    def test_search_with_ordering(self):
        """Тест поиска с дополнительной сортировкой"""
        url = reverse("products:product-list")
        response = self.client.get(url, {"search": "Nike", "ordering": "min_retail_price"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем, что результаты отсортированы по цене
        if len(data["results"]) > 1:
            prices = [float(p["current_price"]) for p in data["results"]]
            self.assertEqual(prices, sorted(prices))

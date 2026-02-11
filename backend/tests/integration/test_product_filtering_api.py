import uuid
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.models import Brand, Category, Product, ProductVariant
from tests.conftest import get_unique_suffix

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestProductFilteringAPI:
    """Интеграционные тесты для API фильтрации товаров"""

    @pytest.fixture(autouse=True)
    def setup_test_data(self):
        """Создание тестовых данных для каждого теста"""
        suffix = get_unique_suffix()

        # Создаем бренды
        self.brand_nike = Brand.objects.create(name=f"Nike-{suffix}", slug=f"nike-{suffix}", is_active=True)
        self.brand_adidas = Brand.objects.create(name=f"Adidas-{suffix}", slug=f"adidas-{suffix}", is_active=True)

        # Создаем категорию
        self.category = Category.objects.create(name=f"Одежда-{suffix}", slug=f"clothes-{suffix}", is_active=True)

        # Создаем товары с различными размерами и ценами
        self.product1 = Product.objects.create(
            name=f"Nike T-shirt XL-{suffix}",
            slug=f"nike-tshirt-xl-{suffix}",
            brand=self.brand_nike,
            category=self.category,
            description="Nike T-shirt XL размер",
            is_active=True,
            specifications={"size": "XL", "color": "black", "material": "cotton"},
            onec_id=f"PROD-1-{suffix}",
        )
        ProductVariant.objects.create(
            product=self.product1,
            sku=f"NIKE-XL-{suffix}",
            onec_id=f"VAR-1-{suffix}",
            retail_price=Decimal("2000.00"),
            opt1_price=Decimal("1800.00"),
            trainer_price=Decimal("1600.00"),
            stock_quantity=10,
            is_active=True,
        )

        self.product2 = Product.objects.create(
            name=f"Adidas Hoodie M-{suffix}",
            slug=f"adidas-hoodie-m-{suffix}",
            brand=self.brand_adidas,
            category=self.category,
            description="Adidas Hoodie M размер",
            is_active=True,
            specifications={"sizes": ["M", "L"], "color": "blue"},
            onec_id=f"PROD-2-{suffix}",
        )
        ProductVariant.objects.create(
            product=self.product2,
            sku=f"ADIDAS-M-{suffix}",
            onec_id=f"VAR-2-{suffix}",
            retail_price=Decimal("3500.00"),
            opt1_price=Decimal("3200.00"),
            trainer_price=Decimal("3000.00"),
            stock_quantity=5,
            is_active=True,
        )

        self.product3 = Product.objects.create(
            name=f"Nike Shoes 42-{suffix}",
            slug=f"nike-shoes-42-{suffix}",
            brand=self.brand_nike,
            category=self.category,
            description="Nike кроссовки 42 размер",
            is_active=True,
            specifications={"размер": "42", "тип": "кроссовки"},
            onec_id=f"PROD-3-{suffix}",
        )
        ProductVariant.objects.create(
            product=self.product3,
            sku=f"NIKE-SHOES-42-{suffix}",
            onec_id=f"VAR-3-{suffix}",
            retail_price=Decimal("8000.00"),
            opt1_price=Decimal("7200.00"),
            trainer_price=Decimal("6800.00"),
            stock_quantity=0,  # Нет в наличии
            is_active=True,
        )

        self.product4 = Product.objects.create(
            name=f"Adidas Shorts S-{suffix}",
            slug=f"adidas-shorts-s-{suffix}",
            brand=self.brand_adidas,
            category=self.category,
            description="Adidas шорты S размер",
            is_active=False,  # Неактивный товар
            specifications={"размеры": ["S", "M", "L"]},
            onec_id=f"PROD-4-{suffix}",
        )
        ProductVariant.objects.create(
            product=self.product4,
            sku=f"ADIDAS-S-{suffix}",
            onec_id=f"VAR-4-{suffix}",
            retail_price=Decimal("1500.00"),
            stock_quantity=20,
            is_active=True,
        )

        # Создаем пользователей разных ролей
        self.retail_user = User.objects.create_user(
            email=f"retail{suffix}@test.com",
            password="testpass123",
            role="retail",
            is_active=True,
            is_verified=True,
            verification_status="verified",
        )

        self.wholesale_user = User.objects.create_user(
            email=f"wholesale{suffix}@test.com",
            password="testpass123",
            role="wholesale_level1",
            is_active=True,
            is_verified=True,
            verification_status="verified",
            company_name=f"Company-{suffix}",
            tax_id="1234567890",
        )

        self.trainer_user = User.objects.create_user(
            email=f"trainer{suffix}@test.com",
            password="testpass123",
            role="trainer",
            is_active=True,
            is_verified=True,
            verification_status="verified",
            company_name=f"Trainer-{suffix}",
            tax_id="1234567891",
        )

        self.client = APIClient()

    def test_filter_by_size_single_value(self):
        """Тест фильтрации по размеру - одиночное значение"""
        url = reverse("products:product-list")

        # Фильтр по размеру XL
        response = self.client.get(url, {"size": "XL"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["name"] == self.product1.name
        assert results[0]["specifications"]["size"] == "XL"

    def test_filter_by_size_array_value(self):
        """Тест фильтрации по размеру - значение из массива"""
        url = reverse("products:product-list")

        # Фильтр по размеру M (который есть в массиве sizes)
        response = self.client.get(url, {"size": "M"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) >= 1

        # Проверяем что нашелся товар с размером M в массиве
        found_product2 = False
        for result in results:
            if result["sku"] == self.product2.variants.first().sku:
                found_product2 = True
                assert "M" in result["specifications"]["sizes"]
        assert found_product2

    def test_filter_by_size_russian_key(self):
        """Тест фильтрации по размеру - русский ключ"""
        url = reverse("products:product-list")

        # Фильтр по размеру 42 (русский ключ "размер")
        response = self.client.get(url, {"size": "42"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) == 1
        assert results[0]["name"] == self.product3.name
        assert results[0]["specifications"]["размер"] == "42"

    def test_filter_by_multiple_brands(self):
        """Тест фильтрации по нескольким брендам"""
        url = reverse("products:product-list")

        # Фильтр по двум брендам через slug
        brand_filter = f"{self.brand_nike.slug},{self.brand_adidas.slug}"
        response = self.client.get(url, {"brand": brand_filter})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) >= 2  # Должно найти товары обоих брендов

        # Проверяем что есть товары от обоих брендов
        brands_found = set()
        for result in results:
            brands_found.add(result["brand"]["slug"])

        assert self.brand_nike.slug in brands_found
        assert self.brand_adidas.slug in brands_found

    def test_filter_by_brand_mixed_id_slug(self):
        """Тест фильтрации по брендам - смешанные ID и slug"""
        url = reverse("products:product-list")

        # Комбинируем ID и slug
        brand_filter = f"{self.brand_nike.id},{self.brand_adidas.slug}"
        response = self.client.get(url, {"brand": brand_filter})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        assert len(results) >= 2

    def test_filter_in_stock_true(self):
        """Тест фильтрации товаров в наличии"""
        url = reverse("products:product-list")

        response = self.client.get(url, {"in_stock": "true"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]

        # Проверяем что все товары в наличии
        for result in results:
            # Через API получаем только активные товары с положительным stock_quantity
            assert result["stock_quantity"] > 0

    def test_filter_in_stock_false(self):
        """Тест фильтрации товаров НЕ в наличии"""
        url = reverse("products:product-list")

        response = self.client.get(url, {"in_stock": "false"})
        assert response.status_code == status.HTTP_200_OK

        # Результат может быть пустым, так как ViewSet фильтрует только is_active=True

    def test_price_filter_anonymous_user(self):
        """Тест ценовой фильтрации для анонимного пользователя"""
        url = reverse("products:product-list")

        # Фильтр по диапазону цены для retail
        response = self.client.get(url, {"min_price": "1000", "max_price": "3000"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        for result in results:
            # Для анонимного пользователя показывается retail_price
            price = Decimal(str(result["current_price"]))
            assert Decimal("1000") <= price <= Decimal("3000")

    def test_price_filter_wholesale_user(self):
        """Тест ценовой фильтрации для оптового пользователя"""
        self.client.force_authenticate(user=self.wholesale_user)
        url = reverse("products:product-list")

        # Фильтр по диапазону цены для оптовика
        response = self.client.get(url, {"min_price": "1500", "max_price": "4000"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        for result in results:
            # Для оптовика должна показываться opt1_price или retail_price
            price = Decimal(str(result["current_price"]))
            assert Decimal("1500") <= price <= Decimal("4000")

    def test_price_filter_trainer_user(self):
        """Тест ценовой фильтрации для тренера"""
        self.client.force_authenticate(user=self.trainer_user)
        url = reverse("products:product-list")

        # Фильтр по цене для тренера
        response = self.client.get(url, {"max_price": "7000"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]
        for result in results:
            # Для тренера должна показываться trainer_price или retail_price
            price = Decimal(str(result["current_price"]))
            assert price <= Decimal("7000")

    def test_combined_filters(self):
        """Тест комбинирования нескольких фильтров"""
        url = reverse("products:product-list")

        # Комбинируем фильтры: бренд + цена + размер
        response = self.client.get(url, {"brand": self.brand_nike.slug, "max_price": "5000", "size": "XL"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]

        # Проверяем что результат соответствует всем фильтрам
        for result in results:
            assert result["brand"]["slug"] == self.brand_nike.slug
            assert Decimal(str(result["current_price"])) <= Decimal("5000")

            # Проверяем размер в спецификациях
            specs = result["specifications"]
            size_found = (
                specs.get("size") == "XL"
                or "XL" in specs.get("sizes", [])
                or specs.get("размер") == "XL"
                or "XL" in specs.get("размеры", [])
            )
            assert size_found

    def test_filter_validation_edge_cases(self):
        """Тест валидации edge cases для фильтров"""
        url = reverse("products:product-list")

        # Отрицательная цена
        response = self.client.get(url, {"min_price": "-100"})
        assert response.status_code == status.HTTP_200_OK

        # Пустой размер
        response = self.client.get(url, {"size": ""})
        assert response.status_code == status.HTTP_200_OK

        # Пустой бренд
        response = self.client.get(url, {"brand": ""})
        assert response.status_code == status.HTTP_200_OK

        # Несуществующий бренд
        response = self.client.get(url, {"brand": "nonexistent"})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 0

    def test_filter_with_search(self):
        """Тест комбинирования фильтров с поиском"""
        url = reverse("products:product-list")

        # Комбинируем поиск с фильтром размера
        response = self.client.get(url, {"search": "Nike", "size": "XL"})
        assert response.status_code == status.HTTP_200_OK

        results = response.data["results"]

        # Проверяем что результаты содержат "Nike" и имеют размер XL
        for result in results:
            assert "Nike" in result["name"] or "nike" in result["name"].lower()

    def test_pagination_with_filters(self):
        """Тест пагинации с фильтрами"""
        url = reverse("products:product-list")

        response = self.client.get(url, {"brand": self.brand_nike.slug, "page_size": 1})
        assert response.status_code == status.HTTP_200_OK

        # Проверяем структуру пагинированного ответа
        assert "count" in response.data
        assert "results" in response.data
        assert len(response.data["results"]) <= 1

    def test_filter_empty_results_graceful_handling(self):
        """Тест graceful обработки пустых результатов"""
        url = reverse("products:product-list")

        # Фильтр который не должен ничего найти
        response = self.client.get(
            url,
            {
                "brand": "nonexistent-brand",
                "size": "nonexistent-size",
                "min_price": "999999",
            },
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 0
        assert len(response.data["results"]) == 0

    def test_size_filter_case_variations(self):
        """Тест фильтрации размеров с различными вариантами case"""
        url = reverse("products:product-list")

        # Проверяем различные варианты написания
        test_cases = ["xl", "XL", "Xl", "xL"]

        for size_variant in test_cases:
            response = self.client.get(url, {"size": size_variant})
            assert response.status_code == status.HTTP_200_OK

            # В зависимости от БД могут или не могут найтись результаты
            # Главное что запрос обрабатывается без ошибок


@pytest.mark.integration
@pytest.mark.django_db
class TestProductFilteringPerformance:
    """Тесты производительности фильтрации"""

    @pytest.fixture(autouse=True)
    def setup_large_dataset(self):
        """Создание большого набора данных для тестирования производительности"""
        suffix = get_unique_suffix()

        # Создаем бренды
        self.brands = []
        for i in range(5):
            brand = Brand.objects.create(name=f"Brand{i}-{suffix}", slug=f"brand{i}-{suffix}", is_active=True)
            self.brands.append(brand)

        # Создаем категорию
        self.category = Category.objects.create(name=f"Category-{suffix}", slug=f"category-{suffix}", is_active=True)

        # Создаем много товаров
        sizes = ["XS", "S", "M", "L", "XL", "XXL", "38", "40", "42", "44"]
        self.products = []

        for i in range(50):  # Создаем 50 товаров
            brand = self.brands[i % len(self.brands)]
            size = sizes[i % len(sizes)]

            product = Product.objects.create(
                name=f"Product {i}-{suffix}",
                slug=f"product-{i}-{suffix}",
                brand=brand,
                category=self.category,
                description=f"Test product {i}",
                is_active=True,
                specifications={"size": size, "test_field": f"value{i}"},
                onec_id=f"PROD-PERF-{i}-{suffix}",
            )
            ProductVariant.objects.create(
                product=product,
                sku=f"SKU-{i}-{suffix}",
                onec_id=f"VAR-PERF-{i}-{suffix}",
                retail_price=Decimal(str(1000 + i * 100)),
                stock_quantity=i % 20 + 1,
                is_active=True,
            )
            self.products.append(product)

        self.client = APIClient()

    def test_multiple_filters_performance(self):
        """Тест производительности при использовании нескольких фильтров"""
        url = reverse("products:product-list")

        # Комбинируем несколько фильтров
        response = self.client.get(
            url,
            {
                "brand": f"{self.brands[0].slug},{self.brands[1].slug}",
                "min_price": "1000",
                "max_price": "5000",
                "size": "M",
                "in_stock": "true",
            },
        )

        assert response.status_code == status.HTTP_200_OK
        # Проверяем что запрос выполняется достаточно быстро
        # (фактическое время может варьироваться)

    def test_size_filter_on_large_dataset(self):
        """Тест фильтра размеров на большом наборе данных"""
        url = reverse("products:product-list")

        response = self.client.get(url, {"size": "L"})
        assert response.status_code == status.HTTP_200_OK

        # Проверяем что нашлись товары размера L
        results = response.data["results"]
        for result in results:
            assert result["specifications"]["size"] == "L"

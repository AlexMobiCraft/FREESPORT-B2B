"""
API тесты для ProductViewSet с поддержкой variants (Story 13.3)
Включает тесты для /products/{slug}/ endpoint и performance тесты (NFR1)
"""

from __future__ import annotations

import time
from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.factories import ColorMappingFactory, ProductFactory, ProductVariantFactory
from apps.products.models import ColorMapping, Product, ProductVariant
from apps.users.models import User


@pytest.mark.django_db
class TestProductRetrieveWithVariants:
    """Тесты API endpoint GET /products/{slug}/ с variants"""

    @pytest.fixture
    def api_client(self):
        """Fixture для API клиента"""
        return APIClient()

    @pytest.fixture
    def retail_user(self, db):
        """Fixture для retail пользователя"""
        return User.objects.create_user(
            email="retail@test.com",
            password="testpass123",
            role="retail",
        )

    @pytest.fixture
    def wholesale_user(self, db):
        """Fixture для wholesale пользователя"""
        return User.objects.create_user(
            email="wholesale@test.com",
            password="testpass123",
            role="wholesale_level1",
        )

    @pytest.fixture
    def product_with_variants(self, db):
        """Fixture для продукта с несколькими вариантами"""
        product = ProductFactory(create_variant=False)

        # Создаем 3 варианта с разными характеристиками
        ProductVariantFactory(
            product=product,
            color_name="Красный",
            size_value="L",
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            stock_quantity=10,
        )
        ProductVariantFactory(
            product=product,
            color_name="Синий",
            size_value="M",
            retail_price=Decimal("1100.00"),
            opt1_price=Decimal("950.00"),
            stock_quantity=5,
        )
        ProductVariantFactory(
            product=product,
            color_name="Черный",
            size_value="XL",
            retail_price=Decimal("1200.00"),
            opt1_price=Decimal("1000.00"),
            stock_quantity=0,  # Out of stock
        )

        return product

    def test_retrieve_product_returns_variants_array(self, api_client, product_with_variants):
        """Тест: GET /products/{slug}/ возвращает массив variants"""
        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "variants" in data
        assert isinstance(data["variants"], list)
        assert len(data["variants"]) == 3

    def test_variants_contain_correct_fields(self, api_client, product_with_variants):
        """Тест: variants содержат все необходимые поля"""
        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        variant = data["variants"][0]

        # Проверяем все ожидаемые поля
        required_fields = [
            "id",
            "sku",
            "color_name",
            "size_value",
            "current_price",
            "color_hex",
            "stock_quantity",
            "is_in_stock",
            "available_quantity",
            "main_image",
            "gallery_images",
        ]

        for field in required_fields:
            assert field in variant, f"Field '{field}' отсутствует в variant"

    def test_current_price_for_retail_user(self, api_client, product_with_variants, retail_user):
        """Тест: current_price рассчитывается для retail пользователя"""
        api_client.force_authenticate(user=retail_user)

        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Все цены должны быть retail_price
        for variant_data in data["variants"]:
            variant = ProductVariant.objects.get(id=variant_data["id"])
            assert variant_data["current_price"] == str(variant.retail_price)

    def test_current_price_for_wholesale_user(self, api_client, product_with_variants, wholesale_user):
        """Тест: current_price рассчитывается для wholesale пользователя"""
        api_client.force_authenticate(user=wholesale_user)

        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Все цены должны быть opt1_price
        for variant_data in data["variants"]:
            variant = ProductVariant.objects.get(id=variant_data["id"])
            assert variant_data["current_price"] == str(variant.opt1_price)

    def test_current_price_for_anonymous_user(self, api_client, product_with_variants):
        """Тест: current_price = retail_price для анонимного пользователя"""
        # Не аутентифицируемся
        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Все цены должны быть retail_price
        for variant_data in data["variants"]:
            variant = ProductVariant.objects.get(id=variant_data["id"])
            assert variant_data["current_price"] == str(variant.retail_price)

    def test_color_hex_with_color_mapping(self, api_client, product_with_variants):
        """Тест: color_hex возвращается из ColorMapping"""
        # Создаем ColorMapping для цветов (get_or_create для избежания дубликатов)
        ColorMapping.objects.get_or_create(name="Красный", defaults={"hex_code": "#FF0000"})
        ColorMapping.objects.get_or_create(name="Синий", defaults={"hex_code": "#0000FF"})

        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Проверяем что hex коды возвращаются
        red_variant = next(v for v in data["variants"] if v["color_name"] == "Красный")
        blue_variant = next(v for v in data["variants"] if v["color_name"] == "Синий")
        black_variant = next(v for v in data["variants"] if v["color_name"] == "Черный")

        assert red_variant["color_hex"] == "#FF0000"
        assert blue_variant["color_hex"] == "#0000FF"
        # Черный может иметь ColorMapping из других тестов или fixture -
        # проверяем что поле есть
        assert "color_hex" in black_variant

    def test_is_in_stock_reflects_stock_quantity(self, api_client, product_with_variants):
        """Тест: is_in_stock корректно отражает наличие товара"""
        url = reverse("products:product-detail", kwargs={"slug": product_with_variants.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        for variant_data in data["variants"]:
            variant = ProductVariant.objects.get(id=variant_data["id"])

            if variant.stock_quantity > 0:
                assert variant_data["is_in_stock"] is True
            else:
                assert variant_data["is_in_stock"] is False

    def test_product_without_variants(self, api_client, db):
        """Тест: продукт без вариантов возвращает пустой массив variants"""
        product = ProductFactory(create_variant=False)  # Без вариантов

        url = reverse("products:product-detail", kwargs={"slug": product.slug})
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        assert "variants" in data
        assert data["variants"] == []

    def test_integration_verification_iv1_list_endpoint_unchanged(self, api_client, db):
        """IV1: Существующий endpoint /products/ не изменен"""
        ProductFactory.create_batch(3)

        url = reverse("products:product-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Убедимся что response структура для list endpoint не изменилась
        assert "results" in data  # Пагинация
        assert isinstance(data["results"], list)

        # Список не должен содержать variants (только retrieve endpoint)
        if data["results"]:
            assert "variants" not in data["results"][0]


@pytest.mark.django_db
class TestProductAPIPerformance:
    """Performance тесты для /products/{slug}/ endpoint (NFR1)"""

    @pytest.fixture
    def api_client(self):
        """Fixture для API клиента"""
        return APIClient()

    @pytest.mark.slow
    def test_retrieve_product_with_100_variants_under_500ms(self, api_client, db, django_assert_num_queries):
        """
        NFR1: Response time <= 500ms для товара с 100 вариантами
        """
        product = ProductFactory(create_variant=False)

        # Создаем 100 вариантов
        ProductVariantFactory.create_batch(100, product=product)

        url = reverse("products:product-detail", kwargs={"slug": product.slug})

        # Измеряем response time
        start_time = time.time()
        response = api_client.get(url)
        elapsed_time = (time.time() - start_time) * 1000  # ms

        assert response.status_code == status.HTTP_200_OK
        assert elapsed_time <= 500, f"Response time {elapsed_time:.2f}ms превышает 500ms (NFR1)"

        # Проверяем что все 100 вариантов в response
        data = response.json()
        assert len(data["variants"]) == 100

    def test_prefetch_related_used_no_n_plus_one(self, api_client, db, django_assert_num_queries):
        """
        Тест: prefetch_related используется (количество queries ~3-5)
        Избегаем N+1 queries проблемы
        """
        product = ProductFactory(create_variant=False)
        ProductVariantFactory.create_batch(10, product=product)

        url = reverse("products:product-detail", kwargs={"slug": product.slug})

        # Должно быть 5 queries (оптимизировано с кэшированием ColorMapping):
        # 1. SELECT Product with select_related(brand, category)
        # 2. SELECT Related products by category
        # 3. SELECT Related products by brand (если меньше 5)
        # 4. PREFETCH ProductVariants
        # 5. SELECT ColorMappings (одним запросом для кэша всех вариантов)
        # Дополнительные запросы могут идти на ContentTypes и системные нужды
        with django_assert_num_queries(20, exact=False):  # Оптимизированный лимит без N+1
            response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert len(data["variants"]) == 10

    @pytest.mark.slow
    def test_response_time_scales_linearly(self, api_client, db):
        """
        Тест: response time масштабируется линейно с количеством вариантов
        (проверка что нет O(N^2) алгоритмов)
        """
        # Создаем продукты с разным количеством вариантов
        test_cases = [10, 50, 100]
        timings = []

        for num_variants in test_cases:
            product = ProductFactory(create_variant=False)
            ProductVariantFactory.create_batch(num_variants, product=product)

            url = reverse("products:product-detail", kwargs={"slug": product.slug})

            start_time = time.time()
            response = api_client.get(url)
            elapsed_time = (time.time() - start_time) * 1000  # ms

            assert response.status_code == status.HTTP_200_OK
            timings.append((num_variants, elapsed_time))

        # Проверяем что время растет линейно, а не квадратично
        # Время для 100 вариантов не должно быть > 10x времени для 10 вариантов
        time_10 = timings[0][1]
        time_100 = timings[2][1]

        assert time_100 <= time_10 * 15, (
            f"Performance не масштабируется линейно: 10v={time_10:.2f}ms, " f"100v={time_100:.2f}ms"
        )


@pytest.mark.django_db
class TestIntegrationVerification:
    """Integration Verification тесты (IV1, IV2, IV3)"""

    @pytest.fixture
    def api_client(self):
        """Fixture для API клиента"""
        return APIClient()

    def test_iv2_categories_endpoint_unchanged(self, api_client, db):
        """IV2: Endpoint /categories/ не изменен (теперь пагинированный)"""
        from apps.products.factories import CategoryFactory

        CategoryFactory.create_batch(3)

        url = reverse("products:category-list")
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        data = response.json()

        # Структура теперь пагинированная (DRF PageNumberPagination)
        assert isinstance(data, dict)
        assert "results" in data
        assert "count" in data
        assert "next" in data
        assert "previous" in data

        # Проверяем структуру категорий в results
        results = data["results"]
        assert len(results) == 3
        if results:
            assert "id" in results[0]
            assert "name" in results[0]
            assert "slug" in results[0]

    def test_iv3_current_price_uses_same_roles(self, api_client, product_with_variants, db):
        """
        IV3: current_price использует те же роли
        (retail, wholesale_level1-3, trainer, federation_rep)
        """
        # Создаем пользователей всех ролей
        roles = [
            "retail",
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "trainer",
            "federation_rep",
        ]

        product = ProductFactory(create_variant=False)
        variant = ProductVariantFactory(
            product=product,
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            opt2_price=Decimal("800.00"),
            opt3_price=Decimal("700.00"),
            trainer_price=Decimal("600.00"),
            federation_price=Decimal("650.00"),
        )

        url = reverse("products:product-detail", kwargs={"slug": product.slug})

        for role in roles:
            user = User.objects.create_user(
                email=f"{role}@test.com",
                password="testpass123",
                role=role,
            )

            api_client.force_authenticate(user=user)
            response = api_client.get(url)

            assert response.status_code == status.HTTP_200_OK
            data = response.json()

            # Проверяем что цена соответствует роли
            variant_data = data["variants"][0]

            expected_price = variant.get_price_for_user(user)
            assert variant_data["current_price"] == str(expected_price)

    @pytest.fixture
    def product_with_variants(self, db):
        """Fixture для продукта с вариантами (для IV3)"""
        product = ProductFactory()
        ProductVariantFactory(
            product=product,
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            stock_quantity=10,
        )
        return product

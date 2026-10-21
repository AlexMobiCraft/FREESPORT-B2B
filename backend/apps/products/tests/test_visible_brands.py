"""
Тесты для ProductViewSet.visible_brands action.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from apps.products.factories import BrandFactory, CategoryFactory, ProductFactory, ProductVariantFactory
from apps.products.views import ProductViewSet


@pytest.mark.django_db
@pytest.mark.integration
class TestVisibleBrandsAction:
    """GET /products/visible-brands/."""

    @pytest.fixture(autouse=True)
    def clear_cache(self):
        cache.clear()

    @pytest.fixture
    def client(self):
        return APIClient()

    @pytest.fixture
    def url(self):
        return reverse("products:product-visible-brands")

    @pytest.fixture
    def brand_nike(self):
        return BrandFactory(name="Nike", slug="nike")

    @pytest.fixture
    def brand_adidas(self):
        return BrandFactory(name="Adidas", slug="adidas")

    @pytest.fixture
    def brand_puma(self):
        return BrandFactory(name="Puma", slug="puma")

    @pytest.fixture
    def cat_football(self):
        return CategoryFactory(name="Футбол", slug="football")

    @pytest.fixture
    def cat_boots(self, cat_football):
        return CategoryFactory(name="Бутсы", slug="boots", parent=cat_football)

    @pytest.fixture
    def cat_running(self):
        return CategoryFactory(name="Бег", slug="running")

    def test_returns_brand_ids_for_in_stock_products(self, client, url, brand_nike, brand_adidas, cat_football):
        nike_product = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        adidas_product = ProductFactory(brand=brand_adidas, category=cat_football, create_variant=False)
        ProductVariantFactory(product=nike_product, stock_quantity=3, retail_price=Decimal("1000"))
        ProductVariantFactory(product=adidas_product, stock_quantity=4, retail_price=Decimal("1500"))

        resp = client.get(url, {"in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.data["brand_ids"]) == {brand_nike.id, brand_adidas.id}

    def test_filter_by_category_id_returns_only_relevant_brands(
        self, client, url, brand_nike, brand_adidas, cat_football, cat_boots, cat_running
    ):
        nike_product = ProductFactory(brand=brand_nike, category=cat_boots, create_variant=False)
        adidas_product = ProductFactory(brand=brand_adidas, category=cat_running, create_variant=False)
        ProductVariantFactory(product=nike_product, stock_quantity=3, retail_price=Decimal("1000"))
        ProductVariantFactory(product=adidas_product, stock_quantity=4, retail_price=Decimal("1500"))

        resp = client.get(url, {"category_id": cat_football.id, "in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_nike.id]

    def test_returns_empty_brand_ids_for_nonexistent_category_id(self, client, url, brand_nike, cat_football):
        product = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        ProductVariantFactory(product=product, stock_quantity=3, retail_price=Decimal("1000"))

        resp = client.get(url, {"category_id": 999999, "in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == []

    def test_ignores_brand_param(self, client, url, brand_nike, brand_adidas, cat_football):
        nike_product = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        adidas_product = ProductFactory(brand=brand_adidas, category=cat_football, create_variant=False)
        ProductVariantFactory(product=nike_product, stock_quantity=3, retail_price=Decimal("1200"))
        ProductVariantFactory(product=adidas_product, stock_quantity=4, retail_price=Decimal("1400"))

        resp = client.get(url, {"brand": "nike", "min_price": "1000"})

        assert resp.status_code == status.HTTP_200_OK
        assert set(resp.data["brand_ids"]) == {brand_nike.id, brand_adidas.id}

    def test_filter_by_min_price(self, client, url, brand_nike, brand_adidas, cat_football):
        cheap = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        expensive = ProductFactory(brand=brand_adidas, category=cat_football, create_variant=False)
        ProductVariantFactory(product=cheap, stock_quantity=3, retail_price=Decimal("500"))
        ProductVariantFactory(product=expensive, stock_quantity=4, retail_price=Decimal("1500"))

        resp = client.get(url, {"min_price": "1000"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_adidas.id]

    def test_filter_by_max_price(self, client, url, brand_nike, brand_adidas, cat_football):
        cheap = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        expensive = ProductFactory(brand=brand_adidas, category=cat_football, create_variant=False)
        ProductVariantFactory(product=cheap, stock_quantity=3, retail_price=Decimal("500"))
        ProductVariantFactory(product=expensive, stock_quantity=4, retail_price=Decimal("1500"))

        resp = client.get(url, {"max_price": "1000"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_nike.id]

    def test_filter_by_in_stock(self, client, url, brand_nike, brand_adidas, cat_football):
        in_stock = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        out_of_stock = ProductFactory(brand=brand_adidas, category=cat_football, create_variant=False)
        ProductVariantFactory(product=in_stock, stock_quantity=3, retail_price=Decimal("1000"))
        ProductVariantFactory(product=out_of_stock, stock_quantity=0, retail_price=Decimal("1500"))

        resp = client.get(url, {"in_stock": "true"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_nike.id]

    def test_filter_by_search(self, client, url, brand_nike, brand_adidas, cat_football):
        nike_product = ProductFactory(
            name="Mercurial Boots", brand=brand_nike, category=cat_football, create_variant=False
        )
        adidas_product = ProductFactory(
            name="Running Jersey", brand=brand_adidas, category=cat_football, create_variant=False
        )
        ProductVariantFactory(product=nike_product, stock_quantity=3, retail_price=Decimal("1000"))
        ProductVariantFactory(product=adidas_product, stock_quantity=4, retail_price=Decimal("1500"))

        resp = client.get(url, {"search": "Mercurial"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_nike.id]

    def test_excludes_brand_id_null_for_products_without_brand(self, client, url, brand_nike, monkeypatch):
        class FakeVisibleBrandsQuerySet:
            def __init__(self, brand_ids):
                self.brand_ids = brand_ids

            def exclude(self, **kwargs):
                assert kwargs == {"brand_id__isnull": True}
                self.brand_ids = [brand_id for brand_id in self.brand_ids if brand_id is not None]
                return self

            def order_by(self, *args):
                assert args == ()
                return self

            def values_list(self, *fields, **kwargs):
                assert fields == ("brand_id",)
                assert kwargs == {"flat": True}
                return self

            def distinct(self):
                result = []
                for brand_id in self.brand_ids:
                    if brand_id not in result:
                        result.append(brand_id)
                return result

        class FakeProductFilter:
            def __init__(self, params, queryset):
                self.qs = FakeVisibleBrandsQuerySet([brand_nike.id, None, brand_nike.id])

        monkeypatch.setattr(ProductViewSet, "filterset_class", FakeProductFilter)

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == [brand_nike.id]
        assert None not in resp.data["brand_ids"]

    def test_empty_result_when_filters_exclude_all_products(self, client, url, brand_nike, cat_football):
        product = ProductFactory(brand=brand_nike, category=cat_football, create_variant=False)
        ProductVariantFactory(product=product, stock_quantity=3, retail_price=Decimal("1000"))

        resp = client.get(url, {"min_price": "999999"})

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"] == []

    def test_returns_distinct_brand_ids_no_duplicates(self, client, url, brand_nike, cat_football):
        for idx in range(3):
            product = ProductFactory(
                name=f"Nike Product {idx}", brand=brand_nike, category=cat_football, create_variant=False
            )
            ProductVariantFactory(product=product, stock_quantity=idx + 1, retail_price=Decimal("1000"))

        resp = client.get(url)

        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["brand_ids"].count(brand_nike.id) == 1

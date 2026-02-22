from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor

User = get_user_model()


@pytest.fixture
def product():
    brand = Brand.objects.create(name="TestBrand", slug="test-brand")
    category = Category.objects.create(name="TestCat", slug="test-cat")
    return Product.objects.create(
        name="Test Product",
        slug="test-product",
        brand=brand,
        category=category,
        onec_id="prod1",
    )


@pytest.fixture
def variant(product):
    return ProductVariant.objects.create(
        product=product,
        sku="SKU-1",
        onec_id="var1",
        retail_price=Decimal("100.00"),
        stock_quantity=10,
    )


@pytest.fixture
def import_session():
    return ImportSession.objects.create(import_type="prices")


@pytest.fixture
def processor(import_session):
    return VariantImportProcessor(session_id=import_session.id)


@pytest.mark.django_db
class TestPriceImportLogic:
    def test_rrp_auto_population_on_import(self, processor, variant):
        """Test AC2: rrp is populated from retail_price if not provided"""

        # Setup PriceType for retail_price
        PriceType.objects.create(
            onec_id="price-retail-id",
            onec_name="Розничная",
            product_field="retail_price",
        )

        # Import data with only retail price
        price_data = {
            "id": variant.onec_id,
            "prices": [{"price_type_id": "price-retail-id", "value": Decimal("150.00")}],
        }

        # Act
        processor.update_variant_prices(price_data)

        # Assert
        variant.refresh_from_db()
        assert variant.retail_price == Decimal("150.00")
        assert variant.rrp == Decimal("150.00")  # Should be auto-populated

    def test_rrp_not_overwritten_if_provided(self, processor, variant):
        """Test AC2 edge case: rrp is used if explicitly provided"""

        PriceType.objects.create(
            onec_id="price-retail-id",
            onec_name="Розничная",
            product_field="retail_price",
        )
        PriceType.objects.create(onec_id="price-rrp-id", onec_name="РРЦ", product_field="rrp")

        price_data = {
            "id": variant.onec_id,
            "prices": [
                {"price_type_id": "price-retail-id", "value": Decimal("150.00")},
                {"price_type_id": "price-rrp-id", "value": Decimal("180.00")},
            ],
        }

        processor.update_variant_prices(price_data)

        variant.refresh_from_db()
        assert variant.retail_price == Decimal("150.00")
        assert variant.rrp == Decimal("180.00")  # Explicit value takes precedence

    def test_msrp_import(self, processor, variant):
        """Test AC3: msrp is imported correctly"""

        PriceType.objects.create(onec_id="price-msrp-id", onec_name="МРЦ", product_field="msrp")

        price_data = {
            "id": variant.onec_id,
            "prices": [{"price_type_id": "price-msrp-id", "value": Decimal("200.00")}],
        }

        processor.update_variant_prices(price_data)

        variant.refresh_from_db()
        assert variant.msrp == Decimal("200.00")


@pytest.mark.django_db
class TestPriceFallbackLogic:
    def test_federation_rep_fallback(self, variant):
        """Test AC4: federation_rep sees retail_price if federation_price is missing"""

        # Setup user
        user = User.objects.create_user(email="fed@example.com", password="password", role="federation_rep")

        # Case 1: No federation price
        variant.retail_price = Decimal("100.00")
        variant.federation_price = None
        variant.save()

        price = variant.get_price_for_user(user)
        assert price == Decimal("100.00")

        # Case 2: Federation price exists
        variant.federation_price = Decimal("80.00")
        variant.save()

        price = variant.get_price_for_user(user)
        assert price == Decimal("80.00")

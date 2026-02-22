import time
import uuid

import factory
from django.utils.text import slugify
from factory.django import DjangoModelFactory

from apps.products.models import Attribute, AttributeValue, Brand, Brand1CMapping, Category, Product, ProductVariant
from apps.users.models import User

# Глобальный счетчик для обеспечения уникальности
_unique_counter = 0


def get_unique_suffix():
    """Генерирует абсолютно уникальный суффикс"""
    global _unique_counter
    _unique_counter += 1
    return f"{int(time.time() * 1000)}-{_unique_counter}-{uuid.uuid4().hex[:6]}"


class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Faker("company")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower().replace(" ", "-"))


class Brand1CMappingFactory(DjangoModelFactory):
    class Meta:
        model = Brand1CMapping

    brand = factory.SubFactory(BrandFactory)
    onec_id = factory.Faker("uuid4")
    onec_name = factory.Faker("company")


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.LazyFunction(lambda: f"Category-{get_unique_suffix()}")
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name))


class ProductVariantFactory(DjangoModelFactory):
    """Factory for ProductVariant - the SKU-level entity with prices and stock."""

    class Meta:
        model = ProductVariant

    product = factory.SubFactory("tests.factories.ProductFactory", create_variant=False)
    sku = factory.LazyAttribute(lambda obj: f"SKU-{uuid.uuid4().hex[:12].upper()}")
    onec_id = factory.LazyAttribute(lambda obj: f"1C-{uuid.uuid4().hex[:16]}")
    retail_price = factory.Faker("pydecimal", left_digits=4, right_digits=2, positive=True, min_value=100)
    stock_quantity = factory.Faker("random_int", min=0, max=100)
    reserved_quantity = 0


class ProductFactory(DjangoModelFactory):
    """
    Factory for Product with automatic ProductVariant creation.

    Price and stock fields (retail_price, stock_quantity, etc.) are passed
    to the auto-created ProductVariant. Access via product.variants.first().
    """

    class Meta:
        model = Product
        skip_postgeneration_save = True

    name = factory.Faker("catch_phrase")
    brand = factory.SubFactory(BrandFactory)
    category = factory.SubFactory(CategoryFactory)
    slug = factory.LazyAttribute(lambda obj: slugify(obj.name) + "-" + str(uuid.uuid4())[:8])
    description = factory.Faker("paragraph")
    is_active = True

    # Class-level storage for variant params (thread-safe per-instance)
    _variant_params_storage = {}

    _VARIANT_FIELDS = [
        "retail_price",
        "opt1_price",
        "opt2_price",
        "opt3_price",
        "trainer_price",
        "federation_price",
        "stock_quantity",
        "reserved_quantity",
        "sku",
        "onec_variant_id",
    ]

    @classmethod
    def _build(cls, model_class, *args, **kwargs):
        """Build the Product instance, stripping variant fields."""
        # Extract and ignore variant params for build
        for field in cls._VARIANT_FIELDS:
            if field in kwargs:
                kwargs.pop(field)
        return model_class(*args, **kwargs)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Extract variant-related kwargs before creating Product."""
        from decimal import Decimal

        # Fields that belong to ProductVariant, not Product
        variant_fields = cls._VARIANT_FIELDS

        # Extract variant params from kwargs
        variant_params = {}
        for field in variant_fields:
            if field in kwargs:
                variant_params[field] = kwargs.pop(field)

        # Create the Product instance
        instance = super()._create(model_class, *args, **kwargs)

        # Store variant params for post_generation hook using instance id
        cls._variant_params_storage[id(instance)] = variant_params

        return instance

    @factory.post_generation
    def create_variant(self, create, extracted, **kwargs):
        """Create a ProductVariant with price/stock data from ProductFactory params."""
        if not create:
            return
        if extracted is False:
            # Skip variant creation when explicitly disabled
            return

        from decimal import Decimal

        # Retrieve stored variant params
        variant_params = ProductFactory._variant_params_storage.pop(id(self), {})

        # Build final variant params with defaults
        final_params = {
            "product": self,
            "retail_price": variant_params.get("retail_price", Decimal("1000.00")),
            "stock_quantity": variant_params.get("stock_quantity", 10),
            "reserved_quantity": variant_params.get("reserved_quantity", 0),
        }

        # Add optional price fields if provided
        for price_field in [
            "opt1_price",
            "opt2_price",
            "opt3_price",
            "trainer_price",
            "federation_price",
        ]:
            if price_field in variant_params:
                final_params[price_field] = variant_params[price_field]

        # Add SKU if provided
        if "sku" in variant_params:
            final_params["sku"] = variant_params["sku"]

        # Add onec_id if provided
        if "onec_variant_id" in variant_params:
            final_params["onec_id"] = variant_params["onec_variant_id"]

        ProductVariantFactory.create(**final_params)


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Faker("email")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True


class AttributeFactory(DjangoModelFactory):
    class Meta:
        model = Attribute

    name = factory.Faker("word")
    slug = factory.LazyAttribute(lambda obj: obj.name.lower())
    is_active = True


class AttributeValueFactory(DjangoModelFactory):
    class Meta:
        model = AttributeValue

    attribute = factory.SubFactory(AttributeFactory)
    value = factory.Faker("word")
    slug = factory.LazyAttribute(lambda obj: obj.value.lower())

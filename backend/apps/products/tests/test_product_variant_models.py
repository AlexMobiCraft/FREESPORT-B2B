"""
Unit тесты для моделей ProductVariant и ColorMapping (Story 13.1)
Покрытие >= 90% для новых моделей
"""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from apps.products.models import ColorMapping, Product, ProductVariant
from apps.users.models import User


@pytest.mark.django_db
class TestProductVariant:
    """Тесты модели ProductVariant"""

    @pytest.fixture
    def product(self, db):
        """Фикстура для создания базового продукта"""
        from apps.products.models import Brand, Category

        brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        category = Category.objects.create(name="Test Category", slug="test-category")
        return Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
            description="Test description",
            base_images=["http://example.com/image1.jpg"],
        )

    @pytest.fixture
    def variant(self, product):
        """Фикстура для создания ProductVariant"""
        return ProductVariant.objects.create(
            product=product,
            sku="TEST-SKU-001",
            onec_id="parent-id#variant-id",
            color_name="Красный",
            size_value="L",
            retail_price=Decimal("1000.00"),
            opt1_price=Decimal("900.00"),
            stock_quantity=10,
        )

    def test_create_variant_with_valid_data(self, product):
        """AC1: Создание ProductVariant с валидными данными"""
        variant = ProductVariant.objects.create(
            product=product,
            sku="VALID-SKU-001",
            onec_id="parent-123#variant-456",
            color_name="Синий",
            size_value="M",
            retail_price=Decimal("1500.00"),
            opt1_price=Decimal("1350.00"),
            opt2_price=Decimal("1200.00"),
            stock_quantity=20,
            reserved_quantity=5,
        )

        assert variant.id is not None
        assert variant.sku == "VALID-SKU-001"
        assert variant.color_name == "Синий"
        assert variant.size_value == "M"
        assert variant.retail_price == Decimal("1500.00")
        assert variant.stock_quantity == 20
        assert variant.reserved_quantity == 5
        assert variant.is_active is True

    def test_is_in_stock_true_when_stock_positive(self, variant):
        """AC6: is_in_stock возвращает True когда stock_quantity > 0"""
        variant.stock_quantity = 5
        variant.save()
        assert variant.is_in_stock is True

    def test_is_in_stock_false_when_stock_zero(self, variant):
        """AC6: is_in_stock возвращает False когда stock_quantity = 0"""
        variant.stock_quantity = 0
        variant.save()
        assert variant.is_in_stock is False

    def test_available_quantity_with_reserve(self, variant):
        """AC6: available_quantity учитывает reserved_quantity"""
        variant.stock_quantity = 10
        variant.reserved_quantity = 3
        variant.save()
        assert variant.available_quantity == 7

    def test_available_quantity_never_negative(self, variant):
        """AC6: available_quantity не может быть отрицательным"""
        variant.stock_quantity = 5
        variant.reserved_quantity = 10
        variant.save()
        assert variant.available_quantity == 0

    def test_get_price_for_retail_user(self, variant, db):
        """AC7: get_price_for_user возвращает retail_price для retail пользователя"""
        user = User.objects.create_user(email="retail@test.com", password="pass", role="retail")
        price = variant.get_price_for_user(user)
        assert price == variant.retail_price

    def test_get_price_for_wholesale_level1(self, variant, db):
        """AC7: get_price_for_user возвращает opt1_price для wholesale_level1"""
        user = User.objects.create_user(email="ws1@test.com", password="pass", role="wholesale_level1")
        price = variant.get_price_for_user(user)
        assert price == variant.opt1_price

    def test_get_price_for_wholesale_level2(self, variant, db):
        """AC7: get_price_for_user возвращает opt2_price для wholesale_level2"""
        variant.opt2_price = Decimal("850.00")
        variant.save()
        user = User.objects.create_user(email="ws2@test.com", password="pass", role="wholesale_level2")
        price = variant.get_price_for_user(user)
        assert price == Decimal("850.00")

    def test_get_price_for_wholesale_level3(self, variant, db):
        """AC7: get_price_for_user возвращает opt3_price для wholesale_level3"""
        variant.opt3_price = Decimal("800.00")
        variant.save()
        user = User.objects.create_user(email="ws3@test.com", password="pass", role="wholesale_level3")
        price = variant.get_price_for_user(user)
        assert price == Decimal("800.00")

    def test_get_price_for_trainer(self, variant, db):
        """AC7: get_price_for_user возвращает trainer_price для trainer"""
        variant.trainer_price = Decimal("750.00")
        variant.save()
        user = User.objects.create_user(email="trainer@test.com", password="pass", role="trainer")
        price = variant.get_price_for_user(user)
        assert price == Decimal("750.00")

    def test_get_price_for_federation_rep(self, variant, db):
        """AC7: get_price_for_user возвращает federation_price для federation_rep"""
        variant.federation_price = Decimal("700.00")
        variant.save()
        user = User.objects.create_user(email="fed@test.com", password="pass", role="federation_rep")
        price = variant.get_price_for_user(user)
        assert price == Decimal("700.00")

    def test_get_price_for_unauthenticated_user(self, variant):
        """AC7: get_price_for_user возвращает retail_price для неавторизованного"""
        price = variant.get_price_for_user(None)
        assert price == variant.retail_price

    def test_sku_unique_constraint(self, variant):
        """AC5: SKU должен быть уникальным"""
        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(
                product=variant.product,
                sku=variant.sku,  # Дублирующийся SKU
                onec_id="different-onec-id",
                retail_price=Decimal("1000.00"),
            )

    def test_onec_id_unique_constraint(self, variant):
        """AC5: onec_id должен быть уникальным"""
        with pytest.raises(IntegrityError):
            ProductVariant.objects.create(
                product=variant.product,
                sku="DIFFERENT-SKU",
                onec_id=variant.onec_id,  # Дублирующийся onec_id
                retail_price=Decimal("1000.00"),
            )

    def test_foreign_key_cascade_delete(self, product, variant):
        """AC1: При удалении Product удаляются все его variants"""
        variant_id = variant.id
        product.delete()

        # Проверяем что variant удален
        assert not ProductVariant.objects.filter(id=variant_id).exists()

    # TEST-GAP-1: effective_images() Hybrid логика
    def test_effective_images_with_variant_own_images(self, product):
        """TEST-GAP-1: effective_images возвращает собственные изображения варианта"""
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        # Создаем реальное изображение для тестирования
        image = Image.new("RGB", (100, 100), color="red")
        image_io = BytesIO()
        image.save(image_io, format="JPEG")
        image_io.seek(0)

        uploaded_file = SimpleUploadedFile("test_variant_image.jpg", image_io.read(), content_type="image/jpeg")

        # Создаем вариант с реальным main_image
        variant = ProductVariant.objects.create(
            product=product,
            sku="VARIANT-WITH-IMAGE",
            onec_id="parent-img#variant-img",
            retail_price=Decimal("1000.00"),
            main_image=uploaded_file,
            gallery_images=[
                "http://example.com/gallery1.jpg",
                "http://example.com/gallery2.jpg",
            ],
        )

        images = variant.effective_images
        assert len(images) == 3
        assert images[0].startswith("/media/products/variants/test_variant_image")
        assert images[1] == "http://example.com/gallery1.jpg"
        assert images[2] == "http://example.com/gallery2.jpg"

    def test_effective_images_fallback_to_product_base_images(self, variant):
        """TEST-GAP-1: effective_images fallback на Product.base_images"""
        variant.main_image = None
        variant.gallery_images = []
        variant.save()

        # Product имеет base_images
        variant.product.base_images = [
            "http://example.com/product-image1.jpg",
            "http://example.com/product-image2.jpg",
        ]
        variant.product.save()

        images = variant.effective_images
        assert len(images) == 2
        assert images[0] == "http://example.com/product-image1.jpg"
        assert images[1] == "http://example.com/product-image2.jpg"

    def test_effective_images_both_empty_returns_empty_list(self, variant):
        """TEST-GAP-1: effective_images возвращает пустой список если нет изображений"""
        variant.main_image = None
        variant.gallery_images = []
        variant.product.base_images = []
        variant.save()
        variant.product.save()

        images = variant.effective_images
        assert images == []

    # TEST-GAP-2: Price fallback логика
    def test_get_price_for_user_opt1_price_null_fallback_retail(self, variant, db):
        """
        TEST-GAP-2: get_price_for_user fallback на retail_price когда opt1_price=None
        """
        variant.opt1_price = None
        variant.save()
        user = User.objects.create_user(email="ws1null@test.com", password="pass", role="wholesale_level1")
        price = variant.get_price_for_user(user)
        assert price == variant.retail_price

    def test_get_price_for_user_all_nullable_prices_fallback(self, variant, db):
        """TEST-GAP-2: Проверка fallback для всех nullable цен"""
        variant.opt1_price = None
        variant.opt2_price = None
        variant.opt3_price = None
        variant.trainer_price = None
        variant.federation_price = None
        variant.save()

        # Проверяем fallback для каждой роли
        roles_data = [
            ("wholesale_level1", "ws1fb@test.com"),
            ("wholesale_level2", "ws2fb@test.com"),
            ("wholesale_level3", "ws3fb@test.com"),
            ("trainer", "trainerfb@test.com"),
            ("federation_rep", "fedfb@test.com"),
        ]

        for role, email in roles_data:
            user = User.objects.create_user(email=email, password="pass", role=role)
            price = variant.get_price_for_user(user)
            assert price == variant.retail_price, f"Role {role} should fallback to retail_price"

    # TEST-GAP-6: Edge cases
    def test_variant_with_empty_color_and_size(self, product, caplog):
        """TEST-GAP-6: ProductVariant с пустыми color_name и size_value"""
        import logging

        with caplog.at_level(logging.WARNING):
            variant = ProductVariant.objects.create(
                product=product,
                sku="NO-CHARACTERISTICS",
                onec_id="parent-no-chars#variant-no-chars",
                color_name="",
                size_value="",
                retail_price=Decimal("1000.00"),
            )
            variant.clean()

        # Проверяем что создание прошло успешно
        assert variant.id is not None

        # Проверяем что было залогировано предупреждение
        assert "создан без характеристик" in caplog.text

    def test_variant_with_empty_images(self, variant):
        """TEST-GAP-6: ProductVariant с main_image=None и gallery_images=[]"""
        variant.main_image = None
        variant.gallery_images = []
        variant.save()

        # ImageField с None становится ImageFieldFile, проверяем через bool
        assert not variant.main_image
        assert variant.gallery_images == []

    def test_available_quantity_when_reserved_exceeds_stock(self, variant):
        """TEST-GAP-6: available_quantity=0 когда reserved_quantity > stock_quantity"""
        variant.stock_quantity = 5
        variant.reserved_quantity = 10
        variant.save()

        assert variant.available_quantity == 0

    def test_str_representation(self, variant):
        """TEST-GAP-6: __str__ возвращает '{product.name} - {sku}'"""
        expected = f"{variant.product.name} - {variant.sku}"
        assert str(variant) == expected

    def test_price_validators_reject_negative(self, product):
        """TEST-GAP-6: validators=[MinValueValidator(0)] отклоняют отрицательные цены"""
        variant = ProductVariant(
            product=product,
            sku="NEGATIVE-PRICE",
            onec_id="parent-neg#variant-neg",
            retail_price=Decimal("-100.00"),  # Отрицательная цена
        )

        with pytest.raises(ValidationError):
            variant.full_clean()


@pytest.mark.django_db
class TestColorMapping:
    """Тесты модели ColorMapping"""

    def test_create_color_mapping(self):
        """AC2: Создание ColorMapping с названием и hex-кодом"""
        # Используем уникальное имя, т.к. миграция 0025 уже создала "Красный"
        color = ColorMapping.objects.create(name="Тестовый Красный", hex_code="#FF0000")

        assert color.id is not None
        assert color.name == "Тестовый Красный"
        assert color.hex_code == "#FF0000"

    def test_name_unique_constraint(self):
        """AC2: Название цвета должно быть уникальным"""
        # Используем уникальное имя для первого создания
        ColorMapping.objects.create(name="Тестовый Синий", hex_code="#0000FF")

        with pytest.raises(IntegrityError):
            ColorMapping.objects.create(name="Тестовый Синий", hex_code="#0000AA")

    # TEST-GAP-4: ColorMapping fallback
    def test_color_not_found_in_mapping(self):
        """TEST-GAP-4: Цвет не найден в ColorMapping (возврат текстового названия)"""
        # Проверяем что можно создать вариант с цветом, которого нет в ColorMapping
        from apps.products.models import Brand, Category

        brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        category = Category.objects.create(name="Test Category", slug="test-category")
        product = Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
            description="Test",
        )

        variant = ProductVariant.objects.create(
            product=product,
            sku="UNMAPPED-COLOR",
            onec_id="parent-unmapped#variant-unmapped",
            color_name="Неизвестный Цвет",  # Цвет отсутствует в ColorMapping
            retail_price=Decimal("1000.00"),
        )

        assert variant.color_name == "Неизвестный Цвет"

    def test_swatch_image_optional(self):
        """TEST-GAP-4: swatch_image опциональное поле"""
        color = ColorMapping.objects.create(name="Зелёный", hex_code="#00FF00")

        assert color.swatch_image.name == ""


@pytest.mark.django_db
class TestProductRefactoring:
    """Тесты рефакторинга модели Product (Story 13.1)"""

    @pytest.fixture
    def product(self, db):
        """Фикстура для создания базового продукта"""
        from apps.products.models import Brand, Category

        brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        category = Category.objects.create(name="Test Category", slug="test-category")
        return Product.objects.create(
            name="Test Product",
            slug="test-product",
            brand=brand,
            category=category,
            description="Test description",
            base_images=["http://example.com/image1.jpg"],
        )

    def test_product_has_no_price_fields(self, product):
        """TEST-GAP-3: Product не должен иметь полей цен после рефакторинга"""
        assert not hasattr(product, "retail_price")
        assert not hasattr(product, "opt1_price")
        assert not hasattr(product, "opt2_price")
        assert not hasattr(product, "opt3_price")
        assert not hasattr(product, "trainer_price")
        assert not hasattr(product, "federation_price")

    def test_product_has_no_stock_fields(self, product):
        """TEST-GAP-3: Product не должен иметь полей остатков"""
        assert not hasattr(product, "stock_quantity")
        assert not hasattr(product, "reserved_quantity")

    def test_product_variants_related_name(self, product):
        """AC3: product.variants.all() возвращает QuerySet[ProductVariant]"""
        # Создаём несколько вариантов
        for i in range(3):
            ProductVariant.objects.create(
                product=product,
                sku=f"VARIANT-{i}",
                onec_id=f"parent-test#variant-{i}",
                retail_price=Decimal("1000.00"),
            )

        variants = product.variants.all()
        assert variants.count() == 3
        assert all(isinstance(v, ProductVariant) for v in variants)

    # TEST-GAP-3: Product рефакторинг валидация
    def test_accessing_removed_price_field_raises_attribute_error(self, product):
        """TEST-GAP-3: Попытка доступа к удалённому полю retail_price → AttributeError"""
        with pytest.raises(AttributeError):
            _ = product.retail_price

    def test_accessing_removed_stock_field_raises_attribute_error(self, product):
        """
        TEST-GAP-3: Попытка доступа к удалённому полю stock_quantity → AttributeError
        """
        with pytest.raises(AttributeError):
            _ = product.stock_quantity

    def test_product_base_images_saves_and_loads_correctly(self, product):
        """TEST-GAP-3: Product.base_images корректно сохраняется и читается"""
        test_images = [
            "http://example.com/img1.jpg",
            "http://example.com/img2.jpg",
            "http://example.com/img3.jpg",
        ]
        product.base_images = test_images
        product.save()

        # Перезагружаем из БД
        product.refresh_from_db()

        assert product.base_images == test_images
        assert len(product.base_images) == 3

    # TEST-GAP-5: Integration с существующими моделями
    def test_product_brand_fk_works_after_refactoring(self, product):
        """TEST-GAP-5: Product.brand FK работает после рефакторинга"""
        assert product.brand is not None
        assert product.brand.name == "Test Brand"

    def test_product_category_fk_works_after_refactoring(self, product):
        """TEST-GAP-5: Product.category FK работает после рефакторинга"""
        assert product.category is not None
        assert product.category.name == "Test Category"

    def test_brand_model_unchanged(self):
        """TEST-GAP-5: Brand модель осталась неизменной (IV1)"""
        from apps.products.models import Brand

        # Проверяем основные поля Brand не изменились
        brand = Brand.objects.create(name="Test Brand", slug="test-brand")
        assert hasattr(brand, "name")
        assert hasattr(brand, "slug")
        assert hasattr(brand, "normalized_name")
        assert hasattr(brand, "is_active")

    def test_category_model_unchanged(self):
        """TEST-GAP-5: Category модель осталась неизменной (IV1)"""
        from apps.products.models import Category

        # Проверяем основные поля Category не изменились
        category = Category.objects.create(name="Test Category", slug="test-category")
        assert hasattr(category, "name")
        assert hasattr(category, "slug")
        assert hasattr(category, "parent")
        assert hasattr(category, "is_active")

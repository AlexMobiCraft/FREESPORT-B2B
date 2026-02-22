"""Unit-тесты для модели Brand1CMapping."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.products.models import Brand, Brand1CMapping


@pytest.mark.unit
@pytest.mark.django_db
class TestBrand1CMappingModel:
    """Тесты для модели Brand1CMapping."""

    def test_brand1c_mapping_creation(self) -> None:
        """Тест: создание маппинга бренда из 1С."""
        # ARRANGE
        brand = Brand.objects.create(name="Nike", slug="nike")

        # ACT
        mapping = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-123",
            onec_name="Nike Original",
        )

        # ASSERT
        assert mapping.brand == brand
        assert mapping.onec_id == "1c-brand-123"
        assert mapping.onec_name == "Nike Original"
        assert mapping.created_at is not None

    def test_brand1c_mapping_unique_onec_id(self) -> None:
        """Тест: onec_id должен быть уникальным."""
        # ARRANGE
        brand1 = Brand.objects.create(name="Nike", slug="nike")
        brand2 = Brand.objects.create(name="Adidas", slug="adidas")

        Brand1CMapping.objects.create(
            brand=brand1,
            onec_id="1c-brand-123",
            onec_name="Nike",
        )

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            Brand1CMapping.objects.create(
                brand=brand2,
                onec_id="1c-brand-123",  # Дубликат
                onec_name="Adidas",
            )

    def test_brand1c_mapping_cascade_delete(self) -> None:
        """Тест: маппинги удаляются при удалении бренда (CASCADE)."""
        # ARRANGE
        brand = Brand.objects.create(name="Nike", slug="nike")
        mapping1 = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-123",
            onec_name="Nike 1",
        )
        mapping2 = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-456",
            onec_name="Nike 2",
        )

        # ACT
        brand.delete()

        # ASSERT
        assert not Brand1CMapping.objects.filter(id=mapping1.id).exists()
        assert not Brand1CMapping.objects.filter(id=mapping2.id).exists()

    def test_brand1c_mapping_str_representation(self) -> None:
        """Тест: строковое представление маппинга."""
        # ARRANGE
        brand = Brand.objects.create(name="Nike", slug="nike")
        mapping = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-123",
            onec_name="Nike Original",
        )

        # ACT
        result = str(mapping)

        # ASSERT
        assert result == "Nike Original (1c-brand-123) -> Nike"

    def test_brand1c_mapping_multiple_mappings_per_brand(self) -> None:
        """Тест: один бренд может иметь несколько маппингов."""
        # ARRANGE
        brand = Brand.objects.create(name="Nike", slug="nike")

        # ACT
        mapping1 = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-123",
            onec_name="Nike",
        )
        mapping2 = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-456",
            onec_name="NIKE",
        )
        mapping3 = Brand1CMapping.objects.create(
            brand=brand,
            onec_id="1c-brand-789",
            onec_name="nike",
        )

        # ASSERT
        assert brand.onec_mappings.count() == 3
        assert mapping1 in brand.onec_mappings.all()
        assert mapping2 in brand.onec_mappings.all()
        assert mapping3 in brand.onec_mappings.all()

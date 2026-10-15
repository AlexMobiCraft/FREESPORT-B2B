"""Unit-тесты для модели Brand."""

from __future__ import annotations

import pytest
from django.db import IntegrityError

from apps.products.models import Brand


@pytest.mark.unit
@pytest.mark.django_db
class TestBrandModel:
    """Тесты для модели Brand."""

    def test_brand_save_calculates_normalized_name(self) -> None:
        """Тест: normalized_name вычисляется автоматически при сохранении."""
        # ARRANGE
        brand = Brand(name="BoyBo", slug="boybo")

        # ACT
        brand.save()

        # ASSERT
        assert brand.normalized_name == "boybo"

    def test_brand_save_handles_empty_name(self) -> None:
        """Тест: normalized_name становится пустой строкой если name пустой."""
        # ARRANGE
        brand = Brand(name="", slug="empty-brand")

        # ACT
        brand.save()

        # ASSERT
        assert brand.normalized_name == ""

    def test_brand_save_uniqueness_violation(self) -> None:
        """Тест: два бренда с одинаковым normalized_name вызывают IntegrityError."""
        # ARRANGE
        brand1 = Brand(name="Nike", slug="nike-1")
        brand1.save()

        brand2 = Brand(name="NIKE", slug="nike-2")

        # ACT & ASSERT
        with pytest.raises(IntegrityError):
            brand2.save()

    def test_brand_save_normalizes_special_chars(self) -> None:
        """Тест: специальные символы удаляются при нормализации."""
        # ARRANGE
        brand = Brand(name="Under-Armour", slug="under-armour")

        # ACT
        brand.save()

        # ASSERT
        assert brand.normalized_name == "underarmour"

    def test_brand_save_normalizes_spaces(self) -> None:
        """Тест: пробелы удаляются при нормализации."""
        # ARRANGE
        brand = Brand(name="Boy Bo", slug="boy-bo")

        # ACT
        brand.save()

        # ASSERT
        assert brand.normalized_name == "boybo"

    def test_brand_save_normalizes_case(self) -> None:
        """Тест: регистр приводится к нижнему при нормализации."""
        # ARRANGE
        brand = Brand(name="ADIDAS", slug="adidas")

        # ACT
        brand.save()

        # ASSERT
        assert brand.normalized_name == "adidas"

    def test_brand_str_representation(self) -> None:
        """Тест: строковое представление модели."""
        # ARRANGE
        brand = Brand(name="Test Brand", slug="test-brand")
        brand.save()

        # ACT
        result = str(brand)

        # ASSERT
        assert result == "Test Brand"

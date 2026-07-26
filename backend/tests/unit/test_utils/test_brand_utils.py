"""Unit-тесты для утилит работы с брендами."""

from __future__ import annotations

import pytest

from apps.products.utils.brands import normalize_brand_name


@pytest.mark.unit
class TestNormalizeBrandName:
    """Тесты для функции normalize_brand_name."""

    def test_normalize_brand_name_lowercase(self) -> None:
        """Тест: приведение к нижнему регистру."""
        # ARRANGE
        brand_name = "BOYBO"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "boybo"

    def test_normalize_brand_name_removes_spaces(self) -> None:
        """Тест: удаление пробелов."""
        # ARRANGE
        brand_name = "Boy Bo"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "boybo"

    def test_normalize_brand_name_removes_special_chars(self) -> None:
        """Тест: удаление специальных символов."""
        # ARRANGE
        brand_name = "Under-Armour"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "underarmour"

    def test_normalize_brand_name_handles_cyrillic(self) -> None:
        """Тест: обработка кириллицы."""
        # ARRANGE
        brand_name = "Рокки"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "рокки"

    def test_normalize_brand_name_handles_accents(self) -> None:
        """Тест: удаление акцентов."""
        # ARRANGE
        brand_name = "Beyoncé"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "beyonce"

    def test_normalize_brand_name_with_numbers(self) -> None:
        """Тест: сохранение цифр."""
        # ARRANGE
        brand_name = "Nike2024"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "nike2024"

    def test_normalize_brand_name_empty_string(self) -> None:
        """Тест: пустая строка."""
        # ARRANGE
        brand_name = ""

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == ""

    def test_normalize_brand_name_none_input(self) -> None:
        """Тест: None на входе."""
        # ARRANGE
        brand_name = None

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == ""

    def test_normalize_brand_name_multiple_spaces(self) -> None:
        """Тест: множественные пробелы."""
        # ARRANGE
        brand_name = "Boy   Bo   Brand"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "boybobrand"

    def test_normalize_brand_name_mixed_case_with_special_chars(self) -> None:
        """Тест: смешанный регистр со спецсимволами."""
        # ARRANGE
        brand_name = "Under_Armour-2024!"

        # ACT
        result = normalize_brand_name(brand_name)

        # ASSERT
        assert result == "underarmour2024"

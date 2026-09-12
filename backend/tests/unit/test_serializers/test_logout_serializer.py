"""
Unit тесты для LogoutSerializer

Story 30.4: Тесты для Logout функциональности
AC: 1, 3, 6 - Unit-тесты покрывают все методы serializer, изолированы,
следуют pytest conventions
"""

import pytest

from apps.users.serializers import LogoutSerializer


@pytest.mark.unit
class TestLogoutSerializer:
    """Unit-тесты для LogoutSerializer.

    Эти тесты проверяют валидацию сериализатора без обращений к базе данных.
    Используется паттерн AAA (Arrange, Act, Assert) для структурирования тестов.
    """

    def test_valid_refresh_token(self):
        """Валидный refresh token проходит валидацию.

        Проверяет, что сериализатор принимает непустой токен и
        корректно возвращает его в validated_data.
        """
        # Arrange
        data = {"refresh": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.valid-token"}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        assert serializer.is_valid(), f"Serializer errors: {serializer.errors}"
        assert serializer.validated_data["refresh"] == data["refresh"]

    def test_missing_refresh_field(self):
        """Отсутствие поля refresh вызывает ошибку валидации.

        Проверяет, что сериализатор требует обязательное поле refresh
        и возвращает корректный код ошибки.
        """
        # Arrange
        data = {}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors
        assert serializer.errors["refresh"][0].code == "required"

    def test_empty_refresh_token(self):
        """Пустой refresh токен вызывает ошибку валидации.

        Проверяет, что сериализатор не принимает пустую строку
        в качестве токена.
        """
        # Arrange
        data = {"refresh": ""}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_blank_refresh_token(self):
        """Токен из пробелов вызывает ошибку валидации.

        CharField с allow_blank=False (по умолчанию) должен отклонить
        строку, состоящую только из пробелов.
        """
        # Arrange
        data = {"refresh": "   "}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_serializer_has_correct_fields(self):
        """Сериализатор содержит только поле refresh.

        Проверяет структуру сериализатора: должно быть ровно одно
        обязательное поле - refresh.
        """
        # Arrange & Act
        serializer = LogoutSerializer()

        # Assert
        assert list(serializer.fields.keys()) == ["refresh"]
        assert serializer.fields["refresh"].required is True

    def test_serializer_field_has_help_text(self):
        """Поле refresh имеет help_text для API документации.

        Проверяет наличие документации для OpenAPI/drf-spectacular.
        """
        # Arrange & Act
        serializer = LogoutSerializer()

        # Assert
        assert serializer.fields["refresh"].help_text is not None
        assert "Refresh token" in serializer.fields["refresh"].help_text

    def test_none_refresh_token_invalid(self):
        """None в качестве refresh токена вызывает ошибку валидации."""
        # Arrange
        data = {"refresh": None}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_very_long_token_accepted(self):
        """Сериализатор принимает токен любой длины.

        JWT токены могут быть достаточно длинными,
        поэтому сериализатор не должен ограничивать длину на уровне валидации.
        """
        # Arrange
        long_token = "a" * 2000  # Очень длинный токен

        data = {"refresh": long_token}

        # Act
        serializer = LogoutSerializer(data=data)

        # Assert
        # Сериализатор должен принять токен (валидность JWT проверяется во view)
        assert serializer.is_valid()
        assert serializer.validated_data["refresh"] == long_token

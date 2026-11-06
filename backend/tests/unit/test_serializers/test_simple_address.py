"""
Простой тест AddressSerializer для проверки работоспособности
"""

import pytest
from django.contrib.auth import get_user_model

from apps.users.serializers import AddressSerializer

User = get_user_model()


@pytest.mark.django_db
class TestAddressSerializerSimple:
    """Простые тесты сериализатора адресов"""

    def test_address_serialization_basic(self, user_factory, address_factory):
        """Базовый тест сериализации адреса"""
        user = user_factory.create()
        address = address_factory.create(user=user)

        serializer = AddressSerializer(address)
        data = serializer.data

        # Проверяем основные поля
        assert "id" in data
        assert data["id"] == address.id
        assert "full_name" in data
        assert "city" in data
        assert "postal_code" in data

    def test_address_creation_simple(self, user_factory):
        """Простой тест создания адреса через сериализатор"""
        user = user_factory.create()

        data = {
            "user": user.id,  # Добавляем пользователя в данные
            "address_type": "shipping",
            "full_name": "Тест Тестов",
            "phone": "79000000000",
            "city": "Москва",
            "street": "ул. Тестовая",
            "building": "1",
            "postal_code": "123456",
        }

        serializer = AddressSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        validated_data = serializer.validated_data
        assert validated_data["full_name"] == "Тест Тестов"
        assert validated_data["city"] == "Москва"
        assert validated_data["postal_code"] == "123456"

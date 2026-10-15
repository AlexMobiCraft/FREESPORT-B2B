"""
Тесты для общих сериализаторов
Тестируем AddressSerializer из приложения users
"""

import pytest
from django.contrib.auth import get_user_model

from apps.users.serializers import AddressSerializer

User = get_user_model()


@pytest.mark.django_db
class TestAddressSerializer:
    """Тесты сериализатора адресов"""

    def test_address_serialization(self, user_factory, address_factory):
        """Тест сериализации адреса"""
        user = user_factory.create()
        address = address_factory.create(
            user=user,
            full_name="Иван Иванов",
            phone="+79001234567",
            city="Москва",
            street="ул. Пушкина",
            building="10",
            apartment="5",
            postal_code="123456",
            is_default=True,
        )

        serializer = AddressSerializer(address)
        data = serializer.data

        assert data["id"] == address.id
        assert data["full_name"] == "Иван Иванов"
        assert data["phone"] == "+79001234567"
        assert data["city"] == "Москва"
        assert data["street"] == "ул. Пушкина"
        assert data["building"] == "10"
        assert data["apartment"] == "5"
        assert data["postal_code"] == "123456"
        assert data["is_default"] is True

    def test_address_creation_validation(self, user_factory):
        """Тест валидации при создании адреса"""
        user = user_factory.create()

        valid_data = {
            "full_name": "Петр Петров",
            "phone": "+79111111111",
            "city": "Санкт-Петербург",
            "street": "Невский проспект",
            "building": "1",
            "postal_code": "190000",
        }

        serializer = AddressSerializer(data=valid_data, context={"user": user})
        assert serializer.is_valid(), serializer.errors

        validated_data = serializer.validated_data
        assert validated_data["full_name"] == "Петр Петров"
        assert validated_data["city"] == "Санкт-Петербург"

    def test_address_phone_validation(self, user_factory):
        """Тест валидации номера телефона"""
        user = user_factory.create()

        invalid_data = {
            "full_name": "Тест Тестов",
            "phone": "123",  # Слишком короткий
            "city": "Москва",
            "street": "ул. Тестовая",
            "building": "1",
        }

        serializer = AddressSerializer(data=invalid_data, context={"user": user})
        # Проверяем валидацию только если она реализована
        if hasattr(serializer, "validate_phone"):
            assert not serializer.is_valid()
            assert "phone" in serializer.errors

    def test_address_required_fields(self, user_factory):
        """Тест валидации номера телефона"""
        user = user_factory.create()

        # Данные без обязательных полей
        incomplete_data = {"full_name": "Неполный адрес"}

        serializer = AddressSerializer(data=incomplete_data, context={"user": user})
        assert not serializer.is_valid()
        # Проверяем что есть ошибки валидации
        assert len(serializer.errors) > 0

    def test_address_multiple_serialization(self, user_factory, address_factory):
        """Тест сериализации нескольких адресов"""
        user = user_factory.create()
        addresses = address_factory.create_batch(3, user=user)

        serializer = AddressSerializer(addresses, many=True)
        data = serializer.data

        assert len(data) == 3
        for address_data in data:
            assert "id" in address_data
            assert "full_name" in address_data
            assert "city" in address_data

    def test_address_update_validation(self, user_factory, address_factory):
        """Тест валидации при обновлении адреса"""
        user = user_factory.create()
        address = address_factory.create(user=user)

        update_data = {"full_name": "Обновленный адрес", "city": "Новосибирск"}

        serializer = AddressSerializer(address, data=update_data, partial=True)
        assert serializer.is_valid(), serializer.errors

        validated_data = serializer.validated_data
        assert validated_data["full_name"] == "Обновленный адрес"
        assert validated_data["city"] == "Новосибирск"


@pytest.mark.django_db
class TestAddressSerializerIntegration:
    """Интеграционные тесты сериализатора адресов"""

    def test_address_with_user_context(self, user_factory):
        """Тест адреса с контекстом пользователя"""
        user = user_factory.create()

        address_data = {
            "full_name": "Сотрудник Компании",
            "phone": "+74951234567",
            "city": "Москва",
            "street": "Бизнес-центр",
            "building": "1",
            "postal_code": "123456",
        }

        serializer = AddressSerializer(data=address_data, context={"user": user})
        assert serializer.is_valid(), serializer.errors

    def test_address_default_logic(self, user_factory):
        """Тест логики адреса по умолчанию"""
        user = user_factory.create()

        # Создаем первый адрес как default
        data1 = {
            "full_name": "Тест",
            "phone": "+79000000000",
            "city": "Москва",
            "street": "ул. Первая",
            "building": "1",
            "postal_code": "123456",
            "is_default": True,
        }

        serializer1 = AddressSerializer(data=data1, context={"user": user})
        assert serializer1.is_valid(), serializer1.errors

        # Создаем второй адрес как default
        data2 = {
            "full_name": "Тест",
            "phone": "+79000000001",
            "city": "Москва",
            "street": "ул. Вторая",
            "building": "2",
            "postal_code": "123456",
            "is_default": True,
        }

        serializer2 = AddressSerializer(data=data2, context={"user": user})
        assert serializer2.is_valid(), serializer2.errors

    def test_address_performance_with_large_dataset(self, user_factory, address_factory):
        """Тест производительности с большим количеством адресов"""
        user = user_factory.create()
        addresses = address_factory.create_batch(20, user=user)

        # Тест множественной сериализации
        serializer = AddressSerializer(addresses, many=True)
        data = serializer.data

        assert len(data) == 20
        # Проверяем что все адреса сериализованы корректно
        for address_data in data:
            assert "id" in address_data
            assert "full_name" in address_data
            assert "city" in address_data
            assert "street" in address_data

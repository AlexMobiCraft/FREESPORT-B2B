"""
Unit-тесты для CustomerIdentityResolver
Story 3.2.1.5: customer-identity-algorithms
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from apps.users.services.identity_resolution import CustomerIdentityResolver

User = get_user_model()


@pytest.mark.django_db
class TestCustomerIdentityResolver:
    """Тесты для CustomerIdentityResolver"""

    @pytest.fixture
    def resolver(self):
        """Фикстура для создания экземпляра resolver"""
        return CustomerIdentityResolver()

    @pytest.fixture
    def b2b_user(self):
        """Фикстура B2B пользователя с ИНН"""
        return User.objects.create_user(
            email="b2b@example.com",
            password="testpass123",
            first_name="B2B",
            last_name="User",
            role="wholesale_level1",
            tax_id="1234567890",
            onec_id="1C-B2B-001",
        )

    @pytest.fixture
    def b2c_user(self):
        """Фикстура B2C пользователя с email"""
        return User.objects.create_user(
            email="b2c@example.com",
            password="testpass123",
            first_name="B2C",
            last_name="User",
            role="retail",
        )

    @pytest.fixture
    def user_with_guid(self):
        """Фикстура пользователя с GUID"""
        guid = uuid.uuid4()
        return User.objects.create_user(
            email="guid@example.com",
            password="testpass123",
            first_name="GUID",
            last_name="User",
            role="retail",
            onec_guid=guid,
        )

    # Тесты идентификации по onec_id (Приоритет 1)
    def test_identify_by_onec_id_success(self, resolver, b2b_user):
        """Тест успешной идентификации по onec_id"""
        onec_data = {
            "onec_id": "1C-B2B-001",
            "email": "different@example.com",
            "tax_id": "9999999999",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2b_user.id
        assert method == "onec_id"

    def test_identify_by_onec_id_not_found(self, resolver):
        """Тест неудачной идентификации по onec_id"""
        onec_data = {
            "onec_id": "NON-EXISTENT-ID",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    # Тесты идентификации по onec_guid (Приоритет 2)
    def test_identify_by_onec_guid_success(self, resolver, user_with_guid):
        """Тест успешной идентификации по onec_guid"""
        onec_data = {
            "onec_guid": user_with_guid.onec_guid,
            "email": "different@example.com",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == user_with_guid.id
        assert method == "onec_guid"

    def test_identify_by_onec_guid_not_found(self, resolver):
        """Тест неудачной идентификации по onec_guid"""
        onec_data = {
            "onec_guid": uuid.uuid4(),
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    # Тесты идентификации по tax_id (Приоритет 3)
    def test_identify_by_tax_id_success(self, resolver, b2b_user):
        """Тест успешной идентификации по ИНН"""
        onec_data = {
            "tax_id": "1234567890",
            "email": "different@example.com",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2b_user.id
        assert method == "tax_id"

    def test_identify_by_tax_id_with_spaces(self, resolver, b2b_user):
        """Тест идентификации по ИНН с пробелами"""
        onec_data = {
            "tax_id": "123 456 7890",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2b_user.id
        assert method == "tax_id"

    def test_identify_by_tax_id_with_dashes(self, resolver, b2b_user):
        """Тест идентификации по ИНН с дефисами"""
        onec_data = {
            "tax_id": "123-456-7890",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2b_user.id
        assert method == "tax_id"

    def test_identify_by_tax_id_invalid_length(self, resolver):
        """Тест идентификации по ИНН с неверной длиной"""
        onec_data = {
            "tax_id": "12345",  # Слишком короткий
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    def test_identify_by_tax_id_not_found(self, resolver):
        """Тест неудачной идентификации по ИНН"""
        onec_data = {
            "tax_id": "9999999999",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    # Тесты идентификации по email (Приоритет 4)
    def test_identify_by_email_success(self, resolver, b2c_user):
        """Тест успешной идентификации по email"""
        onec_data = {
            "email": "b2c@example.com",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2c_user.id
        assert method == "email"

    def test_identify_by_email_case_insensitive(self, resolver, b2c_user):
        """Тест идентификации по email без учета регистра"""
        onec_data = {
            "email": "B2C@EXAMPLE.COM",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2c_user.id
        assert method == "email"

    def test_identify_by_email_with_spaces(self, resolver, b2c_user):
        """Тест идентификации по email с пробелами"""
        onec_data = {
            "email": "  b2c@example.com  ",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is not None
        assert customer.id == b2c_user.id
        assert method == "email"

    def test_identify_by_email_invalid_format(self, resolver):
        """Тест идентификации по email с неверным форматом"""
        onec_data = {
            "email": "invalid-email",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    def test_identify_by_email_not_found(self, resolver):
        """Тест неудачной идентификации по email"""
        onec_data = {
            "email": "nonexistent@example.com",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    # Тесты приоритетов идентификации
    def test_priority_onec_id_over_email(self, resolver, b2b_user, b2c_user):
        """Тест приоритета onec_id над email"""
        onec_data = {
            "onec_id": b2b_user.onec_id,
            "email": b2c_user.email,  # Другой пользователь
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer.id == b2b_user.id  # Найден по onec_id
        assert method == "onec_id"

    def test_priority_onec_guid_over_tax_id(self, resolver, user_with_guid, b2b_user):
        """Тест приоритета onec_guid над tax_id"""
        # Добавляем tax_id пользователю с guid
        user_with_guid.tax_id = "9876543210"
        user_with_guid.save()

        onec_data = {
            "onec_guid": user_with_guid.onec_guid,
            "tax_id": b2b_user.tax_id,  # Другой пользователь
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer.id == user_with_guid.id  # Найден по onec_guid
        assert method == "onec_guid"

    def test_priority_tax_id_over_email(self, resolver, b2b_user, b2c_user):
        """Тест приоритета tax_id над email"""
        onec_data = {
            "tax_id": b2b_user.tax_id,
            "email": b2c_user.email,  # Другой пользователь
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer.id == b2b_user.id  # Найден по tax_id
        assert method == "tax_id"

    # Тесты нормализации ИНН
    def test_normalize_inn_10_digits(self, resolver):
        """Тест нормализации ИНН из 10 цифр"""
        assert resolver.normalize_inn("1234567890") == "1234567890"

    def test_normalize_inn_12_digits(self, resolver):
        """Тест нормализации ИНН из 12 цифр"""
        assert resolver.normalize_inn("123456789012") == "123456789012"

    def test_normalize_inn_with_spaces(self, resolver):
        """Тест нормализации ИНН с пробелами"""
        assert resolver.normalize_inn("123 456 7890") == "1234567890"

    def test_normalize_inn_with_dashes(self, resolver):
        """Тест нормализации ИНН с дефисами"""
        assert resolver.normalize_inn("123-456-7890") == "1234567890"

    def test_normalize_inn_invalid_length(self, resolver):
        """Тест нормализации ИНН с неверной длиной"""
        assert resolver.normalize_inn("12345") is None
        assert resolver.normalize_inn("12345678901234") is None

    def test_normalize_inn_none(self, resolver):
        """Тест нормализации None ИНН"""
        assert resolver.normalize_inn(None) is None

    def test_normalize_inn_empty(self, resolver):
        """Тест нормализации пустого ИНН"""
        assert resolver.normalize_inn("") is None

    # Тесты валидации ИНН
    def test_validate_inn_valid_10(self, resolver):
        """Тест валидации корректного 10-значного ИНН"""
        assert resolver._validate_inn("1234567890") is True

    def test_validate_inn_valid_12(self, resolver):
        """Тест валидации корректного 12-значного ИНН"""
        assert resolver._validate_inn("123456789012") is True

    def test_validate_inn_invalid_length(self, resolver):
        """Тест валидации ИНН с неверной длиной"""
        assert resolver._validate_inn("12345") is False
        assert resolver._validate_inn("12345678901234") is False

    def test_validate_inn_non_digits(self, resolver):
        """Тест валидации ИНН с нецифровыми символами"""
        assert resolver._validate_inn("123456789a") is False

    def test_validate_inn_none(self, resolver):
        """Тест валидации None ИНН"""
        assert resolver._validate_inn(None) is False

    # Тесты нормализации email
    def test_normalize_email_lowercase(self, resolver):
        """Тест нормализации email в lowercase"""
        assert resolver.normalize_email("TEST@EXAMPLE.COM") == "test@example.com"

    def test_normalize_email_trim_spaces(self, resolver):
        """Тест нормализации email с удалением пробелов"""
        assert resolver.normalize_email("  test@example.com  ") == "test@example.com"

    def test_normalize_email_invalid_no_at(self, resolver):
        """Тест нормализации невалидного email без @"""
        assert resolver.normalize_email("invalid-email") is None

    def test_normalize_email_invalid_no_domain(self, resolver):
        """Тест нормализации невалидного email без домена"""
        assert resolver.normalize_email("test@") is None

    def test_normalize_email_none(self, resolver):
        """Тест нормализации None email"""
        assert resolver.normalize_email(None) is None

    def test_normalize_email_empty(self, resolver):
        """Тест нормализации пустого email"""
        assert resolver.normalize_email("") is None

    # Тесты логирования
    @patch("apps.users.services.identity_resolution.CustomerSyncLog")
    def test_log_identification_with_session(self, mock_log, resolver, b2b_user):
        """Тест логирования с session"""
        mock_session = MagicMock()
        onec_data = {
            "session": mock_session,
            "onec_id": "1C-B2B-001",
            "tax_id": "1234567890",
            "email": "b2b@example.com",
        }

        resolver._log_identification("onec_id", b2b_user, onec_data)

        mock_log.objects.create.assert_called_once()
        call_kwargs = mock_log.objects.create.call_args[1]
        assert call_kwargs["session"] == mock_session
        assert call_kwargs["customer"] == b2b_user
        assert call_kwargs["onec_id"] == "1C-B2B-001"
        assert call_kwargs["operation_type"] == "identify_customer"
        assert call_kwargs["status"] == "success"

    def test_log_identification_without_session(self, resolver, b2b_user):
        """Тест логирования без session (не создает запись)"""
        onec_data = {
            "onec_id": "1C-B2B-001",
        }

        # Не должно вызвать исключение
        resolver._log_identification("onec_id", b2b_user, onec_data)

    def test_log_identification_not_found(self, resolver):
        """Тест логирования когда клиент не найден"""
        onec_data = {
            "onec_id": "NON-EXISTENT",
        }

        # Не должно вызвать исключение
        resolver._log_identification("not_found", None, onec_data)

    # Тесты граничных случаев
    def test_identify_with_empty_data(self, resolver):
        """Тест идентификации с пустыми данными"""
        customer, method = resolver.identify_customer({})

        assert customer is None
        assert method is None

    def test_identify_with_all_none_values(self, resolver):
        """Тест идентификации со всеми None значениями"""
        onec_data = {
            "onec_id": None,
            "onec_guid": None,
            "tax_id": None,
            "email": None,
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    def test_identify_with_all_empty_strings(self, resolver):
        """Тест идентификации со всеми пустыми строками"""
        onec_data = {
            "onec_id": "",
            "tax_id": "",
            "email": "",
        }

        customer, method = resolver.identify_customer(onec_data)

        assert customer is None
        assert method is None

    @pytest.mark.django_db
    def test_multiple_users_different_identifiers(self, resolver):
        """Тест с несколькими пользователями с разными идентификаторами"""
        user1 = User.objects.create_user(
            email="user1@example.com",
            password="pass123",
            first_name="User",
            last_name="One",
            onec_id="1C-001",
        )
        user2 = User.objects.create_user(
            email="user2@example.com",
            password="pass123",
            first_name="User",
            last_name="Two",
            tax_id="1111111111",
        )
        user3 = User.objects.create_user(
            email="user3@example.com",
            password="pass123",
            first_name="User",
            last_name="Three",
        )

        # Идентификация каждого пользователя
        customer1, method1 = resolver.identify_customer({"onec_id": "1C-001"})
        assert customer1.id == user1.id
        assert method1 == "onec_id"

        customer2, method2 = resolver.identify_customer({"tax_id": "1111111111"})
        assert customer2.id == user2.id
        assert method2 == "tax_id"

        customer3, method3 = resolver.identify_customer({"email": "user3@example.com"})
        assert customer3.id == user3.id
        assert method3 == "email"

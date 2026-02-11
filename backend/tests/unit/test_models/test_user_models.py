"""
Тесты для моделей пользователей FREESPORT Platform
"""

import time
import uuid
from io import StringIO

import pytest
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.management.commands import createsuperuser
from django.core.exceptions import ValidationError
from django.core.management import CommandError
from django.db import IntegrityError

from apps.users.models import Company
from tests.conftest import AddressFactory, CompanyFactory, UserFactory


@pytest.mark.django_db
class TestUserModel:
    """
    Тесты модели пользователя User
    """

    def test_user_creation_with_valid_data(self):
        """
        Тест создания пользователя с валидными данными
        """
        user = UserFactory.create(
            email="test@freesport.com",
            first_name="Иван",
            last_name="Петров",
            role="retail",
        )

        assert user.email == "test@freesport.com"
        assert user.first_name == "Иван"
        assert user.last_name == "Петров"
        assert user.role == "retail"
        assert user.is_active is True
        assert user.is_verified is False  # По умолчанию не верифицирован
        assert hasattr(user, "username") is False or user.username is None  # Используем email для авторизации

    def test_user_str_representation(self):
        """
        Тест строкового представления пользователя
        """
        user = UserFactory.create(email="test@freesport.com", role="wholesale_level1")
        representation = str(user)

        # Более гибкая проверка содержания ключевых частей
        assert user.email in representation
        assert user.get_role_display() in representation

    def test_user_full_name_property(self):
        """
        Тест свойства full_name
        """
        user = UserFactory.create(first_name="Иван", last_name="Петров")
        assert user.full_name == "Иван Петров"

        # Тест с пустыми полями
        user_empty = UserFactory.create(first_name="", last_name="")
        assert user_empty.full_name == ""

        # Тест с одним заполненным полем
        user_partial = UserFactory.create(first_name="Иван", last_name="")
        assert user_partial.full_name == "Иван"

    def test_unique_email_constraint(self):
        """
        Тест уникальности email
        """
        email = f"duplicate-test-{int(time.time())}-{uuid.uuid4().hex[:8]}@freesport.com"
        UserFactory.create(email=email)

        with pytest.raises(IntegrityError):
            UserFactory.create(email=email)

    def test_valid_phone_number(self):
        """
        Тест валидного номера телефона
        """
        user = UserFactory.build(phone="+79001234567")
        # Проверяем что валидация проходит
        user.full_clean()  # Вызывает валидацию модели
        user.save()
        assert user.phone == "+79001234567"

    @pytest.mark.parametrize(
        "invalid_phone",
        [
            "89001234567",  # Без +7
            "+7900123456",  # Короткий номер
            "+790012345678",  # Длинный номер
            "invalid_phone",  # Нечисловой
        ],
    )
    def test_invalid_phone_number(self, invalid_phone):
        """
        Тест невалидного номера телефона
        """
        with pytest.raises(ValidationError):
            user = UserFactory.build(phone=invalid_phone)
            user.full_clean()

    @pytest.mark.parametrize(
        "role, expected_is_b2b",
        [
            # B2B роли
            ("wholesale_level1", True),
            ("wholesale_level2", True),
            ("wholesale_level3", True),
            ("trainer", True),
            ("federation_rep", True),
            # B2C роли
            ("retail", False),
            ("admin", False),
        ],
    )
    def test_is_b2b_user_property(self, role, expected_is_b2b):
        """
        Тест свойства is_b2b_user для разных ролей
        """
        user = UserFactory.create(role=role)
        assert user.is_b2b_user is expected_is_b2b

    @pytest.mark.parametrize(
        "role, expected_is_wholesale",
        [
            # Оптовые роли
            ("wholesale_level1", True),
            ("wholesale_level2", True),
            ("wholesale_level3", True),
            # Не оптовые роли
            ("retail", False),
            ("trainer", False),
            ("federation_rep", False),
            ("admin", False),
        ],
    )
    def test_is_wholesale_user_property(self, role, expected_is_wholesale):
        """
        Тест свойства is_wholesale_user для разных ролей
        """
        user = UserFactory.create(role=role)
        assert user.is_wholesale_user is expected_is_wholesale

    @pytest.mark.parametrize(
        "role, expected_level",
        [
            # Оптовые пользователи разных уровней
            ("wholesale_level1", 1),
            ("wholesale_level2", 2),
            ("wholesale_level3", 3),
            # Не оптовые пользователи
            ("retail", None),
            ("trainer", None),
            ("federation_rep", None),
            ("admin", None),
        ],
    )
    def test_wholesale_level_property(self, role, expected_level):
        """
        Тест свойства wholesale_level для разных ролей
        """
        user = UserFactory.create(role=role)
        assert user.wholesale_level == expected_level

    @pytest.mark.parametrize(
        "valid_role",
        [
            "retail",
            "wholesale_level1",
            "wholesale_level2",
            "wholesale_level3",
            "trainer",
            "federation_rep",
            "admin",
        ],
    )
    def test_valid_role_choices(self, valid_role):
        """
        Тест валидных ролей
        """
        user = UserFactory.build(role=valid_role)
        user.full_clean()  # Не должно вызывать исключение
        assert user.role == valid_role

    def test_invalid_role_choice(self):
        """
        Тест невалидной роли
        """
        with pytest.raises(ValidationError):
            user = UserFactory.build(role="invalid_role")
            user.full_clean()

    def test_b2b_fields_for_business_users(self):
        """
        Тест B2B полей для бизнес пользователей
        """
        b2b_user = UserFactory.create(
            role="wholesale_level1",
            company_name="ООО Спорт Компани",
            tax_id="7701234567",
            is_verified=True,
        )

        assert b2b_user.company_name == "ООО Спорт Компани"
        assert b2b_user.tax_id == "7701234567"
        assert b2b_user.is_b2b_user is True

    def test_default_values(self):
        """
        Тест значений по умолчанию
        """
        user = UserFactory.create()

        assert user.role == "retail"
        assert user.is_verified is False
        assert user.phone != ""
        assert user.company_name == ""
        assert user.tax_id == ""

    def test_username_field_configuration(self):
        """
        Тест настройки USERNAME_FIELD
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assert User.USERNAME_FIELD == "email"
        assert "first_name" in User.REQUIRED_FIELDS
        assert "last_name" in User.REQUIRED_FIELDS

    def test_meta_configuration(self):
        """
        Тест настроек Meta класса
        """
        from django.contrib.auth import get_user_model

        User = get_user_model()
        assert User._meta.verbose_name == "Пользователь"
        assert User._meta.verbose_name_plural == "Пользователи"
        assert User._meta.db_table == "users"

    def test_user_authentication_with_email(self):
        """
        Тест аутентификации пользователя через email
        """
        # Фабрика автоматически хеширует пароль через PostGenerationMethodCall
        user = UserFactory.create(email="auth@freesport.com", password="test_password123")

        authenticated_user = authenticate(
            username="auth@freesport.com",  # USERNAME_FIELD = email
            password="test_password123",
        )

        assert authenticated_user is not None
        assert authenticated_user == user

    def test_createsuperuser_without_required_fields_fails(self):
        """
        Тест: создание суперпользователя без обязательных полей должно вызывать ошибку
        """
        from django.core.management import call_command
        from django.core.management.base import CommandError

        with pytest.raises((CommandError, SystemExit)):
            call_command(
                "createsuperuser",
                email="admin@test.com",
                interactive=False,
                verbosity=0,
            )

    def test_b2c_user_can_have_empty_b2b_fields(self):
        """
        Тест: B2C пользователь может иметь пустые B2B поля без ошибок
        """
        retail_user = UserFactory.create(
            role="retail",
            company_name="",  # Пустое, но не должно вызывать ошибку
            tax_id="",
            is_verified=False,
        )

        retail_user.full_clean()  # Не должно вызывать ValidationError
        assert retail_user.role == "retail"
        assert retail_user.company_name == ""
        assert retail_user.tax_id == ""
        assert retail_user.is_b2b_user is False


@pytest.mark.django_db
class TestUser1CIntegrationFields:
    """
    Тесты полей интеграции с 1С в модели User
    """

    def test_1c_integration_fields_default_values(self):
        """
        Тест значений по умолчанию для полей интеграции с 1С
        """
        user = UserFactory.create()

        assert user.onec_id is None
        assert user.sync_status == "pending"
        assert user.created_in_1c is False
        assert user.needs_1c_export is False
        assert user.last_sync_at is None
        assert user.sync_error_message == ""

    def test_onec_id_uniqueness(self):
        """
        Тест уникальности onec_id
        """
        unique_onec_id = f"1C-USER-{int(time.time())}-{uuid.uuid4().hex[:8]}"

        # Создаем первого пользователя с уникальным onec_id
        user1 = UserFactory.create(onec_id=unique_onec_id)
        assert user1.onec_id == unique_onec_id

        # Попытка создать второго пользователя с тем же onec_id должна вызвать ошибку
        with pytest.raises(IntegrityError):
            UserFactory.create(onec_id=unique_onec_id)

    def test_onec_id_can_be_null_for_multiple_users(self):
        """
        Тест: несколько пользователей могут иметь NULL значение onec_id
        """
        user1 = UserFactory.create(onec_id=None)
        user2 = UserFactory.create(onec_id=None)

        assert user1.onec_id is None
        assert user2.onec_id is None

    @pytest.mark.parametrize(
        "sync_status, expected_display",
        [
            ("pending", "Ожидает синхронизации"),
            ("synced", "Синхронизирован"),
            ("error", "Ошибка синхронизации"),
            ("conflict", "Конфликт данных"),
        ],
    )
    def test_sync_status_choices(self, sync_status, expected_display):
        """
        Тест валидных статусов синхронизации
        """
        user = UserFactory.create(sync_status=sync_status)
        assert user.sync_status == sync_status
        assert user.get_sync_status_display() == expected_display

    def test_invalid_sync_status(self):
        """
        Тест невалидного статуса синхронизации
        """
        with pytest.raises(ValidationError):
            user = UserFactory.build(sync_status="invalid_status")
            user.full_clean()

    def test_created_in_1c_boolean_field(self):
        """
        Тест поля created_in_1c
        """
        # Пользователь не создан в 1С (по умолчанию)
        user1 = UserFactory.create(created_in_1c=False)
        assert user1.created_in_1c is False

        # Пользователь создан в 1С
        user2 = UserFactory.create(created_in_1c=True)
        assert user2.created_in_1c is True

    def test_needs_1c_export_boolean_field(self):
        """
        Тест поля needs_1c_export
        """
        # Не требует экспорта в 1С (по умолчанию)
        user1 = UserFactory.create(needs_1c_export=False)
        assert user1.needs_1c_export is False

        # Требует экспорта в 1С
        user2 = UserFactory.create(needs_1c_export=True)
        assert user2.needs_1c_export is True

    def test_last_sync_at_datetime_field(self):
        """
        Тест поля last_sync_at
        """
        from datetime import datetime

        from django.utils import timezone

        # Может быть NULL (по умолчанию)
        user1 = UserFactory.create(last_sync_at=None)
        assert user1.last_sync_at is None

        # Может содержать дату и время
        sync_time = timezone.now()
        user2 = UserFactory.create(last_sync_at=sync_time)
        assert user2.last_sync_at == sync_time

    def test_sync_error_message_text_field(self):
        """
        Тест поля sync_error_message
        """
        # Может быть пустым (по умолчанию)
        user1 = UserFactory.create(sync_error_message="")
        assert user1.sync_error_message == ""

        # Может содержать сообщение об ошибке
        error_msg = "Ошибка синхронизации: недоступен сервер 1С"
        user2 = UserFactory.create(sync_error_message=error_msg)
        assert user2.sync_error_message == error_msg

        # Может содержать длинное сообщение
        long_error_msg = "Очень длинное сообщение об ошибке: " + "x" * 1000
        user3 = UserFactory.create(sync_error_message=long_error_msg)
        assert user3.sync_error_message == long_error_msg

    def test_1c_integration_fields_validation(self):
        """
        Тест валидации полей интеграции с 1С
        """
        from django.utils import timezone

        user = UserFactory.build(
            onec_id="1C-USER-123456",
            sync_status="synced",
            created_in_1c=True,
            needs_1c_export=False,
            last_sync_at=timezone.now(),
            sync_error_message="Все в порядке",
        )

        # Валидация должна пройти без ошибок
        user.full_clean()
        user.save()

        assert user.onec_id == "1C-USER-123456"
        assert user.sync_status == "synced"
        assert user.created_in_1c is True
        assert user.needs_1c_export is False
        assert user.last_sync_at is not None
        assert user.sync_error_message == "Все в порядке"

    def test_1c_integration_scenario_import_from_1c(self):
        """
        Тест сценария импорта пользователя из 1С
        """
        from django.utils import timezone

        # Создаем пользователя как будто он был импортирован из 1С
        imported_user = UserFactory.create(
            email="imported@company.ru",
            onec_id="1C-CUSTOMER-987654",
            sync_status="synced",
            created_in_1c=True,
            needs_1c_export=False,
            last_sync_at=timezone.now(),
            sync_error_message="",
        )

        # Проверяем корректность импорта
        assert imported_user.onec_id is not None
        assert imported_user.sync_status == "synced"
        assert imported_user.created_in_1c is True
        assert imported_user.needs_1c_export is False
        assert imported_user.sync_error_message == ""

    def test_1c_integration_scenario_platform_user_needs_export(self):
        """
        Тест сценария пользователя созданного в платформе и требующего экспорта в 1С
        """
        # Создаем пользователя в платформе
        platform_user = UserFactory.create(
            email="platform@company.ru",
            onec_id=None,
            sync_status="pending",
            created_in_1c=False,
            needs_1c_export=True,
            last_sync_at=None,
            sync_error_message="",
        )

        # Проверяем состояние для экспорта в 1С
        assert platform_user.onec_id is None
        assert platform_user.sync_status == "pending"
        assert platform_user.created_in_1c is False
        assert platform_user.needs_1c_export is True
        assert platform_user.last_sync_at is None

    def test_1c_integration_scenario_sync_error(self):
        """
        Тест сценария ошибки синхронизации с 1С
        """
        # Создаем пользователя с ошибкой синхронизации
        error_user = UserFactory.create(
            onec_id="1C-USER-ERROR-123",
            sync_status="error",
            sync_error_message="Таймаут соединения с сервером 1С",
        )

        # Проверяем состояние ошибки
        assert error_user.sync_status == "error"
        assert "Таймаут" in error_user.sync_error_message
        assert error_user.sync_error_message != ""


@pytest.mark.django_db
class TestCompanyModel:
    """
    Тесты модели компании Company
    """

    def test_company_creation(self):
        """
        Тест успешного создания компании
        """
        user = UserFactory.create(role="wholesale_level1", is_verified=True)
        company = CompanyFactory.create(user=user, legal_name='ООО "Рога и Копыта"', tax_id="123456789012")

        assert company.user == user
        assert company.legal_name == 'ООО "Рога и Копыта"'
        assert company.tax_id == "123456789012"
        assert str(company) == 'ООО "Рога и Копыта" (ИНН: 123456789012)'

    def test_tax_id_uniqueness(self):
        """
        Тест: ИНН компании может повторяться у разных пользователей
        """
        user1 = UserFactory.create(role="wholesale_level1")
        user2 = UserFactory.create(role="wholesale_level2")

        test_tax_id = f"{111222333000 + int(time.time()) % 999:012d}"
        CompanyFactory.create(user=user1, tax_id=test_tax_id)

        CompanyFactory.create(user=user2, tax_id=test_tax_id)
        assert Company.objects.filter(tax_id=test_tax_id).count() == 2

    def test_one_to_one_relationship_with_user(self):
        """
        Тест связи OneToOne с пользователем
        """
        user = UserFactory.create(role="wholesale_level1")
        company = CompanyFactory.create(user=user)

        # Проверяем прямую связь
        assert company.user == user
        # Проверяем обратную связь
        assert user.company == company

        # Попытка создать вторую компанию для того же пользователя должна вызвать ошибку
        with pytest.raises(IntegrityError):
            CompanyFactory.create(user=user)

    def test_company_fields_validation(self):
        """
        Тест валидации полей компании
        """
        user = UserFactory.create(role="wholesale_level1")
        company = CompanyFactory.build(
            user=user,
            legal_name="ИП Иванов Иван Иванович",
            tax_id="123456789012",
            kpp="123456789",
            legal_address="г. Москва, ул. Тверская, д. 1",
        )

        company.full_clean()  # Не должно вызывать ValidationError
        assert company.legal_name == "ИП Иванов Иван Иванович"
        assert len(company.tax_id) == 12
        assert len(company.kpp) == 9

    def test_company_meta_configuration(self):
        """
        Тест настроек Meta класса Company
        """
        from apps.users.models import Company

        assert Company._meta.verbose_name == "Компания"
        assert Company._meta.verbose_name_plural == "Компании"
        assert Company._meta.db_table == "companies"


@pytest.mark.django_db
class TestAddressModel:
    """
    Тесты модели адреса Address
    """

    def test_address_creation(self):
        """
        Тест успешного создания адреса
        """
        user = UserFactory.create()
        address = AddressFactory.create(
            user=user,
            city="Москва",
            street="Тверская",
            building="1",
            full_name="Иван Иванов",
        )

        assert address.user == user
        assert address.city == "Москва"
        assert address.street == "Тверская"
        assert address.building == "1"
        assert "Москва, Тверская 1" in str(address)

    def test_full_address_property(self):
        """
        Тест свойства полного адреса
        """
        address = AddressFactory.build(
            postal_code="123456",
            city="Москва",
            street="Тверская",
            building="1",
            apartment="101",
        )

        expected = "123456, Москва, Тверская, 1, кв. 101"
        assert address.full_address == expected

    def test_full_address_property_without_apartment(self):
        """
        Тест свойства полного адреса без квартиры
        """
        address = AddressFactory.build(
            postal_code="654321",
            city="Санкт-Петербург",
            street="Невский проспект",
            building="50",
            apartment="",
        )

        expected = "654321, Санкт-Петербург, Невский проспект, 50"
        assert address.full_address == expected

    def test_multiple_addresses_for_user(self):
        """
        Тест создания нескольких адресов для одного пользователя
        """
        user = UserFactory.create()

        shipping_address = AddressFactory.create(user=user, address_type="shipping", is_default=True)
        legal_address = AddressFactory.create(user=user, address_type="legal", is_default=False)

        assert user.addresses.count() == 2
        assert shipping_address.address_type == "shipping"
        assert legal_address.address_type == "legal"
        assert shipping_address.is_default is True
        assert legal_address.is_default is False

    def test_address_types_choices(self):
        """
        Тест валидных типов адресов
        """
        user = UserFactory.create()

        # Тест валидных типов
        shipping_address = AddressFactory.create(user=user, address_type="shipping")
        legal_address = AddressFactory.create(user=user, address_type="legal")

        shipping_address.full_clean()  # Не должно вызывать ValidationError
        legal_address.full_clean()  # Не должно вызывать ValidationError

        assert shipping_address.address_type == "shipping"
        assert legal_address.address_type == "legal"

    def test_address_str_representation(self):
        """
        Тест строкового представления адреса
        """
        address = AddressFactory.create(full_name="Петр Петров", city="Екатеринбург", street="Ленина", building="25")

        expected = "Петр Петров - Екатеринбург, Ленина 25"
        assert str(address) == expected

    def test_address_meta_configuration(self):
        """
        Тест настроек Meta класса Address
        """
        from apps.users.models import Address

        assert Address._meta.verbose_name == "Адрес"
        assert Address._meta.verbose_name_plural == "Адреса"
        assert Address._meta.db_table == "addresses"

    def test_setting_new_default_address_unsets_old_one(self):
        """
        Тест: установка нового адреса по умолчанию снимает флаг со старого
        """
        user = UserFactory.create()

        # Создаем первый адрес как основной
        addr1 = AddressFactory.create(user=user, address_type="shipping", is_default=True)

        # Создаем второй адрес как не основной
        addr2 = AddressFactory.create(user=user, address_type="shipping", is_default=False)

        # Устанавливаем второй адрес как основной и сохраняем
        addr2.is_default = True
        addr2.save()

        # Обновляем состояние первого адреса из базы данных
        addr1.refresh_from_db()

        # Проверяем, что флаг со старого адреса снят, а у нового установлен
        assert addr1.is_default is False
        assert addr2.is_default is True
        assert user.addresses.filter(address_type="shipping", is_default=True).count() == 1

    def test_multiple_default_addresses_for_different_types(self):
        """
        Тест: пользователь может иметь разные адреса по умолчанию для разных типов
        """
        user = UserFactory.create()

        # Создаем основной адрес доставки
        shipping_addr = AddressFactory.create(user=user, address_type="shipping", is_default=True)

        # Создаем основной юридический адрес
        legal_addr = AddressFactory.create(user=user, address_type="legal", is_default=True)

        # Оба адреса должны остаться основными для своих типов
        assert shipping_addr.is_default is True
        assert legal_addr.is_default is True
        assert user.addresses.filter(is_default=True).count() == 2

        # Но для каждого типа должен быть только один основной
        assert user.addresses.filter(address_type="shipping", is_default=True).count() == 1
        assert user.addresses.filter(address_type="legal", is_default=True).count() == 1

    def test_creating_multiple_default_addresses_same_type_via_factory(self):
        """
        Тест: создание второго адреса по умолчанию через фабрику
        автоматически снимает флаг с первого
        """
        user = UserFactory.create()

        # Создаем первый основной адрес
        addr1 = AddressFactory.create(user=user, address_type="shipping", is_default=True)

        # Создаем второй основной адрес - должен автоматически снять флаг с первого
        addr2 = AddressFactory.create(user=user, address_type="shipping", is_default=True)

        # Обновляем первый адрес из базы
        addr1.refresh_from_db()

        # У первого адреса флаг должен быть снят
        assert addr1.is_default is False
        assert addr2.is_default is True
        assert user.addresses.filter(address_type="shipping", is_default=True).count() == 1

    @pytest.mark.parametrize(
        "address_type, expected_display",
        [
            ("shipping", "Адрес доставки"),
            ("legal", "Юридический адрес"),
        ],
    )
    def test_address_type_display(self, address_type, expected_display):
        """
        Тест отображения типов адресов
        """
        address = AddressFactory.create(address_type=address_type)
        assert address.get_address_type_display() == expected_display

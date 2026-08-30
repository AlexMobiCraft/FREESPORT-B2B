"""
Тесты для User Serializers - Story 2.2 User Management API
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings

from apps.users.serializers import (
    AddressSerializer,
    FavoriteSerializer,
    LogoutSerializer,
    OrderHistorySerializer,
    UserDashboardSerializer,
    UserLoginSerializer,
    UserProfileSerializer,
    UserRegistrationSerializer,
    get_self_service_roles,
)
from apps.users.views.personal_cabinet import DashboardData

User = get_user_model()


@pytest.mark.django_db
class TestUserRegistrationSerializer:
    """Тесты сериализатора регистрации пользователей"""

    def test_retail_role_is_rejected(self, user_factory):
        """Розничная саморегистрация отключена: роль не проходит валидацию"""
        data = {
            "email": "test@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "role": "retail",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert serializer.errors["role"] == ["Недопустимая роль для регистрации."]

    @override_settings(REGISTRATION_ALLOW_RETAIL=True)
    def test_retail_registration_when_flag_enabled(self, user_factory):
        """
        Отключение розницы временное: при REGISTRATION_ALLOW_RETAIL=True заявка
        снова проходит, а аккаунт создаётся сразу активным и верифицированным —
        розничному покупателю верификация менеджером не нужна.
        """
        data = {
            "email": "retail_enabled@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Розница",
            "last_name": "Покупатель",
            "phone": "+79991234571",
            "role": "retail",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        user = serializer.save()
        assert user.role == "retail"
        assert user.is_active is True
        assert user.is_verified is True
        assert user.verification_status == "verified"

    @override_settings(REGISTRATION_ALLOW_RETAIL=True)
    def test_retail_tax_id_is_discarded_when_flag_enabled(self, user_factory):
        """
        ИНН, оставшийся в форме после переключения роли, розничной заявке не
        принадлежит: матч по нему (приоритет выше email) привязал бы её к чужому
        юрлицу из 1С.
        """
        data = {
            "email": "retail_tax@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Розница",
            "last_name": "Покупатель",
            "phone": "+79991234572",
            "role": "retail",
            "tax_id": "7712345678",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        user = serializer.save()
        assert user.tax_id == ""

    @override_settings(REGISTRATION_ALLOW_RETAIL=True)
    def test_retail_registration_does_not_queue_b2b_emails(self, user_factory):
        """Розничная заявка не требует верификации — письма менеджеру не идут."""
        data = {
            "email": "retail_no_mail@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Розница",
            "last_name": "Покупатель",
            "phone": "+79991234573",
            "role": "retail",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        with (
            patch("apps.users.serializers.send_admin_verification_email.delay") as admin_email,
            patch("apps.users.serializers.send_user_pending_email.delay") as user_email,
            patch("apps.users.serializers.send_manager_region_email.delay") as manager_email,
        ):
            serializer.save()

        admin_email.assert_not_called()
        user_email.assert_not_called()
        manager_email.assert_not_called()

    def test_self_service_roles_follow_the_flag(self):
        """Флаг — единственный переключатель состава ролей саморегистрации."""
        assert get_self_service_roles() == frozenset(User.B2B_ROLES)

        with override_settings(REGISTRATION_ALLOW_RETAIL=True):
            assert get_self_service_roles() == frozenset(User.B2B_ROLES) | {"retail"}

    @pytest.mark.parametrize("service_role", ["admin", "unregistered"])
    def test_service_roles_are_rejected(self, user_factory, service_role):
        """
        SELF_SERVICE_ROLES — белый список: служебные роли заявитель назначить
        себе не может. `admin` дал бы метку администратора в интерфейсе,
        `unregistered` ставит только импорт 1С, и такой аккаунт не попал бы
        в admin-действие верификации.
        """
        data = {
            "email": "service_role@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "role": service_role,
            "company_name": "Тест Клуб",
            "tax_id": "7712345670",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert serializer.errors["role"] == ["Недопустимая роль для регистрации."]

    def test_missing_role_is_rejected(self, user_factory):
        """
        Без явной роли заявка отклоняется: модельный default="retail" иначе
        молча создал бы розничный аккаунт.
        """
        data = {
            "email": "test@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "role" in serializer.errors

    def test_valid_b2b_user_registration(self, user_factory):
        """Тест создания B2B пользователя"""
        data = {
            "email": "b2b@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "B2B",
            "last_name": "Пользователь",
            "phone": "+79991234567",
            "role": "wholesale_level1",
            "company_name": "Тест Компания",
            "tax_id": "1234567890",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        user = serializer.save()
        assert user.email == "b2b@test.com"
        assert user.role == "wholesale_level1"
        assert user.company_name == "Тест Компания"

    def test_password_mismatch(self, user_factory):
        """Тест несовпадения паролей"""
        data = {
            "email": "test@test.com",
            "password": "TestPass123!",
            "password_confirm": "DifferentPass123!",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "role": "trainer",
            "company_name": "Тест Клуб",
            "tax_id": "7712345678",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "password_confirm" in serializer.errors

    def test_duplicate_email(self, user_factory):
        """Тест дублирования email"""
        user_factory.create(email="existing@test.com")

        data = {
            "email": "existing@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "role": "trainer",
            "company_name": "Тест Клуб",
            "tax_id": "7712345679",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_b2b_missing_company_data(self, user_factory):
        """Тест B2B регистрации без данных компании"""
        data = {
            "email": "b2b@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "B2B",
            "last_name": "Пользователь",
            "phone": "+79991234568",
            "role": "wholesale_level1",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert not serializer.is_valid()
        assert "company_name" in serializer.errors


@pytest.mark.unit
@pytest.mark.django_db
class TestWholesaleLevel4Registration:
    """
    Стори 39.3, AC7: роль уровня 4 доступна для самостоятельной регистрации.

    До правки роль уже публиковалась в /api/v1/users/roles/ (список строится
    из User.ROLE_CHOICES), но регистрация с ней падала с 400 «Недопустимая
    роль для регистрации» — витрина предлагала то, чего бэкенд не принимал.
    """

    def test_role_is_self_service(self):
        """Роль входит в белый список самостоятельно выбираемых"""
        assert "wholesale_level4" in get_self_service_roles()

    def test_valid_wholesale_level4_registration(self, user_factory):
        """Регистрация с ролью уровня 4 проходит валидацию и создаёт пользователя"""
        data = {
            "email": "opt4@test.com",
            "password": "TestPass123!",
            "password_confirm": "TestPass123!",
            "first_name": "Опт",
            "last_name": "Четвёртый",
            "phone": "+79991234570",
            "role": "wholesale_level4",
            "company_name": "ООО Опт 4",
            "tax_id": "1234567890",
            "pdp_consent": True,
        }

        serializer = UserRegistrationSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        user = serializer.save()
        assert user.role == "wholesale_level4"

    def test_validate_role_accepts_level4(self):
        """validate_role возвращает роль без ошибки"""
        assert UserRegistrationSerializer().validate_role("wholesale_level4") == "wholesale_level4"


@pytest.mark.django_db
class TestUserLoginSerializer:
    """Тесты сериализатора входа пользователя"""

    def test_valid_login(self, user_factory):
        """Тест успешного входа"""
        user = user_factory.create(email="test@test.com", password="testpass123")

        data = {"email": "test@test.com", "password": "testpass123"}

        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid(), serializer.errors

        validated_data = serializer.validated_data
        assert validated_data["user"] == user

    def test_invalid_email(self, user_factory):
        """Тест неверного email"""
        data = {"email": "nonexistent@test.com", "password": "testpass123"}

        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_invalid_password(self, user_factory):
        """Тест неверного пароля"""
        user_factory.create(email="test@test.com", password="correctpass")

        data = {"email": "test@test.com", "password": "wrongpass"}

        serializer = UserLoginSerializer(data=data)
        assert not serializer.is_valid()
        assert "non_field_errors" in serializer.errors

    def test_inactive_user_login(self, user_factory):
        """Тест входа неактивного пользователя"""
        user = user_factory.create(email="inactive@test.com", password="testpass123", is_active=False)

        data = {"email": "inactive@test.com", "password": "testpass123"}

        serializer = UserLoginSerializer(data=data)
        assert serializer.is_valid(), serializer.errors
        assert serializer.validated_data["user"] == user


@pytest.mark.django_db
class TestUserProfileSerializer:
    """Тесты сериализатора профиля пользователя"""

    def test_profile_serialization(self, user_factory):
        """Тест сериализации профиля пользователя"""
        user = user_factory.create(
            email="test@test.com",
            first_name="Тест",
            last_name="Пользователь",
            phone="+7999123456",
        )

        serializer = UserProfileSerializer(user)
        data = serializer.data

        assert data["email"] == "test@test.com"
        assert data["first_name"] == "Тест"
        assert data["last_name"] == "Пользователь"
        assert data["phone"] == "+7999123456"

    def test_profile_update(self, user_factory):
        """Тест обновления профиля"""
        user = user_factory.create(email="test@test.com", first_name="Старое", last_name="Имя")

        data = {"first_name": "Новое", "last_name": "Имя", "phone": "+79996543210"}

        serializer = UserProfileSerializer(user, data=data, partial=True)
        assert serializer.is_valid(), serializer.errors

        updated_user = serializer.save()
        assert updated_user.first_name == "Новое"
        assert updated_user.last_name == "Имя"
        assert updated_user.phone == "+79996543210"

    def test_email_update_not_allowed(self, user_factory):
        """Тест что email нельзя изменить через профиль"""
        user = user_factory.create(email="original@test.com")

        data = {"email": "new@test.com"}

        serializer = UserProfileSerializer(user, data=data, partial=True)
        assert serializer.is_valid()

        updated_user = serializer.save()
        assert updated_user.email == "original@test.com"


@pytest.mark.django_db
class TestAddressSerializer:
    """Тесты сериализатора адресов"""

    def test_address_creation(self, user_factory, address_factory):
        """Тест создания адреса"""
        user = user_factory.create()

        data = {
            "address_type": "shipping",
            "full_name": "Иван Петров",
            "phone": "+79001234567",
            "city": "Москва",
            "street": "Тверская",
            "building": "1",
            "apartment": "10",
            "postal_code": "101000",
            "is_default": True,
        }

        serializer = AddressSerializer(data=data, context={"user": user})
        assert serializer.is_valid(), serializer.errors

        # Передаем пользователя явно при сохранении
        address = serializer.save(user=user)
        assert address.city == "Москва"
        assert address.is_default is True
        assert address.user == user

    def test_address_validation(self, user_factory):
        """Тест валидации адреса"""
        user = user_factory.create()

        data = {"address_type": "invalid_type", "city": "Москва"}

        serializer = AddressSerializer(data=data)
        assert not serializer.is_valid()
        expected_errors = ["full_name", "phone", "street", "building", "postal_code"]
        for field in expected_errors:
            assert field in serializer.errors


@pytest.mark.django_db
class TestFavoriteSerializer:
    """Тесты сериализатора избранного"""

    def test_favorite_serialization(self, user_factory, product_factory):
        """Тест сериализации избранного товара"""
        user = user_factory.create()
        product = product_factory.create(name="Тестовый товар")

        favorite_data = {"user": user, "product": product}

        # Создаем объект избранного напрямую для тестирования сериализации
        from apps.users.models import Favorite

        favorite = Favorite.objects.create(**favorite_data)

        serializer = FavoriteSerializer(favorite)
        data = serializer.data

        assert "product" in data
        assert "created_at" in data

    def test_favorite_creation_validation(self, user_factory, product_factory):
        """Тест валидации создания избранного"""
        user = user_factory.create()
        product = product_factory.create()

        data = {"product": product.id}

        # Передаем context с user для корректного создания
        serializer = FavoriteSerializer(data=data, context={"request": type("obj", (object,), {"user": user})()})
        assert serializer.is_valid(), serializer.errors

        favorite = serializer.save(user=user)
        assert favorite.user == user
        assert favorite.product == product


@pytest.mark.django_db
class TestUserDashboardSerializer:
    """Тесты сериализатора дашборда пользователя"""

    def test_dashboard_data(self, user_factory):
        """Тест данных дашборда"""
        user = user_factory.create(role="retail")

        dashboard_data = DashboardData(
            user_info=user,
            orders_count=5,
            favorites_count=10,
            addresses_count=2,
            total_order_amount=50000.00,
        )
        serializer = UserDashboardSerializer(dashboard_data)
        data = serializer.data

        assert "orders_count" in data
        assert "favorites_count" in data
        assert "addresses_count" in data
        assert data["orders_count"] == 5
        assert data["favorites_count"] == 10


@pytest.mark.django_db
class TestOrderHistorySerializer:
    """Тесты сериализатора истории заказов"""

    def test_order_serialization(self, user_factory, order_factory, order_item_factory):
        """Тест сериализации заказа для истории"""
        user = user_factory.create()
        order = order_factory.create(
            user=user,
            order_number="TEST-001",
            status="delivered",
            payment_status="paid",
            total_amount=15000.00,
            discount_amount=500.00,
            delivery_cost=300.00,
        )

        # Добавляем товары в заказ
        order_item_factory.create(order=order, quantity=2, unit_price=5000.00)
        order_item_factory.create(order=order, quantity=1, unit_price=5000.00)

        serializer = OrderHistorySerializer(order)
        data = serializer.data

        # Проверяем основные поля
        assert data["order_number"] == "TEST-001"
        assert data["status"] == "delivered"
        assert data["status_display"] == "Доставлен"
        assert data["payment_status"] == "paid"
        assert data["payment_status_display"] == "Оплачен"
        assert float(data["total_amount"]) == 15000.00
        assert float(data["discount_amount"]) == 500.00
        assert float(data["delivery_cost"]) == 300.00
        assert data["items_count"] == 3  # 2 + 1 товар

        # Проверяем readonly поля
        assert "created_at" in data
        assert "updated_at" in data
        assert "customer_display_name" in data

    def test_order_items_count_calculation(self, user_factory, order_factory, order_item_factory):
        """Тест подсчета количества товаров в заказе"""
        user = user_factory.create()
        order = order_factory.create(user=user)

        # Создаем несколько товаров с разным количеством
        order_item_factory.create(order=order, quantity=3)
        order_item_factory.create(order=order, quantity=2)
        order_item_factory.create(order=order, quantity=1)

        serializer = OrderHistorySerializer(order)
        data = serializer.data

        assert data["items_count"] == 6  # 3 + 2 + 1

    def test_empty_order_items_count(self, user_factory, order_factory):
        """Тест заказа без товаров"""
        user = user_factory.create()
        order = order_factory.create(user=user)

        serializer = OrderHistorySerializer(order)
        data = serializer.data

        assert data["items_count"] == 0

    def test_customer_display_name_for_user_order(self, user_factory, order_factory):
        """Тест отображения имени клиента для заказа пользователя"""
        user = user_factory.create(first_name="Иван", last_name="Петров", email="ivan@test.com")
        order = order_factory.create(user=user)

        serializer = OrderHistorySerializer(order)
        data = serializer.data

        # customer_display_name должен возвращать полное имя пользователя
        expected_name = user.get_full_name() or user.email
        assert data["customer_display_name"] == expected_name

    def test_readonly_fields(self, user_factory, order_factory):
        """Тест что все поля только для чтения"""
        user = user_factory.create()
        order = order_factory.create(user=user)

        serializer = OrderHistorySerializer(order)

        # Все поля должны быть readonly
        readonly_fields = serializer.Meta.read_only_fields
        expected_fields = [
            "id",
            "order_number",
            "status",
            "status_display",
            "payment_status",
            "payment_status_display",
            "total_amount",
            "discount_amount",
            "delivery_cost",
            "items_count",
            "customer_display_name",
            "created_at",
            "updated_at",
        ]

        assert set(readonly_fields) == set(expected_fields)


@pytest.mark.unit
class TestLogoutSerializer:
    """Unit-тесты для LogoutSerializer - Story 30.2"""

    def test_valid_refresh_token(self):
        """Валидный refresh token проходит валидацию"""
        data = {"refresh": "valid-token-string-here"}
        serializer = LogoutSerializer(data=data)

        assert serializer.is_valid()
        assert serializer.validated_data["refresh"] == "valid-token-string-here"

    def test_missing_refresh_token(self):
        """Отсутствие refresh токена вызывает ошибку"""
        data = {}
        serializer = LogoutSerializer(data=data)

        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_empty_refresh_token(self):
        """Пустой refresh токен вызывает ошибку"""
        data = {"refresh": ""}
        serializer = LogoutSerializer(data=data)

        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_none_refresh_token(self):
        """None в качестве refresh токена вызывает ошибку"""
        data = {"refresh": None}
        serializer = LogoutSerializer(data=data)

        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

    def test_whitespace_only_refresh_token(self):
        """Токен из пробелов проходит базовую валидацию CharField"""
        # CharField считает пробелы валидным значением
        # Реальная валидация токена произойдёт в view при создании RefreshToken
        data = {"refresh": "   "}
        serializer = LogoutSerializer(data=data)

        # CharField не отклонит пробелы, но custom validator должен
        assert not serializer.is_valid()
        assert "refresh" in serializer.errors

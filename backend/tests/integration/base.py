"""
Базовый класс для функциональных тестов с автоматической подготовкой окружения
"""

import os
import sys

import redis
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient, APITestCase

# Настройка Django окружения
backend_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(backend_path)
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freesport.settings.test")

import django

django.setup()

from apps.users.models import User


class BaseFunctionalTest(APITestCase):
    """
    Базовый класс для функциональных тестов
    Автоматически:
    - Очищает кэш перед каждым тестом
    - Загружает необходимые тестовые данные
    - Настраивает API клиент
    """

    @classmethod
    def setUpClass(cls):
        """Настройка класса тестов"""
        super().setUpClass()
        cls.client = APIClient()
        print(f"\n🧪 Запуск функциональных тестов: {cls.__name__}")

    def setUp(self):
        """Подготовка перед каждым тестом"""
        super().setUp()

        # Очищаем кэш
        self.clear_all_cache()

        # Загружаем базовые тестовые данные
        self.load_test_data()

        # Настраиваем API клиент
        self.client = APIClient()

    def tearDown(self):
        """Очистка после каждого теста"""
        super().tearDown()

        # Очищаем кэш после теста
        self.clear_all_cache()

    def clear_all_cache(self):
        """Очищает все виды кэша"""
        try:
            # Очищаем Django кэш
            cache.clear()

            # Очищаем Redis кэш
            try:
                r = redis.Redis(host="localhost", port=6379, db=1)
                r.flushdb()
            except:
                pass  # Redis может быть недоступен в некоторых тестах

        except Exception as e:
            print(f"   ⚠️ Предупреждение при очистке кэша: {e}")

    def load_test_data(self):
        """
        Загружает базовые тестовые данные
        Переопределите в наследуемых классах для специфичных данных
        """
        # Создаем тестовых пользователей если их нет
        self.create_test_users()

    def create_test_users(self):
        """Создает базовых тестовых пользователей"""
        # Создаем retail пользователя
        if not User.objects.filter(email="retail@test.com").exists():
            self.retail_user = User.objects.create_user(
                email="retail@test.com",
                password="TestPass123!",
                first_name="Иван",
                last_name="Петров",
                phone="+79001234567",
                role="retail",
            )
        else:
            self.retail_user = User.objects.get(email="retail@test.com")

        # Создаем B2B пользователя
        if not User.objects.filter(email="b2b@test.com").exists():
            self.b2b_user = User.objects.create_user(
                email="b2b@test.com",
                password="TestPass123!",
                first_name="Мария",
                last_name="Сидорова",
                phone="+79001234568",
                role="wholesale_level1",
                is_verified=True,
                company_name="ООО Тест",
                tax_id="1234567890",
            )
        else:
            self.b2b_user = User.objects.get(email="b2b@test.com")

        # Создаем представителя федерации
        if not User.objects.filter(email="federation@test.com").exists():
            self.federation_user = User.objects.create_user(
                email="federation@test.com",
                password="TestPass123!",
                first_name="Алексей",
                last_name="Федоров",
                phone="+79001234569",
                role="federation_rep",
                is_verified=True,
                company_name="Федерация Спорта",
            )
        else:
            self.federation_user = User.objects.get(email="federation@test.com")

    def authenticate_user(self, user):
        """Аутентифицирует пользователя для API запросов"""
        login_data = {"email": user.email, "password": "TestPass123!"}
        response = self.client.post("/api/auth/login/", login_data)
        if response.status_code == 200 and "access" in response.data:
            token = response.data["access"]
            self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
            return token
        return None

    def logout_user(self):
        """Выходит из системы (убирает токен авторизации)"""
        self.client.credentials()

    def assert_api_success(self, response, expected_status=status.HTTP_200_OK):
        """Проверяет успешность API ответа"""
        self.assertEqual(
            response.status_code,
            expected_status,
            (
                f"Ожидался статус {expected_status}, получен {response.status_code}. "
                f"Ответ: {response.data if hasattr(response, 'data') else ''}"
            ),
        )

    def assert_api_error(self, response, expected_status=status.HTTP_400_BAD_REQUEST):
        """Проверяет что API вернул ошибку"""
        self.assertEqual(
            response.status_code,
            expected_status,
            (
                f"Ожидалась ошибка {expected_status}, получен {response.status_code}. "
                f"Ответ: {response.data if hasattr(response, 'data') else ''}"
            ),
        )

    def print_test_info(self, test_name, description):
        """Выводит информацию о тесте"""
        print(f"\n   🔍 {test_name}: {description}")


class UserManagementFunctionalTest(BaseFunctionalTest):
    """
    Специализированный базовый класс для тестов User Management API
    """

    def load_test_data(self):
        """Загружает данные специфичные для User Management тестов"""
        super().load_test_data()

        # Дополнительные данные для User Management тестов
        # Например, создание дополнительных ролей, групп и т.д.
        pass


class CartFunctionalTest(BaseFunctionalTest):
    """
    Специализированный базовый класс для тестов Cart API
    """

    def load_test_data(self):
        """Загружает данные специфичные для Cart тестов"""
        super().load_test_data()

        # Дополнительные данные для Cart тестов
        # Например, создание товаров, категорий и т.д.
        pass

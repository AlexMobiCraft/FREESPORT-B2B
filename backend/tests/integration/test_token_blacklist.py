"""
Интеграционные тесты для JWT Token Blacklist механизма (Story 30.1)

Проверяет:
1. Конфигурацию blacklist в settings
2. Наличие таблиц в БД
3. Работу blacklist механизма при refresh токенах
4. Автоматическое добавление токенов в blacklist при ротации
"""

from __future__ import annotations

import pytest
from django.conf import settings
from django.db import connection
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.models import User


@pytest.mark.integration
@pytest.mark.django_db
class TestTokenBlacklistConfiguration:
    """Тесты конфигурации JWT Token Blacklist"""

    def test_token_blacklist_in_installed_apps(self) -> None:
        """Проверка наличия token_blacklist в INSTALLED_APPS"""
        assert (
            "rest_framework_simplejwt.token_blacklist" in settings.INSTALLED_APPS
        ), "token_blacklist должен быть в INSTALLED_APPS"

    def test_jwt_rotate_refresh_tokens_enabled(self) -> None:
        """Проверка включения ROTATE_REFRESH_TOKENS"""
        assert settings.SIMPLE_JWT.get("ROTATE_REFRESH_TOKENS") is True, "ROTATE_REFRESH_TOKENS должен быть True"

    def test_jwt_blacklist_after_rotation_enabled(self) -> None:
        """Проверка включения BLACKLIST_AFTER_ROTATION"""
        assert settings.SIMPLE_JWT.get("BLACKLIST_AFTER_ROTATION") is True, "BLACKLIST_AFTER_ROTATION должен быть True"


@pytest.mark.integration
@pytest.mark.django_db
class TestTokenBlacklistDatabaseTables:
    """Тесты структуры БД для blacklist"""

    def test_outstanding_token_table_exists(self) -> None:
        """Проверка существования таблицы token_blacklist_outstandingtoken"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'token_blacklist_outstandingtoken'
                );
                """
            )
            exists = cursor.fetchone()[0]
        assert exists, "Таблица token_blacklist_outstandingtoken должна существовать"

    def test_blacklisted_token_table_exists(self) -> None:
        """Проверка существования таблицы token_blacklist_blacklistedtoken"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'token_blacklist_blacklistedtoken'
                );
                """
            )
            exists = cursor.fetchone()[0]
        assert exists, "Таблица token_blacklist_blacklistedtoken должна существовать"

    def test_outstanding_token_indexes_exist(self) -> None:
        """Проверка наличия индексов на таблице OutstandingToken"""
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'token_blacklist_outstandingtoken'
                ORDER BY indexname;
                """
            )
            indexes = [row[0] for row in cursor.fetchall()]

        # Проверяем ключевые индексы
        assert any("jti" in idx for idx in indexes), "Должен быть индекс на поле jti_hex"
        assert any("user" in idx for idx in indexes), "Должен быть индекс на поле user_id"


@pytest.mark.integration
@pytest.mark.django_db
class TestTokenBlacklistMechanism:
    """Тесты механизма blacklist токенов"""

    @pytest.fixture(autouse=True)
    def setup(self, db) -> None:
        """Настройка для каждого теста"""
        # Очистка таблиц blacklist
        BlacklistedToken.objects.all().delete()
        OutstandingToken.objects.all().delete()

        # Создание тестового пользователя с уникальным email
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.test_user = User.objects.create_user(
            email=f"blacklist_test_{timestamp}@example.com",
            password="TestPassword123!",
            first_name="Test",
            last_name="Blacklist",
            role="retail",
            is_verified=True,
        )

    def test_refresh_token_creates_outstanding_token_record(self) -> None:
        """Генерация refresh токена создаёт запись в OutstandingToken"""
        initial_count = OutstandingToken.objects.filter(user=self.test_user).count()

        # Генерация refresh токена
        refresh = RefreshToken.for_user(self.test_user)

        # Проверка создания записи
        final_count = OutstandingToken.objects.filter(user=self.test_user).count()
        assert final_count == initial_count + 1, "Должна быть создана запись в OutstandingToken"

    def test_blacklist_token_creates_blacklisted_record(self) -> None:
        """Blacklist токена создаёт запись в BlacklistedToken"""
        refresh = RefreshToken.for_user(self.test_user)
        initial_count = BlacklistedToken.objects.count()

        # Blacklist токена
        refresh.blacklist()

        # Проверка создания записи
        final_count = BlacklistedToken.objects.count()
        assert final_count == initial_count + 1, "Должна быть создана запись в BlacklistedToken"

    def test_blacklisted_token_cannot_be_used(self) -> None:
        """Blacklisted токен не может быть использован для refresh"""
        refresh = RefreshToken.for_user(self.test_user)
        refresh_token_str = str(refresh)

        # Blacklist токена
        refresh.blacklist()

        # Попытка использовать blacklisted токен
        with pytest.raises(TokenError) as exc_info:
            RefreshToken(refresh_token_str)

        assert (
            "черный список" in str(exc_info.value).lower() or "blacklist" in str(exc_info.value).lower()
        ), "Должна быть ошибка о blacklist"

    def test_non_blacklisted_token_works_normally(self) -> None:
        """Не-blacklisted токен работает нормально"""
        refresh = RefreshToken.for_user(self.test_user)
        refresh_token_str = str(refresh)

        # Токен не добавлен в blacklist, должен работать
        try:
            new_refresh = RefreshToken(refresh_token_str)
            assert new_refresh is not None, "Токен должен быть валидным"
        except TokenError:
            pytest.fail("Не-blacklisted токен должен работать нормально")

    def test_multiple_tokens_can_be_blacklisted(self) -> None:
        """Несколько токенов могут быть добавлены в blacklist"""
        tokens = [RefreshToken.for_user(self.test_user) for _ in range(3)]
        initial_count = BlacklistedToken.objects.count()

        # Blacklist всех токенов
        for token in tokens:
            token.blacklist()

        # Проверка количества записей
        final_count = BlacklistedToken.objects.count()
        assert final_count == initial_count + 3, "Должно быть добавлено 3 записи в BlacklistedToken"


@pytest.mark.integration
@pytest.mark.django_db
class TestTokenRotationWithBlacklist:
    """Тесты ротации токенов с автоматическим blacklist"""

    @pytest.fixture(autouse=True)
    def setup(self, db) -> None:
        """Настройка для каждого теста"""
        # Очистка таблиц
        BlacklistedToken.objects.all().delete()
        OutstandingToken.objects.all().delete()
        User.objects.filter(email__startswith="rotation_test_").delete()

        # Создание пользователя
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.test_user = User.objects.create_user(
            email=f"rotation_test_{timestamp}@example.com",
            password="TestPassword123!",
            first_name="Rotation",
            last_name="Test",
            role="retail",
            is_verified=True,
        )
        self.client = APIClient()

    def test_token_refresh_with_rotation_via_api(self) -> None:
        """
        Проверка ротации токенов через API endpoint.

        При ROTATE_REFRESH_TOKENS=True и BLACKLIST_AFTER_ROTATION=True:
        - Старый refresh токен должен быть добавлен в blacklist
        - Должен быть возвращён новый refresh токен
        """
        # Получение первого токена через login
        refresh = RefreshToken.for_user(self.test_user)
        old_refresh_token = str(refresh)
        access_token = str(refresh.access_token)

        initial_blacklist_count = BlacklistedToken.objects.count()

        # Refresh токена через API
        response = self.client.post("/api/v1/auth/refresh/", {"refresh": old_refresh_token}, format="json")

        assert (
            response.status_code == status.HTTP_200_OK
        ), f"Refresh должен быть успешным, получен статус {response.status_code}"
        assert "refresh" in response.data, "Должен быть возвращён новый refresh токен"
        assert "access" in response.data, "Должен быть возвращён новый access токен"

        new_refresh_token = response.data["refresh"]
        assert new_refresh_token != old_refresh_token, "Новый refresh токен должен отличаться"

        # Проверка что старый токен добавлен в blacklist
        final_blacklist_count = BlacklistedToken.objects.count()
        assert final_blacklist_count == initial_blacklist_count + 1, "Старый токен должен быть добавлен в blacklist"

        # Проверка что старый токен больше не работает
        old_token_response = self.client.post("/api/v1/auth/refresh/", {"refresh": old_refresh_token}, format="json")
        assert (
            old_token_response.status_code == status.HTTP_401_UNAUTHORIZED
        ), "Старый токен не должен работать после ротации"


@pytest.mark.integration
@pytest.mark.django_db
class TestLogoutView:
    """Integration-тесты для Logout View - Story 30.2"""

    @pytest.fixture(autouse=True)
    def setup(self, db) -> None:
        """Настройка для каждого теста"""
        # Очистка таблиц
        BlacklistedToken.objects.all().delete()
        OutstandingToken.objects.all().delete()
        User.objects.filter(email__startswith="logout_test_").delete()

        # Создание пользователя с уникальным email
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
        self.test_user = User.objects.create_user(
            email=f"logout_test_{timestamp}@example.com",
            password="TestPassword123!",
            first_name="Logout",
            last_name="Test",
            role="retail",
            is_verified=True,
        )
        self.client = APIClient()

    def test_successful_logout(self) -> None:
        """Успешный logout с валидным токеном"""
        # Arrange - создать токены
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Act - выполнить logout
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post("/api/v1/auth/logout/", data={"refresh": refresh_token}, format="json")

        # Assert - проверка ответа
        assert (
            response.status_code == status.HTTP_204_NO_CONTENT
        ), f"Logout должен вернуть 204, получен {response.status_code}"

        # Проверка что токен в blacklist
        assert BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists(), "Токен должен быть в blacklist"

    def test_logout_without_authentication(self) -> None:
        """Logout без аутентификации возвращает 401"""
        # Act - попытка logout без токена
        response = self.client.post("/api/v1/auth/logout/", data={"refresh": "fake-token"}, format="json")

        # Assert
        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Должен вернуть 401, получен {response.status_code}"

    def test_logout_with_invalid_token(self) -> None:
        """Logout с невалидным токеном возвращает 400"""
        # Arrange
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)

        # Act - logout с невалидным refresh токеном
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post(
            "/api/v1/auth/logout/",
            data={"refresh": "invalid-token-string"},
            format="json",
        )

        # Assert
        assert (
            response.status_code == status.HTTP_400_BAD_REQUEST
        ), f"Должен вернуть 400, получен {response.status_code}"
        assert "error" in response.data, "Должно быть сообщение об ошибке"

    def test_blacklisted_token_cannot_refresh(self) -> None:
        """Blacklisted токен не может получить новый access token"""
        # Arrange - создать токены и выполнить logout
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        self.client.post("/api/v1/auth/logout/", data={"refresh": refresh_token}, format="json")

        # Act - попытка refresh с blacklisted токеном
        response = self.client.post("/api/v1/auth/refresh/", data={"refresh": refresh_token}, format="json")

        # Assert
        assert (
            response.status_code == status.HTTP_401_UNAUTHORIZED
        ), f"Blacklisted токен не должен работать, получен {response.status_code}"

    def test_logout_with_already_blacklisted_token(self) -> None:
        """Logout с уже blacklisted токеном возвращает 400"""
        # Arrange - создать токен и добавить в blacklist
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)
        refresh.blacklist()  # Добавляем в blacklist вручную

        # Act - попытка logout с blacklisted токеном
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        response = self.client.post("/api/v1/auth/logout/", data={"refresh": refresh_token}, format="json")

        # Assert
        assert (
            response.status_code == status.HTTP_400_BAD_REQUEST
        ), f"Должен вернуть 400, получен {response.status_code}"

    def test_logout_audit_logging(self, caplog) -> None:
        """Проверка audit logging при logout"""
        import re
        from datetime import datetime

        # Arrange
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # Act - выполнить logout с логированием
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        with caplog.at_level("INFO", logger="apps.users.auth"):
            response = self.client.post(
                "/api/v1/auth/logout/",
                data={"refresh": refresh_token},
                format="json",
                REMOTE_ADDR="192.168.1.100",
            )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверка audit log записи
        log_record = next(
            (r for r in caplog.records if "[AUDIT]" in r.message and "User logout successful" in r.message),
            None,
        )
        assert log_record is not None, "Audit log не найден"
        assert log_record.levelname == "INFO"

        # Проверка содержания audit trail
        log_message = log_record.message
        assert "[AUDIT]" in log_message
        assert f"user_id={self.test_user.id}" in log_message
        assert f"email={self.test_user.email}" in log_message
        assert "ip=192.168.1.100" in log_message

        # Проверка ISO 8601 timestamp формата
        timestamp_match = re.search(r"timestamp=([^\s|]+)", log_message)
        assert timestamp_match is not None, "Timestamp не найден в логе"
        timestamp_str = timestamp_match.group(1)
        # Проверка парсинга timestamp
        parsed_timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        assert parsed_timestamp is not None, "Timestamp должен быть в ISO 8601 формате"

    def test_logout_failed_audit_logging(self, caplog) -> None:
        """Проверка WARNING логирования при неуспешном logout"""
        # Arrange
        refresh = RefreshToken.for_user(self.test_user)
        access_token = str(refresh.access_token)

        # Act - logout с невалидным токеном
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        with caplog.at_level("WARNING", logger="apps.users.auth"):
            response = self.client.post(
                "/api/v1/auth/logout/",
                data={"refresh": "invalid-token"},
                format="json",
                REMOTE_ADDR="192.168.1.200",
            )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Проверка WARNING log записи
        log_record = next(
            (r for r in caplog.records if "[AUDIT]" in r.message and "failed" in r.message),
            None,
        )
        assert log_record is not None, "WARNING audit log не найден"
        assert log_record.levelname == "WARNING"

        # Проверка содержания
        log_message = log_record.message
        assert "[AUDIT]" in log_message
        assert "User logout failed" in log_message
        assert f"user_id={self.test_user.id}" in log_message
        assert "error=" in log_message
        assert "ip=192.168.1.200" in log_message

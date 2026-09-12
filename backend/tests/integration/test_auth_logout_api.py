"""
Integration тесты для Logout API endpoint

Story 30.4: Тесты для Logout функциональности
AC: 2, 3, 5, 6 - Integration-тесты покрывают все сценарии, изолированы,
                проходят в Docker Compose, следуют pytest conventions

Testing Framework: pytest 7.4.3 + pytest-django 4.7.0
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from tests.conftest import get_unique_suffix

User = get_user_model()

pytestmark = pytest.mark.django_db


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def logout_api_client():
    """API клиент для тестов logout."""
    return APIClient()


@pytest.fixture
def create_test_user():
    """Фабрика для создания пользователей с уникальными данными.

    Returns:
        Callable: Функция для создания пользователя с переданными параметрами
    """

    def _create_user(**kwargs):
        email = kwargs.get("email", f"user_{get_unique_suffix()}@freesport.test")
        password = kwargs.get("password", "TestPassword123!")

        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=kwargs.get("first_name", "Test"),
            last_name=kwargs.get("last_name", "User"),
            role=kwargs.get("role", "retail"),
            is_active=kwargs.get("is_active", True),
            verification_status=kwargs.get("verification_status", "verified"),
        )
        return user

    return _create_user


@pytest.fixture
def authenticated_user_with_tokens(create_test_user):
    """Создает пользователя и возвращает токены.

    Returns:
        dict: Словарь с user, access token, refresh token и refresh объектом
    """
    user = create_test_user()
    refresh = RefreshToken.for_user(user)

    return {
        "user": user,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "refresh_obj": refresh,
    }


@pytest.fixture
def get_logout_url():
    """Возвращает URL для logout endpoint."""
    return reverse("users:logout")


@pytest.fixture
def get_refresh_url():
    """Возвращает URL для token refresh endpoint."""
    return reverse("users:token_refresh")


# =============================================================================
# Tests: Successful Logout (AC: 2)
# =============================================================================


@pytest.mark.integration
class TestLogoutAPISuccess:
    """Тесты успешного logout.

    Проверяют корректную работу logout endpoint при валидных данных.
    """

    def test_successful_logout_returns_204(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Успешный logout возвращает 204 No Content.

        Проверяет, что при валидном access токене в заголовке и
        валидном refresh токене в body возвращается статус 204.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert response.content == b""

    def test_token_added_to_blacklist(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Токен добавляется в blacklist после logout.

        Проверяет, что после успешного logout refresh токен
        записывается в таблицу BlacklistedToken.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        jti = tokens["refresh_obj"]["jti"]

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Проверяем blacklist
        outstanding = OutstandingToken.objects.get(jti=jti)
        assert BlacklistedToken.objects.filter(token=outstanding).exists()

    def test_blacklisted_token_cannot_refresh(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
        get_refresh_url,
    ):
        """Blacklisted токен не может получить новый access токен.

        Проверяет, что после logout refresh токен больше не может
        использоваться для получения нового access токена.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - Logout
        logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Act - Попытка refresh
        logout_api_client.credentials()  # Убираем auth для refresh endpoint
        response = logout_api_client.post(
            get_refresh_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_fresh_token(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Logout работает со свежесозданным токеном.

        Проверяет, что logout можно выполнить сразу после создания токенов.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - logout сразу после создания токенов
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT


# =============================================================================
# Tests: Authentication Errors (AC: 2)
# =============================================================================


@pytest.mark.integration
class TestLogoutAPIAuthenticationErrors:
    """Тесты ошибок аутентификации.

    Проверяют корректную обработку запросов без валидной аутентификации.
    """

    def test_logout_without_auth_returns_401(
        self,
        logout_api_client,
        get_logout_url,
    ):
        """Logout без аутентификации возвращает 401.

        Проверяет, что запрос без заголовка Authorization отклоняется.
        """
        # Arrange - клиент без аутентификации

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": "some-token"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "detail" in response.json()

    def test_logout_with_invalid_bearer_token(
        self,
        logout_api_client,
        get_logout_url,
    ):
        """Logout с невалидным Bearer токеном возвращает 401.

        Проверяет, что невалидный JWT в заголовке отклоняется.
        """
        # Arrange
        logout_api_client.credentials(HTTP_AUTHORIZATION="Bearer invalid-token")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": "some-token"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_malformed_auth_header(
        self,
        logout_api_client,
        get_logout_url,
    ):
        """Logout с некорректным заголовком возвращает 401.

        Проверяет, что заголовок без "Bearer " prefix отклоняется.
        """
        # Arrange
        logout_api_client.credentials(HTTP_AUTHORIZATION="InvalidFormat token")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": "some-token"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Tests: Token Validation Errors (AC: 2)
# =============================================================================


@pytest.mark.integration
class TestLogoutAPITokenValidationErrors:
    """Тесты ошибок валидации токенов.

    Проверяют корректную обработку невалидных refresh токенов.
    """

    def test_logout_with_invalid_refresh_token(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Невалидный refresh токен возвращает 400.

        Проверяет, что некорректный JWT в теле запроса вызывает ошибку.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": "invalid-jwt-token"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()

    def test_logout_with_already_blacklisted_token(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Уже blacklisted токен возвращает 400.

        Проверяет, что повторный logout с тем же токеном вызывает ошибку.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Blacklist токена
        logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Act - повторный logout (с новым access токеном)
        new_access = str(RefreshToken.for_user(tokens["user"]).access_token)
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")

        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()

    def test_logout_with_malformed_jwt(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Некорректный JWT формат возвращает 400.

        Проверяет обработку строки, не соответствующей формату JWT.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": "not.a.jwt"},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_without_refresh_field(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Отсутствие поля refresh возвращает 400.

        Проверяет, что пустой body вызывает ошибку валидации сериализатора.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "refresh" in response.json()

    def test_logout_with_access_token_instead_refresh(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Использование access token вместо refresh вызывает ошибку.

        Проверяет, что access токен отклоняется при попытке blacklist.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - передаем access token вместо refresh
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["access"]},  # access вместо refresh!
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# Tests: Edge Cases and Security (AC: 2)
# =============================================================================


@pytest.mark.integration
class TestLogoutAPIEdgeCases:
    """Тесты edge cases и security.

    Проверяют граничные случаи и безопасность logout endpoint.
    """

    def test_logout_own_token(
        self,
        logout_api_client,
        create_test_user,
        get_logout_url,
    ):
        """Пользователь может сделать logout своего токена.

        Проверяет базовый сценарий logout с собственным токеном.
        """
        # Arrange
        user = create_test_user()
        refresh = RefreshToken.for_user(user)

        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {str(refresh.access_token)}")

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": str(refresh)},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_multiple_logouts_same_token(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Повторный logout того же токена возвращает ошибку.

        Проверяет, что нельзя дважды занести токен в blacklist.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # First logout
        first_response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )
        assert first_response.status_code == status.HTTP_204_NO_CONTENT

        # Act - второй logout (с новым access токеном)
        new_access = str(RefreshToken.for_user(tokens["user"]).access_token)
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")

        second_response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert second_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_logout_method_not_allowed_get(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """GET запрос возвращает 405 Method Not Allowed."""
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.get(get_logout_url)

        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_logout_method_not_allowed_put(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """PUT запрос возвращает 405 Method Not Allowed."""
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.put(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
        )

        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_logout_method_not_allowed_delete(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """DELETE запрос возвращает 405 Method Not Allowed."""
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act
        response = logout_api_client.delete(get_logout_url)

        # Assert
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED

    def test_logout_with_very_long_token(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Токен с чрезмерной длиной обрабатывается корректно.

        Проверяет, что очень длинный токен не вызывает server error.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        long_token = "a" * 10000  # Очень длинный токен

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": long_token},
            format="json",
        )

        # Assert - должен вернуть 400, а не 500
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_access_token_rejected_after_logout(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Access токен отклоняется после logout.

        Story JWT-Blacklist: После logout access токен добавляется
        в Redis blacklist и не может использоваться для авторизации.

        Это изменение поведения по сравнению со стандартным JWT,
        где access токен остаётся валидным до истечения TTL.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - logout
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT

        # Assert - access токен больше не работает (Redis blacklist)
        profile_response = logout_api_client.get(reverse("users:profile"))
        assert profile_response.status_code == status.HTTP_401_UNAUTHORIZED


# =============================================================================
# Tests: Redis Access Token Blacklist (Story JWT-Blacklist)
# =============================================================================


@pytest.mark.integration
class TestAccessTokenBlacklist:
    """Тесты Redis blacklist для access-токенов.

    Story JWT-Blacklist: Проверяют функциональность немедленной
    инвалидации access-токенов через Redis.
    """

    def test_access_token_blacklist_stored_in_redis(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Access token JTI записывается в Redis при logout.

        Проверяет, что после logout access token JTI присутствует
        в Redis с правильным префиксом.
        """
        from django.core.cache import cache

        from apps.users.authentication import ACCESS_BLACKLIST_PREFIX

        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Получаем JTI из access token (декодируем строку, чтобы получить верный JTI)
        access_token_obj = AccessToken(tokens["access"])
        access_jti = access_token_obj["jti"]

        # Act
        response = logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        assert response.status_code == status.HTTP_204_NO_CONTENT
        # Проверяем что JTI в Redis
        assert cache.get(f"{ACCESS_BLACKLIST_PREFIX}{access_jti}") is not None

    def test_access_token_blacklist_contains_metadata(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Redis blacklist содержит metadata для forensics.

        Проверяет, что сохранённые данные содержат user_id, ip, timestamp.
        """
        import json

        from django.core.cache import cache

        from apps.users.authentication import ACCESS_BLACKLIST_PREFIX

        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        access_token_obj = AccessToken(tokens["access"])
        access_jti = access_token_obj["jti"]

        # Act
        logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert
        blacklist_data = json.loads(cache.get(f"{ACCESS_BLACKLIST_PREFIX}{access_jti}"))
        assert blacklist_data["blacklisted"] is True
        assert blacklist_data["user_id"] == tokens["user"].id
        assert "timestamp" in blacklist_data
        assert "ip" in blacklist_data

    def test_multiple_access_tokens_can_be_blacklisted(
        self,
        logout_api_client,
        create_test_user,
        get_logout_url,
    ):
        """Несколько access токенов могут быть в blacklist одновременно.

        Проверяет, что при logout разных пользователей все токены
        добавляются в blacklist независимо.
        """
        from django.core.cache import cache

        from apps.users.authentication import ACCESS_BLACKLIST_PREFIX

        # Arrange - создаём двух пользователей с токенами
        user1 = create_test_user(email="user1@test.com")
        user2 = create_test_user(email="user2@test.com")

        refresh1 = RefreshToken.for_user(user1)
        refresh2 = RefreshToken.for_user(user2)

        # Сохраняем access токены чтобы JTI совпадали
        access1 = str(refresh1.access_token)
        access2 = str(refresh2.access_token)

        jti1 = AccessToken(access1)["jti"]
        jti2 = AccessToken(access2)["jti"]

        # Act - logout обоих пользователей
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access1}")
        logout_api_client.post(get_logout_url, data={"refresh": str(refresh1)}, format="json")

        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access2}")
        logout_api_client.post(get_logout_url, data={"refresh": str(refresh2)}, format="json")

        # Assert - оба токена в blacklist
        assert cache.get(f"{ACCESS_BLACKLIST_PREFIX}{jti1}") is not None
        assert cache.get(f"{ACCESS_BLACKLIST_PREFIX}{jti2}") is not None

    def test_blacklisted_access_token_returns_generic_error(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Blacklisted токен возвращает generic error (security).

        Проверяет, что сообщение об ошибке не раскрывает причину отказа
        (blacklisted vs expired vs invalid) для предотвращения утечки информации.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - logout
        logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Assert - generic error message
        profile_response = logout_api_client.get(reverse("users:profile"))
        assert profile_response.status_code == status.HTTP_401_UNAUTHORIZED
        # Проверяем что сообщение generic (не раскрывает "blacklisted")
        response_data = profile_response.json()
        assert "detail" in response_data
        # Сообщение не должно содержать слово "blacklist"
        assert "blacklist" not in response_data["detail"].lower()

    def test_new_token_after_logout_works(
        self,
        logout_api_client,
        authenticated_user_with_tokens,
        get_logout_url,
    ):
        """Новый токен после logout работает нормально.

        Проверяет, что блокируется только конкретный токен,
        а не все токены пользователя.
        """
        # Arrange
        tokens = authenticated_user_with_tokens
        user = tokens["user"]
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")

        # Act - logout
        logout_api_client.post(
            get_logout_url,
            data={"refresh": tokens["refresh"]},
            format="json",
        )

        # Создаём новый токен (как при повторном логине)
        new_refresh = RefreshToken.for_user(user)
        new_access = str(new_refresh.access_token)

        # Assert - новый токен работает
        logout_api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {new_access}")
        profile_response = logout_api_client.get(reverse("users:profile"))
        assert profile_response.status_code == status.HTTP_200_OK

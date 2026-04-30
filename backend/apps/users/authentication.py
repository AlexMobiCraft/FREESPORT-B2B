"""
Кастомная JWT Authentication с проверкой Redis blacklist для access-токенов.

Эта имплементация решает проблему: при logout access-токен остаётся
валидным до истечения TTL (60 минут). С Redis blacklist токен
инвалидируется немедленно.

Tech-Spec: jwt-access-token-blacklist
"""

import json
import logging
from typing import TYPE_CHECKING, Any, cast

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.request import Request
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

logger = logging.getLogger("apps.users.auth")

# Константа для префикса ключей в Redis
ACCESS_BLACKLIST_PREFIX = "access_blacklist:"


class BlacklistCheckJWTAuthentication(JWTAuthentication):
    """
    JWTAuthentication с проверкой Redis blacklist для access-токенов.

    При каждой аутентификации проверяет, находится ли JTI токена
    в Redis blacklist. Если токен заблокирован — возвращает 401.

    Graceful degradation: при недоступности Redis авторизация
    продолжает работать по стандартной JWT логике (с логированием warning).
    """

    def get_validated_token(self, raw_token):
        """
        Валидация токена с дополнительной проверкой Redis blacklist.

        Args:
            raw_token: Сырой JWT токен из заголовка Authorization

        Returns:
            validated_token: Валидированный токен

        Raises:
            InvalidToken: Если токен невалиден или находится в blacklist
        """
        validated_token = super().get_validated_token(raw_token)

        jti = validated_token.get("jti")
        if jti and self._is_token_blacklisted(jti):
            # Security: Generic message to prevent information leakage
            # Не раскрываем причину отказа (blacklisted vs expired vs invalid)
            raise InvalidToken("Token is invalid")

        return validated_token

    def _is_token_blacklisted(self, jti: str) -> bool:
        """
        Проверить, находится ли токен в blacklist.

        Note: We store JSON metadata in Redis for forensics,
        but only check existence here (not parsing JSON).
        This keeps the hot path simple and fast.

        Args:
            jti: JWT ID (уникальный идентификатор токена)

        Returns:
            bool: True если токен в blacklist, False иначе
        """
        try:
            # Existence check only - JSON metadata is for forensics, not validation
            return cache.get(f"{ACCESS_BLACKLIST_PREFIX}{jti}") is not None
        except Exception as e:
            # Redis недоступен — graceful degradation
            # Risk R1: пропускаем проверку, логируем warning
            # TODO: Implement circuit breaker (max 2 min fallback) per tech-spec
            logger.warning(
                f"[SECURITY] Redis blacklist check failed | "
                f"jti={jti[:8]}... | "
                f"error={str(e)} | "
                f"timestamp={timezone.now().isoformat()}"
            )
            return False


def blacklist_access_token(request: Request, user_id: int) -> bool:
    """
    Добавить access token в Redis blacklist.

    Используется в LogoutView для немедленной инвалидации access-токена.
    Сохраняет metadata для forensics (IP, timestamp, user_id).

    Args:
        request: DRF request object с access token в request.auth
        user_id: ID пользователя для логирования

    Returns:
        bool: True если токен успешно добавлен в blacklist, False при ошибке
    """
    access_token = getattr(request, "auth", None)
    if not access_token:
        # Edge case: session auth instead of JWT (FMA F1.3)
        logger.warning(
            f"[AUDIT] Logout without access token | "
            f"user_id={user_id} | "
            f"auth_type=session | "
            f"ip={_get_client_ip(request)}"
        )
        return False

    jti = access_token.get("jti")
    if not jti:
        logger.warning(f"[AUDIT] Access token without JTI | " f"user_id={user_id} | " f"ip={_get_client_ip(request)}")
        return False

    # TTL = ACCESS_TOKEN_LIFETIME (auto-cleanup)
    jwt_settings = settings.SIMPLE_JWT
    access_lifetime = jwt_settings.get("ACCESS_TOKEN_LIFETIME")
    if access_lifetime:
        ttl = access_lifetime.total_seconds()
    else:
        # Default fallback
        ttl = 3600.0

    # Security Audit: Store metadata for forensics
    blacklist_data = {
        "blacklisted": True,
        "ip": _get_client_ip(request),
        "timestamp": timezone.now().isoformat(),
        "user_id": user_id,
    }

    try:
        cache.set(
            f"{ACCESS_BLACKLIST_PREFIX}{jti}",
            json.dumps(blacklist_data),
            timeout=int(ttl),
        )
        logger.info(
            f"[AUDIT] Access token blacklisted | "
            f"user_id={user_id} | "
            f"jti={jti[:8]}... | "
            f"ttl={int(ttl)}s | "
            f"ip={_get_client_ip(request)}"
        )
        return True
    except Exception as e:
        # Redis failure — log but don't block logout
        logger.warning(
            f"[SECURITY] Failed to blacklist access token | "
            f"user_id={user_id} | "
            f"jti={jti[:8]}... | "
            f"error={str(e)}"
        )
        return False


def _get_client_ip(request: Request) -> str:
    """
    Получить IP адрес клиента с учетом proxy серверов.

    Args:
        request: Django/DRF request object

    Returns:
        str: IP адрес клиента
    """
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
    else:
        ip = request.META.get("REMOTE_ADDR", "unknown")
    return cast(str, ip)

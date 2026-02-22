"""
Настройки Django для продакшена FREESPORT
"""

from .base import *

# БЕЗОПАСНОСТЬ: Debug должен быть False в продакшене!
DEBUG = False

# Хосты, которым разрешен доступ к приложению
# Настраивается через переменные окружения
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="").split(",")

# Настройки базы данных для продакшена (PostgreSQL)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME"),
        "USER": config("DB_USER"),
        "PASSWORD": config("DB_PASSWORD"),
        "HOST": config("DB_HOST"),
        "PORT": config("DB_PORT", default="5432", cast=int),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "sslmode": config("DB_SSLMODE", default="prefer"),
        },
    }
}

# Настройки безопасности для продакшена
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000  # 1 год
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = config("SECURE_SSL_REDIRECT", default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = "DENY"

# Настройки обратного прокси для корректного определения HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = True

# Настройки CORS для продакшена
# Домены фронтенда настраиваются через переменные окружения
CORS_ALLOWED_ORIGINS = config("CORS_ALLOWED_ORIGINS", default="").split(",")

# Настройки статических файлов для продакшена
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Настройки кеша для продакшена
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "CONNECTION_POOL_KWARGS": {
                "max_connections": 100,
                "retry_on_timeout": True,
            },
        },
    }
}

# Логирование для продакшена (только console для Docker)
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "freesport": {
            "handlers": ["console"],
            "level": "WARNING",
        },
    },
}

# Настройки email для продакшена
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)

# Домен для email будет настраиваться через переменные
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@freesport.ru")
SERVER_EMAIL = config("SERVER_EMAIL", default="admin@freesport.ru")

# Rate limiting для защиты от SPAM (Story 11.3 - SEC-001)
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # Наследуем настройки из base.py
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.common.throttling.ProxyAwareAnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "6000/min",  # Increased to fix SSR 429 errors
        "user": "10000/day",  # Для авторизованных пользователей
    },
}

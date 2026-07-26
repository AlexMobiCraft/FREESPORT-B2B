import os
import tempfile
from datetime import timedelta
from pathlib import Path
from typing import List

from .base import DATABASES, SECRET_KEY

# Отключаем DEBUG для тестов
DEBUG = False

# Тестовая база данных - ТОЛЬКО PostgreSQL через Docker
# ВАЖНО: Тестирование выполняется ТОЛЬКО с PostgreSQL через Docker Compose
# SQLite больше не поддерживается для тестов из-за ограничений JSON операторов
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "freesport_test"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "password123"),
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "TEST": {
            "NAME": "test_" + os.environ.get("DB_NAME", "freesport_test"),
        },
    }
}


# Отключаем миграции для быстрых тестов
class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

# Простой хешер паролей для скорости
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Настройки кеширования для тестов - ТОЛЬКО Redis через Docker
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.environ.get("REDIS_URL", "redis://localhost:6379/1"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
        "KEY_PREFIX": "freesport_test",
    }
}

# Отключаем логирование для тестов
LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
    "handlers": {
        "null": {
            "class": "logging.NullHandler",
        },
    },
    "root": {
        "handlers": ["null"],
        "level": "CRITICAL",
    },
    "loggers": {
        "django": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "freesport": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["null"],
            "level": "CRITICAL",
            "propagate": False,
        },
    },
}

# Медиа файлы во временной директории
MEDIA_ROOT = Path(tempfile.mkdtemp())

# Статические файлы во временной директории
STATIC_ROOT = Path(tempfile.mkdtemp())

# Отключаем email отправку
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Тестовый SECRET_KEY
SECRET_KEY = "test-secret-key-for-testing-only-do-not-use-in-production"

# Упрощенная настройка middleware для тестов
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# Настройки для тестирования JWT
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=5),
    "REFRESH_TOKEN_LIFETIME": timedelta(minutes=10),
    "SIGNING_KEY": SECRET_KEY,
    "ALGORITHM": "HS256",
    "VERIFYING_KEY": None,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "TOKEN_OBTAIN_SERIALIZER": ("rest_framework_simplejwt.serializers.TokenObtainPairSerializer"),
}

# Разрешаем все домены для тестов
ALLOWED_HOSTS = ["*"]

# Отключаем CORS проверки
CORS_ALLOW_ALL_ORIGINS = True

# Настройки для factory_boy
FACTORY_FOR_DJANGO_FILE_FIELD = True

# Настройки для pytest-django
USE_TZ = True

# Отключаем django-ratelimit для тестов
RATELIMIT_ENABLE = False

# Дополнительные настройки PostgreSQL для стабильных тестов
DATABASES["default"].update(
    {
        "CONN_MAX_AGE": 0,
        "CONN_HEALTH_CHECKS": False,
        "AUTOCOMMIT": True,
        "OPTIONS": {
            "connect_timeout": 30,
            "server_side_binding": False,
            "application_name": "freesport_test",
        },
        "TEST": {
            "NAME": "test_" + os.environ.get("DB_NAME", "freesport_test"),
            "SERIALIZE": False,
            "CREATE_DB": True,
            "DEPENDENCIES": [],
        },
    }
)

# Настройки для предотвращения connection already closed
DATABASE_ROUTERS: List[str] = []

# Дополнительные настройки для изоляции тестов
DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

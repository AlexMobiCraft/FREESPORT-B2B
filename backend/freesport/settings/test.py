"""Настройки окружения для тестов FREESPORT."""

# pylint: disable=wildcard-import, unused-wildcard-import
import os
from typing import Any  # pylint: disable=unused-import

from .base import *  # noqa: F403, F401, F405

# ==============================================================================
# НАСТРОЙКИ ДЛЯ ТЕСТИРОВАНИЯ (TESTING SETTINGS)
# ==============================================================================

# Отключаем отладку в тестах для производительности и безопасности
DEBUG = False

# Используем временный ключ, чтобы не раскрывать продакшен-ключ
SECRET_KEY = os.environ.get("SECRET_KEY", "django-insecure-test-key-for-ci")


# ==============================================================================
# БАЗА ДАННЫХ (DATABASE)
# ==============================================================================
#
# Максимально простая конфигурация БД, совместимая с pytest-django.
# Все значения берутся напрямую из переменных окружения, которые
# мы устанавливаем в .github/workflows/main.yml.


def _get_env_value(primary_key: str, fallback_keys: tuple[str, ...], default: str) -> str:
    """Возвращает значение переменной окружения с поддержкой fallback."""

    for key in (primary_key, *fallback_keys):
        value = os.environ.get(key)
        if value:
            return value
    return default


DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": _get_env_value("DB_NAME", ("POSTGRES_DB", "PGDATABASE"), "freesport_test"),
        "USER": _get_env_value("DB_USER", ("POSTGRES_USER", "PGUSER"), "postgres"),
        "PASSWORD": _get_env_value(
            "DB_PASSWORD",
            ("POSTGRES_PASSWORD", "PGPASSWORD"),
            "postgres",
        ),
        "HOST": _get_env_value("DB_HOST", ("POSTGRES_HOST", "PGHOST"), "127.0.0.1"),
        "PORT": int(_get_env_value("DB_PORT", ("POSTGRES_PORT", "PGPORT"), "5432")),
        "ATOMIC_REQUESTS": True,  # Оборачиваем каждый запрос в транзакцию
        "CONN_MAX_AGE": 0,  # Закрываем соединения после каждого запроса в тестах
        "OPTIONS": {
            "client_encoding": "UTF8",
            "connect_timeout": 10,
        },
        "TEST": {
            "NAME": _get_env_value(
                "TEST_DB_NAME",
                ("TEST_POSTGRES_DB", "DJANGO_TEST_DATABASE_NAME"),
                "pytest_freesport",
            )
        },
    }
}


# ==============================================================================
# УСКОРЕНИЕ ТЕСТОВ (TESTING SPEEDUPS)
# ==============================================================================

# Используем быстрый (небезопасный) хешер паролей для ускорения
# создания пользователей в тестах.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# Отключаем email-отправку, заменяя её на "заглушку",
# которая хранит письма в памяти.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# Значения по умолчанию для email уведомлений в тестовой среде
CONFLICT_NOTIFICATION_EMAIL = os.environ.get(
    "CONFLICT_NOTIFICATION_EMAIL",
    "alex.mobicraft@gmail.com",
)
DEFAULT_FROM_EMAIL = os.environ.get(
    "DEFAULT_FROM_EMAIL",
    "admin@freesport.ru",
)

# Отключаем логирование в консоль, чтобы вывод тестов был чистым.
LOGGING: dict[str, Any] = {}  # type: ignore[no-redef]  # type: ignore[no-redef]

# Гарантированно отключаем Django Debug Toolbar в тестах,
# даже если он был добавлен в другом файле настроек.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]
if "apps.integrations" not in INSTALLED_APPS and "apps.integrations.apps.IntegrationsConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("apps.integrations")
if "apps.integrations" not in INSTALLED_APPS and "apps.integrations.apps.IntegrationsConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("apps.integrations")

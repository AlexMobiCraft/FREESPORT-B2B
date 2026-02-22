"""
Настройки Django для локальной разработки FREESPORT
"""

import os

from .base import *

# ВНИМАНИЕ: не используйте debug=True в продакшене!
DEBUG = True

ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1,backend").split(",")

# Дополнительные приложения для разработки
INSTALLED_APPS += [
    "debug_toolbar",
    "django_extensions",
]

# Middleware для отладки
MIDDLEWARE += [
    "debug_toolbar.middleware.DebugToolbarMiddleware",
]

# Настройки базы данных для разработки (используем PostgreSQL через Docker)
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("DB_NAME", "freesport"),
        "USER": os.environ.get("DB_USER", "postgres"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "password123"),
        "HOST": os.environ.get("DB_HOST", "db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 10,
            # Исправление для UnicodeDecodeError в Windows
            "client_encoding": "UTF8",
        },
    }
}

# Настройки CORS для фронтенда
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://5.35.124.149",
]

CORS_ALLOW_CREDENTIALS = True

# Story 12.1: Allow CSRF for Session Auth from frontend
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

# Настройки Debug Toolbar
INTERNAL_IPS = [
    "127.0.0.1",
]

# Упрощенные настройки безопасности для разработки
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False

# ============================================================================
# Email Configuration для разработки (Story 29.3)
# ============================================================================
# В development используем console backend для отображения писем в консоли
# Для тестирования с Mailhog, установите через .env:
# EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
# EMAIL_HOST=mailhog (или localhost)
# EMAIL_PORT=1025
EMAIL_BACKEND = os.environ.get("EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend")

# Логирование для разработки
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },
        "freesport": {
            "handlers": ["console"],
            "level": "DEBUG",
        },
    },
}

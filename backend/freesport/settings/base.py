"""
Базовые настройки Django для платформы FREESPORT
Общая конфигурация для всех окружений
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# Временно отключаем патч для исправления проблем с кодировкой psycopg2 на Windows
# try:
#     import monkey_patch_psycopg2
#     monkey_patch_psycopg2.apply_monkey_patch()
# except ImportError:
#     pass  # Патч не применен, но продолжаем работу


# Настройка кодировки для Windows консоли
if sys.platform == "win32":
    import locale

    # Попытка установить UTF-8 кодировку
    try:
        locale.setlocale(locale.LC_ALL, "ru_RU.UTF-8")
    except locale.Error:
        try:
            locale.setlocale(locale.LC_ALL, "Russian_Russia.1251")
        except locale.Error:
            pass

# Корневая директория проекта
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ВНИМАНИЕ: секретный ключ должен быть изменен в продакшене!
SECRET_KEY = config("SECRET_KEY", default="django-insecure-development-key-change-in-production")

# Основные Django приложения
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

# Сторонние приложения
THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",  # Story 30.1: JWT Token Blacklist
    "corsheaders",
    "django_redis",
    "drf_spectacular",
    "django_ratelimit",
    "django_filters",
]

# Локальные приложения FREESPORT
LOCAL_APPS = [
    "apps.users",
    "apps.products",
    "apps.orders",
    "apps.cart",
    "apps.pages",
    "apps.common",
    "apps.integrations.apps.IntegrationsConfig",
    "apps.delivery",
    "apps.banners",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# Middleware в порядке выполнения
MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_ratelimit.middleware.RatelimitMiddleware",
]

ROOT_URLCONF = "freesport.urls"

# Конфигурация шаблонов
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "freesport.wsgi.application"

# Конфигурация базы данных PostgreSQL
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="freesport"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="password123"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432", cast=int),
        "OPTIONS": {
            "connect_timeout": 10,
            "client_encoding": "UTF8",
        },
    }
}

# Кастомная модель пользователя
AUTH_USER_MODEL = "users.User"

# Валидаторы паролей
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": ("django.contrib.auth.password_validation.UserAttributeSimilarityValidator"),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# Конфигурация Django REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        # Story JWT-Blacklist: Кастомный auth с проверкой Redis blacklist
        "apps.users.authentication.BlacklistCheckJWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        # Changed from IsAuthenticated to AllowAny (fix: 401 on public endpoints)
        # Protected views must explicitly set permission_classes = [IsAuthenticated]
        "rest_framework.permissions.AllowAny",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
        "rest_framework.filters.SearchFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "PAGE_SIZE_QUERY_PARAM": "page_size",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# ============================================================================
# JWT Authentication Configuration (Story 1.3, Story 30.1)
# ============================================================================
# Story 30.1: JWT Token Blacklist Setup
# - ROTATE_REFRESH_TOKENS: создаёт новый refresh токен при каждом обновлении
# - BLACKLIST_AFTER_ROTATION: автоматически добавляет старый токен в blacklist
# - Требует приложение 'rest_framework_simplejwt.token_blacklist' в INSTALLED_APPS
# - Таблицы: token_blacklist_outstandingtoken, token_blacklist_blacklistedtoken
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,  # Story 30.1: Ротация refresh токенов
    "BLACKLIST_AFTER_ROTATION": True,  # Story 30.1: Автоматический blacklist
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "VERIFYING_KEY": None,
    "AUDIENCE": None,
    "ISSUER": None,
    "JWK_URL": None,
    "LEEWAY": 60,  # Fix 401: Allow 60s clock skew
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "USER_AUTHENTICATION_RULE": ("rest_framework_simplejwt.authentication.default_user_authentication_rule"),
    "AUTH_TOKEN_CLASSES": ("rest_framework_simplejwt.tokens.AccessToken",),
    "TOKEN_TYPE_CLAIM": "token_type",
    "TOKEN_USER_CLASS": "rest_framework_simplejwt.models.TokenUser",
    "JTI_CLAIM": "jti",
}

# Конфигурация Redis кеша
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": config("REDIS_URL", default="redis://:redis123@redis:6379/0"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

CELERY_BROKER_URL = config(
    "CELERY_BROKER_URL",
    default=config("REDIS_URL", default="redis://:redis123@redis:6379/0"),
)
CELERY_RESULT_BACKEND = config(
    "CELERY_RESULT_BACKEND",
    default=CELERY_BROKER_URL,
)

# Celery Beat Schedule (Story 29.4 - мониторинг pending верификаций)
CELERY_BEAT_SCHEDULE = {
    "monitor-pending-verification-queue": {
        "task": "apps.users.tasks.monitor_pending_verification_queue",
        "schedule": 60 * 60 * 8,  # Каждые 8 часов (9:00, 17:00 при запуске в 9:00)
    },
    "cleanup-stale-import-sessions": {
        "task": "apps.products.tasks.cleanup_stale_import_sessions",
        "schedule": 60 * 60,  # Раз в час (Story 3.1 AC6)
    },
}

# Баннеры
MARKETING_BANNER_LIMIT = 5  # FR12: Максимальное количество маркетинговых баннеров

# Интернационализация
LANGUAGE_CODE = "ru-ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

# Статические файлы
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Медиа файлы
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Права доступа для загружаемых файлов
# Необходимо для корректного чтения файлов Nginx'ом, когда бэкенд и
# веб-сервер работают от разных пользователей
FILE_UPLOAD_PERMISSIONS = 0o644
FILE_UPLOAD_DIRECTORY_PERMISSIONS = 0o755

# Лимит POST/GET параметров для Django Admin с большими inline формами
# Увеличен для поддержки атрибутов с большим количеством значений
# (напр. "Размер" с 466+ значениями)
DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# Интеграция с 1С
# Путь к директории с данными импорта из 1С
# Поддерживает переменную окружения ONEC_DATA_DIR
ONEC_DATA_DIR = os.environ.get("ONEC_DATA_DIR", str(BASE_DIR / "data" / "import_1c"))

if sys.version_info >= (3, 8):
    from typing import TypedDict

    class OneCExchangeConfig(TypedDict):
        SESSION_COOKIE_NAME: str
        SESSION_LIFETIME_SECONDS: int
        FILE_LIMIT_BYTES: int
        ZIP_SUPPORT: bool
        COMMERCEML_VERSION: str


ONEC_EXCHANGE = {
    "SESSION_COOKIE_NAME": "FREESPORT_1C_SESSION",
    "SESSION_LIFETIME_SECONDS": 3600,  # 1 hour
    "FILE_LIMIT_BYTES": 100 * 1024 * 1024,  # 100MB per chunk
    "ZIP_SUPPORT": True,
    "COMMERCEML_VERSION": "3.1",  # CommerceML protocol version
    "TEMP_DIR": MEDIA_ROOT / "1c_temp",  # Temporary directory for chunked uploads
    "IMPORT_DIR": MEDIA_ROOT / "1c_import",  # Story 2.2: Directory for routed import files
}

# Тип первичного ключа по умолчанию
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Настройки документации API с drf-spectacular
SPECTACULAR_SETTINGS = {
    "TITLE": "FREESPORT API",
    "DESCRIPTION": "RESTful API для B2B/B2C платформы спортивных товаров FREESPORT",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/v1",
    "SCHEMA_PATH_PREFIX_TRIM": True,
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    "ENABLE_DJANGO_DEPLOY_CHECK": False,
    "DISABLE_ERRORS_AND_WARNINGS": True,
    # OpenAPI 3.1 настройки согласно architecture.md
    "OAS_VERSION": "3.1.0",
    "SCHEMA_COERCE_METHOD_NAMES": {
        "retrieve": "get",
        "list": "list",
        "create": "create",
        "update": "update",
        "partial_update": "partial_update",
        "destroy": "delete",
    },
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayOperationId": True,
        "docExpansion": "list",
        "filter": True,
        "showExtensions": True,
        "showCommonExtensions": True,
    },
    "REDOC_UI_SETTINGS": {
        "nativeScrollbars": True,
        "theme": {"colors": {"primary": {"main": "#1976d2"}}},
        "expandResponses": "200,201",
        "jsonSampleExpandLevel": 2,
    },
    "AUTHENTICATION_WHITELIST": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "SERVE_AUTHENTICATION": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "POSTPROCESSING_HOOKS": ["drf_spectacular.hooks.postprocess_schema_enums"],
    "ENUM_NAME_OVERRIDES": {
        "ValidationErrorEnum": "drf_spectacular.utils.validation_error_enum_class",
    },
    "TAGS": [
        {"name": "Authentication", "description": "Аутентификация и JWT токены"},
        {"name": "Users", "description": "Управление пользователями и профилями"},
        {
            "name": "Products",
            "description": "Каталог товаров и управление ассортиментом",
        },
        {"name": "Cart", "description": "Корзина покупок"},
        {"name": "Orders", "description": "Управление заказами и их статусами"},
        {"name": "Search", "description": "Поиск и фильтрация товаров"},
        {"name": "System", "description": "Системные эндпоинты для мониторинга"},
        {"name": "Webhooks", "description": "Уведомления от внешних сервисов"},
    ],
    "SERVERS": [
        {"url": "http://127.0.0.1:8001", "description": "Development server"},
        {"url": "https://api.freesport.ru", "description": "Production server"},
    ],
    # OpenAPI 3.1 Extensions для будущих webhooks (ЮКасса)
    "EXTENSIONS_INFO": {
        "x-logo": {
            "url": "https://api.freesport.ru/static/logo.png",
            "altText": "FREESPORT API",
        }
    },
}

# Настройки для разрешения конфликтов синхронизации (Story 3.2.2)
CONFLICT_NOTIFICATION_EMAIL = config("CONFLICT_NOTIFICATION_EMAIL", default="admin@freesport.ru")

# ============================================================================
# Email Configuration (Story 29.3)
# ============================================================================

# Email backend: console для development, smtp для production
# В development это переопределяется в development.py на console backend
EMAIL_BACKEND = config("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")

# SMTP сервер настройки
EMAIL_HOST = config("EMAIL_HOST", default="smtp.yandex.ru")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
EMAIL_USE_SSL = config("EMAIL_USE_SSL", default=False, cast=bool)

# Credentials для SMTP (из .env файла)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")

# Адрес отправителя по умолчанию
DEFAULT_FROM_EMAIL = config("DEFAULT_FROM_EMAIL", default="noreply@freesport.ru")
SERVER_EMAIL = config("SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)

# Парсинг списка администраторов из ADMIN_EMAILS
# Формат: "Admin Name <admin@example.com>,Another Admin <admin2@example.com>"
# или просто: "admin@example.com,admin2@example.com"
_admin_emails_raw = config("ADMIN_EMAILS", default="", cast=Csv())
ADMINS = [("Admin", email.strip()) for email in _admin_emails_raw if email.strip()]

# Менеджеры получают уведомления о битых ссылках (404)
MANAGERS = ADMINS

# ============================================================================
# Logging Configuration (Story 13.2 - NFR8)
# ============================================================================

LOGS_DIR = BASE_DIR / "logs"

# Создаём директорию логов безопасно
try:
    LOGS_DIR.mkdir(exist_ok=True)
    _base_file_logging_available = LOGS_DIR.exists() and os.access(str(LOGS_DIR), os.W_OK)
except (OSError, PermissionError):
    _base_file_logging_available = False

# Базовые handlers (всегда доступны)
_base_handlers = {
    "console": {
        "level": "INFO",
        "class": "logging.StreamHandler",
        "formatter": "simple",
    },
}

# Добавляем файловые handlers только если директория доступна
if _base_file_logging_available:
    _base_handlers["import_file"] = {
        "level": "INFO",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOGS_DIR / "import_products.log"),
        "maxBytes": 10 * 1024 * 1024,  # type: ignore[dict-item]
        "backupCount": 5,  # type: ignore[dict-item]
        "formatter": "verbose",
        "encoding": "utf-8",
    }
    _base_handlers["error_file"] = {
        "level": "ERROR",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": str(LOGS_DIR / "errors.log"),
        "maxBytes": 10 * 1024 * 1024,  # type: ignore[dict-item]
        "backupCount": 5,  # type: ignore[dict-item]
        "formatter": "verbose",
        "encoding": "utf-8",
    }

# Определяем loggers в зависимости от доступности файлового логирования
_import_handlers = ["import_file", "console"] if _base_file_logging_available else ["console"]
_products_handlers = ["console", "error_file"] if _base_file_logging_available else ["console"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} [{module}:{lineno}] {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "simple": {
            "format": "[{asctime}] {levelname} {message}",
            "style": "{",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": _base_handlers,
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": True,
        },
        "import_products": {
            "handlers": _import_handlers,
            "level": "INFO",
            "propagate": False,
        },
        "apps.products": {
            "handlers": _products_handlers,
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
}

# Banner limits (Story 32.4)
MARKETING_BANNER_LIMIT = 5
HERO_BANNER_LIMIT = 10

# ============================================================================
# Site URL Configuration (Story 29.4)
# ============================================================================

# URL сайта для использования в email templates и ссылках
SITE_URL = config("SITE_URL", default="http://localhost:3000")

# ============================================================================
# Настройки безопасности (переопределяются в продакшене)
# ============================================================================

SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

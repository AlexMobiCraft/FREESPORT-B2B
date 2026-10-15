"""Настройки окружения для тестов FREESPORT."""

# pylint: disable=wildcard-import, unused-wildcard-import
import os
import tempfile
from pathlib import Path
from typing import Any  # pylint: disable=unused-import
from urllib.parse import urlsplit, urlunsplit

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

# ==============================================================================
# ИЗОЛЯЦИЯ ВОРКЕРОВ pytest-xdist И ВРЕМЕННЫЕ ФАЙЛЫ
# ==============================================================================
#
# При `pytest -n N` каждый воркер — отдельный процесс; xdist сообщает его номер
# через PYTEST_XDIST_WORKER ("gw0", "gw1", …) ещё до загрузки настроек.
# Тестовую БД pytest-django разводит по воркерам сам (суффикс `_gwN`), а Redis и
# файловые каталоги — нет. Без разведения autouse-фикстура `clear_db_before_test`
# одного воркера делает FLUSHDB (`cache.clear()`) посреди теста другого и сносит
# ему локи импорта 1С, а импорты соседей пишут в общий каталог обмена.
_XDIST_WORKER = os.environ.get("PYTEST_XDIST_WORKER", "")
_WORKER_INDEX = int(_XDIST_WORKER[2:]) if _XDIST_WORKER.startswith("gw") else 0

# Своя БД Redis на воркер: номер из REDIS_URL плюс номер воркера. У Redis 16 БД,
# поэтому при номере 1 из docker-compose.test.yml предел — `-n 15`.
_redis_url = urlsplit(CACHES["default"]["LOCATION"])  # noqa: F405
_redis_db = int(_redis_url.path.lstrip("/") or 0) + _WORKER_INDEX
CACHES["default"]["LOCATION"] = urlunsplit(_redis_url._replace(path=f"/{_redis_db}"))  # noqa: F405

# Файлы, которые пишут тесты, — во временный каталог контейнера, а не в BASE_DIR.
# В локальном Docker на Windows `/app` — bind-mount через 9P: каждая запись идёт
# на диск Windows (медленно), а `backend/media` копил десятки тысяч файлов от тестов.
_TEST_FILES_ROOT = Path(tempfile.gettempdir()) / "freesport-test" / (_XDIST_WORKER or "main")
MEDIA_ROOT = _TEST_FILES_ROOT / "media"
ONEC_PRIVATE_DIR = _TEST_FILES_ROOT / "onec"
# В base.py каталоги обмена вычислены из ONEC_PRIVATE_DIR до этого переопределения.
ONEC_EXCHANGE = {  # noqa: F405
    **ONEC_EXCHANGE,  # noqa: F405
    "TEMP_DIR": ONEC_PRIVATE_DIR / "1c_temp",
    "IMPORT_DIR": ONEC_PRIVATE_DIR / "1c_import",
}
# Аудит-логи обмена (orders.xml и т. п.): без настройки `_get_exchange_log_dir()` пишет
# в BASE_DIR/var/1c_exchange/logs — по ~80 файлов на прогон на диск Windows.
EXCHANGE_LOG_DIR = _TEST_FILES_ROOT / "1c_exchange" / "logs"

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
    "admin@optisport.ru",
)

# Отключаем логирование в консоль, чтобы вывод тестов был чистым.
LOGGING: dict[str, Any] = {}  # type: ignore[no-redef]

# В тестах throttle не должен пересекаться между кейсами/worker-ами.
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {
    **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],  # type: ignore[dict-item]
    "anon": "100000/min",
    "subscribe": "100000/min",
    "unsubscribe": "100000/min",
    "user": "100000/min",
}

# Гарантированно отключаем Django Debug Toolbar в тестах,
# даже если он был добавлен в другом файле настроек.
INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "debug_toolbar"]
if "apps.integrations" not in INSTALLED_APPS and "apps.integrations.apps.IntegrationsConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("apps.integrations")
if "apps.integrations" not in INSTALLED_APPS and "apps.integrations.apps.IntegrationsConfig" not in INSTALLED_APPS:
    INSTALLED_APPS.append("apps.integrations")

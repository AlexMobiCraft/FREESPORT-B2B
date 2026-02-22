"""
Константы модуля orders.

Централизованные константы для использования в сервисах и моделях заказов.
"""

from enum import Enum

# =============================================================================
# Order ID Constants
# =============================================================================

ORDER_ID_PREFIX = "order-"
"""Префикс ID заказа в формате 1С (e.g., 'order-123')."""


# =============================================================================
# Status Mapping
# =============================================================================

# Маппинг статусов 1С → FREESPORT (AC3)
STATUS_MAPPING: dict[str, str] = {
    "ОжидаетОбработки": "processing",
    "Подтвержден": "confirmed",
    "Отгружен": "shipped",
    "Доставлен": "delivered",
    "Отменен": "cancelled",
    "Возвращен": "refunded",
}

# Pre-computed lowercase маппинг для оптимизации регистронезависимого поиска
STATUS_MAPPING_LOWER: dict[str, str] = {k.lower(): v for k, v in STATUS_MAPPING.items()}

# [AI-Review][Low] DRY: ORDER_STATUSES — единый источник истины для всех статусов
ORDER_STATUSES = [
    ("pending", "Ожидает обработки"),
    ("confirmed", "Подтвержден"),
    ("processing", "В обработке"),
    ("shipped", "Отправлен"),
    ("delivered", "Доставлен"),
    ("cancelled", "Отменен"),
    ("refunded", "Возвращен"),
]

# Множество всех допустимых статусов (производное от ORDER_STATUSES)
ALL_ORDER_STATUSES: set[str] = {status for status, _ in ORDER_STATUSES}

# Финальные статусы не должны регрессировать в активные
# [AI-Review][Low] DRY: производные множества из ORDER_STATUSES
_FINAL_STATUS_CODES = {"delivered", "cancelled", "refunded"}
FINAL_STATUSES: set[str] = {s for s in ALL_ORDER_STATUSES if s in _FINAL_STATUS_CODES}

_ACTIVE_STATUS_CODES = {"pending", "confirmed", "processing", "shipped"}
ACTIVE_STATUSES: set[str] = {s for s in ALL_ORDER_STATUSES if s in _ACTIVE_STATUS_CODES}

# Priority-based regression check (Story 5.2, AC8)
# Higher number = further in lifecycle. 0 = special (always allowed).
STATUS_PRIORITY: dict[str, int] = {
    "pending": 1,
    "confirmed": 2,
    "processing": 3,
    "shipped": 4,
    "delivered": 5,
    "cancelled": 0,  # Особый случай: всегда разрешён
    "refunded": 0,  # Особый случай: всегда разрешён
}


# =============================================================================
# Processing Status Enum
# =============================================================================


class ProcessingStatus(str, Enum):
    """
    Статусы обработки заказа в сервисе импорта.

    Используется вместо magic strings для типобезопасности.
    """

    UPDATED = "updated"
    """Заказ успешно обновлён."""

    SKIPPED_UP_TO_DATE = "skipped_up_to_date"
    """Заказ пропущен — данные уже актуальны."""

    SKIPPED_UNKNOWN_STATUS = "skipped_unknown_status"
    """Заказ пропущен из-за неизвестного статуса 1С."""

    SKIPPED_DATA_CONFLICT = "skipped_data_conflict"
    """Заказ пропущен из-за конфликта данных (несовпадение номера/ID)."""

    SKIPPED_STATUS_REGRESSION = "skipped_status_regression"
    """Заказ пропущен из-за попытки регрессии финального статуса."""

    NOT_FOUND = "not_found"
    """Заказ не найден в БД."""


# =============================================================================
# Field Whitelist (Story 5.2, AC14)
# =============================================================================

ALLOWED_ORDER_FIELDS: set[str] = {"Номер", "Ид", "ЗначенияРеквизитов"}
"""Допустимые дочерние элементы <Документ> для обработки."""

ALLOWED_REQUISITES: set[str] = {
    "СтатусЗаказа",
    "Статус Заказа",
    "ДатаОплаты",
    "Дата Оплаты",
    "ДатаОтгрузки",
    "Дата Отгрузки",
}
"""Допустимые наименования реквизитов внутри <ЗначенияРеквизитов>."""


# =============================================================================
# Import Limits
# =============================================================================

MAX_ERRORS = 100
"""Максимальное количество ошибок в ImportResult."""

MAX_CONSECUTIVE_ERRORS = 10
"""Максимальное количество последовательных ошибок до остановки логирования."""

"""Утилиты для работы с атрибутами товаров."""

from __future__ import annotations

import re
import unicodedata


def normalize_attribute_name(name: str) -> str:
    """
    Нормализует название атрибута для сравнения и дедупликации.

    Преобразования:
    - Удаление акцентов и диакритики (é → e)
    - Приведение к нижнему регистру
    - Удаление всех пробелов
    - Удаление специальных символов (оставляем только буквы и цифры)

    Args:
        name: Название атрибута для нормализации

    Returns:
        Нормализованное название атрибута

    Examples:
        >>> normalize_attribute_name("Размер")
        'размер'
        >>> normalize_attribute_name("РАЗМЕР")
        'размер'
        >>> normalize_attribute_name(" Размер ")
        'размер'
        >>> normalize_attribute_name("Цвет")
        'цвет'
        >>> normalize_attribute_name("Тест 123")
        'тест123'
        >>> normalize_attribute_name("  Spacing  ")
        'spacing'
        >>> normalize_attribute_name("")
        ''
    """
    if not name:
        return ""

    # Удаляем акценты и диакритики (é → e)
    name = unicodedata.normalize("NFKD", name)
    name = "".join(c for c in name if not unicodedata.combining(c))

    # Lowercase
    name = name.lower()

    # Удаляем все пробелы
    name = re.sub(r"\s+", "", name)

    # Удаляем спецсимволы (оставляем только буквы и цифры)
    # Используем \w но затем удаляем подчеркивания
    name = re.sub(r"[^\w]", "", name, flags=re.UNICODE)
    name = name.replace("_", "")

    return name


def normalize_attribute_value(value: str) -> str:
    """
    Нормализует значение атрибута для сравнения и дедупликации.

    Использует ту же логику что и normalize_attribute_name.

    Args:
        value: Значение атрибута для нормализации

    Returns:
        Нормализованное значение атрибута

    Examples:
        >>> normalize_attribute_value("Красный")
        'красный'
        >>> normalize_attribute_value("КРАСНЫЙ")
        'красный'
        >>> normalize_attribute_value(" красный ")
        'красный'
        >>> normalize_attribute_value("XL")
        'xl'
    """
    return normalize_attribute_name(value)

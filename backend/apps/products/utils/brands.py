"""Утилиты для работы с брендами."""

from __future__ import annotations

import re
import unicodedata


def normalize_brand_name(name: str | None) -> str:
    """
    Нормализует название бренда для сравнения и дедупликации.

    Преобразования:
    - Удаление акцентов и диакритики (é → e)
    - Приведение к нижнему регистру
    - Удаление всех пробелов
    - Удаление специальных символов (оставляем только буквы и цифры)

    Args:
        name: Название бренда для нормализации

    Returns:
        Нормализованное название бренда

    Examples:
        >>> normalize_brand_name("BOYBO")
        'boybo'
        >>> normalize_brand_name("Boy Bo")
        'boybo'
        >>> normalize_brand_name("Under-Armour")
        'underarmour'
        >>> normalize_brand_name("Рокки")
        'рокки'
        >>> normalize_brand_name("Beyoncé")
        'beyonce'
        >>> normalize_brand_name("Nike2024")
        'nike2024'
        >>> normalize_brand_name("")
        ''
        >>> normalize_brand_name(None)
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

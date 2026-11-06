"""Определение типа импорта по имени файла, присланного 1С.

Единственная точка правды. Раньше логика жила в двух независимых копиях —
`ImportOrchestratorService._detect_file_type` и блок `detected_file_type`
в `apps/products/tasks.py`, — и копии разошлись: задача знала префикс
`propertiesGoods`, оркестратор — нет. Из-за расхождения отчёт сессии писал
`file_type=rests`, а выполнялся полный импорт каталога.
"""

from __future__ import annotations

# Префиксы имён файлов CommerceML 3.1 → шаг импорта команды
# `import_products_from_1c`. Порядок кортежей значения не имеет: префиксы
# не пересекаются между группами.
#
# Здесь перечислены только те файлы, которые команда действительно читает
# (`_collect_xml_files`). `units`, `storages`, `propertiesOffers` она не
# собирает — им остаётся `all`, и добавлять их сюда нельзя: строгая проверка
# «обещанный файл обязан быть прочитан» утопила бы такие сессии в FAILED.
_PREFIXES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("goods", "import", "groups", "propertiesgoods"), "goods"),
    (("offers",), "offers"),
    (("prices", "pricelists"), "prices"),
    (("rests",), "rests"),
    (("contragents",), "contragents"),
)


def detect_file_type(filename: str | None) -> str:
    """Вернуть тип импорта для имени файла.

    Args:
        filename: Имя файла от 1С (`rests_1_16_….xml`) или служебное значение
            вроде `"complete"`. Пустое значение и `None` допустимы.

    Returns:
        Один из `goods` / `offers` / `prices` / `rests` / `contragents`; `all` —
        если имя ни о чём не говорит (в том числе для `mode=complete`, где
        выгрузка полная). `contragents` — не шаг команды импорта каталога, а
        маршрут на отдельную команду `import_customers_from_1c`.
    """
    fn_lower = (filename or "").lower()
    if not fn_lower:
        return "all"

    for prefixes, file_type in _PREFIXES:
        if fn_lower.startswith(prefixes):
            return file_type

    return "all"

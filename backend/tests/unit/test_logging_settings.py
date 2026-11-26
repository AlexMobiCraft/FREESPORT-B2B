"""Логгер `apps.integrations` выводит INFO-строки обмена с 1С.

До spec-1c-order-statuses-followup логгер не был настроен: итоги `[INFO MODE]`,
`[BUS ORDERS]`, `[Task …]` пишутся INFO, а root стоит на WARNING — строк не было
ни локально, ни на проде. Каждый модуль окружения (`development`, `staging`,
`production`) объявляет свой `LOGGING` и целиком заменяет `base.py`, поэтому
проверяются все четыре.

Настройки читаются из исходного текста через `ast`, как в
`tests/unit/test_security_settings.py`: `production.py` без `DB_NAME` не
импортируется. `LOGGING` в `base.py` не литерал (хендлеры — переменная
`_base_handlers`), поэтому `literal_eval` применяется к отдельным узлам, а имя
переменной разрешается по присваиванию верхнего уровня.
"""

import ast
import io
import logging
import logging.config
import re
from pathlib import Path

import pytest

SETTINGS_DIR = Path(__file__).resolve().parents[2] / "freesport" / "settings"
SETTINGS_MODULES = ("base.py", "development.py", "staging.py", "production.py")
LOGGER_NAME = "apps.integrations"


def _module_assignments(name: str) -> dict[str, ast.expr]:
    """Узлы значений присваиваний верхнего уровня (последнее присваивание выигрывает)."""
    tree = ast.parse((SETTINGS_DIR / name).read_text(encoding="utf-8"))
    assignments: dict[str, ast.expr] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            targets = [node.target.id]
            value = node.value
        else:
            continue
        for target in targets:
            assignments[target] = value
    return assignments


def _dict_item(node: ast.expr, key: str) -> ast.expr:
    assert isinstance(node, ast.Dict), f"ожидался литерал dict, а не {type(node).__name__}"
    for k, v in zip(node.keys, node.values):
        if isinstance(k, ast.Constant) and k.value == key:
            return v
    raise KeyError(key)


def _resolve(node: ast.expr, assignments: dict[str, ast.expr]) -> object:
    """`literal_eval` узла; имя переменной разрешается по присваиванию модуля."""
    if isinstance(node, ast.Name):
        node = assignments[node.id]
    return ast.literal_eval(node)


def _logging_parts(module: str) -> tuple[dict, dict, dict]:
    """(логгер `apps.integrations`, хендлеры, форматтеры) из `LOGGING` модуля."""
    assignments = _module_assignments(module)
    logging_node = assignments["LOGGING"]
    logger = ast.literal_eval(_dict_item(_dict_item(logging_node, "loggers"), LOGGER_NAME))
    handlers = _resolve(_dict_item(logging_node, "handlers"), assignments)
    try:
        formatters = _resolve(_dict_item(logging_node, "formatters"), assignments)
    except KeyError:
        formatters = {}
    return logger, handlers, formatters  # type: ignore[return-value]


@pytest.mark.unit
@pytest.mark.parametrize("module", SETTINGS_MODULES)
class TestIntegrationsLogger:
    def test_level_is_info(self, module):
        logger, _, _ = _logging_parts(module)

        assert logger["level"] == "INFO"

    def test_does_not_propagate_to_root(self, module):
        """Без дубля: Celery с `-l info` вешает на root свой хендлер."""
        logger, _, _ = _logging_parts(module)

        assert logger["propagate"] is False

    def test_handlers_are_declared(self, module):
        logger, handlers, _ = _logging_parts(module)

        assert logger["handlers"], "у логгера нет хендлеров"
        for handler in logger["handlers"]:
            assert handler in handlers, f"хендлер {handler!r} не объявлен в {module}"

    def test_handler_format_has_time_and_level(self, module):
        logger, handlers, formatters = _logging_parts(module)

        for handler in logger["handlers"]:
            formatter_name = handlers[handler].get("formatter")
            assert formatter_name, f"у хендлера {handler!r} в {module} нет форматтера"
            fmt = formatters[formatter_name]["format"]
            assert "asctime" in fmt, f"формат {formatter_name!r} без времени"
            assert "levelname" in fmt, f"формат {formatter_name!r} без уровня"


@pytest.fixture
def restore_integrations_loggers():
    """Вернуть логгеры `apps.integrations*` в прежнее состояние после `dictConfig`."""
    manager = logging.Logger.manager

    def _snapshot():
        return {
            name: (lg.level, list(lg.handlers), lg.propagate, lg.disabled)
            for name, lg in list(manager.loggerDict.items())
            if isinstance(lg, logging.Logger) and (name == LOGGER_NAME or name.startswith(LOGGER_NAME + "."))
        }

    saved = _snapshot()
    yield
    for name in _snapshot():
        lg = logging.getLogger(name)
        if name in saved:
            lg.level, handlers, lg.propagate, lg.disabled = saved[name]
            lg.handlers = handlers
        else:
            lg.setLevel(logging.NOTSET)
            lg.handlers = []
            lg.propagate = True
            lg.disabled = False


@pytest.mark.unit
@pytest.mark.parametrize("module", SETTINGS_MODULES)
def test_info_line_is_emitted_once_with_time_and_level(module, restore_integrations_loggers):
    """Конфигурация логгера реально применяется `dictConfig` и выводит INFO-строку.

    AST-проверки выше не ловят опечатку в `class` хендлера (упадёт `dictConfig` при старте)
    и `level` хендлера выше INFO (строки молча пропадут) — здесь они видны.
    """
    logger_cfg, handlers, formatters = _logging_parts(module)
    stream = io.StringIO()
    used_handlers = {name: dict(handlers[name], stream=stream) for name in logger_cfg["handlers"]}
    used_formatters = {
        cfg["formatter"]: formatters[cfg["formatter"]] for cfg in used_handlers.values() if "formatter" in cfg
    }

    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": used_formatters,
            "handlers": used_handlers,
            "loggers": {LOGGER_NAME: logger_cfg},
        }
    )
    logging.getLogger(f"{LOGGER_NAME}.x").info("[BUS ORDERS] probe")

    lines = stream.getvalue().splitlines()
    assert len(lines) == 1, f"ожидалась одна строка, а вывод {module}: {lines!r}"
    assert "[BUS ORDERS] probe" in lines[0]
    assert "INFO" in lines[0]
    assert re.search(r"\d{2}:\d{2}:\d{2}", lines[0]), f"строка без времени: {lines[0]!r}"

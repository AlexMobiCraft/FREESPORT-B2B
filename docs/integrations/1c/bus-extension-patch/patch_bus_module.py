"""Часть A задания dev-task-role-from-1c-agreement: правка модуля БУС_ВыгрузкаСервер.

Добавляет в ``СформироватьДанныеПоКонтрагентам`` отбор действующих соглашений с видом цен
(формула A2) и запись блока ``<ЗначенияРеквизитов>`` в XDTO-объект контрагента (A1/A3).

Идемпотентно: повторный запуск ничего не меняет. Все вставки помечены маркером
``FREESPORT: вид цен клиента`` — по нему правки переносятся при обновлении модуля БУС.

Использование::

    python patch_bus_module.py <каталог исходников расширения>

где каталог — результат ``/DumpConfigToFiles ... -Extension ОбменСБитриксУправлениеСайтомУТ``,
внутри которого лежит ``CommonModules/БУС_ВыгрузкаСервер/Ext/Module.bsl``.

Тексты вставок — в ``fragments/``: 01_param (параметр даты), 02_query (временные таблицы
ВТ_FS_* в тексте запроса), 03_code (запись блока в цикле по контрагентам).
"""

import shutil
import sys
from pathlib import Path

MARKER = "FREESPORT: вид цен клиента"

FRAGMENTS = Path(__file__).parent / "fragments"

# Якоря — строки непропатченного модуля БУС 8.1.0.40 / 8.1.0.45 (целевые функции идентичны).
ANCHORS = {
    # вставка после установки параметров запроса контрагентов
    "01_param.bsl": (
        '\tЗапрос.УстановитьПараметр("ТипДанных"\t, СтруктураНастроек.ТипыОбъектовОбмена.Контрагент);\r\n'
        '\tЗапрос.УстановитьПараметр("мДанных"\t\t, МассивДанных.ВыгрузитьКолонку("Объект"));\r\n'
    ),
    # вставка перед финальным запросом пакета (выборка контрагентов)
    "02_query.bsl": (
        "\t|////////////////////////////////////////////////////////////////////////////////\r\n"
        "\t|ВЫБРАТЬ РАЗРЕШЕННЫЕ\r\n"
        "\t|\tВТ_Контрагенты.Контрагент КАК Объект,\r\n"
    ),
    # вставка перед добавлением контрагента в коллекцию XDTO;
    # сама строка встречается в модуле пять раз, поэтому ищется первое вхождение
    # после уникального ориентира GUARD_CODE (см. resolve_anchor)
    "03_code.bsl": "\t\t\tКонтрагентыXDTO.Контрагент.Добавить(КонтрагентXDTO);\r\n",
}

# Куда вставлять фрагмент относительно якоря: after — после, before — перед.
POSITION = {"01_param.bsl": "after", "02_query.bsl": "before", "03_code.bsl": "before"}

# Ориентир для неуникального якоря 03: строка встречается в модуле один раз
# и находится непосредственно перед нужным вхождением.
GUARD_CODE = "Функция СформироватьДанныеПоКонтрагентам(СтруктураНастроек, МассивДанных)"


def resolve_anchor(text: str, name: str, anchor: str) -> int | None:
    """Позиция начала якоря в тексте модуля или None, если якорь не опознан."""
    if name == "03_code.bsl":
        guard = text.find(GUARD_CODE)
        if guard == -1 or text.count(GUARD_CODE) != 1:
            print(f"ориентир для {name} не опознан — модуль изменился, правьте вручную")
            return None
        at = text.find(anchor, guard)
        if at == -1:
            print(f"якорь {name} после ориентира не найден — правьте вручную")
            return None
        return at

    found = text.count(anchor)
    if found != 1:
        print(f"якорь {name} найден {found} раз (ожидался 1) — модуль изменился, правьте вручную")
        return None
    return text.find(anchor)


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    module = Path(sys.argv[1]) / "CommonModules" / "БУС_ВыгрузкаСервер" / "Ext" / "Module.bsl"
    if not module.exists():
        print(f"не найден модуль: {module}")
        return 1

    text = module.read_text(encoding="utf-8-sig", newline="")

    if MARKER in text:
        print("правка уже применена, изменений нет")
        return 0

    positions = {}
    for name, anchor in ANCHORS.items():
        position = resolve_anchor(text, name, anchor)
        if position is None:
            return 1
        positions[name] = position

    backup = module.with_name("Module.bsl.orig")
    shutil.copyfile(module, backup)

    # вставки идут с конца файла, чтобы ранее вычисленные позиции не съезжали
    for name in sorted(positions, key=positions.get, reverse=True):
        fragment = (FRAGMENTS / name).read_text(encoding="utf-8", newline="")
        at = positions[name]
        if POSITION[name] == "after":
            at += len(ANCHORS[name])
        text = text[:at] + fragment + text[at:]

    module.write_text(text, encoding="utf-8-sig", newline="")

    print(f"бэкап: {backup}")
    print("вставлено: параметр отбора соглашений, временные таблицы ВТ_FS_*, запись ЗначенияРеквизитов")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

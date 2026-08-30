"""A1: добавляет элемент ЗначенияРеквизитов в XSD-тип Контрагент расширения БУС.

Без этой правки XDTO не даёт записать блок: в исходной схеме тип `Контрагент` — `xs:choice`
без элемента `ЗначенияРеквизитов` и без `xs:any`.

Идемпотентно: повторный запуск ничего не меняет. Правка помечена маркером FREESPORT,
чтобы её было видно при обновлении модуля БУС.

Использование::

    python patch_xsd_contragent.py <каталог исходников расширения>

где каталог — результат ``/DumpConfigToFiles ... -Extension ОбменСБитриксУправлениеСайтомУТ``.
"""

import shutil
import sys
from pathlib import Path

MARKER = "FREESPORT: вид цен клиента"
TYPE_START = '<xs:complexType name="Контрагент">'
CHOICE_END = "        </xs:choice>\r\n"

BLOCK = (
    f"            <!-- {MARKER} (dev-task-role-from-1c-agreement, A1) -->\r\n"
    '            <xs:element name="ЗначенияРеквизитов"\r\n'
    '                        minOccurs="0">\r\n'
    "                <xs:complexType>\r\n"
    "                    <xs:sequence>\r\n"
    '                        <xs:element name="ЗначениеРеквизита"\r\n'
    '                                    type="tns:ЗначениеРеквизита"\r\n'
    '                                    maxOccurs="unbounded" />\r\n'
    "                    </xs:sequence>\r\n"
    "                </xs:complexType>\r\n"
    "            </xs:element>\r\n"
)

TEMPLATE_PATH = Path("Catalogs") / "БУС_НастройкиОбмена" / "Templates" / "СхемаXSDОбмена" / "Ext" / "Template.bin"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2

    template = Path(sys.argv[1]) / TEMPLATE_PATH
    if not template.exists():
        print(f"не найден макет схемы: {template}")
        return 1

    text = template.read_text(encoding="utf-8-sig", newline="")

    type_pos = text.find(TYPE_START)
    if type_pos == -1:
        print("не найден тип Контрагент")
        return 1

    choice_pos = text.find(CHOICE_END, type_pos)
    if choice_pos == -1:
        print("не найден конец xs:choice типа Контрагент")
        return 1

    if MARKER in text[type_pos:choice_pos]:
        print("правка уже применена, изменений нет")
        return 0

    backup = template.with_name("Template.bin.orig")
    shutil.copyfile(template, backup)

    patched = text[:choice_pos] + BLOCK + text[choice_pos:]
    template.write_text(patched, encoding="utf-8-sig", newline="")

    print(f"бэкап: {backup}")
    print(f"вставлено строк: {BLOCK.count(chr(10))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

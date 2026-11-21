"""
Реальные выгрузки 1С для тестов правила допуска импорта.

Два источника:

* `tests/fixtures/1c-data/` — закоммиченный срез реальной выгрузки (один корень
  «СПОРТ», три товара). Есть в CI, на нём живут тесты, не помеченные
  `data_dependent`.
* `data/import_1c/snapshots/2026-09-21-deletion-marks/` — подмножество снимка
  21.09.2026 со всеми пятью корнями 1С, товарами без группы и с неизвестной
  группой, BT45-RU с пометкой удаления и помеченными предложениями. Каталог в
  `.gitignore`: тесты на нём помечаются `data_dependent` и без данных скипаются.

Синтетические XML для импорта 1С проект запрещает. Для сценариев, которых нет
в выгрузке (помеченная группа внутри СПОРТ, возврат в СПОРТ, несколько групп),
допускается правка КОПИИ реального фрагмента — для этого здесь `edit_copy`.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent

# --- Закоммиченный срез -----------------------------------------------------
ONEC_FIXTURES = BACKEND_ROOT / "tests" / "fixtures" / "1c-data"
FIXTURE_GROUPS_XML = ONEC_FIXTURES / "groups" / "groups.xml"
FIXTURE_GOODS_XML = ONEC_FIXTURES / "goods" / "import_files" / "goods.xml"
FIXTURE_OFFERS_XML = ONEC_FIXTURES / "offers" / "offers.xml"

# Корень «СПОРТ» и один из трёх товаров среза вместе с его группой.
FIXTURE_SPORT_ROOT_ID = "3d148346-bd77-11e4-afc8-20cf3073dde3"
FIXTURE_PRODUCT_ID = "018d777d-9094-11ec-a2ff-04421a23d8e8"
FIXTURE_PRODUCT_GROUP_ID = "9c5bad96-a802-11e7-8151-00155d87f90d"

# --- Подмножество снимка 21.09.2026 -----------------------------------------
DELETION_MARKS_SNAPSHOT = BACKEND_ROOT / "data" / "import_1c" / "snapshots" / "2026-09-21-deletion-marks"

SNAPSHOT_SPORT_ROOT_ID = "3d148346-bd77-11e4-afc8-20cf3073dde3"
# «Трико борцовское BoyBo, BT45-RU»: в папке «Номенклатура к удалению» и с
# <ПометкаУдаления>true</ПометкаУдаления> — с него началась задача.
BT45_RED_ID = "4be1a200-4111-11f0-8af6-fa163ea88911"  # goods_1_9
BT45_BLUE_ID = "5cf1d4de-4111-11f0-8af6-fa163ea88911"  # goods_1_10
# Товар есть в goods_1_1 (СПОРТ) и в goods_1_11 («Номенклатура к удалению»).
MOVED_TO_TRASH_ID = "3b6971fe-235f-11f1-973d-8214524df372"

_DIGITS_RE = re.compile(r"(\d+)")


def natural_key(path: Path) -> list[int | str]:
    """Порядок пакетов 1С по номеру: goods_1_2 раньше goods_1_10."""
    return [int(token) if token.isdigit() else token for token in _DIGITS_RE.split(path.name.lower())]


def snapshot_files(prefix: str) -> list[Path]:
    """Файлы подмножества снимка с данным префиксом в порядке пакетов."""
    return sorted(DELETION_MARKS_SNAPSHOT.glob(f"{prefix}_*.xml"), key=natural_key)


def require_snapshot() -> Path:
    """Каталог подмножества снимка; без данных тест скипается, а не падает."""
    if not snapshot_files("groups") or len(snapshot_files("goods")) < 4:
        pytest.skip(
            f"Подмножество снимка 1С недоступно: {DELETION_MARKS_SNAPSHOT} "
            "(каталог в .gitignore, нужны groups_1_1, goods_1_1/1_9/1_10/1_11 и их offers)"
        )
    return DELETION_MARKS_SNAPSHOT


def make_exchange_dir(base: Path) -> Path:
    """Пустой каталог обмена с подкаталогами, которые требует `--file-type=all`."""
    for subdir in ("groups", "goods", "offers", "prices", "rests", "priceLists"):
        (base / subdir).mkdir(parents=True, exist_ok=True)
    return base


def stage_snapshot(base: Path, *, goods: bool = True, offers: bool = True) -> Path:
    """Разложить подмножество снимка в каталог обмена (копии — импорт удаляет прочитанное)."""
    require_snapshot()
    make_exchange_dir(base)
    for source in snapshot_files("groups"):
        shutil.copyfile(source, base / "groups" / source.name)
    if goods:
        for source in snapshot_files("goods"):
            shutil.copyfile(source, base / "goods" / source.name)
    if offers:
        for source in snapshot_files("offers"):
            shutil.copyfile(source, base / "offers" / source.name)
    return base


def mark_deleted(xml_text: str, onec_id: str, value: str = "true") -> str:
    """Поставить <ПометкаУдаления> объекту с данным Ид в тексте реальной выгрузки.

    В CommerceML пометка идёт сразу за Ид и НомеромВерсии объекта, поэтому
    правится первая пометка после нужного Ид.
    """
    anchor = f"<Ид>{onec_id}</Ид>"
    start = xml_text.index(anchor)
    head, tail = xml_text[:start], xml_text[start:]
    marked = re.sub(
        r"<ПометкаУдаления>[^<]*</ПометкаУдаления>",
        f"<ПометкаУдаления>{value}</ПометкаУдаления>",
        tail,
        count=1,
    )
    assert marked != tail or value == "false", f"У объекта {onec_id} нет тега <ПометкаУдаления>"
    return head + marked


def edit_copy(source: Path, target: Path, transform) -> Path:
    """Скопировать реальный XML в `target`, применив к тексту `transform`."""
    text = source.read_text(encoding="utf-8-sig")
    edited = transform(text)
    assert edited != text, f"Правка копии {source.name} ничего не изменила"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(edited, encoding="utf-8")
    return target

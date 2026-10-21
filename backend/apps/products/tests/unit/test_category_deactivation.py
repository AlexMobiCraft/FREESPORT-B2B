"""Тесты деактивации категорий при импорте 1С (VariantImportProcessor).

Инцидент (21.10.2026): 1С шлёт `groups*.xml` частичными пакетами, а импорт гасил каждую
категорию, которой нет в текущем XML. Порог предохранителя пропускал малые ветки
(3 ребёнка) и потери до 30 %, поэтому подкатегории на витрине мигали в зависимости
от последнего пакета («Обувь для бокса», «Мешки, груши, манекены» и др.).

Теперь отсутствие в XML ничего не значит. Гасятся только группы, которые 1С прислала
и которые правило допуска отсекло: помеченные на удаление, вынесенные из поддерева
якоря и потомки таких групп. Покрывает I/O-матрицу spec-fix-category-deactivation-partial-groups.md.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import pytest

from apps.products.models import Category, ImportSession
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import CategoryData, VariantImportProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.unit]

# Реальная выгрузка групп (в .gitignore, на раннере отсутствует)
ONEC_RUNTIME_GROUPS = Path(__file__).resolve().parents[5] / "data" / "import_1c" / "groups"

# Глобальный счётчик для абсолютной уникальности тестовых данных
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс для тестов."""
    global _unique_counter
    _unique_counter += 1
    return f"{_unique_counter}_{uuid.uuid4().hex[:8]}"


# ============================================================================
# Fixtures и хелперы
# ============================================================================


def new_processor() -> VariantImportProcessor:
    """Процессор с собственной сессией: каждая сессия 1С — отдельный процессор."""
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.IN_PROGRESS,
    )
    return VariantImportProcessor(session_id=session.id)


@pytest.fixture
def unanchored(settings):
    """Отключает фильтрацию по якорю (ROOT_CATEGORY_NAME=None)."""
    settings.ROOT_CATEGORY_NAME = None
    return settings


@pytest.fixture
def anchor(settings: Any) -> Category:
    """Якорь дерева витрины: настройка и категория с одним именем."""
    root_name = f"СПОРТ-{get_unique_suffix()}"
    settings.ROOT_CATEGORY_NAME = root_name
    return make_category(name=root_name)


def make_category(
    *,
    name: str | None = None,
    onec_id: str | None = None,
    parent: Category | None = None,
    is_active: bool = True,
) -> Category:
    """Создаёт категорию с гарантированно уникальными name/slug/onec_id."""
    suffix = get_unique_suffix()
    return Category.objects.create(
        name=name or f"Раздел {suffix}",
        slug=f"cat-{suffix}",
        onec_id=onec_id or f"oid-{suffix}",
        parent=parent,
        is_active=is_active,
    )


def make_children(parent: Category, count: int) -> list[Category]:
    """Создаёт `count` активных детей у указанного родителя."""
    return [make_category(parent=parent) for _ in range(count)]


def cat_data(category: Category, parent: Category | None = None, *, deleted: bool = False) -> CategoryData:
    """Запись XML-выгрузки для существующей категории."""
    data: CategoryData = {"id": category.onec_id, "name": category.name, "description": "", "is_deleted": deleted}
    if parent is not None:
        data["parent_id"] = parent.onec_id
    return data


def run_session(
    xml: list[CategoryData], *, status: str = ImportSession.ImportStatus.COMPLETED
) -> VariantImportProcessor:
    """Одна сессия обмена: groups*.xml → process_categories → finalize_session."""
    processor = new_processor()
    processor.process_categories(xml)
    processor.finalize_session(status)
    return processor


def is_active(category: Category) -> bool:
    category.refresh_from_db()
    return category.is_active


# ============================================================================
# Строки I/O-матрицы
# ============================================================================


def test_partial_packet_keeps_small_branch(anchor):
    """Инцидент «Обувь для единоборств»: у родителя 3 ребёнка, в пакете пришёл один."""
    parent = make_category(parent=anchor)
    kids = make_children(parent, 3)

    run_session([cat_data(anchor), cat_data(parent, anchor), cat_data(kids[0], parent)])

    assert all(is_active(k) for k in kids), "Не пришедшие в пакете подкатегории должны остаться активными"
    assert is_active(parent)


def test_partial_packet_keeps_loss_below_old_threshold(anchor):
    """Инцидент «Легкая атлетика»: 1 из 5 (20 %) раньше проходило под порог 30 %."""
    parent = make_category(parent=anchor)
    kids = make_children(parent, 5)

    run_session([cat_data(anchor), cat_data(parent, anchor)] + [cat_data(k, parent) for k in kids[:4]])

    assert is_active(kids[4]), "Пятая подкатегория не пришла в пакете, но удалена в 1С не была"


def test_marked_group_is_deactivated(anchor):
    """Группа помечена на удаление — гаснет; не пришедший сосед остаётся."""
    parent = make_category(parent=anchor)
    marked, kept, absent = make_children(parent, 3)

    run_session(
        [
            cat_data(anchor),
            cat_data(parent, anchor),
            cat_data(marked, parent, deleted=True),
            cat_data(kept, parent),
        ]
    )

    assert is_active(marked) is False
    assert is_active(kept)
    assert is_active(absent), "Сосед, которого нет в XML, трогать нельзя"


def test_descendant_of_marked_group_is_deactivated(anchor):
    """Потомок помеченной группы без собственной пометки гаснет вместе с предком."""
    marked = make_category(parent=anchor)
    child = make_category(parent=marked)
    outsider = make_category(parent=anchor)

    run_session(
        [
            cat_data(anchor),
            cat_data(marked, anchor, deleted=True),
            cat_data(child, marked),
        ]
    )

    assert is_active(marked) is False
    assert is_active(child) is False
    assert is_active(outsider), "Категории вне XML не тронуты"


def test_group_moved_out_of_anchor_tree_is_deactivated(anchor):
    """Якорный режим: 1С перенесла группу под чужой корень («Номенклатура к удалению»)."""
    moved = make_category(parent=anchor)
    foreign_root = make_category(name=f"К удалению {get_unique_suffix()}")
    sibling = make_category(parent=anchor)

    foreign_root_data = cat_data(foreign_root)
    run_session([cat_data(anchor), foreign_root_data, cat_data(moved, foreign_root)])

    assert is_active(moved) is False
    assert is_active(sibling)
    assert is_active(foreign_root) is False, "Корень вне дерева якоря, пришедший в XML, тоже отсекается"


def test_unanchored_group_returned_by_later_file_stays_active(unanchored):
    """Без якоря: помечена в первом groups*.xml, пометка снята во втором — сессия её не гасит."""
    root = make_category()
    bounced = make_category(parent=root)

    processor = new_processor()
    processor.process_categories([cat_data(root), cat_data(bounced, root, deleted=True)])
    processor.process_categories([cat_data(bounced, root)])
    processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

    assert is_active(bounced)


def test_deactivation_lands_in_session_report_and_details(anchor):
    """Гашение видно в ImportSession.report и report_details, а не только в файловом логе."""
    parent = make_category(parent=anchor)
    marked = make_category(parent=parent)

    processor = run_session([cat_data(anchor), cat_data(parent, anchor), cat_data(marked, parent, deleted=True)])

    session = ImportSession.objects.get(pk=processor.session_id)
    assert "погашено по явному сигналу" in session.report
    assert session.report_details["categories_deactivated"] == 1


def test_unanchored_marked_group_is_deactivated(unanchored):
    """Без якоря пометка удаления работает так же."""
    root = make_category()
    marked, kept = make_children(root, 2)

    run_session([cat_data(root), cat_data(marked, root, deleted=True), cat_data(kept, root)])

    assert is_active(marked) is False
    assert is_active(kept)


def test_returned_group_is_active_and_survives_next_partial_packet(anchor):
    """Регресс прода: группа вернулась в дерево — и следующий частичный пакет её не гасит."""
    parent = make_category(parent=anchor)
    bounced, other = make_children(parent, 2)

    run_session([cat_data(anchor), cat_data(parent, anchor), cat_data(bounced, parent, deleted=True)])
    assert is_active(bounced) is False

    run_session([cat_data(anchor), cat_data(parent, anchor), cat_data(bounced, parent)])
    assert is_active(bounced), "Снятая в 1С пометка должна включить группу обратно"

    run_session([cat_data(anchor), cat_data(parent, anchor), cat_data(other, parent)])
    assert is_active(bounced), "Частичный пакет без группы не должен её гасить"


def test_anchor_is_never_deactivated(anchor):
    """Пометка якоря в XML игнорируется: дерево витрины не должно опустеть."""
    child = make_category(parent=anchor)

    run_session([cat_data(anchor, deleted=True), cat_data(child, anchor)])

    assert is_active(anchor)
    assert is_active(child)


def test_failed_session_changes_nothing(anchor):
    """Деактивация применяется только при completed: упавшая сессия витрину не трогает."""
    parent = make_category(parent=anchor)
    marked = make_category(parent=parent)

    run_session(
        [cat_data(anchor), cat_data(parent, anchor), cat_data(marked, parent, deleted=True)],
        status=ImportSession.ImportStatus.FAILED,
    )

    assert is_active(marked)


def test_exclusions_accumulate_between_groups_files(anchor):
    """Помеченная группа пришла в первом groups*.xml, второй её не содержит — гасится по итогам сессии."""
    parent = make_category(parent=anchor)
    marked, kept = make_children(parent, 2)

    processor = new_processor()
    processor.process_categories([cat_data(anchor), cat_data(parent, anchor), cat_data(marked, parent, deleted=True)])
    processor.process_categories([cat_data(kept, parent)])
    processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

    assert is_active(marked) is False
    assert is_active(kept)


# ============================================================================
# Реальная выгрузка 1С
# ============================================================================


@pytest.mark.data_dependent
def test_real_groups_partial_packets_deactivate_nothing(settings: Any) -> None:
    """Полная выгрузка групп, затем частичные пакеты из неё же: ни одна категория не гаснет."""
    files = sorted(ONEC_RUNTIME_GROUPS.glob("groups_*.xml")) if ONEC_RUNTIME_GROUPS.exists() else []
    if not files:
        pytest.skip("Назначенный корпус data/import_1c/groups отсутствует (в .gitignore)")

    groups = XMLDataParser().parse_groups_xml(str(files[0]))
    anchor_row = next((g for g in groups if not g.get("parent_id") and g["name"] == "СПОРТ"), None)
    if anchor_row is None:
        pytest.skip("В реальной выгрузке групп нет якоря «СПОРТ»")
    settings.ROOT_CATEGORY_NAME = anchor_row["name"]

    run_session(groups)
    imported = Category.objects.count()
    assert imported > 50, "Поддерево СПОРТ из реальной выгрузки должно загрузиться целиком"

    # Три частичных пакета разного состава: якорь + каждый 7-й / 3-й / 11-й узел
    for step in (7, 3, 11):
        run_session([anchor_row] + groups[::step])

    assert Category.objects.count() == imported
    assert Category.objects.filter(is_active=False).count() == 0, "Частичные пакеты не должны гасить категории"

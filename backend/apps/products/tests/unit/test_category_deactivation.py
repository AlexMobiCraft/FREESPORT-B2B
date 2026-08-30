"""Тесты предохранителей деактивации категорий (VariantImportProcessor).

Инцидент: частичная выгрузка 1С гасила все категории, не встреченные в текущем XML,
и витрина `/catalog` схлопывалась до одной ветки. Реализованы два независимых барьера:

1. Гасятся только дети «раскрытых» родителей — тех, под которыми в выгрузке пришёл
   хотя бы один прошедший allowed-фильтр ребёнок.
2. Для каждого раскрытого родителя отдельно: деактивация отменяется, если затронет
   больше 30 % его активных детей (порог не применяется при < 4 активных детях).

Покрывает строки I/O-матрицы спецификации spec-fix-catalog-categories-deactivation.md.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from apps.products.models import Category, ImportSession
from apps.products.services.variant_import import CategoryData, VariantImportProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.unit]

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


@pytest.fixture
def import_session():
    """Сессия импорта для процессора."""
    return ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.IN_PROGRESS,
    )


@pytest.fixture
def processor(import_session):
    """Процессор импорта, привязанный к сессии."""
    return VariantImportProcessor(session_id=import_session.id)


@pytest.fixture
def unanchored(settings):
    """Отключает фильтрацию по якорю (ROOT_CATEGORY_NAME=None).

    Настраивается через фикстуру `settings`, а не @override_settings на классе:
    Django запрещает декорировать классы, не наследующие SimpleTestCase.
    """
    settings.ROOT_CATEGORY_NAME = None
    return settings


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


def cat_data(category: Category, parent: Category | None = None) -> CategoryData:
    """Формирует запись XML-выгрузки для существующей категории."""
    data: CategoryData = {"id": category.onec_id, "name": category.name, "description": ""}
    if parent is not None:
        data["parent_id"] = parent.onec_id
    return data


def deactivation_error_calls(mock_logger) -> list:
    """Отбирает вызовы logger.error, относящиеся к отмене деактивации.

    Проверка `call.args` обязательна: в модуле есть logger.error без позиционных
    аргументов, и безусловный доступ к args[0] уронил бы хелпер по IndexError.
    """
    return [
        call for call in mock_logger.error.call_args_list if call.args and "отменена для родителя" in str(call.args[0])
    ]


def small_branch_warning_calls(mock_logger) -> list:
    """Отбирает вызовы logger.warning про крупную потерю в малой ветке."""
    return [call for call in mock_logger.warning.call_args_list if call.args and "Малая ветка" in str(call.args[0])]


# ============================================================================
# Строки I/O-матрицы
# ============================================================================


def test_full_export_deactivates_only_category_removed_in_1c(processor, unanchored):
    """I/O-матрица «Полная выгрузка»: удалённая в 1С категория гаснет, прочие активны."""
    root = make_category()
    kept = make_children(root, 4)
    removed = make_category(parent=root)

    xml: list[CategoryData] = [cat_data(root)] + [cat_data(c, root) for c in kept]
    processor.process_categories(xml)
    processor.deactivate_obsolete_categories()

    removed.refresh_from_db()
    root.refresh_from_db()
    assert removed.is_active is False, "Удалённая в 1С категория должна погаснуть"
    assert root.is_active is True
    for child in kept:
        child.refresh_from_db()
        assert child.is_active is True, "Пришедшие в выгрузке категории должны остаться активными"


def test_partial_branch_leaves_unexpanded_parent_children_untouched(processor, unanchored):
    """I/O-матрица «Частичная ветка»: дети нераскрытого СПОРТа не тронуты, внутри ветки чистка идёт."""
    sport = make_category()
    martial = make_category(parent=sport)  # Единоборства
    sport_siblings = make_children(sport, 5)  # прочие дети СПОРТа, в выгрузку не попали

    protection = make_category(parent=martial)  # Защита
    martial_kept = make_children(martial, 5)
    martial_removed = make_category(parent=martial)

    helmets = make_category(parent=protection)  # Шлема
    protection_kept = make_children(protection, 3)
    protection_removed = make_category(parent=protection)

    # СПОРТ в этом файле без вложенных <Группы>; пришла цепочка Единоборства → Защита → Шлема
    xml: list[CategoryData] = [cat_data(martial)]
    xml += [cat_data(c, martial) for c in [protection] + martial_kept]
    xml += [cat_data(c, protection) for c in [helmets] + protection_kept]

    processor.process_categories(xml)
    processor.deactivate_obsolete_categories()

    sport.refresh_from_db()
    assert sport.is_active is True
    for sibling in sport_siblings:
        sibling.refresh_from_db()
        assert sibling.is_active is True, "Дети нераскрытого родителя не должны гаснуть"

    martial_removed.refresh_from_db()
    protection_removed.refresh_from_db()
    assert martial_removed.is_active is False, "Внутри раскрытой ветки не пришедшая категория гаснет"
    assert protection_removed.is_active is False

    for survivor in [martial, protection, helmets] + martial_kept + protection_kept:
        survivor.refresh_from_db()
        assert survivor.is_active is True


def test_whole_branch_exported_blocks_anchor_children_only_anchored_mode(processor, settings):
    """I/O-матрица «Ветка выгружена целиком» в anchored-режиме — сценарий прода.

    Под якорем 12 активных детей, в выгрузке пришёл один (Единоборства) → 11/12 = 92 %,
    предохранитель отменяет чистку детей якоря. Под Единоборствами пришли все 30 детей,
    один устарел → 1/31 = 3 %, чистка проходит штатно.
    """
    root_name = f"СПОРТ-{get_unique_suffix()}"
    settings.ROOT_CATEGORY_NAME = root_name

    anchor = make_category(name=root_name)
    martial = make_category(parent=anchor)
    anchor_siblings = make_children(anchor, 11)  # 12-й ребёнок якоря — martial

    martial_kept = make_children(martial, 30)
    martial_removed = make_category(parent=martial)

    xml: list[CategoryData] = [cat_data(anchor), cat_data(martial, anchor)]
    xml += [cat_data(c, martial) for c in martial_kept]

    processor.process_categories(xml)
    assert processor._category_filtering_active is True, "Тест обязан идти в anchored-режиме"

    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    for sibling in anchor_siblings:
        sibling.refresh_from_db()
        assert sibling.is_active is True, "Предохранитель обязан отменить гашение 11 из 12 детей якоря"

    martial_removed.refresh_from_db()
    assert martial_removed.is_active is False, "Под другим родителем чистка должна пройти штатно"
    for survivor in martial_kept:
        survivor.refresh_from_db()
        assert survivor.is_active is True

    errors = deactivation_error_calls(mock_logger)
    assert len(errors) == 1, "Ошибка предохранителя должна быть ровно одна — по якорю"
    args = errors[0].args
    assert args[1] == anchor.name, "Первый аргумент после шаблона — имя родителя"
    assert args[2] == anchor.onec_id, "Второй — onec_id родителя"
    assert args[3] == 11, "Третий — число кандидатов на деактивацию"
    assert args[4] == 12, "Четвёртый — число активных детей родителя"


def test_small_parent_deactivates_without_threshold(processor, unanchored):
    """I/O-матрица «Малый родитель»: 1 из 3 детей (33 %) гаснет, порог не применяется."""
    parent = make_category()
    kept = make_children(parent, 2)
    removed = make_category(parent=parent)

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]

    processor.process_categories(xml)
    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    removed.refresh_from_db()
    assert removed.is_active is False, "При < 4 активных детях порог не применяется"
    assert deactivation_error_calls(mock_logger) == [], "Лог не должен засоряться ошибками на малых родителях"


def test_no_valid_categories_returns_early(processor, unanchored):
    """I/O-матрица «Категорий нет»: пустое `_valid_category_onec_ids` → ранний return."""
    parent = make_category()
    make_children(parent, 5)
    active_before = Category.objects.filter(is_active=True).count()
    total_before = Category.objects.count()

    # Раскрытый родитель есть, а валидных категорий — нет
    processor._expanded_parent_onec_ids.add(parent.onec_id)
    assert processor._valid_category_onec_ids == set()

    processor.deactivate_obsolete_categories()

    assert Category.objects.filter(is_active=True).count() == active_before
    assert Category.objects.count() == total_before


def test_no_expanded_parents_returns_early(processor, unanchored):
    """I/O-матрица «Нет раскрытых родителей»: плоский список групп → ранний return."""
    parent = make_category()
    make_children(parent, 5)
    flat_roots = [make_category() for _ in range(3)]
    active_before = Category.objects.filter(is_active=True).count()
    total_before = Category.objects.count()

    xml: list[CategoryData] = [cat_data(c) for c in flat_roots]
    processor.process_categories(xml)

    assert processor._valid_category_onec_ids, "Плоские группы всё равно попадают в валидные"
    assert processor._expanded_parent_onec_ids == set(), "Без вложенности раскрытых родителей нет"

    processor.deactivate_obsolete_categories()

    assert Category.objects.filter(is_active=True).count() == active_before
    assert Category.objects.count() == total_before


# ============================================================================
# Граница порога, изоляция родителей, накопление множеств, наблюдаемость
# ============================================================================


def test_ratio_exactly_at_threshold_passes(processor, unanchored):
    """Ровно 30 % (3 из 10) — не «больше порога», деактивация проходит."""
    parent = make_category()
    kept = make_children(parent, 7)
    removed = make_children(parent, 3)

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]

    processor.process_categories(xml)
    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    for cat in removed:
        cat.refresh_from_db()
        assert cat.is_active is False, "Ровно 30 % не превышает порог — чистка должна пройти"
    assert deactivation_error_calls(mock_logger) == []


def test_ratio_above_threshold_blocks(processor, unanchored):
    """40 % (4 из 10) — порог превышен, деактивация отменяется."""
    parent = make_category()
    kept = make_children(parent, 6)
    doomed = make_children(parent, 4)

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]

    processor.process_categories(xml)
    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    for cat in doomed:
        cat.refresh_from_db()
        assert cat.is_active is True, "Превышение порога должно отменить деактивацию"

    errors = deactivation_error_calls(mock_logger)
    assert len(errors) == 1
    assert errors[0].args[1] == parent.name
    assert errors[0].args[2] == parent.onec_id
    assert errors[0].args[3] == 4
    assert errors[0].args[4] == 10


def test_threshold_isolated_per_parent(processor, unanchored):
    """Блокировка под одним родителем не мешает чистке под другим."""
    blocked_parent = make_category()
    blocked_kept = make_children(blocked_parent, 6)
    blocked_doomed = make_children(blocked_parent, 4)

    clean_parent = make_category()
    clean_kept = make_children(clean_parent, 9)
    clean_doomed = make_children(clean_parent, 1)

    xml: list[CategoryData] = [cat_data(blocked_parent), cat_data(clean_parent)]
    xml += [cat_data(c, blocked_parent) for c in blocked_kept]
    xml += [cat_data(c, clean_parent) for c in clean_kept]

    processor.process_categories(xml)
    processor.deactivate_obsolete_categories()

    for cat in blocked_doomed:
        cat.refresh_from_db()
        assert cat.is_active is True, "Дети заблокированного родителя не должны меняться"
    for cat in clean_doomed:
        cat.refresh_from_db()
        assert cat.is_active is False, "Под другим родителем чистка обязана пройти"


def test_sets_accumulate_between_groups_files(processor, unanchored):
    """Множества накапливаются между groups*.xml: один процессор — несколько файлов."""
    parent_one = make_category()
    kept_one = make_children(parent_one, 2)
    removed_one = make_category(parent=parent_one)

    parent_two = make_category()
    kept_two = make_children(parent_two, 2)
    removed_two = make_category(parent=parent_two)

    # groups1.xml
    processor.process_categories([cat_data(parent_one)] + [cat_data(c, parent_one) for c in kept_one])
    # groups2.xml
    processor.process_categories([cat_data(parent_two)] + [cat_data(c, parent_two) for c in kept_two])

    assert {parent_one.onec_id, parent_two.onec_id} <= processor._expanded_parent_onec_ids

    processor.deactivate_obsolete_categories()

    for cat in [removed_one, removed_two]:
        cat.refresh_from_db()
        assert cat.is_active is False, "Раскрытые родители обоих файлов должны быть в зоне чистки"
    for cat in kept_one + kept_two:
        cat.refresh_from_db()
        assert cat.is_active is True, "Валидные id из первого файла не должны теряться на втором"


def test_foreign_root_does_not_become_expanded(processor, settings):
    """Guard чужого корня: категория якоря, перевешенная в XML под чужой корень, не раскрывает его.

    Без guard чужой корень попал бы в `_expanded_parent_onec_ids`, и его собственные
    дети — ветка вне якоря — уехали бы в зону деактивации.
    """
    root_name = f"СПОРТ-{get_unique_suffix()}"
    settings.ROOT_CATEGORY_NAME = root_name

    anchor = make_category(name=root_name)
    anchor_child = make_category(parent=anchor)  # попадает в allowed через seed из БД

    foreign_root = make_category()
    foreign_children = make_children(foreign_root, 5)

    # В выгрузке ребёнок якоря ошибочно перевешен под чужой корень
    xml: list[CategoryData] = [
        cat_data(anchor),
        cat_data(foreign_root),
        cat_data(anchor_child, foreign_root),
    ]

    processor.process_categories(xml)
    assert processor._category_filtering_active is True

    assert foreign_root.onec_id not in processor._expanded_parent_onec_ids, "Чужой корень не должен считаться раскрытым"

    processor.deactivate_obsolete_categories()

    for child in foreign_children:
        child.refresh_from_db()
        assert child.is_active is True, "Дети чужого корня обязаны остаться нетронутыми"


def test_threshold_applies_at_exactly_min_children(processor, unanchored):
    """Граница MIN_CHILDREN_FOR_DEACTIVATION_RATIO: ровно 4 ребёнка — порог уже применяется.

    Дискриминирующий тест: при замене `>=` на `>` в проверке минимума родитель
    с 4 детьми потерял бы защиту и 2 категории погасли бы молча.
    """
    parent = make_category()
    kept = make_children(parent, 2)
    doomed = make_children(parent, 2)  # 2 из 4 = 50 % > 30 %

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]

    processor.process_categories(xml)
    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    for cat in doomed:
        cat.refresh_from_db()
        assert cat.is_active is True, "При ровно 4 активных детях порог обязан применяться"
    assert len(deactivation_error_calls(mock_logger)) == 1


def test_small_branch_majority_loss_is_logged(processor, unanchored):
    """Малая ветка теряет большинство детей: порог не применяется, но потеря фиксируется в логе."""
    parent = make_category()
    kept = make_children(parent, 1)
    doomed = make_children(parent, 2)  # 2 из 3 = 67 %, но детей < 4

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]

    processor.process_categories(xml)
    with patch("apps.products.services.variant_import.logger") as mock_logger:
        processor.deactivate_obsolete_categories()

    for cat in doomed:
        cat.refresh_from_db()
        assert cat.is_active is False, "Порог не применяется при < 4 детях — чистка проходит"

    warnings = small_branch_warning_calls(mock_logger)
    assert len(warnings) == 1, "Крупная потеря в малой ветке не должна проходить молча"
    assert warnings[0].args[2] == parent.onec_id
    assert warnings[0].args[3] == 2
    assert warnings[0].args[4] == 3


def test_skipped_deactivation_lands_in_session_report_and_details(processor, import_session, unanchored):
    """Отмена предохранителем видна в ImportSession.report и в report_details, а не только в файловом логе."""
    parent = make_category()
    kept = make_children(parent, 6)
    make_children(parent, 4)

    xml: list[CategoryData] = [cat_data(parent)] + [cat_data(c, parent) for c in kept]
    processor.process_categories(xml)

    processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

    assert processor.stats["categories_deactivation_skipped"] == 4

    import_session.refresh_from_db()
    assert "предохранитель" in import_session.report, "Факт отмены обязан попасть в ImportSession.report"
    assert import_session.report_details["categories_deactivation_skipped"] == 4

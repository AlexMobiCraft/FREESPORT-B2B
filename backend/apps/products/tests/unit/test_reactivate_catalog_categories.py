"""Тесты команды восстановления витрины каталога `reactivate_catalog_categories`.

Команда возвращает `is_active=True` якорю ROOT_CATEGORY_NAME и его потомкам после
массовой деактивации частичной выгрузкой 1С, не поднимая технические категории.
"""

from __future__ import annotations

import io
import uuid

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.products.models import Category

pytestmark = [pytest.mark.django_db, pytest.mark.unit]

# Глобальный счётчик для абсолютной уникальности тестовых данных
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс для тестов."""
    global _unique_counter
    _unique_counter += 1
    return f"{_unique_counter}_{uuid.uuid4().hex[:8]}"


def make_category(
    *,
    name: str | None = None,
    slug: str | None = None,
    parent: Category | None = None,
    is_active: bool = True,
) -> Category:
    """Создаёт категорию с уникальными name/slug/onec_id, если они не заданы явно."""
    suffix = get_unique_suffix()
    return Category.objects.create(
        name=name or f"Раздел витрины {suffix}",
        slug=slug or f"cat-{suffix}",
        onec_id=f"oid-{suffix}",
        parent=parent,
        is_active=is_active,
    )


@pytest.fixture
def root_name(settings) -> str:
    """Уникальное имя якоря, прописанное в settings.ROOT_CATEGORY_NAME."""
    name = f"СПОРТ-{get_unique_suffix()}"
    settings.ROOT_CATEGORY_NAME = name
    return name


def run(**options) -> str:
    """Запускает команду и возвращает её stdout."""
    out = io.StringIO()
    call_command("reactivate_catalog_categories", stdout=out, **options)
    return out.getvalue()


def test_dry_run_does_not_write(root_name):
    """DRY-RUN перечисляет кандидатов, но БД не меняет."""
    anchor = make_category(name=root_name, is_active=False)
    child = make_category(parent=anchor, is_active=False)

    output = run()

    anchor.refresh_from_db()
    child.refresh_from_db()
    assert "DRY-RUN" in output
    assert anchor.is_active is False, "DRY-RUN не должен активировать якорь"
    assert child.is_active is False, "DRY-RUN не должен активировать потомков"
    assert "reactivated=0" in output, "В dry-run фактических записей быть не должно"


def test_execute_reactivates_anchor_and_descendants(root_name):
    """Неактивный якорь активируется вместе с потомками — иначе дерево остаётся пустым."""
    anchor = make_category(name=root_name, is_active=False)
    branch = make_category(parent=anchor, is_active=False)
    leaf = make_category(parent=branch, is_active=False)
    already_active = make_category(parent=anchor, is_active=True)

    output = run(execute=True)

    for category in (anchor, branch, leaf, already_active):
        category.refresh_from_db()
        assert category.is_active is True

    assert "anchor_activated=1" in output, "Погашенный якорь обязан быть активирован"
    assert "reactivated=3" in output, "Активируются якорь и два неактивных потомка"


def test_execute_skips_technical_categories(root_name):
    """Placeholder, «Без категории» и технические slug на витрину не поднимаются."""
    anchor = make_category(name=root_name, is_active=False)
    useful = make_category(parent=anchor, is_active=False)
    # Имена и slug ниже — доменные константы контракта CategoryTreeViewSet, не тестовые данные.
    placeholder = make_category(name=f"Категория {uuid.uuid4()}", parent=anchor, is_active=False)
    no_category = make_category(name="Без категории", parent=anchor, is_active=False)
    uncategorized = make_category(slug="uncategorized", parent=anchor, is_active=False)
    unresolved = make_category(slug="onec-unresolved-category", parent=anchor, is_active=False)

    run(execute=True)

    anchor.refresh_from_db()
    useful.refresh_from_db()
    assert anchor.is_active is True
    assert useful.is_active is True

    for technical in (placeholder, no_category, uncategorized, unresolved):
        technical.refresh_from_db()
        assert technical.is_active is False, f"Техническая категория {technical.slug} не должна активироваться"


def test_execute_does_not_activate_orphan_under_technical_branch(root_name):
    """Потомок скрытой технической ветки остаётся неактивным — иначе он всплывёт в плоском /categories/."""
    anchor = make_category(name=root_name, is_active=False)
    technical = make_category(slug="uncategorized", parent=anchor, is_active=False)
    orphan = make_category(parent=technical, is_active=False)
    deep_orphan = make_category(parent=orphan, is_active=False)

    run(execute=True)

    anchor.refresh_from_db()
    technical.refresh_from_db()
    orphan.refresh_from_db()
    deep_orphan.refresh_from_db()

    assert anchor.is_active is True
    assert technical.is_active is False
    assert orphan.is_active is False, "Сирота под технической ветвью не должна активироваться"
    assert deep_orphan.is_active is False


def test_multiple_anchors_processed_with_warning(root_name):
    """Несколько якорей: union-семантика витрины + предупреждение оператору."""
    first = make_category(name=root_name, is_active=False)
    second = make_category(name=root_name, is_active=False)
    first_child = make_category(parent=first, is_active=False)
    second_child = make_category(parent=second, is_active=False)

    output = run(execute=True)

    for category in (first, second, first_child, second_child):
        category.refresh_from_db()
        assert category.is_active is True, "Обрабатываться должны все якоря, а не произвольный один"

    assert "WARNING" in output
    assert "anchors=2" in output


def test_cycle_in_tree_does_not_break_command(root_name):
    """Цикл в дереве (self-FK допускает) не должен ронять команду RecursionError."""
    anchor = make_category(name=root_name, is_active=False)
    child = make_category(parent=anchor, is_active=False)

    # Искусственная аномалия БД: две категории ссылаются друг на друга
    loop_a = make_category(is_active=False)
    loop_b = make_category(parent=loop_a, is_active=False)
    Category.objects.filter(pk=loop_a.pk).update(parent=loop_b)

    output = run(execute=True)

    anchor.refresh_from_db()
    child.refresh_from_db()
    loop_a.refresh_from_db()
    loop_b.refresh_from_db()

    assert anchor.is_active is True
    assert child.is_active is True
    assert loop_a.is_active is False, "Цикл вне ветки якоря активироваться не должен"
    assert loop_b.is_active is False
    assert "SUMMARY" in output


def test_second_run_is_idempotent(root_name):
    """Повторный запуск на восстановленном дереве не меняет ничего и завершается успешно."""
    anchor = make_category(name=root_name, is_active=False)
    child = make_category(parent=anchor, is_active=False)

    run(execute=True)
    output = run(execute=True)

    assert "reactivated=0" in output
    assert "anchor_activated=0" in output
    # Проверяем только созданные тестом категории: БД тестового контейнера собирается
    # миграциями, и посторонние неактивные записи (например, техническая категория
    # неразрешённых ссылок 1С) не должны ломать этот тест.
    assert (
        Category.objects.filter(pk__in=[anchor.pk, child.pk], is_active=False).count() == 0
    ), "Дерево якоря после повторного прогона обязано остаться активным"


def test_missing_anchor_raises_command_error(root_name):
    """Якоря нет в БД → CommandError."""
    make_category(is_active=False)

    with pytest.raises(CommandError, match="не найдена"):
        run(execute=True)


def test_empty_root_name_raises_configuration_command_error(settings):
    """Имя якоря не задано → CommandError про конфигурацию, а не про «категория не найдена»."""
    settings.ROOT_CATEGORY_NAME = None

    with pytest.raises(CommandError, match="конфигурации"):
        run(execute=True)

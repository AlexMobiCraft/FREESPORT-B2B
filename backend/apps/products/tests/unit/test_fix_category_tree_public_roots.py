"""Тесты repair-команды публичных root-категорий."""

from __future__ import annotations

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.products.factories import CategoryFactory, ProductFactory
from apps.products.models import Category, Product

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def test_fix_category_tree_execute_reparents_public_roots_and_isolates_placeholders():
    sport = CategoryFactory(name="СПОРТ", slug="sport-anchor", onec_id="sport-root", parent=None)
    useful_root = CategoryFactory(name="Футбол", slug="football-root", parent=None)
    useful_product = ProductFactory(category=useful_root, create_variant=False)
    placeholder = CategoryFactory(
        name="Категория 123e4567-e89b-12d3-a456-426614174000",
        slug="category-placeholder",
        parent=None,
        is_active=True,
    )
    placeholder_product = ProductFactory(category=placeholder, create_variant=False)

    out = io.StringIO()
    call_command("fix_category_tree_public_roots", execute=True, stdout=out)

    sport.refresh_from_db()
    useful_root.refresh_from_db()
    placeholder.refresh_from_db()
    useful_product.refresh_from_db()
    placeholder_product.refresh_from_db()
    fallback = Category.objects.get(slug="onec-unresolved-category")

    assert sport.parent is None
    assert useful_root.parent == sport
    assert useful_product.category == useful_root
    assert placeholder.parent == fallback
    assert placeholder.is_active is False
    assert placeholder_product.category == fallback
    assert Product.objects.filter(pk__in=[useful_product.pk, placeholder_product.pk]).count() == 2
    assert "products_moved_to_fallback=1" in out.getvalue()


def test_fix_category_tree_execute_restores_missing_sport_anchor_without_deleting_products():
    useful_root = CategoryFactory(name="Одежда", slug="clothes-root", parent=None)
    useful_product = ProductFactory(category=useful_root, create_variant=False)

    call_command("fix_category_tree_public_roots", execute=True, stdout=io.StringIO())

    sport = Category.objects.get(name="СПОРТ", parent=None)
    useful_root.refresh_from_db()
    useful_product.refresh_from_db()

    assert sport.slug == "sport"
    assert useful_root.parent == sport
    assert useful_product.category == useful_root


def test_fix_category_tree_execute_reactivates_inactive_sport_anchor():
    """Регрессия: repair реактивирует якорь СПОРТ (is_active=False → True); публичное дерево становится видимым."""
    sport = CategoryFactory(
        name="СПОРТ", slug="sport-inactive", onec_id="sport-inactive", parent=None, is_active=False
    )
    child = CategoryFactory(name="Теннис", slug="tennis-inactive-test", parent=None)

    out = io.StringIO()
    call_command("fix_category_tree_public_roots", execute=True, stdout=out)

    sport.refresh_from_db()
    child.refresh_from_db()

    assert sport.is_active is True, "Неактивный якорь СПОРТ должен быть реактивирован"
    assert child.parent == sport, "Публичные root должны быть перенесены под СПОРТ"
    assert "anchor=inactive" in out.getvalue(), "До исправления якорь должен быть отмечен как inactive"
    assert "public_reparented=1" in out.getvalue(), (
        "Дочерняя категория должна быть перенесена под реактивированный якорь"
    )


def test_fix_category_tree_multiple_anchors_raises_command_error():
    """Регрессия: при нескольких якорях СПОРТ команда завершается с ненулевым кодом (CommandError)."""
    CategoryFactory(name="СПОРТ", slug="sport-anchor-1", parent=None)
    CategoryFactory(name="СПОРТ", slug="sport-anchor-2", parent=None)

    with pytest.raises(CommandError, match="более одного корневого якоря"):
        call_command("fix_category_tree_public_roots", execute=True, stdout=io.StringIO())


def test_fix_category_tree_create_anchor_sets_sentinel_onec_id():
    """CR-3: repair-команда создаёт якорь с sentinel onec_id, чтобы импорт мог найти и обновить его."""
    from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID

    call_command("fix_category_tree_public_roots", execute=True, stdout=io.StringIO())

    anchor = Category.objects.get(name="СПОРТ", parent=None)
    assert anchor.onec_id == REPAIR_ANCHOR_ONEC_ID, (
        "Repair-якорь должен иметь sentinel onec_id для корректного слияния при следующем импорте"
    )


def test_fix_category_tree_dry_run_lists_affected_categories():
    """CR-4 Fix 6: DRY-RUN режим перечисляет затрагиваемые категории и товары."""
    sport = CategoryFactory(name="СПОРТ", slug="sport-dryrun", onec_id="sport-dryrun-root", parent=None)
    useful_root = CategoryFactory(name="Теннис", slug="tennis-dryrun", parent=None)
    placeholder = CategoryFactory(
        name="Категория 123e4567-e89b-12d3-a456-426614174002",
        slug="category-placeholder-dryrun",
        parent=None,
        is_active=True,
    )

    out = io.StringIO()
    call_command("fix_category_tree_public_roots", stdout=out)

    output = out.getvalue()
    assert "DRY-RUN" in output, "DRY-RUN метка должна присутствовать в выводе"
    assert "[placeholder]" in output, "Список placeholder-категорий должен быть выведен в dry-run"
    assert "[public_root]" in output, "Список публичных root-категорий должен быть выведен в dry-run"
    # Убеждаемся, что БД не изменена
    useful_root.refresh_from_db()
    assert useful_root.parent is None, "DRY-RUN не должен изменять БД"


def test_fix_category_tree_repair_no_cycle_when_fallback_inside_placeholder():
    """CR-4 Fix 2: repair не создаёт цикл, если fallback уже вложен внутри placeholder-поддерева."""
    placeholder = CategoryFactory(
        name="Категория 123e4567-e89b-12d3-a456-426614174003",
        slug="category-placeholder-cycle",
        parent=None,
        is_active=True,
    )
    # fallback-категория уже является дочерней placeholder-а (искусственная БД-аномалия)
    fallback_cat = CategoryFactory(
        name="Техническая категория: неразрешенные ссылки 1С",
        slug="onec-unresolved-category",
        parent=placeholder,
        is_active=False,
    )

    out = io.StringIO()
    # Должна выполниться без ошибок, без создания цикла
    call_command("fix_category_tree_public_roots", execute=True, stdout=out)

    placeholder.refresh_from_db()
    fallback_cat.refresh_from_db()
    # Fallback не становится parent для самого placeholder
    assert placeholder.parent != fallback_cat, "Repair не должен создавать цикл placeholder -> fallback -> placeholder"
    # Placeholder деактивирован
    assert placeholder.is_active is False


def test_fix_category_tree_cycle_guard_moves_products_to_fallback():
    """CR-5 #1: при fallback внутри placeholder-поддерева товары всё равно переносятся в fallback,
    а fallback отвязывается от placeholder-родителя, чтобы не оставаться в скрытой ветке."""
    placeholder = CategoryFactory(
        name="Категория 123e4567-e89b-12d3-a456-426614174777",
        slug="category-placeholder-cycle-products",
        parent=None,
        is_active=True,
    )
    # fallback искусственно вложен внутрь placeholder-поддерева (старая аномалия БД)
    fallback_cat = CategoryFactory(
        name="Техническая категория: неразрешенные ссылки 1С",
        slug="onec-unresolved-category",
        parent=placeholder,
        is_active=False,
    )
    # Товар лежит в самом placeholder, не в fallback
    placeholder_product = ProductFactory(category=placeholder, create_variant=False)

    out = io.StringIO()
    call_command("fix_category_tree_public_roots", execute=True, stdout=out)

    placeholder.refresh_from_db()
    fallback_cat.refresh_from_db()
    placeholder_product.refresh_from_db()

    assert placeholder_product.category_id == fallback_cat.pk, (
        "Товар из placeholder должен быть перенесён в fallback даже при cycle guard"
    )
    assert fallback_cat.parent_id is None, (
        "Fallback должен быть отвязан от placeholder-родителя, чтобы не остаться в скрытой ветке"
    )
    assert placeholder.is_active is False, "Placeholder должен быть деактивирован"
    assert "products_moved_to_fallback=1" in out.getvalue(), (
        "В отчёте должен быть учтён 1 перенесённый товар"
    )


def test_fix_category_tree_dry_run_lists_products_in_placeholder_branches():
    """CR-5 #4: DRY-RUN перечисляет конкретные товары из placeholder-веток (Task 4.2)."""
    CategoryFactory(name="СПОРТ", slug="sport-dryrun-products", onec_id="sport-dr-products", parent=None)
    placeholder = CategoryFactory(
        name="Категория 123e4567-e89b-12d3-a456-426614174888",
        slug="category-placeholder-dryrun-products",
        parent=None,
        is_active=True,
    )
    p1 = ProductFactory(category=placeholder, create_variant=False)
    p2 = ProductFactory(category=placeholder, create_variant=False)

    out = io.StringIO()
    call_command("fix_category_tree_public_roots", stdout=out)
    output = out.getvalue()

    assert "[product]" in output, "DRY-RUN должен помечать товары префиксом [product]"
    assert f"id={p1.pk}" in output, "Конкретный товар p1 должен присутствовать в DRY-RUN отчёте"
    assert f"id={p2.pk}" in output, "Конкретный товар p2 должен присутствовать в DRY-RUN отчёте"


def test_fix_category_tree_legacy_placeholder_isolated_by_broad_regex():
    """CR-3: legacy placeholder с не-UUID именем (длинный hex-ID) изолируется, а не переносится под СПОРТ."""
    sport = CategoryFactory(name="СПОРТ", slug="sport-cr3", onec_id="sport-cr3-root", parent=None)
    legacy = CategoryFactory(
        name="Категория 1a2b3c4d5e6f",  # 12 hex-char суффикс, не стандартный UUID
        slug="category-legacy-hex",
        parent=None,
        is_active=True,
    )

    call_command("fix_category_tree_public_roots", execute=True, stdout=io.StringIO())

    legacy.refresh_from_db()
    fallback = Category.objects.get(slug="onec-unresolved-category")

    assert legacy.parent == fallback, "Legacy hex-ID placeholder должен быть изолирован под fallback"
    assert legacy.is_active is False, "Legacy placeholder должен быть деактивирован"
    assert legacy.parent != sport, "Legacy placeholder не должен быть перемещён под СПОРТ как публичная категория"

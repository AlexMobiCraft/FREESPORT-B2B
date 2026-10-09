"""
Импорт 1С записывает в БД только товары дерева «СПОРТ» без пометки удаления.

Интеграционный прогон команды `import_products_from_1c` и связки
«импорт → purge_products_outside_root» (спецификация
`spec-1c-deletion-marked-goods`).

Данные — реальные выгрузки 1С:

* сценарии AC идут на подмножестве снимка 21.09.2026 (`data_dependent`);
* сценарии, которых в снимке нет (помеченная группа внутри СПОРТ, возврат в
  СПОРТ, несколько групп, порядок пакетов), — на копии закоммиченного среза с
  точечной правкой текста.
"""

from __future__ import annotations

import shutil
from decimal import Decimal
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from django.core.management import call_command
from django.urls import reverse

from apps.orders.models import OrderItem
from apps.products.models import Category, ImportSession, OnecExcludedItem, Product, ProductVariant
from apps.products.services.onec_admission import (
    KIND_GROUP,
    KIND_OFFER,
    KIND_PRODUCT,
    REASON_GROUP_MARKED,
    REASON_OUTSIDE_TREE,
    REASON_PRODUCT_MARKED,
    REASON_UNKNOWN_GROUP,
)
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor
from tests.conftest import BrandFactory, OrderFactory, UserFactory
from tests.onec_corpus import (
    BT45_BLUE_ID,
    BT45_RED_ID,
    FIXTURE_GOODS_XML,
    FIXTURE_GROUPS_XML,
    FIXTURE_PRODUCT_GROUP_ID,
    FIXTURE_PRODUCT_ID,
    FIXTURE_SPORT_ROOT_ID,
    MOVED_TO_TRASH_ID,
    SNAPSHOT_SPORT_ROOT_ID,
    edit_copy,
    make_exchange_dir,
    mark_deleted,
    require_snapshot,
    snapshot_files,
    stage_snapshot,
)

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

FALLBACK_CATEGORY_SLUGS = ("onec-unresolved-category", "uncategorized")


# ============================================================================
# Helpers
# ============================================================================


def _run_import(data_dir: Path, file_type: str = "all") -> tuple[ImportSession, str]:
    """Прогон команды импорта; возвращает сессию прогона и вывод команды."""
    out = StringIO()
    call_command(
        "import_products_from_1c",
        data_dir=str(data_dir),
        file_type=file_type,
        skip_backup=True,
        skip_images=True,
        stdout=out,
        stderr=StringIO(),
    )
    session = ImportSession.objects.order_by("-pk").first()
    assert session is not None
    return session, out.getvalue()


def _purge(**options: Any) -> str:
    out = StringIO()
    call_command("purge_products_outside_root", stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


def _subtree_pks(anchor: Category) -> set[int]:
    """pk якоря и всех его потомков по связям `Category.parent` в БД."""
    children: dict[int | None, list[int]] = {}
    for pk, parent_id in Category.objects.values_list("pk", "parent_id"):
        children.setdefault(parent_id, []).append(pk)
    result: set[int] = set()
    stack = [anchor.pk]
    while stack:
        pk = stack.pop()
        if pk in result:
            continue
        result.add(pk)
        stack.extend(children.get(pk, []))
    return result


def _assert_nothing_outside_sport() -> set[int]:
    """В БД нет ни категорий, ни товаров вне поддерева якоря «СПОРТ»."""
    anchor = Category.objects.get(name="СПОРТ", parent__isnull=True)
    subtree = _subtree_pks(anchor)
    assert set(Category.objects.values_list("pk", flat=True)) == subtree, "Есть категории вне поддерева СПОРТ"
    assert not Product.objects.exclude(category_id__in=subtree).exists(), "Есть товары вне поддерева СПОРТ"
    assert not Category.objects.filter(slug__in=FALLBACK_CATEGORY_SLUGS).exists()
    return subtree


# ============================================================================
# Независимый оракул правила допуска по реальному снимку
# ============================================================================


def _snapshot_oracle() -> SimpleNamespace:
    """Ожидаемый исход импорта подмножества снимка в пустую БД.

    Правило допуска здесь пересчитано заново и намеренно наивно — по тексту ТЗ,
    без кода импорта: пакеты в порядке номеров, побеждает поздний.
    """
    require_snapshot()
    parser = XMLDataParser()
    groups = parser.parse_groups_xml(str(snapshot_files("groups")[0]))
    parent = {group["id"]: group.get("parent_id", "") for group in groups}

    def in_sport(group_id: str) -> bool:
        seen: set[str] = set()
        while group_id and group_id not in seen:
            if group_id == SNAPSHOT_SPORT_ROOT_ID:
                return True
            if group_id not in parent:
                return False
            seen.add(group_id)
            group_id = parent[group_id]
        return False

    existing: set[str] = set()
    hidden: set[str] = set()
    last: dict[str, bool] = {}
    counters = {"skipped_products": 0, "hidden_products": 0, "restored_products": 0}

    for path in snapshot_files("goods"):
        for item in parser.parse_goods_xml(str(path)):
            group_ids = item["category_ids"]
            admitted = not item["is_deleted"] and bool(group_ids) and all(in_sport(g) for g in group_ids)
            last[item["id"]] = admitted
            if admitted:
                if item["id"] in hidden:
                    hidden.discard(item["id"])
                    counters["restored_products"] += 1
                existing.add(item["id"])
            elif item["id"] not in existing:
                counters["skipped_products"] += 1
            elif item["id"] not in hidden:
                hidden.add(item["id"])
                counters["hidden_products"] += 1

    visible = existing - hidden
    excluded = set(last) - visible

    offers = {"created": 0, "skipped_variants": 0, "missing_parent": 0}
    offers_by_parent: dict[str, list[bool]] = {}
    marked_offer_ids: set[str] = set()
    for path in snapshot_files("offers"):
        for offer in parser.parse_offers_xml(str(path)):
            parent_id = offer["id"].split("#", 1)[0]
            if parent_id in excluded:
                offers["skipped_variants"] += 1
            elif parent_id not in visible:
                offers["missing_parent"] += 1
            elif offer["is_deleted"]:
                offers["skipped_variants"] += 1
                marked_offer_ids.add(offer["id"])
                offers_by_parent.setdefault(parent_id, []).append(True)
            else:
                offers["created"] += 1
                offers_by_parent.setdefault(parent_id, []).append(False)

    return SimpleNamespace(
        sport_groups={group_id for group_id in parent if in_sport(group_id)},
        other_groups={group_id for group_id in parent if not in_sport(group_id)},
        visible=visible,
        hidden=hidden,
        excluded=excluded,
        counters=counters,
        offers=offers,
        marked_offer_ids=marked_offer_ids,
        all_offers_marked={pid for pid, marks in offers_by_parent.items() if all(marks)},
        without_offers=visible - set(offers_by_parent),
        last=last,
        parent=parent,
        in_sport=in_sport,
    )


# ============================================================================
# AC на реальном снимке
# ============================================================================


@pytest.mark.data_dependent
class TestSnapshotImportIntoEmptyDb:
    """AC1: подмножество снимка в пустую БД — ничего вне СПОРТ, BT45-RU нет.

    Импорт подмножества (2 000 товаров, 2 000 предложений) идёт полминуты,
    поэтому прогон один, а проверки разнесены по методам `_check_*`.
    """

    @pytest.fixture
    def imported(self, tmp_path) -> SimpleNamespace:
        data_dir = stage_snapshot(tmp_path / "exchange")
        oracle = _snapshot_oracle()
        session, output = _run_import(data_dir)
        return SimpleNamespace(session=session, output=output, oracle=oracle)

    def test_only_sport_tree_without_deletion_marks_reaches_db(self, imported, tmp_path):
        self._check_products_and_categories(imported)
        self._check_offers(imported)
        self._check_session_report(imported)
        self._check_second_import_changes_nothing(tmp_path)

    def _check_products_and_categories(self, imported):
        oracle = imported.oracle
        session = imported.session
        assert session.status == ImportSession.ImportStatus.COMPLETED

        # --- Категории: только поддерево СПОРТ, запасных нет
        _assert_nothing_outside_sport()
        assert set(Category.objects.values_list("onec_id", flat=True)) == oracle.sport_groups
        assert len(oracle.sport_groups) == 121
        assert Category.objects.filter(parent__isnull=True).count() == 1

        # --- Товары: созданы только допущенные; переехавшие «к удалению» скрыты
        products = dict(Product.objects.values_list("onec_id", "onec_deleted"))
        assert set(products) == oracle.visible | oracle.hidden
        assert {onec_id for onec_id, deleted in products.items() if deleted} == oracle.hidden
        assert not Product.objects.filter(onec_deleted=True, is_active=True).exists()
        assert oracle.visible, "В подмножестве обязаны быть допущенные товары СПОРТ"

        # --- BT45-RU (папка «Номенклатура к удалению» + пометка удаления) в БД нет
        assert not Product.objects.filter(onec_id__in=[BT45_RED_ID, BT45_BLUE_ID]).exists()
        assert not Product.objects.filter(article__istartswith="BT45-Ru").exists()
        registry = {item.onec_id: (item.kind, item.reason) for item in OnecExcludedItem.objects.all()}
        assert registry[BT45_RED_ID] == (KIND_PRODUCT, REASON_PRODUCT_MARKED)
        assert registry[BT45_BLUE_ID] == (KIND_PRODUCT, REASON_PRODUCT_MARKED)

        # --- Порядок пакетов: товар из goods_1_1 (СПОРТ) и goods_1_11 («к удалению»)
        moved = Product.objects.get(onec_id=MOVED_TO_TRASH_ID)
        assert moved.onec_deleted is True and moved.is_active is False
        assert registry[MOVED_TO_TRASH_ID] == (KIND_PRODUCT, REASON_OUTSIDE_TREE)

        # --- Реестр: все исключённые товары и все группы вне СПОРТ
        assert {i for i, (kind, _) in registry.items() if kind == KIND_PRODUCT} == oracle.excluded
        assert {i for i, (kind, _) in registry.items() if kind == KIND_GROUP} == oracle.other_groups
        reasons = {reason for kind, reason in registry.values() if kind == KIND_PRODUCT}
        assert {REASON_OUTSIDE_TREE, REASON_PRODUCT_MARKED, REASON_UNKNOWN_GROUP, "нет группы"} <= reasons

    def _check_offers(self, imported):
        """Предложения следуют допуску товара; помеченные не создаются."""
        oracle = imported.oracle
        details = imported.session.report_details

        # Варианты есть только у допущенных товаров; помеченных предложений нет
        assert not ProductVariant.objects.exclude(product__onec_id__in=oracle.visible).exists()
        assert not ProductVariant.objects.filter(onec_id__in=oracle.marked_offer_ids).exists()
        assert oracle.marked_offer_ids, "В подмножестве обязаны быть помеченные предложения товаров СПОРТ"
        registry_offers = set(OnecExcludedItem.objects.filter(kind=KIND_OFFER).values_list("onec_id", flat=True))
        assert registry_offers == oracle.marked_offer_ids

        assert details["variants_created"] == oracle.offers["created"]
        assert details["skipped_variants"] == oracle.offers["skipped_variants"]
        # WARNING «parent Product not found» остался только для настоящих пропаж
        assert details["skipped"] == oracle.offers["missing_parent"]
        assert details["hidden_variants"] == 0

        # Товар, все предложения которого помечены: вариантов нет, дефолтный не создан
        assert oracle.all_offers_marked, "В подмножестве обязан быть товар со всеми помеченными предложениями"
        for product in Product.objects.filter(onec_id__in=oracle.all_offers_marked):
            assert product.is_active is False
            assert product.onec_deleted is False
            assert not product.variants.exists()
        # Товар без характеристик в выгрузке получает дефолтный вариант
        assert details["default_variants_created"] == len(oracle.without_offers)
        assert (
            not Product.objects.filter(onec_deleted=True, variants__isnull=False)
            .exclude(onec_id__in=oracle.hidden)
            .exists()
        )

    def _check_session_report(self, imported):
        """Счётчики — в report_details, итоговая строка — в report и в выводе команды."""
        oracle = imported.oracle
        session = imported.session
        details = session.report_details

        for key, expected in oracle.counters.items():
            assert details[key] == expected, key
        assert details["recategorized_products"] == 0
        assert details["restored_variants"] == 0
        assert details["products_created"] == len(oracle.visible | oracle.hidden)

        summary = (
            f"Вне СПОРТ / к удалению: не создано {oracle.counters['skipped_products']} товаров / "
            f"{oracle.offers['skipped_variants']} вариантов, скрыто {oracle.counters['hidden_products']} / 0, "
            f"возвращено {oracle.counters['restored_products']} / 0, перенесено в категорию группы 0"
        )
        assert summary in session.report
        # Строка пишется после шага товаров — до шага предложений счётчик вариантов ещё нулевой
        assert f"не создано {oracle.counters['skipped_products']} товаров / 0 вариантов" in session.report
        assert "ВНЕ ДЕРЕВА ЯКОРЯ / К УДАЛЕНИЮ" in imported.output
        assert summary in imported.output

    def _check_second_import_changes_nothing(self, tmp_path):
        """Повторный прогон той же выгрузки: реестр и скрытое не трогаются."""
        before = {
            "products": sorted(Product.objects.values_list("onec_id", "is_active", "onec_deleted", "category_id")),
            "variants": sorted(ProductVariant.objects.values_list("onec_id", "is_active", "onec_deleted")),
            "registry": sorted(OnecExcludedItem.objects.values_list("onec_id", "kind", "reason")),
            "categories": sorted(Category.objects.values_list("onec_id", "parent__onec_id", "is_active")),
        }

        session, _ = _run_import(stage_snapshot(tmp_path / "exchange-2"))

        after = {
            "products": sorted(Product.objects.values_list("onec_id", "is_active", "onec_deleted", "category_id")),
            "variants": sorted(ProductVariant.objects.values_list("onec_id", "is_active", "onec_deleted")),
            "registry": sorted(OnecExcludedItem.objects.values_list("onec_id", "kind", "reason")),
            "categories": sorted(Category.objects.values_list("onec_id", "parent__onec_id", "is_active")),
        }
        assert after == before
        details = session.report_details
        assert details["products_created"] == 0
        assert details["variants_created"] == 0


@pytest.mark.data_dependent
class TestSnapshotImportThenPurge:
    """AC2: БД с товарами СПОРТ, вне СПОРТ, «к удалению», с заказом → импорт → purge --apply."""

    @pytest.fixture
    def world(self) -> SimpleNamespace:
        oracle = _snapshot_oracle()
        parser = XMLDataParser()
        goods = {}
        for path in snapshot_files("goods"):
            goods.update({item["id"]: dict(item) for item in parser.parse_goods_xml(str(path))})

        def root_id_of(item: dict) -> str | None:
            """Ид корневой группы товара или None, если группы нет либо она неизвестна."""
            groups = item["category_ids"]
            if not groups or groups[0] not in oracle.parent:
                return None
            group_id = groups[0]
            while oracle.parent[group_id]:
                group_id = oracle.parent[group_id]
            return str(group_id)

        special_root_id = next(
            group_id
            for group_id, parent_id in oracle.parent.items()
            if not parent_id and group_id in oracle.other_groups
        )
        special_id = next(
            onec_id
            for onec_id in sorted(oracle.excluded - oracle.hidden)
            if root_id_of(goods[onec_id]) == special_root_id and not goods[onec_id]["is_deleted"]
        )
        ordered_id = next(
            onec_id
            for onec_id in sorted(oracle.excluded - oracle.hidden, reverse=True)
            if onec_id not in (special_id, BT45_RED_ID, BT45_BLUE_ID) and goods[onec_id]["category_ids"]
        )
        sport_id = next(onec_id for onec_id in sorted(oracle.visible) if onec_id not in oracle.all_offers_marked)
        sport_group_id = goods[sport_id]["category_ids"][0]

        brand = BrandFactory.create()
        # Дерево до импорта: якорь и одна настоящая группа СПОРТ (связь с родителем
        # намеренно упрощена — импорт выправит её по groups.xml)
        sport = Category.objects.create(name="СПОРТ", slug="ac2-sport", onec_id=SNAPSHOT_SPORT_ROOT_ID)
        sport_child = Category.objects.create(
            name="Группа СПОРТ", slug="ac2-child", onec_id=sport_group_id, parent=sport
        )
        # Категории вне дерева, оставшиеся от прежних импортов
        special_root = Category.objects.create(name="для спецзаказов", slug="ac2-special", onec_id=special_root_id)
        placeholder = Category.objects.create(
            name="Категория 11111111-2222-3333-4444-555555555555", slug="ac2-placeholder", onec_id="ac2-placeholder"
        )
        fallback = Category.objects.create(
            name="Техническая категория: неразрешенные ссылки 1С",
            slug="onec-unresolved-category",
            onec_id="__onec_unresolved_category__",
            is_active=False,
        )

        def make(onec_id: str, category: Category, slug: str, variants: int = 1) -> Product:
            product = Product.objects.create(
                name=goods.get(onec_id, {}).get("name") or f"Товар {slug}",
                slug=slug,
                onec_id=onec_id,
                parent_onec_id=onec_id,
                brand=brand,
                category=category,
                description="",
                is_active=True,
            )
            for index in range(variants):
                ProductVariant.objects.create(
                    product=product,
                    sku=f"AC2-{slug}-{index}",
                    onec_id=f"{onec_id}#ac2-{index}",
                    retail_price=Decimal("500"),
                    stock_quantity=4,
                    is_active=True,
                )
            return product

        world = SimpleNamespace(
            oracle=oracle,
            sport=sport,
            special_root=special_root,
            placeholder=placeholder,
            fallback=fallback,
            # Товар СПОРТ — не тронут
            sport_product=make(sport_id, sport_child, "ac2-sport-product"),
            # Вне СПОРТ (спецзаказ) с остатком, категория вне дерева
            special_product=make(special_id, special_root, "ac2-special-product"),
            # «К удалению», но числится в категории СПОРТ — как BT45-RU на проде
            bt45=make(BT45_RED_ID, sport_child, "ac2-bt45", variants=2),
            # Недопущенный товар с заказом
            ordered=make(ordered_id, fallback, "ac2-ordered"),
            # Нет в выгрузке, категория вне дерева — импорт его не увидит
            absent_outside=make("ac2-absent-outside", placeholder, "ac2-absent-outside"),
            # Нет в выгрузке, категория в дереве СПОРТ — остаётся
            absent_in_sport=make("ac2-absent-in-sport", sport_child, "ac2-absent-in-sport"),
        )
        order = OrderFactory.create(user=UserFactory.create())
        world.order_item = OrderItem.objects.create(
            order=order,
            product=world.ordered,
            variant=world.ordered.variants.first(),
            quantity=2,
            unit_price=Decimal("500"),
            total_price=Decimal("1000"),
            product_name=world.ordered.name,
            product_sku="AC2-ordered-0",
        )
        return world

    def test_import_hides_then_purge_deletes_everything_not_admitted(self, world, tmp_path, api_client):
        session, _ = _run_import(stage_snapshot(tmp_path / "exchange"))
        assert session.status == ImportSession.ImportStatus.COMPLETED

        # ---- После импорта: недопущенное скрыто, ничего не удалено
        for name in ("special_product", "bt45", "ordered"):
            product = getattr(world, name)
            product.refresh_from_db()
            assert product.is_active is False, name
            assert product.onec_deleted is True, name
            # Скрытие товара варианты не трогает
            assert product.variants.filter(is_active=True, onec_deleted=False, stock_quantity=4).count() >= 1, name
        for name in ("sport_product", "absent_outside", "absent_in_sport"):
            product = getattr(world, name)
            product.refresh_from_db()
            assert product.is_active is True, name
            assert product.onec_deleted is False, name
        assert Product.objects.filter(pk=world.bt45.pk).exists(), "обмен ничего не удаляет физически"
        details = session.report_details
        assert details["hidden_products"] == world.oracle.counters["hidden_products"] + 3

        deleted_slugs = [world.special_product.slug, world.bt45.slug, world.absent_outside.slug]
        bt45_variants = list(world.bt45.variants.values_list("pk", flat=True))

        # ---- Dry-run ничего не меняет
        products_before = Product.objects.count()
        assert "БД не изменена" in _purge()
        assert Product.objects.count() == products_before

        # ---- purge --apply
        output = _purge(apply=True)
        assert "ошибок 0" in output

        # Удалено всё недопущенное без заказов
        assert not Product.objects.filter(slug__in=deleted_slugs).exists()
        assert not ProductVariant.objects.filter(pk__in=bt45_variants).exists()
        # Товар с заказом скрыт, заказ цел
        world.ordered.refresh_from_db()
        world.order_item.refresh_from_db()
        assert world.ordered.is_active is False and world.ordered.onec_deleted is True
        assert world.order_item.product_id == world.ordered.pk
        assert world.order_item.variant_id is not None
        assert set(Product.objects.filter(onec_deleted=True).values_list("pk", flat=True)) == {world.ordered.pk}
        # Товары СПОРТ не тронуты
        for name in ("sport_product", "absent_in_sport"):
            product = getattr(world, name)
            product.refresh_from_db()
            assert product.is_active is True and product.onec_deleted is False, name
        assert set(Product.objects.filter(onec_deleted=False).values_list("onec_id", flat=True)) == (
            world.oracle.visible | {"ac2-absent-in-sport"}
        )

        # Категории вне дерева удалены; осталась только ветка с защищённым товаром
        subtree = _subtree_pks(Category.objects.get(name="СПОРТ", parent__isnull=True))
        outside = Category.objects.exclude(pk__in=subtree)
        assert set(outside.values_list("pk", flat=True)) == {world.fallback.pk}
        assert set(Product.objects.exclude(category_id__in=subtree).values_list("pk", flat=True)) == {world.ordered.pk}
        assert len(subtree) == 121

        # Удалённый товар не отдаётся публичным API
        for slug in (*deleted_slugs, world.ordered.slug):
            assert api_client.get(reverse("products:product-detail", kwargs={"slug": slug})).status_code == 404, slug
        detail = api_client.get(reverse("products:product-detail", kwargs={"slug": world.sport_product.slug}))
        assert detail.status_code == 200
        listed: set[str] = set()
        url: str | None = reverse("products:product-list") + "?page_size=100"
        while url:
            page = api_client.get(url)
            assert page.status_code == 200
            listed.update(item["slug"] for item in page.data["results"])
            url = page.data.get("next")
        assert world.sport_product.slug in listed
        assert listed.isdisjoint({*deleted_slugs, world.ordered.slug})

        # Предложения удалённого товара следующая сессия пропускает молча — Ид в реестре
        assert OnecExcludedItem.objects.filter(onec_id=BT45_RED_ID, kind=KIND_PRODUCT).exists()
        assert OnecExcludedItem.objects.filter(onec_id="ac2-absent-outside", kind=KIND_PRODUCT).exists()


# ============================================================================
# Сценарии на копии закоммиченного среза (идут в CI без приватных данных)
# ============================================================================


def _stage_fixture(
    base: Path, *, groups: Path | None = FIXTURE_GROUPS_XML, goods: Path | None = FIXTURE_GOODS_XML
) -> Path:
    """Каталог обмена из закоммиченного среза реальной выгрузки (копии файлов)."""
    make_exchange_dir(base)
    if groups is not None:
        shutil.copyfile(groups, base / "groups" / "groups.xml")
    if goods is not None:
        shutil.copyfile(goods, base / "goods" / "goods.xml")
    return base


class TestFixtureCorpusScenarios:
    def test_real_goods_of_sport_tree_are_imported(self, tmp_path):
        session, _ = _run_import(_stage_fixture(tmp_path / "x"), file_type="goods")

        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert Product.objects.count() == 3
        _assert_nothing_outside_sport()
        assert OnecExcludedItem.objects.count() == 0
        assert session.report_details["skipped_products"] == 0
        assert "к удалению" not in session.report

    def test_goods_session_without_groups_xml_uses_tree_from_db(self, tmp_path):
        """На проде groups и goods — разные сессии: поддерево якоря берётся из БД."""
        _run_import(_stage_fixture(tmp_path / "groups-session", goods=None), file_type="goods")
        assert Product.objects.count() == 0
        categories_before = Category.objects.count()

        session, _ = _run_import(_stage_fixture(tmp_path / "goods-session", groups=None), file_type="goods")

        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert Product.objects.count() == 3
        assert Category.objects.count() == categories_before
        _assert_nothing_outside_sport()

    def test_anchor_not_found_creates_and_hides_nothing(self, tmp_path):
        """Дельта товаров в БД без дерева: якоря нет — сессия ничего не создаёт."""
        session, _ = _run_import(_stage_fixture(tmp_path / "x", groups=None), file_type="goods")

        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert Product.objects.count() == 0
        assert Category.objects.count() == 0
        assert OnecExcludedItem.objects.count() == 0
        assert "ROOT_CATEGORY_NAME='СПОРТ' не найден ни в XML, ни в БД" in session.report
        assert session.report_details["skipped_products"] == 3
        assert session.report_details["hidden_products"] == 0

    def test_marked_group_inside_sport_hides_its_products(self, tmp_path):
        """Помеченная группа внутри СПОРТ исключает себя, потомков и их товары."""
        _run_import(_stage_fixture(tmp_path / "first"), file_type="goods")
        product = Product.objects.get(onec_id=FIXTURE_PRODUCT_ID)
        assert product.onec_deleted is False
        parent_group_id = Category.objects.get(onec_id=FIXTURE_PRODUCT_GROUP_ID).parent.onec_id
        assert parent_group_id != FIXTURE_SPORT_ROOT_ID, "Нужен предок между группой товара и якорем"

        marked_groups = edit_copy(
            FIXTURE_GROUPS_XML, tmp_path / "groups-marked.xml", lambda text: mark_deleted(text, parent_group_id)
        )
        session, _ = _run_import(_stage_fixture(tmp_path / "second", groups=marked_groups), file_type="goods")

        product.refresh_from_db()
        assert product.is_active is False
        assert product.onec_deleted is True
        registry = {item.onec_id: (item.kind, item.reason) for item in OnecExcludedItem.objects.all()}
        assert registry[FIXTURE_PRODUCT_ID] == (KIND_PRODUCT, REASON_GROUP_MARKED)
        assert registry[parent_group_id] == (KIND_GROUP, REASON_GROUP_MARKED)
        assert registry[FIXTURE_PRODUCT_GROUP_ID] == (KIND_GROUP, REASON_GROUP_MARKED)
        assert session.report_details["hidden_products"] >= 1
        assert "Вне СПОРТ / к удалению" in session.report

        # Следующая сессия — только товары, без groups.xml: группа остаётся исключённой по реестру
        session, _ = _run_import(_stage_fixture(tmp_path / "third", groups=None), file_type="goods")
        product.refresh_from_db()
        assert product.onec_deleted is True
        assert session.report_details["hidden_products"] == 0

    def test_product_returns_to_sport(self, tmp_path):
        """Товар вынесли из СПОРТ, затем вернули: скрытое импортом возвращается."""
        _run_import(_stage_fixture(tmp_path / "first"), file_type="goods")
        product = Product.objects.get(onec_id=FIXTURE_PRODUCT_ID)
        variant = ProductVariant.objects.create(
            product=product, sku="RETURN-SKU", onec_id=f"{FIXTURE_PRODUCT_ID}#v", retail_price=Decimal("10")
        )
        Product.objects.filter(pk=product.pk).update(is_active=True)

        moved_out = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods-moved.xml",
            lambda text: text.replace(f"<Ид>{FIXTURE_PRODUCT_GROUP_ID}</Ид>", "<Ид>group-outside-sport</Ид>", 1),
        )
        session, _ = _run_import(_stage_fixture(tmp_path / "second", groups=None, goods=moved_out), file_type="goods")
        product.refresh_from_db()
        assert (product.is_active, product.onec_deleted) == (False, True)
        assert OnecExcludedItem.objects.get(onec_id=FIXTURE_PRODUCT_ID).reason == REASON_UNKNOWN_GROUP
        assert session.report_details["hidden_products"] == 1

        session, _ = _run_import(_stage_fixture(tmp_path / "third", groups=None), file_type="goods")

        product.refresh_from_db()
        variant.refresh_from_db()
        assert (product.is_active, product.onec_deleted) == (True, False)
        assert variant.is_active is True
        assert not OnecExcludedItem.objects.filter(onec_id=FIXTURE_PRODUCT_ID).exists()
        assert session.report_details["restored_products"] == 1
        assert "возвращено 1 / 0" in session.report

    def test_all_groups_of_product_must_be_in_subtree(self, tmp_path):
        first_group = f"<Ид>{FIXTURE_PRODUCT_GROUP_ID}</Ид>"
        both_inside = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods-two-inside.xml",
            lambda text: text.replace(first_group, f"{first_group}<Ид>{FIXTURE_SPORT_ROOT_ID}</Ид>", 1),
        )
        one_outside = edit_copy(
            FIXTURE_GOODS_XML,
            tmp_path / "goods-one-outside.xml",
            lambda text: text.replace(first_group, f"{first_group}<Ид>group-outside-sport</Ид>", 1),
        )

        _run_import(_stage_fixture(tmp_path / "outside", goods=one_outside), file_type="goods")
        assert not Product.objects.filter(onec_id=FIXTURE_PRODUCT_ID).exists()
        assert Product.objects.count() == 2
        assert OnecExcludedItem.objects.get(onec_id=FIXTURE_PRODUCT_ID).kind == KIND_PRODUCT

        _run_import(_stage_fixture(tmp_path / "inside", goods=both_inside), file_type="goods")
        product = Product.objects.get(onec_id=FIXTURE_PRODUCT_ID)
        assert product.category.onec_id == FIXTURE_PRODUCT_GROUP_ID
        assert not OnecExcludedItem.objects.filter(onec_id=FIXTURE_PRODUCT_ID).exists()
        _assert_nothing_outside_sport()

    @pytest.mark.parametrize(
        ("early_marked", "expected_hidden"),
        [(True, False), (False, True)],
        ids=["late-packet-admits", "late-packet-rejects"],
    )
    def test_later_packet_wins_in_natural_order(self, tmp_path, early_marked, expected_hidden):
        """goods_1_2 идёт раньше goods_1_10: лексикографический порядок дал бы обратный исход."""
        base = _stage_fixture(tmp_path / "x", goods=None)
        marked = edit_copy(
            FIXTURE_GOODS_XML, tmp_path / "goods-marked.xml", lambda text: mark_deleted(text, FIXTURE_PRODUCT_ID)
        )
        early, late = (marked, FIXTURE_GOODS_XML) if early_marked else (FIXTURE_GOODS_XML, marked)
        shutil.copyfile(early, base / "goods" / "goods_1_2_aaaa.xml")
        shutil.copyfile(late, base / "goods" / "goods_1_10_bbbb.xml")

        session, output = _run_import(base, file_type="goods")

        assert output.index("goods_1_2_aaaa.xml") < output.index("goods_1_10_bbbb.xml")
        if expected_hidden:
            product = Product.objects.get(onec_id=FIXTURE_PRODUCT_ID)
            assert (product.is_active, product.onec_deleted) == (False, True)
            assert session.report_details["hidden_products"] == 1
        else:
            product = Product.objects.get(onec_id=FIXTURE_PRODUCT_ID)
            assert product.onec_deleted is False
            assert not OnecExcludedItem.objects.filter(onec_id=FIXTURE_PRODUCT_ID).exists()
            assert session.report_details["skipped_products"] == 1
            assert session.report_details["hidden_products"] == 0

    def test_marked_offer_registry_survives_between_sessions(self, tmp_path):
        """Сессия offers помечает предложение; следующая сессия prices/rests пропускает его молча."""
        _run_import(_stage_fixture(tmp_path / "first"), file_type="goods")
        offer_id = f"{FIXTURE_PRODUCT_ID}#marked-characteristic"
        OnecExcludedItem.objects.create(onec_id=offer_id, kind=KIND_OFFER, reason="пометка предложения")

        processor = VariantImportProcessor(session_id=ImportSession.objects.create().pk)
        assert processor.update_variant_stock({"id": offer_id, "warehouse_id": "w", "quantity": 1}) is False
        assert processor.create_default_variants() == 2

        assert processor.stats["skipped_variants"] == 1
        assert processor.stats["warnings"] == 0
        assert not ProductVariant.objects.filter(product__onec_id=FIXTURE_PRODUCT_ID).exists()

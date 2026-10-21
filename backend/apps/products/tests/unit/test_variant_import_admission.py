"""
Правило допуска импорта 1С: в БД только товары дерева якоря без пометки удаления.

Покрывает I/O-матрицу спецификации `spec-1c-deletion-marked-goods`:
недопущенное не создаётся, существующее скрывается (`onec_deleted=True`) и
заносится в реестр исключённых Ид; обмен ничего не удаляет физически.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from types import SimpleNamespace
from typing import Any

import pytest

from apps.products.models import Brand, Category, ImportSession, OnecExcludedItem, PriceType, Product, ProductVariant
from apps.products.services.onec_admission import (
    KIND_GROUP,
    KIND_OFFER,
    KIND_PRODUCT,
    REASON_GROUP_MARKED,
    REASON_NO_GROUP,
    REASON_OFFER_MARKED,
    REASON_OUTSIDE_TREE,
    REASON_PRODUCT_MARKED,
    REASON_UNKNOWN_GROUP,
)
from apps.products.services.variant_import import CategoryData, VariantImportProcessor

pytestmark = [pytest.mark.django_db, pytest.mark.unit]

FALLBACK_CATEGORY_SLUGS = ("onec-unresolved-category", "uncategorized")


# ============================================================================
# Fixtures
# ============================================================================


def _new_processor() -> VariantImportProcessor:
    """Новый процессор = новая сессия обмена (каждый файл 1С — отдельная сессия)."""
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.IN_PROGRESS,
    )
    return VariantImportProcessor(session_id=session.pk)


@pytest.fixture
def processor() -> VariantImportProcessor:
    return _new_processor()


@pytest.fixture
def tree(settings: Any) -> SimpleNamespace:
    """Дерево БД: СПОРТ → Единоборства → Перчатки, СПОРТ → Футбол; чужой корень."""
    settings.ROOT_CATEGORY_NAME = "СПОРТ"
    sport = Category.objects.create(name="СПОРТ", slug="adm-sport", onec_id="grp-sport")
    combat = Category.objects.create(name="Единоборства", slug="adm-combat", onec_id="grp-combat", parent=sport)
    gloves = Category.objects.create(name="Перчатки", slug="adm-gloves", onec_id="grp-gloves", parent=combat)
    football = Category.objects.create(name="Футбол", slug="adm-football", onec_id="grp-football", parent=sport)
    trash = Category.objects.create(name="Номенклатура к удалению", slug="adm-trash", onec_id="grp-trash")
    brand = Brand.objects.create(name="Adm Brand", slug="adm-brand")
    return SimpleNamespace(sport=sport, combat=combat, gloves=gloves, football=football, trash=trash, brand=brand)


def _goods(onec_id: str, groups: list[str] | None = None, **extra: Any) -> dict[str, Any]:
    """Данные товара в том виде, в каком их отдаёт XMLDataParser.parse_goods_xml."""
    group_ids = list(groups or [])
    data: dict[str, Any] = {
        "id": onec_id,
        "name": f"Товар {onec_id}",
        "article": f"ART-{onec_id}",
        "description": "",
        "category_ids": group_ids,
        "is_deleted": False,
    }
    if group_ids:
        data["category_id"] = group_ids[0]
    data.update(extra)
    return data


def _offer(onec_id: str, **extra: Any) -> dict[str, Any]:
    data: dict[str, Any] = {"id": onec_id, "name": f"Предложение {onec_id}", "article": "", "is_deleted": False}
    data.update(extra)
    return data


def _xml_groups(**overrides: CategoryData) -> list[CategoryData]:
    """Дерево групп в том виде, в каком его отдаёт XMLDataParser.parse_groups_xml."""
    groups: dict[str, CategoryData] = {
        "grp-sport": {"id": "grp-sport", "name": "СПОРТ", "is_deleted": False},
        "grp-combat": {"id": "grp-combat", "name": "Единоборства", "parent_id": "grp-sport", "is_deleted": False},
        "grp-gloves": {"id": "grp-gloves", "name": "Перчатки", "parent_id": "grp-combat", "is_deleted": False},
        "grp-football": {"id": "grp-football", "name": "Футбол", "parent_id": "grp-sport", "is_deleted": False},
        "grp-trash": {"id": "grp-trash", "name": "Номенклатура к удалению", "is_deleted": False},
    }
    for group_id, patch in overrides.items():
        groups[group_id.replace("_", "-")].update(patch)
    return list(groups.values())


def _make_product(tree: SimpleNamespace, onec_id: str, category: Category | None = None, **extra: Any) -> Product:
    fields: dict[str, Any] = {
        "name": f"Товар {onec_id}",
        "slug": f"adm-{onec_id}",
        "onec_id": onec_id,
        "parent_onec_id": onec_id,
        "article": f"ART-{onec_id}",
        "brand": tree.brand,
        "category": category or tree.gloves,
        "description": "",
        "is_active": True,
    }
    fields.update(extra)
    return Product.objects.create(**fields)


def _make_variant(product: Product, onec_id: str, **extra: Any) -> ProductVariant:
    fields: dict[str, Any] = {
        "product": product,
        "sku": f"SKU-{onec_id}",
        "onec_id": onec_id,
        "retail_price": Decimal("100"),
        "stock_quantity": 5,
        "is_active": True,
    }
    fields.update(extra)
    return ProductVariant.objects.create(**fields)


def _registry(onec_id: str) -> tuple[str, str] | None:
    item = OnecExcludedItem.objects.filter(onec_id=onec_id).first()
    return (item.kind, item.reason) if item else None


# ============================================================================
# Недопущенный товар, которого нет в БД
# ============================================================================


class TestNewProductNotAdmitted:
    @pytest.mark.parametrize(
        ("goods_kwargs", "reason"),
        [
            ({"groups": ["grp-trash"]}, REASON_OUTSIDE_TREE),
            ({"groups": []}, REASON_NO_GROUP),
            ({"groups": ["grp-never-seen"]}, REASON_UNKNOWN_GROUP),
            ({"groups": ["grp-gloves"], "is_deleted": True}, REASON_PRODUCT_MARKED),
            ({"groups": ["grp-gloves", "grp-trash"]}, REASON_OUTSIDE_TREE),
        ],
        ids=["outside-tree", "no-group", "unknown-group", "product-marked", "one-of-groups-outside"],
    )
    def test_is_not_created_in_session_without_groups_xml(self, processor, tree, goods_kwargs, reason):
        """Дельта без groups.xml: поддерево якоря собирается из БД."""
        result = processor.process_product_from_goods(_goods("new-1", **goods_kwargs), skip_images=True)

        assert result is None
        assert not Product.objects.filter(onec_id="new-1").exists()
        assert _registry("new-1") == (KIND_PRODUCT, reason)
        assert processor.stats["skipped_products"] == 1
        assert processor.stats["products_created"] == 0
        assert processor.stats["hidden_products"] == 0

    def test_is_not_created_when_ancestor_group_is_marked(self, processor, tree):
        """Ни одна группа на пути до якоря не должна быть помечена на удаление."""
        processor.process_categories(_xml_groups(grp_combat={"is_deleted": True}))

        result = processor.process_product_from_goods(_goods("new-2", ["grp-gloves"]), skip_images=True)

        assert result is None
        assert not Product.objects.filter(onec_id="new-2").exists()
        assert _registry("new-2") == (KIND_PRODUCT, REASON_GROUP_MARKED)

    def test_admitted_product_is_created_in_its_group_category(self, processor, tree):
        product = processor.process_product_from_goods(_goods("new-3", ["grp-gloves"]), skip_images=True)

        assert product is not None
        assert product.category == tree.gloves
        assert product.onec_deleted is False
        assert _registry("new-3") is None
        assert processor.stats["products_created"] == 1
        assert processor.stats["skipped_products"] == 0

    def test_old_format_goods_without_category_ids_still_work(self, processor, tree):
        """`category_id` без `category_ids` — формат до появления списка групп."""
        product = processor.process_product_from_goods(
            {"id": "new-4", "name": "Старый формат", "category_id": "grp-football"}, skip_images=True
        )

        assert product is not None
        assert product.category == tree.football

    @pytest.mark.parametrize("groups", [[], ["grp-never-seen"], ["grp-trash"]], ids=["no-group", "unknown", "outside"])
    def test_no_category_is_created_outside_anchor_subtree(self, processor, tree, groups):
        """Ни один путь импорта не создаёт Category вне поддерева якоря."""
        before = set(Category.objects.values_list("pk", flat=True))

        processor.process_product_from_goods(_goods("new-5", groups), skip_images=True)

        assert set(Category.objects.values_list("pk", flat=True)) == before
        assert not Category.objects.filter(slug__in=FALLBACK_CATEGORY_SLUGS).exists()

    def test_readmitted_product_is_created_and_leaves_registry(self, tree):
        """Товар перенесли в 1С в ветку СПОРТ — при очередном обмене он создаётся как новый."""
        _new_processor().process_product_from_goods(_goods("new-6", ["grp-trash"]), skip_images=True)
        assert _registry("new-6") is not None

        product = _new_processor().process_product_from_goods(_goods("new-6", ["grp-gloves"]), skip_images=True)

        assert product is not None
        assert _registry("new-6") is None


# ============================================================================
# Недопущенный товар, который уже есть в БД
# ============================================================================


class TestExistingProductNotAdmitted:
    def test_is_hidden_and_registered_variants_untouched(self, processor, tree):
        """Товар с остатком в категории СПОРТ, переехавший в 1С «к удалению»."""
        product = _make_product(tree, "exist-1")
        variant = _make_variant(product, "exist-1#v1", stock_quantity=7)

        result = processor.process_product_from_goods(_goods("exist-1", ["grp-trash"]), skip_images=True)

        assert result is None
        product.refresh_from_db()
        variant.refresh_from_db()
        assert product.is_active is False
        assert product.onec_deleted is True
        assert Product.objects.filter(pk=product.pk).exists(), "обмен ничего не удаляет физически"
        # Скрытие товара варианты не трогает: возврат не должен включать варианты,
        # скрытые их собственной пометкой.
        assert variant.is_active is True
        assert variant.onec_deleted is False
        assert variant.stock_quantity == 7
        assert _registry("exist-1") == (KIND_PRODUCT, REASON_OUTSIDE_TREE)
        assert processor.stats["hidden_products"] == 1
        assert processor.stats["skipped_products"] == 0
        assert processor.stats["products_updated"] == 0

    def test_all_matches_by_onec_id_and_parent_onec_id_are_hidden(self, processor, tree):
        """`parent_onec_id` не уникален — скрываются все совпадения, а не первое."""
        by_onec_id = _make_product(tree, "exist-2")
        by_parent = _make_product(tree, "exist-2#legacy", parent_onec_id="exist-2")

        processor.process_product_from_goods(
            _goods("exist-2", is_deleted=True, groups=["grp-gloves"]), skip_images=True
        )

        for product in (by_onec_id, by_parent):
            product.refresh_from_db()
            assert product.is_active is False
            assert product.onec_deleted is True
        assert processor.stats["hidden_products"] == 2

    def test_already_hidden_product_is_not_counted_again(self, tree):
        product = _make_product(tree, "exist-3")
        _new_processor().process_product_from_goods(_goods("exist-3", ["grp-trash"]), skip_images=True)

        second = _new_processor()
        second.process_product_from_goods(_goods("exist-3", ["grp-trash"]), skip_images=True)

        product.refresh_from_db()
        assert product.onec_deleted is True
        assert second.stats["hidden_products"] == 0
        assert second.stats["skipped_products"] == 0

    def test_hidden_product_is_logged_with_id_article_name_and_reason(self, processor, tree, caplog):
        """По построчному логу позицию находят в 1С."""
        _make_product(tree, "exist-4", name="Трико борцовское", article="BT45-RU")

        with caplog.at_level(logging.INFO, logger="import_products"):
            processor.process_product_from_goods(_goods("exist-4", ["grp-gloves"], is_deleted=True), skip_images=True)

        lines = [record.getMessage() for record in caplog.records if "Товар скрыт импортом 1С" in record.getMessage()]
        assert len(lines) == 1
        assert "exist-4" in lines[0]
        assert "BT45-RU" in lines[0]
        assert "Трико борцовское" in lines[0]
        assert REASON_PRODUCT_MARKED in lines[0]


# ============================================================================
# Возврат и ручное выключение
# ============================================================================


class TestProductReturn:
    def test_hidden_product_with_active_variant_is_restored(self, processor, tree):
        product = _make_product(tree, "back-1", is_active=False, onec_deleted=True)
        _make_variant(product, "back-1#v1")
        OnecExcludedItem.objects.create(onec_id="back-1", kind=KIND_PRODUCT, reason=REASON_OUTSIDE_TREE)

        result = processor.process_product_from_goods(_goods("back-1", ["grp-gloves"]), skip_images=True)

        assert result is not None
        product.refresh_from_db()
        assert product.onec_deleted is False
        assert product.is_active is True
        assert _registry("back-1") is None
        assert processor.stats["restored_products"] == 1
        assert processor.stats["products_updated"] == 1

    def test_hidden_product_without_active_variant_stays_inactive(self, processor, tree):
        product = _make_product(tree, "back-2", is_active=False, onec_deleted=True)
        _make_variant(product, "back-2#v1", is_active=False, onec_deleted=True)

        processor.process_product_from_goods(_goods("back-2", ["grp-gloves"]), skip_images=True)

        product.refresh_from_db()
        assert product.onec_deleted is False
        assert product.is_active is False
        assert processor.stats["restored_products"] == 1

    def test_manually_disabled_product_is_not_enabled(self, processor, tree):
        """`is_active=False` без `onec_deleted` — выключено руками в админке."""
        product = _make_product(tree, "back-3", is_active=False, onec_deleted=False)
        _make_variant(product, "back-3#v1")

        processor.process_product_from_goods(_goods("back-3", ["grp-gloves"]), skip_images=True)

        product.refresh_from_db()
        assert product.is_active is False
        assert product.onec_deleted is False
        assert processor.stats["restored_products"] == 0


class TestRecategorization:
    def test_admitted_product_outside_subtree_moves_to_its_group_category(self, processor, tree):
        product = _make_product(tree, "cat-1", category=tree.trash)

        processor.process_product_from_goods(_goods("cat-1", ["grp-football"]), skip_images=True)

        product.refresh_from_db()
        assert product.category == tree.football
        assert processor.stats["recategorized_products"] == 1

    def test_category_inside_subtree_is_not_synced(self, processor, tree):
        """Полная синхронизация категорий вне объёма: товар уже в поддереве — не трогаем."""
        product = _make_product(tree, "cat-2", category=tree.gloves)

        processor.process_product_from_goods(_goods("cat-2", ["grp-football"]), skip_images=True)

        product.refresh_from_db()
        assert product.category == tree.gloves
        assert processor.stats["recategorized_products"] == 0

    def test_product_in_anchor_without_onec_id_is_not_moved(self, processor, settings):
        """Якорь без Ид 1С остаётся якорем: его товар лежит в поддереве."""
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        sport = Category.objects.create(name="СПОРТ", slug="adm-sport-bare")
        child = Category.objects.create(name="Бокс", slug="adm-boxing", onec_id="grp-boxing", parent=sport)
        brand = Brand.objects.create(name="Bare Brand", slug="adm-bare-brand")
        product = Product.objects.create(
            name="В якоре", slug="adm-in-anchor", onec_id="cat-3", brand=brand, category=sport, description=""
        )

        result = processor.process_product_from_goods(_goods("cat-3", ["grp-boxing"]), skip_images=True)

        assert result is not None
        product.refresh_from_db()
        assert product.category == sport
        assert child.pk != sport.pk
        assert processor.stats["recategorized_products"] == 0


# ============================================================================
# Предложения
# ============================================================================


class TestMarkedOffer:
    def test_new_variant_is_not_created(self, processor, tree):
        product = _make_product(tree, "off-1", is_active=False)

        result = processor.process_variant_from_offer(_offer("off-1#v1", is_deleted=True), skip_images=True)

        assert result is None
        assert not ProductVariant.objects.filter(onec_id="off-1#v1").exists()
        assert _registry("off-1#v1") == (KIND_OFFER, REASON_OFFER_MARKED)
        assert processor.stats["skipped_variants"] == 1
        product.refresh_from_db()
        assert product.onec_deleted is False

    def test_existing_variant_is_hidden_others_stay_active(self, processor, tree, caplog):
        product = _make_product(tree, "off-2")
        marked = _make_variant(product, "off-2#v1")
        other = _make_variant(product, "off-2#v2")

        with caplog.at_level(logging.INFO, logger="import_products"):
            processor.process_variant_from_offer(_offer("off-2#v1", is_deleted=True), skip_images=True)

        marked.refresh_from_db()
        other.refresh_from_db()
        product.refresh_from_db()
        assert marked.is_active is False
        assert marked.onec_deleted is True
        assert other.is_active is True
        assert other.onec_deleted is False
        assert product.is_active is True
        assert _registry("off-2#v1") == (KIND_OFFER, REASON_OFFER_MARKED)
        assert processor.stats["hidden_variants"] == 1
        lines = [r.getMessage() for r in caplog.records if "Вариант скрыт импортом 1С" in r.getMessage()]
        assert len(lines) == 1
        assert "off-2#v1" in lines[0] and "SKU-off-2#v1" in lines[0] and REASON_OFFER_MARKED in lines[0]

    def test_repeated_mark_is_not_counted_again(self, tree):
        product = _make_product(tree, "off-3")
        _make_variant(product, "off-3#v1")
        _make_variant(product, "off-3#v2")
        _new_processor().process_variant_from_offer(_offer("off-3#v1", is_deleted=True), skip_images=True)

        second = _new_processor()
        second.process_variant_from_offer(_offer("off-3#v1", is_deleted=True), skip_images=True)

        assert second.stats["hidden_variants"] == 0
        assert second.stats["skipped_variants"] == 0

    def test_all_offers_marked_deactivates_product_without_flag(self, processor, tree):
        product = _make_product(tree, "off-4")
        _make_variant(product, "off-4#v1")
        _make_variant(product, "off-4#v2")

        processor.process_variant_from_offer(_offer("off-4#v1", is_deleted=True), skip_images=True)
        processor.process_variant_from_offer(_offer("off-4#v2", is_deleted=True), skip_images=True)

        product.refresh_from_db()
        assert product.is_active is False
        # Сам товар в 1С допущен — флаг «скрыт импортом» он не получает.
        assert product.onec_deleted is False

    def test_no_default_variant_for_product_whose_offers_are_all_marked(self, processor, tree):
        """«Все предложения помечены» отличается от «характеристик нет» по реестру."""
        marked = _make_product(tree, "off-5", is_active=False)
        plain = _make_product(tree, "off-6", is_active=False)
        processor.process_variant_from_offer(_offer("off-5#v1", is_deleted=True), skip_images=True)

        created = processor.create_default_variants()

        assert created == 1
        assert not ProductVariant.objects.filter(product=marked).exists()
        assert ProductVariant.objects.filter(product=plain, onec_id="off-6").exists()
        marked.refresh_from_db()
        plain.refresh_from_db()
        assert marked.is_active is False
        assert plain.is_active is True

    def test_marked_plain_offer_blocks_default_variant(self, processor, tree):
        """У товара без характеристик Ид предложения совпадает с Ид товара."""
        product = _make_product(tree, "off-7", is_active=False)
        processor.process_variant_from_offer(_offer("off-7", is_deleted=True), skip_images=True)

        assert processor.create_default_variants() == 0
        assert not ProductVariant.objects.filter(product=product).exists()

    def test_unmarked_offer_restores_variant_and_parent(self, tree):
        product = _make_product(tree, "off-8")
        variant = _make_variant(product, "off-8#v1")
        _new_processor().process_variant_from_offer(_offer("off-8#v1", is_deleted=True), skip_images=True)
        # Свежая выборка, а не refresh_from_db(): иначе mypy сузит product.is_active до False
        # и сочтёт недостижимым всё после `assert product.is_active is True` ниже.
        assert Product.objects.get(pk=product.pk).is_active is False

        second = _new_processor()
        result = second.process_variant_from_offer(_offer("off-8#v1"), skip_images=True)

        assert result is not None
        variant.refresh_from_db()
        product.refresh_from_db()
        assert variant.is_active is True
        assert variant.onec_deleted is False
        assert product.is_active is True
        assert _registry("off-8#v1") is None
        assert second.stats["restored_variants"] == 1


class TestOffersOfExcludedProduct:
    def test_offer_of_product_rejected_in_this_session_is_skipped_silently(self, processor, tree, caplog):
        processor.process_product_from_goods(_goods("ex-1", ["grp-trash"]), skip_images=True)

        with caplog.at_level(logging.WARNING, logger="import_products"):
            result = processor.process_variant_from_offer(_offer("ex-1#v1"), skip_images=True)

        assert result is None
        assert processor.stats["skipped_variants"] == 1
        assert processor.stats["skipped"] == 0
        assert not any("parent Product not found" in r.getMessage() for r in caplog.records)

    def test_offer_of_product_from_registry_is_skipped_silently(self, tree, caplog):
        """Сессия offers приходит отдельно от goods — решение берётся из реестра."""
        _new_processor().process_product_from_goods(_goods("ex-2", ["grp-trash"]), skip_images=True)

        offers_session = _new_processor()
        with caplog.at_level(logging.WARNING, logger="import_products"):
            result = offers_session.process_variant_from_offer(_offer("ex-2#v1"), skip_images=True)

        assert result is None
        assert offers_session.stats["skipped_variants"] == 1
        assert not any("parent Product not found" in r.getMessage() for r in caplog.records)

    def test_offer_of_hidden_product_does_not_touch_its_variants(self, processor, tree):
        product = _make_product(tree, "ex-3", is_active=False, onec_deleted=True)
        variant = _make_variant(product, "ex-3#v1", is_active=False)

        assert processor.process_variant_from_offer(_offer("ex-3#v1"), skip_images=True) is None
        assert processor.process_variant_from_offer(_offer("ex-3#v2"), skip_images=True) is None

        variant.refresh_from_db()
        product.refresh_from_db()
        assert variant.is_active is False
        assert product.is_active is False
        assert not ProductVariant.objects.filter(onec_id="ex-3#v2").exists()
        assert processor.stats["skipped_variants"] == 2

    def test_truly_missing_parent_still_warns(self, processor, tree, caplog):
        """WARNING остаётся для настоящих пропаж."""
        with caplog.at_level(logging.WARNING, logger="import_products"):
            processor.process_variant_from_offer(_offer("ghost#v1"), skip_images=True)

        assert any("parent Product not found" in r.getMessage() for r in caplog.records)
        assert processor.stats["skipped"] == 1
        assert processor.stats["skipped_variants"] == 0


class TestPricesAndStocksOfExcluded:
    @pytest.fixture
    def price_type(self) -> PriceType:
        return PriceType.objects.create(
            onec_id="pt-retail", onec_name="Розничная", product_field="retail_price", is_active=True
        )

    def _price(self, onec_id: str) -> dict[str, Any]:
        return {"id": onec_id, "prices": [{"price_type_id": "pt-retail", "value": Decimal("777")}]}

    def _rest(self, onec_id: str) -> dict[str, Any]:
        return {"id": onec_id, "warehouse_id": "wh-1", "quantity": 9}

    def test_excluded_offer_is_skipped_without_warning(self, processor, tree, price_type, caplog):
        _make_product(tree, "pr-1", is_active=False)
        processor.process_variant_from_offer(_offer("pr-1#v1", is_deleted=True), skip_images=True)
        processor.process_product_from_goods(_goods("pr-2", ["grp-trash"]), skip_images=True)
        before = processor.stats["skipped_variants"]

        with caplog.at_level(logging.WARNING, logger="import_products"):
            assert processor.update_variant_prices(self._price("pr-1#v1")) is False
            assert processor.update_variant_stock(self._rest("pr-1#v1")) is False
            assert processor.update_variant_prices(self._price("pr-2#v1")) is False
            assert processor.update_variant_stock(self._rest("pr-2")) is False

        assert processor.stats["skipped_variants"] == before + 4
        assert processor.stats["warnings"] == 0
        assert not any("ProductVariant not found" in r.getMessage() for r in caplog.records)

    def test_truly_missing_variant_still_warns(self, processor, tree, price_type, caplog):
        with caplog.at_level(logging.WARNING, logger="import_products"):
            assert processor.update_variant_prices(self._price("ghost#v1")) is False
            assert processor.update_variant_stock(self._rest("ghost#v2")) is False

        messages = [r.getMessage() for r in caplog.records]
        assert any("ProductVariant not found for price update" in m for m in messages)
        assert any("ProductVariant not found for stock update" in m for m in messages)
        assert processor.stats["warnings"] == 2
        assert processor.stats["skipped_variants"] == 0

    def test_excluded_offer_is_cut_before_parent_fallback(self, processor, tree, price_type):
        """Цена помеченной характеристики не должна лечь на дефолтный вариант товара."""
        product = _make_product(tree, "pr-3")
        default_variant = _make_variant(product, "pr-3", retail_price=Decimal("100"))
        processor.process_variant_from_offer(_offer("pr-3#v1", is_deleted=True), skip_images=True)

        assert processor.update_variant_prices(self._price("pr-3#v1")) is False
        assert processor.update_variant_stock(self._rest("pr-3#v1")) is False

        default_variant.refresh_from_db()
        assert default_variant.retail_price == Decimal("100")
        assert default_variant.stock_quantity == 5

    def test_parent_fallback_still_works_for_admitted_offer(self, processor, tree, price_type):
        product = _make_product(tree, "pr-4")
        default_variant = _make_variant(product, "pr-4", retail_price=Decimal("100"))

        assert processor.update_variant_prices(self._price("pr-4#v1")) is True

        default_variant.refresh_from_db()
        assert default_variant.retail_price == Decimal("777")

    def test_hidden_variant_gets_prices_and_stock_but_stays_hidden(self, processor, tree, price_type):
        """Цены и остатки активность не трогают — скрытому варианту они обновляются."""
        product = _make_product(tree, "pr-5")
        hidden = _make_variant(product, "pr-5#v1", is_active=False, onec_deleted=True, stock_quantity=0)
        _make_variant(product, "pr-5#v2")
        OnecExcludedItem.objects.create(onec_id="pr-5#v1", kind=KIND_OFFER, reason=REASON_OFFER_MARKED)

        assert processor.update_variant_prices(self._price("pr-5#v1")) is True
        assert processor.update_variant_stock(self._rest("pr-5#v1")) is True

        hidden.refresh_from_db()
        assert hidden.retail_price == Decimal("777")
        assert hidden.stock_quantity == 9
        assert hidden.is_active is False
        assert hidden.onec_deleted is True


# ============================================================================
# Пути повторной активации закрыты
# ============================================================================


class TestReactivationPathsClosed:
    def test_update_existing_variant_does_not_activate_hidden_variant(self, processor, tree):
        product = _make_product(tree, "re-1")
        hidden = _make_variant(product, "re-1#v1", is_active=False, onec_deleted=True)

        processor._update_existing_variant(hidden, _offer("re-1#v1"), None, True)

        hidden.refresh_from_db()
        assert hidden.is_active is False
        assert hidden.onec_deleted is True

    def test_update_existing_variant_still_activates_plain_inactive_variant(self, processor, tree):
        product = _make_product(tree, "re-2")
        inactive = _make_variant(product, "re-2#v1", is_active=False)

        processor._update_existing_variant(inactive, _offer("re-2#v1"), None, True)

        inactive.refresh_from_db()
        assert inactive.is_active is True

    def test_create_new_variant_does_not_activate_hidden_product(self, processor, tree):
        product = _make_product(tree, "re-3", is_active=False, onec_deleted=True)

        variant = processor._create_new_variant(product, "re-3#v1", _offer("re-3#v1"), None, True)

        assert variant is not None
        product.refresh_from_db()
        assert product.is_active is False
        assert product.onec_deleted is True

    def test_create_new_variant_activates_fresh_product(self, processor, tree):
        product = _make_product(tree, "re-4", is_active=False)

        processor._create_new_variant(product, "re-4#v1", _offer("re-4#v1"), None, True)

        product.refresh_from_db()
        assert product.is_active is True

    def test_create_default_variants_skips_hidden_products(self, processor, tree):
        hidden = _make_product(tree, "re-5", is_active=False, onec_deleted=True)

        assert processor.create_default_variants() == 0

        hidden.refresh_from_db()
        assert hidden.is_active is False
        assert not ProductVariant.objects.filter(product=hidden).exists()


# ============================================================================
# Якорь не найден / фильтр отключён
# ============================================================================


class TestAnchorNotFound:
    def test_nothing_is_created_or_hidden(self, processor, settings, caplog):
        """Сбой определения якоря не должен скрыть каталог."""
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        category = Category.objects.create(name="Осиротевшая", slug="adm-orphan", onec_id="grp-orphan")
        brand = Brand.objects.create(name="Orphan Brand", slug="adm-orphan-brand")
        existing = Product.objects.create(
            name="Старое имя",
            slug="adm-orphan-product",
            onec_id="anc-1",
            brand=brand,
            category=category,
            description="",
        )

        with caplog.at_level(logging.ERROR, logger="import_products"):
            updated = processor.process_product_from_goods(
                _goods("anc-1", ["grp-orphan"], name="Новое имя", is_deleted=True), skip_images=True
            )
            created = processor.process_product_from_goods(_goods("anc-2", ["grp-orphan"]), skip_images=True)

        # Существующий товар обновляется как раньше, без проверки допуска
        assert updated is not None
        existing.refresh_from_db()
        assert existing.name == "Новое имя"
        assert existing.is_active is True
        assert existing.onec_deleted is False
        # Новый не создаётся
        assert created is None
        assert not Product.objects.filter(onec_id="anc-2").exists()
        assert processor.stats["hidden_products"] == 0
        assert processor.stats["products_created"] == 0
        assert processor.stats["skipped_products"] == 1
        # Реестр не ведётся: классификации нет
        assert OnecExcludedItem.objects.count() == 0
        # logger.error + строка в отчёт — один раз за сессию
        errors = [r for r in caplog.records if r.levelno == logging.ERROR and "ROOT_CATEGORY_NAME" in r.getMessage()]
        assert len(errors) == 1
        report = ImportSession.objects.get(pk=processor.session_id).report
        assert report.count("не найден ни в XML, ни в БД") == 1

    def test_offers_of_products_not_created_are_skipped_silently(self, processor, settings, caplog):
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        processor.process_product_from_goods(_goods("anc-3", ["grp-x"]), skip_images=True)

        with caplog.at_level(logging.WARNING, logger="import_products"):
            processor.process_variant_from_offer(_offer("anc-3#v1"), skip_images=True)

        assert processor.stats["skipped_variants"] == 1
        assert not any("parent Product not found" in r.getMessage() for r in caplog.records)

    def test_groups_file_without_anchor_creates_no_categories(self, processor, settings):
        settings.ROOT_CATEGORY_NAME = "СПОРТ"

        result = processor.process_categories(
            [{"id": "grp-a", "name": "ДРУГОЕ", "is_deleted": False}, {"id": "grp-b", "name": "Б", "parent_id": "grp-a"}]
        )

        assert result.get("root_not_found") is True
        assert Category.objects.count() == 0
        assert OnecExcludedItem.objects.count() == 0
        assert processor._anchor_missing is True


class TestRootFilterDisabled:
    """ROOT_CATEGORY_NAME пуст: условие «в поддереве якоря» выключено, пометки работают."""

    @pytest.fixture
    def plain_category(self, settings: Any) -> Category:
        settings.ROOT_CATEGORY_NAME = ""
        return Category.objects.create(name="Любая", slug="adm-any", onec_id="grp-any")

    def test_product_in_any_known_group_is_created(self, processor, plain_category, caplog):
        with caplog.at_level(logging.WARNING, logger="import_products"):
            first = processor.process_product_from_goods(_goods("nr-1", ["grp-any"]), skip_images=True)
            second = processor.process_product_from_goods(_goods("nr-2", ["grp-any"]), skip_images=True)

        assert first is not None and second is not None
        assert first.category == plain_category
        warnings = [r for r in caplog.records if "ROOT_CATEGORY_NAME пуст" in r.getMessage()]
        assert len(warnings) == 1, "WARNING об отключённом фильтре — один раз за сессию"

    def test_marked_product_is_rejected(self, processor, plain_category):
        result = processor.process_product_from_goods(_goods("nr-3", ["grp-any"], is_deleted=True), skip_images=True)

        assert result is None
        assert _registry("nr-3") == (KIND_PRODUCT, REASON_PRODUCT_MARKED)

    def test_product_under_marked_group_is_rejected(self, processor, plain_category):
        processor.process_categories(
            [
                {"id": "grp-any", "name": "Любая", "is_deleted": False},
                {"id": "grp-dead", "name": "К удалению", "is_deleted": True},
                {"id": "grp-dead-child", "name": "Потомок", "parent_id": "grp-dead", "is_deleted": False},
            ]
        )

        result = processor.process_product_from_goods(_goods("nr-4", ["grp-dead-child"]), skip_images=True)

        assert result is None
        assert _registry("nr-4") == (KIND_PRODUCT, REASON_GROUP_MARKED)
        # Помеченная группа и её потомки в каталог не попадают
        assert not Category.objects.filter(onec_id__in=["grp-dead", "grp-dead-child"]).exists()
        assert _registry("grp-dead") == (KIND_GROUP, REASON_GROUP_MARKED)
        assert _registry("grp-dead-child") == (KIND_GROUP, REASON_GROUP_MARKED)
        assert _registry("grp-any") is None

    def test_unmarked_group_leaves_registry(self, plain_category):
        OnecExcludedItem.objects.create(onec_id="grp-any", kind=KIND_GROUP, reason=REASON_GROUP_MARKED)

        _new_processor().process_categories([{"id": "grp-any", "name": "Любая", "is_deleted": False}])

        assert _registry("grp-any") is None

    @pytest.mark.parametrize("groups", [[], ["grp-never-seen"]], ids=["no-group", "unknown-group"])
    def test_product_without_resolvable_category_is_not_created(self, processor, plain_category, groups):
        """Запасных категорий больше нет: товар без категории не создаётся вовсе."""
        result = processor.process_product_from_goods(_goods("nr-5", groups), skip_images=True)

        assert result is None
        assert not Product.objects.filter(onec_id="nr-5").exists()
        assert not Category.objects.filter(slug__in=FALLBACK_CATEGORY_SLUGS).exists()
        assert Category.objects.count() == 1
        assert processor.stats["skipped_products"] == 1


# ============================================================================
# Поддерево якоря: XML поверх БД, реестр групп
# ============================================================================


class TestSubtreeFromXmlAndRegistry:
    def test_xml_parent_wins_over_db_parent(self, tree):
        """Группу вынесли из СПОРТ в 1С: в БД у категории ещё старая связь с родителем."""
        groups_session = _new_processor()
        groups_session.process_categories(_xml_groups(grp_combat={"parent_id": "grp-trash"}))

        assert "grp-combat" not in groups_session._allowed_category_ids
        assert "grp-gloves" not in groups_session._allowed_category_ids
        assert "grp-football" in groups_session._allowed_category_ids
        assert _registry("grp-combat") == (KIND_GROUP, REASON_OUTSIDE_TREE)
        assert _registry("grp-gloves") == (KIND_GROUP, REASON_OUTSIDE_TREE)
        assert _registry("grp-trash") == (KIND_GROUP, REASON_OUTSIDE_TREE)
        assert _registry("grp-football") is None

    def test_moved_out_group_stays_excluded_in_session_without_groups_xml(self, tree):
        _new_processor().process_categories(_xml_groups(grp_combat={"parent_id": "grp-trash"}))
        tree.combat.refresh_from_db()
        assert tree.combat.parent == tree.sport, "связь в БД осталась прежней — решает реестр"

        goods_session = _new_processor()
        rejected = goods_session.process_product_from_goods(_goods("sub-1", ["grp-gloves"]), skip_images=True)
        admitted = goods_session.process_product_from_goods(_goods("sub-2", ["grp-football"]), skip_images=True)

        assert rejected is None
        assert _registry("sub-1") == (KIND_PRODUCT, REASON_OUTSIDE_TREE)
        assert admitted is not None

    def test_marked_group_excludes_subtree_in_later_sessions(self, tree):
        first = _new_processor()
        first.process_categories(_xml_groups(grp_combat={"is_deleted": True}))

        assert "grp-combat" not in first._allowed_category_ids
        assert "grp-gloves" not in first._allowed_category_ids
        assert _registry("grp-combat") == (KIND_GROUP, REASON_GROUP_MARKED)
        assert _registry("grp-gloves") == (KIND_GROUP, REASON_GROUP_MARKED)

        result = _new_processor().process_product_from_goods(_goods("sub-3", ["grp-gloves"]), skip_images=True)

        assert result is None
        assert _registry("sub-3") == (KIND_PRODUCT, REASON_GROUP_MARKED)

    def test_group_returned_to_tree_leaves_registry(self, tree):
        _new_processor().process_categories(_xml_groups(grp_combat={"is_deleted": True}))

        back = _new_processor()
        back.process_categories(_xml_groups())

        assert "grp-gloves" in back._allowed_category_ids
        assert _registry("grp-combat") is None
        assert _registry("grp-gloves") is None
        assert back.process_product_from_goods(_goods("sub-4", ["grp-gloves"]), skip_images=True) is not None

    def test_partial_groups_file_takes_missing_ancestors_from_db(self, tree):
        """В XML только лист: его цепочка до якоря достраивается по БД."""
        session = _new_processor()
        session.process_categories(
            [{"id": "grp-new-leaf", "name": "Новый лист", "parent_id": "grp-gloves", "is_deleted": False}]
        )

        assert "grp-new-leaf" in session._allowed_category_ids
        assert Category.objects.get(onec_id="grp-new-leaf").is_active is True

    def test_groups_outside_subtree_are_not_created(self, settings):
        settings.ROOT_CATEGORY_NAME = "СПОРТ"

        _new_processor().process_categories(_xml_groups(grp_combat={"is_deleted": True}))

        assert set(Category.objects.values_list("onec_id", flat=True)) == {"grp-sport", "grp-football"}

    def test_marked_anchor_is_ignored_with_warning(self, settings, caplog):
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        session = _new_processor()

        with caplog.at_level(logging.WARNING, logger="import_products"):
            session.process_categories(_xml_groups(grp_sport={"is_deleted": True}))

        assert {"grp-sport", "grp-combat", "grp-gloves", "grp-football"} <= session._allowed_category_ids
        assert any("пометка якоря игнорируется" in r.getMessage() for r in caplog.records)

    def test_repair_anchor_children_stay_in_subtree(self, settings):
        """Repair-якорь (sentinel onec_id) — тот же якорь: его потомки из БД допущены."""
        from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID

        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        repair = Category.objects.create(name="СПОРТ", slug="adm-repair", onec_id=REPAIR_ANCHOR_ONEC_ID)
        Category.objects.create(name="Только в БД", slug="adm-db-only", onec_id="grp-db-only", parent=repair)

        session = _new_processor()
        session.process_categories([{"id": "grp-sport", "name": "СПОРТ", "is_deleted": False}])

        assert "grp-db-only" in session._allowed_category_ids
        repair.refresh_from_db()
        assert repair.onec_id == "grp-sport"


# ============================================================================
# Отчёт сессии
# ============================================================================


class TestSessionReport:
    def test_counters_in_report_details_and_summary_line_in_report(self, tree):
        processor = _new_processor()
        _make_product(tree, "rep-hidden")
        restored = _make_product(tree, "rep-restored", is_active=False, onec_deleted=True)
        _make_variant(restored, "rep-restored#v1")
        _make_product(tree, "rep-moved", category=tree.trash)
        with_variants = _make_product(tree, "rep-variants")
        _make_variant(with_variants, "rep-variants#v1")
        _make_variant(with_variants, "rep-variants#v2")
        back = _make_variant(with_variants, "rep-variants#v3", is_active=False, onec_deleted=True)

        processor.process_product_from_goods(_goods("rep-new", ["grp-trash"]), skip_images=True)
        processor.process_product_from_goods(_goods("rep-hidden", ["grp-trash"]), skip_images=True)
        processor.process_product_from_goods(_goods("rep-restored", ["grp-gloves"]), skip_images=True)
        processor.process_product_from_goods(_goods("rep-moved", ["grp-football"]), skip_images=True)
        processor.process_variant_from_offer(_offer("rep-new#v1"), skip_images=True)
        processor.process_variant_from_offer(_offer("rep-variants#v1", is_deleted=True), skip_images=True)
        processor.process_variant_from_offer(_offer(back.onec_id), skip_images=True)

        processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

        session = ImportSession.objects.get(pk=processor.session_id)
        details = session.report_details
        assert details["skipped_products"] == 1
        assert details["hidden_products"] == 1
        assert details["restored_products"] == 1
        assert details["recategorized_products"] == 1
        assert details["skipped_variants"] == 1
        assert details["hidden_variants"] == 1
        assert details["restored_variants"] == 1
        assert (
            "Вне СПОРТ / к удалению: не создано 1 товаров / 1 вариантов, скрыто 1 / 1, "
            "возвращено 1 / 1, перенесено в категорию группы 1"
        ) in session.report

    def test_summary_is_written_after_each_step_without_repeats(self, tree):
        """`report_details` пишется только при COMPLETED — строка шага видна и в упавшей сессии."""
        processor = _new_processor()
        processor.process_product_from_goods(_goods("rep-step-1", ["grp-trash"]), skip_images=True)

        processor.log_admission_summary()
        processor.log_admission_summary()
        processor.process_product_from_goods(_goods("rep-step-2", ["grp-trash"]), skip_images=True)
        processor.log_admission_summary()
        processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

        report = ImportSession.objects.get(pk=processor.session_id).report
        assert report.count("не создано 1 товаров") == 1
        assert report.count("не создано 2 товаров") == 1
        assert report.count("Вне СПОРТ / к удалению") == 2

    def test_no_summary_line_when_nothing_was_excluded(self, tree):
        """Сегменты цен и остатков без исключённых позиций не получают шум в отчёте."""
        processor = _new_processor()
        processor.process_product_from_goods(_goods("rep-clean", ["grp-gloves"]), skip_images=True)

        assert processor.admission_report_line() == ""
        processor.log_admission_summary()
        processor.finalize_session(ImportSession.ImportStatus.COMPLETED)

        session = ImportSession.objects.get(pk=processor.session_id)
        assert "к удалению" not in session.report
        assert session.report_details["skipped_products"] == 0

    def test_summary_line_names_tree_when_root_filter_is_disabled(self, settings):
        settings.ROOT_CATEGORY_NAME = ""
        processor = _new_processor()
        processor.process_product_from_goods(_goods("rep-noroot", [], is_deleted=True), skip_images=True)

        assert processor.admission_report_line().startswith("Вне дерева / к удалению: не создано 1 товаров")

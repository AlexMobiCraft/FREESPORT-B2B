"""
Команда `purge_products_outside_root`: единственное место, где товары, скрытые
импортом 1С, удаляются физически.

Обмен с 1С только скрывает недопущенное (`onec_deleted=True`); очистка —
разовая операция с dry-run по умолчанию. Товар с заказом не удаляется никогда:
`OrderItem.product` — CASCADE, удаление стёрло бы историю заказов.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from io import StringIO
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from apps.orders.models import Order, OrderItem
from apps.products.management.commands.purge_products_outside_root import Command
from apps.products.models import Category, OnecExcludedItem, Product, ProductVariant
from apps.products.services.onec_admission import (
    KIND_GROUP,
    KIND_OFFER,
    KIND_PRODUCT,
    REASON_CATEGORY_OUTSIDE_TREE,
    REASON_GROUP_MARKED,
    REASON_HIDDEN_BY_IMPORT,
    REASON_OFFER_MARKED,
    REASON_PRODUCT_MARKED,
)
from tests.conftest import BrandFactory, CartItemFactory, OrderFactory, UserFactory

pytestmark = [pytest.mark.django_db, pytest.mark.integration]


# ============================================================================
# Fixtures
# ============================================================================


def _category(name: str, onec_id: str, parent: Category | None = None, **extra: Any) -> Category:
    return Category.objects.create(name=name, slug=f"purge-{onec_id}", onec_id=onec_id, parent=parent, **extra)


def _product(world: SimpleNamespace, onec_id: str, category: Category, **extra: Any) -> Product:
    fields: dict[str, Any] = {
        "name": f"Товар {onec_id}",
        "slug": f"purge-{onec_id}",
        "onec_id": onec_id,
        "parent_onec_id": onec_id,
        "article": f"ART-{onec_id}",
        "brand": world.brand,
        "category": category,
        "description": "",
        "is_active": True,
    }
    fields.update(extra)
    return Product.objects.create(**fields)


def _variant(product: Product, onec_id: str, **extra: Any) -> ProductVariant:
    fields: dict[str, Any] = {
        "product": product,
        "sku": f"SKU-{onec_id}",
        "onec_id": onec_id,
        "retail_price": Decimal("100"),
        "stock_quantity": 3,
        "is_active": True,
    }
    fields.update(extra)
    return ProductVariant.objects.create(**fields)


def _order_item(product: Product, variant: ProductVariant | None = None) -> OrderItem:
    order = OrderFactory.create(user=UserFactory.create())
    return OrderItem.objects.create(
        order=order,
        product=product,
        variant=variant,
        quantity=1,
        unit_price=Decimal("100"),
        total_price=Decimal("100"),
        product_name=product.name,
        product_sku=variant.sku if variant else "",
    )


@pytest.fixture
def world(settings) -> SimpleNamespace:
    """Каталог до очистки: дерево СПОРТ и всё, что лежит вне него."""
    settings.ROOT_CATEGORY_NAME = "СПОРТ"
    brand = BrandFactory.create()
    sport = _category("СПОРТ", "grp-sport")
    combat = _category("Единоборства", "grp-combat", sport)
    trash = _category("Номенклатура к удалению", "grp-trash")
    trash_child = _category("Выбыло из ассортимента", "grp-trash-child", trash)
    special = _category("для спецзаказов", "grp-special")
    placeholder = _category("Категория 12345678-aaaa-bbbb-cccc-1234567890ab", "grp-placeholder")
    world = SimpleNamespace(
        brand=brand,
        sport=sport,
        combat=combat,
        trash=trash,
        trash_child=trash_child,
        special=special,
        placeholder=placeholder,
    )

    # Товар СПОРТ — остаётся
    world.kept = _product(world, "kept", combat)
    world.kept_variant = _variant(world.kept, "kept#v1")
    # Скрыт импортом, лежит в категории СПОРТ («к удалению» после переноса в 1С)
    world.hidden = _product(world, "hidden", combat, is_active=False, onec_deleted=True)
    _variant(world.hidden, "hidden#v1")
    OnecExcludedItem.objects.create(onec_id="hidden", kind=KIND_PRODUCT, reason=REASON_PRODUCT_MARKED)
    # Категория вне поддерева, в выгрузке товара нет — импорт его не видел
    world.outside = _product(world, "outside", trash_child)
    _variant(world.outside, "outside#v1")
    world.special_product = _product(world, "special", special)
    # Вне поддерева, но с заказом — защищён
    world.ordered = _product(world, "ordered", trash)
    world.ordered_variant = _variant(world.ordered, "ordered#v1")
    world.order_item = _order_item(world.ordered, world.ordered_variant)
    return world


def _purge(**options: Any) -> str:
    out = StringIO()
    call_command("purge_products_outside_root", stdout=out, stderr=StringIO(), **options)
    return out.getvalue()


def _snapshot() -> dict[str, Any]:
    return {
        "products": sorted(Product.objects.values_list("pk", "is_active", "onec_deleted")),
        "variants": sorted(ProductVariant.objects.values_list("pk", "is_active", "onec_deleted")),
        "categories": sorted(Category.objects.values_list("pk", flat=True)),
        "registry": sorted(OnecExcludedItem.objects.values_list("onec_id", "kind", "reason")),
        "order_items": sorted(OrderItem.objects.values_list("pk", "product_id", "variant_id")),
    }


# ============================================================================
# Dry-run
# ============================================================================


class TestDryRun:
    def test_changes_nothing_and_reports_counts(self, world):
        before = _snapshot()

        output = _purge()

        assert _snapshot() == before, "dry-run не вправе менять БД"
        assert "DRY-RUN: якорь 'СПОРТ'" in output
        assert "категорий в поддереве: 2" in output
        assert "товаров будет удалено 3, сохранено из-за заказов 1" in output
        assert "вариантов будет удалено 0" in output
        assert "категорий будет удалено 3, сохранено 1" in output
        assert "БД не изменена" in output

    def test_lists_positions_with_id_article_name_and_reason(self, world):
        output = _purge()

        assert f"[товар к удалению: {REASON_HIDDEN_BY_IMPORT}] onec_id=hidden article='ART-hidden'" in output
        assert f"[товар к удалению: {REASON_CATEGORY_OUTSIDE_TREE}] onec_id=outside" in output
        assert "[товар сохранён: заказов 1] onec_id=ordered" in output
        assert "[категория к удалению] onec_id=grp-special" in output
        assert "[категория к удалению] onec_id=grp-trash-child" in output
        assert "[категория сохранена] onec_id=grp-trash" in output
        assert "onec_id=kept" not in output

    def test_preview_is_limited_to_first_positions(self, world):
        """Печатаются первые N позиций каждого вида, остальное — счётчиком."""
        for index in range(4):
            _product(world, f"bulk-{index}", world.special)

        with patch.object(Command, "PREVIEW_LIMIT", 2):
            output = _purge()

        assert output.count("[товар к удалению") == 2
        assert "... и ещё 5 товар(ов) к удалению" in output
        assert output.count("[категория к удалению]") == 2
        assert "... и ещё 1 категори(й) к удалению" in output

    def test_hidden_variants_of_kept_products_are_previewed(self, world):
        _variant(world.kept, "kept#marked", is_active=False, onec_deleted=True)
        # Вариант удаляемого товара уйдёт каскадом и отдельно не считается
        _variant(world.hidden, "hidden#marked", is_active=False, onec_deleted=True)
        before = _snapshot()

        with patch.object(Command, "PREVIEW_LIMIT", 0):
            output = _purge()

        assert _snapshot() == before
        assert "вариантов будет удалено 1" in output
        assert "... и ещё 1 вариант(ов) к удалению" in output


class TestAnchorErrors:
    def test_missing_anchor_aborts(self, settings):
        """Без якоря «вне дерева» оказался бы весь каталог."""
        settings.ROOT_CATEGORY_NAME = "СПОРТ"
        brand = BrandFactory.create()
        category = _category("Без якоря", "grp-orphan")
        product = Product.objects.create(
            name="Уцелевший", slug="purge-survivor", onec_id="survivor", brand=brand, category=category, description=""
        )

        with pytest.raises(CommandError, match="не найдена"):
            _purge(apply=True)

        assert Product.objects.filter(pk=product.pk).exists()

    def test_duplicate_anchor_aborts(self, world):
        _category("СПОРТ", "grp-sport-dup")

        with pytest.raises(CommandError, match="более одного"):
            _purge(apply=True)

        assert Product.objects.count() == 5

    def test_empty_root_name_aborts(self, world, settings):
        settings.ROOT_CATEGORY_NAME = ""

        with pytest.raises(CommandError, match="не задано"):
            _purge(apply=True)

    def test_root_name_option_overrides_settings(self, world, settings):
        settings.ROOT_CATEGORY_NAME = "НЕТ ТАКОГО"

        output = _purge(root_name="СПОРТ")

        assert "DRY-RUN: якорь 'СПОРТ'" in output


# ============================================================================
# Apply
# ============================================================================


class TestApply:
    def test_deletes_everything_not_admitted_without_orders(self, world, caplog):
        with caplog.at_level(logging.INFO, logger="import_products"):
            output = _purge(apply=True)

        # Скрытый импортом и товары с категорией вне поддерева удалены
        assert not Product.objects.filter(onec_id__in=["hidden", "outside", "special"]).exists()
        assert not ProductVariant.objects.filter(onec_id__in=["hidden#v1", "outside#v1"]).exists()
        # Товар СПОРТ не тронут
        world.kept.refresh_from_db()
        world.kept_variant.refresh_from_db()
        assert world.kept.is_active is True
        assert world.kept.onec_deleted is False
        assert world.kept_variant.is_active is True
        # Сводка
        assert "APPLY: якорь 'СПОРТ'" in output
        assert "товаров удалено 3, сохранено из-за заказов 1" in output
        assert "ошибок 0" in output
        # Построчный лог: Ид 1С, артикул, наименование, причина
        deleted_lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Товар удалён")]
        assert len(deleted_lines) == 3
        hidden_line = next(line for line in deleted_lines if "onec_id=hidden" in line)
        assert "article=ART-hidden" in hidden_line
        assert "name=Товар hidden" in hidden_line
        assert f"reason={REASON_HIDDEN_BY_IMPORT}" in hidden_line

    def test_product_with_order_is_hidden_not_deleted(self, world, caplog):
        with caplog.at_level(logging.WARNING, logger="import_products"):
            _purge(apply=True)

        world.ordered.refresh_from_db()
        world.ordered_variant.refresh_from_db()
        world.order_item.refresh_from_db()
        assert world.ordered.is_active is False
        assert world.ordered.onec_deleted is True
        assert world.order_item.product_id == world.ordered.pk
        assert world.order_item.variant_id == world.ordered_variant.pk
        assert Order.objects.count() == 1
        # Его категория сохранена, пустые соседние — удалены
        assert Category.objects.filter(pk=world.trash.pk).exists()
        assert not Category.objects.filter(pk=world.trash_child.pk).exists()
        warnings = [r.getMessage() for r in caplog.records if "ссылаются заказы" in r.getMessage()]
        assert len(warnings) == 1
        assert "onec_id=ordered" in warnings[0]
        assert "orders=1" in warnings[0]
        assert any("Категория вне дерева сохранена" in r.getMessage() for r in caplog.records)

    def test_product_protected_through_variant_order(self, world):
        """Заказ ссылается на вариант: удаление товара каскадом оборвало бы связь заказа с SKU."""
        other = _product(world, "other-owner", world.combat)
        variant_only = _product(world, "variant-only", world.special)
        variant = _variant(variant_only, "variant-only#v1")
        item = _order_item(other, variant)

        _purge(apply=True)

        variant_only.refresh_from_db()
        item.refresh_from_db()
        assert variant_only.onec_deleted is True
        assert item.variant_id == variant.pk
        assert Category.objects.filter(pk=world.special.pk).exists()

    def test_empty_categories_outside_subtree_are_deleted_leaves_first(self, world):
        _purge(apply=True)

        remaining = set(Category.objects.values_list("onec_id", flat=True))
        assert remaining == {"grp-sport", "grp-combat", "grp-trash"}
        assert Category.objects.filter(pk=world.sport.pk).exists(), "якорь сохраняется"

    def test_deleted_ids_go_to_registry(self, world):
        _purge(apply=True)

        registry = {item.onec_id: (item.kind, item.reason) for item in OnecExcludedItem.objects.all()}
        # Причину, записанную импортом, очистка не затирает
        assert registry["hidden"] == (KIND_PRODUCT, REASON_PRODUCT_MARKED)
        assert registry["outside"] == (KIND_PRODUCT, REASON_CATEGORY_OUTSIDE_TREE)
        assert registry["special"] == (KIND_PRODUCT, REASON_CATEGORY_OUTSIDE_TREE)
        assert registry["ordered"] == (KIND_PRODUCT, REASON_CATEGORY_OUTSIDE_TREE)
        assert "kept" not in registry

    def test_cart_items_and_favorites_go_with_product(self, world):
        from apps.cart.models import CartItem
        from apps.users.models import Favorite

        variant = ProductVariant.objects.get(onec_id="outside#v1")
        cart_item = CartItemFactory.create(variant=variant, quantity=1)
        favorite = Favorite.objects.create(user=UserFactory.create(), product=world.outside)

        output = _purge(apply=True)

        assert "ошибок 0" in output
        assert not CartItem.objects.filter(pk=cart_item.pk).exists()
        assert not Favorite.objects.filter(pk=favorite.pk).exists()
        assert not Product.objects.filter(onec_id="outside").exists()

    def test_second_run_has_nothing_to_do(self, world):
        _purge(apply=True)
        before = _snapshot()

        output = _purge(apply=True)

        assert _snapshot() == before
        assert "товаров удалено 0, сохранено из-за заказов 1" in output

    def test_registry_group_is_outside_subtree(self, world):
        """Группа, помеченная в 1С, в БД ещё числится под якорем — её товары тоже уходят."""
        marked = _category("Помеченная", "grp-marked", world.sport)
        nested = _category("Вложенная", "grp-marked-nested", marked)
        _product(world, "in-marked", nested)
        OnecExcludedItem.objects.create(onec_id="grp-marked", kind=KIND_GROUP, reason=REASON_GROUP_MARKED)

        _purge(apply=True)

        assert not Product.objects.filter(onec_id="in-marked").exists()
        assert not Category.objects.filter(onec_id__in=["grp-marked", "grp-marked-nested"]).exists()
        assert Product.objects.filter(onec_id="kept").exists()


class TestHiddenVariants:
    def test_hidden_variant_without_order_is_deleted(self, world, caplog):
        marked = _variant(world.kept, "kept#marked", is_active=False, onec_deleted=True)

        with caplog.at_level(logging.INFO, logger="import_products"):
            output = _purge(apply=True)

        assert not ProductVariant.objects.filter(pk=marked.pk).exists()
        assert ProductVariant.objects.filter(pk=world.kept_variant.pk).exists()
        world.kept.refresh_from_db()
        assert world.kept.is_active is True
        assert "вариантов удалено 1, сохранено из-за заказов 0" in output
        assert OnecExcludedItem.objects.get(onec_id="kept#marked").kind == KIND_OFFER
        lines = [r.getMessage() for r in caplog.records if r.getMessage().startswith("Вариант удалён")]
        assert len(lines) == 1
        assert "onec_id=kept#marked" in lines[0] and f"reason={REASON_OFFER_MARKED}" in lines[0]

    def test_hidden_variant_with_order_is_kept(self, world, caplog):
        marked = _variant(world.kept, "kept#ordered", is_active=False, onec_deleted=True)
        item = _order_item(world.kept, marked)

        with caplog.at_level(logging.WARNING, logger="import_products"):
            output = _purge(apply=True)

        marked.refresh_from_db()
        item.refresh_from_db()
        assert marked.onec_deleted is True
        assert item.variant_id == marked.pk
        assert "вариантов удалено 0, сохранено из-за заказов 1" in output
        assert "[вариант сохранён: заказов 1] onec_id=kept#ordered" in output
        assert any("Вариант не удалён" in r.getMessage() for r in caplog.records)

    def test_product_left_without_active_variants_is_deactivated(self, world):
        """Дефолтный вариант импорт такому товару не создаст: предложения — в реестре."""
        lonely = _product(world, "lonely", world.combat)
        _variant(lonely, "lonely#v1", is_active=False, onec_deleted=True)

        _purge(apply=True)

        lonely.refresh_from_db()
        assert lonely.is_active is False
        assert lonely.onec_deleted is False
        assert not ProductVariant.objects.filter(product=lonely).exists()
        assert OnecExcludedItem.objects.filter(onec_id="lonely#v1", kind=KIND_OFFER).exists()


class TestFailures:
    def test_batch_failure_falls_back_to_one_by_one(self, world):
        """Сбой пачки → повтор по одному; ошибка одного объекта не останавливает команду."""
        original_delete = Product.delete

        def flaky_delete(self, *args, **kwargs):
            if self.onec_id == "outside":
                raise RuntimeError("boom")
            return original_delete(self, *args, **kwargs)

        with patch.object(Product, "delete", flaky_delete):
            output = _purge(apply=True)

        assert Product.objects.filter(onec_id="outside").exists(), "сбойный объект остался"
        assert not Product.objects.filter(onec_id__in=["hidden", "special"]).exists(), "остальные удалены"
        assert "товаров удалено 2" in output
        assert "ошибок 1" in output
        assert "Не удалось удалить" in output
        # Категория сбойного товара не удалена — в ней остался товар
        assert Category.objects.filter(pk=world.trash_child.pk).exists()
        assert not OnecExcludedItem.objects.filter(onec_id="outside").exists()

    def test_batches_are_processed_independently(self, world):
        with patch.object(Command, "BATCH_SIZE", 1):
            output = _purge(apply=True)

        assert "товаров удалено 3" in output
        assert Product.objects.count() == 2

    def test_category_delete_error_is_reported_and_skipped(self, world):
        original_delete = Category.delete

        def flaky_delete(self, *args, **kwargs):
            if self.onec_id == "grp-special":
                raise RuntimeError("locked")
            return original_delete(self, *args, **kwargs)

        with patch.object(Category, "delete", flaky_delete):
            output = _purge(apply=True)

        assert Category.objects.filter(onec_id="grp-special").exists()
        assert not Category.objects.filter(onec_id="grp-placeholder").exists()
        assert "Не удалось удалить категорию onec_id=grp-special" in output
        assert "ошибок 1" in output

    def test_registry_failure_after_delete_is_reported(self, world):
        with patch(
            "apps.products.services.onec_admission.ExclusionRegistry.add", side_effect=RuntimeError("registry down")
        ):
            output = _purge(apply=True)

        assert not Product.objects.filter(onec_id="outside").exists()
        assert "запись в реестр не удалась" in output
        assert "Не удалось скрыть товар onec_id=ordered" in output


# ============================================================================
# Публичный API
# ============================================================================


class TestPublicApiAfterPurge:
    def test_deleted_product_is_not_served(self, world, api_client):
        deleted_slug = world.outside.slug
        ordered_slug = world.ordered.slug
        assert api_client.get(reverse("products:product-detail", kwargs={"slug": deleted_slug})).status_code == 200

        _purge(apply=True)

        assert api_client.get(reverse("products:product-detail", kwargs={"slug": deleted_slug})).status_code == 404
        # Товар с заказом остался в БД, но скрыт
        assert api_client.get(reverse("products:product-detail", kwargs={"slug": ordered_slug})).status_code == 404
        assert api_client.get(reverse("products:product-detail", kwargs={"slug": world.kept.slug})).status_code == 200

        listing = api_client.get(reverse("products:product-list"))
        assert listing.status_code == 200
        slugs = {item["slug"] for item in listing.data["results"]}
        assert slugs == {world.kept.slug}

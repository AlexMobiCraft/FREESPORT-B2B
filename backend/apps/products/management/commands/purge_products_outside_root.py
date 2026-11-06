"""
Разовая очистка каталога: физическое удаление товаров, вариантов и категорий
вне дерева якорной категории (ROOT_CATEGORY_NAME).

Обмен с 1С ничего не удаляет — он только скрывает недопущенное
(`onec_deleted=True`). Удаляет эта команда, и только по явному `--apply`:

    python manage.py purge_products_outside_root            # dry-run
    python manage.py purge_products_outside_root --apply

Порядок: товары → варианты → категории. Товар, на который ссылается заказ,
не удаляется никогда: `OrderItem.product` — CASCADE, удаление стёрло бы
историю заказов. Такой товар скрывается, а его категория сохраняется.

Файлы картинок в MEDIA_ROOT не трогаются: при возврате товара импорт найдёт
их на месте и не будет копировать заново.
"""

from __future__ import annotations

import logging
from collections import Counter
from collections.abc import Iterable, Iterator
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.products.services.onec_admission import (
    KIND_OFFER,
    KIND_PRODUCT,
    REASON_CATEGORY_OUTSIDE_TREE,
    REASON_HIDDEN_BY_IMPORT,
    REASON_OFFER_MARKED,
    ExclusionRegistry,
    compute_subtree,
    load_db_category_tree,
)

# Построчный лог уходит туда же, куда пишет импорт: по нему позицию ищут в 1С.
logger = logging.getLogger("import_products")


class Command(BaseCommand):
    help = (
        "Удаляет товары, скрытые импортом 1С, товары с категорией вне дерева якоря, "
        "скрытые варианты и пустые категории вне дерева. По умолчанию — dry-run."
    )

    # Размер пачки удаления. Пачка — одна транзакция: сбой откатывает только её.
    BATCH_SIZE = 200
    # Сколько позиций каждого вида печатает dry-run.
    PREVIEW_LIMIT = 50

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--apply", action="store_true", help="Выполнить удаление (без флага — dry-run)")
        parser.add_argument(
            "--root-name",
            type=str,
            default=None,
            help="Имя якорной категории (override settings.ROOT_CATEGORY_NAME)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.products.models import Category

        self.apply = bool(options.get("apply"))
        root_name = str(options.get("root_name") or getattr(settings, "ROOT_CATEGORY_NAME", "") or "")
        if not root_name:
            raise CommandError("Имя якорной категории не задано: укажите --root-name или ROOT_CATEGORY_NAME.")

        anchors = list(Category.objects.filter(name=root_name, parent__isnull=True))
        if not anchors:
            # Без якоря «вне дерева» оказался бы весь каталог.
            raise CommandError(f"Якорная категория '{root_name}' не найдена — очистка не выполняется.")
        if len(anchors) > 1:
            raise CommandError(
                f"Найдено более одного корневого якоря с именем '{root_name}'. "
                "Устраните дублирование вручную перед повторным запуском."
            )
        anchor = anchors[0]

        self.registry = ExclusionRegistry()
        self.errors = 0

        # Поддерево считается так же, как в импорте: потомки якоря минус группы,
        # помеченные или вынесенные из дерева (они лежат в реестре).
        key_by_pk, parent_of, _ = load_db_category_tree()
        allowed_keys = compute_subtree(parent_of, {key_by_pk[anchor.pk]}, self.registry.groups())
        self.subtree_pks = {pk for pk, key in key_by_pk.items() if key in allowed_keys}

        mode = "APPLY" if self.apply else "DRY-RUN"
        self._out(f"{mode}: якорь '{anchor.name}' (id={anchor.pk}), категорий в поддереве: {len(self.subtree_pks)}")

        products = self._purge_products()
        variants = self._purge_variants(products["deletable_pks"])
        categories = self._purge_categories(products["protected_category_pks"])

        verb = "удалено" if self.apply else "будет удалено"
        self._out(
            f"SUMMARY ({mode}): товаров {verb} {products['deleted']}, сохранено из-за заказов {products['protected']}; "
            f"вариантов {verb} {variants['deleted']}, сохранено из-за заказов {variants['protected']}; "
            f"категорий {verb} {categories['deleted']}, сохранено {categories['kept']}; ошибок {self.errors}"
        )
        if not self.apply:
            self._out("DRY-RUN: БД не изменена. Для удаления запустите команду с --apply.")

    # ------------------------------------------------------------------
    # Товары
    # ------------------------------------------------------------------

    def _purge_products(self) -> dict[str, Any]:
        from apps.products.models import Product

        candidates = Product.objects.filter(Q(onec_deleted=True) | ~Q(category_id__in=self.subtree_pks))
        pks = list(candidates.order_by("pk").values_list("pk", flat=True))

        deleted = 0
        protected = 0
        previewed = 0
        protected_previewed = 0
        deletable_pks: set[int] = set()
        protected_category_pks: set[int] = set()

        for batch_pks in self._batches(pks):
            batch = list(Product.objects.filter(pk__in=batch_pks).order_by("pk"))
            order_counts = self._order_counts_for_products(batch_pks)
            deletable: list[Any] = []

            for product in batch:
                orders = order_counts.get(product.pk, 0)
                if orders:
                    protected += 1
                    protected_category_pks.add(product.category_id)
                    logger.warning(
                        "Товар не удалён — на него ссылаются заказы: onec_id=%s article=%s name=%s orders=%s",
                        product.onec_id,
                        product.article,
                        product.name,
                        orders,
                    )
                    if protected_previewed < self.PREVIEW_LIMIT:
                        protected_previewed += 1
                        self._out(
                            f"  [товар сохранён: заказов {orders}] onec_id={product.onec_id} "
                            f"article={product.article!r} name={product.name!r}"
                        )
                    if self.apply:
                        self._hide_protected_product(product)
                    continue

                deletable.append(product)
                deletable_pks.add(product.pk)
                if not self.apply and previewed < self.PREVIEW_LIMIT:
                    previewed += 1
                    self._out(
                        f"  [товар к удалению: {self._product_reason(product)}] onec_id={product.onec_id} "
                        f"article={product.article!r} name={product.name!r}"
                    )

            if self.apply:
                deleted += self._delete_objects(deletable, self._after_product_delete)
            else:
                deleted += len(deletable)

        if not self.apply and deleted > previewed:
            self._out(f"  ... и ещё {deleted - previewed} товар(ов) к удалению")

        return {
            "deleted": deleted,
            "protected": protected,
            "deletable_pks": deletable_pks,
            "protected_category_pks": protected_category_pks,
        }

    def _product_reason(self, product: Any) -> str:
        if product.onec_deleted:
            return REASON_HIDDEN_BY_IMPORT
        return REASON_CATEGORY_OUTSIDE_TREE

    def _order_counts_for_products(self, product_pks: list[int]) -> Counter[int]:
        """Число позиций заказов на товар — напрямую или через его вариант.

        Один запрос на пачку. Вариант учитывается потому, что удаление товара
        каскадом удалит вариант, а `OrderItem.variant` (SET_NULL) потеряет связь
        заказа с SKU, нужную для выгрузки заказа в 1С.
        """
        from apps.orders.models import OrderItem

        pk_set = set(product_pks)
        counts: Counter[int] = Counter()
        rows = OrderItem.objects.filter(Q(product_id__in=pk_set) | Q(variant__product_id__in=pk_set)).values_list(
            "product_id", "variant__product_id"
        )
        for product_id, variant_product_id in rows:
            for owner in {product_id, variant_product_id} & pk_set:
                counts[owner] += 1
        return counts

    def _hide_protected_product(self, product: Any) -> None:
        """Товар с заказами остаётся в БД скрытым."""
        # Причина снимается до скрытия: после него товар выглядел бы «скрытым импортом».
        reason = self._product_reason(product)
        try:
            if product.is_active or not product.onec_deleted:
                product.is_active = False
                product.onec_deleted = True
                product.save(update_fields=["is_active", "onec_deleted", "updated_at"])
            self._register_product(product, reason)
        except Exception as exc:
            self._error(f"Не удалось скрыть товар onec_id={product.onec_id} или занести его в реестр: {exc}")

    def _register_product(self, product: Any, reason: str) -> None:
        """Занести Ид товара в реестр: его предложения, цены и остатки импорт пропустит молча."""
        for onec_id in {product.onec_id, product.parent_onec_id}:
            # Причину, записанную импортом, не затираем — она точнее.
            if onec_id and not self.registry.is_product_excluded(onec_id):
                self.registry.add(onec_id, KIND_PRODUCT, reason)

    def _after_product_delete(self, product: Any) -> None:
        reason = self._product_reason(product)
        self._register_product(product, reason)
        logger.info(
            "Товар удалён: onec_id=%s article=%s name=%s reason=%s",
            product.onec_id,
            product.article,
            product.name,
            reason,
        )

    # ------------------------------------------------------------------
    # Варианты
    # ------------------------------------------------------------------

    def _purge_variants(self, deletable_product_pks: set[int]) -> dict[str, int]:
        """Варианты, скрытые пометкой предложения, у оставшихся товаров."""
        from apps.orders.models import OrderItem
        from apps.products.models import Product, ProductVariant

        pks = [
            pk
            for pk, product_id in ProductVariant.objects.filter(onec_deleted=True)
            .order_by("pk")
            .values_list("pk", "product_id")
            # В dry-run товары ещё на месте: их варианты уйдут каскадом и
            # отдельно не считаются.
            if self.apply or product_id not in deletable_product_pks
        ]

        deleted = 0
        protected = 0
        previewed = 0

        for batch_pks in self._batches(pks):
            batch = list(ProductVariant.objects.filter(pk__in=batch_pks).select_related("product").order_by("pk"))
            order_counts: Counter[int] = Counter(
                OrderItem.objects.filter(variant_id__in=batch_pks).values_list("variant_id", flat=True)
            )
            deletable: list[Any] = []

            for variant in batch:
                orders = order_counts.get(variant.pk, 0)
                if orders:
                    protected += 1
                    logger.warning(
                        "Вариант не удалён — на него ссылаются заказы: onec_id=%s sku=%s name=%s orders=%s",
                        variant.onec_id,
                        variant.sku,
                        variant.product.name,
                        orders,
                    )
                    self._out(
                        f"  [вариант сохранён: заказов {orders}] onec_id={variant.onec_id} sku={variant.sku!r} "
                        f"name={variant.product.name!r}"
                    )
                    continue

                deletable.append(variant)
                if not self.apply and previewed < self.PREVIEW_LIMIT:
                    previewed += 1
                    self._out(
                        f"  [вариант к удалению] onec_id={variant.onec_id} sku={variant.sku!r} "
                        f"name={variant.product.name!r}"
                    )

            if self.apply:
                deleted += self._delete_objects(deletable, self._after_variant_delete)
                # Товар, у которого не осталось активных вариантов, с витрины уходит.
                # Дефолтный вариант импорт ему не создаст: предложения — в реестре.
                product_pks = {variant.product_id for variant in deletable}
                Product.objects.filter(pk__in=product_pks, is_active=True).exclude(variants__is_active=True).update(
                    is_active=False
                )
            else:
                deleted += len(deletable)

        if not self.apply and deleted > previewed:
            self._out(f"  ... и ещё {deleted - previewed} вариант(ов) к удалению")

        return {"deleted": deleted, "protected": protected}

    def _after_variant_delete(self, variant: Any) -> None:
        if variant.onec_id and not self.registry.is_offer_excluded(variant.onec_id):
            self.registry.add(variant.onec_id, KIND_OFFER, REASON_OFFER_MARKED)
        logger.info(
            "Вариант удалён: onec_id=%s sku=%s name=%s reason=%s",
            variant.onec_id,
            variant.sku,
            variant.product.name,
            REASON_OFFER_MARKED,
        )

    # ------------------------------------------------------------------
    # Категории
    # ------------------------------------------------------------------

    def _purge_categories(self, protected_category_pks: set[int]) -> dict[str, int]:
        """Пустые категории вне поддерева якоря, от листьев к корню.

        `Product.category` и `Category.parent` — CASCADE: удаление непустой
        категории снесло бы товары, а через них — позиции заказов. Поэтому
        удаляется только лист без товаров; категория с защищённым товаром и все
        её предки остаются.
        """
        from apps.products.models import Category

        outside = Category.objects.exclude(pk__in=self.subtree_pks)

        if not self.apply:
            return self._preview_categories(list(outside.order_by("pk")), protected_category_pks)

        deleted = 0
        failed: set[int] = set()
        while True:
            leaves = list(
                outside.filter(children__isnull=True, products__isnull=True).exclude(pk__in=failed).order_by("pk")
            )
            if not leaves:
                break
            for category in leaves:
                try:
                    with transaction.atomic():
                        category.delete()
                except Exception as exc:
                    failed.add(category.pk)
                    self._error(f"Не удалось удалить категорию onec_id={category.onec_id} '{category.name}': {exc}")
                    continue
                deleted += 1
                logger.info("Категория удалена: onec_id=%s name=%s", category.onec_id, category.name)

        kept = 0
        for category in outside.order_by("pk"):
            kept += 1
            logger.warning(
                "Категория вне дерева сохранена — в её ветке остались товары или подкатегории: onec_id=%s name=%s",
                category.onec_id,
                category.name,
            )
            self._out(f"  [категория сохранена] onec_id={category.onec_id} name={category.name!r}")

        return {"deleted": deleted, "kept": kept}

    def _preview_categories(self, outside: list[Any], protected_category_pks: set[int]) -> dict[str, int]:
        """Dry-run: после удаления товаров непустыми останутся только ветки с защищёнными товарами."""
        parent_of = {category.pk: category.parent_id for category in outside}
        kept_pks: set[int] = set()
        for category_pk in protected_category_pks:
            node: int | None = category_pk
            while node is not None and node in parent_of and node not in kept_pks:
                kept_pks.add(node)
                node = parent_of[node]

        previewed = 0
        deleted = 0
        for category in outside:
            if category.pk in kept_pks:
                self._out(f"  [категория сохранена] onec_id={category.onec_id} name={category.name!r}")
                continue
            deleted += 1
            if previewed < self.PREVIEW_LIMIT:
                previewed += 1
                self._out(f"  [категория к удалению] onec_id={category.onec_id} name={category.name!r}")

        if deleted > previewed:
            self._out(f"  ... и ещё {deleted - previewed} категори(й) к удалению")

        return {"deleted": deleted, "kept": len(kept_pks)}

    # ------------------------------------------------------------------
    # Общее
    # ------------------------------------------------------------------

    def _batches(self, pks: list[int]) -> Iterator[list[int]]:
        for start in range(0, len(pks), self.BATCH_SIZE):
            yield pks[start : start + self.BATCH_SIZE]

    def _delete_objects(self, objects: Iterable[Any], after_delete: Any) -> int:
        """Удалить пачку в одной транзакции; при сбое — повторить по одному.

        Ошибка одного объекта не останавливает команду: она попадает в лог и в
        счётчик ошибок, остальные объекты пачки удаляются.
        """
        # `delete()` обнуляет pk экземпляра, даже если транзакция потом
        # откатится, — для повтора по одному pk запоминаем заранее.
        pairs = [(obj.pk, obj) for obj in objects]
        if not pairs:
            return 0

        try:
            with transaction.atomic():
                for _, obj in pairs:
                    obj.delete()
        except Exception as exc:
            logger.warning("Сбой удаления пачки (%s объектов): %s — повтор по одному", len(pairs), exc)
        else:
            for _, obj in pairs:
                self._run_after_delete(after_delete, obj)
            return len(pairs)

        deleted = 0
        for pk, obj in pairs:
            obj.pk = pk
            try:
                with transaction.atomic():
                    obj.delete()
            except Exception as exc:
                self._error(f"Не удалось удалить {obj._meta.verbose_name} onec_id={obj.onec_id}: {exc}")
                continue
            deleted += 1
            self._run_after_delete(after_delete, obj)
        return deleted

    def _run_after_delete(self, after_delete: Any, obj: Any) -> None:
        try:
            after_delete(obj)
        except Exception as exc:
            self._error(f"Объект onec_id={obj.onec_id} удалён, но запись в реестр не удалась: {exc}")

    def _error(self, message: str) -> None:
        self.errors += 1
        logger.error(message)
        self.stdout.write(self.style.ERROR(message))

    def _out(self, message: str) -> None:
        self.stdout.write(message)

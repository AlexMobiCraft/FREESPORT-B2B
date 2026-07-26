"""Repair-команда для нового контракта публичного дерева категорий."""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID, is_repair_placeholder_category_name

FALLBACK_SLUG = "onec-unresolved-category"


class Command(BaseCommand):
    help = (
        "Восстанавливает якорь СПОРТ, переносит полезные root-категории под него "
        "и изолирует placeholder-категории без каскадного удаления товаров."
    )

    def add_arguments(self, parser):
        parser.add_argument("--execute", action="store_true", help="Выполнить изменения в БД")
        parser.add_argument(
            "--root-name",
            type=str,
            default=None,
            help="Имя якорной категории (override settings.ROOT_CATEGORY_NAME)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        from apps.products.models import Category, Product

        execute = bool(options.get("execute"))
        root_name = options.get("root_name") or getattr(settings, "ROOT_CATEGORY_NAME", "СПОРТ")

        anchor_qs = Category.objects.filter(name=root_name, parent__isnull=True)
        if anchor_qs.count() > 1:
            raise CommandError(
                f"Найдено более одного корневого якоря с именем '{root_name}'. "
                "Устраните дублирование вручную перед повторным запуском."
            )
        anchor = anchor_qs.first()
        placeholder_roots = list(
            Category.objects.filter(parent__isnull=True, name__startswith="Категория ").exclude(name=root_name)
        )
        placeholder_roots = [cat for cat in placeholder_roots if self._is_placeholder(cat)]
        public_roots = list(
            Category.objects.filter(parent__isnull=True)
            .exclude(name=root_name)
            .exclude(slug__in=[FALLBACK_SLUG, "uncategorized"])
        )
        public_roots = [cat for cat in public_roots if not self._is_placeholder(cat)]

        products_in_placeholders = 0
        for category in placeholder_roots:
            ids = self._descendant_ids(category)
            ids.add(category.pk)
            products_in_placeholders += Product.objects.filter(category_id__in=ids).count()

        anchor_status = "missing"
        if anchor:
            anchor_status = "active" if anchor.is_active else "inactive"
        mode = "DRY-RUN" if not execute else "EXECUTE"
        self.stdout.write(
            f"{mode}: anchor={anchor_status}, public_roots={len(public_roots)}, "
            f"placeholder_roots={len(placeholder_roots)}, "
            f"products_in_placeholders={products_in_placeholders}"
        )

        if not execute:
            for cat in placeholder_roots:
                self.stdout.write(f"  [placeholder] id={cat.pk} name={cat.name!r}")
                ids = self._descendant_ids(cat)
                ids.add(cat.pk)
                products_in_branch = list(
                    Product.objects.filter(category_id__in=ids).values_list("pk", "slug", "name")[:50]
                )
                total_in_branch = Product.objects.filter(category_id__in=ids).count()
                for pk, slug, prod_name in products_in_branch:
                    self.stdout.write(f"    [product] id={pk} slug={slug!r} name={prod_name!r}")
                if total_in_branch > len(products_in_branch):
                    self.stdout.write(
                        f"    ... и ещё {total_in_branch - len(products_in_branch)} товар(ов) в ветке"
                    )
            for cat in public_roots:
                self.stdout.write(f"  [public_root] id={cat.pk} name={cat.name!r}")
            return

        with transaction.atomic():
            if anchor is None:
                anchor = self._create_anchor(root_name)
            elif not anchor.is_active:
                anchor.is_active = True
                anchor.save(update_fields=["is_active"])
            fallback = self._get_fallback_category()

            public_reparented = 0
            for category in public_roots:
                if category.pk in {anchor.pk, fallback.pk}:
                    continue
                category.parent = anchor
                category.save(update_fields=["parent"])
                public_reparented += 1

            products_moved = 0
            placeholders_hidden = 0
            for category in placeholder_roots:
                ids = self._descendant_ids(category)
                ids.add(category.pk)
                if fallback.pk in ids:
                    # Защита от цикла: fallback уже вложен внутри placeholder-поддерева.
                    # Сначала переносим товары из поддерева (кроме самого fallback) в fallback,
                    # затем деактивируем все категории поддерева кроме fallback и отвязываем
                    # fallback от placeholder-родителя, чтобы он не остался в скрытой ветке.
                    products_moved += (
                        Product.objects.filter(category_id__in=ids)
                        .exclude(category_id=fallback.pk)
                        .update(category=fallback)
                    )
                    Category.objects.filter(pk__in=ids).exclude(pk=fallback.pk).update(is_active=False)
                    fallback.refresh_from_db(fields=["parent_id"])
                    if fallback.parent_id is not None:
                        fallback.parent = None
                        fallback.save(update_fields=["parent"])
                    placeholders_hidden += 1
                    continue
                products_moved += Product.objects.filter(category_id__in=ids).update(category=fallback)
                Category.objects.filter(pk__in=ids).update(is_active=False)
                if category.pk != fallback.pk:
                    category.parent = fallback
                    category.is_active = False
                    category.save(update_fields=["parent", "is_active"])
                    placeholders_hidden += 1

        self.stdout.write(
            "SUMMARY: "
            f"anchor={anchor.name}, public_reparented={public_reparented}, "
            f"placeholders_hidden={placeholders_hidden}, "
            f"products_moved_to_fallback={products_moved}"
        )

    def _is_placeholder(self, category: Any) -> bool:
        return is_repair_placeholder_category_name(category.name or "")

    def _create_anchor(self, root_name: str) -> Any:
        from apps.products.models import Category

        slug = self._unique_slug(slugify(root_name) or "sport")
        # Sentinel onec_id сигнализирует import-процессору о repair-created якоре,
        # чтобы он обновил его реальным onec_id вместо создания дублирующего root.
        return Category.objects.create(
            name=root_name,
            slug=slug,
            is_active=True,
            onec_id=REPAIR_ANCHOR_ONEC_ID,
        )

    def _get_fallback_category(self) -> Any:
        from apps.products.models import Category

        category, _ = Category.objects.get_or_create(
            slug=FALLBACK_SLUG,
            defaults={
                "name": "Техническая категория: неразрешенные ссылки 1С",
                "onec_id": "__onec_unresolved_category__",
                "is_active": False,
            },
        )
        if category.is_active:
            category.is_active = False
            category.save(update_fields=["is_active"])
        return category

    def _unique_slug(self, base_slug: str) -> str:
        from apps.products.models import Category

        slug = base_slug
        counter = 1
        while Category.objects.filter(slug=slug).exists():
            counter += 1
            slug = f"{base_slug}-{counter}"
        return slug

    def _descendant_ids(self, category: Any) -> set[int]:
        ids: set[int] = set()
        children = category.children.all()
        for child in children:
            ids.add(child.pk)
            ids.update(self._descendant_ids(child))
        return ids

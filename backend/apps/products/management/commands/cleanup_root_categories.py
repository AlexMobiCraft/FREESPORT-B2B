"""
Management команда для очистки корневых категорий после импорта из 1С.

Проблема: парсер groups.xml импортирует ВСЕ категории, включая корневую «СПОРТ»
и другие корневые категории. Эта команда:
1. Reparent дочерних СПОРТ → parent=None (они становятся корневыми на сайте)
2. Удаляет якорную категорию «СПОРТ»
3. Удаляет все оставшиеся посторонние корневые категории (CASCADE)

ВАЖНО: По умолчанию запускается в режиме --dry-run.
Для реального выполнения требуется флаг --execute.
"""

from __future__ import annotations

import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Очистка корневых категорий после импорта из 1С. "
        "Reparent подкатегорий СПОРТ, удаление якорной и посторонних категорий."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Режим просмотра без изменений (по умолчанию)",
        )
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Выполнить реальные изменения в БД",
        )
        parser.add_argument(
            "--root-name",
            type=str,
            default=None,
            help="Имя корневой категории (override settings.ROOT_CATEGORY_NAME)",
        )

    def handle(self, *args, **options):
        from apps.products.models import Category, HomepageCategory, Product

        execute = options.get("execute", False)
        root_name = options.get("root_name") or getattr(settings, "ROOT_CATEGORY_NAME", "СПОРТ")

        if not root_name:
            self.stderr.write(self.style.ERROR("❌ ROOT_CATEGORY_NAME не задан ни в settings, ни через --root-name"))
            return

        self.stdout.write(self.style.NOTICE(f"\n{'=' * 60}"))
        self.stdout.write(
            self.style.NOTICE(
                f"🔍 Cleanup Root Categories | "
                f"Якорная: «{root_name}» | "
                f"Режим: {'EXECUTE' if execute else 'DRY-RUN'}"
            )
        )
        self.stdout.write(self.style.NOTICE(f"{'=' * 60}\n"))

        # ======================================================================
        # ШАГ 1: Аудит — найти все корневые категории
        # ======================================================================
        root_categories = Category.objects.filter(parent=None)
        self.stdout.write(
            self.style.HTTP_INFO(f"📋 Шаг 1: Аудит корневых категорий (parent=None): " f"{root_categories.count()}")
        )

        for root_cat in root_categories:
            # Прямые children
            direct_children = Category.objects.filter(parent=root_cat).count()
            # Все потомки рекурсивно
            all_descendants = self._count_all_descendants(root_cat)
            # Товары привязанные к этой корневой
            products_on_root = Product.objects.filter(category=root_cat).count()
            # Товары привязанные ко всем потомкам
            descendant_ids = self._get_all_descendant_ids(root_cat)
            products_on_descendants = Product.objects.filter(category_id__in=descendant_ids).count()

            marker = "🎯" if root_cat.name == root_name else "🗑️"
            self.stdout.write(f"   {marker} «{root_cat.name}» (onec_id={root_cat.onec_id})")
            self.stdout.write(f"      Прямых children: {direct_children}, " f"всего потомков: {all_descendants}")
            self.stdout.write(
                f"      Товаров на корневой: {products_on_root}, " f"товаров на потомках: {products_on_descendants}"
            )

            # Проверка HomepageCategory
            homepage_count = HomepageCategory.objects.filter(Q(pk=root_cat.pk) | Q(pk__in=descendant_ids)).count()
            if homepage_count > 0:
                self.stdout.write(self.style.WARNING(f"      ⚠️ HomepageCategory записей: {homepage_count}"))

        # ======================================================================
        # ШАГ 2: Найти якорную категорию
        # ======================================================================
        anchor = root_categories.filter(name=root_name).first()
        if not anchor:
            self.stderr.write(
                self.style.WARNING(
                    f"\n⚠️ Якорная категория «{root_name}» не найдена среди " f"корневых. Ничего не делаем."
                )
            )
            return

        anchor_children = Category.objects.filter(parent=anchor)
        anchor_children_count = anchor_children.count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n✅ Якорная категория найдена: «{anchor.name}» " f"(pk={anchor.pk}, onec_id={anchor.onec_id})"
            )
        )
        self.stdout.write(f"   Прямых дочерних для reparent: {anchor_children_count}")

        # Другие корневые (кроме якорной)
        other_roots = root_categories.exclude(pk=anchor.pk)
        other_roots_count = other_roots.count()

        # Подсчёт каскадно удаляемых товаров от других корневых
        cascade_products = 0
        for other_root in other_roots:
            desc_ids = self._get_all_descendant_ids(other_root)
            desc_ids.add(other_root.pk)
            cascade_products += Product.objects.filter(category_id__in=desc_ids).count()

        # Товары на якорной напрямую
        anchor_direct_products = Product.objects.filter(category=anchor).count()

        if other_roots_count > 0:
            self.stdout.write(self.style.WARNING(f"\n🗑️ Другие корневые для удаления: {other_roots_count}"))
            if cascade_products > 0:
                self.stdout.write(self.style.WARNING(f"   ⚠️ CASCADE удалит {cascade_products} товаров!"))

        if anchor_direct_products > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"   ⚠️ {anchor_direct_products} товаров привязаны "
                    f"напрямую к «{root_name}» — будут удалены каскадно!"
                )
            )

        if not execute:
            self.stdout.write(
                self.style.WARNING(
                    "\n🔍 DRY-RUN: Изменения НЕ применены. " "Используйте --execute для реального запуска."
                )
            )
            return

        # ======================================================================
        # ШАГ 3-6: Выполнение (только с --execute)
        # ======================================================================
        reparented = 0
        categories_deleted = 0
        products_deleted_cascade = 0

        # ВАЖНО: материализуем PKs ДО reparent, иначе ленивый QuerySet
        # подхватит reparented children (у которых parent станет None)
        other_root_pks = list(Category.objects.filter(parent=None).exclude(pk=anchor.pk).values_list("pk", flat=True))

        with transaction.atomic():
            # Шаг 3: Reparent дочерних якорной
            reparented = Category.objects.filter(parent=anchor).update(parent=None)
            self.stdout.write(self.style.SUCCESS(f"\n✅ Шаг 3: Reparented {reparented} категорий → parent=None"))

            # Шаг 4: Удалить якорную (уже без children)
            anchor_products_deleted = Product.objects.filter(category=anchor).count()
            products_deleted_cascade += anchor_products_deleted
            anchor.delete()
            categories_deleted += 1
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Шаг 4: Удалена якорная «{root_name}» " f"(товаров удалено каскадно: {anchor_products_deleted})"
                )
            )

            # Шаг 5: Удалить все посторонние корневые
            # (other_root_pks вычислены ДО reparent — не содержат reparented children)
            if other_root_pks:
                for other_pk in other_root_pks:
                    try:
                        other_cat = Category.objects.get(pk=other_pk)
                        desc_ids = self._get_all_descendant_ids(other_cat)
                        desc_ids.add(other_cat.pk)
                        other_products = Product.objects.filter(category_id__in=desc_ids).count()
                        products_deleted_cascade += other_products

                        cat_name = other_cat.name
                        desc_count = len(desc_ids) - 1
                        other_cat.delete()  # CASCADE удалит потомков и товары
                        categories_deleted += 1 + desc_count

                        self.stdout.write(
                            f"   🗑️ Удалена «{cat_name}» "
                            f"(+{desc_count} потомков, "
                            f"{other_products} товаров каскадно)"
                        )
                    except Category.DoesNotExist:
                        pass  # Уже удалена каскадно

            self.stdout.write(self.style.SUCCESS(f"✅ Шаг 5: Удалено посторонних корневых: " f"{len(other_root_pks)}"))

        # ======================================================================
        # ШАГ 6: Итоговый отчёт
        # ======================================================================
        self.stdout.write(f"\n{'=' * 60}")
        self.stdout.write(self.style.SUCCESS("📊 ИТОГОВЫЙ ОТЧЁТ:"))
        self.stdout.write(f"   Категорий reparented:     {reparented}")
        self.stdout.write(f"   Категорий удалено:        {categories_deleted}")
        self.stdout.write(f"   Товаров удалено каскадно: {products_deleted_cascade}")
        remaining = Category.objects.filter(parent=None).count()
        self.stdout.write(f"   Корневых категорий сейчас: {remaining}")
        self.stdout.write(f"{'=' * 60}")

        logger.info(
            f"cleanup_root_categories: reparented={reparented}, "
            f"deleted={categories_deleted}, "
            f"cascade_products={products_deleted_cascade}"
        )

    def _count_all_descendants(self, category) -> int:
        """Рекурсивный подсчёт всех потомков категории."""
        from apps.products.models import Category

        count = 0
        children = Category.objects.filter(parent=category)
        for child in children:
            count += 1 + self._count_all_descendants(child)
        return count

    def _get_all_descendant_ids(self, category) -> set:
        """Рекурсивно собирает pk всех потомков категории."""
        from apps.products.models import Category

        ids = set()
        children = Category.objects.filter(parent=category)
        for child in children:
            ids.add(child.pk)
            ids.update(self._get_all_descendant_ids(child))
        return ids

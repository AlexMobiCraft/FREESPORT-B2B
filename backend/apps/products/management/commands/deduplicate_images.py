"""
Management команда для удаления дублированных и мелких изображений в базе данных.

Использование:
    python manage.py deduplicate_images                  # Очистка всех дублей
    python manage.py deduplicate_images --dry-run       # Тестовый запуск
    python manage.py deduplicate_images --verbose       # Подробный вывод
    python manage.py deduplicate_images --min-size 100  # Удалить файлы меньше 100KB

Описание проблемы:
    Из-за бага в импорте, одно изображение могло сохраняться с разными путями:
    - products/base/import_files/41cae745...jpg
    - products/base/41/41cae745...jpg

    Эта команда удаляет дубликаты, оставляя только первый путь для каждого
    уникального filename.
    Также удаляет изображения меньше указанного размера (по умолчанию 100KB).

    Дополнительно проверяется размер main_image у вариантов товара:
    - Если main_image меньше минимального размера И в gallery_images есть
      файл >= min_size, то main_image заменяется на первый подходящий файл
      из галереи.
"""

import logging
import os
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand
from django.db import models
from tqdm import tqdm

from apps.products.models import Product, ProductVariant

logger = logging.getLogger(__name__)

# Минимальный размер файла в KB (по умолчанию 100KB)
DEFAULT_MIN_SIZE_KB = 100


class Command(BaseCommand):
    """Удаление дублированных путей изображений в Product и ProductVariant."""

    help = "Удаление дублированных и мелких изображений в базе данных"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Добавление аргументов командной строки."""
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без записи изменений в базу",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод обнаруженных дублей",
        )
        parser.add_argument(
            "--prefer-new-path",
            action="store_true",
            help=("Предпочитать новый формат пути (XX/...) вместо старого " "(import_files/...)"),
        )
        parser.add_argument(
            "--min-size",
            type=int,
            default=DEFAULT_MIN_SIZE_KB,
            help=(
                f"Минимальный размер файла в KB (по умолчанию "
                f"{DEFAULT_MIN_SIZE_KB}KB). Файлы меньше этого размера будут "
                "удалены из списка."
            ),
        )
        parser.add_argument(
            "--skip-size-check",
            action="store_true",
            help="Пропустить проверку размера файлов",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основной метод выполнения команды."""
        dry_run = options.get("dry_run", False)
        verbose = options.get("verbose", False)
        prefer_new_path = options.get("prefer_new_path", False)
        min_size_kb = options.get("min_size", DEFAULT_MIN_SIZE_KB)
        skip_size_check = options.get("skip_size_check", False)

        self.stdout.write(
            self.style.SUCCESS(f"\n{'=' * 60}\n" f"  Дедупликация изображений в базе данных\n" f"{'=' * 60}\n")
        )

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 Режим DRY-RUN: изменения НЕ будут сохранены\n"))

        if not skip_size_check:
            self.stdout.write(f"📏 Минимальный размер файла: {min_size_kb}KB\n")

        # Обработка Product.base_images
        products_result = self._deduplicate_products(dry_run, verbose, prefer_new_path, min_size_kb, skip_size_check)

        # Обработка ProductVariant.gallery_images
        variants_result = self._deduplicate_variants(dry_run, verbose, prefer_new_path, min_size_kb, skip_size_check)

        # Итоговая статистика
        self._print_summary(products_result, variants_result, dry_run)

    def _get_file_size_kb(self, image_path: str) -> float | None:
        """
        Получить размер файла в KB.

        Args:
            image_path: Относительный путь к файлу в MEDIA_ROOT

        Returns:
            Размер в KB или None если файл не найден
        """
        try:
            if default_storage.exists(image_path):
                size_bytes = default_storage.size(image_path)
                return size_bytes / 1024
            return None
        except Exception as e:
            logger.debug(f"Error getting file size for {image_path}: {e}")
            return None

    def _deduplicate_products(
        self,
        dry_run: bool,
        verbose: bool,
        prefer_new_path: bool,
        min_size_kb: int,
        skip_size_check: bool,
    ) -> dict:
        """
        Дедупликация Product.base_images.

        Returns:
            Dict со статистикой
        """
        self.stdout.write("\n📦 Обработка Product.base_images...")

        products = Product.objects.exclude(base_images__isnull=True).exclude(base_images=[])
        total = products.count()

        if total == 0:
            self.stdout.write("   Нет товаров с изображениями")
            return {"total": 0, "with_duplicates": 0, "removed": 0, "small_removed": 0}

        with_duplicates = 0
        total_removed = 0
        small_removed = 0

        with tqdm(
            total=total,
            desc="   Товары",
            unit="шт",
            disable=not self.stdout.isatty(),
        ) as pbar:
            for product in products.iterator(chunk_size=100):
                original_images = product.base_images or []

                # Шаг 1: Фильтрация по размеру
                filtered_images = original_images
                small_files = []

                if not skip_size_check:
                    filtered_images = []
                    for img_path in original_images:
                        size_kb = self._get_file_size_kb(img_path)
                        if size_kb is not None and size_kb < min_size_kb:
                            small_files.append((img_path, size_kb))
                        else:
                            filtered_images.append(img_path)

                    # Если после фильтрации не осталось изображений,
                    # оставляем первое (даже маленькое)
                    if len(filtered_images) == 0 and len(original_images) > 0:
                        # Возвращаем первое изображение
                        filtered_images = [original_images[0]]
                        # Убираем его из списка мелких
                        small_files = [(p, s) for p, s in small_files if p != original_images[0]]

                    small_removed += len(small_files)

                # Шаг 2: Дедупликация
                deduplicated = self._deduplicate_list(filtered_images, prefer_new_path)

                removed_count = len(original_images) - len(deduplicated)

                if removed_count > 0:
                    with_duplicates += 1
                    total_removed += removed_count

                    if verbose:
                        self.stdout.write(f"\n   [{product.onec_id}] {product.name}:")
                        self.stdout.write(f"      Было: {len(original_images)}")
                        self.stdout.write(f"      Стало: {len(deduplicated)}")
                        self.stdout.write(f"      Удалено: {removed_count}")

                        # Показать удалённые мелкие файлы
                        for img_path, size_kb in small_files:
                            self.stdout.write(
                                self.style.ERROR(f"      ❌ {img_path} ({size_kb:.1f}KB < " f"{min_size_kb}KB)")
                            )

                        # Показать удалённые дубли
                        kept_set = set(deduplicated)
                        removed_as_dups = [img for img in filtered_images if img not in kept_set]
                        for img in removed_as_dups:
                            self.stdout.write(self.style.WARNING(f"      - {img} (дубликат)"))

                    if not dry_run:
                        product.base_images = deduplicated
                        product.save(update_fields=["base_images"])

                pbar.update(1)

        return {
            "total": total,
            "with_duplicates": with_duplicates,
            "removed": total_removed,
            "small_removed": small_removed,
        }

    def _deduplicate_variants(
        self,
        dry_run: bool,
        verbose: bool,
        prefer_new_path: bool,
        min_size_kb: int,
        skip_size_check: bool,
    ) -> dict:
        """
        Дедупликация ProductVariant.gallery_images.

        Returns:
            Dict со статистикой
        """
        self.stdout.write("\n🎨 Обработка ProductVariant.gallery_images и main_image...")

        # Выбираем варианты с галереей ИЛИ с main_image (для проверки размера)
        variants = ProductVariant.objects.filter(
            models.Q(gallery_images__isnull=False) & ~models.Q(gallery_images=[])
            | models.Q(main_image__isnull=False) & ~models.Q(main_image="")
        ).distinct()
        total = variants.count()

        if total == 0:
            self.stdout.write("   Нет вариантов с изображениями")
            return {
                "total": 0,
                "with_duplicates": 0,
                "removed": 0,
                "small_removed": 0,
                "main_image_replaced": 0,
            }

        with_duplicates = 0
        total_removed = 0
        small_removed = 0
        main_image_replaced = 0

        with tqdm(
            total=total,
            desc="   Варианты",
            unit="шт",
            disable=not self.stdout.isatty(),
        ) as pbar:
            for variant in variants.iterator(chunk_size=100):
                original_images = variant.gallery_images or []
                variant_modified = False
                new_main_image = None
                old_main_image_path = None
                main_image_replacement_info = None

                # Шаг 0: Проверка размера main_image
                if not skip_size_check and variant.main_image:
                    main_image_path = str(variant.main_image)
                    if main_image_path:
                        main_size_kb = self._get_file_size_kb(main_image_path)

                        if main_size_kb is not None and main_size_kb < min_size_kb:
                            # main_image маленький - ищем замену в gallery_images
                            if original_images and len(original_images) > 0:
                                for gallery_img in original_images:
                                    gallery_size_kb = self._get_file_size_kb(gallery_img)
                                    if gallery_size_kb is not None and gallery_size_kb >= min_size_kb:
                                        # Нашли подходящую замену
                                        new_main_image = gallery_img
                                        old_main_image_path = main_image_path
                                        main_image_replacement_info = (
                                            main_image_path,
                                            main_size_kb,
                                            gallery_img,
                                            gallery_size_kb,
                                        )
                                        variant_modified = True
                                        main_image_replaced += 1
                                        break

                # Шаг 1: Фильтрация по размеру
                filtered_images = original_images
                small_files = []

                # Если мы нашли замену для main_image, удаляем её из списка галереи
                if new_main_image:
                    filtered_images = [img for img in original_images if img != new_main_image]
                    original_images = filtered_images  # Обновляем для подсчёта removed_count

                if not skip_size_check:
                    temp_filtered = []
                    for img_path in filtered_images:
                        size_kb = self._get_file_size_kb(img_path)
                        if size_kb is not None and size_kb < min_size_kb:
                            small_files.append((img_path, size_kb))
                        else:
                            temp_filtered.append(img_path)
                    filtered_images = temp_filtered

                    # Если после фильтрации не осталось изображений,
                    # оставляем первое (даже маленькое)
                    if len(filtered_images) == 0 and len(variant.gallery_images or []) > 0:
                        # Возвращаем первое изображение (если не использовано
                        # как main_image)
                        fallback_images = [img for img in (variant.gallery_images or []) if img != new_main_image]
                        if fallback_images:
                            filtered_images = [fallback_images[0]]
                            # Убираем его из списка мелких
                            small_files = [(p, s) for p, s in small_files if p != fallback_images[0]]

                    small_removed += len(small_files)

                # Учитываем main_image при дедупликации
                main_image = variant.main_image
                seen_filenames = set()

                # Используем новый main_image если есть замена, иначе текущий
                effective_main_image = new_main_image if new_main_image else (str(main_image) if main_image else "")
                if effective_main_image:
                    main_filename = Path(effective_main_image).name
                    if main_filename:
                        seen_filenames.add(main_filename)

                deduplicated = self._deduplicate_list(filtered_images, prefer_new_path, seen_filenames)

                # Сравниваем с оригинальными gallery_images (без
                # перемещённого в main_image)
                compare_original = [img for img in (variant.gallery_images or []) if img != new_main_image]
                removed_count = len(compare_original) - len(deduplicated)

                if removed_count > 0 or variant_modified:
                    if removed_count > 0:
                        with_duplicates += 1
                        total_removed += removed_count

                    if verbose:
                        self.stdout.write(f"\n   [{variant.onec_id}] SKU: {variant.sku}:")

                        # Показать замену main_image
                        if main_image_replacement_info:
                            (
                                old_path,
                                old_size,
                                new_path,
                                new_size,
                            ) = main_image_replacement_info
                            self.stdout.write(
                                self.style.WARNING(
                                    f"      🔄 main_image заменён: "
                                    f"{Path(old_path).name} ({old_size:.1f}KB) "
                                    f"→ {Path(new_path).name} ({new_size:.1f}KB)"
                                )
                            )

                        if removed_count > 0:
                            self.stdout.write(f"      Галерея было: {len(compare_original)}")
                            self.stdout.write(f"      Галерея стало: {len(deduplicated)}")
                            self.stdout.write(f"      Удалено: {removed_count}")

                        # Показать удалённые мелкие файлы
                        for img_path, size_kb in small_files:
                            self.stdout.write(
                                self.style.ERROR(f"      ❌ {img_path} ({size_kb:.1f}KB < " f"{min_size_kb}KB)")
                            )

                    if not dry_run:
                        update_fields = []
                        if new_main_image:
                            variant.main_image = new_main_image
                            update_fields.append("main_image")
                        if removed_count > 0 or new_main_image:
                            variant.gallery_images = deduplicated
                            update_fields.append("gallery_images")
                        if update_fields:
                            variant.save(update_fields=update_fields)

                pbar.update(1)

        return {
            "total": total,
            "with_duplicates": with_duplicates,
            "removed": total_removed,
            "small_removed": small_removed,
            "main_image_replaced": main_image_replaced,
        }

    def _deduplicate_list(
        self,
        image_paths: list[str],
        prefer_new_path: bool = False,
        initial_seen: set[str] | None = None,
    ) -> list[str]:
        """
        Удаление дублей из списка путей по filename.

        Args:
            image_paths: Список путей к изображениям
            prefer_new_path: Если True, предпочитать пути без 'import_files/'
            initial_seen: Начальный набор уже виденных filename'ов

        Returns:
            Дедуплицированный список
        """
        seen_filenames: set[str] = set(initial_seen) if initial_seen else set()
        result: list[str] = []

        # Группируем по filename
        by_filename: dict[str, list[str]] = {}
        for path in image_paths:
            filename = Path(path).name if path else ""
            if filename:
                if filename not in by_filename:
                    by_filename[filename] = []
                by_filename[filename].append(path)

        # Выбираем один путь для каждого filename
        for filename, paths in by_filename.items():
            if filename in seen_filenames:
                continue

            if len(paths) == 1:
                result.append(paths[0])
            else:
                # Есть дубли - выбираем один
                if prefer_new_path:
                    # Предпочитаем путь БЕЗ import_files/
                    chosen = None
                    for p in paths:
                        if "import_files" not in p:
                            chosen = p
                            break
                    if chosen is None:
                        chosen = paths[0]
                else:
                    # По умолчанию берём первый
                    chosen = paths[0]

                result.append(chosen)

            seen_filenames.add(filename)

        return result

    def _print_summary(
        self,
        products_result: dict[str, int],
        variants_result: dict[str, int],
        dry_run: bool,
    ) -> None:
        """Вывод итоговой статистики."""
        status_msg = "✅ Дедупликация завершена" if not dry_run else "🔍 DRY-RUN завершён"
        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}\n" f"  {status_msg}\n" f"{'=' * 60}\n"))

        self.stdout.write("📊 Статистика Product.base_images:")
        self.stdout.write(f"   • Всего товаров с изображениями: {products_result['total']}")
        self.stdout.write(f"   • Товаров с дублями/мелкими: {products_result['with_duplicates']}")
        self.stdout.write(
            self.style.SUCCESS(f"   • Удалено записей: {products_result['removed']}")
            if products_result["removed"] > 0
            else "   • Удалено записей: 0"
        )
        if products_result.get("small_removed", 0) > 0:
            self.stdout.write(self.style.ERROR(f"   • Из них мелких файлов: {products_result['small_removed']}"))

        self.stdout.write("\n📊 Статистика ProductVariant.gallery_images и main_image:")
        self.stdout.write(f"   • Всего вариантов с изображениями: {variants_result['total']}")
        self.stdout.write(f"   • Вариантов с дублями/мелкими: {variants_result['with_duplicates']}")
        self.stdout.write(
            self.style.SUCCESS(f"   • Удалено записей из галереи: {variants_result['removed']}")
            if variants_result["removed"] > 0
            else "   • Удалено записей из галереи: 0"
        )
        if variants_result.get("small_removed", 0) > 0:
            self.stdout.write(self.style.ERROR(f"   • Из них мелких файлов: {variants_result['small_removed']}"))
        if variants_result.get("main_image_replaced", 0) > 0:
            self.stdout.write(
                self.style.WARNING(f"   • Заменено main_image: " f"{variants_result['main_image_replaced']}")
            )

        total_removed = products_result["removed"] + variants_result["removed"]
        total_small = products_result.get("small_removed", 0) + variants_result.get("small_removed", 0)

        self.stdout.write(self.style.SUCCESS(f"\n🎯 Всего удалено записей: {total_removed}"))
        if total_small > 0:
            self.stdout.write(self.style.ERROR(f"   Из них мелких файлов (<100KB): {total_small}"))

        if dry_run and total_removed > 0:
            self.stdout.write(
                self.style.WARNING(
                    "\n⚠️  Это был тестовый запуск. " "Запустите без --dry-run для сохранения изменений."
                )
            )

        self.stdout.write("")

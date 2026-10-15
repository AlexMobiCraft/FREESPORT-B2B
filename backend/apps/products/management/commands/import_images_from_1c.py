"""
Management команда для импорта изображений товаров из 1С.

Использование:
    python manage.py import_images_from_1c                  # Импорт всех изображений
    python manage.py import_images_from_1c --dry-run       # Тестовый запуск
    python manage.py import_images_from_1c --limit 100     # Только первые 100 товаров
"""

import logging
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from tqdm import tqdm

from apps.products.models import ImportSession, Product
from apps.products.services.variant_import import VariantImportProcessor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Импорт изображений товаров из директории 1С.

    Использует то же поведение что и пункт меню "Только изображения товаров"
    в Django Admin (https://optisport.ru/admin/integrations/import_1c/).
    """

    help = "Импорт изображений товаров из директории 1С"

    def add_arguments(self, parser):
        """Добавление аргументов командной строки."""
        parser.add_argument(
            "--data-dir",
            type=str,
            default=None,
            help="Директория с данными 1С (по умолчанию из settings.ONEC_DATA_DIR)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без записи изображений",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help="Ограничить количество обрабатываемых товаров",
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            help="Подробный вывод в консоль",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основной метод выполнения команды."""
        data_dir = options.get("data_dir")
        dry_run = options.get("dry_run", False)
        limit = options.get("limit")
        verbose = options.get("verbose", False)

        # Получаем директорию с данными
        if data_dir is None:
            data_dir = getattr(settings, "ONEC_DATA_DIR", None)
            if not data_dir:
                raise CommandError(
                    "Настройка ONEC_DATA_DIR не найдена в settings. "
                    "Укажите директорию через --data-dir или настройте ONEC_DATA_DIR."
                )

        # Проверяем директорию изображений
        base_dir = Path(data_dir) / "goods" / "import_files"
        if not base_dir.exists():
            raise CommandError(
                f"Директория изображений не найдена: {base_dir}\n" "Убедитесь что данные из 1С синхронизированы."
            )

        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}\n" f"  Импорт изображений товаров из 1С\n" f"{'=' * 60}\n"))

        if dry_run:
            self.stdout.write(self.style.WARNING("🔍 Режим DRY-RUN: изображения НЕ будут записаны\n"))

        self.stdout.write(f"📁 Директория изображений: {base_dir}")

        # Создаём сессию импорта
        session = None
        if not dry_run:
            session = ImportSession.objects.create(
                import_type=ImportSession.ImportType.IMAGES,
                status=ImportSession.ImportStatus.IN_PROGRESS,
            )
            self.stdout.write(f"📋 Создана сессия импорта: {session.id}")

        try:
            result = self._run_import(
                base_dir=base_dir,
                session=session,
                dry_run=dry_run,
                limit=limit,
                verbose=verbose,
            )

            # Обновляем сессию
            if session:
                session.status = ImportSession.ImportStatus.COMPLETED
                session.finished_at = timezone.now()
                session.report_details = result
                session.save(update_fields=["status", "finished_at", "report_details"])

            self._print_summary(result)

        except Exception as e:
            logger.error(f"Ошибка импорта изображений: {e}", exc_info=True)

            if session:
                session.status = ImportSession.ImportStatus.FAILED
                session.finished_at = timezone.now()
                session.error_message = str(e)
                session.save(update_fields=["status", "finished_at", "error_message"])

            raise CommandError(f"Ошибка импорта: {e}")

    def _run_import(
        self,
        base_dir: Path,
        session: ImportSession | None,
        dry_run: bool,
        limit: int | None,
        verbose: bool,
    ) -> dict:
        """
        Выполнение импорта изображений.

        Args:
            base_dir: Путь к директории import_files
            session: Сессия импорта (или None для dry-run)
            dry_run: Тестовый запуск без записи
            limit: Лимит товаров для обработки
            verbose: Подробный вывод

        Returns:
            Dict со статистикой импорта
        """
        # Получаем товары с onec_id
        products_qs = Product.objects.filter(is_active=True, onec_id__isnull=False).exclude(onec_id="")

        if limit:
            products_qs = products_qs[:limit]
            self.stdout.write(f"⚠️  Лимит: обработка только {limit} товаров\n")

        total_products = products_qs.count()
        self.stdout.write(f"📦 Найдено товаров: {total_products}\n")

        if total_products == 0:
            return {
                "total_products": 0,
                "processed": 0,
                "copied": 0,
                "skipped": 0,
                "errors": 0,
            }

        # Создаём процессор
        processor = VariantImportProcessor(session_id=session.id if session else 0)

        processed = 0
        total_copied = 0
        total_skipped = 0
        total_errors = 0

        # Прогресс бар
        with tqdm(
            total=total_products,
            desc="Импорт изображений",
            unit="товар",
            disable=not self.stdout.isatty(),
        ) as pbar:
            for product in products_qs.iterator(chunk_size=100):
                try:
                    # Получаем изображения для товара
                    image_paths = self._get_product_images(product, base_dir)

                    if not image_paths:
                        total_skipped += 1
                        processed += 1
                        pbar.update(1)
                        continue

                    if verbose:
                        self.stdout.write(f"  [{product.onec_id}] {product.name}: " f"{len(image_paths)} изображений")

                    if not dry_run:
                        # Импорт в base_images
                        processor._import_base_images(
                            product=product,
                            image_paths=image_paths,
                            base_dir=str(base_dir),
                        )

                        # Импорт в первый ProductVariant
                        first_variant = product.variants.first()
                        if first_variant:
                            processor._import_variant_images(
                                variant=first_variant,
                                image_paths=image_paths,
                                base_dir=str(base_dir),
                            )

                    total_copied += len(image_paths)
                    processed += 1

                except Exception as e:
                    if verbose:
                        self.stdout.write(self.style.ERROR(f"  ❌ Ошибка [{product.onec_id}]: {e}"))
                    logger.error(f"Ошибка обработки товара {product.id} " f"(onec_id: {product.onec_id}): {e}")
                    total_errors += 1
                    processed += 1

                pbar.update(1)

                # Периодическое обновление сессии
                if session and processed % 50 == 0:
                    session.report_details = {
                        "total_products": total_products,
                        "processed": processed,
                        "copied": total_copied,
                        "skipped": total_skipped,
                        "errors": total_errors,
                        "last_updated": timezone.now().isoformat(),
                    }
                    session.save(update_fields=["report_details"])

        return {
            "total_products": total_products,
            "processed": processed,
            "copied": total_copied,
            "skipped": total_skipped,
            "errors": total_errors,
            "completed_at": timezone.now().isoformat(),
        }

    def _get_product_images(self, product: Product, base_dir: Path) -> list[str]:
        """
        Получить список изображений для товара из директории 1С.

        Args:
            product: Product instance с onec_id
            base_dir: Путь к goods/import_files/

        Returns:
            Список относительных путей (например, ["00/001a16a4_image.jpg"])
        """
        if not product.onec_id:
            return []

        # Первые 2 символа onec_id определяют поддиректорию
        onec_id = product.onec_id
        subdir = onec_id[:2] if len(onec_id) >= 2 else "00"

        images_dir = base_dir / subdir

        if not images_dir.exists():
            return []

        # Поиск файлов начинающихся с onec_id
        image_paths = []
        for img_file in images_dir.glob(f"{onec_id}*"):
            if img_file.suffix.lower() in [".jpg", ".jpeg", ".png"]:
                relative_path = f"{subdir}/{img_file.name}"
                image_paths.append(relative_path)

        return image_paths

    def _print_summary(self, result: dict[str, int]) -> None:
        """Вывод итоговой статистики."""
        self.stdout.write(self.style.SUCCESS(f"\n{'=' * 60}\n" f"  ✅ Импорт изображений завершён\n" f"{'=' * 60}\n"))
        self.stdout.write("📊 Статистика:")
        self.stdout.write(f"   • Всего товаров: {result['total_products']}")
        self.stdout.write(f"   • Обработано: {result['processed']}")
        self.stdout.write(self.style.SUCCESS(f"   • Изображений скопировано: {result['copied']}"))
        self.stdout.write(f"   • Пропущено (без изображений): {result['skipped']}")

        if result["errors"] > 0:
            self.stdout.write(self.style.ERROR(f"   • Ошибок: {result['errors']}"))
        else:
            self.stdout.write(f"   • Ошибок: {result['errors']}")

        self.stdout.write("")

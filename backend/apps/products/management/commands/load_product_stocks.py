"""
Management команда для обновления остатков товаров из файла rests.xml

Story 3.1.5: Команда для обновления остатков товаров
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.products.models import ImportSession, Product, ProductVariant
from apps.products.services.parser import XMLDataParser

if TYPE_CHECKING:
    from argparse import ArgumentParser


class Command(BaseCommand):
    """
    Обновляет остатки товаров из файла rests.xml

    Использует XMLDataParser.parse_rests_xml() для чтения данных.
    Создает ImportSession для логирования операции.
    Поддерживает dry-run режим и batch processing.
    """

    help = "Обновляет остатки товаров из файла rests.xml"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Добавление аргументов команды"""
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Путь к файлу rests.xml",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=1000,
            help="Размер пакета для bulk_update (по умолчанию: 1000)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без сохранения в БД",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основная логика команды"""
        file_path: str = options["file"]
        batch_size: int = options["batch_size"]
        dry_run: bool = options["dry_run"]

        # Валидация входных данных
        if not os.path.exists(file_path):
            raise CommandError(f"Файл не найден: {file_path}")

        if batch_size <= 0:
            raise CommandError(f"Некорректный размер пакета: {batch_size}. Должен быть > 0.")

        if dry_run:
            self.stdout.write(self.style.WARNING("РЕЖИМ ТЕСТИРОВАНИЯ: изменения не будут сохранены."))

        # Создание сессии импорта
        session = ImportSession.objects.create(import_type=ImportSession.ImportType.STOCKS)
        self.stdout.write(f"Начата сессия обновления остатков #{session.pk}...")

        updated_count = 0
        not_found_count = 0
        skipped_count = 0
        not_found_skus: list[str] = []

        try:
            # Парсинг файла
            parser = XMLDataParser()
            stock_data = parser.parse_rests_xml(file_path)

            # Валидация результата парсинга
            if not stock_data:
                self.stdout.write(self.style.WARNING("Файл пуст или не содержит данных об остатках."))
                session.status = ImportSession.ImportStatus.COMPLETED
                session.report_details = {
                    "warning": "Empty file",
                    "total_records": 0,
                    "updated_count": 0,
                }
                session.finished_at = timezone.now()
                session.save()
                return

            total_records = len(stock_data)
            self.stdout.write(f"Найдено записей: {total_records}")

            with transaction.atomic():
                variants_to_update: list[ProductVariant] = []
                current_time = timezone.now()

                for item in stock_data:
                    onec_id = item.get("id")  # parse_rests_xml возвращает 'id'
                    quantity = item.get("quantity", 0)

                    # Валидация данных записи
                    if not onec_id:
                        skipped_count += 1
                        self.stdout.write(self.style.WARNING("Пропущена запись без onec_id"))
                        continue

                    if quantity < 0:
                        skipped_count += 1
                        self.stdout.write(
                            self.style.WARNING(
                                f"Пропущена запись с некорректным количеством: " f"{onec_id} (quantity={quantity})"
                            )
                        )
                        continue

                    # Поиск варианта по onec_id
                    try:
                        variant = ProductVariant.objects.get(onec_id=onec_id)
                        variant.stock_quantity = quantity
                        variant.last_sync_at = current_time
                        variants_to_update.append(variant)
                        updated_count += 1
                    except ProductVariant.DoesNotExist:
                        not_found_count += 1
                        not_found_skus.append(onec_id)
                        self.stdout.write(self.style.WARNING(f"Вариант не найден: {onec_id}"))

                # Массовое обновление с batch processing
                if variants_to_update:
                    for i in range(0, len(variants_to_update), batch_size):
                        batch = variants_to_update[i : i + batch_size]
                        ProductVariant.objects.bulk_update(batch, ["stock_quantity", "last_sync_at"])
                        self.stdout.write(
                            f"Обновлено {min(i + batch_size, len(variants_to_update))} "
                            f"из {len(variants_to_update)} вариантов"
                        )

                # Откат транзакции в режиме dry-run
                if dry_run:
                    transaction.set_rollback(True)
                    self.stdout.write(self.style.SUCCESS("ТЕСТИРОВАНИЕ: транзакция откатана, изменения не сохранены."))

            # Обновление сессии при успехе
            session.status = ImportSession.ImportStatus.COMPLETED
            session.report_details = {
                "file_path": file_path,
                "total_records": total_records,
                "updated_count": updated_count,
                "not_found_count": not_found_count,
                "skipped_count": skipped_count,
                "not_found_skus": not_found_skus[:100],  # Ограничение для больших списков
                "batch_size": batch_size,
                "dry_run": dry_run,
                "duration_seconds": (timezone.now() - session.started_at).total_seconds(),
            }
            self.stdout.write(
                self.style.SUCCESS(
                    f"Обновление остатков завершено. "
                    f"Обновлено: {updated_count}, "
                    f"Не найдено: {not_found_count}, "
                    f"Пропущено: {skipped_count}"
                )
            )

        except Exception as e:
            session.status = ImportSession.ImportStatus.FAILED
            session.error_message = str(e)
            self.stderr.write(self.style.ERROR(f"Ошибка во время обновления: {e}"))
            raise

        finally:
            session.finished_at = timezone.now()
            session.save()
            self.stdout.write(f"Сессия #{session.pk} завершена со статусом '{session.status}'.")

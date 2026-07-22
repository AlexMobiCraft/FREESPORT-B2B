"""
Django management команда для импорта клиентов из 1С (contragents*.xml)
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.products.models import ImportSession
from apps.users.models import User
from apps.users.services.parser import CustomerDataParser
from apps.users.services.processor import CustomerDataProcessor

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Импортирует клиентов из директории с файлами 1С (contragents*.xml).

    Аналогично команде import_catalog_from_1c, обрабатывает все файлы
    в директории автоматически.

    Использует архитектуру Парсер/Процессор для гибкости.
    Создает ImportSession для отслеживания импорта.
    Логирует детали операций в CustomerSyncLog.
    """

    help = "Импортирует клиентов из директории с файлами 1С (contragents*.xml)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--data-dir",
            type=str,
            required=True,
            help=("Путь к директории с данными 1С (содержит поддиректорию " "contragents/)."),
        )
        parser.add_argument(
            "--chunk-size",
            type=int,
            default=100,
            help="Размер пакета для обработки (по умолчанию: 100).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без сохранения данных.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        data_dir = options["data_dir"]
        chunk_size = options["chunk_size"]
        dry_run = options["dry_run"]

        # Валидация входных данных
        data_path = Path(data_dir)
        if not data_path.exists():
            raise CommandError(f"Директория не найдена: {data_dir}")

        # Проверяем наличие поддиректории contragents
        contragents_dir = data_path / "contragents"
        if not contragents_dir.exists():
            raise CommandError(
                f"Поддиректория contragents не найдена в {data_dir}. "
                f"Структура должна быть: {data_dir}/contragents/contragents*.xml"
            )

        # Находим все файлы contragents*.xml
        contragents_files = sorted(contragents_dir.glob("contragents*.xml"))
        if not contragents_files:
            raise CommandError(
                f"Файлы contragents*.xml не найдены в {contragents_dir}. " f"Убедитесь, что данные из 1С выгружены."
            )

        if chunk_size <= 0:
            raise CommandError("chunk-size должен быть положительным числом.")

        self.stdout.write(self.style.SUCCESS(f"Найдено {len(contragents_files)} файлов контрагентов для импорта"))

        # Проверяем наличие активной сессии (созданной из views.py)
        # Если есть - используем ее, если нет - создаем новую
        session = (
            ImportSession.objects.filter(
                import_type=ImportSession.ImportType.CUSTOMERS,
                status=ImportSession.ImportStatus.STARTED,
            )
            .order_by("-started_at")
            .first()
        )

        session_created_here = False
        if session:
            self.stdout.write(self.style.SUCCESS(f"Используется существующая сессия импорта #{session.pk}"))
        else:
            # Создаем новую сессию если нет активной
            session = ImportSession.objects.create(
                import_type=ImportSession.ImportType.CUSTOMERS,
                status=ImportSession.ImportStatus.STARTED,
            )
            session_created_here = True
            self.stdout.write(self.style.SUCCESS(f"Создана новая сессия импорта #{session.pk}"))

        try:
            # Парсер и процессор
            parser = CustomerDataParser()
            processor = CustomerDataProcessor(session_id=session.pk)

            # Обрабатываем каждый файл
            total_stats = {
                "total": 0,
                "created": 0,
                "updated": 0,
                "skipped": 0,
                "errors": 0,
            }

            for idx, file_path in enumerate(contragents_files, 1):
                self.stdout.write(
                    self.style.SUCCESS(f"\n[{idx}/{len(contragents_files)}] " f"Обработка файла: {file_path.name}")
                )

                try:
                    with transaction.atomic():
                        # Парсинг данных из XML
                        self.stdout.write("  Парсинг файла...")
                        customer_data = parser.parse(str(file_path))

                        self.stdout.write(self.style.SUCCESS(f"  Распознано {len(customer_data)} клиентов"))

                        # Обработка данных
                        self.stdout.write("  Обработка клиентов...")
                        result = processor.process_customers(customer_data, chunk_size=chunk_size)

                        # Суммируем статистику
                        for key in total_stats.keys():
                            total_stats[key] += result.get(key, 0)

                        # Вывод статистики по файлу
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"  ✅ Файл обработан: создано={result['created']}, "
                                f"обновлено={result['updated']}, "
                                f"пропущено={result['skipped']}, "
                                f"ошибок={result['errors']}"
                            )
                        )

                        # Dry-run режим
                        if dry_run:
                            transaction.set_rollback(True)

                except Exception as e:
                    error_msg = f"Ошибка обработки файла {file_path.name}: {e}"
                    logger.error(error_msg, exc_info=True)
                    self.stdout.write(self.style.ERROR(f"  ❌ {error_msg}"))
                    # Продолжаем обработку остальных файлов
                    total_stats["errors"] += 1

            # Dry-run сообщение
            if dry_run:
                self.stdout.write(self.style.WARNING("\n⚠️  DRY-RUN режим: изменения не сохранены"))
            else:
                # Обновление сессии с итоговой статистикой
                session.status = ImportSession.ImportStatus.COMPLETED
                session.finished_at = timezone.now()
                session.report_details = total_stats
                session.save()

                # Итоговая статистика
                self.stdout.write(
                    self.style.SUCCESS(
                        f"\n{'=' * 60}\n"
                        f"✅ Импорт успешно завершен!\n"
                        f"{'=' * 60}\n"
                        f"Обработано файлов: {len(contragents_files)}\n"
                        f"Сессия импорта: #{session.pk}\n"
                        f"\nИтоговая статистика:\n"
                        f"  Всего клиентов: {total_stats['total']}\n"
                        f"  Создано: {total_stats['created']}\n"
                        f"  Обновлено: {total_stats['updated']}\n"
                        f"  Пропущено: {total_stats['skipped']}\n"
                        f"  Ошибок: {total_stats['errors']}\n"
                        f"{'=' * 60}"
                    )
                )

        except Exception as e:
            # Критическая ошибка - обновляем сессию
            if session:
                session.status = ImportSession.ImportStatus.FAILED
                session.error_message = str(e)
                session.finished_at = timezone.now()
                session.save()

                self.stdout.write(
                    self.style.ERROR(
                        f"\n❌ Критическая ошибка импорта: {str(e)}\n" f"Сессия #{session.pk} завершена с ошибкой"
                    )
                )
            else:
                self.stdout.write(self.style.ERROR(f"\n❌ Ошибка импорта: {str(e)}"))

            logger.error(f"Критическая ошибка импорта клиентов: {e}", exc_info=True)
            raise CommandError(f"Импорт завершен с ошибкой: {e}") from e

"""
Management команда для очистки старых логов синхронизации
"""

import os
from datetime import datetime, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from apps.common.models import CustomerSyncLog


class Command(BaseCommand):
    """Очищает старые логи синхронизации клиентов"""

    help = "Удаляет логи синхронизации старше указанного количества дней"

    def add_arguments(self, parser):
        """Добавляет аргументы команды"""
        parser.add_argument(
            "--days",
            type=int,
            default=None,
            help="Количество дней для хранения логов (по умолчанию из .env или 90)",
        )

        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help="Размер пакета для удаления (по умолчанию из .env или 1000)",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет удалено, но не удалять",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help="Пропустить подтверждение удаления",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        # Получаем параметры
        retention_days = self._get_retention_days(options.get("days"))
        batch_size = self._get_batch_size(options.get("batch_size"))
        dry_run = options["dry_run"]
        force = options["force"]

        # Вычисляем дату отсечения
        cutoff_date = timezone.now() - timedelta(days=retention_days)

        self.stdout.write(
            f"\nПараметры очистки:"
            f"\n  - Удалить логи старше: {cutoff_date.strftime('%Y-%m-%d %H:%M:%S')}"
            f"\n  - Период хранения: {retention_days} дней"
            f"\n  - Размер пакета: {batch_size}"
        )

        # Подсчитываем количество логов для удаления
        logs_to_delete = CustomerSyncLog.objects.filter(created_at__lt=cutoff_date)
        total_count = logs_to_delete.count()

        if total_count == 0:
            self.stdout.write(self.style.SUCCESS("\n✓ Нет логов для удаления"))
            return

        self.stdout.write(f"\nНайдено логов для удаления: {total_count}")

        # Показываем статистику по типам и статусам
        self._display_statistics(logs_to_delete)

        # Dry run режим
        if dry_run:
            self.stdout.write(self.style.WARNING("\n⚠ DRY RUN режим - логи не будут удалены"))
            return

        # Подтверждение от пользователя
        if not force:
            confirm = input(f"\nВы уверены что хотите удалить {total_count} логов? (yes/no): ")
            if confirm.lower() != "yes":
                self.stdout.write(self.style.WARNING("Отменено пользователем"))
                return

        # Выполняем удаление
        self._delete_logs(logs_to_delete, batch_size, total_count)

    def _get_retention_days(self, days_arg):
        """Получает количество дней хранения"""
        if days_arg is not None:
            return days_arg

        # Из переменных окружения
        env_days = os.getenv("SYNC_LOG_RETENTION_DAYS")
        if env_days:
            try:
                return int(env_days)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"Некорректное значение SYNC_LOG_RETENTION_DAYS: {env_days}"))

        # По умолчанию 90 дней
        return 90

    def _get_batch_size(self, batch_arg):
        """Получает размер пакета"""
        if batch_arg is not None:
            return batch_arg

        # Из переменных окружения
        env_batch = os.getenv("SYNC_LOG_BATCH_SIZE")
        if env_batch:
            try:
                return int(env_batch)
            except ValueError:
                self.stdout.write(self.style.WARNING(f"Некорректное значение SYNC_LOG_BATCH_SIZE: {env_batch}"))

        # По умолчанию 1000
        return 1000

    def _display_statistics(self, queryset):
        """Отображает статистику логов"""
        # Статистика по типам операций
        by_type = queryset.values("operation_type").annotate(count=Count("id")).order_by("-count")

        if by_type:
            self.stdout.write("\nПо типам операций:")
            for item in by_type[:5]:  # Топ-5
                self.stdout.write(f"  - {item['operation_type']}: {item['count']}")

        # Статистика по статусам
        by_status = queryset.values("status").annotate(count=Count("id")).order_by("-count")

        if by_status:
            self.stdout.write("\nПо статусам:")
            for item in by_status:
                self.stdout.write(f"  - {item['status']}: {item['count']}")

    def _delete_logs(self, queryset, batch_size, total_count):
        """Удаляет логи пакетами"""
        deleted_count = 0

        self.stdout.write("\nУдаление логов...")

        try:
            while True:
                # Получаем ID следующего пакета
                batch_ids = list(queryset.values_list("id", flat=True)[:batch_size])

                if not batch_ids:
                    break

                # Удаляем пакет
                with transaction.atomic():
                    batch_deleted = CustomerSyncLog.objects.filter(id__in=batch_ids).delete()[0]
                    deleted_count += batch_deleted

                # Показываем прогресс
                progress = (deleted_count / total_count) * 100
                self.stdout.write(
                    f"  Удалено: {deleted_count}/{total_count} " f"({progress:.1f}%)",
                    ending="\r",
                )

            self.stdout.write("")  # Новая строка
            self.stdout.write(self.style.SUCCESS(f"\n✓ Успешно удалено {deleted_count} логов"))

        except Exception as e:
            self.stdout.write("")  # Новая строка
            self.stdout.write(self.style.ERROR(f"\n✗ Ошибка при удалении: {str(e)}"))
            self.stdout.write(f"Удалено до ошибки: {deleted_count} логов")
            raise

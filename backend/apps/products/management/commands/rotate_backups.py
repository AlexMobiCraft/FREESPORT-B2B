"""
Management команда для ротации backup файлов (Story 3.1.2)
"""

from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    Ротация backup файлов - удаление старых копий

    Использование:
        python manage.py rotate_backups
        python manage.py rotate_backups --keep=5
        python manage.py rotate_backups --dry-run

    По умолчанию сохраняются последние 3 backup файла
    """

    help = "Ротация backup файлов (удаление старых копий)"

    def add_arguments(self, parser):
        """Добавление аргументов команды"""
        parser.add_argument(
            "--keep",
            type=int,
            default=3,
            help="Количество последних backup файлов для сохранения (default: 3)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет удалено без фактического удаления",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        keep = options.get("keep", 3)
        dry_run = options.get("dry_run", False)

        if keep < 1:
            self.stdout.write(self.style.ERROR("❌ Параметр --keep должен быть >= 1"))
            return

        # Определяем директорию с бэкапами
        backup_dir = getattr(settings, "BACKUP_DIR", "backend/backup_db")
        backup_path = Path(backup_dir)

        if not backup_path.exists():
            self.stdout.write(self.style.WARNING(f"⚠️ Директория backup не найдена: {backup_dir}"))
            return

        # Находим все backup файлы
        backup_patterns = ["backup_*.sql", "backup_*.sql.gpg"]
        all_backups: list[Path] = []

        for pattern in backup_patterns:
            all_backups.extend(backup_path.glob(pattern))

        if not all_backups:
            self.stdout.write(self.style.WARNING(f"⚠️ Backup файлы не найдены в {backup_dir}"))
            return

        # Сортируем по времени модификации (новые первые)
        sorted_backups = sorted(all_backups, key=lambda p: p.stat().st_mtime, reverse=True)

        total_count = len(sorted_backups)
        to_keep = sorted_backups[:keep]
        to_delete = sorted_backups[keep:]

        # Вывод информации
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("📊 СТАТИСТИКА BACKUP ФАЙЛОВ:")
        self.stdout.write(f"   Всего файлов: {total_count}")
        self.stdout.write(f"   Сохранить: {len(to_keep)}")
        self.stdout.write(f"   Удалить: {len(to_delete)}")
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN MODE: Файлы не будут удалены"))

        # Выводим файлы которые будут сохранены
        if to_keep:
            self.stdout.write("\n✅ СОХРАНИТЬ (последние):")
            for backup in to_keep:
                file_time = datetime.fromtimestamp(backup.stat().st_mtime)
                file_size = backup.stat().st_size / (1024 * 1024)  # MB
                self.stdout.write(
                    f"   • {backup.name} ({file_time.strftime('%Y-%m-%d %H:%M:%S')}, " f"{file_size:.2f} MB)"
                )

        # Выводим и удаляем файлы
        if to_delete:
            self.stdout.write("\n🗑️  УДАЛИТЬ (старые):")
            deleted_count = 0
            errors = 0

            for backup in to_delete:
                file_time = datetime.fromtimestamp(backup.stat().st_mtime)
                file_size = backup.stat().st_size / (1024 * 1024)  # MB

                if dry_run:
                    log_msg = (
                        f"   • {backup.name} " f"({file_time.strftime('%Y-%m-%d %H:%M:%S')}, " f"{file_size:.2f} MB)"
                    )
                    self.stdout.write(log_msg)
                else:
                    try:
                        backup.unlink()
                        deleted_count += 1
                        log_msg = (
                            f"   ✓ {backup.name} "
                            f"({file_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                            f"{file_size:.2f} MB)"
                        )
                        self.stdout.write(log_msg)
                    except Exception as e:
                        errors += 1
                        self.stdout.write(self.style.ERROR(f"   ✗ {backup.name}: {e}"))

            # Итоговое сообщение
            self.stdout.write("\n" + "=" * 50)
            if dry_run:
                self.stdout.write(self.style.SUCCESS(f"✅ DRY RUN ЗАВЕРШЕН: Будет удалено {len(to_delete)} файлов"))
            else:
                if errors == 0:
                    self.stdout.write(self.style.SUCCESS(f"✅ РОТАЦИЯ ЗАВЕРШЕНА: Удалено {deleted_count} файлов"))
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️ РОТАЦИЯ ЗАВЕРШЕНА С ОШИБКАМИ: " f"Удалено {deleted_count}, ошибок {errors}"
                        )
                    )
            self.stdout.write("=" * 50)
        else:
            self.stdout.write(self.style.SUCCESS(f"\n✅ Файлов для удаления нет (всего {total_count}, хранить {keep})"))

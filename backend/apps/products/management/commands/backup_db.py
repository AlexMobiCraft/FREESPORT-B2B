"""
Management команда для создания резервной копии базы данных (Story 3.1.2)
"""

import glob
import os
import subprocess
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Создание резервной копии базы данных PostgreSQL

    Использование:
        python manage.py backup_db
        python manage.py backup_db --encrypt

    Backup файлы сохраняются в BACKUP_DIR (default: backend/backup_db/)
    Автоматически сохраняются последние 3 копии (ротация)
    """

    help = "Создание резервной копии базы данных"

    def add_arguments(self, parser):
        """Добавление аргументов команды"""
        parser.add_argument(
            "--encrypt",
            action="store_true",
            help="Шифровать backup с использованием GPG (опционально)",
        )
        parser.add_argument(
            "--output",
            type=str,
            help="Путь для сохранения backup файла (опционально)",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        encrypt = options.get("encrypt", False)
        custom_output = options.get("output")

        # Определяем директорию для бэкапов
        backup_dir = getattr(settings, "BACKUP_DIR", "backend/backup_db")
        backup_path = Path(backup_dir)
        backup_path.mkdir(parents=True, exist_ok=True)

        # Создаем имя файла бэкапа
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if custom_output:
            backup_file = Path(custom_output)
        else:
            backup_file = backup_path / f"backup_{timestamp}.sql"

        # Получаем настройки базы данных
        db_settings = settings.DATABASES["default"]

        if db_settings["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError(
                f"Unsupported database engine: {db_settings['ENGINE']}. " "Only PostgreSQL is supported."
            )

        self.stdout.write(f"💾 Создание backup: {backup_file}")

        # Формируем команду для создания бэкапа
        cmd = [
            "pg_dump",
            "--host",
            db_settings.get("HOST", "localhost"),
            "--port",
            str(db_settings.get("PORT", 5432)),
            "--username",
            db_settings["USER"],
            "--dbname",
            db_settings["NAME"],
            "--no-password",
            "--file",
            str(backup_file),
            "--format=plain",
            "--no-owner",
            "--no-privileges",
        ]

        # Устанавливаем переменную окружения для пароля
        env = os.environ.copy()
        env["PGPASSWORD"] = db_settings["PASSWORD"]

        try:
            # Выполняем команду
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

            if result.returncode == 0:
                file_size = backup_file.stat().st_size / (1024 * 1024)  # MB
                self.stdout.write(self.style.SUCCESS(f"✅ Backup создан: {backup_file} ({file_size:.2f} MB)"))

                # Опциональное шифрование (Story 3.1.2)
                if encrypt:
                    self._encrypt_backup(backup_file)

                # Автоматическая ротация (сохраняем последние 3 копии)
                if not custom_output:
                    self._rotate_backups(backup_path, keep=3)

            else:
                raise CommandError(f"pg_dump failed: {result.stderr}")

        except subprocess.CalledProcessError as e:
            raise CommandError(f"Backup failed: {e.stderr}")
        except FileNotFoundError:
            raise CommandError("pg_dump not found. Убедитесь что PostgreSQL client установлен.")

    def _encrypt_backup(self, backup_file: Path) -> None:
        """
        Шифрование backup файла с использованием GPG (опционально)

        Story 3.1.2: Добавлено опциональное шифрование backup-файлов
        """
        try:
            import gnupg  # type: ignore

            gpg = gnupg.GPG()
            encrypted_file = backup_file.with_suffix(".sql.gpg")

            with open(backup_file, "rb") as f:
                encrypted = gpg.encrypt_file(
                    f,
                    recipients=[getattr(settings, "BACKUP_GPG_RECIPIENT", "backup@freesport.com")],
                    output=str(encrypted_file),
                    armor=False,
                )

            if encrypted.ok:
                # Удаляем незашифрованную копию
                backup_file.unlink()
                self.stdout.write(self.style.SUCCESS(f"🔐 Backup зашифрован: {encrypted_file}"))
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"⚠️ Шифрование не удалось: {encrypted.status}. " "Сохранена незашифрованная копия."
                    )
                )

        except ImportError:
            self.stdout.write(self.style.WARNING("⚠️ python-gnupg не установлен. Пропускаем шифрование."))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f"⚠️ Ошибка шифрования: {e}. Backup сохранен."))

    def _rotate_backups(self, backup_dir: Path, keep: int = 3) -> None:
        """
        Ротация backup файлов - сохранение последних N копий

        Story 3.1.2: Хранение последних 3 backup копий
        """
        # Находим все backup файлы
        backup_files = sorted(
            backup_dir.glob("backup_*.sql*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        # Удаляем старые бэкапы, оставляя только keep последних
        for old_backup in backup_files[keep:]:
            try:
                old_backup.unlink()
                self.stdout.write(f"🗑️  Удален старый backup: {old_backup.name}")
            except Exception as e:
                self.stdout.write(self.style.WARNING(f"⚠️ Не удалось удалить {old_backup}: {e}"))

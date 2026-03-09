"""
Management команда для восстановления базы данных из backup (Story 3.1.2)
"""

import os
import subprocess
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """
    Восстановление базы данных PostgreSQL из backup файла

    Использование:
        python manage.py restore_db --backup-file=/path/to/backup.sql
        python manage.py restore_db --backup-file=/path/to/backup.sql --confirm

    ВНИМАНИЕ: Эта операция ПЕРЕЗАПИШЕТ текущую базу данных!
    """

    help = "Восстановление базы данных из backup файла"

    def add_arguments(self, parser):
        """Добавление аргументов команды"""
        parser.add_argument(
            "--backup-file",
            type=str,
            required=True,
            help="Путь к backup файлу для восстановления",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Пропустить подтверждение (для автоматизации)",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        backup_file = options["backup_file"]
        confirm = options.get("confirm", False)

        # Валидация backup файла
        backup_path = Path(backup_file)
        if not backup_path.exists():
            raise CommandError(f"Backup файл не найден: {backup_file}")

        if not backup_path.is_file():
            raise CommandError(f"Путь не является файлом: {backup_file}")

        # Проверка расширения файла
        if backup_path.suffix not in [".sql", ".gpg"]:
            self.stdout.write(self.style.WARNING(f"⚠️ Неожиданное расширение файла: {backup_path.suffix}"))

        # Получаем настройки базы данных
        db_settings = settings.DATABASES["default"]

        if db_settings["ENGINE"] != "django.db.backends.postgresql":
            raise CommandError(
                f"Unsupported database engine: {db_settings['ENGINE']}. " "Only PostgreSQL is supported."
            )

        # Подтверждение действия
        if not confirm:
            self.stdout.write(self.style.WARNING("\n⚠️  ВНИМАНИЕ: Эта операция ПЕРЕЗАПИШЕТ текущую базу данных!"))
            self.stdout.write(f"База данных: {db_settings['NAME']}")
            self.stdout.write(f"Backup файл: {backup_path}")
            user_confirm = input("\nВы уверены? Введите 'yes' для подтверждения: ")

            if user_confirm.lower() != "yes":
                self.stdout.write(self.style.ERROR("❌ Восстановление отменено"))
                return

        self.stdout.write(f"\n💾 Восстановление базы из: {backup_path}")

        # Расшифровка GPG файла если нужно
        actual_backup = backup_path
        if backup_path.suffix == ".gpg":
            actual_backup = self._decrypt_backup(backup_path)

        # Формируем команду для восстановления
        cmd = [
            "psql",
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
            str(actual_backup),
        ]

        # Устанавливаем переменную окружения для пароля
        env = os.environ.copy()
        env["PGPASSWORD"] = db_settings["PASSWORD"]

        try:
            # Выполняем команду
            result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=True)

            if result.returncode == 0:
                self.stdout.write(self.style.SUCCESS("✅ База данных успешно восстановлена"))

                # Очищаем временный расшифрованный файл
                if actual_backup != backup_path and actual_backup.exists():
                    actual_backup.unlink()

            else:
                raise CommandError(f"psql failed: {result.stderr}")

        except subprocess.CalledProcessError as e:
            raise CommandError(f"Restore failed: {e.stderr}")
        except FileNotFoundError:
            raise CommandError("psql not found. Убедитесь что PostgreSQL client установлен.")
        finally:
            # Очищаем временный файл даже при ошибке
            if actual_backup != backup_path and actual_backup.exists() and actual_backup.suffix == ".tmp":
                actual_backup.unlink()

    def _decrypt_backup(self, encrypted_file: Path) -> Path:
        """
        Расшифровка GPG backup файла

        Story 3.1.2: Поддержка зашифрованных backup файлов
        """
        try:
            import gnupg  # type: ignore

            gpg = gnupg.GPG()
            decrypted_file = encrypted_file.with_suffix(".sql.tmp")

            with open(encrypted_file, "rb") as ef:
                decrypted = gpg.decrypt_file(ef, output=str(decrypted_file))

            if decrypted.ok:
                self.stdout.write(self.style.SUCCESS("🔓 Backup расшифрован"))
                return decrypted_file
            else:
                raise CommandError(
                    f"Расшифровка не удалась: {decrypted.status}. " "Проверьте что у вас есть приватный ключ."
                )

        except ImportError:
            raise CommandError("python-gnupg не установлен. " "Установите для работы с зашифрованными backup файлами.")
        except Exception as e:
            raise CommandError(f"Ошибка расшифровки: {e}")

"""
Unit-тесты для команд backup_db, restore_db, rotate_backups (Story 3.1.2)
"""

import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings


@pytest.mark.unit
class TestBackupDbCommand(TestCase):
    """Unit-тесты для команды backup_db"""

    def setUp(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = Path(self.temp_dir) / "backups"
        self.backup_dir.mkdir()

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "test_backups"))
    @patch("subprocess.run")
    def test_backup_creates_file(self, mock_subprocess):
        """Тест создания backup файла"""
        # Создаем backup директорию заранее
        backup_dir = Path(tempfile.gettempdir()) / "test_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Настраиваем mock для subprocess
        def mock_run_side_effect(cmd, **kwargs):
            # Создаем фиктивный backup файл после "pg_dump"
            if "pg_dump" in str(cmd):
                # Извлекаем имя файла из команды
                for part in cmd:
                    if "backup_" in str(part) and ".sql" in str(part):
                        backup_file = Path(part)
                        backup_file.write_text("-- Test backup content")
                        break

            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_subprocess.side_effect = mock_run_side_effect

        out = StringIO()
        call_command("backup_db", stdout=out)

        # Проверяем что subprocess.run был вызван
        assert mock_subprocess.called
        output = out.getvalue()
        assert "Backup" in output or "backup" in output.lower()

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "test_backups"))
    @patch("subprocess.run")
    def test_backup_with_encryption_flag(self, mock_subprocess):
        """Тест создания backup с флагом --encrypt"""
        # Создаем backup директорию
        backup_dir = Path(tempfile.gettempdir()) / "test_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        def mock_run_side_effect(cmd, **kwargs):
            if "pg_dump" in str(cmd):
                for part in cmd:
                    if "backup_" in str(part) and ".sql" in str(part):
                        backup_file = Path(part)
                        backup_file.write_text("-- Test backup content")
                        break

            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_subprocess.side_effect = mock_run_side_effect

        out = StringIO()
        # Команда не должна падать даже если GPG не установлен
        call_command("backup_db", "--encrypt", stdout=out)

        assert mock_subprocess.called

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "test_backups"))
    @patch("subprocess.run")
    def test_backup_rotation(self, mock_subprocess):
        """Тест автоматической ротации backup файлов"""
        # Создаем backup директорию
        backup_dir = Path(tempfile.gettempdir()) / "test_backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # Создаем 5 старых backup файлов
        for i in range(5):
            backup_file = backup_dir / f"backup_old_{i}.sql"
            backup_file.write_text("test backup content")

        def mock_run_side_effect(cmd, **kwargs):
            if "pg_dump" in str(cmd):
                for part in cmd:
                    if "backup_" in str(part) and ".sql" in str(part):
                        backup_file = Path(part)
                        backup_file.write_text("-- Test backup content")
                        break

            result = MagicMock()
            result.returncode = 0
            result.stderr = ""
            return result

        mock_subprocess.side_effect = mock_run_side_effect

        out = StringIO()
        call_command("backup_db", stdout=out)

        # Проверяем что subprocess был вызван
        assert mock_subprocess.called


@pytest.mark.unit
class TestRestoreDbCommand(TestCase):
    """Unit-тесты для команды restore_db"""

    def setUp(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.test_backup = Path(self.temp_dir) / "test_backup.sql"
        self.test_backup.write_text("-- Test backup SQL content")

    def test_restore_requires_backup_file(self):
        """Тест что команда требует параметр --backup-file"""
        # Django call_command выбрасывает CommandError, а не SystemExit
        with pytest.raises(CommandError) as exc_info:
            call_command("restore_db")

        assert "--backup-file" in str(exc_info.value)

    def test_restore_validates_file_exists(self):
        """Тест валидации существования backup файла"""
        with pytest.raises(CommandError) as exc_info:
            call_command("restore_db", "--backup-file=/nonexistent/backup.sql", "--confirm")

        assert "не найден" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()

    @patch("subprocess.run")
    def test_restore_with_confirm_flag(self, mock_subprocess):
        """Тест восстановления с флагом --confirm (без prompt)"""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""
        mock_subprocess.return_value = mock_result

        out = StringIO()
        call_command(
            "restore_db",
            f"--backup-file={self.test_backup}",
            "--confirm",
            stdout=out,
        )

        # Проверяем что subprocess был вызван с psql
        assert mock_subprocess.called
        call_args = mock_subprocess.call_args
        assert "psql" in call_args[0][0]


@pytest.mark.unit
class TestRotateBackupsCommand(TestCase):
    """Unit-тесты для команды rotate_backups"""

    def setUp(self):
        """Настройка для каждого теста"""
        self.temp_dir = tempfile.mkdtemp()
        self.backup_dir = Path(self.temp_dir) / "backups"
        self.backup_dir.mkdir()

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "test_backups_rotate"))
    def test_rotate_with_keep_parameter(self):
        """Тест ротации с параметром --keep"""
        backup_dir = Path(tempfile.gettempdir()) / "test_backups_rotate"
        backup_dir.mkdir(exist_ok=True)

        # Создаем 5 backup файлов
        for i in range(5):
            backup_file = backup_dir / f"backup_2025010{i}_120000.sql"
            backup_file.write_text(f"backup content {i}")

        out = StringIO()
        call_command("rotate_backups", "--keep=3", stdout=out)

        # Проверяем output
        output = out.getvalue()
        assert "3" in output  # keep=3

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "test_backups_rotate_dry"))
    def test_rotate_dry_run(self):
        """Тест dry-run режима (без фактического удаления)"""
        backup_dir = Path(tempfile.gettempdir()) / "test_backups_rotate_dry"
        backup_dir.mkdir(exist_ok=True)

        # Создаем 4 backup файла
        for i in range(4):
            backup_file = backup_dir / f"backup_2025010{i}_120000.sql"
            backup_file.write_text(f"backup content {i}")

        initial_count = len(list(backup_dir.glob("backup_*.sql")))

        out = StringIO()
        call_command("rotate_backups", "--keep=2", "--dry-run", stdout=out)

        # Проверяем что файлы НЕ были удалены
        final_count = len(list(backup_dir.glob("backup_*.sql")))
        assert initial_count == final_count

        # Проверяем что в выводе есть DRY RUN
        output = out.getvalue()
        assert "DRY RUN" in output or "dry run" in output.lower()

    @override_settings(BACKUP_DIR=str(Path(tempfile.gettempdir()) / "nonexistent_dir"))
    def test_rotate_handles_missing_directory(self):
        """Тест обработки отсутствующей директории"""
        out = StringIO()
        # Команда не должна падать, только warning
        call_command("rotate_backups", stdout=out)

        output = out.getvalue()
        assert "не найдена" in output.lower() or "not found" in output.lower()

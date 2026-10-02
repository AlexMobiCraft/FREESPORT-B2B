"""Шаг бэкапа перед полным импортом каталога (AC6 стори гонки cleanup).

На проде бэкап не работал вообще: умолчание `BACKUP_DIR` было относительным
(`backend/backup_db`), команда исполняется с рабочим каталогом `/app`, и
`/app/backend/backup_db` принадлежит uid 999 при процессе под 1000:1000.
Каждый полный импорт получал `Permission denied`, а вызывающий код глотал это
в WARNING — прод жил без бэкапов неизвестно сколько.

Вторая половина проблемы вскрылась замером: шаг нельзя чинить «в лоб». На
прод-выгрузке 27.08.2026 из 172 сессий **37** пришли с `file_type=all`
(`mode=complete`, забирающий остатки каталога), и каждая дёргала бэкап. Тридцать
семь полных `pg_dump` базы подряд во время обмена — это нагрузка, а не защита.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import override_settings

from apps.products.models import ImportSession


@pytest.fixture
def clean_cache():
    cache.clear()
    yield
    cache.clear()


def _exchange_dir(base: Path) -> Path:
    """Пустой каталог обмена: шаг бэкапа от наличия файлов не зависит."""
    data_dir = base / "1c_import"
    for sub in ("goods", "offers", "prices", "rests", "priceLists"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    return data_dir


def _run_full_import(data_dir: Path, session: ImportSession) -> str:
    out = StringIO()
    call_command(
        "import_products_from_1c",
        data_dir=str(data_dir),
        file_type="all",
        import_session_id=session.pk,
        stdout=out,
        stderr=StringIO(),
    )
    return out.getvalue()


@pytest.mark.django_db
class TestBackupStepIsThrottled:
    """Одна выгрузка 1С не должна порождать десятки полных pg_dump."""

    def test_second_import_in_window_skips_backup(self, clean_cache, tmp_path):
        data_dir = _exchange_dir(tmp_path)

        with patch("apps.products.management.commands.import_products_from_1c.call_command") as mock_backup:
            for _ in range(3):
                session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
                _run_full_import(data_dir, session)

            backup_calls = [c for c in mock_backup.call_args_list if c.args and c.args[0] == "backup_db"]

        assert len(backup_calls) == 1, "Бэкап обязан делаться один раз в окне, а не на каждом прогоне"

    def test_backup_runs_again_after_window_expires(self, clean_cache, tmp_path):
        data_dir = _exchange_dir(tmp_path)

        with (
            override_settings(BACKUP_MIN_INTERVAL_SECONDS=1),
            patch("apps.products.management.commands.import_products_from_1c.call_command") as mock_backup,
        ):
            session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
            _run_full_import(data_dir, session)
            # Окно истекло — снимаем отметку, как это сделал бы TTL.
            from apps.products.management.commands.import_products_from_1c import Command

            cache.delete(Command.BACKUP_MARKER_KEY)

            session2 = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
            _run_full_import(data_dir, session2)

            backup_calls = [c for c in mock_backup.call_args_list if c.args and c.args[0] == "backup_db"]

        assert len(backup_calls) == 2


@pytest.mark.django_db
class TestBackupStepCanBeDisabled:
    """AC6: либо бэкап работает, либо шаг явно отключён настройкой."""

    def test_disabled_by_setting_does_not_call_backup(self, clean_cache, tmp_path):
        data_dir = _exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with (
            override_settings(BACKUP_BEFORE_IMPORT=False),
            patch("apps.products.management.commands.import_products_from_1c.call_command") as mock_backup,
        ):
            output = _run_full_import(data_dir, session)
            backup_calls = [c for c in mock_backup.call_args_list if c.args and c.args[0] == "backup_db"]

        assert backup_calls == []
        assert "отключён настройкой" in output, "Отключение обязано быть видно, а не молчаливо"


@pytest.mark.django_db
class TestBackupFailureIsLoud:
    """Провал бэкапа больше не тонет в WARNING."""

    def test_failure_reaches_session_report_and_import_continues(self, clean_cache, tmp_path):
        data_dir = _exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        real_call_command = call_command

        def failing(*args, **kwargs):
            if args and args[0] == "backup_db":
                raise CommandError("Каталог бэкапов /app/var/backups недоступен: Permission denied")
            return real_call_command(*args, **kwargs)

        with patch("apps.products.management.commands.import_products_from_1c.call_command", side_effect=failing):
            output = _run_full_import(data_dir, session)

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED, "Импорт обязан продолжиться: 1С файл не повторит"
        assert "Бэкап перед импортом НЕ создан" in session.report, "Провал обязан быть виден в отчёте сессии"
        assert "Permission denied" in session.report
        assert "НЕ создан" in output


@pytest.mark.django_db
class TestBackupDirMustBeUsable:
    """Сама команда бэкапа обязана падать внятно, а не молча писать не туда."""

    def test_relative_backup_dir_is_rejected(self, tmp_path):
        with override_settings(BACKUP_DIR="backend/backup_db"):
            with pytest.raises(CommandError, match="абсолютным путём"):
                call_command("backup_db", stdout=StringIO(), stderr=StringIO())

    def test_unwritable_backup_dir_is_rejected(self, tmp_path):
        target = tmp_path / "backups"

        with override_settings(BACKUP_DIR=str(target)):
            with patch("apps.products.management.commands.backup_db.os.access", return_value=False):
                with pytest.raises(CommandError, match="недоступен на запись"):
                    call_command("backup_db", stdout=StringIO(), stderr=StringIO())

    def test_absolute_writable_dir_reaches_pg_dump(self, tmp_path):
        """Путь в порядке — команда доходит до pg_dump, а не падает на каталоге."""
        target = tmp_path / "backups"

        with override_settings(BACKUP_DIR=str(target)):
            with patch("apps.products.management.commands.backup_db.subprocess.run") as mock_run:
                mock_run.return_value.returncode = 0
                # Файл pg_dump не создаёт (он замокан) — обрываемся на stat().
                with pytest.raises(Exception):
                    call_command("backup_db", stdout=StringIO(), stderr=StringIO())

        assert target.exists(), "Каталог обязан быть создан"
        assert mock_run.called, "До pg_dump дойти обязаны"

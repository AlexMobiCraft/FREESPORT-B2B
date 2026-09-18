"""Удаление legacy-каталогов обмена 1С из публичного MEDIA_ROOT (Story 36.1).

Каталоги приёма файлов обмена (`1c_import`, `1c_temp`) перенесены в приватный
`ONEC_PRIVATE_DIR` вне `MEDIA_ROOT`. Однако media-том на production переживает
деплой: файлы незавершённых обменов, записанные до переезда, физически остаются
под `MEDIA_ROOT` — с прайс-листами, остатками и реквизитами контрагентов.

nginx-гарды (`location /media/1c_import|1c_temp/ { return 404; }`) закрывают
доступ по URL, эта команда удаляет сами файлы. Запускается один раз при деплое
Story 36.1; повторные запуски безопасны (идемпотентна).
"""

import shutil
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

LEGACY_SUBDIRS = ("1c_import", "1c_temp")


class Command(BaseCommand):
    help = "Удаляет legacy-каталоги обмена 1С (1c_import, 1c_temp) из публичного MEDIA_ROOT"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет удалено, ничего не удаляя",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        dry_run: bool = options["dry_run"]
        media_root = Path(str(settings.MEDIA_ROOT)).resolve()

        self._assert_exchange_dirs_are_private(media_root)

        found = False
        for subdir in LEGACY_SUBDIRS:
            legacy_dir = media_root / subdir
            if not legacy_dir.exists():
                continue

            found = True
            file_count = sum(1 for path in legacy_dir.rglob("*") if path.is_file())

            if dry_run:
                self.stdout.write(f"DRY RUN: {legacy_dir} — будет удалён ({file_count} файлов)")
                continue

            shutil.rmtree(legacy_dir)
            self.stdout.write(self.style.SUCCESS(f"Удалён {legacy_dir} ({file_count} файлов)"))

        if not found:
            self.stdout.write(f"Legacy-каталоги обмена 1С под {media_root} отсутствуют — нечего удалять.")

    def _assert_exchange_dirs_are_private(self, media_root: Path) -> None:
        """Отказ, если рабочие каталоги обмена всё ещё под MEDIA_ROOT.

        Такое возможно при откате Story 36.1 или сбитом `ONEC_PRIVATE_DIR`.
        Удалять их нельзя — это активная очередь обмена, а не остатки.
        """
        exchange = getattr(settings, "ONEC_EXCHANGE", {}) or {}

        for key in ("IMPORT_DIR", "TEMP_DIR"):
            value = exchange.get(key)
            if not value:
                continue

            active_dir = Path(str(value)).resolve()
            if active_dir == media_root or media_root in active_dir.parents:
                raise CommandError(
                    f"ONEC_EXCHANGE[{key!r}] = {active_dir} находится внутри MEDIA_ROOT "
                    f"({media_root}). Это активный каталог обмена, а не legacy-остатки. "
                    "Проверьте ONEC_PRIVATE_DIR перед очисткой."
                )

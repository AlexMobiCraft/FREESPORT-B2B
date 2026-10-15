"""Отчёт упавшей сессии импорта не затирается (AC5 стори гонки cleanup).

`Command.handle` держит объект `session`, загруженный в начале прогона, а
`VariantImportProcessor.log_progress` всё это время пишет `report` прямо в БД
через `F`-выражение. Полный `session.save()` в обработчике ошибки записывал
строку целиком — вместе со СТАРЫМ `report` из памяти, — и весь прогресс упавшей
сессии исчезал.

Именно поэтому у пяти `failed`-сессий инцидента 25.08.2026 в отчёте было по
несколько строк и не было видно, что они успели сделать до падения. Разбирать
инцидент по таким отчётам нельзя: они врут не о статусе, а об истории.
"""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import CommandError, call_command

from apps.products.models import ImportSession

ONEC_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "1c-data"


def _exchange_dir(base: Path) -> Path:
    data_dir = base / "1c_import"
    for sub in ("goods", "offers", "prices", "rests", "priceLists"):
        (data_dir / sub).mkdir(parents=True, exist_ok=True)
    return data_dir


def _run_failing_import(data_dir: Path, session: ImportSession, promised: str) -> None:
    """Прогон, который дойдёт до строгой проверки обещанного файла и упадёт.

    Это не искусственная поломка, а прод-сценарий: 1С обещала сегмент, к моменту
    сбора его в каталоге уже нет. До падения команда успевает записать в отчёт
    несколько шагов импорта.
    """
    call_command(
        "import_products_from_1c",
        data_dir=str(data_dir),
        file_type="all",
        import_session_id=session.pk,
        source_filename=promised,
        skip_backup=True,
        stdout=StringIO(),
        stderr=StringIO(),
    )


@pytest.mark.django_db
class TestFailedSessionKeepsItsReport:
    """AC5 — прогресс, записанный до падения, обязан пережить фиксацию ошибки."""

    def test_progress_survives_failure(self, tmp_path):
        data_dir = _exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with pytest.raises(CommandError):
            _run_failing_import(data_dir, session, "rests_1_4_missing.xml")

        session.refresh_from_db()

        assert session.status == ImportSession.ImportStatus.FAILED
        assert "rests_1_4_missing.xml" in session.error_message

        # Шаги, записанные log_progress ДО падения, обязаны остаться в отчёте.
        for step in (
            "Начало импорта категорий",
            "Начало импорта брендов",
            "Начало импорта типов цен",
            "Начало импорта товаров",
            "Обновление остатков",
        ):
            assert step in session.report, f"Из отчёта пропал шаг «{step}» — прогресс затёрт"

    def test_report_is_not_shorter_than_before_failure(self, tmp_path):
        """Прямая проверка на затирание: отчёт не может стать короче."""
        data_dir = _exchange_dir(tmp_path)
        session = ImportSession.objects.create(
            status=ImportSession.ImportStatus.IN_PROGRESS,
            report="[до прогона] строка, которая обязана уцелеть\n",
        )
        before = ImportSession.objects.get(pk=session.pk).report

        with pytest.raises(CommandError):
            _run_failing_import(data_dir, session, "rests_1_4_missing.xml")

        session.refresh_from_db()

        assert session.report.startswith(before), "Начало отчёта затёрто"
        assert len(session.report) > len(before), "Отчёт не пополнился прогрессом прогона"

    def test_failure_reason_is_recorded_in_report(self, tmp_path):
        """Причина падения фиксируется в отчёте — её пишет log_progress до raise."""
        data_dir = _exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with pytest.raises(CommandError):
            _run_failing_import(data_dir, session, "rests_1_4_missing.xml")

        session.refresh_from_db()
        assert "не прочитаны" in session.report
        assert "rests_1_4_missing.xml" in session.report

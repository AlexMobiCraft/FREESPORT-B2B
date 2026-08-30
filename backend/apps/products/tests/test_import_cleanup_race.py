"""Регрессия гонки cleanup в обмене 1С (инцидент выгрузки 25.08.2026).

Каталог обмена общий для всех сессий, задачи Celery идут параллельно, а
`_cleanup_files` удалял XML по маске `glob("rests/rests*.xml")` — и сносил файлы
соседних задач раньше, чем те успевали их прочитать. Итог на проде: 5 сессий
`failed`, 6 из 16 сегментов остатков не прочитаны никем, две сессии отчитались
`completed` с нулём записей.

Здесь закрыты обе половины исправления:
- точечный cleanup — удаляется только то, что эта команда реально распарсила;
- сериализация `process_1c_import_task` через лок каталога обмена в Redis.

XML берутся из закоммиченного среза реальной выгрузки 1С
(`backend/tests/fixtures/1c-data/rests/segments/`) — синтетику проект запрещает.
Это восемь **разных** сегментов настоящей выгрузки, сохранившие исходные имена
файлов 1С и непересекающиеся наборы предложений: копия одного файла под восемью
именами не отличила бы «каждый сегмент прочитан ровно один раз» от «один и тот же
файл прочитан восемь раз».
"""

from __future__ import annotations

import re
import shutil
import threading
import zipfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

import pytest
from celery.exceptions import MaxRetriesExceededError, Retry
from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.db import connection
from kombu.exceptions import OperationalError
from redis.exceptions import ConnectionError as RedisConnectionError

from apps.integrations.onec_exchange.file_type_detection import detect_file_type
from apps.products.management.commands.import_products_from_1c import Command
from apps.products.models import ImportSession
from apps.products.services.parser import XMLDataParser
from apps.products.services.variant_import import VariantImportProcessor
from apps.products.tasks import _release_import_lock, process_1c_import_task

ONEC_FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "fixtures" / "1c-data"

# Восемь реальных сегментов остатков с исходными именами 1С (`rests_1_<N>_<guid>.xml`).
# Порядок — числовой по номеру сегмента, а не лексикографический: `rests_1_10`
# идёт раньше `rests_1_9`, и на порядковые номера закладываться нельзя.
REAL_SEGMENTS = sorted(
    (ONEC_FIXTURES / "rests" / "segments").glob("rests_1_*.xml"),
    key=lambda p: int(p.name.split("_")[2]),
)

# Назначенный правилами проекта корпус runtime-выгрузок (в .gitignore, на раннере
# отсутствует) — источник полноразмерных сегментов для data_dependent теста.
ONEC_RUNTIME_RESTS = Path(__file__).resolve().parents[3] / "data" / "import_1c" / "rests"

RECORDS_RE = re.compile(r"записей остатков (\d+)")
SEGMENT_LINE_RE = re.compile(r"• (\S+\.xml): записей остатков (\d+)")


def _segment_path(index: int) -> Path:
    """Реальный сегмент по порядковому номеру (1-based)."""
    return REAL_SEGMENTS[index - 1]


def _segment_name(index: int) -> str:
    """Имя сегмента ровно в том виде, в котором его присылает 1С."""
    return _segment_path(index).name


def _make_exchange_dir(base: Path) -> Path:
    """Каталог обмена с пустой подпапкой rests."""
    data_dir = base / "1c_import"
    (data_dir / "rests").mkdir(parents=True)
    return data_dir


def _stage_segment(data_dir: Path, index: int) -> Path:
    """Положить в каталог обмена очередной реальный сегмент остатков."""
    target = data_dir / "rests" / _segment_name(index)
    shutil.copyfile(_segment_path(index), target)
    return target


def _run_import(data_dir: Path, session: ImportSession, source_filename: str | None = None) -> str:
    """Прогон команды импорта остатков поверх существующей сессии."""
    out = StringIO()
    options: dict[str, object] = {
        "data_dir": str(data_dir),
        "file_type": "rests",
        "import_session_id": session.pk,
        "stdout": out,
        "stderr": StringIO(),
    }
    if source_filename is not None:
        options["source_filename"] = source_filename
    call_command("import_products_from_1c", **options)
    return out.getvalue()


def _records_in(output: str) -> int:
    return sum(int(m) for m in RECORDS_RE.findall(output))


def _segments_in(output: str) -> dict[str, int]:
    """Какие сегменты прочитаны прогоном и сколько записей дал каждый."""
    return {name: int(count) for name, count in SEGMENT_LINE_RE.findall(output)}


@pytest.fixture
def clean_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestPinpointCleanup:
    """AC1 — удаляются только файлы, которые эта команда действительно распарсила."""

    def test_neighbour_file_survives_cleanup(self, tmp_path):
        """Сосед положил свой сегмент до cleanup — он обязан уцелеть."""
        data_dir = _make_exchange_dir(tmp_path)
        own = _stage_segment(data_dir, 1)
        neighbour = data_dir / "rests" / _segment_name(2)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        original_finalize = VariantImportProcessor.finalize_session

        def stage_neighbour(processor, *args, **kwargs):
            # Момент гонки: сосед принял файл между сбором списка и cleanup.
            shutil.copyfile(_segment_path(2), neighbour)
            return original_finalize(processor, *args, **kwargs)

        with patch.object(VariantImportProcessor, "finalize_session", stage_neighbour):
            _run_import(data_dir, session)

        assert not own.exists(), "Свой распарсенный сегмент должен быть удалён"
        assert neighbour.exists(), "Чужой сегмент удалять нельзя — это и есть дефект"

    def test_cleanup_counts_only_processed_files(self, tmp_path):
        """Счётчик удалённых XML не может превышать число распарсенных файлов."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)
        _stage_segment(data_dir, 2)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        output = _run_import(data_dir, session)

        match = re.search(r"Удалено XML файлов: (\d+)", output)
        assert match is not None
        assert int(match.group(1)) == 2

    def test_replaced_file_with_same_name_survives_cleanup(self, tmp_path):
        """Файл подменён под тем же именем после парсинга — удалять его нельзя.

        1С переиспользует имена (`rests.xml` без сегментации), и путь сам по себе
        не доказывает, что на диске всё ещё лежит именно распарсенный файл.
        """
        data_dir = _make_exchange_dir(tmp_path)
        own = _stage_segment(data_dir, 1)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        original_finalize = VariantImportProcessor.finalize_session

        def replace_own(processor, *args, **kwargs):
            # Сосед снёс наш файл и положил под тем же именем свой сегмент.
            own.unlink()
            shutil.copyfile(_segment_path(2), own)
            return original_finalize(processor, *args, **kwargs)

        with patch.object(VariantImportProcessor, "finalize_session", replace_own):
            _run_import(data_dir, session)

        assert own.exists(), "Под этим именем лежит уже другой файл — он не наш и не удаляется"
        assert own.read_bytes() == _segment_path(2).read_bytes()

    def test_cleanup_files_ignores_unparsed_neighbours(self, tmp_path):
        """`_cleanup_files` без списка обработанного не удаляет ничего."""
        data_dir = _make_exchange_dir(tmp_path)
        stranger = _stage_segment(data_dir, 7)

        command = Command()
        command.stdout = StringIO()
        command._cleanup_files([])

        assert stranger.exists()


@pytest.mark.django_db
class TestMissingFileResilience:
    """AC3 — исчезнувший файл не валит импорт целиком."""

    def _run_with_vanishing(self, data_dir: Path, session: ImportSession, vanish: set[int]) -> str:
        """Прогон, где перечисленные сегменты исчезают между сбором и парсингом."""
        original_parse = XMLDataParser.parse_rests_xml

        def parse_or_vanish(parser, file_path):
            for index in vanish:
                if _segment_name(index) == Path(file_path).name:
                    Path(file_path).unlink(missing_ok=True)
            return original_parse(parser, file_path)

        with patch.object(XMLDataParser, "parse_rests_xml", parse_or_vanish):
            return _run_import(data_dir, session)

    def test_partial_loss_completes_and_reports(self, tmp_path):
        """Один файл из трёх исчез: два обработаны, сессия COMPLETED."""
        data_dir = _make_exchange_dir(tmp_path)
        for index in (1, 2, 3):
            _stage_segment(data_dir, index)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        output = self._run_with_vanishing(data_dir, session, vanish={2})

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert len(RECORDS_RE.findall(output)) == 2
        assert _segment_name(2) in session.report

    def test_total_loss_fails_instead_of_silent_success(self, tmp_path):
        """Исчезли все файлы: FAILED с перечнем, а не COMPLETED с нулём записей."""
        data_dir = _make_exchange_dir(tmp_path)
        for index in (1, 2, 3):
            _stage_segment(data_dir, index)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with pytest.raises(CommandError):
            self._run_with_vanishing(data_dir, session, vanish={1, 2, 3})

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert _segment_name(1) in session.error_message

    def test_no_files_at_all_keeps_current_behaviour(self, tmp_path):
        """Файлов типа нет изначально — прежнее поведение: предупреждение и успех."""
        data_dir = _make_exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        output = _run_import(data_dir, session)

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert "Файлы rests.xml не найдены" in output


@pytest.mark.django_db
class TestExpectedSegmentIsMandatory:
    """Решение Alex 2026-08-26: у сегмента с конкретным именем нет права на тихий успех.

    Если 1С прислала `rests_1_12_….xml`, а к моменту `_collect_xml_files` файла
    в каталоге уже нет — его увёл сосед. Это потеря данных, и сессия обязана быть
    `FAILED`. Пустой список остаётся успехом только там, где конкретного файла
    не обещали: `mode=complete` и ручной общий импорт.
    """

    def test_own_segment_stolen_before_collect_fails(self, tmp_path):
        """Своего сегмента нет, чужой лежит — это не повод отчитаться успехом."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 2)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with pytest.raises(CommandError):
            _run_import(data_dir, session, source_filename=_segment_name(1))

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert _segment_name(1) in session.error_message

    def test_empty_directory_with_expected_segment_fails(self, tmp_path):
        """Каталог пуст, а сегмент обещан — сценарий сессий 62672/62674."""
        data_dir = _make_exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with pytest.raises(CommandError):
            _run_import(data_dir, session, source_filename=_segment_name(5))

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED

    def test_expected_segment_vanished_before_parse_fails(self, tmp_path):
        """Файл собран, но исчез до парсинга — тоже потеря именно нашего сегмента."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)
        _stage_segment(data_dir, 2)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        original_parse = XMLDataParser.parse_rests_xml

        def parse_or_vanish(parser, file_path):
            if Path(file_path).name == _segment_name(1):
                Path(file_path).unlink(missing_ok=True)
            return original_parse(parser, file_path)

        with patch.object(XMLDataParser, "parse_rests_xml", parse_or_vanish):
            with pytest.raises(CommandError):
                _run_import(data_dir, session, source_filename=_segment_name(1))

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED

    def test_own_segment_present_completes(self, tmp_path):
        """Свой сегмент на месте — строгая проверка не мешает штатному прогону."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 3)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        output = _run_import(data_dir, session, source_filename=_segment_name(3))

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert _segment_name(3) in _segments_in(output)

    def test_manual_import_without_expected_segment_still_succeeds(self, tmp_path):
        """Ручной общий импорт имени файла не обещает — прежнее поведение."""
        data_dir = _make_exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        output = _run_import(data_dir, session)

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert "Файлы rests.xml не найдены" in output


@pytest.mark.django_db
class TestTaskPropagatesExpectedSegment:
    """Задача обязана донести имя сегмента до команды, иначе строгость AC не работает."""

    @patch("apps.products.tasks.call_command")
    def test_concrete_segment_reaches_command(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": data_dir, "source_filename": _segment_name(4)},
            task_id="task-expect-1",
        ).get()

        # Контракт списка: одиночный сегмент — список из одного имени. Список,
        # а не строка, потому что задача архива обещает весь свой распакованный XML.
        assert mock_call_command.call_args.kwargs["source_filename"] == [_segment_name(4)]

    @patch("apps.products.tasks.call_command")
    def test_complete_mode_does_not_promise_a_file(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": data_dir, "source_filename": "complete"},
            task_id="task-expect-2",
        ).get()

        assert mock_call_command.call_args.kwargs["file_type"] == "all"
        assert mock_call_command.call_args.kwargs.get("source_filename") is None


@pytest.mark.django_db
class TestCleanupRaceRegression:
    """AC8 — восемь наложенных сессий не теряют ни одного сегмента."""

    SESSIONS = 8

    def test_eight_overlapping_sessions_lose_nothing(self, tmp_path):
        assert len(REAL_SEGMENTS) >= self.SESSIONS, "Нужны восемь реальных сегментов в фикстурах"

        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)

        original_finalize = VariantImportProcessor.finalize_session
        staged = {"next": 2}

        def stage_next(processor, *args, **kwargs):
            # Сосед кладёт следующий сегмент ровно в окно между сбором списка
            # и cleanup текущей команды — так и выглядела выгрузка 25.08.2026.
            if staged["next"] <= TestCleanupRaceRegression.SESSIONS:
                _stage_segment(data_dir, staged["next"])
                staged["next"] += 1
            return original_finalize(processor, *args, **kwargs)

        seen: dict[str, int] = {}
        sessions = []
        with patch.object(VariantImportProcessor, "finalize_session", stage_next):
            for index in range(1, self.SESSIONS + 1):
                session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
                sessions.append(session)
                read = _segments_in(_run_import(data_dir, session, source_filename=_segment_name(index)))
                overlap = set(read) & set(seen)
                assert not overlap, f"Сегмент прочитан повторно: {overlap}"
                seen.update(read)

        statuses = [ImportSession.objects.get(pk=s.pk).status for s in sessions]
        assert ImportSession.ImportStatus.FAILED not in statuses

        # Каждый сегмент прочитан ровно один раз, и записи из него не потеряны.
        expected = {
            _segment_name(i): len(XMLDataParser().parse_rests_xml(str(_segment_path(i))))
            for i in range(1, self.SESSIONS + 1)
        }
        assert all(count > 0 for count in expected.values())
        assert seen == expected
        assert not list((data_dir / "rests").glob("*.xml")), "Каталог обмена должен опустеть"

    @pytest.mark.data_dependent
    def test_real_runtime_segments_lose_nothing(self, tmp_path):
        """То же самое на полноразмерных сегментах назначенного корпуса."""
        if not ONEC_RUNTIME_RESTS.exists():
            pytest.skip("Назначенный корпус data/import_1c отсутствует (в .gitignore)")

        segments = sorted(ONEC_RUNTIME_RESTS.glob("rests_1_*.xml"))
        if len(segments) < 2:
            pytest.skip("Недостаточно сегментов остатков в назначенном корпусе")

        data_dir = _make_exchange_dir(tmp_path)
        shutil.copyfile(segments[0], data_dir / "rests" / segments[0].name)

        original_finalize = VariantImportProcessor.finalize_session
        staged = {"next": 1}

        def stage_next(processor, *args, **kwargs):
            if staged["next"] < len(segments):
                nxt = segments[staged["next"]]
                shutil.copyfile(nxt, data_dir / "rests" / nxt.name)
                staged["next"] += 1
            return original_finalize(processor, *args, **kwargs)

        seen: dict[str, int] = {}
        with patch.object(VariantImportProcessor, "finalize_session", stage_next):
            for segment in segments:
                session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
                read = _segments_in(_run_import(data_dir, session, source_filename=segment.name))
                assert not set(read) & set(seen), "Сегмент прочитан повторно"
                seen.update(read)

        assert set(seen) == {s.name for s in segments}, "Каждый сегмент обязан быть прочитан ровно один раз"


class TestDetectFileType:
    """AC4 — единая логика определения типа файла для задачи и оркестратора."""

    @pytest.mark.parametrize(
        "filename,expected",
        [
            ("goods_1_1_abc.xml", "goods"),
            ("import.xml", "goods"),
            ("propertiesGoods_1_1.xml", "goods"),
            ("groups.xml", "goods"),
            ("groups_1_1_abc.xml", "goods"),
            ("units.xml", "all"),
            ("storages.xml", "all"),
            ("offers_1_3_abc.xml", "offers"),
            ("prices_1_2_abc.xml", "prices"),
            ("priceLists.xml", "prices"),
            ("rests_1_16_5e505506.xml", "rests"),
            ("contragents_1_1_abc.xml", "contragents"),
            ("complete", "all"),
            ("unknown.xml", "all"),
            ("", "all"),
            (None, "all"),
        ],
    )
    def test_detect_file_type(self, filename, expected):
        assert detect_file_type(filename) == expected


@pytest.mark.django_db
class TestOrchestratorPassesFilename:
    """AC4 — обе точки диспатча передают имя файла в задачу."""

    def _orchestrator(self, tmp_path, filename):
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        service = ImportOrchestratorService("sess-1", filename)
        service.import_dir = tmp_path / "1c_import"
        service.import_dir.mkdir(parents=True, exist_ok=True)
        return service

    def test_dispatch_import_passes_source_filename(self, tmp_path):
        service = self._orchestrator(tmp_path, "rests_1_16_5e505506.xml")
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        with patch("apps.products.tasks.process_1c_import_task.delay") as mock_delay:
            service._dispatch_import(session)

        assert mock_delay.call_args.kwargs["source_filename"] == "rests_1_16_5e505506.xml"

    def test_dispatch_or_dryrun_passes_source_filename(self, tmp_path):
        service = self._orchestrator(tmp_path, "complete")
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        with (
            patch("apps.products.tasks.process_1c_import_task.delay") as mock_delay,
            patch("apps.integrations.onec_exchange.import_orchestrator.FileStreamService"),
        ):
            service._dispatch_or_dryrun(session, dry_run=False)

        assert mock_delay.call_args.kwargs["source_filename"] == "complete"

    def test_complete_mode_still_means_all(self, tmp_path):
        service = self._orchestrator(tmp_path, "complete")
        assert service._detect_file_type() == "all"

    def test_archive_dispatch_carries_unpacked_xml(self, tmp_path):
        """`mode=import` распаковывает архив в HTTP-обработчике, а не в задаче.

        К старту задачи архива на диске уже нет, и связь «архив → его сегменты»
        она восстановить не может. Значит имена обязан передать оркестратор.
        """
        service = self._orchestrator(tmp_path, "import_files.zip")
        (service.import_dir / "rests").mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(service.import_dir / "import_files.zip", "w") as archive:
            archive.write(_segment_path(1), _segment_name(1))

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)
        service._unpack_zips(session)

        with patch("apps.products.tasks.process_1c_import_task.delay") as mock_delay:
            service._dispatch_import(session)

        assert mock_delay.call_args.kwargs["source_filename"] == ["import_files.zip", _segment_name(1)]

    def test_archive_without_xml_dispatches_its_own_name(self, tmp_path):
        """Архив изображений: задача обязана видеть, что обещали именно архив."""
        service = self._orchestrator(tmp_path, "import_files.zip")
        with zipfile.ZipFile(service.import_dir / "import_files.zip", "w") as archive:
            archive.writestr("import_files/photo.jpg", bytes.fromhex("ffd8ffe0") + b"jpeg-stub")

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)
        service._unpack_zips(session)

        with patch("apps.products.tasks.process_1c_import_task.delay") as mock_delay:
            service._dispatch_import(session)

        assert mock_delay.call_args.kwargs["source_filename"] == ["import_files.zip"]


@pytest.mark.django_db
class TestImportDirectoryLock:
    """AC2 — на каталог обмена одновременно работает ровно одна задача."""

    @staticmethod
    def _lock_key(data_dir: str) -> str:
        return f"onec:import:lock:{data_dir}"

    @patch("apps.products.tasks.call_command")
    def test_lock_taken_and_released(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        seen = {}

        def capture(*args, **kwargs):
            seen["locked"] = cache.get(self._lock_key(data_dir))

        mock_call_command.side_effect = capture

        result = process_1c_import_task.apply(
            args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-1"
        ).get()

        assert result == "success"
        assert seen["locked"] == "task-lock-1", "Во время импорта лок обязан принадлежать задаче"
        assert cache.get(self._lock_key(data_dir)) is None, "Лок обязан сниматься в finally"

    @patch("apps.products.tasks.call_command")
    def test_lock_released_on_failure(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        mock_call_command.side_effect = Exception("boom")
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-2").get()

        assert cache.get(self._lock_key(data_dir)) is None

    @patch("apps.products.tasks.call_command")
    def test_busy_lock_retries_without_touching_session(self, mock_call_command, clean_cache, tmp_path, settings):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        cache.add(self._lock_key(data_dir), "other-task", 60)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with patch.object(process_1c_import_task, "retry", side_effect=Retry()) as mock_retry:
            process_1c_import_task.apply(args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-3")

        mock_retry.assert_called_once()
        assert mock_retry.call_args.kwargs["countdown"] == settings.ONEC_IMPORT_LOCK_RETRY_COUNTDOWN
        assert mock_retry.call_args.kwargs["max_retries"] == settings.ONEC_IMPORT_LOCK_MAX_RETRIES

        mock_call_command.assert_not_called()

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.IN_PROGRESS
        assert cache.get(self._lock_key(data_dir)) == "other-task", "Чужой лок трогать нельзя"

    @patch("apps.products.tasks.call_command")
    def test_max_retries_marks_session_failed(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        cache.add(self._lock_key(data_dir), "other-task", 60)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with patch.object(process_1c_import_task, "retry", side_effect=MaxRetriesExceededError()):
            result = process_1c_import_task.apply(
                args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-4"
            ).get()

        assert result == "failure"
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert session.error_message

    @patch("apps.products.tasks.call_command")
    def test_retry_publish_failure_marks_session_failed(self, mock_call_command, clean_cache, tmp_path):
        """Брокер недоступен: `retry` не доехал — сессия не имеет права висеть IN_PROGRESS."""
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        cache.add(self._lock_key(data_dir), "other-task", 60)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with patch.object(process_1c_import_task, "retry", side_effect=OperationalError("broker down")):
            result = process_1c_import_task.apply(
                args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-5"
            ).get()

        assert result == "failure"
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "broker down" in session.error_message
        mock_call_command.assert_not_called()
        assert cache.get(self._lock_key(data_dir)) == "other-task", "Чужой лок трогать нельзя"

    def test_lock_ttl_is_configured(self, settings):
        """Упавший воркер не блокирует обмен навсегда — лок живёт по TTL из настроек."""
        assert settings.ONEC_IMPORT_LOCK_TTL > 0

    def test_release_lock_only_by_owner(self, clean_cache):
        key = "onec:import:lock:/tmp/whatever"
        cache.add(key, "owner-a", 60)

        _release_import_lock(key, "owner-b")
        assert cache.get(key) == "owner-a", "Чужой лок снимать нельзя"

        _release_import_lock(key, "owner-a")
        assert cache.get(key) is None


@pytest.mark.django_db
class TestTaskUsesSourceFilename:
    """AC4 — сегмент остатков запускает только шаг остатков."""

    @patch("apps.products.tasks.call_command")
    def test_source_filename_drives_file_type(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": data_dir, "source_filename": "rests_1_16_5e505506.xml"},
            task_id="task-ft-1",
        ).get()

        assert mock_call_command.call_args.kwargs["file_type"] == "rests"

    @patch("apps.products.tasks.call_command")
    def test_without_source_filename_stays_all(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-ft-2").get()

        assert mock_call_command.call_args.kwargs["file_type"] == "all"


@pytest.mark.django_db(transaction=True)
class TestImportLockUnderConcurrency:
    """AC2 «ровно одна задача на каталог» — проверка настоящим параллелизмом.

    Проверять сериализацию последовательными вызовами бессмысленно: они не
    пересекаются по времени и разошлись бы и без лока. Здесь одна задача
    физически находится внутри импорта (поток удерживается на `call_command`),
    пока вторая пытается зайти на тот же каталог.

    Лок живёт в Redis, а не в памяти процесса, — поэтому механизм не зависит
    от `--concurrency` воркера: соседний prefork-процесс упирается в тот же ключ.
    """

    LOCK_HOLD_TIMEOUT = 15

    @staticmethod
    def _lock_key(data_dir: str) -> str:
        return f"onec:import:lock:{data_dir}"

    def test_second_task_cannot_enter_while_first_is_importing(self, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)

        holder = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        contender = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        inside_lock = threading.Lock()
        inside: list[int] = []
        peak: list[int] = []
        entered = threading.Event()
        release = threading.Event()

        def guarded_call_command(*args, **kwargs):
            with inside_lock:
                inside.append(kwargs.get("import_session_id"))
                peak.append(len(inside))
            try:
                if kwargs.get("import_session_id") == holder.pk:
                    entered.set()
                    release.wait(timeout=self.LOCK_HOLD_TIMEOUT)
            finally:
                with inside_lock:
                    inside.pop()

        retry_calls: list[dict] = []

        def fake_retry(*args, **kwargs):
            retry_calls.append(kwargs)
            raise Retry()

        holder_result: list[str] = []

        def run_holder():
            try:
                holder_result.append(
                    process_1c_import_task.apply(
                        args=(holder.pk,),
                        # Имена сегментов обязательны: прогон без обещания
                        # сгребает каталог целиком и потому уступает дорогу
                        # активным сессиям (см. TestCompleteDoesNotStealPromisedSegments).
                        # На проде каждый сегмент приходит своим mode=import —
                        # именно эти прогоны лок и обязан сериализовать.
                        kwargs={"data_dir": data_dir, "source_filename": _segment_name(1)},
                        task_id="task-conc-holder",
                    ).get()
                )
            finally:
                connection.close()

        with (
            patch("apps.products.tasks.call_command", side_effect=guarded_call_command),
            patch.object(process_1c_import_task, "retry", side_effect=fake_retry),
        ):
            worker = threading.Thread(target=run_holder, daemon=True)
            worker.start()
            assert entered.wait(timeout=self.LOCK_HOLD_TIMEOUT), "Первая задача не дошла до импорта"

            # Первая задача сейчас физически внутри импорта.
            assert cache.get(self._lock_key(data_dir)) == "task-conc-holder"

            process_1c_import_task.apply(
                args=(contender.pk,),
                kwargs={"data_dir": data_dir, "source_filename": _segment_name(2)},
                task_id="task-conc-contender",
            )

            assert len(retry_calls) == 1, "Вторая задача обязана уйти в retry, а не работать параллельно"
            assert [s for s in inside if s == contender.pk] == [], "Вторая задача вошла в импорт при занятом локе"

            release.set()
            worker.join(timeout=self.LOCK_HOLD_TIMEOUT)

        assert not worker.is_alive()
        assert holder_result == ["success"]
        assert max(peak) == 1, "Одновременно в импорте была больше чем одна задача"
        assert cache.get(self._lock_key(data_dir)) is None, "Лок обязан освободиться после первой задачи"

    def test_lock_is_released_for_the_next_task(self, clean_cache, tmp_path):
        """После освобождения лока следующая задача заходит без retry."""
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)

        first = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        second = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        entered: list[int] = []

        def record(*args, **kwargs):
            entered.append(kwargs.get("import_session_id"))

        with patch("apps.products.tasks.call_command", side_effect=record):
            for index, (session, task_id) in enumerate(((first, "task-seq-1"), (second, "task-seq-2")), start=1):
                process_1c_import_task.apply(
                    args=(session.pk,),
                    kwargs={"data_dir": data_dir, "source_filename": _segment_name(index)},
                    task_id=task_id,
                ).get()

        assert entered == [first.pk, second.pk]
        assert cache.get(self._lock_key(data_dir)) is None


@pytest.mark.django_db
class TestSegmentBacklogBelongsToItsOwnTask:
    """Замечание ревью 2026-08-26: чужой сегмент нельзя ни читать, ни удалять.

    Сериализация лока превратила параллельную гонку в очередь, но не убрала
    проблему: пока задача держит лок, 1С успевает положить в общий каталог
    следующие сегменты. `_collect_xml_files` собирал их по маске `rests_*.xml`,
    прогон обрабатывал и удалял **весь** накопившийся backlog, а собственные
    задачи этих сегментов затем падали `FAILED` — «сегмент не найден».
    Данные при этом в БД попадали, но выгрузка отчитывалась провалом,
    и AC8 («ни одна сессия не в статусе failed») нарушался.
    """

    def test_waiting_segments_are_left_untouched(self, tmp_path):
        """Backlog из четырёх сегментов: прогон читает свой, три ждут своих задач."""
        data_dir = _make_exchange_dir(tmp_path)
        for index in (1, 2, 3, 4):
            _stage_segment(data_dir, index)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        read = _segments_in(_run_import(data_dir, session, source_filename=_segment_name(1)))

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert set(read) == {_segment_name(1)}, "Прогон обязан прочитать только обещанный ему сегмент"

        remaining = {p.name for p in (data_dir / "rests").glob("*.xml")}
        assert remaining == {_segment_name(i) for i in (2, 3, 4)}, "Чужие сегменты обязаны дождаться своих задач"

    def test_full_backlog_queue_loses_nothing_and_fails_nobody(self, tmp_path):
        """Восемь сегментов уже лежат в каталоге, задачи идут по очереди (как под локом)."""
        assert len(REAL_SEGMENTS) >= 8, "Нужны восемь реальных сегментов в фикстурах"

        data_dir = _make_exchange_dir(tmp_path)
        for index in range(1, 9):
            _stage_segment(data_dir, index)

        seen: dict[str, int] = {}
        sessions = []
        for index in range(1, 9):
            session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
            sessions.append(session)
            read = _segments_in(_run_import(data_dir, session, source_filename=_segment_name(index)))
            assert set(read) == {_segment_name(index)}, f"Сегмент {index} прочитал чужие файлы: {set(read)}"
            assert not set(read) & set(seen), "Сегмент прочитан повторно"
            seen.update(read)

        statuses = [ImportSession.objects.get(pk=s.pk).status for s in sessions]
        assert ImportSession.ImportStatus.FAILED not in statuses, "Backlog не имеет права топить чужие сессии"

        expected = {_segment_name(i): len(XMLDataParser().parse_rests_xml(str(_segment_path(i)))) for i in range(1, 9)}
        assert all(count > 0 for count in expected.values())
        assert seen == expected
        assert not list((data_dir / "rests").glob("*.xml")), "Каталог обмена должен опустеть"

    def test_manual_import_still_takes_everything(self, tmp_path):
        """Ручной прогон конкретного файла не обещал — забирает весь каталог, как раньше."""
        data_dir = _make_exchange_dir(tmp_path)
        for index in (1, 2, 3):
            _stage_segment(data_dir, index)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        read = _segments_in(_run_import(data_dir, session))

        assert set(read) == {_segment_name(i) for i in (1, 2, 3)}
        assert not list((data_dir / "rests").glob("*.xml"))


@pytest.mark.django_db
class TestContragentsDoNotSwallowPromisedSegment:
    """Замечание ревью 2026-08-26: `contragents*.xml` в каталоге обходил товарный импорт.

    Задача проверяла наличие любых `contragents*.xml` и, найдя их, звала
    `import_customers_from_1c` вместо импорта обещанного сегмента, после чего
    помечала сессию успешной. Файл контрагентов, оставшийся от соседней сессии,
    таким образом молча съедал сегмент остатков — ровно та потеря данных,
    против которой написана эта стори.
    """

    @staticmethod
    def _exchange_dir(tmp_path: Path) -> Path:
        data_dir = tmp_path / "1c_import"
        (data_dir / "contragents").mkdir(parents=True)
        (data_dir / "contragents" / "contragents_1_1.xml").write_text(
            '<?xml version="1.0" encoding="UTF-8"?><КоммерческаяИнформация/>', encoding="utf-8"
        )
        return data_dir

    @staticmethod
    def _commands(mock_call_command) -> list[str]:
        return [call.args[0] for call in mock_call_command.call_args_list]

    @patch("apps.products.tasks.call_command")
    def test_promised_segment_wins_over_leftover_contragents(self, mock_call_command, clean_cache, tmp_path):
        data_dir = self._exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": _segment_name(2)},
            task_id="task-contragents-1",
        ).get()

        commands = self._commands(mock_call_command)
        assert "import_products_from_1c" in commands, "Обещанный сегмент обязан быть импортирован"
        assert "import_customers_from_1c" not in commands, "Чужие контрагенты не отменяют наш сегмент"
        assert mock_call_command.call_args.kwargs["file_type"] == "rests"
        assert mock_call_command.call_args.kwargs["source_filename"] == [_segment_name(2)]

    @patch("apps.products.tasks.call_command")
    def test_contragents_file_still_routes_to_customers(self, mock_call_command, clean_cache, tmp_path):
        data_dir = self._exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "contragents_1_1.xml"},
            task_id="task-contragents-2",
        ).get()

        assert self._commands(mock_call_command) == ["import_customers_from_1c"]

    @patch("apps.products.tasks.call_command")
    def test_complete_mode_with_contragents_keeps_legacy_route(self, mock_call_command, clean_cache, tmp_path):
        """`mode=complete` конкретного файла не обещает — прежний маршрут сохраняется."""
        data_dir = self._exchange_dir(tmp_path)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "complete"},
            task_id="task-contragents-3",
        ).get()

        assert self._commands(mock_call_command) == ["import_customers_from_1c"]


@pytest.mark.django_db
class TestLockBackendFailure:
    """Замечание ревью 2026-08-26: падение Redis на захвате лока оставляло сессию IN_PROGRESS.

    Отказ публикации `retry` уже переводил сессию в `FAILED`, а отказ самого
    `cache.add` — нет: исключение летело вне обработчиков, и сессия висела
    `IN_PROGRESS` до `cleanup_stale_import_sessions` (порог 2 часа).
    """

    @patch("apps.products.tasks.call_command")
    def test_cache_failure_marks_session_failed(self, mock_call_command, clean_cache, tmp_path):
        data_dir = str(tmp_path / "1c_import")
        Path(data_dir).mkdir(parents=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with patch("apps.products.tasks.cache.add", side_effect=RedisConnectionError("redis down")):
            result = process_1c_import_task.apply(
                args=(session.id,), kwargs={"data_dir": data_dir}, task_id="task-lock-backend-1"
            ).get()

        assert result == "failure"
        mock_call_command.assert_not_called()

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "redis down" in session.error_message


class TestCollectionIsLimitedToPromisedFile:
    """Сужение сбора действует на все шаги прогона, а не только на шаг своего типа.

    Сегмент `offers_….xml` запускает ещё и шаги цен и остатков
    (`file_type in ["all", "prices", "offers"]`). Без сужения такой прогон
    съедал бы уже ожидающие `prices_*`/`rests_*` — тот же backlog, только
    через другое семейство файлов.
    """

    @staticmethod
    def _command() -> Command:
        command = Command()
        command.stdout = StringIO()
        return command

    def test_foreign_family_is_not_collected(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)

        command = self._command()
        command._expected_filenames = {"offers_1_1_abc.xml"}

        assert command._collect_xml_files(str(data_dir), "rests", "rests.xml") == []

    def test_promised_file_is_collected(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)
        _stage_segment(data_dir, 2)

        command = self._command()
        command._expected_filenames = {_segment_name(2).lower()}

        collected = command._collect_xml_files(str(data_dir), "rests", "rests.xml")
        assert [Path(p).name for p in collected] == [_segment_name(2)]

    def test_manual_run_collects_everything(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)
        _stage_segment(data_dir, 2)

        command = self._command()
        command._expected_filenames = None

        collected = command._collect_xml_files(str(data_dir), "rests", "rests.xml")
        assert {Path(p).name for p in collected} == {_segment_name(1), _segment_name(2)}


@pytest.mark.django_db
class TestArchiveOwnsOnlyItsOwnXml:
    """Замечание ревью 2026-08-27: задача архива забирала чужие XML.

    `detect_file_type("import_files.zip")` даёт `goods`, но XML с таким именем
    команда не найдёт никогда — значит обещания нет, значит сбор не сужается,
    значит прогон архива сгребал весь накопившийся backlog соседних
    `goods*.xml`. Решение Alex: связь архива с сегментом обязана быть явной.
    Обещание архива — тот XML, который распаковала и удалила именно эта задача.
    """

    @staticmethod
    def _archive(data_dir: Path, name: str, *, xml_indexes: tuple[int, ...] = (), with_image: bool = False) -> Path:
        """Архив 1С в корне каталога обмена: реальные сегменты и/или картинка."""
        archive = data_dir / name
        with zipfile.ZipFile(archive, "w") as zf:
            for index in xml_indexes:
                zf.write(_segment_path(index), _segment_name(index))
            if with_image:
                zf.writestr("import_files/photo.jpg", bytes.fromhex("ffd8ffe0") + b"jpeg-stub")
        return archive

    @patch("apps.products.tasks.call_command")
    def test_own_xml_from_archive_becomes_the_promise(self, mock_call_command, clean_cache, tmp_path):
        """XML из архива — обещание прогона, и тип берётся из него, а не из имени архива."""
        data_dir = _make_exchange_dir(tmp_path)
        self._archive(data_dir, "import_files.zip", xml_indexes=(1,), with_image=True)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "import_files.zip"},
            task_id="task-archive-own-1",
        ).get()

        kwargs = mock_call_command.call_args.kwargs
        assert kwargs["source_filename"] == [_segment_name(1)]
        assert kwargs["file_type"] == "rests", "Тип обязан следовать за содержимым архива, а не за его именем"

    @patch("apps.products.tasks.call_command")
    def test_image_only_archive_does_not_start_catalog_import(self, mock_call_command, clean_cache, tmp_path):
        """Архив без XML своего сегмента не имеет — чужие ему не принадлежат."""
        data_dir = _make_exchange_dir(tmp_path)
        self._archive(data_dir, "import_files.zip", with_image=True)
        neighbour = _stage_segment(data_dir, 3)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "import_files.zip"},
            task_id="task-archive-images-1",
        ).get()

        mock_call_command.assert_not_called()
        assert neighbour.exists(), "Сегмент соседней сессии обязан дождаться своей задачи"
        assert (data_dir / "goods" / "import_files" / "photo.jpg").exists(), "Картинки должны остаться на месте"

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert "не принёс ни одного XML-сегмента" in session.report

    @patch("apps.products.tasks.call_command")
    def test_promise_list_from_orchestrator_is_honoured(self, mock_call_command, clean_cache, tmp_path):
        """Архив распакован обработчиком `mode=import` — задача получает список имён."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 1)
        _stage_segment(data_dir, 4)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={
                "data_dir": str(data_dir),
                "source_filename": ["import_files.zip", _segment_name(1)],
            },
            task_id="task-archive-list-1",
        ).get()

        kwargs = mock_call_command.call_args.kwargs
        assert kwargs["source_filename"] == [_segment_name(1)]
        assert kwargs["file_type"] == "rests"

    @patch("apps.products.tasks.call_command")
    def test_archive_without_xml_from_orchestrator_skips_import(self, mock_call_command, clean_cache, tmp_path):
        """Список из одного имени архива — «своих сегментов нет», а не «обещания нет»."""
        data_dir = _make_exchange_dir(tmp_path)
        neighbour = _stage_segment(data_dir, 5)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": ["import_files.zip"]},
            task_id="task-archive-list-2",
        ).get()

        mock_call_command.assert_not_called()
        assert neighbour.exists()

    def test_archive_run_does_not_eat_neighbour_segment(self, clean_cache, tmp_path):
        """Сквозной прогон: архив читает только свой сегмент, соседний уцелел."""
        data_dir = _make_exchange_dir(tmp_path)
        self._archive(data_dir, "import_files.zip", xml_indexes=(1,))
        neighbour = _stage_segment(data_dir, 2)
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "import_files.zip"},
            task_id="task-archive-e2e-1",
        ).get()

        assert neighbour.exists(), "Задача архива не имеет права ни читать, ни удалять чужой сегмент"
        assert not (data_dir / "rests" / _segment_name(1)).exists(), "Свой сегмент прочитан и убран"

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED


@pytest.mark.django_db
class TestUnknownSignatureIsNotDeleted:
    """Замечание ревью 2026-08-27: cleanup был fail-open при неснятом отпечатке.

    Если `os.stat()` в момент парсинга вернул None, а парсер файл всё же открыл,
    путь попадал в `_processed_files` без отпечатка — и удалялся безусловно.
    Подмена файла до cleanup снова сносила файл соседа.
    """

    def test_file_without_signature_survives_cleanup(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        own = _stage_segment(data_dir, 1)

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)

        with patch.object(Command, "_file_signature", staticmethod(lambda path: None)):
            output = _run_import(data_dir, session, source_filename=_segment_name(1))

        assert own.exists(), "Без отпечатка сверять нечего — удалять вслепую нельзя"
        assert "Отпечаток" in output
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED


class TestAmbiguousPromisedSegment:
    """Замечание ревью 2026-08-27: два файла, различающиеся регистром, как один сегмент.

    `_collect_xml_files` ищет регистронезависимо (`rests_*.xml`, `Rests_*.xml`),
    и на регистрозависимой ФС оба физических файла проходят сравнение через
    `.lower()`. Один прогон обработал бы и удалил оба, второй ушёл бы в `FAILED`.
    """

    def test_case_variants_of_promised_name_raise(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        lower = _stage_segment(data_dir, 1)
        upper = data_dir / "rests" / lower.name.capitalize()
        shutil.copyfile(_segment_path(2), upper)
        if not lower.exists() or upper.name == lower.name or lower.read_bytes() == upper.read_bytes():
            pytest.skip("Регистронезависимая ФС: два таких файла рядом не существуют")

        command = Command()
        command.stdout = StringIO()
        command._expected_filenames = {lower.name.lower()}

        with pytest.raises(CommandError, match="различаются только регистром"):
            command._collect_xml_files(str(data_dir), "rests", "rests.xml")

    def test_single_match_is_not_ambiguous(self, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        own = _stage_segment(data_dir, 1)

        command = Command()
        command.stdout = StringIO()
        command._expected_filenames = {own.name.lower()}

        collected = command._collect_xml_files(str(data_dir), "rests", "rests.xml")
        assert [Path(path).name for path in collected] == [own.name]


@pytest.mark.django_db
class TestCompleteDoesNotStealPromisedSegments:
    """Прод-прогон AC9 2026-08-27: `mode=complete` воровал сегменты из очереди.

    Штатный протокол этой 1С шлёт `mode=import` на каждый файл **и**
    `mode=complete` следом, каждые пару секунд. Сегмент уходит в очередь за
    локом («Каталог обмена занят»), а подоспевший `complete` обещания не имеет,
    сбор не сужает, забирает каталог целиком — вместе с чужим сегментом — и
    удаляет его. Задача сегмента, получив лок, своего файла не находит и падает.

    Замер прода: 223 сессии, 53 `failed`, и **48 из 48** объяснённых падений
    имели потребителем именно `mode=complete`. Данные при этом доезжали, но
    выгрузка отчитывалась провалом, а пять файлов не прочитал никто.

    Контракт: прогон без обещания не трогает каталог, пока живы другие сессии
    в `IN_PROGRESS` — их файлы заберут собственные задачи. Ровно тот же guard,
    что уже стоит на post-import cleanup и в `views.handle_init`.
    """

    @patch("apps.products.tasks.call_command")
    def test_complete_skips_sweep_while_other_sessions_active(self, mock_call_command, clean_cache, tmp_path):
        data_dir = _make_exchange_dir(tmp_path)
        promised = _stage_segment(data_dir, 6)

        # Сессия соседнего сегмента: её задача стоит в очереди за локом.
        ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        complete_session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(complete_session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "complete"},
            task_id="task-complete-guard-1",
        ).get()

        mock_call_command.assert_not_called()
        assert promised.exists(), "Файл обещан другой сессии — complete не имеет права его забирать"

        complete_session.refresh_from_db()
        assert complete_session.status == ImportSession.ImportStatus.COMPLETED
        assert "другие сессии" in complete_session.report

    @patch("apps.products.tasks.call_command")
    def test_complete_sweeps_when_no_other_sessions_active(self, mock_call_command, clean_cache, tmp_path):
        """Прежнее поведение там, где оно нужно: файлы без хозяина забирает complete."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 7)
        complete_session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(complete_session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "complete"},
            task_id="task-complete-guard-2",
        ).get()

        kwargs = mock_call_command.call_args.kwargs
        assert mock_call_command.call_args.args[0] == "import_products_from_1c"
        assert kwargs["file_type"] == "all"
        assert kwargs["source_filename"] is None

    @patch("apps.products.tasks.call_command")
    def test_promised_segment_runs_even_with_other_sessions_active(self, mock_call_command, clean_cache, tmp_path):
        """Guard бьёт только по несужаемому сбору: свой сегмент идёт как шёл."""
        data_dir = _make_exchange_dir(tmp_path)
        _stage_segment(data_dir, 8)

        ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        own_session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(own_session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": _segment_name(8)},
            task_id="task-complete-guard-3",
        ).get()

        kwargs = mock_call_command.call_args.kwargs
        assert kwargs["source_filename"] == [_segment_name(8)]
        assert kwargs["file_type"] == "rests"

    @patch("apps.products.tasks.call_command")
    def test_unknown_file_type_also_defers_to_active_sessions(self, mock_call_command, clean_cache, tmp_path):
        """`units.xml` тип не определяет и тоже сгребал бы каталог целиком."""
        data_dir = _make_exchange_dir(tmp_path)
        promised = _stage_segment(data_dir, 2)

        ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        units_session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        process_1c_import_task.apply(
            args=(units_session.id,),
            kwargs={"data_dir": str(data_dir), "source_filename": "units.xml"},
            task_id="task-complete-guard-4",
        ).get()

        mock_call_command.assert_not_called()
        assert promised.exists()

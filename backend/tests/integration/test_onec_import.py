"""
Tests for ImportOrchestratorService and related import functionality.

Moved from test_onec_export.py for better test organization.
"""

import base64
import inspect
import io
import logging
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

# Реальные выгрузки 1С (CommerceML 3.1) — синтетические XML для импорта запрещены
# правилами проекта. Здесь закоммиченный срез реальных выгрузок: он доступен в CI,
# поэтому на нём держатся тесты обязательного гейта. Полный назначенный корпус —
# ONEC_RUNTIME_CORPUS ниже.
ONEC_FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "1c-data"

# Порядок соответствует реальной последовательности выгрузки из 1С.
CATALOG_XML_FILES = (
    ONEC_FIXTURES / "groups" / "groups.xml",
    ONEC_FIXTURES / "units" / "units.xml",
    ONEC_FIXTURES / "storages" / "storages.xml",
    ONEC_FIXTURES / "priceLists" / "priceLists.xml",
    ONEC_FIXTURES / "goods" / "import_files" / "goods.xml",
    ONEC_FIXTURES / "offers" / "offers.xml",
    ONEC_FIXTURES / "prices" / "prices.xml",
    ONEC_FIXTURES / "rests" / "rests.xml",
)

CONTRAGENTS_XML = ONEC_FIXTURES / "contragents" / "contragents.xml"

# Назначенный правилами проекта корпус runtime-выгрузок 1С (backend/data/import_1c).
# Каталог в .gitignore, поэтому на раннере его нет — тесты на нём помечаются
# data_dependent и штатно скипаются в CI (как ещё ~32 теста импорта 1С).
ONEC_RUNTIME_CORPUS = Path(__file__).resolve().parents[2] / "data" / "import_1c"

# Разделы выгрузки в порядке, в котором их присылает 1С.
RUNTIME_CORPUS_SECTIONS = (
    "groups",
    "units",
    "storages",
    "priceLists",
    "goods",
    "offers",
    "prices",
    "rests",
)


def _smallest_corpus_segment(section: str) -> Path | None:
    """Наименьший реальный сегмент раздела назначенного корпуса.

    Сегменты одного раздела равнозначны по структуре и отличаются только объёмом,
    поэтому берём самый лёгкий: E2E гоняет настоящий протокол обмена, а не
    измеряет пропускную способность.
    """
    directory = ONEC_RUNTIME_CORPUS / section
    if not directory.is_dir():
        return None
    segments = sorted(directory.glob("*.xml"), key=lambda path: path.stat().st_size)
    return segments[0] if segments else None


def _runtime_corpus_files() -> list[Path]:
    """Полный набор разделов корпуса или пустой список, если корпуса нет."""
    selected: list[Path] = []
    for section in RUNTIME_CORPUS_SECTIONS:
        segment = _smallest_corpus_segment(section)
        if segment is None:
            return []
        selected.append(segment)
    return selected


def get_response_content(response) -> bytes:
    """Helper to get content from both HttpResponse and FileResponse."""
    if hasattr(response, "streaming_content"):
        return b"".join(response.streaming_content)
    return response.content


@pytest.fixture
def onec_user(db):
    """Create a 1C exchange user with proper permissions."""
    user = User.objects.create_user(
        email="1c_import@example.com",
        password="secure_pass_123",
        first_name="1C",
        last_name="Import",
        is_staff=True,
    )
    return user


@pytest.fixture
def authenticated_client(onec_user):
    """APIClient that performs checkauth first to establish session."""
    client = APIClient()
    auth_header = "Basic " + base64.b64encode(b"1c_import@example.com:secure_pass_123").decode("ascii")
    response = client.get(
        "/api/integration/1c/exchange/",
        data={"mode": "checkauth"},
        HTTP_AUTHORIZATION=auth_header,
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert body.startswith("success")
    lines = body.replace("\r\n", "\n").split("\n")
    cookie_name = lines[1]
    cookie_value = lines[2]
    client.cookies[cookie_name] = cookie_value
    return client


@pytest.fixture
def onec_private_dirs(monkeypatch, settings, tmp_path):
    """Configure private 1C runtime directories outside MEDIA_ROOT."""
    media_root = tmp_path / "media"
    private_root = tmp_path / "var" / "onec"
    temp_dir = private_root / "1c_temp"
    import_dir = private_root / "1c_import"

    monkeypatch.setattr(settings, "MEDIA_ROOT", str(media_root), raising=False)
    monkeypatch.setattr(
        settings,
        "ONEC_EXCHANGE",
        {
            **getattr(settings, "ONEC_EXCHANGE", {}),
            "TEMP_DIR": temp_dir,
            "IMPORT_DIR": import_dir,
        },
        raising=False,
    )

    temp_dir.mkdir(parents=True, exist_ok=True)
    import_dir.mkdir(parents=True, exist_ok=True)

    return {
        "media_root": media_root,
        "private_root": private_root,
        "temp_dir": temp_dir,
        "import_dir": import_dir,
    }


@pytest.fixture
def celery_eager():
    """Исполнять Celery-задачи синхронно, не подменяя их моками.

    Нужно для честного E2E: `process_1c_import_task` должен реально отработать
    (распаковка, management-команда импорта, финализация ImportSession),
    а не просто зафиксировать факт вызова `.delay`.
    """
    from freesport.celery import app as celery_app

    previous_eager = celery_app.conf.task_always_eager
    previous_propagates = celery_app.conf.task_eager_propagates
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = False
    try:
        yield
    finally:
        celery_app.conf.task_always_eager = previous_eager
        celery_app.conf.task_eager_propagates = previous_propagates


# ============================================================
# ImportOrchestratorService tests
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestImportOrchestratorService:
    """Tests for ImportOrchestratorService (Fat View refactoring)."""

    def test_orchestrator_is_importable(self):
        """Service class exists and is importable."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        svc = ImportOrchestratorService("test-sessid", "goods.xml")
        assert svc.sessid == "test-sessid"
        assert svc.filename == "goods.xml"

    def test_orchestrator_imported_at_module_level(self):
        """LOW: ImportOrchestratorService must be a top-level import in views.py."""
        import apps.integrations.onec_exchange.views as views_mod

        assert hasattr(views_mod, "ImportOrchestratorService")

        source = inspect.getsource(views_mod.ICExchangeView.handle_import)
        assert "from .import_orchestrator import" not in source

    def test_detect_file_type(self):
        """File type detection works correctly."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        assert ImportOrchestratorService("s", "goods_1.xml")._detect_file_type() == "goods"
        assert ImportOrchestratorService("s", "import_data.xml")._detect_file_type() == "goods"
        assert ImportOrchestratorService("s", "offers_1.xml")._detect_file_type() == "offers"
        assert ImportOrchestratorService("s", "prices_1.xml")._detect_file_type() == "prices"
        assert ImportOrchestratorService("s", "pricelists_1.xml")._detect_file_type() == "prices"
        assert ImportOrchestratorService("s", "rests_1.xml")._detect_file_type() == "rests"
        assert ImportOrchestratorService("s", "unknown.xml")._detect_file_type() == "all"

    def test_handle_import_delegates_to_orchestrator(self, authenticated_client, settings, tmp_path):
        """handle_import in view delegates to ImportOrchestratorService."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "import", "filename": "goods.xml"},
        )
        assert response.status_code in (200, 500)


@pytest.mark.django_db
@pytest.mark.integration
class TestAsyncImportDispatch:
    """Tests for async import dispatch via Celery."""

    def test_execute_dispatches_celery_task(self, onec_private_dirs):
        """MEDIUM: ImportOrchestratorService.execute must dispatch Celery task."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        with patch("apps.products.tasks.process_1c_import_task") as mock_task:
            mock_task.delay.return_value.id = "fake-task-id"
            svc = ImportOrchestratorService("test-sessid", "goods.xml")
            with patch.object(svc, "_transfer_files", return_value=(True, "")), patch.object(
                svc, "_unpack_zips"
            ), patch.object(svc, "_resolve_session") as mock_resolve:
                from apps.products.models import ImportSession

                mock_session = MagicMock()
                mock_session.status = ImportSession.ImportStatus.PENDING
                mock_session.pk = 999
                mock_session.ImportStatus = ImportSession.ImportStatus
                mock_resolve.return_value = mock_session

                success, msg = svc.execute()
                assert success is True
                # source_filename обязателен: без него задача теряет тип сегмента
                # и гоняет полный импорт каталога на каждом файле выгрузки.
                # data_dir — каталог СВОЕЙ сессии: каталог обмена изолирован
                # (стори onec-exchange-dir-isolation).
                mock_task.delay.assert_called_once_with(
                    999,
                    str(onec_private_dirs["import_dir"] / "test-sessid"),
                    source_filename="goods.xml",
                )

    def test_real_xml_upload_and_import_use_private_dirs(self, authenticated_client, onec_private_dirs):
        """Реальный XML обмена не должен появляться под MEDIA_ROOT."""
        real_xml = ONEC_FIXTURES / "goods" / "import_files" / "goods.xml"
        payload = real_xml.read_bytes()
        filename = real_xml.name
        session_key = authenticated_client.session.session_key

        upload_url = "/api/integration/1c/exchange/" f"?mode=file&filename={filename}&sessid={session_key}"
        upload_response = authenticated_client.post(
            upload_url,
            data=payload,
            content_type="application/octet-stream",
        )

        assert upload_response.status_code == 200
        temp_file = onec_private_dirs["temp_dir"] / session_key / filename
        assert temp_file.exists()
        assert temp_file.read_bytes() == payload

        with patch("apps.products.tasks.process_1c_import_task.delay") as mock_task:
            import_response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={
                    "mode": "import",
                    "filename": filename,
                    "sessid": session_key,
                },
            )

            assert import_response.status_code == 200
            assert import_response.content.decode("utf-8") == "success"
            mock_task.assert_called_once()
            assert mock_task.call_args[0][1] == str(onec_private_dirs["import_dir"] / session_key)

        routed_file = onec_private_dirs["import_dir"] / session_key / "goods" / filename
        assert routed_file.exists()
        assert routed_file.read_bytes() == payload
        assert not temp_file.exists()

    def test_full_http_exchange_imports_catalog_from_private_dir(
        self, authenticated_client, onec_private_dirs, celery_eager
    ):
        """AC-3 E2E: checkauth → init → file → complete на реальных XML из 1С.

        Celery работает в eager-режиме, поэтому `process_1c_import_task`
        исполняется по-настоящему: management-команда импорта отрабатывает,
        сессия доходит до COMPLETED, каталог наполняется. Ни один файл при этом
        не появляется под MEDIA_ROOT.
        """
        from apps.products.models import Category, ImportSession, Product

        assert Product.objects.count() == 0

        session_key = authenticated_client.session.session_key

        init_response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "init", "sessid": session_key},
        )
        assert init_response.status_code == 200
        assert f"sessid={session_key}" in init_response.content.decode("utf-8")

        for source in CATALOG_XML_FILES:
            self._upload(authenticated_client, session_key, source)
            uploaded = onec_private_dirs["temp_dir"] / session_key / source.name
            assert uploaded.exists(), f"{source.name} не попал в приватный temp-каталог"

        complete_response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "complete", "sessid": session_key},
        )
        assert complete_response.status_code == 200
        assert "success" in get_response_content(complete_response).decode("utf-8")

        session = ImportSession.objects.filter(session_key=session_key).latest("pk")
        assert session.status == ImportSession.ImportStatus.COMPLETED, (
            f"Сессия не завершилась: status={session.status}, "
            f"error={session.error_message}, report={session.report}"
        )
        assert session.celery_task_id, "Задача Celery не отработала — celery_task_id пуст"

        assert Product.objects.count() > 0, "Реальный goods.xml не создал ни одного товара"
        assert Category.objects.count() > 0, "Реальный groups.xml не создал ни одной категории"

        media_root = onec_private_dirs["media_root"]
        assert not (media_root / "1c_import").exists()
        assert not (media_root / "1c_temp").exists()

    def test_full_http_exchange_imports_contragents_from_private_dir(
        self, authenticated_client, onec_private_dirs, celery_eager
    ):
        """AC-3 E2E: тот же цикл для выгрузки контрагентов."""
        from apps.products.models import ImportSession
        from apps.users.models import Company

        companies_before = Company.objects.count()
        session_key = authenticated_client.session.session_key

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "init", "sessid": session_key},
        )
        self._upload(authenticated_client, session_key, CONTRAGENTS_XML)

        complete_response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "complete", "sessid": session_key},
        )
        assert complete_response.status_code == 200
        assert "success" in get_response_content(complete_response).decode("utf-8")

        session = ImportSession.objects.filter(session_key=session_key).latest("pk")
        assert session.status == ImportSession.ImportStatus.COMPLETED, (
            f"Сессия не завершилась: status={session.status}, "
            f"error={session.error_message}, report={session.report}"
        )
        assert Company.objects.count() > companies_before, "Реальный contragents.xml не создал ни одной компании"

        media_root = onec_private_dirs["media_root"]
        assert not (media_root / "1c_import").exists()
        assert not (media_root / "1c_temp").exists()

    @pytest.mark.data_dependent
    def test_full_http_exchange_on_designated_runtime_corpus(
        self, authenticated_client, onec_private_dirs, celery_eager
    ):
        """AC-3 E2E на назначенном корпусе backend/data/import_1c.

        Правило проекта требует прогонять импорт 1С именно на runtime-выгрузках
        из `data/import_1c/`, а не только на закоммиченном срезе в
        `tests/fixtures/1c-data/`. Каталог в .gitignore, поэтому на раннере тест
        скипается — как и остальные ~32 теста корпуса, помеченные data_dependent.
        Маркера slow здесь нет намеренно: он означает «таймингозависимый», а этот
        тест зависит от данных, и из `make test-integration` выпадать не должен.
        """
        from apps.products.models import ImportSession, Product

        corpus_files = _runtime_corpus_files()
        if not corpus_files:
            pytest.skip(
                f"Назначенный корпус выгрузок 1С недоступен: {ONEC_RUNTIME_CORPUS} "
                f"(нужны разделы {', '.join(RUNTIME_CORPUS_SECTIONS)})"
            )

        session_key = authenticated_client.session.session_key

        init_response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "init", "sessid": session_key},
        )
        assert init_response.status_code == 200

        for source in corpus_files:
            self._upload(authenticated_client, session_key, source)
            uploaded = onec_private_dirs["temp_dir"] / session_key / source.name
            assert uploaded.exists(), f"{source.name} не попал в приватный temp-каталог"
            assert not (onec_private_dirs["media_root"] / "1c_temp" / session_key / source.name).exists()

        complete_response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "complete", "sessid": session_key},
        )
        assert complete_response.status_code == 200
        assert "success" in get_response_content(complete_response).decode("utf-8")

        session = ImportSession.objects.filter(session_key=session_key).latest("pk")
        assert session.status == ImportSession.ImportStatus.COMPLETED, (
            f"Сессия не завершилась на реальном корпусе: status={session.status}, "
            f"error={session.error_message}, report={session.report}"
        )
        assert Product.objects.count() > 0, "Реальная выгрузка 1С не создала ни одного товара"

        media_root = onec_private_dirs["media_root"]
        assert not (media_root / "1c_import").exists()
        assert not (media_root / "1c_temp").exists()

    def test_full_http_exchange_unpacks_zip_inside_private_dir(
        self, authenticated_client, onec_private_dirs, celery_eager, caplog
    ):
        """AC-3 E2E: ZIP-выгрузка распаковывается и маршрутизируется в приватном каталоге.

        1С штатно присылает архив, а не отдельные XML. Ветка распаковки раньше
        подтверждалась только mock-based тестом — здесь она проходит настоящий
        протокол обмена и настоящую Celery-задачу.
        """
        from apps.products.models import Category, ImportSession, Product

        archive_buffer = io.BytesIO()
        with zipfile.ZipFile(archive_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for source in CATALOG_XML_FILES:
                archive.writestr(source.name, source.read_bytes())
        payload = archive_buffer.getvalue()

        session_key = authenticated_client.session.session_key

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "init", "sessid": session_key},
        )

        upload_response = authenticated_client.post(
            f"/api/integration/1c/exchange/?mode=file&filename=catalog.zip&sessid={session_key}",
            data=payload,
            content_type="application/octet-stream",
        )
        assert upload_response.status_code == 200
        assert upload_response.content.decode("utf-8") == "success"

        uploaded_archive = onec_private_dirs["temp_dir"] / session_key / "catalog.zip"
        assert uploaded_archive.exists(), "Архив не попал в приватный temp-каталог"

        # Логгер задачи импорта объявлен как getLogger("import_tasks"), не по __name__.
        with caplog.at_level(logging.INFO, logger="import_tasks"):
            complete_response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "complete", "sessid": session_key},
            )
        assert complete_response.status_code == 200
        assert "success" in get_response_content(complete_response).decode("utf-8")

        session = ImportSession.objects.filter(session_key=session_key).latest("pk")
        assert session.status == ImportSession.ImportStatus.COMPLETED, (
            f"Сессия не завершилась: status={session.status}, "
            f"error={session.error_message}, report={session.report}"
        )

        # Отчёт сессии здесь ненадёжен: в eager-режиме задача отрабатывает внутри
        # `.delay()`, и оркестратор дописывает свой (устаревший) объект следом.
        # Лог задачи фиксирует и факт распаковки, и каталог назначения.
        unpack_records = [
            record for record in caplog.records if record.getMessage().startswith("Unpacked: catalog.zip")
        ]
        assert (
            unpack_records
        ), f"Нет записи о распаковке архива в логах задачи: {[r.getMessage() for r in caplog.records]}"
        assert (
            str(onec_private_dirs["import_dir"]) in unpack_records[0].getMessage()
        ), f"Архив распакован не в приватный каталог: {unpack_records[0].getMessage()}"

        # Импорт читает распакованные файлы только из ONEC_EXCHANGE["IMPORT_DIR"],
        # поэтому созданные сущности доказывают, что распаковка шла в приватный каталог.
        assert Product.objects.count() > 0, "ZIP-выгрузка не создала ни одного товара"
        assert Category.objects.count() > 0, "ZIP-выгрузка не создала ни одной категории"

        media_root = onec_private_dirs["media_root"]
        assert not (media_root / "1c_import").exists()
        assert not (media_root / "1c_temp").exists()
        assert not (onec_private_dirs["import_dir"] / "catalog.zip").exists(), "Архив не удалён после распаковки"

    @staticmethod
    def _upload(client, session_key: str, source: Path) -> None:
        """Один шаг mode=file протокола обмена."""
        response = client.post(
            f"/api/integration/1c/exchange/?mode=file&filename={source.name}&sessid={session_key}",
            data=source.read_bytes(),
            content_type="application/octet-stream",
        )
        assert response.status_code == 200
        assert response.content.decode("utf-8") == "success", f"Загрузка {source.name} провалилась"

    def test_execute_no_call_command(self):
        """Import orchestrator must not use call_command (synchronous)."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        source = inspect.getsource(ImportOrchestratorService)
        assert "call_command" not in source


@pytest.mark.django_db
@pytest.mark.integration
class TestFinalizeBatchReliability:
    """Tests for finalize_batch file transfer error propagation."""

    def test_finalize_batch_fails_on_transfer_error(self, settings, tmp_path):
        """MEDIUM: finalize_batch must return failure when file transfer fails."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)

        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        svc = ImportOrchestratorService("test-finalize-fail", "goods.xml")

        with patch.object(svc, "_transfer_files", return_value=(False, "disk full")), patch.object(
            svc, "_resolve_complete_session"
        ) as mock_resolve:
            mock_session = MagicMock()
            mock_session.report = ""
            mock_resolve.return_value = mock_session

            with patch("apps.integrations.onec_exchange.import_orchestrator.FileStreamService") as mock_fs_cls:
                mock_fs_cls.return_value.is_complete.return_value = False

                success, msg = svc.finalize_batch()
                assert success is False
                assert "disk full" in msg

    def test_transfer_files_reports_partial_failure(self, settings, tmp_path):
        """MEDIUM: _transfer_files returns failure when some files fail to move."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)

        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        svc = ImportOrchestratorService("test-partial", "goods.xml")

        with patch("apps.integrations.onec_exchange.import_orchestrator.FileStreamService") as mock_fs_cls, patch(
            "apps.integrations.onec_exchange.import_orchestrator.FileRoutingService"
        ) as mock_rs_cls:
            mock_fs_cls.return_value.list_files.return_value = ["a.xml", "b.xml"]
            mock_rs_cls.return_value.move_to_import.side_effect = [
                None,
                OSError("permission denied"),
            ]

            mock_session = MagicMock()
            mock_session.report = ""

            ok, msg = svc._transfer_files(mock_session)
            assert ok is False
            assert "b.xml" in msg


@pytest.mark.django_db
@pytest.mark.integration
class TestTransferFilesUnified:
    """Tests for unified _transfer_files (code duplication fix)."""

    def test_no_transfer_files_complete_method(self):
        """LOW: _transfer_files_complete should no longer exist."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        assert not hasattr(ImportOrchestratorService, "_transfer_files_complete")

    def test_transfer_files_accepts_label_param(self):
        """LOW: _transfer_files accepts a label parameter for log context."""
        from apps.integrations.onec_exchange.import_orchestrator import ImportOrchestratorService

        sig = inspect.signature(ImportOrchestratorService._transfer_files)
        assert "label" in sig.parameters


# ============================================================
# Zip Slip protection (import-related security)
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestZipSlipProtection:
    """Tests for Zip Slip vulnerability protection in handle_import."""

    def test_handle_import_rejects_zip_slip(self, authenticated_client, settings, tmp_path):
        """CRITICAL: Malicious ZIP with path traversal must be rejected."""
        import_dir = tmp_path / "1c_import"
        import_dir.mkdir(parents=True, exist_ok=True)
        settings.MEDIA_ROOT = str(tmp_path)

        malicious_zip = import_dir / "malicious.zip"
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("../../etc/evil.txt", "pwned")
        malicious_zip.write_bytes(buf.getvalue())

        evil_path = tmp_path / "etc" / "evil.txt"
        assert not evil_path.exists()


# ============================================================
# View-level test for mode=complete
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestModeComplete:
    """View-level integration test for GET /?mode=complete."""

    def test_mode_complete_delegates_to_orchestrator(self, authenticated_client, settings, tmp_path):
        """Verify mode=complete delegates to ImportOrchestratorService.finalize_batch."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)

        with patch("apps.integrations.onec_exchange.views.ImportOrchestratorService") as MockOrch:
            MockOrch.return_value.finalize_batch.return_value = (True, "ok")

            response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "complete"},
            )
            assert response.status_code == 200
            content = get_response_content(response).decode("utf-8")
            assert "success" in content
            MockOrch.return_value.finalize_batch.assert_called_once()

    def test_mode_complete_returns_failure_on_error(self, authenticated_client, settings, tmp_path):
        """Verify mode=complete returns failure when finalize_batch fails."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)

        with patch("apps.integrations.onec_exchange.views.ImportOrchestratorService") as MockOrch:
            MockOrch.return_value.finalize_batch.return_value = (
                False,
                "transfer error",
            )

            response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "complete"},
            )
            assert response.status_code == 200
            content = get_response_content(response).decode("utf-8")
            assert "failure" in content
            assert "transfer error" in content

    def test_mode_complete_without_sessid(self, authenticated_client, settings, tmp_path):
        """Verify mode=complete without sessid returns failure."""
        settings.MEDIA_ROOT = str(tmp_path)

        with patch(
            "apps.integrations.onec_exchange.views.ICExchangeView._get_exchange_identity",
            return_value=None,
        ):
            response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "complete"},
            )
            assert response.status_code == 200
            content = get_response_content(response).decode("utf-8")
            assert "failure" in content

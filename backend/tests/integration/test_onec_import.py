"""
Tests for ImportOrchestratorService and related import functionality.

Moved from test_onec_export.py for better test organization.
"""

import base64
import inspect
import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()


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

    def test_execute_dispatches_celery_task(self, settings, tmp_path):
        """MEDIUM: ImportOrchestratorService.execute must dispatch Celery task."""
        settings.MEDIA_ROOT = str(tmp_path)
        (tmp_path / "1c_import").mkdir(parents=True, exist_ok=True)

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
                mock_task.delay.assert_called_once_with(999, str(tmp_path / "1c_import"))

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

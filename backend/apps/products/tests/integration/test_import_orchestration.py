from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.models import ImportSession


@pytest.mark.django_db
class TestImportOrchestration:
    @pytest.fixture
    def onec_private_dirs(self, monkeypatch, settings, tmp_path):
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
    def api_client(self):
        return APIClient()

    @pytest.fixture
    def exchange_user(self, db):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        user = User.objects.create_user(
            email="exchange@example.com",
            password="password",
            first_name="Exchange",
            last_name="User",
        )
        # Assuming Is1CExchangeUser permission check allows this user
        # Let's make him staff just in case
        user.is_staff = True
        user.save()
        return user

    def test_mode_import_triggers_task(self, api_client, exchange_user, onec_private_dirs):
        """TC1: mode=import creates session and triggers task"""
        api_client.login(email="exchange@example.com", password="password")

        # Step 1: checkauth to establish session
        auth_url = reverse("integrations:onec_exchange:exchange") + "?mode=checkauth"
        api_client.get(auth_url)

        # Get session id
        session_key = api_client.session.session_key

        url = reverse("integrations:onec_exchange:exchange") + f"?mode=import&filename=test.xml&sessid={session_key}"

        with patch("apps.products.tasks.process_1c_import_task.delay") as mock_task:
            response = api_client.get(url)

            assert response.status_code == 200
            assert "success" in response.content.decode()

            # Check session created
            session = ImportSession.objects.latest("created_at")
            assert session is not None
            # Race-fix: session marked IN_PROGRESS before Celery dispatch (see
            # import_orchestrator.py::_dispatch_import) to guard shared import_dir
            # from concurrent cleanup while still PENDING in the Celery queue.
            assert session.status == ImportSession.ImportStatus.IN_PROGRESS
            assert "test.xml" in session.report

            # Check task triggered
            mock_task.assert_called_once_with(session.pk, str(onec_private_dirs["import_dir"]))

    def test_mode_import_blocks_duplicate(self, api_client, exchange_user):
        """TC7: mode=import blocks if another import is active"""
        api_client.login(email="exchange@example.com", password="password")
        api_client.get(reverse("integrations:onec_exchange:exchange") + "?mode=checkauth")
        session_key = api_client.session.session_key

        # Create an active session for the same sessid
        ImportSession.objects.create(
            session_key=session_key,
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.IN_PROGRESS,
        )

        url = reverse("integrations:onec_exchange:exchange") + f"?mode=import&filename=test.xml&sessid={session_key}"

        response = api_client.get(url)

        assert response.status_code == 200
        assert "success" in response.content.decode()

        # Ensure no new session created (only the one we created manually exists)
        assert ImportSession.objects.count() == 1
        session = ImportSession.objects.first()
        assert session is not None
        assert session.status == ImportSession.ImportStatus.IN_PROGRESS

    def test_zip_passing_to_task(self, api_client, exchange_user, onec_private_dirs):
        """Test that ZIP filename is passed to the task for async unpacking"""
        api_client.login(email="exchange@example.com", password="password")
        api_client.get(reverse("integrations:onec_exchange:exchange") + "?mode=checkauth")
        session_key = api_client.session.session_key

        # Mock FileStreamService to ensure it is NOT used for unpacking in view
        with patch("apps.integrations.onec_exchange.views.FileStreamService") as mock_service_class:
            mock_service = mock_service_class.return_value

            url = (
                reverse("integrations:onec_exchange:exchange")
                + f"?mode=import&filename=import.zip&sessid={session_key}"
            )

            with patch("apps.products.tasks.process_1c_import_task.delay") as mock_task:
                response = api_client.get(url)

                assert response.status_code == 200
                assert "success" in response.content.decode()

                # Verify unpack_zip was NOT called in view
                mock_service.unpack_zip.assert_not_called()

                # Verify task was called without filename (handled in orchestrator)
                mock_task.assert_called_once()
                args = mock_task.call_args[0]
                # args[0]: session_id, args[1]: data_dir
                assert len(args) == 2
                assert str(onec_private_dirs["import_dir"]) == args[1]

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_logic(self, mock_call_command, db, tmp_path):
        """Test process_1c_import_task updates session correctly on success"""
        from typing import Any, cast

        from apps.products.tasks import process_1c_import_task

        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.PENDING,
            report="Initial report\n",
        )

        # Create a mock for 'self'
        mock_self = MagicMock()
        mock_self.request.id = "fake-task-id"

        # Bind the task function to mock_self and call it
        # This bypasses Celery's task wrapper but keeps the 'self' argument
        # Use cast(Any, ...) to avoid mypy error about __wrapped__
        task_func = cast(Any, process_1c_import_task)
        data_dir = tmp_path / "var" / "onec" / "1c_import"
        task_func.__wrapped__.__get__(mock_self, type(mock_self))(session_id=session.pk, data_dir=str(data_dir))

        # Verification
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.celery_task_id == "fake-task-id"
        assert "Задача Celery запущена" in session.report
        assert "Импорт успешно завершен" in session.report
        assert session.finished_at is not None

        # Check call_command
        mock_call_command.assert_called_once_with(
            "import_products_from_1c",
            celery_task_id="fake-task-id",
            file_type="all",
            import_session_id=session.pk,
            data_dir=str(data_dir),
        )

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_error_handling(self, mock_call_command, db):
        """Test process_1c_import_task updates session correctly on failure"""
        from typing import Any, cast

        from django.core.management import CommandError

        from apps.products.tasks import process_1c_import_task

        session = ImportSession.objects.create(
            import_type=ImportSession.ImportType.CATALOG,
            status=ImportSession.ImportStatus.PENDING,
        )

        # Mock failure in call_command
        mock_call_command.side_effect = CommandError("Simulated error")

        mock_self = MagicMock()
        mock_self.request.id = "error-task-id"

        task_func = cast(Any, process_1c_import_task)
        task_func.__wrapped__.__get__(mock_self, type(mock_self))(session_id=session.pk)

        # Verification
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert session.error_message == "Simulated error"
        assert "ОШИБКА КОМАНДЫ: Simulated error" in session.report

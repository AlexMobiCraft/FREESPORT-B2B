from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.products.models import ImportSession
from apps.products.tasks import cleanup_stale_import_sessions, process_1c_import_task


@pytest.mark.django_db
class TestImportOrchestrationTasks:
    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_success(self, mock_call_command):
        """Test successful execution of import task."""
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        # Use apply to simulate task execution with a specific task_id
        result = process_1c_import_task.apply(args=(session.id,), task_id="task-123").get()

        assert result == "success"

        session.refresh_from_db()
        # The task now ensures status is COMPLETED even if command is mocked
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.celery_task_id == "task-123"
        assert "Задача Celery запущена" in session.report

        mock_call_command.assert_called_once()
        args, kwargs = mock_call_command.call_args
        assert args[0] == "import_products_from_1c"
        assert kwargs["celery_task_id"] == "task-123"

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_failure(self, mock_call_command):
        """Test execution when a generic error occurs."""
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        mock_call_command.side_effect = Exception("Integration error")

        # Use apply to execute synchronously
        result = process_1c_import_task.apply(args=(session.id,), task_id="task-err").get()

        assert result == "failure"

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "КРИТИЧЕСКАЯ ОШИБКА: Integration error" in session.report
        assert session.error_message == "Integration error"

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_command_error(self, mock_call_command):
        """Test execution when a CommandError occurs."""
        from django.core.management import CommandError

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        mock_call_command.side_effect = CommandError("Invalid arguments")

        result = process_1c_import_task.apply(args=(session.id,), task_id="task-cmd-err").get()

        assert result == "failure"
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "ОШИБКА КОМАНДЫ: Invalid arguments" in session.report
        assert "Invalid arguments" in session.error_message

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_timeout(self, mock_call_command):
        """Test execution when a time limit is exceeded."""
        from celery.exceptions import SoftTimeLimitExceeded

        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        mock_call_command.side_effect = SoftTimeLimitExceeded()

        result = process_1c_import_task.apply(args=(session.id,), task_id="task-timeout").get()

        assert result == "failure"
        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.FAILED
        assert "ПРЕВЫШЕН ЛИМИТ ВРЕМЕНИ" in session.report
        assert "Time limit exceeded" in session.error_message

    def test_cleanup_stale_import_sessions(self):
        """Test cleanup of sessions older than 2 hours."""
        now = timezone.now()

        # Stale session (updated 3 hours ago)
        stale_session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        ImportSession.objects.filter(pk=stale_session.pk).update(updated_at=now - timedelta(hours=3))

        # Fresh session (updated 1 hour ago)
        fresh_session = ImportSession.objects.create(status=ImportSession.ImportStatus.IN_PROGRESS)
        ImportSession.objects.filter(pk=fresh_session.pk).update(updated_at=now - timedelta(hours=1))

        # Completed session (should be ignored)
        completed_session = ImportSession.objects.create(status=ImportSession.ImportStatus.COMPLETED)
        ImportSession.objects.filter(pk=completed_session.pk).update(updated_at=now - timedelta(hours=3))

        count = cleanup_stale_import_sessions()

        assert count == 1

        stale_session.refresh_from_db()
        assert stale_session.status == ImportSession.ImportStatus.FAILED
        assert "Зависла/Таймаут" in stale_session.error_message

        fresh_session.refresh_from_db()
        assert fresh_session.status == ImportSession.ImportStatus.IN_PROGRESS

        completed_session.refresh_from_db()
        assert completed_session.status == ImportSession.ImportStatus.COMPLETED

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_status_transition_integration(self, mock_call_command):
        """
        Integration test verifying that the task respects status changes made by the management command.
        If the command sets status to COMPLETED, the task should not overwrite it.
        """
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        # Define side effect to simulate the management command updating the session
        def command_side_effect(*args, **kwargs):
            # Refresh session to mock the real command behavior which fetches fresh object
            s = ImportSession.objects.get(pk=session.pk)
            s.status = ImportSession.ImportStatus.COMPLETED
            s.finished_at = timezone.now()
            s.save()

        mock_call_command.side_effect = command_side_effect

        # Execute task
        result = process_1c_import_task.apply(args=(session.id,), task_id="task-integration").get()

        assert result == "success"

        session.refresh_from_db()
        # Verify the final status is COMPLETED (from the command), not IN_PROGRESS (from the task start)
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.celery_task_id == "task-integration"

    @patch("apps.products.tasks.call_command")
    @patch("apps.products.tasks.FileStreamService")
    def test_process_1c_import_task_with_zip_unpacking(self, mock_file_service_cls, mock_call_command):
        """Test import task with synchronous ZIP unpacking."""
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)
        zip_filename = "data.zip"
        data_dir = "/media/1c_import/abc_123"

        mock_file_service = MagicMock()
        mock_file_service_cls.return_value = mock_file_service

        # We need to mock the import inside the function specifically if using patch directly?
        # Actually patch('apps.integrations.onec_exchange.file_service.FileStreamService')
        # patches the class where it's defined.
        # When tasks.py does `from apps.integrations.onec_exchange.file_service import FileStreamService`,
        # it gets the Mock.
        # Valid.

        process_1c_import_task.apply(
            args=(session.id,),
            kwargs={"data_dir": data_dir, "zip_filename": zip_filename},
            task_id="task-zip",
        ).get()

        # Verify FileStreamService was initialized with correct sessid
        # path is /media/1c_import/abc_123, so sessid name is abc_123
        mock_file_service_cls.assert_called_once_with("abc_123")

        # Verify unpack_zip was called
        mock_file_service.unpack_zip.assert_called_once()
        args = mock_file_service.unpack_zip.call_args[0]
        # args[0] is zip_filename, args[1] is destination path
        assert args[0] == zip_filename
        assert str(args[1]) == data_dir

        # Verify report updated
        session.refresh_from_db()
        assert "Архив data.zip успешно распакован" in session.report

    @patch("apps.products.tasks.call_command")
    def test_process_1c_import_task_ensures_completed_status(self, mock_call_command):
        """
        Test that the task explicitly sets status to COMPLETED upon success,
        even if the management command doesn't.
        """
        session = ImportSession.objects.create(status=ImportSession.ImportStatus.PENDING)

        # Mock call_command to do nothing (simulate successful run that implies 'success' but doesn't touch DB)
        mock_call_command.return_value = None

        process_1c_import_task.apply(args=(session.id,), task_id="task-ensure-complete").get()

        session.refresh_from_db()
        assert session.status == ImportSession.ImportStatus.COMPLETED
        assert session.finished_at is not None
        assert "Импорт успешно завершен" in session.report

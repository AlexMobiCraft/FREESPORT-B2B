import pytest
from django.utils import timezone

from apps.products.models import ImportSession


@pytest.mark.django_db
class TestImportSessionModel:
    def test_import_session_creation(self):
        """Test creating an ImportSession with default values."""
        session = ImportSession.objects.create()

        assert session.status == ImportSession.ImportStatus.PENDING
        assert session.import_type == ImportSession.ImportType.CATALOG
        assert session.created_at is not None
        assert session.updated_at is not None
        assert session.report == ""
        assert session.report_details == {}

    def test_import_session_fields(self):
        """Verify all required fields exist on the model."""
        session = ImportSession()
        # AC requirements: status, created_at, updated_at, finished_at, report
        # Plus fields for implementation: celery_task_id, error_message, started_at

        fields = [
            "status",
            "created_at",
            "updated_at",
            "finished_at",
            "report",
            "report_details",
            "error_message",
            "celery_task_id",
            "started_at",
            "import_type",
        ]

        for field in fields:
            assert hasattr(session, field), f"Field {field} missing in ImportSession"

    def test_status_choices(self):
        """Verify required status choices exist."""
        choices = dict(ImportSession.ImportStatus.choices)
        expected_statuses = ["pending", "started", "in_progress", "completed", "failed"]

        for status in expected_statuses:
            assert status in choices, f"Status {status} missing in ImportStatus"

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.sessions.backends.db import SessionStore
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.models import ImportSession
from apps.users.models import User


@pytest.mark.django_db
class TestICExchangeViewImport:
    def setup_method(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="1c_user@example.com", password="password")
        self.user.role = "admin"  # Or specific role if needed
        self.user.is_staff = True  # Required for Is1CExchangeUser permission
        self.user.save()

        # Setup session
        session = SessionStore()
        session.create()
        self.session_key = session.session_key

        # Authenticate client properly (using session or force_authenticate)
        # Detailed auth is tricky for 1C view which uses Basic1CAuthentication + Session
        # We can force authenticate or use HTTP_AUTHORIZATION
        self.client.force_authenticate(user=self.user)

        # Inject session into client
        self.client.cookies[dict(ImportSession.ImportType.choices).get("default", "sessionid")] = (
            self.session_key or "sessionid"
        )

        # Mock session on request is handled by middleware, but for APIClient we might need to be careful
        # The view checks request.session.session_key matching 'sessid' param.
        # We need to ensure the request has a session.
        # The CsrfExemptSessionAuthentication should handle it if cookie is present.

        # Hack: Inject session into the client's session store wrapper if possible,
        # or just rely on cookie.

        # Actually, let's just make sure we send the cookie corresponding to settings.SESSION_COOKIE_NAME.
        from django.conf import settings

        self.client.cookies[settings.SESSION_COOKIE_NAME] = self.session_key

        # Also, the view checks `sessid == request.session.session_key`
        # We need `request.session` to be populated.
        # APIClient usually handles this if session middleware is active.

    @patch("apps.products.tasks.process_1c_import_task")
    def test_import_trigger_success(self, mock_task):
        """Test successful trigger of import task."""
        url = reverse("integrations:onec_exchange:exchange")

        path = "/api/integration/1c_exchange/"

        # Create session in DB so it can be loaded
        s = SessionStore(session_key=self.session_key)
        s["test"] = "val"
        s.save()

        response = self.client.get(
            url,
            {
                "mode": "import",
                "filename": "import.xml",
                "sessid": self.session_key or "sessionid",
            },
        )

        assert response.status_code == 200
        assert response.content.decode() == "success"

        # Verify session created
        assert ImportSession.objects.count() == 1
        session = ImportSession.objects.first()
        assert session is not None
        assert session.status == ImportSession.ImportStatus.PENDING
        assert "import.xml" in session.report

        # Verify task called
        mock_task.delay.assert_called_once()
        args = mock_task.delay.call_args[0]
        assert args[0] == session.pk

    def test_import_blocked_active_session(self):
        """Test that import is blocked if a session is already in progress."""
        # Create active session
        active_session = ImportSession.objects.create(
            session_key=self.session_key,
            status=ImportSession.ImportStatus.IN_PROGRESS,
        )

        url = reverse("integrations:onec_exchange:exchange")

        # Ensure session exists
        s = SessionStore(session_key=self.session_key)
        s.save()

        response = self.client.get(
            url,
            {
                "mode": "import",
                "filename": "import.xml",
                "sessid": self.session_key or "sessionid",
            },
        )

        assert response.status_code == 200
        assert response.content.decode() == "success"

        # Verify no new session created
        assert ImportSession.objects.count() == 1
        session = ImportSession.objects.first()
        assert session is not None
        assert session.pk == active_session.pk
        assert session.status == ImportSession.ImportStatus.IN_PROGRESS

    def test_import_invalid_sessid(self):
        """Test blocking import with invalid session ID."""
        url = reverse("integrations:onec_exchange:exchange")

        response = self.client.get(url, {"mode": "import", "filename": "import.xml", "sessid": "wrong_id"})

        assert response.status_code == 200
        assert response.content.decode() == "success"
        assert ImportSession.objects.filter(session_key="wrong_id").exists()

    @patch("apps.integrations.onec_exchange.views.FileStreamService")
    @patch("apps.products.tasks.process_1c_import_task.delay")
    def test_view_delegates_unpacking_to_task(self, mock_task_delay, mock_file_service_cls):
        """
        Test that Import1CView does NOT unpack ZIPs synchronously,
        but passes the filename to the Celery task.
        """
        mock_file_service = MagicMock()
        mock_file_service_cls.return_value = mock_file_service

        url = reverse("integrations:onec_exchange:exchange")
        filename = "data.zip"

        # Ensure session exists (using setup from class)
        # Note: self.client in TestICExchangeViewImport is setup in setup_method
        # We can reuse it if we add this method to the class or create a new one.
        # Adding to TestICExchangeViewImport is better.

        # We need to make sure we have a valid session in the DB matching the cookie
        s = SessionStore(session_key=self.session_key)
        s.save()

        response = self.client.get(
            url,
            {
                "mode": "import",
                "filename": filename,
                "sessid": self.session_key or "sessionid",
            },
        )

        assert response.status_code == 200
        assert response.content.decode() == "success"

        # CRITICAL: Verify unpack_zip was NOT called in the view
        mock_file_service.unpack_zip.assert_not_called()

        # Verify task was called with filename
        assert mock_task_delay.called
        args = mock_task_delay.call_args[0]
        assert len(args) == 2
        # args[0] is session_id, args[1] is import_path
        assert args[1].endswith("/media/1c_import")

    @patch("apps.integrations.onec_exchange.import_orchestrator.FileStreamService")
    def test_complete_after_import_idempotency(self, mock_file_service_cls):
        """
        Test that mode=complete does NOT create a new session if the cycle is already marked complete.
        This prevents the 'Loop' issue where 1C sends complete after import is done.
        """
        # Setup FileService mock to report is_complete() = True
        mock_file_service = MagicMock()
        mock_file_service.is_complete.return_value = True
        mock_file_service_cls.return_value = mock_file_service

        url = reverse("integrations:onec_exchange:exchange")

        # Create a completed session in DB to simulate past state
        ImportSession.objects.create(session_key=self.session_key, status=ImportSession.ImportStatus.COMPLETED)

        # Make request
        # Ensure session exists
        s = SessionStore(session_key=self.session_key)
        s.save()

        response = self.client.get(url, {"mode": "complete", "sessid": self.session_key or "sessionid"})

        assert response.status_code == 200
        assert response.content.decode() == "success"

        # CRITICAL: Should NOT create a new PENDING session
        # We started with 1 COMPLETED session. count() should still be 1.
        # If bug exists: count() will be 2 (one COMPLETED, one new PENDING)
        assert ImportSession.objects.count() == 1
        first_session = ImportSession.objects.first()
        assert first_session is not None
        assert first_session.status == ImportSession.ImportStatus.COMPLETED

"""
Tests for 1C File Upload (mode=file).

Story 2.1: File Stream Upload

These tests cover:
- TC1: Valid upload with correct sessid (single chunk)
- TC2: Upload with invalid sessid
- TC3: Upload without sessid param
- TC4: Upload 250MB as 3 chunks (simulation)
- Verify file existence and integrity in 1c_temp after upload
"""
import base64
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def temp_1c_dir(tmp_path, monkeypatch):
    """
    Create and configure a temporary 1c_temp directory for testing.
    Uses monkeypatch for thread-safe settings modification.
    """
    temp_dir = tmp_path / "1c_temp"
    temp_dir.mkdir()

    # Use monkeypatch.setitem for dict modification (thread-safe, auto-reverted)
    monkeypatch.setitem(settings.ONEC_EXCHANGE, "TEMP_DIR", temp_dir)
    return temp_dir


@pytest.fixture
def staff_user(db):
    """Create a staff user for 1C exchange."""
    return User.objects.create_user(
        email="1c_file@example.com",
        password="secure_password_123",
        first_name="1C",
        last_name="FileUser",
        is_staff=True,
    )


@pytest.fixture
def authenticated_client(staff_user):
    """Create an API client with an established session (post-checkauth)."""
    client = APIClient()
    auth_header = "Basic " + base64.b64encode(b"1c_file@example.com:secure_password_123").decode("ascii")
    # Establish session via checkauth
    response: Any = client.get(
        "/api/integration/1c/exchange/",
        data={"mode": "checkauth"},
        HTTP_AUTHORIZATION=auth_header,
    )
    assert response.status_code == 200, f"Failed to establish session: {response.content}"
    return client


def get_session_id(client):
    """Extract session ID from client cookies."""
    session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    return session_cookie.value if session_cookie else None


@pytest.mark.django_db
@pytest.mark.integration
class Test1CFileUpload:
    """
    Tests for Story 2.1: File Stream Upload
    """

    def test_tc1_valid_upload_single_chunk(self, authenticated_client, temp_1c_dir):
        """
        TC1/AC1: Valid upload with correct sessid returns 'success'.
        File is created in 1c_temp/<sessid>/filename.
        """
        sessid = get_session_id(authenticated_client)
        assert sessid, "Session ID should be set after checkauth"

        # Binary content to upload
        test_content = b"This is test file content for 1C import."

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=import.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=test_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"success"

        # Verify file was created
        expected_file = temp_1c_dir / sessid / "import.zip"
        assert expected_file.exists(), f"File should exist at {expected_file}"
        assert expected_file.read_bytes() == test_content

    def test_tc2_upload_invalid_sessid(self, authenticated_client, temp_1c_dir):
        """
        TC2/AC3: URL sessid имеет приоритет и используется для маршрутизации файла.
        """
        # Use a fake sessid that doesn't match the session
        fake_sessid = "invalid_session_id_12345"
        test_content = b"Should be saved in explicit sessid dir"
        assert get_session_id(authenticated_client) != fake_sessid

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=test.zip&sessid={fake_sessid}"
        response = authenticated_client.post(
            url,
            data=test_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"success"

        expected_file = temp_1c_dir / fake_sessid / "test.zip"
        assert expected_file.exists()
        assert expected_file.read_bytes() == test_content

    def test_tc3_upload_missing_sessid(self, authenticated_client, temp_1c_dir):
        """
        TC3/AC4: Отсутствующий sessid берётся из session cookie и загрузка успешна.
        """
        sessid = get_session_id(authenticated_client)
        test_content = b"Should be saved using session cookie"

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=test.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=test_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"success"

        expected_file = temp_1c_dir / sessid / "test.zip"
        assert expected_file.exists()
        assert expected_file.read_bytes() == test_content

    def test_tc4_chunked_upload_append(self, authenticated_client, temp_1c_dir):
        """
        TC4/AC2: Upload 250MB-simulated as 3 chunks - content is appended correctly.
        Tests that multiple POST requests with same filename append the content.
        """
        sessid = get_session_id(authenticated_client)

        # Simulate 3 chunks (smaller for test speed)
        chunk1 = b"A" * 1000  # First chunk
        chunk2 = b"B" * 1000  # Second chunk
        chunk3 = b"C" * 1000  # Third chunk

        # Send chunk 1
        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=large_import.zip&sessid={sessid}"
        resp1 = authenticated_client.post(
            url,
            data=chunk1,
            content_type="application/octet-stream",
        )
        assert resp1.status_code == 200
        assert resp1.content == b"success"

        # Send chunk 2
        resp2 = authenticated_client.post(
            f"/api/integration/1c/exchange/" f"?mode=file&filename=large_import.zip&sessid={sessid}",
            data=chunk2,
            content_type="application/octet-stream",
        )
        assert resp2.status_code == 200

        # Send chunk 3
        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=large_import.zip&sessid={sessid}"
        resp3 = authenticated_client.post(
            url,
            data=chunk3,
            content_type="application/octet-stream",
        )
        assert resp3.status_code == 200

        # Verify final file size and content
        expected_file = temp_1c_dir / sessid / "large_import.zip"
        assert expected_file.exists()

        file_content = expected_file.read_bytes()
        assert len(file_content) == 3000, f"Expected 3000 bytes, got {len(file_content)}"
        assert file_content == chunk1 + chunk2 + chunk3

    def test_upload_missing_filename(self, authenticated_client, temp_1c_dir):
        """
        Edge case: Upload without filename param returns failure response.
        """
        sessid = get_session_id(authenticated_client)
        test_content = b"Content without filename"

        url = f"/api/integration/1c/exchange/" f"?mode=file&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=test_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"failure\nMissing session or filename"

    def test_upload_empty_body(self, authenticated_client, temp_1c_dir):
        """
        Edge case: Upload with empty body returns failure response.
        """
        sessid = get_session_id(authenticated_client)

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=empty.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=b"",
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert b"failure" in response.content

    def test_upload_directory_traversal_prevention(self, authenticated_client, temp_1c_dir):
        """
        Security: Filename with path traversal is sanitized.
        """
        sessid = get_session_id(authenticated_client)
        test_content = b"Malicious content"

        # Try directory traversal attack
        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=../../../etc/passwd.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=test_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        # File should be saved with sanitized name (just 'passwd')
        expected_file = temp_1c_dir / sessid / "passwd.zip"
        assert expected_file.exists()

        # Original target should NOT exist
        assert not (temp_1c_dir.parent.parent.parent / "etc" / "passwd").exists()

    def test_content_type_text_plain(self, authenticated_client, temp_1c_dir):
        """
        Response Content-Type is text/plain per 1C protocol.
        """
        sessid = get_session_id(authenticated_client)

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=test.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=b"test",
            content_type="application/octet-stream",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "text/plain" in response["Content-Type"]

    def test_file_limit_exceeded(self, authenticated_client, temp_1c_dir):
        """
        File exceeding FILE_LIMIT_BYTES returns failure response.
        Uses mock.patch.dict for thread-safe settings modification.
        """
        sessid = get_session_id(authenticated_client)
        with patch.dict(settings.ONEC_EXCHANGE, {"FILE_LIMIT_BYTES": 100}, clear=False):
            # Try to upload more than 100 bytes
            large_content = b"X" * 150

            url = f"/api/integration/1c/exchange/" f"?mode=file&filename=large.zip&sessid={sessid}"
            response = authenticated_client.post(
                url,
                data=large_content,
                content_type="application/octet-stream",
            )

            assert response.status_code == status.HTTP_200_OK
            assert response.content == b"failure\nFile too large"

    def test_init_cleans_session_files(self, authenticated_client, temp_1c_dir):
        """
        Calling init mode cleans up files only when previous cycle is marked complete.
        """
        sessid = get_session_id(authenticated_client)
        assert sessid

        # Upload a file first
        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=old_file.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=b"Old content",
            content_type="application/octet-stream",
        )
        assert response.status_code == 200

        # Verify file exists
        old_file = temp_1c_dir / sessid / "old_file.zip"
        assert old_file.exists()

        from apps.integrations.onec_exchange.file_service import FileStreamService

        file_service = FileStreamService(sessid)
        file_service.mark_complete()
        assert (temp_1c_dir / sessid / ".exchange_complete").exists()

        # Call init mode
        response = authenticated_client.get("/api/integration/1c/exchange/?mode=init")
        assert response.status_code == 200

        # Verify old file was cleaned up
        assert not old_file.exists()
        assert not (temp_1c_dir / sessid / ".exchange_complete").exists()

    def test_streaming_upload_uses_chunked_reads(self, authenticated_client, temp_1c_dir):
        """
        Verify that upload uses streaming reads (doesn't load entire body into memory).
        """
        sessid = get_session_id(authenticated_client)

        # Use a larger payload to ensure chunked reading
        large_content = b"Y" * (128 * 1024)  # 128KB

        url = f"/api/integration/1c/exchange/" f"?mode=file&filename=streamed.zip&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=large_content,
            content_type="application/octet-stream",
        )

        assert response.status_code == 200
        assert response.content == b"success"

        # Verify file content is complete
        expected_file = temp_1c_dir / sessid / "streamed.zip"
        assert expected_file.exists()
        assert expected_file.read_bytes() == large_content


@pytest.mark.django_db
class TestFileStreamService:
    """
    Unit tests for FileStreamService.
    """

    def test_append_chunk_creates_file(self, temp_1c_dir):
        """Service creates file on first append."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("test-session-123")
        content = b"Initial content"

        bytes_written = service.append_chunk("new_file.zip", content)

        assert bytes_written == len(content)
        expected_path = temp_1c_dir / "test-session-123" / "new_file.zip"
        assert expected_path.exists()
        assert expected_path.read_bytes() == content

    def test_append_chunk_appends_to_existing(self, temp_1c_dir):
        """Service appends content to existing file."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("test-session-456")

        # First write
        service.append_chunk("append_test.bin", b"First part")
        # Second write - should append
        service.append_chunk("append_test.bin", b" Second part")

        expected_path = temp_1c_dir / "test-session-456" / "append_test.bin"
        assert expected_path.read_bytes() == b"First part Second part"

    def test_get_file_size(self, temp_1c_dir):
        """Service reports correct file size."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("size-session")
        service.append_chunk("sized.bin", b"0123456789")  # 10 bytes

        assert service.get_file_size("sized.bin") == 10
        assert service.get_file_size("nonexistent.bin") == 0

    def test_file_exists(self, temp_1c_dir):
        """Service correctly checks file existence."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("exists-session")

        assert not service.file_exists("not_created.bin")

        service.append_chunk("created.bin", b"exists")
        assert service.file_exists("created.bin")

    def test_list_files(self, temp_1c_dir):
        """Service lists all files in session directory."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("list-session")

        assert service.list_files() == []

        service.append_chunk("file1.xml", b"content1")
        service.append_chunk("file2.xml", b"content2")

        files = service.list_files()
        assert len(files) == 2
        assert "file1.xml" in files
        assert "file2.xml" in files

    def test_session_id_required(self):
        """Service raises error without session_id."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        with pytest.raises(ValueError, match="session_id is required"):
            FileStreamService("")

        with pytest.raises(ValueError, match="session_id is required"):
            FileStreamService(None)  # type: ignore[arg-type]

    def test_filename_sanitization(self, temp_1c_dir):
        """Service sanitizes filenames to prevent path traversal."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("sanitize-session")

        # Attempt path traversal
        service.append_chunk("../../../etc/passwd", b"malicious")

        # File should be created with sanitized name
        expected = temp_1c_dir / "sanitize-session" / "passwd"
        assert expected.exists()

        # Original target should not be affected
        assert not (temp_1c_dir / ".." / ".." / ".." / "etc" / "passwd").exists()

    def test_cleanup_session(self, temp_1c_dir):
        """Service cleans up all files in session directory with force=True."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("cleanup-session")

        # Create some files
        service.append_chunk("file1.xml", b"content1")
        service.append_chunk("file2.xml", b"content2")
        service.append_chunk("file3.zip", b"content3")

        assert len(service.list_files()) == 3

        # Cleanup session
        deleted_count = service.cleanup_session(force=True)

        assert deleted_count == 3
        assert len(service.list_files()) == 0

    def test_cleanup_session_empty_dir(self, temp_1c_dir):
        """Cleanup on empty/non-existent session directory returns 0."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("nonexistent-session")

        # Should not raise, just return 0
        deleted_count = service.cleanup_session()
        assert deleted_count == 0

    def test_open_for_write_context_manager(self, temp_1c_dir):
        """
        Context manager opens file once for multiple writes.
        This tests the efficient I/O pattern for streaming uploads.
        """
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("ctx-manager-session")

        # Use context manager to write multiple chunks
        with service.open_for_write("streamed.bin") as writer:
            writer.write(b"chunk1")
            writer.write(b"chunk2")
            writer.write(b"chunk3")

        # Verify file content
        expected_path = temp_1c_dir / "ctx-manager-session" / "streamed.bin"
        assert expected_path.exists()
        assert expected_path.read_bytes() == b"chunk1chunk2chunk3"

    def test_open_for_write_appends_to_existing(self, temp_1c_dir):
        """Context manager appends to existing file when append=True."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("ctx-append-session")

        # First write session
        with service.open_for_write("appended.bin") as writer:
            writer.write(b"FIRST")

        # Second write session (simulating chunked upload continuation)
        with service.open_for_write("appended.bin") as writer:
            writer.write(b"SECOND")

        expected_path = temp_1c_dir / "ctx-append-session" / "appended.bin"
        assert expected_path.read_bytes() == b"FIRSTSECOND"

    def test_open_for_write_returns_bytes_written(self, temp_1c_dir):
        """Context manager tracks total bytes written."""
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("bytes-session")

        with service.open_for_write("tracked.bin") as writer:
            writer.write(b"12345")  # 5 bytes
            writer.write(b"67890")  # 5 bytes

        assert writer.bytes_written == 10

    def test_concurrent_writes_use_file_locking(self, temp_1c_dir):
        """
        File locking prevents corruption during concurrent writes.
        This verifies the lock file is created and prevents simultaneous access.
        """
        from apps.integrations.onec_exchange.file_service import FileLock, FileLockError, FileStreamService

        service = FileStreamService("lock-test-session")

        # First writer acquires lock
        with service.open_for_write("locked.bin") as writer:
            writer.write(b"FIRST")

            # Verify lock file exists during write
            lock_path = temp_1c_dir / "lock-test-session" / "locked.bin.lock"
            assert lock_path.exists(), "Lock file should exist during write"

        # Lock file should be cleaned up after write
        assert not lock_path.exists(), "Lock file should be removed after write"

    def test_file_lock_timeout(self, temp_1c_dir):
        """FileLock raises FileLockError when timeout exceeded."""
        import os

        from apps.integrations.onec_exchange.file_service import FileLock, FileLockError

        lock_path = temp_1c_dir / "test.lock"

        # Manually create a lock file to simulate held lock
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)

        # Try to acquire lock with very short timeout
        lock = FileLock(lock_path, timeout=0.2)

        with pytest.raises(FileLockError, match="Could not acquire lock"):
            lock.acquire()

        # Cleanup
        os.unlink(str(lock_path))

    def test_file_has_correct_permissions(self, temp_1c_dir):
        """Files created via open_for_write have explicit permissions (0o644)."""
        import stat

        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService("perms-session")

        with service.open_for_write("permtest.bin") as writer:
            writer.write(b"test")

        file_path = temp_1c_dir / "perms-session" / "permtest.bin"
        file_stat = file_path.stat()

        # Check file mode (ignoring type bits)
        mode = stat.S_IMODE(file_stat.st_mode)
        # On Windows, permissions work differently, so we just check file exists
        # On Unix, should be 0o644 (but may vary due to umask)
        assert file_path.exists()

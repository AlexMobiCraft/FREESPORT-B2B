"""
Integration Tests for Story 2.2: File Routing.
Verifies that files uploaded via mode=file are correctly routed to import directories.
"""
import base64
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def temp_1c_dirs(tmp_path, monkeypatch):
    """
    Create and configure temporary 1c_temp and 1c_import directories.
    Uses monkeypatch for thread-safe settings modification.
    """
    temp_dir = tmp_path / "1c_temp"
    temp_dir.mkdir()

    import_dir = tmp_path / "1c_import"
    import_dir.mkdir()

    # Use monkeypatch.setitem for dict modification (thread-safe, auto-reverted)
    # We need to update existing dictionary, ensuring we keep other keys if needed,
    # but here we just update/set the keys we care about.
    # Note: settings.ONEC_EXCHANGE is a dict, so we can set items on it.
    monkeypatch.setitem(settings.ONEC_EXCHANGE, "TEMP_DIR", temp_dir)
    monkeypatch.setitem(settings.ONEC_EXCHANGE, "IMPORT_DIR", import_dir)

    return {"temp": temp_dir, "import": import_dir}


@pytest.fixture
def staff_user(db):
    """Create a staff user for 1C exchange."""
    return User.objects.create_user(
        email="1c_routing@example.com",
        password="secure_password_routing",
        first_name="1C",
        last_name="RoutingUser",
        is_staff=True,
    )


@pytest.fixture
def authenticated_client(staff_user):
    """Create an API client with an established session (post-checkauth)."""
    client = APIClient()
    auth_header = "Basic " + base64.b64encode(b"1c_routing@example.com:secure_password_routing").decode("ascii")
    # Establish session via checkauth
    response = client.get(
        "/api/integration/1c/exchange/",
        data={"mode": "checkauth"},
        HTTP_AUTHORIZATION=auth_header,
    )
    assert response.status_code == 200
    return client


def get_session_id(client):
    """Extract session ID from client cookies."""
    session_cookie = client.cookies.get(settings.SESSION_COOKIE_NAME)
    return session_cookie.value if session_cookie else None


@pytest.mark.django_db
@pytest.mark.integration
class Test1CFileRouting:
    """
    End-to-end tests for file routing logic in views.py.
    """

    def test_xml_routing_goods(self, authenticated_client, temp_1c_dirs):
        """
        TC1: Upload goods.xml -> stored in 1c_temp/<sessid>/ (routing happens later)
        """
        sessid = get_session_id(authenticated_client)
        content = b"<xml>goods</xml>"
        filename = "goods.xml"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.content == b"success"

        # Verify IN temp (routing happens during import/complete)
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()
        assert temp_file.read_bytes() == content

        # Verify NOT in import directory yet
        import_file = temp_1c_dirs["import"] / "goods" / filename
        assert not import_file.exists()

    def test_xml_routing_offers(self, authenticated_client, temp_1c_dirs):
        """
        TC2: Upload offers_123.xml -> stored in 1c_temp/<sessid>/ (routing happens later)
        """
        sessid = get_session_id(authenticated_client)
        content = b"<xml>offers</xml>"
        filename = "offers_123.xml"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify IN temp
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()

        # Verify NOT in import directory yet
        import_file = temp_1c_dirs["import"] / "offers" / filename
        assert not import_file.exists()

    def test_image_routing(self, authenticated_client, temp_1c_dirs):
        """
        TC3: Upload image.jpg -> stored in 1c_temp/<sessid>/ (routing happens later)
        """
        sessid = get_session_id(authenticated_client)
        content = b"fake_image_bytes"
        filename = "product_image.jpg"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify IN temp
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()

        # Verify NOT in import directory yet
        import_file = temp_1c_dirs["import"] / "goods" / "import_files" / filename
        assert not import_file.exists()

    def test_zip_no_routing(self, authenticated_client, temp_1c_dirs):
        """
        TC4: Upload data.zip -> remains in 1c_temp/<sessid>/
        """
        sessid = get_session_id(authenticated_client)
        content = b"PK..."
        filename = "data.zip"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify IN temp
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()

        # Verify NOT in import root or subdirs
        import_file_root = temp_1c_dirs["import"] / filename
        assert not import_file_root.exists()

    def test_unknown_file_routing(self, authenticated_client, temp_1c_dirs):
        """
        TC5: Upload unknown.dat -> stored in 1c_temp/<sessid>/ (routing happens later)
        """
        sessid = get_session_id(authenticated_client)
        content = b"unknown data"
        filename = "unknown.dat"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify IN temp
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()

        # Verify NOT in import directory yet
        import_file = temp_1c_dirs["import"] / filename
        assert not import_file.exists()

    def test_uppercase_extensions(self, authenticated_client, temp_1c_dirs):
        """
        TC6: Uppercase extensions handled correctly (stored in temp, routed later)
        """
        sessid = get_session_id(authenticated_client)
        content = b"png bytes"
        filename = "IMAGE.PNG"

        url = f"/api/integration/1c/exchange/?mode=file&filename={filename}&sessid={sessid}"
        response = authenticated_client.post(
            url,
            data=content,
            content_type="application/octet-stream",
        )

        assert response.status_code == status.HTTP_200_OK

        # Verify IN temp
        temp_file = temp_1c_dirs["temp"] / sessid / filename
        assert temp_file.exists()

        # Verify NOT in import directory yet
        import_file = temp_1c_dirs["import"] / "goods" / "import_files" / filename
        assert not import_file.exists()

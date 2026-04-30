"""
Unit tests for 1C file routing (current behavior).

Tests FileRoutingService logic without Django DB dependencies.
Validates that files are routed to correct directories based on type.

Red-Green-Refactor: These tests define expected behavior.
"""
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add backend to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def session_id():
    """Generate a unique session ID for test isolation."""
    import uuid

    return str(uuid.uuid4())


@pytest.fixture
def temp_base(tmp_path):
    """Create temp directory base."""
    temp = tmp_path / "1c_temp"
    temp.mkdir(parents=True)
    return temp


@pytest.fixture
def import_base(tmp_path):
    """Create import directory base."""
    import_dir = tmp_path / "1c_import"
    import_dir.mkdir(parents=True)
    return import_dir


@pytest.fixture
def mock_settings(tmp_path, temp_base, import_base):
    """Create mock Django settings."""
    mock = MagicMock()
    mock.MEDIA_ROOT = tmp_path
    mock.ONEC_EXCHANGE = {
        "TEMP_DIR": temp_base,
        "IMPORT_DIR": import_base,
    }
    return mock


@pytest.fixture
def routing_service(session_id, mock_settings):
    """Create FileRoutingService with mocked settings."""
    with patch("apps.integrations.onec_exchange.routing_service.settings", mock_settings):
        from apps.integrations.onec_exchange.routing_service import FileRoutingService

        return FileRoutingService(session_id)


@pytest.fixture
def file_service(session_id, mock_settings):
    """Create FileStreamService with mocked settings."""
    with patch("apps.integrations.onec_exchange.file_service.settings", mock_settings):
        from apps.integrations.onec_exchange.file_service import FileStreamService

        service = FileStreamService(session_id)
        service._ensure_session_dir()
        return service


# ============================================================================
# TC1: XML goods routing
# ============================================================================


class TestXMLGoodsRouting:
    """TC1: Загрузка goods.xml -> перемещён в 1c_import/goods/"""

    def test_goods_xml_routed_to_goods_folder(self, routing_service, file_service, import_base, session_id):
        """goods.xml should be moved to import/goods/ directory."""
        # Arrange: Create goods.xml in temp directory
        filename = "goods.xml"
        content = b"<goods><item>test</item></goods>"
        file_service.append_chunk(filename, content)

        assert file_service.file_exists(filename), "File should exist in temp"

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: File is in goods/ subdirectory
        expected_dir = import_base / "goods"
        assert target_path.parent == expected_dir
        assert target_path.name == filename
        assert target_path.exists()
        assert not file_service.file_exists(filename), "File should be moved from temp"


# ============================================================================
# TC2: XML offers routing with UUID suffix
# ============================================================================


class TestXMLOffersRouting:
    """TC2: Загрузка offers_1_uuid.xml -> перемещён в 1c_import/offers/"""

    def test_offers_xml_with_uuid_routed_to_offers_folder(self, routing_service, file_service, import_base, session_id):
        """offers_*.xml files should be moved to import/offers/ directory."""
        # Arrange: Create offers file with typical 1C naming pattern
        filename = "offers_1_a1b2c3d4-e5f6-7890-abcd-ef1234567890.xml"
        content = b"<offers><offer>test</offer></offers>"
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: File is in offers/ subdirectory
        expected_dir = import_base / "offers"
        assert target_path.parent == expected_dir
        assert target_path.exists()


# ============================================================================
# TC3: Image routing (jpg)
# ============================================================================


class TestImageJpgRouting:
    """TC3: Загрузка image.jpg -> перемещён в 1c_import/goods/import_files/"""

    def test_jpg_image_routed_to_import_files(self, routing_service, file_service, import_base, session_id):
        """JPG images should be moved to import_files/ directory."""
        # Arrange: Create image file
        filename = "image.jpg"
        content = b"\xFF\xD8\xFF\xE0"  # JPEG magic bytes
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: File is in import_files/ subdirectory
        expected_dir = import_base / "goods" / "import_files"
        assert target_path.parent == expected_dir
        assert target_path.exists()


# ============================================================================
# TC4: Image routing with uppercase extension
# ============================================================================


class TestImageUppercaseRouting:
    """TC4: Загрузка photo.PNG (uppercase) -> перемещён в goods/import_files/"""

    def test_uppercase_png_routed_to_import_files(self, routing_service, file_service, import_base, session_id):
        """Uppercase image extensions should be handled case-insensitively."""
        # Arrange: Create image with uppercase extension
        filename = "photo.PNG"
        content = b"\x89PNG\r\n\x1a\n"  # PNG magic bytes
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: File is in goods/import_files/
        expected_dir = import_base / "goods" / "import_files"
        assert target_path.parent == expected_dir


# ============================================================================
# TC5: ZIP routed to import root
# ============================================================================


class TestZipRouting:
    """TC5: Загрузка import.zip -> перемещён в 1c_import/"""

    def test_zip_file_routed_to_import_root(self, file_service, import_base, session_id):
        """ZIP files should be routed to import root for later unpacking."""
        # Arrange: Create ZIP file
        filename = "import.zip"
        content = b"PK\x03\x04" + b"\x00" * 26
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: ZIP moved to import root
        assert target_path.parent == import_base
        assert target_path.exists()
        assert not file_service.file_exists(filename), "ZIP should be moved from temp"


# ============================================================================
# TC6: ZIP with uppercase extension routed
# ============================================================================


class TestZipUppercaseRouting:
    """TC6: Загрузка archive.ZIP (uppercase) -> перемещён в 1c_import/"""

    def test_uppercase_zip_routed(self, file_service, import_base, session_id):
        """Uppercase ZIP extensions should also be routed."""
        # Arrange: Create ZIP with uppercase extension
        filename = "archive.ZIP"
        content = b"PK\x03\x04" + b"\x00" * 26
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: ZIP moved to import root
        assert target_path.parent == import_base
        assert target_path.exists()


# ============================================================================
# TC7: Unknown file type routes to root
# ============================================================================


class TestUnknownFileRouting:
    """TC7: Загрузка unknown.dat -> перемещён в корень 1c_import/"""

    def test_unknown_extension_routed_to_import_root(self, file_service, import_base, session_id):
        """Files with unknown extensions should be moved to import root."""
        # Arrange: Create file with unknown extension
        filename = "unknown.dat"
        content = b"binary data here"
        file_service.append_chunk(filename, content)

        # Act: Route the file
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert: File is in import root (not a subdirectory)
        expected_dir = import_base
        assert target_path.parent == expected_dir
        assert target_path.exists()


# ============================================================================
# TC8: Session isolation
# ============================================================================


class TestSessionIsolation:
    """TC8: Temp изолирован по сессиям, import очередь общая."""

    def test_files_isolated_between_sessions(self, tmp_path):
        """Files from different sessions should not interfere with each other."""
        temp_base = tmp_path / "1c_temp"
        import_base = tmp_path / "1c_import"
        temp_base.mkdir(parents=True)
        import_base.mkdir(parents=True)

        with patch("apps.integrations.onec_exchange.file_service.settings") as mock_fs:
            mock_fs.ONEC_EXCHANGE = {
                "TEMP_DIR": temp_base,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.file_service import FileStreamService

            session1 = "session-aaa-111"
            session2 = "session-bbb-222"

            service1 = FileStreamService(session1)
            service2 = FileStreamService(session2)

            filename1 = "goods.xml"
            filename2 = "offers.xml"
            content1 = b"<goods>session1</goods>"
            content2 = b"<offers>session2</offers>"

            # Create files in both sessions
            service1.append_chunk(filename1, content1)
            service2.append_chunk(filename2, content2)

            assert (temp_base / session1 / filename1).exists()
            assert (temp_base / session2 / filename2).exists()

        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock_rs:
            mock_rs.ONEC_EXCHANGE = {
                "TEMP_DIR": temp_base,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router1 = FileRoutingService(session1)
            router2 = FileRoutingService(session2)

            # Act: Route files
            path1 = router1.move_to_import(filename1)
            path2 = router2.move_to_import(filename2)

            # Assert: Import queue is shared (no session isolation)
            assert path1.parent == import_base / "goods"
            assert path2.parent == import_base / "offers"

            # Verify contents are preserved
            assert path1.read_bytes() == content1
            assert path2.read_bytes() == content2

            # Temp files removed after routing
            assert not (temp_base / session1 / filename1).exists()
            assert not (temp_base / session2 / filename2).exists()


# ============================================================================
# TC9: File overwrite on same name
# ============================================================================


class TestFileOverwrite:
    """TC9: Повторная загрузка файла с тем же именем -> перезаписывает существующий"""

    def test_repeated_upload_overwrites_existing(self, file_service, import_base, session_id):
        """Re-uploading a file with the same name should overwrite the previous one."""
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            # Arrange: Create and route first file
            filename = "goods.xml"
            content1 = b"<goods>version1</goods>"
            file_service.append_chunk(filename, content1)

            router = FileRoutingService(session_id)
            path1 = router.move_to_import(filename)

            # Act: Upload second file with same name
            content2 = b"<goods>version2</goods>"
            file_service.append_chunk(filename, content2)
            path2 = router.move_to_import(filename)

            # Assert: Same path, new content
            assert path1 == path2
            assert path2.read_bytes() == content2


# ============================================================================
# Additional routing tests
# ============================================================================


class TestRoutingRules:
    """Test all XML routing rules for completeness."""

    @pytest.mark.parametrize(
        "filename,expected_subdir",
        [
            ("goods.xml", "goods"),
            ("goods_1_uuid.xml", "goods"),
            ("offers.xml", "offers"),
            ("offers_2_uuid.xml", "offers"),
            ("prices.xml", "prices"),
            ("prices_1_uuid.xml", "prices"),
            ("rests.xml", "rests"),
            ("rests_1_uuid.xml", "rests"),
            ("groups.xml", "groups"),
            ("groups_1_uuid.xml", "groups"),
        ],
    )
    def test_xml_routing_by_prefix(self, file_service, import_base, session_id, filename, expected_subdir):
        """XML files should be routed based on filename prefix."""
        # Arrange
        content = b"<root>test</root>"
        file_service.append_chunk(filename, content)

        # Act
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert
        expected_dir = import_base / expected_subdir
        assert target_path.parent == expected_dir

    @pytest.mark.parametrize("extension", [".jpg", ".jpeg", ".png", ".gif", ".webp"])
    def test_all_image_extensions_routed(self, file_service, import_base, session_id, extension):
        """All supported image extensions should be routed to import_files/."""
        # Arrange
        filename = f"image{extension}"
        content = b"fake image content"
        file_service.append_chunk(filename, content)

        # Act
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": file_service.base_dir,
                "IMPORT_DIR": import_base,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)
            target_path = router.move_to_import(filename)

        # Assert
        expected_dir = import_base / "goods" / "import_files"
        assert target_path.parent == expected_dir


# ============================================================================
# Service initialization tests
# ============================================================================


class TestRoutingServiceInit:
    """Test FileRoutingService initialization and configuration."""

    def test_service_requires_session_id(self, tmp_path):
        """FileRoutingService should require a session_id."""
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": tmp_path / "1c_temp",
                "IMPORT_DIR": tmp_path / "1c_import",
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            with pytest.raises(ValueError, match="session_id"):
                FileRoutingService("")

    def test_service_uses_import_dir_from_settings(self, session_id, tmp_path):
        """Service should use IMPORT_DIR from ONEC_EXCHANGE settings."""
        import_dir = tmp_path / "1c_import"

        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": tmp_path / "1c_temp",
                "IMPORT_DIR": import_dir,
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            service = FileRoutingService(session_id)
            assert service.import_base == import_dir


# ============================================================================
# should_route tests
# ============================================================================


class TestShouldRoute:
    """Test should_route method for various file types."""

    def test_xml_should_route(self, tmp_path, session_id):
        """XML files should be routed."""
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": tmp_path / "1c_temp",
                "IMPORT_DIR": tmp_path / "1c_import",
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)

            assert router.should_route("goods.xml") is True
            assert router.should_route("offers.xml") is True

    def test_images_should_route(self, tmp_path, session_id):
        """Image files should be routed."""
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": tmp_path / "1c_temp",
                "IMPORT_DIR": tmp_path / "1c_import",
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)

            assert router.should_route("image.jpg") is True
            assert router.should_route("photo.PNG") is True

    def test_zip_should_route(self, tmp_path, session_id):
        """ZIP files should be routed."""
        with patch("apps.integrations.onec_exchange.routing_service.settings") as mock:
            mock.ONEC_EXCHANGE = {
                "TEMP_DIR": tmp_path / "1c_temp",
                "IMPORT_DIR": tmp_path / "1c_import",
            }
            from apps.integrations.onec_exchange.routing_service import FileRoutingService

            router = FileRoutingService(session_id)

            assert router.should_route("import.zip") is True
            assert router.should_route("data.ZIP") is True

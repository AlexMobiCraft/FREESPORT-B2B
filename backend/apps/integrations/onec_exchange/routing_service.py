"""
File Routing Service for 1C Exchange.

Routes uploaded files to appropriate directories based on file type:
- XML files (goods, offers, prices, rests, groups) -> 1c_import/<sessid>/<type>/
- Images (jpg, jpeg, png, gif, webp) -> 1c_import/<sessid>/import_files/
- ZIP files -> NOT routed (stays in temp for later unpacking)
- Other files -> 1c_import/<sessid>/ (root)

Story 2.2: Сохранение файлов и маршрутизация
"""
import logging
import shutil
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

# Routing rules for XML files based on filename prefix
XML_ROUTING_RULES = {
    "goods": "goods/",
    "import": "goods/",  # Стандартное имя 1С для товаров/групп
    "offers": "offers/",
    "prices": "prices/",
    "rests": "rests/",
    "groups": "groups/",
    "priceLists": "priceLists/",
    "properties": "propertiesGoods/",  # Стандартное имя 1С для свойств
    "propertiesGoods": "propertiesGoods/",
    "propertiesOffers": "propertiesOffers/",
    "contragents": "contragents/",
    "storages": "storages/",
    "units": "units/",
    # orders.xml is handled inline by _handle_orders_xml (Story 5.2, ADR-001)
    # Listed here for documentation/consistency only
    "orders": "orders/",
}

# Supported image extensions (case-insensitive)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}

# ZIP extensions that should NOT be routed
ZIP_EXTENSIONS = {".zip"}


class FileRoutingService:
    """
    Service for routing uploaded files to appropriate import directories.

    Files are isolated per session to prevent collisions:
    MEDIA_ROOT/1c_import/<session_id>/<subdir>/<filename>

    Usage:
        router = FileRoutingService(session_id)
        if router.should_route(filename):
            target_path = router.move_to_import(filename)
    """

    def __init__(self, session_id: str):
        """
        Initialize service for a specific session.

        Args:
            session_id: Django session key for isolation

        Raises:
            ValueError: If session_id is empty
        """
        if not session_id:
            raise ValueError("session_id is required for FileRoutingService")

        self.session_id = session_id

        # Get directories from settings
        temp_dir = settings.ONEC_EXCHANGE.get("TEMP_DIR", Path(settings.MEDIA_ROOT) / "1c_temp")
        self.temp_base = Path(str(temp_dir))

        import_dir = settings.ONEC_EXCHANGE.get("IMPORT_DIR", Path(settings.MEDIA_ROOT) / "1c_import")
        self.import_base = Path(str(import_dir))

        self.temp_dir = self.temp_base / session_id
        # FIXED: Import directory should be shared/root, not session-isolated
        # Parser expects files in data/import_1c/goods, not data/import_1c/<sessid>/goods
        self.import_dir = self.import_base

    def _get_temp_file_path(self, filename: str) -> Path:
        """
        Get path to file in temp directory.

        Args:
            filename: Name of the file

        Returns:
            Full path to file in temp directory
        """
        safe_filename = Path(filename).name
        return self.temp_dir / safe_filename

    def _ensure_import_dir(self, subdir: str = "") -> Path:
        """
        Create import directory (with optional subdirectory) if it doesn't exist.

        Args:
            subdir: Optional subdirectory within session import folder

        Returns:
            Path to the directory
        """
        target_dir = self.import_dir
        if subdir:
            target_dir = target_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        return target_dir

    def route_file(self, filename: str) -> str:
        """
        Determine the target subdirectory for a file based on its name/extension.

        Args:
            filename: Name of the file

        Returns:
            Subdirectory name (e.g., 'goods/', 'import_files/').
            Returns empty string ('') to indicate the file should be placed in
            the root of the session import directory (1c_import/<sessid>/).
        """
        safe_filename = Path(filename).name
        suffix = Path(safe_filename).suffix.lower()
        name_lower = safe_filename.lower()

        # Check XML routing rules by prefix
        if suffix == ".xml":
            # Sort rules by length of prefix descending to match most specific first
            # e.g. 'propertiesOffers' (len 16) before 'properties' (len 10)
            sorted_rules = sorted(XML_ROUTING_RULES.items(), key=lambda x: len(x[0]), reverse=True)
            for prefix, subdir in sorted_rules:
                if name_lower.startswith(prefix):
                    return subdir.rstrip("/")
            # Unknown XML file -> root
            return ""

        # Check image extensions
        # Parser expects images in 'goods/import_files/' or 'offers/import_files/'
        # By default, we route to 'goods/import_files/' as it's the primary location
        if suffix in IMAGE_EXTENSIONS:
            return "goods/import_files"

        # Other unknown files -> root
        return ""

    def should_route(self, filename: str) -> bool:
        """
        Determine if a file should be routed (moved to import directory).

        Updated: We now route everything including ZIPs to allow accumulation
        in shared import directory.
        """
        return True

    def move_to_import(self, filename: str) -> Path:
        """
        Move a file from temp directory to appropriate import subdirectory.

        Args:
            filename: Name of the file in temp directory

        Returns:
            Path to the file in its new location

        Raises:
            FileNotFoundError: If source file doesn't exist
        """
        source_path = self._get_temp_file_path(filename)

        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")

        # Determine target subdirectory
        subdir = self.route_file(filename)
        target_dir = self._ensure_import_dir(subdir)

        # Target file path
        target_path = target_dir / Path(filename).name

        # Move file (overwrites if exists)
        shutil.move(str(source_path), str(target_path))

        logger.info(f"Routed file: {filename} -> {subdir or 'root'} " f"(session: {self.session_id[:8]}...)")

        return target_path

    def cleanup_import_dir(self, force: bool = False) -> int:
        """
        Cleans up the shared import directory.

        As the import directory is shared across sessions, 1C can create segmented 
        XML files that accumulate. This method ensures old segments are cleared before 
        a new exchange cycle begins.

        Args:
            force: If True, completely deletes all files and directories 
                   except `.dry_run` flag.

        Returns:
            Number of files/directories deleted
        """
        if not self.import_dir.exists():
            return 0

        deleted_count = 0
        for item in self.import_dir.iterdir():
            if item.name == ".dry_run":
                continue
            
            try:
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
                deleted_count += 1
            except OSError as e:
                logger.warning(f"Failed to delete {item.name} during import cleanup: {e}")

        logger.info(f"Cleaned up import directory: deleted {deleted_count} items")
        return deleted_count

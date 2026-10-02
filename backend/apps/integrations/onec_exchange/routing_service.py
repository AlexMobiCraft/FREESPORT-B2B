"""
File Routing Service for 1C Exchange.

Routes uploaded files to appropriate directories based on file type:
- XML files (goods, offers, prices, rests, groups) -> 1c_import/<sessid>/<type>/
- Images (jpg, jpeg, png, gif, webp) -> 1c_import/import_files/ (ОБЩИЙ каталог)
- ZIP files -> 1c_import/<sessid>/ (root, распаковываются позже)
- Other files -> 1c_import/<sessid>/ (root)

Каталог обмена изолирован по сессии: прогон, не получивший от 1С имён файлов
(`mode=complete`), собирал по маске свежие файлы соседей, читал их и удалял как
обработанные — сегмент, отстоявший очередь за локом каталога, обещанного файла
не находил и падал. Картинки — единственное исключение: их 1С присылает
отдельным обменом со своим `sessid`, связи «архив картинок ↔ XML-сессия» в
протоколе нет, поэтому они остаются общими.

Story 2.2: Сохранение файлов и маршрутизация
Стори `onec-exchange-dir-isolation`: изоляция каталога обмена по сессии
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

# Каталог картинок — единственное, что остаётся общим для всех сессий обмена.
# 1С присылает изображения отдельным обменом со своим `sessid` и связи
# «архив картинок ↔ XML-сессия» не передаёт: механизма для этого в протоколе
# нет. Изолируй картинки по сессии — и goods.xml перестанет их находить.
IMAGES_SUBDIR = "import_files"

# Раскладка картинок до изоляции каталога обмена. Остаётся источником на время
# переходного окна выката: goods.xml, приехавший сразу после выката, может
# ссылаться на картинку, доставленную до него (стори onec-exchange-dir-isolation).
LEGACY_IMAGES_SUBDIR = "goods/import_files"

# Имена в корне каталога обмена, которые каталогом сессии не являются и под
# автоматическую уборку не попадают: общие картинки, легаси-раскладка и
# подпапки типов, накопленные до изоляции.
SHARED_ROOT_NAMES = frozenset({IMAGES_SUBDIR, ".dry_run"}) | {
    subdir.rstrip("/").split("/")[0] for subdir in XML_ROUTING_RULES.values()
}

# То же множество для сверки `sessid`. Регистр снят: NTFS и APFS его не
# различают, и `Import_Files` увёл бы сессию ровно в общий каталог картинок.
_SHARED_ROOT_NAMES_FOLDED = frozenset(name.casefold() for name in SHARED_ROOT_NAMES)


def get_import_base() -> Path:
    """Общий корень каталога обмена (`ONEC_EXCHANGE["IMPORT_DIR"]`)."""
    return Path(str(settings.ONEC_EXCHANGE["IMPORT_DIR"]))


def get_temp_base() -> Path:
    """Общий корень временного каталога обмена (`ONEC_EXCHANGE["TEMP_DIR"]`)."""
    return Path(str(settings.ONEC_EXCHANGE["TEMP_DIR"]))


def is_session_import_dir(data_dir: str | Path) -> bool:
    """Лежит ли каталог прямо в корне обмена, то есть является ли он сессионным.

    Правило детерминированное и одно на весь импорт: сессионная раскладка — это
    `IMPORT_DIR/<sessid>`, ровно один сегмент вглубь. Всё остальное (ручной
    прогон по `ONEC_DATA_DIR`, тесты с `tmp_path`, сам общий корень) сохраняет
    прежнее поведение.
    """
    try:
        return Path(data_dir).resolve().parent == get_import_base().resolve()
    except (OSError, ValueError):  # pragma: no cover - защита от битого пути
        return False


def image_relative_name(name_in_archive: str) -> str:
    """Путь картинки относительно каталога `import_files`.

    1С кладёт в архив либо `import_files/<xx>/<file>.jpg`, либо голое имя.
    Подкаталог `<xx>` обязан сохраниться: goods.xml адресует картинку именно
    как `import_files/<xx>/<file>.jpg`, а `normalize_image_path` срезает только
    сам префикс `import_files/`.
    """
    normalized = name_in_archive.replace("\\", "/")
    prefix = f"{IMAGES_SUBDIR}/"
    if normalized.lower().startswith(prefix):
        return normalized[len(prefix) :]
    return normalized


def session_import_dir(session_id: str) -> Path:
    """Каталог обмена конкретной сессии: `IMPORT_DIR/<sessid>`."""
    return get_import_base() / validate_session_segment(session_id)


def images_dir_for(data_dir: str | Path) -> Path:
    """Каталог картинок для данного каталога обмена.

    Сессионная раскладка — общий `IMPORT_DIR/import_files`; всё прочее — прежний
    `<data_dir>/goods/import_files`.
    """
    if is_session_import_dir(data_dir):
        return get_import_base() / IMAGES_SUBDIR
    return Path(data_dir) / "goods" / IMAGES_SUBDIR


def legacy_images_dir_for(data_dir: str | Path) -> Path | None:
    """Легаси-каталог картинок, если он вообще применим к этому прогону."""
    if not is_session_import_dir(data_dir):
        return None
    return get_import_base() / LEGACY_IMAGES_SUBDIR


def dry_run_flag_for(data_dir: str | Path) -> Path:
    """Флаг `.dry_run` — режим всего обмена, а не отдельной сессии."""
    if is_session_import_dir(data_dir):
        return get_import_base() / ".dry_run"
    return Path(data_dir) / ".dry_run"


def validate_session_segment(session_id: str) -> str:
    """Проверить, что `sessid` — один безопасный сегмент пути.

    `sessid` приходит прямо из query-параметра 1С и нигде не санитизируется, а
    после изоляции он становится сегментом пути, по которому работает
    `shutil.rmtree`. Эндпоинт закрыт `Basic1CAuthentication` + `Is1CExchangeUser`,
    поэтому это укрепление, а не открытая дыра, — но рычаг удаления по внешнему
    пути без проверки существовать не должен.
    """
    if not session_id:
        raise ValueError("session_id is required for FileRoutingService")

    if session_id in {".", ".."} or "/" in session_id or "\\" in session_id:
        raise ValueError(f"session_id must be a single safe path segment, got: {session_id!r}")

    # Сегмент, совпавший с общим именем в корне обмена, превращает каталог
    # сессии в общий каталог: `sessid=import_files` даёт `IMPORT_DIR/import_files`,
    # и `cleanup_import_dir`/`remove_session_dirs` этой сессии сносят картинки
    # всех остальных, а `sessid=goods` — легаси-раскладку, на которую опирается
    # фолбэк переходного окна. Проверка идёт здесь, а не в уборке: каталог не
    # должен существовать вовсе.
    if session_id.casefold() in _SHARED_ROOT_NAMES_FOLDED:
        raise ValueError(f"session_id must not collide with a shared exchange directory, got: {session_id!r}")

    return session_id


class FileRoutingService:
    """
    Service for routing uploaded files to appropriate import directories.

    Files are isolated per session to prevent collisions:
    ONEC_EXCHANGE["IMPORT_DIR"]/<session_id>/<subdir>/<filename>

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
            ValueError: если session_id пуст, не является одним безопасным
                сегментом пути или совпадает с общим каталогом в корне обмена
                (см. `validate_session_segment`)
        """
        self.session_id = validate_session_segment(session_id)

        # Get directories from settings. Они уже заданы вне MEDIA_ROOT.
        self.temp_base = Path(str(settings.ONEC_EXCHANGE["TEMP_DIR"]))
        self.import_base = Path(str(settings.ONEC_EXCHANGE["IMPORT_DIR"]))

        self.temp_dir = self.temp_base / self.session_id
        # Каталог обмена — свой на каждую сессию. `session_key` уникален для
        # каждого файла (1С не держит cookie-сессию между запросами), поэтому
        # каталог на сессию = каталог на файл, и пересечься физически нельзя.
        # Общим остаётся только `import_files` (см. IMAGES_SUBDIR).
        self.import_dir = self.import_base / self.session_id

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

    def _route_root(self, subdir: str) -> Path:
        """Корень маршрута: картинки — в общий каталог, всё прочее — в сессионный.

        Единственное исключение из изоляции. Картинки 1С присылает отдельным
        обменом со своим `sessid`, и goods.xml другой сессии обязан их видеть.
        """
        return self.import_base if subdir == IMAGES_SUBDIR else self.import_dir

    def _ensure_import_dir(self, subdir: str = "") -> Path:
        """
        Create import directory (with optional subdirectory) if it doesn't exist.

        Args:
            subdir: Optional subdirectory within session import folder

        Returns:
            Path to the directory
        """
        target_dir = self._route_root(subdir)
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
                # Сравнение case-insensitive: 1С присылает 'priceLists_*.xml' (mixed case),
                # а name_lower уже lowercased — без .lower() на префиксе матчинг проваливается
                if name_lower.startswith(prefix.lower()):
                    return subdir.rstrip("/")
            # Unknown XML file -> root
            return ""

        # Картинки — в общий `import_files` (маршрут разворачивается в
        # `_route_root`: он единственный, кто уходит мимо каталога сессии).
        if suffix in IMAGE_EXTENSIONS:
            return IMAGES_SUBDIR

        # Other unknown files -> root
        return ""

    def should_route(self, filename: str) -> bool:
        """
        Determine if a file should be routed (moved to import directory).

        Маршрутизируется всё, включая ZIP: архивы копятся в каталоге обмена
        своей сессии и распаковываются позже.
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
        """Убрать каталог обмена СВОЕЙ сессии.

        Область уборки ограничена `IMPORT_DIR/<sessid>`: файлы соседних сессий
        уже обещаны их собственным задачам, и снос их по маске — это и есть
        дефект, ради которого вводилась изоляция. Общий `import_files` сюда не
        попадает — он лежит в корне обмена, а не в каталоге сессии.

        Побочное следствие изоляции: `session_key` уникален на файл, поэтому в
        `handle_init` этот вызов почти всегда попадает на свежий (пустой или
        несуществующий) каталог и становится практически no-op. Мусор чужих
        сессий подбирает периодическая `cleanup_stale_exchange_dirs`.

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

    def remove_session_dirs(self) -> int:
        """Удалить сами каталоги сессии в `1c_import` и `1c_temp` после обмена.

        Без этого каталоги копятся навсегда: на проде к 28.08.2026 накопилось
        32 276 папок. Каталог обмена сносится целиком (`rmtree`, а не `rmdir`):
        задача импорта на каждом прогоне создаёт в нём `goods`/`offers`/… ради
        валидации команды, поэтому пустым он не бывает.

        Временный каталог удаляется только когда в нём не осталось полезных
        файлов: 1С может дослать в ту же сессию ещё один файл, и снести его
        вместе с каталогом — потерять данные. Осиротевшее подберёт
        `cleanup_stale_exchange_dirs` по порогу 24 часа.
        """
        removed = 0

        if self.import_dir.exists():
            removed += self._rmtree_session_dir(self.import_dir)

        if self.temp_dir.exists():
            if self._temp_dir_has_payload():
                logger.info(f"Keeping temp session dir with pending files: {self.temp_dir}")
            else:
                removed += self._rmtree_session_dir(self.temp_dir)

        return removed

    @staticmethod
    def _rmtree_session_dir(directory: Path) -> int:
        try:
            shutil.rmtree(directory)
            return 1
        except OSError as e:
            logger.warning(f"Failed to remove session directory {directory}: {e}")
            return 0

    def _temp_dir_has_payload(self) -> bool:
        """Есть ли во временном каталоге сессии файлы, кроме служебных маркеров."""
        markers = {".exchange_complete", ".dry_run"}
        return any(item.is_file() and item.name not in markers for item in self.temp_dir.iterdir())

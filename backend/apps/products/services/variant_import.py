"""
Сервисы для импорта ProductVariant из 1С

Основной процессор импорта для новой архитектуры Product + ProductVariant:
- goods.xml → Product (базовая информация, base_images)
- offers.xml → ProductVariant (SKU, характеристики)
- prices.xml → ProductVariant (цены)
- rests.xml → ProductVariant (остатки)
"""

from __future__ import annotations

import logging
import os
import re
import uuid
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TypedDict

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.products.category_utils import REPAIR_ANCHOR_ONEC_ID

if TYPE_CHECKING:
    from apps.products.models import Product, ProductVariant

logger = logging.getLogger("import_products")

# Предохранитель массовой деактивации категорий.
# Если под одним раскрытым родителем гасится больше этой доли его активных детей,
# деактивация детей именно этого родителя отменяется (частичная выгрузка 1С).
MAX_CATEGORY_DEACTIVATION_RATIO = 0.3
# Порог не применяется к родителям с малым числом активных детей: штатное удаление
# 1 категории из 3 даёт 33 % и блокировалось бы навсегда, засоряя лог ошибками.
MIN_CHILDREN_FOR_DEACTIVATION_RATIO = 4


# ============================================================================
# TypedDict definitions for parsed data
# ============================================================================


class VariantOfferData(TypedDict, total=False):
    """Данные варианта из offers.xml"""

    id: str  # Составной ID: parent_id#variant_id
    parent_id: str  # ID родительского Product
    variant_id: str  # ID варианта
    name: str
    article: str  # SKU/Артикул
    color_name: str
    size_value: str
    images: list[str]  # Пути к изображениям варианта


class VariantPriceData(TypedDict):
    """Данные цен варианта из prices.xml"""

    id: str  # Составной ID: parent_id#variant_id
    prices: list[dict[str, Any]]  # [{price_type_id, value}, ...]


class VariantRestData(TypedDict):
    """Данные остатков варианта из rests.xml"""

    id: str  # Составной ID: parent_id#variant_id
    warehouse_id: str
    quantity: int


class CategoryData(TypedDict, total=False):
    """Данные категории из goods.xml"""

    id: str
    name: str
    description: str
    parent_id: str


class BrandData(TypedDict):
    """Данные бренда из propertiesGoods.xml"""

    id: str
    name: str


class PriceTypeData(TypedDict):
    """Данные типа цены из prices.xml"""

    onec_id: str
    onec_name: str
    product_field: str


# ============================================================================
# Helper functions
# ============================================================================


def parse_onec_id(onec_id: str) -> tuple[str, str]:
    """
    Парсинг составного onec_id из offers.xml

    Args:
        onec_id: Строка вида "parent-uuid#variant-uuid"

    Returns:
        Tuple (parent_id, variant_id)

    Raises:
        ValueError: Если формат ID некорректен

    Example:
        >>> parse_onec_id("12345678-abcd#87654321-dcba")
        ("12345678-abcd", "87654321-dcba")
    """
    if "#" not in onec_id:
        # Товар без вариантов - используем один ID для обоих
        return onec_id, onec_id

    parts = onec_id.split("#", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid onec_id format: {onec_id}")

    return parts[0], parts[1]


def parse_characteristics(characteristics: list[dict[str, str]]) -> dict[str, str]:
    """
    Парсинг характеристик товара из offers.xml

    Извлекает color_name и size_value из списка характеристик.
    Поддерживает различные названия полей из 1С.

    Args:
        characteristics: Список словарей {name, value}

    Returns:
        Dict с ключами 'color_name', 'size_value'
    """
    result = {"color_name": "", "size_value": ""}

    # Маппинг названий характеристик из 1С на наши поля
    color_names = {"цвет", "color", "окраска"}
    # Убран "детский размер" — это булевый флаг, не размер
    size_names = {"размер", "size", "размерtd"}

    # Невалидные значения для размера (булевые флаги)
    invalid_size_values = {"да", "нет", "yes", "no", "true", "false", "-"}

    for char in characteristics:
        name = char.get("name", "").lower().strip()
        value = char.get("value", "").strip()

        if not value or value == "-999 999 999,9" or value == "-999999999.9":
            continue

        if name in color_names:
            result["color_name"] = value
        elif name in size_names or name.startswith("размер_"):
            # Фильтруем невалидные булевые значения
            if value.lower() not in invalid_size_values:
                result["size_value"] = value

    return result


def extract_size_from_name(name: str) -> str:
    """
    Извлечение размера из названия товара

    Пример: "Кимоно для джиу джитсу (BJJ) BoyBo, BBJJ24, синий (А5 (2XL))"
    Результат: "А5 (2XL)"

    Args:
        name: Название товара

    Returns:
        Извлечённый размер или пустая строка
    """
    # Паттерн для размера в скобках в конце названия
    # Примеры: (42), (XL), (А5 (2XL)), (36-38)
    pattern = r"\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*$"
    match = re.search(pattern, name)
    if match:
        return match.group(1).strip()
    return ""


def extract_color_from_name(name: str) -> str:
    """
    Извлечение цвета из названия товара используя ColorMapping модель

    Пример: "Боксерки BoyBo TITAN,IB-26 (одобрены ФБР), синий"
    Результат: "синий"

    Args:
        name: Название товара

    Returns:
        Извлечённый цвет или пустая строка
    """
    from apps.products.models import ColorMapping

    # Получаем цвета из ColorMapping модели
    color_mappings = ColorMapping.objects.values_list("name", flat=True)

    name_lower = name.lower()
    for color in color_mappings:
        if color.lower() in name_lower:
            return color.capitalize()

    return ""


def normalize_image_path(image_path: str) -> str:
    """
    Нормализация пути к изображению.

    Убирает префикс 'import_files/' если присутствует, чтобы обеспечить
    единый стандарт путей между XML-импортом и импортом через админку.

    Args:
        image_path: Путь к изображению (относительный)

    Returns:
        Нормализованный путь без префикса 'import_files/'
    """
    if image_path.startswith("import_files/"):
        return image_path[len("import_files/") :]
    return image_path


# ============================================================================
# VariantImportProcessor - основной процессор импорта
# ============================================================================


class VariantImportProcessor:
    """
    Процессор для импорта ProductVariant из 1С

    Workflow импорта:
    1. goods.xml → Product (базовая информация, base_images)
    2. offers.xml → ProductVariant (SKU, характеристики)
    3. Default variants → ProductVariant для товаров без вариантов
    4. prices.xml → ProductVariant (цены)
    5. rests.xml → ProductVariant (остатки)
    """

    DEFAULT_PLACEHOLDER_IMAGE = "products/placeholder.png"
    BATCH_SIZE = 500  # NFR4: batch processing

    # AC7: сколько отброшенных размеров попадёт в текстовый report поимённо.
    # Дальше растёт только счётчик: аномальная выгрузка не должна устроить
    # лавину UPDATE по полю report.
    SIZE_VALUE_REPORT_LIMIT = 50

    def __init__(
        self,
        session_id: int,
        batch_size: int = 500,
        skip_validation: bool = False,
    ):
        """
        Инициализация процессора

        Args:
            session_id: ID сессии импорта
            batch_size: Размер batch для bulk операций (default 500)
            skip_validation: Пропустить валидацию данных
        """
        from apps.products.models import ProductVariant

        self.session_id = session_id
        self.batch_size = batch_size
        self.skip_validation = skip_validation

        # Запасные каталоги изображений, проверяемые ПОФАЙЛОВО, когда файла нет
        # в основном `base_dir`. Список задаёт вызывающая команда — она одна
        # знает раскладку каталога обмена. Пустой список = прежнее поведение.
        self.image_fallback_dirs: list[str] = []

        # Исходники картинок, которые этот прогон реально потребил: копия лежит
        # в хранилище, значит файл в каталоге обмена больше не нужен. Удаляет их
        # команда (`_cleanup_files`) — она одна знает, какой каталог её, а какой
        # принадлежит ручному корпусу `ONEC_DATA_DIR`, который трогать нельзя.
        # Превью ниже порога размера сюда НЕ попадают: копии в хранилище у них
        # не появляется никогда, и удалять их по этому признаку было бы нечестно.
        self.consumed_image_sources: set[str] = set()

        self.stats: dict[str, Any] = {
            "products_created": 0,
            "products_updated": 0,
            "variants_created": 0,
            "variants_updated": 0,
            "default_variants_created": 0,
            "prices_updated": 0,
            "stocks_updated": 0,
            "skipped": 0,
            "errors": 0,
            "warnings": 0,
            # AC7: сколько «размеров» не влезло в поле и было отброшено.
            # Инициализируем здесь, чтобы отличать «не сработало» от «код не задеплоен».
            "size_value_dropped": 0,
            "images_copied": 0,
            # CAP-5: содержимое сменилось при том же имени файла — копия перезаписана.
            "images_replaced": 0,
            # Сумма трёх исходов ниже. Оставлена ради совместимости: значение уже
            # лежит в `report_details` прошлых сессий и читается админкой.
            "images_skipped": 0,
            # Три исхода, которые раньше сливались в `images_skipped` и делали
            # отчёт нечитаемым (tech-debt п. 24: на проде 11 186 в одной куче).
            # Смысл у них разный вплоть до противоположного: «узнано по копии» —
            # это картинка РАЗРЕШЕНА, а не отброшена.
            "images_skipped_existing": 0,
            "images_skipped_small": 0,
            "images_resolved_from_copy": 0,
            "images_errors": 0,
            "attributes_linked": 0,
            "attributes_missing": 0,
            # Story 27.1: Keys for migrated methods
            "brand_fallbacks": 0,
            "category_fallbacks": 0,
            "attributes_missing_mapping": 0,
            # Сколько категорий предохранитель отказался гасить (0 = сработок не было).
            # Инициализируем здесь, чтобы отличать «не сработал» от «код не задеплоен».
            "categories_deactivation_skipped": 0,
        }

        # Story 13.2+ Debugging: Track specific updated items
        self.updated_products: list[str] = []
        self.updated_variants: list[str] = []

        # Кэш для оптимизации поиска
        self._product_cache: dict[str, Any] = {}
        self._variant_cache: dict[str, Any] = {}
        self._stock_buffer: dict[str, dict[str, Any]] = {}
        self._missing_products_logged: set[str] = set()
        # AC7: сколько отброшенных размеров уже названо в текстовом report
        self._size_value_reports: int = 0
        # AC7: onec_id, у которых размер уже отбракован — счётчик считает
        # варианты, а не встречи одного оффера в разных сегментах
        self._size_value_dropped_logged: set[str] = set()
        # AC7: лимит колонки неизменен в рамках процесса — снимаем один раз,
        # а не на каждый из ~16 тыс. офферов полного каталога
        self._size_value_max_length: int | None = ProductVariant._meta.get_field("size_value").max_length
        self._missing_variants_logged: set[str] = set()
        self._unmapped_price_types_logged: set[str] = set()
        # Маппинг parent_onec_id → vat_rate из goods.xml
        self._product_vat_rates: dict[str, Decimal] = {}

        # Фильтрация категорий (заполняется в process_categories)
        self._category_filtering_active: bool = False
        self._allowed_category_ids: set[str] = set()

        # Коллекция всех валидных категорий для деактивации устаревших
        self._valid_category_onec_ids: set[str] = set()

        # onec_id родителей, реально «раскрытых» в обработанных XML: под ними в выгрузке
        # перечислен хотя бы один прошедший allowed-фильтр ребёнок. Только дети этих
        # родителей попадают в зону деактивации. Множество накапливается между groups*.xml.
        self._expanded_parent_onec_ids: set[str] = set()

        # onec_id корневых категорий (без parent_id), встреченных в обработанных XML.
        # Копится между файлами: корень может прийти в одном groups*.xml, а его дети —
        # в другом, и guard «чужой корень не раскрыт» должен работать в обоих случаях.
        self._root_category_onec_ids: set[str] = set()

    # ========================================================================
    # Helper methods
    # ========================================================================

    # Минимальный размер изображения в байтах (100KB)
    MIN_IMAGE_SIZE_BYTES = 100 * 1024
    # Резервный минимум — используется когда нет изображений >= 100KB
    FALLBACK_MIN_IMAGE_SIZE_BYTES = 8 * 1024

    def _resolve_image_source(self, base_dir: str, normalized_path: str) -> Path:
        """Исходник картинки: основной каталог, иначе первый подходящий запасной.

        Проверка пофайловая, а не покаталожная. Переходное окно выката оставляет
        картинки одного товара в двух раскладках сразу, а ЧАСТИЧНОЕ разрешение
        состава обрезает фото товара (`_import_base_images(mirror_composition=True)`):
        выбор одного каталога на весь прогон терял бы половину картинок молча.

        Возврат по умолчанию — путь в основном каталоге: так сообщения об
        отсутствующем файле и опрос хранилища остаются прежними.
        """
        primary = Path(base_dir) / normalized_path
        if primary.exists() or not self.image_fallback_dirs:
            return primary

        for fallback_dir in self.image_fallback_dirs:
            candidate = Path(fallback_dir) / normalized_path
            if candidate.exists():
                return candidate

        return primary

    def _build_destination_path(self, image_path: str, destination_prefix: str) -> str:
        """
        Собирает путь копии изображения в хранилище.

        Args:
            image_path: НОРМАЛИЗОВАННЫЙ путь изображения (без префикса 'import_files/').
                Подкаталог берётся из первого сегмента пути, поэтому на сыром пути
                из XML он выродился бы в 'import_files' и целевые пути разъехались
                бы у всего каталога.
            destination_prefix: Префикс директории назначения ('base' или 'variants')

        Returns:
            Относительный путь копии в default_storage
        """
        filename = Path(image_path).name
        subdir = image_path.split("/")[0] if "/" in image_path else ""
        if subdir:
            return f"products/{destination_prefix}/{subdir}/{filename}"
        return f"products/{destination_prefix}/{filename}"

    def _stored_image_exists(self, destination_path: str) -> bool:
        """Проверяет наличие уже перенесённой копии изображения в хранилище."""
        from django.core.files.storage import default_storage

        try:
            return bool(default_storage.exists(destination_path))
        except OSError:
            return False

    def _get_stored_image_size(self, destination_path: str) -> int | None:
        """
        Размер уже перенесённой копии в хранилище.

        Returns:
            Размер в байтах или None, если хранилище его не отдаёт.
        """
        from django.core.files.storage import default_storage

        try:
            return default_storage.size(destination_path)
        except (OSError, NotImplementedError):
            return None

    def _get_effective_min_size(self, image_paths: list[str], base_dir: str, destination_prefix: str) -> int:
        """
        Определяет эффективный минимальный размер изображения.

        Если среди image_paths есть хотя бы одно изображение >= MIN_IMAGE_SIZE_BYTES,
        возвращает MIN_IMAGE_SIZE_BYTES. Иначе возвращает FALLBACK_MIN_IMAGE_SIZE_BYTES,
        чтобы не оставлять товар/вариант вообще без изображений.

        Размер берётся у фактически доступного файла: исходника из выгрузки либо,
        если 1С уже подчистила import_files, у перенесённой копии в хранилище.
        Без этого после подчистки порог падал бы до резервного и отсеянные ранее
        мелкие превью возвращались бы в состав.
        """
        for image_path in image_paths:
            normalized_path = normalize_image_path(image_path)
            source_path = self._resolve_image_source(base_dir, normalized_path)
            try:
                if source_path.exists():
                    if source_path.stat().st_size >= self.MIN_IMAGE_SIZE_BYTES:
                        return self.MIN_IMAGE_SIZE_BYTES
                    continue
            except OSError:
                continue

            # Хранилище опрашивается СТРОГО в ветке отсутствующего исходника:
            # в существующих тестах импорта default_storage подменяется моком,
            # и безусловный вызов size() вернул бы мок вместо числа.
            destination_path = self._build_destination_path(normalized_path, destination_prefix)
            if not self._stored_image_exists(destination_path):
                continue
            copy_size = self._get_stored_image_size(destination_path)
            if copy_size is not None and copy_size >= self.MIN_IMAGE_SIZE_BYTES:
                return self.MIN_IMAGE_SIZE_BYTES
        return self.FALLBACK_MIN_IMAGE_SIZE_BYTES

    # Исходы, попадающие в текстовый отчёт сессии. Порядок фиксирован: по нему
    # строится строка, на которую вешаются тесты и грепы по проду.
    IMAGE_OUTCOMES = (
        ("images_copied", "скопировано"),
        ("images_replaced", "заменено"),
        ("images_skipped_existing", "уже в хранилище"),
        ("images_skipped_small", "отсеяно по размеру"),
        ("images_resolved_from_copy", "узнано по копии"),
        ("images_errors", "ошибок"),
    )

    def _count_image_skip(self, outcome: str) -> None:
        """Учесть исход-«пропуск» и детально, и в общей сумме.

        `images_skipped` остаётся суммой трёх детальных счётчиков: значение уже
        лежит в `report_details` прошлых сессий и читается админкой, и менять
        его смысл задним числом нельзя.
        """
        self.stats[outcome] += 1
        self.stats["images_skipped"] += 1

    def image_report_line(self) -> str:
        """Строка про изображения для текстового отчёта сессии.

        До этого числа жили только в JSONB `report_details`, а `images_skipped`
        смешивал три разных исхода — оператор видел одну кучу (на проде 11 186)
        и не мог сказать, сколько фото отброшено, а сколько просто узнано по уже
        перенесённой копии. Пустая строка для прогонов без картинок: сегменты
        остатков и цен не должны получать шумную строку в отчёте.
        """
        if not any(self.stats.get(key) for key, _ in self.IMAGE_OUTCOMES):
            return ""

        parts = ", ".join(f"{label} {self.stats.get(key, 0)}" for key, label in self.IMAGE_OUTCOMES)
        return f"Изображения: {parts}"

    def _save_image_if_not_exists(
        self,
        source_path: Path,
        image_path: str,
        destination_prefix: str,
        min_size_bytes: int | None = None,
    ) -> str | None:
        """
        Helper метод для сохранения изображения если оно еще не существует

        Args:
            source_path: Путь к исходному файлу изображения
            image_path: Относительный путь изображения из XML
            destination_prefix: Префикс директории назначения ('base' или 'variants')
            min_size_bytes: Минимальный размер файла; если None — использует MIN_IMAGE_SIZE_BYTES

        Returns:
            Путь к сохраненному файлу или None если файл не найден/ошибка/слишком мал
        """
        from django.conf import settings
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        effective_min = min_size_bytes if min_size_bytes is not None else self.MIN_IMAGE_SIZE_BYTES

        # Целевой путь вычисляется ДО проверки исходника: без него нельзя узнать,
        # что картинка уже перенесена в хранилище прошлым прогоном.
        destination_path = self._build_destination_path(image_path, destination_prefix)
        subdir = image_path.split("/")[0] if "/" in image_path else ""

        if not source_path.exists():
            # Исходник уже убран — как самой 1С, так и уборкой потреблённого
            # ниже. goods.xml с теми же товарами приходит снова, и уже
            # перенесённая копия — не потеря файла, иначе каждый прогон выдаёт
            # сотни ложных Image not found.
            if self._stored_image_exists(destination_path):
                copy_size = self._get_stored_image_size(destination_path)
                if copy_size is not None and copy_size < effective_min:
                    # Отсев по размеру, просто замеренный на копии, а не на
                    # исходнике: исход тот же, что и у мелкого превью ниже.
                    self._count_image_skip("images_skipped_small")
                    logger.debug(
                        f"Stored image too small, skipping: {destination_path} "
                        f"({copy_size / 1024:.1f}KB < {effective_min // 1024}KB)"
                    )
                    return None
                # Картинка РАЗРЕШЕНА копией, а не отброшена. На проде это самый
                # частый исход, и в общей куче `images_skipped` он читался как
                # потеря — отсюда отдельный счётчик.
                self._count_image_skip("images_resolved_from_copy")
                return destination_path

            logger.warning(f"Image not found: {source_path}")
            self.stats["images_errors"] += 1
            return None

        file_size = source_path.stat().st_size
        if file_size < effective_min:
            size_kb = file_size / 1024
            logger.debug(f"Image too small, skipping: {source_path} " f"({size_kb:.1f}KB < {effective_min // 1024}KB)")
            self._count_image_skip("images_skipped_small")
            return None

        # CAP-5. Решение «копировать или пропустить» больше не принимается по
        # одному лишь имени файла. Имя детерминировано парой GUID товара и
        # картинки, поэтому замена СОДЕРЖИМОГО снимка в 1С без смены GUID
        # оставляла на сайте старую версию — молча, без ошибок и следов в
        # отчёте. Сверяем размер: это дёшево (хранилище отдаёт его одним
        # вызовом) и ловит подавляющее большинство реальных замен.
        replacing = False
        if default_storage.exists(destination_path):
            stored_size = self._get_stored_image_size(destination_path)

            if stored_size is None or stored_size == file_size:
                # Размер совпал либо хранилище его не отдаёт — считаем копию
                # актуальной. Побайтовое сравнение здесь стоило бы чтения всего
                # каталога на каждом прогоне (6,4 ГБ на проде) ради случая,
                # когда подменённый снимок весит ровно столько же.
                self._count_image_skip("images_skipped_existing")
                self.consumed_image_sources.add(str(source_path))
                return destination_path

            # Размеры разошлись — 1С прислала другое содержимое под тем же
            # именем. `default_storage.save` на занятый путь завёл бы файл с
            # суффиксом, а карточка осталась бы на старом, поэтому копию
            # удаляем и пишем заново.
            try:
                default_storage.delete(destination_path)
                replacing = True
            except Exception as exc:
                logger.warning(f"Failed to delete stale image copy {destination_path}: {exc}")
                self._count_image_skip("images_skipped_existing")
                self.consumed_image_sources.add(str(source_path))
                return destination_path

        # Создание директории
        if subdir:
            subdir_path = os.path.join(settings.MEDIA_ROOT, "products", destination_prefix, subdir)
            os.makedirs(subdir_path, exist_ok=True)

        # Копирование файла
        try:
            with open(source_path, "rb") as f:
                saved_path = default_storage.save(destination_path, ContentFile(f.read()))
            self.stats["images_replaced" if replacing else "images_copied"] += 1
            if replacing:
                logger.info(
                    f"Image content replaced under the same name: {destination_path} "
                    f"({stored_size} -> {file_size} bytes)"
                )
            self.consumed_image_sources.add(str(source_path))
            return saved_path
        except Exception as e:
            logger.error(f"Error saving image {image_path}: {e}")
            self.stats["images_errors"] += 1
            return None

    # ========================================================================
    # Task 1: Рефакторинг парсера goods.xml (AC: 1)
    # ========================================================================

    def process_product_from_goods(
        self,
        goods_data: dict[str, Any],
        base_dir: str | None = None,
        skip_images: bool = False,
    ) -> Any | None:
        """
        Создание/обновление Product из goods.xml (AC1)

        Создаёт только базовую информацию Product:
        - name, slug, brand, category, description
        - base_images (Hybrid подход)
        - НЕ записывает цены/остатки (перенесены в ProductVariant)

        Args:
            goods_data: Данные товара из XMLDataParser.parse_goods_xml()
            base_dir: Базовая директория для изображений
            skip_images: Пропустить импорт изображений

        Returns:
            Product instance или None при ошибке
        """
        from apps.products.models import Brand, Brand1CMapping, Category, Product

        try:
            parent_id = goods_data.get("id")
            if not parent_id:
                self._log_error("Missing parent_id in goods_data", goods_data)
                return None

            # Ensure types
            parent_id = str(parent_id)
            brand_id = str(goods_data.get("brand_id")) if goods_data.get("brand_id") else None

            logger.info(f"Processing product from goods.xml: {parent_id}")

            # Сохраняем ставку НДС для последующего использования при создании вариантов
            vat_rate = goods_data.get("vat_rate")
            if vat_rate is not None:
                vat_rate = Decimal(str(vat_rate))
                goods_data["vat_rate"] = vat_rate
                self._product_vat_rates[parent_id] = vat_rate

            # Проверка существующего товара
            existing = Product.objects.filter(models.Q(onec_id=parent_id) | models.Q(parent_onec_id=parent_id)).first()

            if existing:
                # Обновление существующего Product
                return self._update_existing_product(existing, goods_data, base_dir, skip_images)

            # Создание нового Product
            return self._create_new_product(goods_data, base_dir, skip_images)

        except Exception as e:
            self._log_error(f"Error processing product from goods: {e}", goods_data)
            return None

    def _update_existing_product(
        self,
        product: Any,
        goods_data: dict[str, Any],
        base_dir: str | None,
        skip_images: bool,
    ) -> Any:
        """Обновление существующего Product"""
        from apps.products.models import Brand, Brand1CMapping

        parent_id = str(goods_data.get("id"))
        brand_id = str(goods_data.get("brand_id")) if goods_data.get("brand_id") else None

        # Убедимся что onec_id установлен
        if not product.onec_id:
            product.onec_id = parent_id

        # Обновляем бренд если изменился
        brand = self._determine_brand(brand_id, str(parent_id))
        fields_to_update: list[str] = []

        if product.brand_id != brand.pk:
            product.brand = brand
            fields_to_update.append("brand")

        if brand_id and product.onec_brand_id != brand_id:
            product.onec_brand_id = brand_id
            fields_to_update.append("onec_brand_id")

        # Обновляем описание если есть
        description = goods_data.get("description")
        if description and product.description != description:
            product.description = description
            fields_to_update.append("description")

        vat_rate = goods_data.get("vat_rate")
        if vat_rate is not None:
            vat_rate = Decimal(str(vat_rate))
            if product.vat_rate != vat_rate:
                product.vat_rate = vat_rate
                fields_to_update.append("vat_rate")

        if fields_to_update:
            product.save(update_fields=fields_to_update)

        if vat_rate is not None:
            self._sync_product_variants_vat_rate(product, vat_rate)

        # Импорт изображений в base_images (Hybrid подход).
        # goods.xml — источник истины по составу, поэтому зеркалируем.
        if not skip_images and base_dir and "images" in goods_data:
            self._import_base_images(product, goods_data["images"], base_dir, mirror_composition=True)

        self.stats["products_updated"] += 1
        self.updated_products.append(str(product.onec_id))
        logger.info(f"Product updated: {product.onec_id}")
        return product

    def _create_new_product(
        self,
        goods_data: dict[str, Any],
        base_dir: str | None,
        skip_images: bool,
    ) -> Any | None:
        """Создание нового Product"""
        from apps.products.models import Brand, Category, Product

        parent_id = goods_data.get("id")
        brand_id = goods_data.get("brand_id")

        # Получаем категорию
        category = self._get_or_create_category(goods_data)

        if category is None:
            # Категория отфильтрована — пропускаем товар
            self.stats["skipped"] += 1
            logger.debug(f"Product {parent_id} skipped: category filtered out")
            return None

        # Получаем бренд
        brand = self._determine_brand(brand_id, str(parent_id))

        # Генерируем уникальный slug
        name = goods_data.get("name", "Product Placeholder")
        slug = self._generate_unique_slug(name, str(parent_id))

        # Создание Product (без цен/остатков - они в ProductVariant)
        product = Product(
            onec_id=parent_id,
            parent_onec_id=parent_id,
            onec_brand_id=brand_id,
            name=name,
            slug=slug,
            description=goods_data.get("description", ""),
            brand=brand,
            category=category,
            vat_rate=Decimal(str(goods_data["vat_rate"])) if goods_data.get("vat_rate") is not None else None,
            is_active=False,  # Активируется после создания variants
            sync_status=Product.SyncStatus.PENDING,
            base_images=[],  # Будет заполнено при импорте изображений
        )

        try:
            product.save()
            logger.info(f"Product created: {product.onec_id}")
            self.stats["products_created"] += 1

            # Импорт изображений в base_images (Hybrid подход).
            # goods.xml — источник истины по составу, поэтому зеркалируем.
            if not skip_images and base_dir and "images" in goods_data:
                self._import_base_images(product, goods_data["images"], base_dir, mirror_composition=True)

            return product

        except Exception as e:
            self._log_error(f"Error saving product: {e}", goods_data)
            return None

    def _sync_product_variants_vat_rate(self, product: Any, vat_rate: Decimal) -> int:
        """Обновляет ставки НДС существующих вариантов после раздельного импорта goods.xml.

        Пропускает варианты, у которых склад имеет собственный маппинг vat_rate в WAREHOUSE_RULES:
        для таких вариантов ставка НДС определяется складом (rests.xml), а не товаром (goods.xml).
        """
        from apps.products.models import ProductVariant

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        # Склады с явным vat_rate — их варианты обновляет rests.xml, не goods.xml
        warehouses_with_own_vat = [name for name, info in warehouse_rules.items() if info.get("vat_rate") is not None]

        updated = (
            ProductVariant.objects.filter(product=product)
            .filter(models.Q(vat_rate__isnull=True) | ~models.Q(vat_rate=vat_rate))
            .exclude(warehouse_name__in=warehouses_with_own_vat)
            .update(vat_rate=vat_rate)
        )
        if updated:
            self.stats["variants_updated"] += updated
            logger.info(f"Product {product.onec_id}: synchronized vat_rate={vat_rate} to {updated} existing variants")
        return updated

    def _import_base_images(
        self,
        product: Any,
        image_paths: list[str],
        base_dir: str,
        *,
        mirror_composition: bool = False,
    ) -> None:
        """
        Импорт изображений в Product.base_images (Hybrid подход AC6)

        Args:
            product: Product instance
            image_paths: Список путей к изображениям из goods.xml
            base_dir: Базовая директория импорта
            mirror_composition: True — состав и порядок берутся из выгрузки
                (goods.xml — источник истины, снятая в 1С картинка уходит).
                False — прежнее аддитивное поведение; используется импортом
                сканированием каталога, где список собран по остаткам на диске
                и зеркалирование обрезало бы всё, чего на диске уже нет.
        """
        if not image_paths:
            return

        effective_min = self._get_effective_min_size(image_paths, base_dir, "base")

        # Разрешение картинок выгрузки строго в её порядке
        resolved: list[str] = []
        resolved_filenames: set[str] = set()

        for image_path in image_paths:
            try:
                # Нормализация пути (убираем import_files/ если есть)
                normalized_path = normalize_image_path(image_path)
                source_path = self._resolve_image_source(base_dir, normalized_path)
                saved_path = self._save_image_if_not_exists(
                    source_path, normalized_path, "base", min_size_bytes=effective_min
                )

                if saved_path:
                    saved_filename = Path(saved_path).name
                    # 1С может прислать один и тот же файл дважды
                    if saved_filename in resolved_filenames:
                        continue
                    resolved.append(saved_path)
                    resolved_filenames.add(saved_filename)

            except Exception as e:
                logger.error(f"Error copying image {image_path}: {e}")
                self.stats["images_errors"] += 1

        if mirror_composition:
            if not resolved:
                # Сбой обмена, подчищенный каталог и «в 1С сняли все фото»
                # неотличимы — состав остаётся прежним.
                logger.warning(
                    f"Product {product.onec_id}: ни одна картинка выгрузки не разрешилась, "
                    f"base_images оставлены без изменений"
                )
                return
            base_images = resolved
        else:
            # Дедупликация существующих base_images по filename (исправление бага дублей)
            existing_images = product.base_images or []
            seen_filenames: set[str] = set()
            base_images = []

            for img_path in existing_images:
                filename = Path(img_path).name if img_path else ""
                if filename and filename not in seen_filenames:
                    base_images.append(img_path)
                    seen_filenames.add(filename)

            seen_paths: set[str] = set(base_images)

            for saved_path in resolved:
                saved_filename = Path(saved_path).name
                # Проверяем и по пути, и по filename
                if saved_filename in seen_filenames:
                    continue
                if saved_path not in seen_paths:
                    base_images.append(saved_path)
                    seen_paths.add(saved_path)
                    seen_filenames.add(saved_filename)

        # Сохранение base_images
        if base_images != list(product.base_images or []):
            product.base_images = base_images
            product.save(update_fields=["base_images"])
            logger.info(f"Product {product.onec_id} base_images updated: " f"{len(base_images)} images")

    # ========================================================================
    # Task 2: Парсер offers.xml для ProductVariant (AC: 2, 3, 4)
    # ========================================================================

    def process_variant_from_offer(
        self,
        offer_data: dict[str, Any],
        base_dir: str | None = None,
        skip_images: bool = False,
    ) -> Any | None:
        """
        Создание ProductVariant из offers.xml (AC2, AC3, AC4)

        Args:
            offer_data: Данные предложения из XMLDataParser.parse_offers_xml()
            base_dir: Базовая директория для изображений вариантов
            skip_images: Пропустить импорт изображений

        Returns:
            ProductVariant instance или None при ошибке/пропуске
        """
        from apps.products.models import Product, ProductVariant

        try:
            onec_id = offer_data.get("id")
            if not onec_id:
                self._log_error("Missing id in offer_data", offer_data)
                return None

            # Парсинг составного ID (AC2)
            try:
                parent_id, variant_id = parse_onec_id(onec_id)
            except ValueError as e:
                logger.warning(f"Invalid onec_id format: {onec_id} - {e}")
                self.stats["warnings"] += 1
                return None

            # Поиск родительского Product (AC3)
            product = self._get_product_by_parent_id(parent_id)
            if not product:
                # AC3: логировать warning и пропустить
                if parent_id not in self._missing_products_logged:
                    logger.warning(
                        f"Skipping <Предложение> {onec_id}: " f"parent Product not found (parent_id={parent_id})"
                    )
                    self._missing_products_logged.add(parent_id)
                self.stats["skipped"] += 1
                return None

            # Ставка НДС из маппинга goods.xml → variants
            vat_rate = self._product_vat_rates.get(parent_id)
            if vat_rate is None and product.vat_rate is not None:
                vat_rate = Decimal(str(product.vat_rate))

            # Проверка существующего варианта
            existing_variant = ProductVariant.objects.filter(onec_id=onec_id).first()
            if existing_variant:
                return self._update_existing_variant(existing_variant, offer_data, base_dir, skip_images, vat_rate)

            # Создание нового варианта
            return self._create_new_variant(product, onec_id, offer_data, base_dir, skip_images, vat_rate)

        except Exception as e:
            self._log_error(f"Error processing variant from offer: {e}", offer_data)
            return None

    def _update_existing_variant(
        self,
        variant: Any,
        offer_data: dict[str, Any],
        base_dir: str | None,
        skip_images: bool,
        vat_rate: "Decimal | None" = None,
    ) -> Any:
        """Обновление существующего ProductVariant"""
        fields_to_update: list[str] = []

        # Обновляем SKU если изменился
        article = offer_data.get("article")
        if article and variant.sku != article:
            variant.sku = article
            fields_to_update.append("sku")

        # Обновляем характеристики (AC4)
        characteristics = offer_data.get("characteristics", [])
        parsed_chars = parse_characteristics(characteristics)

        # Fallback на извлечение из названия
        name = offer_data.get("name", "")
        if not parsed_chars["color_name"]:
            parsed_chars["color_name"] = extract_color_from_name(name)
        # AC7: непомещающуюся характеристику бракуем ДО fallback — иначе она
        # блокирует извлечение валидного размера из наименования и он теряется
        parsed_chars["size_value"] = self._normalize_size_value(parsed_chars["size_value"], variant.onec_id)
        if not parsed_chars["size_value"]:
            parsed_chars["size_value"] = self._normalize_size_value(extract_size_from_name(name), variant.onec_id)

        if parsed_chars["color_name"] and variant.color_name != parsed_chars["color_name"]:
            variant.color_name = parsed_chars["color_name"]
            fields_to_update.append("color_name")

        if parsed_chars["size_value"] and variant.size_value != parsed_chars["size_value"]:
            variant.size_value = parsed_chars["size_value"]
            fields_to_update.append("size_value")

        # Активируем вариант
        if not variant.is_active:
            variant.is_active = True
            fields_to_update.append("is_active")

        # Обновляем ставку НДС если известна из goods.xml
        if vat_rate is not None and variant.vat_rate != vat_rate:
            variant.vat_rate = vat_rate
            fields_to_update.append("vat_rate")

        if fields_to_update:
            variant.save(update_fields=fields_to_update)

        # Импорт изображений варианта (AC6).
        # offers.xml — источник истины по составу, поэтому зеркалируем.
        if not skip_images and base_dir:
            images = offer_data.get("images", [])
            if images:
                self._import_variant_images(variant, images, base_dir, mirror_composition=True)

        # Story 14.4: Связывание атрибутов с ProductVariant (offers.xml)
        characteristics = offer_data.get("characteristics", [])
        if characteristics:
            try:
                self._link_variant_attributes(variant, characteristics)
            except Exception as attr_error:
                logger.error(f"Error linking attributes for variant {variant.onec_id}: " f"{attr_error}")
                self.stats["errors"] += 1

        self.stats["variants_updated"] += 1
        self.updated_variants.append(str(variant.onec_id))
        logger.info(f"ProductVariant updated: {variant.onec_id}")
        return variant

    def _create_new_variant(
        self,
        product: Any,
        onec_id: str,
        offer_data: dict[str, Any],
        base_dir: str | None,
        skip_images: bool,
        vat_rate: "Decimal | None" = None,
    ) -> Any | None:
        """Создание нового ProductVariant"""
        from apps.products.models import ProductVariant

        # Извлечение характеристик (AC4)
        characteristics = offer_data.get("characteristics", [])
        parsed_chars = parse_characteristics(characteristics)

        # Fallback на извлечение из названия
        name = offer_data.get("name", "")
        if not parsed_chars["color_name"]:
            parsed_chars["color_name"] = extract_color_from_name(name)
        # AC7: непомещающуюся характеристику бракуем ДО fallback — иначе она
        # блокирует извлечение валидного размера из наименования и он теряется
        parsed_chars["size_value"] = self._normalize_size_value(parsed_chars["size_value"], onec_id)
        if not parsed_chars["size_value"]:
            parsed_chars["size_value"] = self._normalize_size_value(extract_size_from_name(name), onec_id)

        # SKU
        article = offer_data.get("article")
        sku = article if article else f"SKU-{onec_id[:8]}"

        # Обеспечиваем уникальность SKU
        sku = self._ensure_unique_sku(sku)

        variant = ProductVariant(
            product=product,
            sku=sku,
            onec_id=onec_id,
            color_name=parsed_chars["color_name"],
            size_value=parsed_chars["size_value"],
            is_active=True,
            # Цены по умолчанию = 0, будут обновлены из prices.xml
            retail_price=Decimal("0"),
            opt1_price=None,
            opt2_price=None,
            opt3_price=None,
            opt4_price=None,
            trainer_price=None,
            federation_price=None,
            stock_quantity=0,  # Будет обновлен из rests.xml
            vat_rate=vat_rate,  # Ставка НДС из goods.xml
        )

        try:
            variant.save()
            logger.info(
                f"ProductVariant created: {variant.onec_id} "
                f"(sku={variant.sku}, color={variant.color_name}, "
                f"size={variant.size_value})"
            )
            self.stats["variants_created"] += 1

            # Активируем родительский Product
            if not product.is_active:
                product.is_active = True
                product.sync_status = product.SyncStatus.IN_PROGRESS
                product.save(update_fields=["is_active", "sync_status"])

            # Импорт изображений варианта (AC6).
            # offers.xml — источник истины по составу, поэтому зеркалируем.
            if not skip_images and base_dir:
                images = offer_data.get("images", [])
                if images:
                    self._import_variant_images(variant, images, base_dir, mirror_composition=True)

            # Story 14.4: Связывание атрибутов с ProductVariant (offers.xml)
            characteristics = offer_data.get("characteristics", [])
            if characteristics:
                try:
                    self._link_variant_attributes(variant, characteristics)
                except Exception as attr_error:
                    logger.error(f"Error linking attributes for new variant {variant.onec_id}: " f"{attr_error}")
                    self.stats["errors"] += 1

            return variant

        except Exception as e:
            self._log_error(f"Error saving variant: {e}", offer_data)
            return None

    def _import_variant_images(
        self,
        variant: Any,
        image_paths: list[str],
        base_dir: str,
        *,
        mirror_composition: bool = False,
    ) -> None:
        """
        Импорт изображений в ProductVariant (AC6 - Hybrid подход)

        Первое изображение → main_image
        Остальные → gallery_images

        Args:
            variant: ProductVariant instance
            image_paths: Список путей к изображениям из offers.xml
            base_dir: Базовая директория импорта
            mirror_composition: True — состав и порядок берутся из выгрузки,
                уже заполненное main_image переназначается. False — прежнее
                аддитивное поведение для импорта сканированием каталога.
        """
        if not image_paths:
            return

        effective_min = self._get_effective_min_size(image_paths, base_dir, "variants")

        # Разрешение картинок выгрузки строго в её порядке
        resolved: list[str] = []
        resolved_filenames: set[str] = set()

        for image_path in image_paths:
            try:
                # Нормализация пути (убираем import_files/ если есть)
                normalized_path = normalize_image_path(image_path)
                source_path = self._resolve_image_source(base_dir, normalized_path)
                saved_path = self._save_image_if_not_exists(
                    source_path, normalized_path, "variants", min_size_bytes=effective_min
                )

                if saved_path:
                    saved_filename = Path(saved_path).name
                    # 1С может прислать один и тот же файл дважды
                    if saved_filename in resolved_filenames:
                        continue
                    resolved.append(saved_path)
                    resolved_filenames.add(saved_filename)

            except Exception as e:
                logger.error(f"Error copying variant image {image_path}: {e}")
                self.stats["images_errors"] += 1

        if mirror_composition:
            if not resolved:
                # Пустое разрешение состав варианта не меняет — см. _import_base_images
                logger.warning(
                    f"Variant {variant.onec_id}: ни одна картинка выгрузки не разрешилась, "
                    f"состав изображений оставлен без изменений"
                )
                return

            variant.main_image = resolved[0]
            variant.gallery_images = resolved[1:]
            variant.save(update_fields=["main_image", "gallery_images"])
            return

        main_image_set = bool(variant.main_image)

        # Дедупликация существующих gallery_images по filename (исправление бага дублей)
        existing_gallery = variant.gallery_images or []
        seen_filenames: set[str] = set()
        gallery_images: list[str] = []

        # Добавляем main_image filename в seen_filenames.
        # Path() принимает только str: main_image — ImageFieldFile, берём .name.
        if variant.main_image:
            main_filename = Path(variant.main_image.name).name
            if main_filename:
                seen_filenames.add(main_filename)

        for img_path in existing_gallery:
            filename = Path(img_path).name if img_path else ""
            if filename and filename not in seen_filenames:
                gallery_images.append(img_path)
                seen_filenames.add(filename)

        seen_paths: set[str] = set(gallery_images)

        for saved_path in resolved:
            saved_filename = Path(saved_path).name
            # Проверяем и по пути, и по filename
            if saved_filename in seen_filenames:
                continue

            if not main_image_set:
                variant.main_image = saved_path
                main_image_set = True
                seen_filenames.add(saved_filename)
            elif saved_path not in seen_paths:
                gallery_images.append(saved_path)
                seen_paths.add(saved_path)
                seen_filenames.add(saved_filename)

        # Сохранение
        variant.gallery_images = gallery_images
        variant.save(update_fields=["main_image", "gallery_images"])

    # ========================================================================
    # Task 3: Обработка товаров без вариантов (AC: 5)
    # ========================================================================

    def create_default_variants(self) -> int:
        """
        Создание дефолтных ProductVariant для товаров без вариантов (AC5)

        Выполняется ПОСЛЕ parse_offers_xml() и ДО parse_prices_xml()

        Returns:
            Количество созданных default variants
        """
        from apps.products.models import Product, ProductVariant

        # Найти все Products без ProductVariant (включая неактивные)
        products_without_variants = Product.objects.filter(
            variants__isnull=True,
        )

        count = products_without_variants.count()
        logger.info(f"Found {count} products without variants")

        if count == 0:
            logger.info("No products without variants found, skipping default variant creation")
            return 0

        default_variants: list[ProductVariant] = []
        product_ids_to_activate: list[int] = []
        batch_count = 0

        for product in products_without_variants.iterator():
            # Генерируем уникальный SKU
            sku = self._ensure_unique_sku(product.onec_id or f"DEFAULT-{product.pk}")

            variant = ProductVariant(
                product=product,
                sku=sku,
                onec_id=product.onec_id or f"default-{product.pk}",
                color_name="",
                size_value="",
                is_active=True,
                retail_price=Decimal("0"),
                opt1_price=None,
                opt2_price=None,
                opt3_price=None,
                opt4_price=None,
                trainer_price=None,
                federation_price=None,
                stock_quantity=0,
                vat_rate=Decimal(str(product.vat_rate)) if product.vat_rate is not None else None,
            )
            default_variants.append(variant)
            product_ids_to_activate.append(product.pk)

            logger.info(
                f"Creating default variant for product: {product.name} " f"(onec_id={product.onec_id}, sku={sku})"
            )

            # Batch processing (NFR4)
            if len(default_variants) >= self.batch_size:
                with transaction.atomic():
                    ProductVariant.objects.bulk_create(default_variants, ignore_conflicts=True)
                    Product.objects.filter(pk__in=product_ids_to_activate, is_active=False).update(is_active=True)
                batch_count += len(default_variants)
                logger.info(f"Processed {batch_count} default variants")
                default_variants = []
                product_ids_to_activate = []

        # Сохранение оставшихся
        if default_variants:
            with transaction.atomic():
                ProductVariant.objects.bulk_create(default_variants, ignore_conflicts=True)
                Product.objects.filter(pk__in=product_ids_to_activate, is_active=False).update(is_active=True)
            batch_count += len(default_variants)

        self.stats["default_variants_created"] = batch_count
        logger.info(f"Successfully created {batch_count} default variants")
        return batch_count

    # ========================================================================
    # Task 5: Рефакторинг парсера prices.xml (AC: 7)
    # ========================================================================

    def update_variant_prices(self, price_data: dict[str, Any]) -> bool:
        """
        Обновление цен ProductVariant из prices.xml (AC7)

        Args:
            price_data: Данные цен из XMLDataParser.parse_prices_xml()

        Returns:
            True если обновление успешно, False при ошибке
        """
        from apps.products.models import PriceType, ProductVariant

        try:
            onec_id = price_data.get("id")
            if not onec_id:
                self._log_error("Missing id in price_data", price_data)
                return False

            # Находим ProductVariant по onec_id
            variant = self._get_variant_by_onec_id(onec_id)
            if not variant:
                if onec_id not in self._missing_variants_logged:
                    logger.warning(f"ProductVariant not found for price update: {onec_id}")
                    self._missing_variants_logged.add(onec_id)
                self.stats["warnings"] += 1
                return False

            # Маппинг цен через PriceType
            prices = price_data.get("prices", [])
            price_updates: dict[str, Decimal] = {}

            for price_item in prices:
                price_type_id = price_item.get("price_type_id")
                price_value = price_item.get("value")

                if not price_type_id or price_value is None:
                    continue

                # Находим маппинг типа цены
                price_type = PriceType.objects.filter(onec_id=price_type_id, is_active=True).first()

                if price_type:
                    field_name = price_type.product_field
                    # Вид цен без маппинга (product_field="") не применяем ни к одному
                    # полю — иначе цена уехала бы в розницу через прежний fallback
                    if not field_name:
                        if price_type_id not in self._unmapped_price_types_logged:
                            logger.warning(
                                f"Вид цен '{price_type.onec_name}' ({price_type_id}) "
                                f"не сопоставлен полю ProductVariant — цены этого вида пропускаются"
                            )
                            self._unmapped_price_types_logged.add(price_type_id)
                        continue
                    price_updates[field_name] = price_value

            # Auto-populate retail_price from RRP if not provided
            # РРЦ из 1С является базовой розничной ценой для сайта
            if "rrp" in price_updates and "retail_price" not in price_updates:
                price_updates["retail_price"] = price_updates["rrp"]

            # Применяем обновления цен
            fields_to_update: list[str] = []
            for field_name, value in price_updates.items():
                if hasattr(variant, field_name):
                    setattr(variant, field_name, value)
                    fields_to_update.append(field_name)

            if fields_to_update:
                variant.last_sync_at = timezone.now()
                fields_to_update.append("last_sync_at")
                variant.save(update_fields=fields_to_update)
                self.stats["prices_updated"] += 1
                self.updated_variants.append(str(variant.onec_id))
                return True

            return False

        except Exception as e:
            self._log_error(f"Error updating variant prices: {e}", price_data)
            return False

    # ========================================================================
    # Task 6: Рефакторинг парсера rests.xml (AC: 8)
    # ========================================================================

    def update_variant_stock(self, rest_data: dict[str, Any]) -> bool:
        """
        Обновление остатков ProductVariant из rests.xml (AC8)

        Args:
            rest_data: Данные остатков из XMLDataParser.parse_rests_xml()

        Returns:
            True если обновление успешно, False при ошибке
        """
        from apps.products.models import ProductVariant

        try:
            onec_id = rest_data.get("id")
            quantity = rest_data.get("quantity", 0)
            warehouse_id = str(rest_data.get("warehouse_id") or "").strip()

            if not onec_id:
                self._log_error("Missing id in rest_data", rest_data)
                return False

            # Находим ProductVariant по onec_id
            variant = self._get_variant_by_onec_id(onec_id)
            if not variant:
                if onec_id not in self._missing_variants_logged:
                    logger.warning(f"ProductVariant not found for stock update: {onec_id}")
                    self._missing_variants_logged.add(onec_id)
                self.stats["warnings"] += 1
                return False

            # Остатки приходят отдельными строками по складам.
            # Храним суммарный остаток и определяем основной склад по наибольшему количеству.
            stock_state = self._stock_buffer.setdefault(onec_id, {"total": 0, "warehouses": {}})
            stock_state["total"] += quantity
            if warehouse_id:
                warehouse_totals = stock_state["warehouses"]
                warehouse_totals[warehouse_id] = warehouse_totals.get(warehouse_id, 0) + quantity

            total_quantity = int(stock_state["total"])
            primary_warehouse_id = self._select_primary_warehouse_id(
                stock_state["warehouses"],
                variant.warehouse_id,
            )
            primary_warehouse_name = self._resolve_warehouse_name(primary_warehouse_id)
            primary_vat_rate = self._get_vat_rate_by_warehouse_name(primary_warehouse_name)

            variant.stock_quantity = total_quantity
            if primary_warehouse_id:
                variant.warehouse_id = primary_warehouse_id
            if primary_warehouse_name:
                variant.warehouse_name = primary_warehouse_name
            if primary_vat_rate is not None:
                variant.vat_rate = primary_vat_rate
            variant.last_sync_at = timezone.now()
            update_fields = ["stock_quantity", "last_sync_at"]
            if primary_warehouse_id:
                update_fields.append("warehouse_id")
            if primary_warehouse_name:
                update_fields.append("warehouse_name")
            if primary_vat_rate is not None:
                update_fields.append("vat_rate")
            variant.save(update_fields=update_fields)

            # Обновляем статус родительского Product
            product = variant.product
            if product.sync_status != product.SyncStatus.COMPLETED:
                product.sync_status = product.SyncStatus.COMPLETED
                product.last_sync_at = timezone.now()
                product.save(update_fields=["sync_status", "last_sync_at"])

            self.stats["stocks_updated"] += 1
            self.updated_variants.append(str(variant.onec_id))
            return True

        except Exception as e:
            self._log_error(f"Error updating variant stock: {e}", rest_data)
            return False

    # ========================================================================
    # Story 14.4: Link attributes to ProductVariant
    # ========================================================================

    def _link_variant_attributes(self, variant: Any, characteristics: list[dict[str, str]]) -> None:
        """
        Связывание атрибутов с ProductVariant по normalized name/value (offers.xml).

        Args:
            variant: ProductVariant instance для связывания атрибутов
            characteristics: Список словарей {name, value} из offers.xml

        Behavior:
            - Search Attribute by normalized_name (NO is_active filter - Variant C)
            - Search AttributeValue by attribute + normalized_value
            - Create AttributeValue on-the-fly if missing (AC3)
            - Handle slug uniqueness for on-the-fly values
            - Update stats: attributes_linked, attributes_missing
        """
        from apps.products.models import Attribute, AttributeValue
        from apps.products.utils.attributes import normalize_attribute_name, normalize_attribute_value

        if not characteristics:
            return

        attribute_values_to_link = []

        for char in characteristics:
            char_name = char.get("name", "").strip()
            char_value = char.get("value", "").strip()

            if not char_name or not char_value:
                continue

            # Нормализация для поиска
            normalized_name = normalize_attribute_name(char_name)
            normalized_value = normalize_attribute_value(char_value)

            # Поиск Attribute по normalized_name (БЕЗ фильтрации по is_active)
            attribute = Attribute.objects.filter(normalized_name=normalized_name).first()

            if not attribute:
                logger.warning(
                    f"Attribute not found for normalized_name='{normalized_name}' "
                    f"(original: '{char_name}'), variant={variant.onec_id}, "
                    f"skipping attribute linkage"
                )
                self.stats["attributes_missing"] += 1
                continue

            # Поиск AttributeValue по attribute + normalized_value
            attribute_value = AttributeValue.objects.filter(
                attribute=attribute,
                normalized_value=normalized_value,
            ).first()

            if not attribute_value:
                # AC3: Create AttributeValue on-the-fly
                try:
                    from transliterate import translit

                    transliterated = translit(char_value, "ru", reversed=True)
                    base_slug = slugify(transliterated)
                except (RuntimeError, ImportError):
                    base_slug = slugify(char_value)

                if not base_slug:
                    base_slug = f"value-{normalized_value[:20]}"

                # Обеспечиваем уникальность slug
                slug = base_slug
                counter = 1
                while AttributeValue.objects.filter(slug=slug).exists():
                    slug = f"{base_slug}-{counter}"
                    counter += 1

                attribute_value = AttributeValue.objects.create(
                    attribute=attribute,
                    value=char_value,
                    slug=slug,
                    normalized_value=normalized_value,
                )

                logger.info(
                    f"Created AttributeValue on-the-fly: "
                    f"{attribute.name}='{char_value}' (slug={slug}), "
                    f"variant={variant.onec_id}"
                )

            attribute_values_to_link.append(attribute_value)
            self.stats["attributes_linked"] += 1

        # Bulk link через set()
        if attribute_values_to_link:
            variant.attributes.set(attribute_values_to_link)

    # ========================================================================
    # Helper methods
    # ========================================================================

    def _get_product_by_parent_id(self, parent_id: str) -> Any | None:
        """Найти Product по parent_onec_id или onec_id"""
        from apps.products.models import Product

        # Проверяем кэш
        if parent_id in self._product_cache:
            return self._product_cache[parent_id]

        product = Product.objects.filter(models.Q(parent_onec_id=parent_id) | models.Q(onec_id=parent_id)).first()

        if product:
            self._product_cache[parent_id] = product

        return product

    def _get_variant_by_onec_id(self, onec_id: str) -> Any | None:
        """Найти ProductVariant по onec_id"""
        from apps.products.models import ProductVariant

        # Проверяем кэш
        if onec_id in self._variant_cache:
            return self._variant_cache[onec_id]

        variant = ProductVariant.objects.filter(onec_id=onec_id).first()

        # Если не найден по полному ID, пробуем по parent_id
        if not variant and "#" in onec_id:
            parent_id = onec_id.split("#")[0]
            variant = ProductVariant.objects.filter(onec_id=parent_id).first()

        if variant:
            self._variant_cache[onec_id] = variant

        return variant

    def _select_primary_warehouse_id(
        self,
        warehouse_totals: dict[str, int],
        current_warehouse_id: str | None = None,
    ) -> str | None:
        """Возвращает склад с максимальным остатком, сохраняя текущий при равенстве."""
        if not warehouse_totals:
            return current_warehouse_id

        max_qty = max(warehouse_totals.values())
        if current_warehouse_id and warehouse_totals.get(current_warehouse_id) == max_qty:
            return current_warehouse_id

        for warehouse_id, qty in warehouse_totals.items():
            if qty == max_qty:
                return warehouse_id

        return current_warehouse_id

    def _resolve_warehouse_name(self, warehouse_id: str | None) -> str | None:
        """Преобразует GUID склада из rests.xml в имя склада из настроек."""
        if not warehouse_id:
            return None

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_name_by_id = exchange_cfg.get("WAREHOUSE_NAME_BY_ID", {})
        if warehouse_id in warehouse_name_by_id:
            return str(warehouse_name_by_id[warehouse_id])

        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        if warehouse_id in warehouse_rules:
            return warehouse_id

        return None

    def _get_vat_rate_by_warehouse_name(self, warehouse_name: str | None) -> Decimal | None:
        """Возвращает ставку НДС по имени склада."""
        if not warehouse_name:
            return None

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        info = warehouse_rules.get(warehouse_name)
        if not info:
            return None

        vat_rate = info.get("vat_rate")
        if vat_rate is None:
            return None

        return Decimal(str(vat_rate))

    def _determine_brand(self, brand_id: str | None, parent_id: str) -> Any:
        """Определяет бренд через Brand1CMapping или возвращает fallback"""
        from apps.products.models import Brand, Brand1CMapping

        if brand_id:
            mapping = Brand1CMapping.objects.select_related("brand").filter(onec_id=brand_id).first()
            if mapping and mapping.brand:
                return mapping.brand

            logger.warning(
                f"Brand1CMapping not found for onec_id={brand_id}, " f"product={parent_id}, using 'No Brand' fallback"
            )

        return self._get_no_brand()

    def _get_no_brand(self) -> Any:
        """Возвращает fallback бренд 'No Brand'"""
        from apps.products.models import Brand

        brand, _ = Brand.objects.get_or_create(name="No Brand", defaults={"slug": "no-brand", "is_active": True})
        return brand

    def _get_or_create_category(self, goods_data: dict[str, Any]) -> Any:
        """Получает или создаёт категорию.

        Не создаёт публичные placeholder-категории по неизвестным ссылкам из
        goods.xml. Неразрешённые ссылки изолируются в скрытой техкатегории.
        """
        from apps.products.models import Category

        category_id = goods_data.get("category_id")

        if category_id:
            category = Category.objects.filter(onec_id=category_id).first()
            if category:
                if self._category_filtering_active and category_id not in self._allowed_category_ids:
                    logger.warning(
                        "Категория вне разрешённого поддерева; товар перемещается в техкатегорию: "
                        "category_id=%s product_id=%s",
                        category_id,
                        goods_data.get("id"),
                    )
                    self.stats["category_fallbacks"] += 1
                    return self._get_unresolved_category()
                return category

            logger.warning(
                "Ссылка на категорию не разрешена; используется техническая fallback-категория: "
                "category_id=%s product_id=%s",
                category_id,
                goods_data.get("id"),
            )
            self.stats["category_fallbacks"] += 1
            return self._get_unresolved_category()

        # Fallback категория
        if self._category_filtering_active:
            logger.warning("Product without category_id moved to hidden fallback: product_id=%s", goods_data.get("id"))
            self.stats["category_fallbacks"] += 1
            return self._get_unresolved_category()

        category, _ = Category.objects.get_or_create(
            slug="uncategorized",
            defaults={"name": "Без категории", "is_active": True},
        )
        return category

    def _get_unresolved_category(self) -> Any:
        """Скрытая техкатегория для товаров с неразрешённой ссылкой 1С."""
        from apps.products.models import Category

        category, _ = Category.objects.get_or_create(
            slug="onec-unresolved-category",
            defaults={
                "name": "Техническая категория: неразрешенные ссылки 1С",
                "onec_id": "__onec_unresolved_category__",
                "is_active": False,
            },
        )
        if category.is_active:
            category.is_active = False
            category.save(update_fields=["is_active"])
        return category

    def _generate_unique_slug(self, name: str, parent_id: str) -> str:
        """Генерирует уникальный slug для Product"""
        from apps.products.models import Product

        try:
            from transliterate import translit

            transliterated = translit(name, "ru", reversed=True)
            base_slug = slugify(transliterated)
        except (RuntimeError, ImportError):
            base_slug = slugify(name)

        if not base_slug:
            base_slug = f"product-{parent_id[:8]}"

        unique_slug = base_slug
        while Product.objects.filter(slug=unique_slug).exists():
            unique_slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"

        return str(unique_slug)

    def _ensure_unique_sku(self, sku: str) -> str:
        """Обеспечивает уникальность SKU"""
        from apps.products.models import ProductVariant

        if not ProductVariant.objects.filter(sku=sku).exists():
            return sku

        counter = 1
        unique_sku = f"{sku}-{counter}"
        while ProductVariant.objects.filter(sku=unique_sku).exists():
            counter += 1
            unique_sku = f"{sku}-{counter}"

        return unique_sku

    def _normalize_size_value(self, size_value: str, onec_id: str) -> str:
        """Отбрасывает «размер», не влезающий в колонку (AC7).

        Импорт пишет `size_value` напрямую, минуя `full_clean()`. Без этой
        проверки длинное значение возвращает `DataError` и вариант не создаётся
        вообще — так 25.08.2026 потерялись 12 вариантов. Соседние `color_name`
        и `sku` уязвимы тем же механизмом, но по замерам 27.08.2026 держатся
        втрое-восьмеро ниже своего лимита; они вынесены в deferred-work.

        Значение отбрасывается целиком, а не усекается: обрезок вроде
        «Romana 501.96.00 Оборудование спор» — тот же мусор, только теперь ещё
        и в `db_index`, и в композитном индексе `idx_variant_characteristics`.
        Пустое поле честнее.

        Порог берётся из самой модели, чтобы он не мог разойтись с колонкой.
        Счётчик считает варианты, а не события: один и тот же оффер приезжает
        в нескольких сегментах `offers_*.xml`, и в отчёте нужно число товаров,
        а не число встреч.
        """
        max_length = self._size_value_max_length
        # max_length is None — это TextField вместо CharField, то есть колонка,
        # которая не переполняется. Проверять нечего, значение проходит как есть.
        if not size_value or max_length is None or len(size_value) <= max_length:
            return size_value

        if onec_id in self._size_value_dropped_logged:
            return ""
        self._size_value_dropped_logged.add(onec_id)

        self.stats["size_value_dropped"] += 1
        # Общий счётчик warnings намеренно не трогаем: длинные наименования
        # приезжают каждой выгрузкой, и постоянный фон растворил бы в себе
        # настоящие предупреждения сессии.
        preview = " ".join(size_value.split())[:max_length]
        logger.warning(
            f"size_value из выгрузки не записан для {onec_id}: {len(size_value)} символов "
            f"при лимите {max_length} — {preview!r}"
        )
        if self._size_value_reports < self.SIZE_VALUE_REPORT_LIMIT:
            self._size_value_reports += 1
            self.log_progress(
                f"size_value из выгрузки не записан ({len(size_value)} символов "
                f"при лимите {max_length}): {onec_id} — {preview}"
            )
        return ""

    def _log_error(self, message: str, data: Any) -> None:
        """Логирование ошибки"""
        logger.error(f"{message}: {data}")
        self.stats["errors"] += 1

    def get_stats(self) -> dict[str, Any]:
        """Возвращает статистику импорта"""
        # Limit the lists to avoid huge JSONs
        limit = 100
        stats: dict[str, Any] = self.stats.copy()

        stats["updated_products_ids"] = self.updated_products[:limit]
        stats["updated_variants_ids"] = self.updated_variants[:limit]

        if len(self.updated_products) > limit:
            stats["updated_products_ids"].append(f"...and {len(self.updated_products) - limit} more")

        if len(self.updated_variants) > limit:
            stats["updated_variants_ids"].append(f"...and {len(self.updated_variants) - limit} more")

        return stats

    def process_price_types(self, price_types_data: Sequence[PriceTypeData]) -> int:
        """
        Создание/обновление справочника PriceType

        Пустой `product_field` (вид цен не опознан маппером) в defaults не
        попадает — прежний маппинг существующей записи сохраняется.

        Args:
            price_types_data: Последовательность PriceTypeData

        Returns:
            Количество обработанных типов цен
        """
        from apps.products.models import PriceType

        count = 0
        for price_type_data in price_types_data:
            try:
                defaults: dict[str, Any] = {
                    "onec_name": price_type_data["onec_name"],
                    "is_active": True,
                }
                # Пустой product_field = вид цен не опознан маппером
                # (_map_price_type_to_field вернул ""). Не затираем им корректный
                # маппинг существующей записи: переименование вида цен в 1С иначе
                # сбило бы рабочее поле, и цены этого вида стали бы молча
                # пропускаться guard'ом в update_variant_prices.
                # Для новой записи поле останется пустым — цены не применятся,
                # что и требуется для неопознанного вида цен.
                if price_type_data["product_field"]:
                    defaults["product_field"] = price_type_data["product_field"]

                PriceType.objects.update_or_create(
                    onec_id=price_type_data["onec_id"],
                    defaults=defaults,
                )
                count += 1
            except Exception as e:
                logger.error(f"Error processing price type: {e}")
                self.stats["errors"] += 1

        return count

    def process_categories(self, categories_data: list[CategoryData]) -> dict[str, int]:
        """
        Обработка категорий с иерархией (Story 3.1.2)

        Двухпроходный алгоритм:
        1. Создаём все категории без родительских связей
        2. Устанавливаем родительские связи с валидацией циклов

        Фильтрация корневых категорий:
        - Если ROOT_CATEGORY_NAME задан: импортируются только якорь и его потомки
        - Если не задан (None): импортируются все категории (обратная совместимость)
        - Если задан но не найден ни в XML, ни в БД: logger.error + импорт отменяется

        Args:
            categories_data: Список данных категорий с полями
                             id, name, description, parent_id

        Returns:
            dict с количеством created, updated, errors, cycles_detected,
            и опционально root_not_found
        """
        from apps.products.models import Category

        result: dict[str, int | bool] = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "cycles_detected": 0,
        }
        category_map: dict[str, Category] = {}

        # ======================================================================
        # Фильтрация корневых категорий по ROOT_CATEGORY_NAME
        # ======================================================================
        root_category_name = getattr(settings, "ROOT_CATEGORY_NAME", None)
        filtering_active = False
        root_ids: set[str] = set()
        allowed_ids: set[str] = set()
        anchor_id: str | None = None

        if root_category_name:
            # Определяем root_ids — ID категорий без parent_id (корневые)
            for cat in categories_data:
                if not cat.get("parent_id"):
                    cat_id = cat.get("id")
                    if cat_id:
                        root_ids.add(cat_id)
            # Накапливаем корни между файлами выгрузки — см. guard при сборе
            # «раскрытых» родителей ниже.
            self._root_category_onec_ids.update(root_ids)

            # 1. Ищем якорную среди корневых
            for cat in categories_data:
                cat_id = cat.get("id")
                if cat_id in root_ids and cat.get("name") == root_category_name:
                    anchor_id = cat_id
                    break

            # 2. Ищем якорную в базе, если не нашли в XML (случай инкрементального обновления)
            if not anchor_id:
                anchor_cat = Category.objects.filter(
                    name=root_category_name, parent__isnull=True, is_active=True
                ).first()
                if not anchor_cat:
                    # Неактивный якорь реактивируется, чтобы дерево не стало пустым
                    inactive_anchor = Category.objects.filter(
                        name=root_category_name, parent__isnull=True, is_active=False
                    ).first()
                    if inactive_anchor:
                        inactive_anchor.is_active = True
                        inactive_anchor.save(update_fields=["is_active"])
                        anchor_cat = inactive_anchor
                        logger.info(
                            "Якорная категория '%s' была неактивной — реактивирована при инкрементальном импорте.",
                            root_category_name,
                        )
                if anchor_cat:
                    anchor_id = anchor_cat.onec_id

            if anchor_id:
                filtering_active = True
                self._category_filtering_active = True
                self._allowed_category_ids.add(anchor_id)

                # Загружаем существующие категории из БД для построения дерева разрешенных
                db_categories = list(
                    Category.objects.exclude(onec_id__isnull=True)
                    .exclude(onec_id="")
                    .values("onec_id", "parent__onec_id")
                )
                db_parent_map = {c["onec_id"]: c["parent__onec_id"] for c in db_categories if c["onec_id"]}

                # Инициализация Seed: прямые потомки якорной из БД
                for db_cat in db_categories:
                    if db_cat["parent__onec_id"] == anchor_id and db_cat["onec_id"]:
                        self._allowed_category_ids.add(db_cat["onec_id"])

                # Инициализация Seed: прямые потомки якорной из XML
                for cat in categories_data:
                    if cat.get("parent_id") == anchor_id:
                        cat_id = cat.get("id")
                        if cat_id:
                            self._allowed_category_ids.add(cat_id)

                # Expand из БД (если часть дерева уже импортирована)
                changed = True
                while changed:
                    changed = False
                    for cat_id, pid in db_parent_map.items():
                        if pid in self._allowed_category_ids and cat_id not in self._allowed_category_ids:
                            self._allowed_category_ids.add(cat_id)
                            changed = True

                # Expand из текущего XML
                changed = True
                while changed:
                    changed = False
                    for cat in categories_data:
                        pid = cat.get("parent_id")
                        cat_id = cat.get("id")
                        if (
                            pid
                            and pid in self._allowed_category_ids
                            and cat_id
                            and cat_id not in self._allowed_category_ids
                        ):
                            self._allowed_category_ids.add(cat_id)
                            changed = True

                logger.info(
                    f"Category filtering active: anchor='{root_category_name}' "
                    f"(id={anchor_id}), total_allowed={len(self._allowed_category_ids)}, "
                    f"root_ids={len(root_ids)}"
                )
            else:
                # ROOT_CATEGORY_NAME задан но не найден ни в XML, ни в БД
                logger.error(
                    f"ROOT_CATEGORY_NAME='{root_category_name}' не найден ни в XML, "
                    f"ни в БД. Импорт категорий из этого файла отменен."
                )
                result["root_not_found"] = True
                return result

        # ШАГ 1: Создаём/обновляем категории без parent
        for i, category_data in enumerate(categories_data):
            try:
                onec_id = category_data.get("id")
                name = category_data.get("name")
                description = category_data.get("description", "")

                if not onec_id or not name:
                    result["errors"] += 1
                    continue

                # Фильтрация: импортируем только якорь СПОРТ и его потомков
                if filtering_active:
                    if onec_id not in self._allowed_category_ids:
                        continue  # Пропускаем не-allowed (потомки других корневых)

                if (i + 1) % 50 == 0:
                    self.log_progress(f"Обработка категорий: {i + 1}...")

                # Если это якорная категория — проверяем наличие repair-якоря с sentinel onec_id.
                # Repair-команда создаёт якорь с onec_id=REPAIR_ANCHOR_ONEC_ID или без onec_id;
                # при следующем полном импорте обновляем его реальным onec_id вместо создания дубликата.
                # CR-5 #2: фильтруем sentinel/blank onec_id на уровне БД ДО .first(),
                # чтобы при наличии нескольких root СПОРТ не выбрать произвольный с чужим onec_id.
                if filtering_active and onec_id == anchor_id:
                    repair_anchor = (
                        Category.objects.filter(name=name, parent__isnull=True)
                        .exclude(onec_id=onec_id)
                        .filter(
                            models.Q(onec_id__isnull=True)
                            | models.Q(onec_id="")
                            | models.Q(onec_id=REPAIR_ANCHOR_ONEC_ID)
                        )
                        .order_by("pk")
                        .first()
                    )
                    if repair_anchor:
                        repair_anchor.onec_id = onec_id
                        repair_anchor.name = name
                        repair_anchor.is_active = True
                        if description:
                            repair_anchor.description = description
                        repair_anchor.save(update_fields=["onec_id", "name", "is_active", "description"])
                        category_map[onec_id] = repair_anchor
                        self._valid_category_onec_ids.add(onec_id)
                        result["updated"] += 1
                        logger.info(f"Repair-якорь '{name}' обновлён реальным onec_id={onec_id}")
                        continue

                category, created = Category.objects.update_or_create(
                    onec_id=onec_id,
                    defaults={
                        "name": name,
                        "description": description,
                        "is_active": True,
                    },
                )

                category_map[onec_id] = category
                self._valid_category_onec_ids.add(onec_id)

                if created:
                    result["created"] += 1
                else:
                    result["updated"] += 1

            except Exception as e:
                logger.error(f"Error processing category {category_data}: {e}")
                result["errors"] += 1

        # ======================================================================
        # Сбор «раскрытых» родителей: под ними в выгрузке перечислен хотя бы один
        # ребёнок. Только дети таких родителей попадут в зону деактивации
        # (см. deactivate_obsolete_categories). Множество накапливается между файлами
        # groups*.xml, поэтому здесь оно не сбрасывается.
        #
        # Считаем ребёнка только после ШАГ 1 и только если он реально записан
        # (есть в category_map). Иначе битая строка XML (без name) или упавшая запись
        # открыла бы зону деактивации для всей ветки родителя, а сама попала бы
        # в кандидаты на деактивацию — родитель «раскрыт», ребёнок «невалиден».
        # Присутствие в category_map также означает, что allowed-фильтр пройден.
        # ======================================================================
        for category_data in categories_data:
            parent_onec_id = category_data.get("parent_id")
            child_onec_id = category_data.get("id")
            if not parent_onec_id or not child_onec_id or child_onec_id not in category_map:
                continue
            # Тот же guard, что в ШАГ 2: чужой корень не считается раскрытым,
            # иначе его дети попадут в зону деактивации. Множество корней копится
            # между файлами: корень может быть объявлен в одном groups*.xml,
            # а его дети — в другом.
            if filtering_active and parent_onec_id in self._root_category_onec_ids and parent_onec_id != anchor_id:
                continue
            self._expanded_parent_onec_ids.add(parent_onec_id)

        # ШАГ 2: Устанавливаем родительские связи с валидацией циклов
        for category_data in categories_data:
            try:
                onec_id = category_data.get("id")
                parent_id = category_data.get("parent_id")

                if not parent_id or not onec_id:
                    continue  # Корневая категория или ошибка

                child_category: Category | None = category_map.get(onec_id)

                if not child_category:
                    continue

                # Фильтрация parent при активной фильтрации
                if filtering_active:
                    if parent_id in root_ids and parent_id != anchor_id:
                        # Parent = другая корневая → пропускаем
                        continue

                parent: Category | None = category_map.get(parent_id)

                if not parent:
                    continue

                # Валидация циклических ссылок
                if self._has_circular_reference(child_category, parent, category_map):
                    result["cycles_detected"] += 1
                    continue

                # Устанавливаем parent, включая полный путь СПОРТ -> child -> descendant
                child_category.parent = parent
                child_category.save(update_fields=["parent"])

            except Exception:
                result["errors"] += 1

        logger.info(
            f"Categories processed: {result['created']} created, "
            f"{result['updated']} updated, {result['errors']} errors, "
            f"{result['cycles_detected']} cycles detected"
            + (f", filtering={'active' if filtering_active else 'inactive'}" "")
        )
        return result

    def deactivate_obsolete_categories(self) -> None:
        """Деактивация устаревших категорий после обработки всех XML файлов.

        Витрину от схлопывания на частичной выгрузке 1С защищают два независимых барьера:

        1. Зона деактивации ограничена активными детьми «раскрытых» родителей — тех,
           под которыми в выгрузке пришёл хотя бы один прошедший allowed-фильтр ребёнок.
           Категории под нераскрытыми ветками не трогаются вовсе.
        2. Для каждого раскрытого родителя **отдельно**: если деактивация затронет больше
           MAX_CATEGORY_DEACTIVATION_RATIO его активных детей, чистка детей именно этого
           родителя отменяется с logger.error; под остальными родителями она проходит штатно.
           Порог не применяется к родителям, у которых меньше
           MIN_CHILDREN_FOR_DEACTIVATION_RATIO активных детей.

        Осознанный компромисс барьера 1: корневые категории (parent IS NULL) выпадают из
        зоны деактивации, хотя старый код их гасил. Витрину это не затрагивает
        (CategoryTreeViewSet отдаёт только детей якоря), но устаревший корень остаётся
        видимым в плоском /api/v1/categories/ — тот фильтрует только по is_active.
        """
        # Нечего сверять или ни одного раскрытого родителя — деактивировать нечего.
        if not self._valid_category_onec_ids or not self._expanded_parent_onec_ids:
            return

        from apps.products.models import Category

        skipped_candidates = 0
        skipped_parents: list[str] = []
        deactivated = 0

        with transaction.atomic():
            # Один запрос без N+1: активные дети всех раскрытых родителей.
            # Пустой onec_id исключаем наравне с NULL: в _valid_category_onec_ids
            # пустая строка не попадает никогда, иначе такая запись — вечный кандидат.
            rows = (
                Category.objects.filter(
                    is_active=True,
                    parent__onec_id__in=self._expanded_parent_onec_ids,
                )
                .exclude(onec_id__isnull=True)
                .exclude(onec_id="")
                .values_list("pk", "onec_id", "parent__onec_id", "parent__name")
            )

            by_parent: dict[str, list[tuple[int, str]]] = defaultdict(list)
            parent_names: dict[str, str] = {}
            for pk, onec_id, parent_onec_id, parent_name in rows:
                by_parent[parent_onec_id].append((pk, onec_id))
                parent_names[parent_onec_id] = parent_name

            to_deactivate: list[int] = []
            for parent_onec_id, kids in by_parent.items():
                doomed = [pk for pk, oid in kids if oid not in self._valid_category_onec_ids]
                if not doomed:
                    continue
                # Умножение вместо деления: доля 3/10 против порога 0.3 не должна
                # зависеть от округления double.
                over_threshold = len(doomed) > len(kids) * MAX_CATEGORY_DEACTIVATION_RATIO

                if len(kids) < MIN_CHILDREN_FOR_DEACTIVATION_RATIO:
                    # Порог не применяется — иначе штатное удаление 1 категории из 3
                    # блокировалось бы навсегда. Но крупную потерю в малой ветке
                    # всё равно фиксируем: гасить 2 из 3 молча недопустимо.
                    if over_threshold:
                        logger.warning(
                            "Малая ветка теряет большинство детей: родитель '%s' (onec_id=%s), "
                            "гасим %s из %s активных детей. Порог не применён — детей меньше %s.",
                            parent_names.get(parent_onec_id),
                            parent_onec_id,
                            len(doomed),
                            len(kids),
                            MIN_CHILDREN_FOR_DEACTIVATION_RATIO,
                        )
                    to_deactivate.extend(doomed)
                    continue

                if over_threshold:
                    logger.error(
                        "Деактивация категорий отменена для родителя '%s' (onec_id=%s): "
                        "кандидатов на деактивацию %s из %s активных детей — "
                        "превышен порог %s. Вероятна частичная выгрузка 1С.",
                        parent_names.get(parent_onec_id),
                        parent_onec_id,
                        len(doomed),
                        len(kids),
                        MAX_CATEGORY_DEACTIVATION_RATIO,
                    )
                    skipped_candidates += len(doomed)
                    skipped_parents.append(parent_onec_id)
                    continue
                to_deactivate.extend(doomed)

            if to_deactivate:
                # Обновляем по явному списку pk: parent__onec_id__in — это join, по нему
                # update() невозможен. QuerySet.update() намеренно не трогает auto_now-поле
                # updated_at — поведение сохраняем.
                deactivated = Category.objects.filter(pk__in=to_deactivate).update(is_active=False)

        if skipped_candidates:
            # Наблюдаемость: при фоновом Celery-импорте оператор видит только ImportSession.
            # stats доедет до report_details (finalize_session сохраняет их после деактивации),
            # log_progress пишет в report немедленно.
            self.stats["categories_deactivation_skipped"] = skipped_candidates
            self.log_progress(
                f"ВНИМАНИЕ: предохранитель отменил деактивацию категорий "
                f"у {len(skipped_parents)} родител(ей): не погашено {skipped_candidates} "
                f"категорий. Вероятна частичная выгрузка 1С."
            )

        logger.info(f"Deactivated {deactivated} obsolete categories.")

    def _has_circular_reference(
        self,
        category: Any,
        proposed_parent: Any,
        category_map: dict[str, Any],
    ) -> bool:
        """
        Проверка циклических ссылок в иерархии категорий

        Обходим родителей proposed_parent и проверяем что category
        не встречается в цепочке (Story 3.1.2)

        Args:
            category: Категория для проверки
            proposed_parent: Предлагаемый родитель
            category_map: Словарь onec_id -> Category

        Returns:
            True если обнаружен цикл, False иначе
        """
        visited: set[int] = set()
        current = proposed_parent

        while current:
            # Если мы вернулись к исходной категории - цикл обнаружен
            if current.pk == category.pk:
                return True

            # Защита от бесконечного цикла
            if current.pk in visited:
                return True

            visited.add(current.pk)

            # Переходим к parent
            current = current.parent

        return False

    def process_brands(self, brands_data: Sequence[BrandData]) -> dict[str, int]:
        """
        Обработка брендов из propertiesGoods.xml с дедупликацией по normalized_name

        Args:
            brands_data: Список брендов с полями id и name

        Returns:
            dict с количеством brands_created, mappings_created, mappings_updated
        """
        from apps.products.models import Brand, Brand1CMapping
        from apps.products.utils.brands import normalize_brand_name

        result = {
            "brands_created": 0,
            "mappings_created": 0,
            "mappings_updated": 0,
        }

        for i, brand_data in enumerate(brands_data):
            try:
                if (i + 1) % 50 == 0:
                    self.log_progress(f"Обработка брендов: {i + 1}...")

                onec_id = brand_data.get("id")
                onec_name = brand_data.get("name")

                if not onec_id or not onec_name:
                    logger.warning(f"Skipping brand with missing id or name: {brand_data}")
                    continue

                # Нормализуем название для поиска дубликатов
                normalized = normalize_brand_name(onec_name)

                # Проверяем существующий маппинг для этого onec_id
                existing_mapping = Brand1CMapping.objects.filter(onec_id=onec_id).first()

                if existing_mapping:
                    # Маппинг уже существует - обновляем onec_name если изменилось
                    if existing_mapping.onec_name != onec_name:
                        existing_mapping.onec_name = onec_name
                        existing_mapping.save(update_fields=["onec_name"])
                        result["mappings_updated"] += 1
                        logger.debug(
                            "Brand mapping updated",
                            extra={
                                "onec_id": onec_id,
                                "brand_id": existing_mapping.brand.id,
                                "operation": "update",
                                "import_session_id": self.session_id,
                            },
                        )
                    else:
                        result["mappings_updated"] += 1
                    continue

                # Ищем существующий бренд по normalized_name
                existing_brand = Brand.objects.filter(normalized_name=normalized).first()

                # Добавляем fallback-поиск бренда по name__iexact
                if not existing_brand:
                    existing_brand = Brand.objects.filter(name__iexact=onec_name).first()
                    if existing_brand:
                        self.stats["brand_fallbacks"] += 1
                        logger.info(f"Brand found via fallback: {onec_name}")

                if existing_brand:
                    # Бренд существует - создаём только маппинг (объединение дубликатов)
                    Brand1CMapping.objects.create(
                        brand=existing_brand,
                        onec_id=onec_id,
                        onec_name=onec_name,
                    )
                    result["mappings_created"] += 1

                    logger.info(
                        "Brand mapping created - duplicate merged",
                        extra={
                            "onec_id": onec_id,
                            "onec_name": onec_name,
                            "brand_id": existing_brand.id,
                            "brand_name": existing_brand.name,
                            "normalized_name": existing_brand.normalized_name,
                            "slug": existing_brand.slug,
                            "operation": "merge",
                            "import_session_id": self.session_id,
                        },
                    )
                else:
                    # Бренд не найден - создаём новый бренд + маппинг
                    # Генерируем уникальный slug
                    try:
                        from transliterate import translit

                        transliterated = translit(onec_name, "ru", reversed=True)
                        base_slug = slugify(transliterated)
                    except (RuntimeError, ImportError):
                        base_slug = slugify(onec_name)

                    if not base_slug:
                        base_slug = f"brand-{onec_id[:8]}"

                    # Обеспечиваем уникальность slug
                    unique_slug = base_slug
                    counter = 2
                    while Brand.objects.filter(slug=unique_slug).exists():
                        unique_slug = f"{base_slug}-{counter}"
                        counter += 1

                    # Создаём бренд (normalized_name установится автоматически в save())
                    brand = Brand.objects.create(
                        name=onec_name,
                        slug=unique_slug,
                        is_active=True,
                    )

                    # Создаём маппинг
                    Brand1CMapping.objects.create(
                        brand=brand,
                        onec_id=onec_id,
                        onec_name=onec_name,
                    )

                    result["brands_created"] += 1
                    result["mappings_created"] += 1

                    logger.info(
                        "Brand created with mapping",
                        extra={
                            "onec_id": onec_id,
                            "onec_name": onec_name,
                            "brand_id": brand.id,
                            "brand_name": brand.name,
                            "normalized_name": brand.normalized_name,
                            "slug": brand.slug,
                            "operation": "create",
                            "import_session_id": self.session_id,
                        },
                    )

            except Exception as e:
                logger.error(f"Error processing brand {brand_data}: {e}")
                self.stats["errors"] += 1

        logger.info(
            f"Brands processed: {result['brands_created']} brands created, "
            f"{result['mappings_created']} mappings created, "
            f"{result['mappings_updated']} mappings updated"
        )

        # Инвалидация кэша избранных брендов
        from django.core.cache import cache

        from apps.products.constants import FEATURED_BRANDS_CACHE_KEY

        cache.delete(FEATURED_BRANDS_CACHE_KEY)
        logger.info("Invalidated featured brands cache after import.")

        return result

    def log_progress(self, message: str) -> None:
        """
        Логирование прогресса в консоль и в поле report модели ImportSession.
        """
        from django.db.models import F, Value
        from django.db.models.functions import Concat

        from apps.products.models import ImportSession

        timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        full_message = f"[{timestamp}] {message}"
        logger.info(full_message)

        try:
            ImportSession.objects.filter(pk=self.session_id).update(
                report=Concat(F("report"), Value(full_message + "\n")),
                updated_at=timezone.now(),
            )
        except Exception as e:
            logger.error(f"Error updating session report: {e}")

    def finalize_session(self, status: str, error_message: str = "") -> None:
        """Завершение сессии импорта"""
        from apps.products.models import ImportSession

        # Перед финальным сохранением статуса применяем деактивацию
        if status == ImportSession.ImportStatus.COMPLETED or status == "completed":
            try:
                self.deactivate_obsolete_categories()
            except Exception as e:
                logger.error(f"Error during deactivate_obsolete_categories: {e}")

        try:
            session = ImportSession.objects.get(id=self.session_id)
            session.status = status
            session.finished_at = timezone.now()

            # Ensure Updated Items are saved in report_details
            # Limit to 100 to avoid huge JSONs
            self.stats.update(
                {
                    "updated_products_ids": self.updated_products[:100],
                    "updated_variants_ids": self.updated_variants[:100],
                }
            )
            if len(self.updated_products) > 100:
                self.stats["updated_products_ids"].append(f"...and {len(self.updated_products) - 100} more")
            if len(self.updated_variants) > 100:
                self.stats["updated_variants_ids"].append(f"...and {len(self.updated_variants) - 100} more")

            session.report_details = self.stats

            timestamp = timezone.now().strftime("%Y-%m-%d %H:%M:%S")
            status_display = dict(ImportSession.ImportStatus.choices).get(status, status)
            completion_message = f"[{timestamp}] Импорт завершен со статусом: {status_display}\n"

            # CAP-7 в части изображений: числа обязаны быть видны в тексте
            # отчёта, а не только в JSONB `report_details`.
            images_line = self.image_report_line()
            if images_line:
                completion_message += f"[{timestamp}] {images_line}\n"
            if error_message:
                completion_message += f"[{timestamp}] Ошибка: {error_message}\n"
                session.error_message = error_message

            session.report = (session.report or "") + completion_message
            session.save()

            logger.info(f"Import session {self.session_id} finalized with status: {status}")
            logger.info(f"Import stats: {self.stats}")

        except ImportSession.DoesNotExist:
            logger.error(f"ImportSession {self.session_id} not found")

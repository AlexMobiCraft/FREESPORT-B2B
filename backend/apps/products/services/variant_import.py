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
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING, Any, Sequence, TypedDict

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.db import models, transaction
from django.utils import timezone
from django.utils.text import slugify

if TYPE_CHECKING:
    from apps.products.models import Product, ProductVariant

logger = logging.getLogger("import_products")


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
        self.session_id = session_id
        self.batch_size = batch_size
        self.skip_validation = skip_validation

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
            "images_copied": 0,
            "images_skipped": 0,
            "images_errors": 0,
            "attributes_linked": 0,
            "attributes_missing": 0,
            # Story 27.1: Keys for migrated methods
            "brand_fallbacks": 0,
            "attributes_missing_mapping": 0,
        }

        # Story 13.2+ Debugging: Track specific updated items
        self.updated_products: list[str] = []
        self.updated_variants: list[str] = []

        # Кэш для оптимизации поиска
        self._product_cache: dict[str, Any] = {}
        self._variant_cache: dict[str, Any] = {}
        self._stock_buffer: dict[str, int] = {}
        self._missing_products_logged: set[str] = set()
        self._missing_variants_logged: set[str] = set()

    # ========================================================================
    # Helper methods
    # ========================================================================

    # Минимальный размер изображения в байтах (100KB)
    MIN_IMAGE_SIZE_BYTES = 100 * 1024

    def _save_image_if_not_exists(
        self,
        source_path: Path,
        image_path: str,
        destination_prefix: str,
    ) -> str | None:
        """
        Helper метод для сохранения изображения если оно еще не существует

        Args:
            source_path: Путь к исходному файлу изображения
            image_path: Относительный путь изображения из XML
            destination_prefix: Префикс директории назначения ('base' или 'variants')

        Returns:
            Путь к сохраненному файлу или None если файл не найден/ошибка/слишком мал
        """
        from django.conf import settings
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        if not source_path.exists():
            logger.warning(f"Image not found: {source_path}")
            self.stats["images_errors"] += 1
            return None

        # Проверка минимального размера файла (100KB)
        file_size = source_path.stat().st_size
        if file_size < self.MIN_IMAGE_SIZE_BYTES:
            size_kb = file_size / 1024
            logger.debug(
                f"Image too small, skipping: {source_path} "
                f"({size_kb:.1f}KB < {self.MIN_IMAGE_SIZE_BYTES // 1024}KB)"
            )
            self.stats["images_skipped"] += 1
            return None

        # Сохранение структуры директорий
        filename = source_path.name
        subdir = image_path.split("/")[0] if "/" in image_path else ""
        destination_path = (
            f"products/{destination_prefix}/{subdir}/{filename}"
            if subdir
            else f"products/{destination_prefix}/{filename}"
        )

        # Проверка существования
        if default_storage.exists(destination_path):
            self.stats["images_skipped"] += 1
            return destination_path

        # Создание директории
        if subdir:
            subdir_path = os.path.join(settings.MEDIA_ROOT, "products", destination_prefix, subdir)
            os.makedirs(subdir_path, exist_ok=True)

        # Копирование файла
        try:
            with open(source_path, "rb") as f:
                saved_path = default_storage.save(destination_path, ContentFile(f.read()))
            self.stats["images_copied"] += 1
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

        if fields_to_update:
            product.save(update_fields=fields_to_update)

        # Импорт изображений в base_images (Hybrid подход)
        if not skip_images and base_dir and "images" in goods_data:
            self._import_base_images(product, goods_data["images"], base_dir)

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
            is_active=False,  # Активируется после создания variants
            sync_status=Product.SyncStatus.PENDING,
            base_images=[],  # Будет заполнено при импорте изображений
        )

        try:
            product.save()
            logger.info(f"Product created: {product.onec_id}")
            self.stats["products_created"] += 1

            # Импорт изображений в base_images (Hybrid подход)
            if not skip_images and base_dir and "images" in goods_data:
                self._import_base_images(product, goods_data["images"], base_dir)

            return product

        except Exception as e:
            self._log_error(f"Error saving product: {e}", goods_data)
            return None

    def _import_base_images(
        self,
        product: Any,
        image_paths: list[str],
        base_dir: str,
    ) -> None:
        """
        Импорт изображений в Product.base_images (Hybrid подход AC6)

        Args:
            product: Product instance
            image_paths: Список путей к изображениям из goods.xml
            base_dir: Базовая директория импорта
        """
        if not image_paths:
            return

        # Дедупликация существующих base_images по filename (исправление бага дублей)
        existing_images = product.base_images or []
        seen_filenames: set[str] = set()
        base_images: list[str] = []

        for img_path in existing_images:
            filename = Path(img_path).name if img_path else ""
            if filename and filename not in seen_filenames:
                base_images.append(img_path)
                seen_filenames.add(filename)

        seen_paths: set[str] = set(base_images)

        for image_path in image_paths:
            try:
                # Нормализация пути (убираем import_files/ если есть)
                normalized_path = normalize_image_path(image_path)
                source_path = Path(base_dir) / normalized_path
                saved_path = self._save_image_if_not_exists(source_path, normalized_path, "base")

                if saved_path:
                    saved_filename = Path(saved_path).name
                    # Проверяем и по пути, и по filename
                    if saved_filename in seen_filenames:
                        continue
                    if saved_path not in seen_paths:
                        base_images.append(saved_path)
                        seen_paths.add(saved_path)
                        seen_filenames.add(saved_filename)

            except Exception as e:
                logger.error(f"Error copying image {image_path}: {e}")
                self.stats["images_errors"] += 1

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

            # Проверка существующего варианта
            existing_variant = ProductVariant.objects.filter(onec_id=onec_id).first()
            if existing_variant:
                return self._update_existing_variant(existing_variant, offer_data, base_dir, skip_images)

            # Создание нового варианта
            return self._create_new_variant(product, onec_id, offer_data, base_dir, skip_images)

        except Exception as e:
            self._log_error(f"Error processing variant from offer: {e}", offer_data)
            return None

    def _update_existing_variant(
        self,
        variant: Any,
        offer_data: dict[str, Any],
        base_dir: str | None,
        skip_images: bool,
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
        if not parsed_chars["size_value"]:
            parsed_chars["size_value"] = extract_size_from_name(name)

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

        if fields_to_update:
            variant.save(update_fields=fields_to_update)

        # Импорт изображений варианта (AC6)
        if not skip_images and base_dir:
            images = offer_data.get("images", [])
            if images:
                self._import_variant_images(variant, images, base_dir)

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
        if not parsed_chars["size_value"]:
            parsed_chars["size_value"] = extract_size_from_name(name)

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
            trainer_price=None,
            federation_price=None,
            stock_quantity=0,  # Будет обновлен из rests.xml
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

            # Импорт изображений варианта (AC6)
            if not skip_images and base_dir:
                images = offer_data.get("images", [])
                if images:
                    self._import_variant_images(variant, images, base_dir)

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
    ) -> None:
        """
        Импорт изображений в ProductVariant (AC6 - Hybrid подход)

        Первое изображение → main_image
        Остальные → gallery_images
        """
        if not image_paths:
            return

        main_image_set = bool(variant.main_image)

        # Дедупликация существующих gallery_images по filename (исправление бага дублей)
        existing_gallery = variant.gallery_images or []
        seen_filenames: set[str] = set()
        gallery_images: list[str] = []

        # Добавляем main_image filename в seen_filenames
        if variant.main_image:
            main_filename = Path(variant.main_image).name
            if main_filename:
                seen_filenames.add(main_filename)

        for img_path in existing_gallery:
            filename = Path(img_path).name if img_path else ""
            if filename and filename not in seen_filenames:
                gallery_images.append(img_path)
                seen_filenames.add(filename)

        seen_paths: set[str] = set(gallery_images)

        for image_path in image_paths:
            try:
                # Нормализация пути (убираем import_files/ если есть)
                normalized_path = normalize_image_path(image_path)
                source_path = Path(base_dir) / normalized_path
                saved_path = self._save_image_if_not_exists(source_path, normalized_path, "variants")

                if saved_path:
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

            except Exception as e:
                logger.error(f"Error copying variant image {image_path}: {e}")
                self.stats["images_errors"] += 1

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
                trainer_price=None,
                federation_price=None,
                stock_quantity=0,
            )
            default_variants.append(variant)

            logger.info(
                f"Creating default variant for product: {product.name} " f"(onec_id={product.onec_id}, sku={sku})"
            )

            # Batch processing (NFR4)
            if len(default_variants) >= self.batch_size:
                with transaction.atomic():
                    ProductVariant.objects.bulk_create(default_variants, ignore_conflicts=True)
                batch_count += len(default_variants)
                logger.info(f"Processed {batch_count} default variants")
                default_variants = []

        # Сохранение оставшихся
        if default_variants:
            with transaction.atomic():
                ProductVariant.objects.bulk_create(default_variants, ignore_conflicts=True)
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
                    price_updates[field_name] = price_value

            # Story 3.1.4: Auto-populate RRP from Retail Price if not provided
            # This ensures B2B users always have a baseline for comparison
            if "retail_price" in price_updates and "rrp" not in price_updates:
                price_updates["rrp"] = price_updates["retail_price"]

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

            # Суммируем остатки если товар на разных складах
            total_quantity = self._stock_buffer.get(onec_id, 0) + quantity
            self._stock_buffer[onec_id] = total_quantity

            variant.stock_quantity = total_quantity
            variant.last_sync_at = timezone.now()
            variant.save(update_fields=["stock_quantity", "last_sync_at"])

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
        """Получает или создаёт категорию"""
        from apps.products.models import Category

        category_id = goods_data.get("category_id")

        if category_id:
            category = Category.objects.filter(onec_id=category_id).first()
            if category:
                return category

            # Создаём placeholder категорию
            category_name = goods_data.get("category_name", f"Категория {category_id}")
            slug = slugify(category_name) or f"category-{uuid.uuid4().hex[:8]}"

            # Обеспечиваем уникальность slug
            if Category.objects.filter(slug=slug).exists():
                slug = f"{slug}-{uuid.uuid4().hex[:8]}"

            category, _ = Category.objects.get_or_create(
                onec_id=category_id,
                defaults={
                    "name": category_name,
                    "slug": slug,
                    "is_active": True,
                },
            )
            return category

        # Fallback категория
        category, _ = Category.objects.get_or_create(
            slug="uncategorized",
            defaults={"name": "Без категории", "is_active": True},
        )
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

        Args:
            price_types_data: Последовательность PriceTypeData

        Returns:
            Количество обработанных типов цен
        """
        from apps.products.models import PriceType

        count = 0
        for price_type_data in price_types_data:
            try:
                PriceType.objects.update_or_create(
                    onec_id=price_type_data["onec_id"],
                    defaults={
                        "onec_name": price_type_data["onec_name"],
                        "product_field": price_type_data["product_field"],
                        "is_active": True,
                    },
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

        Args:
            categories_data: Список данных категорий с полями
                             id, name, description, parent_id

        Returns:
            dict с количеством created, updated, errors, cycles_detected
        """
        from apps.products.models import Category

        result = {
            "created": 0,
            "updated": 0,
            "errors": 0,
            "cycles_detected": 0,
        }
        category_map: dict[str, Category] = {}

        # ШАГ 1: Создаём/обновляем все категории без parent
        for i, category_data in enumerate(categories_data):
            try:
                onec_id = category_data.get("id")
                name = category_data.get("name")
                description = category_data.get("description", "")

                if not onec_id or not name:
                    result["errors"] += 1
                    continue

                if (i + 1) % 50 == 0:
                    self.log_progress(f"Обработка категорий: {i + 1}...")

                category, created = Category.objects.update_or_create(
                    onec_id=onec_id,
                    defaults={
                        "name": name,
                        "description": description,
                        "is_active": True,
                    },
                )

                category_map[onec_id] = category

                if created:
                    result["created"] += 1
                else:
                    result["updated"] += 1

            except Exception as e:
                logger.error(f"Error processing category {category_data}: {e}")
                result["errors"] += 1

        # ШАГ 2: Устанавливаем родительские связи с валидацией циклов
        for category_data in categories_data:
            try:
                onec_id = category_data.get("id")
                parent_id = category_data.get("parent_id")

                if not parent_id or not onec_id:
                    continue  # Корневая категория или ошибка

                child_category: Category | None = category_map.get(onec_id)
                parent: Category | None = category_map.get(parent_id)

                if not child_category:
                    continue

                if not parent:
                    continue

                # Валидация циклических ссылок
                if self._has_circular_reference(child_category, parent, category_map):
                    result["cycles_detected"] += 1
                    continue

                # Устанавливаем parent
                child_category.parent = parent
                child_category.save(update_fields=["parent"])

            except Exception:
                result["errors"] += 1

        logger.info(
            f"Categories processed: {result['created']} created, "
            f"{result['updated']} updated, {result['errors']} errors, "
            f"{result['cycles_detected']} cycles detected"
        )
        return result

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
            if error_message:
                completion_message += f"[{timestamp}] Ошибка: {error_message}\n"
                session.error_message = error_message

            session.report = (session.report or "") + completion_message
            session.save()

            logger.info(f"Import session {self.session_id} finalized with status: {status}")
            logger.info(f"Import stats: {self.stats}")

        except ImportSession.DoesNotExist:
            logger.error(f"ImportSession {self.session_id} not found")

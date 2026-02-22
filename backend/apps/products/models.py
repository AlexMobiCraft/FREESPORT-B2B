"""
Модели продуктов для платформы FREESPORT
Включает товары, категории, бренды с роле-ориентированным ценообразованием
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils.text import slugify
from transliterate import translit

from apps.products.utils.attributes import normalize_attribute_name
from apps.products.utils.brands import normalize_brand_name

if TYPE_CHECKING:
    from apps.users.models import User


class BrandManager(models.Manager["Brand"]):
    """Кастомный менеджер для модели Brand."""

    def active(self) -> models.QuerySet["Brand"]:
        """Возвращает только активные бренды."""
        return self.filter(is_active=True)


class Brand(models.Model):
    """
    Модель бренда товаров
    """

    name = cast(str, models.CharField("Название бренда", max_length=100, unique=False))
    slug = cast(str, models.SlugField("Slug", max_length=255, unique=True))
    normalized_name = cast(
        str,
        models.CharField(
            "Нормализованное название",
            max_length=100,
            unique=True,
            blank=False,
            null=False,
            db_index=True,
            help_text="Нормализованное название для дедупликации брендов",
        ),
    )
    image = cast(models.ImageField, models.ImageField("Изображение", upload_to="brands/", blank=True))
    is_featured = cast(bool, models.BooleanField("Показывать на главной", default=False, db_index=True))
    description = cast(str, models.TextField("Описание", blank=True))
    website = cast(str, models.URLField("Веб-сайт", blank=True))
    is_active = cast(bool, models.BooleanField("Активный", default=True, db_index=True))

    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    objects = BrandManager()

    class Meta:
        verbose_name = "Бренд"
        verbose_name_plural = "Бренды"
        db_table = "brands"

    def clean(self) -> None:
        super().clean()
        errors: dict[str, str] = {}

        if self.is_featured and not self.image:
            errors["image"] = "Image is required for featured brands"

        # Проверка уникальности normalized_name до save(), чтобы вернуть
        # ValidationError вместо IntegrityError (500)
        if self.name:
            computed_normalized = normalize_brand_name(self.name)
            qs = Brand.objects.filter(normalized_name=computed_normalized)
            if self.pk:
                qs = qs.exclude(pk=self.pk)
            if qs.exists():
                errors["name"] = f"Brand with similar name already exists " f"(normalized: '{computed_normalized}')"

        if errors:
            raise ValidationError(errors)

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Вычисляем normalized_name при сохранении
        self.normalized_name = normalize_brand_name(self.name) if self.name else ""

        if not self.slug:
            try:
                # Транслитерация кириллицы в латиницу, затем slugify
                transliterated = translit(self.name, "ru", reversed=True)
                base_slug = slugify(transliterated)
            except RuntimeError:
                # Fallback на обычный slugify
                base_slug = slugify(self.name)

            # Если slug все еще пустой, создаем fallback
            if not base_slug:
                base_slug = f"brand-{self.pk or 0}"

            # Обеспечиваем уникальность slug
            self.slug = base_slug
            counter = 1
            while Brand.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                self.slug = f"{base_slug}-{counter}"
                counter += 1
                if counter > 100:
                    self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
                    break

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return str(self.name)


class Brand1CMapping(models.Model):
    """
    Маппинг брендов из 1С на master-бренды в системе.
    Позволяет связывать несколько ID из 1С с одним брендом.
    """

    brand = cast(
        Brand,
        models.ForeignKey(
            Brand,
            on_delete=models.CASCADE,
            related_name="onec_mappings",
            verbose_name="Бренд",
            help_text="Master-бренд в системе",
        ),
    )
    onec_id = cast(
        str,
        models.CharField(
            "ID в 1С",
            max_length=100,
            unique=True,
            db_index=True,
            help_text="Уникальный идентификатор бренда из 1С",
        ),
    )
    onec_name = cast(
        str,
        models.CharField(
            "Название в 1С",
            max_length=100,
            help_text="Оригинальное название бренда из 1С",
        ),
    )
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))

    class Meta:
        verbose_name = "Маппинг бренда 1С"
        verbose_name_plural = "Маппинги брендов 1С"
        db_table = "products_brand_1c_mapping"

    def __str__(self) -> str:
        return f"{self.onec_name} ({self.onec_id}) -> {self.brand}"


class Category(models.Model):
    """
    Модель категорий товаров с поддержкой иерархии
    """

    name = cast(str, models.CharField("Название", max_length=200))
    slug = cast(str, models.SlugField("Slug", max_length=255, unique=True))
    parent = cast(
        "Category | None",
        models.ForeignKey(
            "self",
            on_delete=models.CASCADE,
            null=True,
            blank=True,
            related_name="children",
            verbose_name="Родительская категория",
        ),
    )
    description = cast(str, models.TextField("Описание", blank=True))
    image = cast(
        models.ImageField,
        models.ImageField("Изображение", upload_to="categories/", blank=True),
    )
    is_active = cast(bool, models.BooleanField("Активная", default=True))
    sort_order = cast(int, models.PositiveIntegerField("Порядок сортировки", default=0))

    # SEO поля
    seo_title = cast(str, models.CharField("SEO заголовок", max_length=200, blank=True))
    seo_description = cast(str, models.TextField("SEO описание", blank=True))

    # Интеграция с 1С
    onec_id = cast(
        str,
        models.CharField(
            "ID в 1С",
            max_length=100,
            unique=True,
            null=True,
            blank=True,
            db_index=True,
            help_text="Уникальный идентификатор категории из 1С",
        ),
    )

    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Категория"
        verbose_name_plural = "Категории"
        db_table = "categories"
        ordering = ["sort_order", "name"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            try:
                # Транслитерация кириллицы в латиницу, затем slugify
                transliterated = translit(self.name, "ru", reversed=True)
                self.slug = slugify(transliterated)
            except RuntimeError:
                # Fallback на обычный slugify
                self.slug = slugify(self.name)

            # Если slug все еще пустой, создаем fallback
            if not self.slug:
                self.slug = f"category-{self.pk or 0}"
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.full_name

    @property
    def full_name(self) -> str:
        """Полное название категории с учетом иерархии"""
        parent = self.parent
        if parent:
            return f"{parent.full_name} > {self.name}"
        return self.name


class HomepageCategory(Category):
    """
    Proxy модель для управления категориями на главной странице.
    Использует ту же таблицу, что и Category, но с отдельным разделом в админке.
    """

    class Meta:
        proxy = True
        verbose_name = "Категория для главной"
        verbose_name_plural = "Категории для главной"
        ordering = ["sort_order", "id"]


class Product(models.Model):
    """
    Модель товара с роле-ориентированным ценообразованием
    """

    name = cast(str, models.CharField("Название", max_length=300))
    slug = cast(str, models.SlugField("Slug", max_length=255, unique=True))
    brand = cast(
        Brand,
        models.ForeignKey(
            Brand,
            on_delete=models.CASCADE,
            related_name="products",
            verbose_name="Бренд",
        ),
    )
    category = cast(
        Category,
        models.ForeignKey(
            Category,
            on_delete=models.CASCADE,
            related_name="products",
            verbose_name="Категория",
        ),
    )
    description = cast(str, models.TextField("Описание"))
    short_description = cast(str, models.CharField("Краткое описание", max_length=500, blank=True))
    specifications = cast(dict, models.JSONField("Технические характеристики", default=dict, blank=True))

    # Изображения (Hybrid подход)
    # Структура: ['url1.jpg', 'url2.jpg', ...] - список URL изображений из 1С
    # Используется как fallback в ProductVariant.effective_images()
    base_images = cast(
        list,
        models.JSONField(
            "Базовые изображения",
            default=list,
            blank=True,
            help_text=("Общие изображения товара из 1С " "(используются как fallback для вариантов)"),
        ),
    )

    # SEO и мета информация
    seo_title = cast(str, models.CharField("SEO заголовок", max_length=200, blank=True))
    seo_description = cast(str, models.TextField("SEO описание", blank=True))

    # Флаги
    is_active = cast(bool, models.BooleanField("Активный", default=True))
    is_featured = cast(bool, models.BooleanField("Рекомендуемый", default=False))

    # Маркетинговые флаги для бейджей (Story 11.0)
    is_hit = cast(
        bool,
        models.BooleanField(
            "Хит продаж",
            default=False,
            db_index=True,
            help_text="Отображать бейдж 'Хит продаж' на карточке товара",
        ),
    )
    is_new = cast(
        bool,
        models.BooleanField(
            "Новинка",
            default=False,
            db_index=True,
            help_text="Отображать бейдж 'Новинка' на карточке товара",
        ),
    )
    is_sale = cast(
        bool,
        models.BooleanField(
            "Распродажа",
            default=False,
            db_index=True,
            help_text="Товар участвует в распродаже",
        ),
    )
    is_promo = cast(
        bool,
        models.BooleanField(
            "Акция",
            default=False,
            db_index=True,
            help_text="Товар участвует в акции/промо",
        ),
    )
    is_premium = cast(
        bool,
        models.BooleanField(
            "Премиум",
            default=False,
            db_index=True,
            help_text="Премиум товар (эксклюзив, лимитированная серия)",
        ),
    )
    discount_percent = cast(
        int | None,
        models.PositiveSmallIntegerField(
            "Процент скидки",
            null=True,
            blank=True,
            validators=[MaxValueValidator(100)],
            help_text="Процент скидки для отображения на бейдже (0-100)",
        ),
    )

    min_order_quantity = cast(
        int,
        models.PositiveIntegerField(
            "Минимальное количество заказа",
            default=1,
            help_text="Минимальное количество товара для заказа (для B2B)",
        ),
    )

    # Временные метки и интеграция с 1С
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    # 1С Integration fields (Story 3.1.1 AC: 3)
    class SyncStatus(models.TextChoices):
        PENDING = "pending", "Ожидает синхронизации"
        IN_PROGRESS = "in_progress", "Синхронизация"
        COMPLETED = "completed", "Синхронизировано"
        FAILED = "failed", "Ошибка"

    onec_id = cast(
        str | None,
        models.CharField(
            "ID товара в 1С (SKU)",
            max_length=100,
            unique=True,
            blank=True,
            null=True,
            db_index=True,
            help_text="Составной ID из offers.xml: parent_id#sku_id",
        ),
    )
    parent_onec_id = cast(
        str | None,
        models.CharField(
            "ID родительского товара в 1С",
            max_length=100,
            blank=True,
            null=True,
            db_index=True,
            help_text="ID базового товара из goods.xml",
        ),
    )
    onec_brand_id = cast(
        str | None,
        models.CharField(
            "ID бренда в 1С",
            max_length=100,
            null=True,
            blank=True,
            db_index=True,
            help_text=("Исходный идентификатор бренда из CommerceML " "для обратной синхронизации"),
        ),
    )
    sync_status = cast(
        str,
        models.CharField(
            "Статус синхронизации",
            max_length=20,
            choices=SyncStatus.choices,
            default=SyncStatus.PENDING,
            db_index=True,
        ),
    )
    last_sync_at = cast(
        datetime | None,
        models.DateTimeField("Последняя синхронизация", null=True, blank=True),
    )
    error_message = cast(str, models.TextField("Сообщение об ошибке", blank=True))

    # Many-to-Many relationship with AttributeValue
    attributes: models.ManyToManyField = models.ManyToManyField(
        "AttributeValue",
        blank=True,
        related_name="products",
        verbose_name="Атрибуты",
        help_text="Атрибуты товара (цвет, материал, размер и т.д.)",
    )

    class Meta:
        verbose_name = "Товар"
        verbose_name_plural = "Товары"
        db_table = "products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["is_active", "category"]),
            models.Index(fields=["brand", "is_active"]),
            models.Index(fields=["onec_id"]),  # 1С integration index
            models.Index(fields=["parent_onec_id"]),  # Parent 1C ID index
            models.Index(fields=["sync_status"]),  # Sync status index
            # Story 11.0: Composite indexes для маркетинговых флагов (PERF-001)
            models.Index(fields=["is_hit", "is_active"]),
            models.Index(fields=["is_new", "is_active"]),
            models.Index(fields=["is_sale", "is_active"]),
            models.Index(fields=["is_promo", "is_active"]),
            models.Index(fields=["is_premium", "is_active"]),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        if not self.slug:
            try:
                # Транслитерация кириллицы в латиницу, затем slugify
                transliterated = translit(self.name, "ru", reversed=True)
                base_slug = slugify(transliterated)
            except RuntimeError:
                # Fallback на обычный slugify
                base_slug = slugify(self.name)

            # Если slug все еще пустой, создаем fallback
            if not base_slug:
                base_slug = f"product-{self.pk or 0}"

            # Обеспечиваем уникальность slug
            self.slug = base_slug
            counter = 1
            while Product.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                # Добавляем UUID-суффикс для уникальности
                self.slug = f"{base_slug}-{uuid.uuid4().hex[:8]}"
                counter += 1
                # Защита от бесконечного цикла (маловероятно с UUID)
                if counter > 10:
                    self.slug = f"{base_slug}-{uuid.uuid4().hex}"
                    break

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ProductImage(models.Model):
    """
    Модель изображений товара
    """

    product = cast(
        Product,
        models.ForeignKey(
            Product,
            on_delete=models.CASCADE,
            related_name="images",
            verbose_name="Товар",
        ),
    )
    objects = models.Manager()
    image = cast(
        models.ImageField,
        models.ImageField("Изображение", upload_to="products/gallery/"),
    )
    alt_text = cast(str, models.CharField("Альтернативный текст", max_length=255, blank=True))
    is_main = cast(bool, models.BooleanField("Основное изображение", default=False))
    sort_order = cast(int, models.PositiveIntegerField("Порядок сортировки", default=0))

    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Изображение товара"
        verbose_name_plural = "Изображения товаров"
        db_table = "product_images"
        ordering = ["sort_order", "created_at"]
        indexes = [
            models.Index(fields=["product", "is_main"]),
            models.Index(fields=["sort_order"]),
        ]

    def __str__(self) -> str:
        image_type = "основное" if self.is_main else "дополнительное"
        return f"Изображение {self.product.name} ({image_type})"

    def save(self, *args: Any, **kwargs: Any) -> None:
        # Если это основное изображение, убираем флаг у других изображений этого товара
        if self.is_main:
            ProductImage.objects.filter(product=self.product, is_main=True).exclude(pk=self.pk).update(is_main=False)
        super().save(*args, **kwargs)


class ImportType(models.TextChoices):
    CATALOG = "catalog", "Каталог товаров"
    VARIANTS = "variants", "Варианты товаров"
    ATTRIBUTES = "attributes", "Атрибуты (справочники)"
    IMAGES = "images", "Изображения товаров"
    STOCKS = "stocks", "Остатки товаров"
    PRICES = "prices", "Цены товаров"
    CUSTOMERS = "customers", "Клиенты"


class ImportStatus(models.TextChoices):
    PENDING = "pending", "В очереди"
    STARTED = "started", "Начато"
    IN_PROGRESS = "in_progress", "В процессе"
    COMPLETED = "completed", "Завершено"
    FAILED = "failed", "Ошибка"


class ImportSession(models.Model):
    """
    Модель для отслеживания сессий импорта данных из 1С
    """

    ImportType = ImportType
    ImportStatus = ImportStatus

    import_type = cast(
        str,
        models.CharField(
            "Тип импорта",
            max_length=20,
            choices=ImportType.choices,
            default=ImportType.CATALOG,
        ),
    )
    status = cast(
        str,
        models.CharField(
            "Статус",
            max_length=20,
            choices=ImportStatus.choices,
            default=ImportStatus.PENDING,
        ),
    )
    session_key = cast(
        str | None,
        models.CharField(
            "Ключ сессии (SESSID)",
            max_length=40,
            db_index=True,
            blank=True,
            null=True,
            help_text="ID сессии из URL (sessid) для отслеживания транзакции",
        ),
    )
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    started_at = cast(datetime, models.DateTimeField("Начало импорта", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))
    finished_at = cast(
        datetime | None,
        models.DateTimeField("Окончание импорта", null=True, blank=True),
    )
    report = cast(
        str,
        models.TextField(
            "Отчет",
            blank=True,
            help_text="Текстовый лог/отчет о выполнении",
        ),
    )
    report_details = cast(
        dict,
        models.JSONField(
            "Детали отчета",
            default=dict,
            blank=True,
            help_text="Статистика: created, updated, skipped, errors",
        ),
    )
    error_message = cast(str, models.TextField("Сообщение об ошибке", blank=True))
    celery_task_id = cast(
        str | None,
        models.CharField(
            "ID задачи Celery",
            max_length=255,
            null=True,
            blank=True,
            db_index=True,
            help_text="UUID задачи Celery для отслеживания прогресса",
        ),
    )

    class Meta:
        verbose_name = "Сессия импорта"
        verbose_name_plural = "Сессии импорта"
        db_table = "import_sessions"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["import_type", "status"]),
            models.Index(fields=["-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=models.Q(
                    status__in=[
                        ImportStatus.PENDING,
                        ImportStatus.STARTED,
                        ImportStatus.IN_PROGRESS,
                    ]
                ),
                name="unique_active_session_key",
            )
        ]

    if TYPE_CHECKING:

        def get_import_type_display(self) -> str:
            """Заглушка для метода Django, возвращающего название типа импорта."""
            return ""

        def get_status_display(self) -> str:
            """Заглушка для метода Django, возвращающего название статуса."""
            return ""

    def __str__(self) -> str:
        return f"{self.get_import_type_display()} - " f"{self.get_status_display()} ({self.created_at})"


class PriceType(models.Model):
    """
    Справочник типов цен из 1С для маппинга на поля Product
    """

    onec_id = cast(
        str,
        models.CharField(
            "UUID типа цены в 1С",
            max_length=100,
            unique=True,
            help_text="UUID из priceLists.xml",
        ),
    )
    onec_name = cast(
        str,
        models.CharField(
            "Название в 1С",
            max_length=200,
            help_text='Например: "Опт 1 (300-600 тыс.руб в квартал)"',
        ),
    )
    product_field = cast(
        str,
        models.CharField(
            "Поле в модели Product",
            max_length=50,
            choices=[
                ("retail_price", "Розничная цена"),
                ("opt1_price", "Оптовая цена уровень 1"),
                ("opt2_price", "Оптовая цена уровень 2"),
                ("opt3_price", "Оптовая цена уровень 3"),
                ("trainer_price", "Цена для тренера"),
                ("federation_price", "Цена для представителя федерации"),
                (
                    "rrp",
                    "Рекомендованная розничная цена",
                ),
                (
                    "msrp",
                    "Максимальная рекомендованная цена",
                ),
            ],
            help_text="Поле Product, в которое мапится эта цена",
        ),
    )
    user_role = cast(
        str,
        models.CharField(
            "Роль пользователя",
            max_length=50,
            blank=True,
            help_text="Роль пользователя, для которой применяется эта цена",
        ),
    )
    is_active = cast(bool, models.BooleanField("Активный", default=True))
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))

    class Meta:
        verbose_name = "Тип цены"
        verbose_name_plural = "Типы цен"
        db_table = "price_types"
        ordering = ["onec_name"]

    def __str__(self) -> str:
        return f"{self.onec_name} → {self.product_field}"


class ColorMapping(models.Model):
    """
    Маппинг цветов на hex-коды для визуализации вариантов товаров
    """

    name = cast(
        str,
        models.CharField(
            "Название цвета",
            max_length=100,
            unique=True,
            help_text="Название цвета из 1С",
        ),
    )
    hex_code = cast(
        str,
        models.CharField(
            "Hex-код",
            max_length=7,
            help_text="Hex-код цвета (например: #FF0000)",
        ),
    )
    swatch_image = cast(
        models.ImageField,
        models.ImageField(
            "Изображение свотча",
            upload_to="colors/",
            blank=True,
            help_text="Для градиентов и паттернов",
        ),
    )

    class Meta:
        verbose_name = "Маппинг цвета"
        verbose_name_plural = "Маппинг цветов"
        db_table = "color_mappings"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.hex_code})"


class ProductVariant(models.Model):
    """
    SKU-вариант товара с ценами, остатками и характеристиками
    Hybrid подход: собственные изображения варианта с fallback на Product.base_images
    """

    # Foreign Key
    product = cast(
        Product,
        models.ForeignKey(
            Product,
            on_delete=models.CASCADE,
            related_name="variants",
            verbose_name="Товар",
        ),
    )

    # Идентификация
    sku = cast(
        str,
        models.CharField(
            "Артикул SKU",
            max_length=100,
            unique=True,
            db_index=True,
            help_text="Уникальный артикул варианта",
        ),
    )
    onec_id = cast(
        str,
        models.CharField(
            "ID в 1С",
            max_length=100,
            unique=True,
            db_index=True,
            help_text="Составной ID: parent_id#variant_id",
        ),
    )

    # Характеристики
    color_name = cast(
        str,
        models.CharField(
            "Цвет",
            max_length=100,
            blank=True,
            db_index=True,
            help_text="Название цвета из 1С",
        ),
    )
    size_value = cast(
        str,
        models.CharField(
            "Размер",
            max_length=50,
            blank=True,
            db_index=True,
            help_text="Значение размера",
        ),
    )

    # Цены для различных ролей (6 типов)
    retail_price = cast(
        Decimal,
        models.DecimalField(
            "Розничная цена",
            max_digits=10,
            decimal_places=2,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли retail",
        ),
    )
    opt1_price = cast(
        Decimal | None,
        models.DecimalField(
            "Оптовая цена уровень 1",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли wholesale_level1",
        ),
    )
    opt2_price = cast(
        Decimal | None,
        models.DecimalField(
            "Оптовая цена уровень 2",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли wholesale_level2",
        ),
    )
    opt3_price = cast(
        Decimal | None,
        models.DecimalField(
            "Оптовая цена уровень 3",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли wholesale_level3",
        ),
    )
    trainer_price = cast(
        Decimal | None,
        models.DecimalField(
            "Цена для тренера",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли trainer",
        ),
    )
    federation_price = cast(
        Decimal | None,
        models.DecimalField(
            "Цена для представителя федерации",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли federation_rep",
        ),
    )
    rrp = cast(
        Decimal | None,
        models.DecimalField(
            "РРЦ",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Рекомендованная розничная цена (информационно)",
        ),
    )
    msrp = cast(
        Decimal | None,
        models.DecimalField(
            "МРЦ",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Минимальная рекомендованная розничная цена (информационно)",
        ),
    )

    # Остатки
    stock_quantity = cast(
        int,
        models.PositiveIntegerField(
            "Количество на складе",
            default=0,
            db_index=True,
            help_text="Доступное количество на складе",
        ),
    )
    reserved_quantity = cast(
        int,
        models.PositiveIntegerField(
            "Зарезервированное количество",
            default=0,
            help_text="Количество, зарезервированное в корзинах и заказах",
        ),
    )

    # Изображения (Hybrid подход - опциональные)
    main_image = cast(
        models.ImageField,
        models.ImageField(
            "Основное изображение",
            upload_to="products/variants/",
            null=True,
            blank=True,
            help_text="Основное изображение варианта (опционально)",
        ),
    )
    gallery_images = cast(
        list,
        models.JSONField(
            "Галерея изображений",
            default=list,
            blank=True,
            help_text="Список URL дополнительных изображений варианта",
        ),
    )

    # Статус
    is_active = cast(
        bool,
        models.BooleanField(
            "Активный",
            default=True,
            db_index=True,
            help_text="Доступен для заказа",
        ),
    )
    last_sync_at = cast(
        datetime | None,
        models.DateTimeField(
            "Последняя синхронизация",
            null=True,
            blank=True,
            help_text="Время последней синхронизации с 1С",
        ),
    )
    created_at = cast(
        datetime,
        models.DateTimeField("Дата создания", auto_now_add=True),
    )
    updated_at = cast(
        datetime,
        models.DateTimeField("Дата обновления", auto_now=True),
    )

    # Many-to-Many relationship with AttributeValue
    attributes: models.ManyToManyField = models.ManyToManyField(
        "AttributeValue",
        blank=True,
        related_name="variants",
        verbose_name="Атрибуты",
        help_text=("Атрибуты варианта товара " "(цвет, материал, размер и т.д.)"),
    )

    class Meta:
        verbose_name = "Вариант товара"
        verbose_name_plural = "Варианты товаров"
        db_table = "product_variants"
        ordering = ["color_name", "size_value"]
        indexes = [
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["onec_id"]),
            models.Index(fields=["color_name"]),
            models.Index(fields=["size_value"]),
            models.Index(fields=["stock_quantity"]),
            # Композитный индекс для оптимизации фильтрации по характеристикам
            models.Index(
                fields=["color_name", "size_value"],
                name="idx_variant_characteristics",
            ),
            # Индексы для оптимизации ценовых фильтров (Story 12.7 performance)
            models.Index(fields=["retail_price"]),
            models.Index(
                fields=["product", "stock_quantity"],
                name="idx_variant_product_stock",
            ),
            models.Index(
                fields=["product", "retail_price"],
                name="idx_variant_product_price",
            ),
        ]

    def __str__(self) -> str:
        """Строковое представление варианта товара"""
        return f"{self.product.name} - {self.sku}"

    def clean(self) -> None:
        """
        Валидация модели: хотя бы одна характеристика
        (цвет или размер) должна быть заполнена.
        Если импорт из 1С создаёт варианты без характеристик -
        это допустимый сценарий, но для UI выбора опций
        рекомендуется иметь хотя бы одну характеристику.
        """
        super().clean()
        if not self.color_name and not self.size_value:
            # Это WARNING, не ValidationError - позволяем создать вариант,
            # но логируем предупреждение для мониторинга качества данных из 1С
            import logging

            logger = logging.getLogger(__name__)
            logger.warning(
                f"ProductVariant {self.sku} создан без характеристик "
                f"(color_name и size_value пустые). Проверьте данные из 1С."
            )

    @property
    def is_in_stock(self) -> bool:
        """Проверка наличия товара на складе"""
        return self.stock_quantity > 0

    @property
    def available_quantity(self) -> int:
        """Доступное количество товара (с учетом резерва)"""
        return max(0, self.stock_quantity - self.reserved_quantity)

    @property
    def can_be_ordered(self) -> bool:
        """
        Проверка возможности заказа товара.
        Учитывает: активность Product, активность варианта,
        наличие и минимальное количество заказа.
        """
        if not self.product.is_active:
            return False
        if not self.is_active:
            return False
        if self.available_quantity < self.product.min_order_quantity:
            return False
        return True

    @property
    def effective_images(self) -> list[str]:
        """
        Hybrid подход: вернуть собственные изображения варианта,
        если отсутствуют - fallback на Product.base_images
        """
        if self.main_image:
            images = [self.main_image.url]
            if self.gallery_images:
                images.extend(self.gallery_images)
            return images
        # Fallback на базовые изображения продукта
        return self.product.base_images if self.product.base_images else []

    def get_price_for_user(self, user: User | None) -> Decimal:
        """Получить цену варианта для конкретного пользователя на основе его роли"""
        if not user or not user.is_authenticated:
            return self.retail_price

        role_price_mapping = {
            "retail": self.retail_price,
            "wholesale_level1": self.opt1_price or self.retail_price,
            "wholesale_level2": self.opt2_price or self.retail_price,
            "wholesale_level3": self.opt3_price or self.retail_price,
            "trainer": self.trainer_price or self.retail_price,
            "federation_rep": self.federation_price or self.retail_price,
        }

        return role_price_mapping.get(user.role, self.retail_price)


class Attribute(models.Model):
    """
    Модель атрибута товара (тип свойства: Цвет, Размер, Материал и т.д.)
    """

    name = cast(
        str,
        models.CharField(
            "Название атрибута",
            max_length=255,
            help_text="Название типа свойства (например, 'Цвет', 'Размер', 'Материал')",
        ),
    )
    slug = cast(
        str,
        models.SlugField(
            "Slug",
            max_length=255,
            unique=True,
            db_index=True,
            help_text="URL-совместимый идентификатор",
        ),
    )
    type = cast(
        str,
        models.CharField(
            "Тип атрибута",
            max_length=50,
            blank=True,
            help_text="Тип атрибута для будущей логики фильтрации",
        ),
    )
    normalized_name = cast(
        str,
        models.CharField(
            "Нормализованное название",
            max_length=255,
            unique=True,
            db_index=True,
            blank=True,
            null=True,
            help_text="Нормализованное название для дедупликации атрибутов",
        ),
    )
    is_active = cast(
        bool,
        models.BooleanField(
            "Активный атрибут",
            default=False,
            db_index=True,
            help_text="Атрибут активен и отображается в каталоге",
        ),
    )
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Атрибут товара"
        verbose_name_plural = "Атрибуты товаров"
        db_table = "product_attributes"
        ordering = ["name"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Автоматическая генерация slug и normalized_name при сохранении"""
        # Вычисляем normalized_name для дедупликации
        self.normalized_name = normalize_attribute_name(self.name) if self.name else ""

        # Автогенерация slug с обработкой дубликатов
        if not self.slug:
            try:
                # Транслитерация кириллицы в латиницу, затем slugify
                transliterated = translit(self.name, "ru", reversed=True)
                base_slug = slugify(transliterated)
            except RuntimeError:
                # Fallback на обычный slugify
                base_slug = slugify(self.name)

            # Если slug все еще пустой, создаем fallback
            if not base_slug:
                base_slug = f"attribute-{self.pk or int(time.time())}"

            # Проверка уникальности и добавление суффикса при необходимости
            slug = base_slug
            counter = 1
            while Attribute.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            self.slug = slug

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class AttributeValue(models.Model):
    """
    Модель значения атрибута (конкретное значение: Красный, XL, Хлопок и т.д.)
    """

    attribute = cast(
        Attribute,
        models.ForeignKey(
            Attribute,
            on_delete=models.CASCADE,
            related_name="values",
            verbose_name="Атрибут",
            help_text="Тип атрибута, к которому относится это значение",
        ),
    )
    value = cast(
        str,
        models.CharField(
            "Значение",
            max_length=255,
            help_text=("Конкретное значение атрибута " "(например, 'Красный', 'XL', 'Хлопок')"),
        ),
    )
    slug = cast(
        str,
        models.SlugField(
            "Slug",
            max_length=255,
            db_index=True,
            help_text="URL-совместимый идентификатор",
        ),
    )
    normalized_value = cast(
        str,
        models.CharField(
            "Нормализованное значение",
            max_length=255,
            db_index=True,
            blank=True,
            null=True,  # Initially nullable for migration
            help_text="Нормализованное значение для дедупликации",
        ),
    )
    created_at = cast(datetime, models.DateTimeField("Дата создания", auto_now_add=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Значение атрибута"
        verbose_name_plural = "Значения атрибутов"
        db_table = "product_attribute_values"
        ordering = ["attribute", "value"]
        indexes = [
            models.Index(fields=["attribute", "value"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["attribute", "normalized_value"],
                name="unique_attribute_normalized_value",
            ),
        ]

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Автоматическая генерация slug и normalized_value при сохранении"""
        # Вычисляем normalized_value для дедупликации
        from apps.products.utils.attributes import normalize_attribute_value

        self.normalized_value = normalize_attribute_value(self.value) if self.value else ""

        # Автогенерация slug
        if not self.slug:
            try:
                # Транслитерация кириллицы в латиницу, затем slugify
                transliterated = translit(self.value, "ru", reversed=True)
                self.slug = slugify(transliterated)
            except RuntimeError:
                # Fallback на обычный slugify
                self.slug = slugify(self.value)

            # Если slug все еще пустой, создаем fallback
            if not self.slug:
                self.slug = f"value-{self.pk or int(time.time())}"

        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return f"{self.attribute.name}: {self.value}"


class Attribute1CMapping(models.Model):
    """
    Маппинг атрибутов из 1С на master-атрибуты в системе.
    Позволяет связывать несколько ID из 1С с одним атрибутом для дедупликации.
    """

    attribute = cast(
        Attribute,
        models.ForeignKey(
            Attribute,
            on_delete=models.CASCADE,
            related_name="onec_mappings",
            verbose_name="Атрибут",
            help_text="Master-атрибут в системе",
        ),
    )
    onec_id = cast(
        str,
        models.CharField(
            "ID в 1С",
            max_length=255,
            unique=True,
            db_index=True,
            help_text="Уникальный идентификатор атрибута из 1С",
        ),
    )
    onec_name = cast(
        str,
        models.CharField(
            "Название в 1С",
            max_length=255,
            help_text="Оригинальное название атрибута из 1С",
        ),
    )
    source = cast(
        str,
        models.CharField(
            "Источник импорта",
            max_length=10,
            choices=[("goods", "Goods"), ("offers", "Offers")],
            help_text="Тип файла откуда импортирован атрибут (goods/offers)",
        ),
    )
    created_at = cast(
        datetime,
        models.DateTimeField("Дата создания", auto_now_add=True),
    )

    class Meta:
        verbose_name = "Маппинг атрибута 1С"
        verbose_name_plural = "Маппинги атрибутов 1С"
        db_table = "product_attribute_1c_mappings"
        indexes = [
            models.Index(fields=["attribute", "source"]),
        ]

    def __str__(self) -> str:
        return f"{self.onec_name} ({self.onec_id}) → {self.attribute.name}"


class AttributeValue1CMapping(models.Model):
    """
    Маппинг значений атрибутов из 1С на master-значения в системе.
    Позволяет связывать несколько ID из 1С с одним значением для дедупликации.
    """

    attribute_value = cast(
        AttributeValue,
        models.ForeignKey(
            AttributeValue,
            on_delete=models.CASCADE,
            related_name="onec_mappings",
            verbose_name="Значение атрибута",
            help_text="Master-значение атрибута в системе",
        ),
    )
    onec_id = cast(
        str,
        models.CharField(
            "ID в 1С",
            max_length=255,
            unique=True,
            db_index=True,
            help_text="Уникальный идентификатор значения атрибута из 1С",
        ),
    )
    onec_value = cast(
        str,
        models.CharField(
            "Значение в 1С",
            max_length=255,
            help_text="Оригинальное значение атрибута из 1С",
        ),
    )
    source = cast(
        str,
        models.CharField(
            "Источник импорта",
            max_length=10,
            choices=[("goods", "Goods"), ("offers", "Offers")],
            help_text="Тип файла откуда импортировано значение (goods/offers)",
        ),
    )
    created_at = cast(
        datetime,
        models.DateTimeField("Дата создания", auto_now_add=True),
    )

    class Meta:
        verbose_name = "Маппинг значения атрибута 1С"
        verbose_name_plural = "Маппинги значений атрибутов 1С"
        db_table = "product_attribute_value_1c_mappings"
        indexes = [
            models.Index(fields=["attribute_value", "source"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.onec_value} ({self.onec_id}) → "
            f"{self.attribute_value.attribute.name}: {self.attribute_value.value}"
        )

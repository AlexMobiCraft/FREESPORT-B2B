"""
Модели продуктов для платформы OPTISPORT
Включает товары, категории, бренды с роле-ориентированным ценообразованием
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.utils.text import slugify
from transliterate import translit

from apps.products.utils.attributes import normalize_attribute_name
from apps.products.utils.brands import normalize_brand_name

if TYPE_CHECKING:
    from apps.users.models import User


def _skip_derived_field(instance: models.Model, args: tuple[Any, ...], kwargs: dict[str, Any], *fields: str) -> None:
    """
    Полное сохранение существующей записи не пишет поля, которые ведёт импорт 1С или сервис акции.

    `Product.is_promo`, `ProductVariant.promo_price` и `ProductVariant.special_price` меняют
    импорт 1С и `services/promo.py` (`update_fields` или `QuerySet.update`). Экземпляр,
    загруженный до их смены (форма админки, инлайн товара), иначе вернул бы в БД устаревшее
    значение при правке любого другого поля. Создание, явный `update_fields` и отложенные
    (`defer`) поля не затрагиваются.
    """
    update_fields = kwargs.get("update_fields")
    if update_fields is not None and not isinstance(update_fields, (list, tuple, set, frozenset)):
        # Итератор (в том числе генератор) исчерпывается первой же проверкой `name in update_fields`,
        # и Django получил бы пустой набор: материализуем один раз, до собственных проверок моделей
        kwargs["update_fields"] = tuple(update_fields)
    if (
        not args
        and kwargs.get("update_fields") is None
        and not kwargs.get("force_insert")
        and not instance._state.adding
        and instance.pk
    ):
        deferred = instance.get_deferred_fields()
        kwargs["update_fields"] = [
            f.name
            for f in instance._meta.concrete_fields
            if not f.primary_key and f.name not in fields and f.attname not in deferred
        ]


def _delete_pinned(
    queryset: models.QuerySet[Any], lock_owners: Callable[[list[int]], None]
) -> tuple[int, dict[str, int]]:
    """
    Пакетное удаление по закреплённому набору `pk`: `lock_owners` берёт блокировки товаров до каскада.

    Набор собирается без блокировок строк. `select_for_update()` исходного запроса при сборе не
    действует — Django снимает его и сам при удалении: иначе строки брались бы раньше товаров и в
    порядке сканирования, а не по возрастанию `pk`, против общего порядка (`services/promo.py`).

    Удаление идёт на клоне (`filter(pk__in=pks)`), поэтому кэш результата исходного запроса
    Django не очищает: после удаления он продолжал бы отдавать уже удалённые объекты.
    """
    if queryset.query.is_sliced or queryset.query.distinct_fields:
        return models.QuerySet.delete(queryset)  # Django сам откажет: такой запрос удалить нельзя
    with transaction.atomic():
        collecting = queryset.all()
        collecting.query.select_for_update = False
        pks = list(collecting.order_by().values_list("pk", flat=True))
        lock_owners(pks)
        result = models.QuerySet.delete(queryset.filter(pk__in=pks))
    queryset._result_cache = None
    return result


class ProductVariantQuerySet(models.QuerySet["ProductVariant"]):
    """Менеджер вариантов: пакетное удаление берёт блокировки товаров в едином порядке."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Блокирует товары всех удаляемых вариантов по возрастанию `pk` до удаления.

        Сигналы `post_delete` приходят в порядке `pk` вариантов, и пересчёт флага «Акция» блокировал
        бы товары в этом порядке. Параллельный перенос варианта берёт те же товары по возрастанию
        `pk` — две операции с противоположным порядком ждали бы друг друга по кругу. Блокировка
        всего набора заранее исключает цикл.

        Набор владельцев собирается заново после блокировок (`promo.lock_products_stable`): вариант
        могли перенести в другой товар между сбором и блокировкой. Блокируются владельцы всех
        вариантов набора, а не только акционных: акционную цену варианту может записать импорт цен
        уже после сбора, и тогда его товар остался бы незаблокированным.

        Набор закреплён по `pk`: исходный запрос повторно не выполняется. Иначе вариант, подошедший
        под условие уже после блокировок, попал бы в Collector вместе с незаблокированным владельцем.
        """
        from apps.products.services import promo

        def lock_owners(pks: list[int]) -> None:
            promo.lock_products_stable(
                lambda: ProductVariant.objects.filter(pk__in=pks).order_by().values_list("product_id", flat=True)
            )

        return _delete_pinned(self, lock_owners)


class ProductQuerySet(models.QuerySet["Product"]):
    """Менеджер товаров: пакетное удаление берёт блокировки товаров до каскада на варианты."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Блокирует все удаляемые товары по возрастанию `pk` до каскадного удаления их вариантов.

        Collector шлёт `pre_delete` вариантов по их `pk`, а не по `pk` товаров, и каждый такой сигнал
        блокирует товар варианта (`promo.lock_variant`). Порядок товаров получился бы случайным и
        встречался бы с пересчётом флагов и переносами, которые берут товары по возрастанию, —
        взаимоблокировка. Товары, заблокированные заранее, дальше блокировать повторно можно без
        ожидания; варианты удаляемых товаров перенести в другой товар или добавить к ним никто не
        успеет, пока товар заблокирован.

        Набор закреплён по `pk` так же, как у `ProductVariantQuerySet.delete`.
        """
        from apps.products.services import promo

        return _delete_pinned(self, promo.lock_products)


def _lock_brand_products(brand_pks: list[int]) -> None:
    """Блокирует товары брендов по возрастанию `pk`: бренд каскадно удаляет товары, а те — свои варианты."""
    from apps.products.services import promo

    promo.lock_products_stable(
        lambda: Product.objects.filter(brand_id__in=brand_pks).order_by().values_list("pk", flat=True)
    )


def _category_tree_ids(category_pks: Iterable[int]) -> set[int]:
    """`pk` категорий и всех их потомков: `Category.parent` каскадно удаляет вложенные категории."""
    tree = set(category_pks)
    level = set(tree)
    while level:
        level = set(Category.objects.filter(parent_id__in=level).order_by().values_list("pk", flat=True)) - tree
        tree |= level
    return tree


def _lock_category_products(category_pks: list[int]) -> None:
    """Блокирует товары категорий и их потомков по возрастанию `pk` (см. `_lock_brand_products`)."""
    from apps.products.services import promo

    promo.lock_products_stable(
        lambda: Product.objects.filter(category_id__in=_category_tree_ids(category_pks))
        .order_by()
        .values_list("pk", flat=True)
    )


class BrandQuerySet(models.QuerySet["Brand"]):
    """Бренды: пакетное удаление берёт блокировки товаров бренда до каскада."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Блокирует товары удаляемых брендов по возрастанию `pk` до каскада на товары и их варианты.

        Collector обходит `ProductQuerySet.delete()`, а `pre_delete` вариантов приходит раньше
        сигналов бренда и по `pk` вариантов, не товаров: товары брались бы в случайном порядке и
        встречались бы с пересчётом флагов и переносами, которые берут их по возрастанию, —
        взаимоблокировка. Набор закреплён по `pk`, как у `ProductVariantQuerySet.delete`.
        """
        return _delete_pinned(self, _lock_brand_products)


class BrandManager(models.Manager["Brand"]):
    """Кастомный менеджер для модели Brand."""

    def get_queryset(self) -> BrandQuerySet:
        return BrandQuerySet(self.model, using=self._db)

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
            errors["image"] = "Для показа на главной нужен логотип"

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

    def delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Блокирует товары бренда по возрастанию `pk` до каскада (см. `BrandQuerySet.delete`)."""
        with transaction.atomic(using=using):
            _lock_brand_products([self.pk])
            return super().delete(using=using, keep_parents=keep_parents)

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


class CategoryQuerySet(models.QuerySet["Category"]):
    """Категории: пакетное удаление берёт блокировки товаров категорий и их потомков до каскада."""

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Блокирует товары удаляемых категорий и всех вложенных по возрастанию `pk` до каскада.

        Причина и закрепление набора те же, что у `BrandQuerySet.delete`; `Category.parent`
        удаляет потомков каскадно, поэтому товары берутся по всему поддереву.
        """
        return _delete_pinned(self, _lock_category_products)


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
    icon = cast(
        models.FileField,
        models.FileField("Иконка", upload_to="categories/icons/", blank=True),
    )
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

    objects = CategoryQuerySet.as_manager()

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

    def delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Блокирует товары категории и её потомков по возрастанию `pk` до каскада (см. `CategoryQuerySet.delete`)."""
        with transaction.atomic(using=using):
            _lock_category_products([self.pk])
            return super().delete(using=using, keep_parents=keep_parents)

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
    # Артикул в 1С — реквизит номенклатуры, один на товар: в offers.xml его нет,
    # поэтому у вариантов собственного артикула не бывает и sku там технический.
    article = cast(
        str,
        models.CharField(
            "Артикул",
            max_length=100,
            blank=True,
            default="",
            db_index=True,
            help_text="Артикул номенклатуры из goods.xml",
        ),
    )
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
    vat_rate = cast(
        "Decimal | None",
        models.DecimalField(
            "Ставка НДС (%)",
            max_digits=5,
            decimal_places=2,
            null=True,
            blank=True,
            db_index=True,
            help_text=(
                "Ставка НДС базового товара из goods.xml. "
                "Используется как устойчивый источник для вариантов при раздельном импорте 1С."
            ),
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
    # Отличает «скрыто импортом» от «выключено на сайте»: скрытое возвращает только
    # допуск товара в goods.xml, выключенное импорт включает, когда у товара есть цена.
    onec_deleted = cast(
        bool,
        models.BooleanField(
            "Скрыт импортом 1С",
            default=False,
            db_index=True,
            help_text=(
                "Товар в 1С вне дерева якорной категории или помечен на удаление. "
                "Ставится и снимается импортом; физически удаляет только команда "
                "purge_products_outside_root."
            ),
        ),
    )

    # Many-to-Many relationship with AttributeValue
    attributes: models.ManyToManyField = models.ManyToManyField(
        "AttributeValue",
        blank=True,
        related_name="products",
        verbose_name="Атрибуты",
        help_text="Атрибуты товара (цвет, материал, размер и т.д.)",
    )

    objects = ProductQuerySet.as_manager()

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

        # «Акция» выводится из акционных цен (`services/promo.sync_promo_flags`), руками не пишется
        _skip_derived_field(self, args, kwargs, "is_promo")
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
                ("opt4_price", "Оптовая цена уровень 4"),
                ("trainer_price", "Цена для тренера"),
                ("federation_price", "Цена для представителя федерации"),
                ("vip_price", "Цена VIP"),
                ("special_price", "Специальная цена"),
                (
                    "rrp",
                    "Рекомендованная розничная цена",
                ),
                (
                    "msrp",
                    "Максимальная рекомендованная цена",
                ),
                ("promo_price", "Акционная цена"),
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
        constraints = [
            # Одновременно действует одна акция. Переключение — только через
            # apps.products.services.promo: он гасит прежнюю акцию раньше, чем
            # включает новую, иначе этот индекс отклонит запись.
            models.UniqueConstraint(
                fields=["product_field"],
                condition=models.Q(product_field="promo_price", is_active=True),
                name="price_types_single_active_promo",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.onec_name} → {self.product_field}"

    def get_constraints(self) -> list[tuple[type[models.Model], Sequence[models.BaseConstraint]]]:
        # «Одна текущая акция» — не ошибка ввода: включение второй акции гасит прежнюю
        # `promo.save_price_type`, а страхует инвариант индекс БД. Стандартная проверка
        # ограничений отклонила бы форму админки раньше, чем сработал `save_model`.
        return [
            (model_class, [c for c in constraints if c.name != "price_types_single_active_promo"])
            for model_class, constraints in super().get_constraints()
        ]


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

    # Цены для различных ролей (7 типов)
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
    opt4_price = cast(
        Decimal | None,
        models.DecimalField(
            "Оптовая цена уровень 4",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли wholesale_level4",
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
    vip_price = cast(
        Decimal | None,
        models.DecimalField(
            "Цена VIP",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text="Цена для роли vip (вид цен «VIP цены» из 1С). Нет цены — розница.",
        ),
    )
    special_price = cast(
        Decimal | None,
        models.DecimalField(
            "Специальная цена",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text=(
                "Цена для роли special_price (вид цен «СПЕЦЦЕНА» из 1С). Нет цены — «Опт 1», затем розница. "
                "Ставит и снимает только импорт 1С."
            ),
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
    promo_price = cast(
        Decimal | None,
        models.DecimalField(
            "Акционная цена",
            max_digits=10,
            decimal_places=2,
            null=True,
            blank=True,
            validators=[MinValueValidator(Decimal("0"))],
            help_text=(
                "Цена текущей акции из 1С (вид цен «АКЦИЯ …»). Действует для всех ролей. "
                "Ставит и снимает только импорт 1С."
            ),
        ),
    )

    # НДС
    vat_rate = cast(
        "Decimal | None",
        models.DecimalField(
            "Ставка НДС (%)",
            max_digits=5,
            decimal_places=2,
            null=True,
            blank=True,
            help_text=(
                "Ставка НДС в % (22 — импортные товары ИП Семерюк, "
                "10/5 — товары ИП Терещенко). "
                "Заполняется автоматически при импорте из 1С (<СтавкаНДС>). "
                "Если не заполнено, используется DEFAULT_VAT_RATE из настроек."
            ),
        ),
    )

    # Остатки
    warehouse_id = cast(
        str | None,
        models.CharField(
            "Идентификатор склада 1С",
            max_length=64,
            null=True,
            blank=True,
            db_index=True,
            help_text="GUID склада из rests.xml, по которому определяется организация и ставка НДС",
        ),
    )
    warehouse_name = cast(
        str | None,
        models.CharField(
            "Склад",
            max_length=255,
            null=True,
            blank=True,
            help_text="Человекочитаемое имя склада 1С, например '1 СДВ склад'",
        ),
    )
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
    # У варианта флаг означает одно: предложение в 1С помечено на удаление.
    # Скрытие товара целиком варианты не трогает — см. Product.onec_deleted.
    onec_deleted = cast(
        bool,
        models.BooleanField(
            "Скрыт импортом 1С",
            default=False,
            db_index=True,
            help_text=(
                "Предложение в 1С помечено на удаление. Ставится и снимается импортом; "
                "физически удаляет только команда purge_products_outside_root."
            ),
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

    objects = ProductVariantQuerySet.as_manager()

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
        constraints = [
            # Цена четвёртого оптового уровня не может быть отрицательной
            models.CheckConstraint(  # type: ignore[call-arg]  # django-stubs 4.2 не знает condition=
                condition=models.Q(opt4_price__gte=0) | models.Q(opt4_price__isnull=True),
                name="products_opt4_price_positive",
            ),
            # Цены VIP и спеццена приходят из 1С и не бывают отрицательными
            models.CheckConstraint(  # type: ignore[call-arg]  # django-stubs 4.2 не знает condition=
                condition=models.Q(vip_price__gte=0) | models.Q(vip_price__isnull=True),
                name="products_vip_price_positive",
            ),
            models.CheckConstraint(  # type: ignore[call-arg]  # django-stubs 4.2 не знает condition=
                condition=models.Q(special_price__gte=0) | models.Q(special_price__isnull=True),
                name="products_special_price_positive",
            ),
        ]

    def __str__(self) -> str:
        """Строковое представление варианта товара"""
        return f"{self.product.name} - {self.sku}"

    def save(self, *args: Any, **kwargs: Any) -> None:
        """
        Полное сохранение существующего варианта не пишет `promo_price` и `special_price`.

        Акционную цену ставит и снимает только импорт 1С (`update_fields=["promo_price"]`)
        и `services/promo.py`, спеццену — только импорт 1С (`update_fields=["special_price", ...]`).
        Экземпляр, загруженный до сброса (форма админки, инлайн товара), иначе вернул бы в БД
        устаревшую цену при правке любого другого поля. `vip_price` правится в админке как
        `opt1–4`, поэтому полное сохранение его пишет.

        Запись активности или товара существующего варианта идёт в транзакции вместе с
        блокировками и пересчётом флага «Акция» (`signals.py`): упал пересчёт — откатится и
        сама запись. В автокоммите `UPDATE` иначе фиксировался бы до сигнала `post_save`.
        """
        _skip_derived_field(self, args, kwargs, "promo_price", "special_price")
        update_fields = None if args else kwargs.get("update_fields")
        writes_flag_source = update_fields is None or any(
            name in update_fields for name in ("is_active", "product", "product_id")
        )
        if self._state.adding or not self.pk or not writes_flag_source:
            super().save(*args, **kwargs)
            return
        with transaction.atomic():
            super().save(*args, **kwargs)

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
        """
        Цена, которую платит пользователь: меньшая из цены по роли и акционной.

        Акционная цена действует для всех ролей, но клиенту невыгодной не бывает:
        `min(цена по роли, акционная)` (решение владельца 2026-10-26, оно отменило
        решение 2026-10-21 «акция применяется, даже если выше цены клиента»).
        `min` считается только здесь: корзина, заказ, API и JSON-LD берут результат отсюда.
        Цена роли `≤ 0` в сравнении не участвует: платит акцию.
        """
        regular = self.get_regular_price_for_user(user)
        promo = self.promo_price
        if promo is None or promo <= 0:
            return regular
        if regular <= 0:
            return promo
        return min(regular, promo)

    def get_regular_price_for_user(self, user: User | None) -> Decimal:
        """Цена варианта по роли пользователя без учёта акции"""
        from apps.products.pricing_policy import resolve_pricing_role, resolve_role_price

        # Неверифицированный B2B и гость понижаются до retail (project-context.md §3)
        role = resolve_pricing_role(user)

        # Цепочка «поле роли → запасное поле → розница» общая с ценовыми фильтрами
        # каталога (`filters.visible_price_q`): живёт в pricing_policy.
        return resolve_role_price(self, role)


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


class OnecExcludedItem(models.Model):
    """Реестр Ид 1С, исключённых правилом допуска импорта.

    Дельта-обмен присылает `offers`/`prices`/`rests` отдельными сессиями, в
    которых нет ни дерева групп, ни пометок товаров. Реестр — память между
    сессиями: по нему импорт молча пропускает строки исключённых позиций
    (вместо тысяч «parent Product not found») и не пускает в поддерево якоря
    группу, помеченную или вынесенную из дерева в прошлой сессии.

    Запись появляется при недопуске или удалении, исчезает при допуске.
    """

    class Kind(models.TextChoices):
        GROUP = "group", "Группа"
        PRODUCT = "product", "Товар"
        OFFER = "offer", "Предложение"

    onec_id = cast(
        str,
        models.CharField(
            "Ид в 1С",
            max_length=255,
            unique=True,
            help_text="Ид группы или товара либо составной Ид предложения (товар#характеристика)",
        ),
    )
    kind = cast(
        str,
        models.CharField("Вид объекта", max_length=10, choices=Kind.choices, db_index=True),
    )
    reason = cast(str, models.CharField("Причина исключения", max_length=100, blank=True))
    updated_at = cast(datetime, models.DateTimeField("Дата обновления", auto_now=True))

    class Meta:
        verbose_name = "Исключённый Ид 1С"
        verbose_name_plural = "Реестр исключённых Ид 1С"
        db_table = "products_onec_excluded_items"
        ordering = ["kind", "onec_id"]

    def __str__(self) -> str:
        return f"{self.get_kind_display()} {self.onec_id}: {self.reason}"

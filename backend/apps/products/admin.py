"""
Django Admin для приложения products
"""

from __future__ import annotations

import logging
from typing import Any, cast

from django.contrib import admin, messages
from django.contrib.admin import SimpleListFilter
from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Count, QuerySet
from django.http import HttpRequest, HttpResponseRedirect
from django.shortcuts import render
from django.utils.html import format_html

from .forms import MergeAttributesActionForm, MergeBrandsActionForm, TransferMappingsActionForm
from .models import (
    Attribute,
    Attribute1CMapping,
    AttributeValue,
    AttributeValue1CMapping,
    Brand,
    Brand1CMapping,
    Category,
    ColorMapping,
    HomepageCategory,
    Product,
    ProductImage,
    ProductVariant,
)

logger = logging.getLogger(__name__)


class ProductImageInline(admin.TabularInline):
    """Инлайн для изображений продукта"""

    model = ProductImage
    extra = 1  # Количество пустых форм для добавления
    fields = ("image", "alt_text", "is_main", "sort_order")
    readonly_fields = ("created_at", "updated_at")


class ProductVariantInline(admin.TabularInline):
    """Инлайн для вариантов продукта (Story 13.x)"""

    model = ProductVariant
    extra = 0
    fields = (
        "sku",
        "color_name",
        "size_value",
        "retail_price",
        "rrp",
        "msrp",
        "stock_quantity",
        "is_active",
    )
    readonly_fields = ("created_at", "updated_at")
    show_change_link = True


class Brand1CMappingInline(admin.TabularInline):
    """Инлайн маппингов 1С для бренда"""

    model = Brand1CMapping
    extra = 0
    readonly_fields = ("created_at",)
    classes = ("collapse",)


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    """Admin для модели Brand"""

    list_display = (
        "image_preview",
        "name",
        "slug",
        "normalized_name",
        "is_featured",
        "mappings_count",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "is_featured", "created_at")
    search_fields = ("name", "slug", "normalized_name")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("normalized_name", "created_at", "updated_at")
    inlines = [Brand1CMappingInline]
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "name",
                    "slug",
                    "normalized_name",
                    "description",
                    "website",
                )
            },
        ),
        (
            "Изображение и отображение",
            {
                "fields": (
                    "image",
                    "is_featured",
                )
            },
        ),
        (
            "Статус и даты",
            {
                "fields": ("is_active", "created_at", "updated_at"),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Brand]:
        """Оптимизация запросов и аннотация количества маппингов"""
        qs = super().get_queryset(request)
        return cast("QuerySet[Brand]", qs.annotate(mappings_count=Count("onec_mappings")))

    @admin.display(description="Маппинги 1С", ordering="mappings_count")
    def mappings_count(self, obj: Brand) -> int:
        """Возвращает количество связанных маппингов 1С"""
        return getattr(obj, "mappings_count", 0)

    @admin.display(description="Лого")
    def image_preview(self, obj: Brand) -> str:
        """Превью изображения бренда в list view"""
        if obj.image:
            return format_html('<img src="{}" style="max-height:50px;max-width:100px;" />', obj.image.url)
        return "-"

    @admin.action(description="Объединить выбранные бренды")
    def merge_brands(self, request: HttpRequest, queryset: QuerySet[Brand]) -> Any:
        """Действие для объединения нескольких брендов в один"""
        if "apply" in request.POST:
            form = MergeBrandsActionForm(request.POST)
            if form.is_valid():
                target_brand = form.cleaned_data["target_brand"]
                count = 0
                try:
                    with transaction.atomic():
                        for source_brand in queryset:
                            if source_brand == target_brand:
                                continue

                            # Перенос маппингов
                            for mapping in source_brand.onec_mappings.all():
                                if target_brand.onec_mappings.filter(onec_id=mapping.onec_id).exists():
                                    logger.warning(
                                        f"Duplicate mapping for brand {target_brand}: "
                                        f"{mapping.onec_id}. Skipping transfer."
                                    )
                                    continue  # Mapping will be deleted with
                                    # source_brand
                                mapping.brand = target_brand
                                mapping.save()

                            # Перенос продуктов
                            # У продуктов brand PROTECT
                            # поэтому их НАДО перенести перед удалением бренда
                            source_brand.products.update(brand=target_brand)

                            source_brand.delete()
                            count += 1

                    self.message_user(
                        request,
                        f"Успешно объединено {count} брендов в {target_brand}",
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(request.get_full_path())
                except Exception as e:
                    logger.error(f"Error merging brands: {e}")
                    self.message_user(request, f"Ошибка: {e}", messages.ERROR)
                    return HttpResponseRedirect(request.get_full_path())
        else:
            form = MergeBrandsActionForm()

        return render(
            request,
            "admin/products/brand/merge_action.html",
            context={
                "brands": queryset,
                "form": form,
                "title": "Объединение брендов",
                "opts": self.model._meta,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    actions = ["merge_brands"]


@admin.register(Brand1CMapping)
class Brand1CMappingAdmin(admin.ModelAdmin):
    """Admin для модели Brand1CMapping"""

    list_display = ("brand", "onec_id", "onec_name", "created_at")
    list_filter = ("brand", "created_at")
    search_fields = ("onec_id", "onec_name", "brand__name")
    autocomplete_fields = ("brand",)
    readonly_fields = ("created_at",)

    @admin.action(description="Перенести на другой бренд")
    def transfer_to_brand(self, request: HttpRequest, queryset: QuerySet[Brand1CMapping]) -> Any:
        """Действие для переноса маппингов на другой бренд"""
        if "apply" in request.POST:
            form = TransferMappingsActionForm(request.POST)
            if form.is_valid():
                target_brand = form.cleaned_data["target_brand"]
                try:
                    with transaction.atomic():
                        count = 0
                        for mapping in queryset:
                            if target_brand.onec_mappings.filter(onec_id=mapping.onec_id).exists():
                                logger.warning(
                                    f"Mapping {mapping.onec_id} already exists in " f"{target_brand}. Skipping."
                                )
                                continue
                            mapping.brand = target_brand
                            mapping.save()
                            count += 1
                    self.message_user(
                        request,
                        f"Перенесено {count} маппингов на {target_brand}",
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(request.get_full_path())
                except Exception as e:
                    self.message_user(request, f"Ошибка: {e}", messages.ERROR)
                    return HttpResponseRedirect(request.get_full_path())
        else:
            form = TransferMappingsActionForm()

        return render(
            request,
            "admin/products/brand1cmapping/transfer_action.html",
            context={
                "mappings": queryset,
                "form": form,
                "title": "Перенос маппингов",
                "opts": self.model._meta,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )

    actions = ["transfer_to_brand"]


class HasIconFilter(SimpleListFilter):
    title = "С иконкой"
    parameter_name = "has_icon"

    def lookups(self, request: HttpRequest, model_admin: Any) -> tuple:
        return (("yes", "Да"), ("no", "Нет"))

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet | None:
        if self.value() == "yes":
            return queryset.exclude(icon="")
        if self.value() == "no":
            return queryset.filter(icon="")
        return None


class HasImageFilter(SimpleListFilter):
    title = "С картинкой"
    parameter_name = "has_image"

    def lookups(self, request: HttpRequest, model_admin: Any) -> tuple:
        return (("yes", "Да"), ("no", "Нет"))

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet | None:
        if self.value() == "yes":
            return queryset.exclude(image="")
        if self.value() == "no":
            return queryset.filter(image="")
        return None


class IsOnHomepageFilter(SimpleListFilter):
    title = "На главной"
    parameter_name = "is_homepage"

    def lookups(self, request: HttpRequest, model_admin: Any) -> tuple:
        return (("yes", "Да"), ("no", "Нет"))

    def queryset(self, request: HttpRequest, queryset: QuerySet) -> QuerySet | None:
        if self.value() == "yes":
            return queryset.filter(sort_order__gt=0)
        if self.value() == "no":
            return queryset.filter(sort_order=0)
        return None


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin для модели Category"""

    list_display = ("name", "slug", "parent", "onec_id", "is_active", "created_at")
    list_filter = ("is_active", IsOnHomepageFilter, HasIconFilter, HasImageFilter, "created_at")
    search_fields = ("name", "slug", "onec_id")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at")
    raw_id_fields = ("parent",)


@admin.register(HomepageCategory)
class HomepageCategoryAdmin(admin.ModelAdmin):
    """
    Admin для управления категориями на главной странице.
    Показывает только корневые категории (parent=None).
    Удаление запрещено для безопасности каталога.
    """

    list_display = ("id", "image_preview", "name", "parent", "sort_order", "is_active")
    list_editable = ("sort_order", "is_active")
    list_display_links = ("name",)
    list_filter = ("parent", "is_active")
    search_fields = ("name", "slug")
    ordering = ("sort_order",)
    fields = ("name", "parent", "icon", "image", "sort_order", "is_active")
    readonly_fields = ("name", "parent")

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Все категории для удобного выбора (без ограничений по уровню)."""
        qs = super().get_queryset(request)
        return qs

    def has_delete_permission(self, request: HttpRequest | None = None, obj: Any = None) -> bool:
        """Запрет удаления категорий из этого раздела."""
        return False

    def has_add_permission(self, request: HttpRequest) -> bool:
        """Запрет добавления — категории создаются в основном разделе."""
        return False

    @admin.display(description="Изображение")
    def image_preview(self, obj: HomepageCategory) -> str:
        """Превью изображения категории."""
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height:50px;max-width:80px;object-fit:cover;" />',
                obj.image.url,
            )
        return "-"

    def get_form(self, request: HttpRequest, obj: Any = None, change: bool = False, **kwargs: Any) -> Any:
        """Добавляем help_text к полю image."""
        form = super().get_form(request, obj, **kwargs)
        if "image" in form.base_fields:
            form.base_fields["image"].help_text = "Рекомендуемый размер: 400x300px (4:3)"
        return form


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Admin для модели Product"""

    list_display = (
        "name",
        "brand",
        "category",
        "is_active",
        "rrp_display",
        "msrp_display",
        # Story 11.0: Маркетинговые флаги
        "is_hit",
        "is_new",
        "is_sale",
        "is_promo",
        "is_premium",
        "discount_percent",
        "onec_id",
    )
    list_filter = (
        "is_active",
        "brand",
        "category",
        "sync_status",
        # Story 11.0: Маркетинговые фильтры
        "is_hit",
        "is_new",
        "is_sale",
        "is_promo",
        "is_premium",
        "created_at",
    )
    search_fields = ("name", "onec_id", "parent_onec_id", "onec_brand_id")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = (
        "created_at",
        "updated_at",
        "last_sync_at",
        "sync_status",
        "error_message",
        "onec_brand_id",
    )
    raw_id_fields = ("brand", "category")
    inlines = [ProductImageInline, ProductVariantInline]  # Добавляем инлайны
    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "name",
                    "slug",
                    "brand",
                    "category",
                    "description",
                    "short_description",
                )
            },
        ),
        (
            "Изображения (Hybrid подход - Story 13.1)",
            {
                "fields": ("base_images",),
                "description": ("Общие изображения товара из 1С. " "Используются как fallback для вариантов."),
            },
        ),
        (
            "Характеристики",
            {
                "fields": ("specifications",),
            },
        ),
        (
            "Интеграция с 1С",
            {
                "fields": (
                    "onec_id",
                    "parent_onec_id",
                    "onec_brand_id",
                    "sync_status",
                    "last_sync_at",
                    "error_message",
                ),
            },
        ),
        (
            "Маркетинговые флаги (Story 11.0)",
            {
                "fields": (
                    "is_hit",
                    "is_new",
                    "is_sale",
                    "is_promo",
                    "is_premium",
                    "discount_percent",
                ),
            },
        ),
        (
            "Статус и даты",
            {
                "fields": ("is_active", "created_at", "updated_at"),
            },
        ),
    )

    # Story 11.0: Массовые действия для маркетинговых флагов
    actions = [
        "mark_as_hit",
        "unmark_as_hit",
        "mark_as_new",
        "unmark_as_new",
        "mark_as_sale",
        "unmark_as_sale",
        "mark_as_promo",
        "unmark_as_promo",
        "mark_as_premium",
        "unmark_as_premium",
    ]

    @admin.action(description="✓ Отметить как хит продаж")
    def mark_as_hit(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: пометить как хит продаж"""
        updated = queryset.update(is_hit=True)
        self.message_user(request, f"Отмечено хитами продаж: {updated} товаров")

    @admin.action(description="✗ Снять отметку хит продаж")
    def unmark_as_hit(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: снять отметку хит продаж"""
        updated = queryset.update(is_hit=False)
        self.message_user(request, f"Снята отметка хитов продаж: {updated} товаров")

    @admin.action(description="✓ Отметить как новинку")
    def mark_as_new(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: пометить как новинку"""
        updated = queryset.update(is_new=True)
        self.message_user(request, f"Отмечено новинками: {updated} товаров")

    @admin.action(description="✗ Снять отметку новинка")
    def unmark_as_new(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: снять отметку новинка"""
        updated = queryset.update(is_new=False)
        self.message_user(request, f"Снята отметка новинок: {updated} товаров")

    @admin.action(description="✓ Отметить как распродажа")
    def mark_as_sale(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: пометить как распродажа"""
        updated = queryset.update(is_sale=True)
        self.message_user(request, f"Отмечено распродажей: {updated} товаров")

    @admin.action(description="✗ Снять отметку распродажа")
    def unmark_as_sale(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: снять отметку распродажа"""
        updated = queryset.update(is_sale=False)
        self.message_user(request, f"Снята отметка распродажи: {updated} товаров")

    @admin.action(description="✓ Отметить как акция")
    def mark_as_promo(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: пометить как акция"""
        updated = queryset.update(is_promo=True)
        self.message_user(request, f"Отмечено акцией: {updated} товаров")

    @admin.action(description="✗ Снять отметку акция")
    def unmark_as_promo(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: снять отметку акция"""
        updated = queryset.update(is_promo=False)
        self.message_user(request, f"Снята отметка акции: {updated} товаров")

    @admin.action(description="✓ Отметить как премиум")
    def mark_as_premium(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: пометить как премиум"""
        updated = queryset.update(is_premium=True)
        self.message_user(request, f"Отмечено премиум: {updated} товаров")

    @admin.action(description="✗ Снять отметку премиум")
    def unmark_as_premium(self, request: HttpRequest, queryset: QuerySet[Product]) -> None:
        """Массовое действие: снять отметка премиум"""
        updated = queryset.update(is_premium=False)
        self.message_user(request, f"Снята отметка премиум: {updated} товаров")

    @admin.display(description="РРЦ", ordering="variants__rrp")
    def rrp_display(self, obj: Product) -> str | None:
        """Отображение РРЦ из первого варианта"""
        variant = obj.variants.filter(rrp__isnull=False).first()
        return f"{variant.rrp} ₽" if variant and variant.rrp else "-"

    @admin.display(description="МРЦ", ordering="variants__msrp")
    def msrp_display(self, obj: Product) -> str | None:
        """Отображение МРЦ из первого варианта"""
        variant = obj.variants.filter(msrp__isnull=False).first()
        return f"{variant.msrp} ₽" if variant and variant.msrp else "-"

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related("brand", "category").prefetch_related("variants")


@admin.register(ColorMapping)
class ColorMappingAdmin(admin.ModelAdmin):
    """Admin для модели ColorMapping"""

    list_display = ("name", "hex_code", "swatch_image")
    search_fields = ("name", "hex_code")
    ordering = ("name",)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    """Admin для модели ProductVariant"""

    list_display = (
        "sku",
        "product",
        "color_name",
        "size_value",
        "retail_price",
        "rrp",
        "msrp",
        "stock_quantity",
        "is_active",
    )
    list_filter = ("is_active", "color_name", "size_value")
    search_fields = ("sku", "onec_id", "product__name")
    raw_id_fields = ("product",)
    readonly_fields = ("created_at", "updated_at", "last_sync_at")
    fieldsets = (
        (
            "Идентификация",
            {
                "fields": (
                    "product",
                    "sku",
                    "onec_id",
                )
            },
        ),
        (
            "Характеристики",
            {
                "fields": (
                    "color_name",
                    "size_value",
                )
            },
        ),
        (
            "Ценообразование",
            {
                "fields": (
                    "retail_price",
                    "rrp",
                    "msrp",
                    "opt1_price",
                    "opt2_price",
                    "opt3_price",
                    "trainer_price",
                    "federation_price",
                )
            },
        ),
        (
            "Остатки",
            {
                "fields": (
                    "stock_quantity",
                    "reserved_quantity",
                )
            },
        ),
        (
            "Изображения (опционально)",
            {
                "fields": (
                    "main_image",
                    "gallery_images",
                ),
                "description": (
                    "Собственные изображения варианта. " "Если не заданы, используются Product.base_images."
                ),
            },
        ),
        (
            "Статус и даты",
            {
                "fields": ("is_active", "last_sync_at", "created_at", "updated_at"),
            },
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[ProductVariant]:
        """Оптимизация запросов"""
        return super().get_queryset(request).select_related("product")


class AttributeValueInline(admin.TabularInline):
    """Inline для отображения значений атрибута в карточке Attribute"""

    model = AttributeValue
    extra = 0  # Не показывать пустые формы для добавления
    fields = ("value", "slug", "normalized_value", "created_at")
    readonly_fields = ("created_at", "normalized_value")
    can_delete = True
    show_change_link = True  # Ссылка на редактирование значения


class Attribute1CMappingInline(admin.TabularInline):
    """Inline для отображения маппингов 1С в карточке Attribute"""

    model = Attribute1CMapping
    extra = 0
    fields = ("onec_id", "onec_name", "source", "created_at")
    readonly_fields = ("created_at",)
    can_delete = False  # Не позволяем удалять маппинги
    show_change_link = True


@admin.register(Attribute)
class AttributeAdmin(admin.ModelAdmin):
    """Admin для модели Attribute с подсчетом значений и inline значениями"""

    list_display = (
        "name",
        "slug",
        "normalized_name",
        "is_active",
        "type",
        "values_count",
        "mappings_count",
        "created_at",
    )
    list_filter = ("type", "is_active", "created_at")
    search_fields = ("name", "slug", "normalized_name")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = (
        "created_at",
        "updated_at",
        "values_count",
        "mappings_count",
        "normalized_name",
    )
    ordering = ("name",)
    inlines = [AttributeValueInline, Attribute1CMappingInline]
    actions = ["activate_attributes", "deactivate_attributes", "merge_attributes"]

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "name",
                    "slug",
                    "normalized_name",
                    "type",
                    "is_active",
                )
            },
        ),
        (
            "Статистика",
            {
                "fields": ("values_count", "mappings_count"),
                "classes": ("collapse",),
            },
        ),
        (
            "Даты",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Кол-во значений")
    def values_count(self, obj: Attribute) -> int:
        """Отображение количества значений для атрибута"""
        return obj.values.count()

    @admin.display(description="Кол-во маппингов 1С")
    def mappings_count(self, obj: Attribute) -> int:
        """Отображение количества маппингов 1С для атрибута"""
        return obj.onec_mappings.count()

    @admin.action(description="✅ Активировать выбранные атрибуты")
    def activate_attributes(self, request: HttpRequest, queryset: QuerySet[Attribute]) -> None:
        """Массовая активация атрибутов"""
        updated = queryset.update(is_active=True)
        self.message_user(
            request,
            f"Активировано атрибутов: {updated}",
            messages.SUCCESS,
        )

    @admin.action(description="❌ Деактивировать выбранные атрибуты")
    def deactivate_attributes(self, request: HttpRequest, queryset: QuerySet[Attribute]) -> None:
        """Массовая деактивация атрибутов"""
        updated = queryset.update(is_active=False)
        self.message_user(
            request,
            f"Деактивировано атрибутов: {updated}",
            messages.SUCCESS,
        )

    @admin.action(description="🔗 Объединить выбранные атрибуты")
    def merge_attributes(self, request: HttpRequest, queryset: QuerySet[Attribute]) -> Any:
        """
        Действие для объединения нескольких атрибутов в один.

        Переносит все маппинги 1С и значения атрибутов на целевой атрибут.
        Исходные атрибуты удаляются после переноса.
        """
        # Валидация: минимум 2 атрибута
        if queryset.count() < 2:
            self.message_user(
                request,
                "Для объединения необходимо выбрать минимум 2 атрибута.",
                messages.WARNING,
            )
            return None

        if "apply" in request.POST:
            form = MergeAttributesActionForm(request.POST)
            if form.is_valid():
                target_attribute = form.cleaned_data["target_attribute"]
                merged_count = 0
                mappings_transferred = 0
                values_transferred = 0
                values_deduplicated = 0

                try:
                    with transaction.atomic():
                        for source_attribute in queryset:
                            if source_attribute == target_attribute:
                                continue

                            # 1. Перенос маппингов 1С
                            for mapping in source_attribute.onec_mappings.all():
                                if target_attribute.onec_mappings.filter(onec_id=mapping.onec_id).exists():
                                    logger.warning(
                                        f"Duplicate mapping for attribute "
                                        f"{target_attribute}: {mapping.onec_id}. "
                                        f"Skipping transfer."
                                    )
                                    continue
                                mapping.attribute = target_attribute
                                mapping.save()
                                mappings_transferred += 1

                            # 2. Перенос значений атрибута с дедупликацией
                            for value in source_attribute.values.all():
                                # Проверяем есть ли уже такое значение у target
                                existing_value = target_attribute.values.filter(
                                    normalized_value=value.normalized_value
                                ).first()

                                if existing_value:
                                    # Значение уже существует - переносим только
                                    # маппинги
                                    for value_mapping in value.onec_mappings.all():
                                        if existing_value.onec_mappings.filter(onec_id=value_mapping.onec_id).exists():
                                            continue
                                        value_mapping.attribute_value = existing_value
                                        value_mapping.save()
                                    values_deduplicated += 1
                                else:
                                    # Переносим значение целиком
                                    value.attribute = target_attribute
                                    value.save()
                                    values_transferred += 1

                            # 3. Удаляем исходный атрибут
                            # (CASCADE удалит оставшиеся связи)
                            source_attribute.delete()
                            merged_count += 1

                        # 4. Audit logging через LogEntry
                        LogEntry.objects.log_actions(  # type: ignore[attr-defined]
                            user_id=request.user.pk,
                            queryset=Attribute.objects.filter(pk=target_attribute.pk),
                            action_flag=CHANGE,
                            change_message=f"Объединены {merged_count} атрибутов. "
                            f"Перенесено маппингов: {mappings_transferred}, "
                            f"значений: {values_transferred}, "
                            f"дедуплицировано: {values_deduplicated}.",
                            single_object=True,
                        )

                    self.message_user(
                        request,
                        f"Успешно объединено {merged_count} атрибутов в "
                        f"'{target_attribute}'. "
                        f"Перенесено маппингов: {mappings_transferred}, "
                        f"значений: {values_transferred}.",
                        messages.SUCCESS,
                    )
                    return HttpResponseRedirect(request.get_full_path())

                except Exception as e:
                    logger.error(f"Error merging attributes: {e}")
                    self.message_user(
                        request,
                        f"Ошибка при объединении атрибутов: {e}",
                        messages.ERROR,
                    )
                    return HttpResponseRedirect(request.get_full_path())
        else:
            form = MergeAttributesActionForm()

        # Подготовка статистики для preview
        attributes_with_stats = []
        total_mappings = 0
        total_values = 0

        for attr in queryset:
            mappings_count = attr.onec_mappings.count()
            values_count = attr.values.count()
            total_mappings += mappings_count
            total_values += values_count
            attributes_with_stats.append(
                {
                    "name": attr.name,
                    "pk": attr.pk,
                    "mappings_count": mappings_count,
                    "values_count": values_count,
                    "is_active": attr.is_active,
                }
            )

        return render(
            request,
            "admin/products/attribute/merge_action.html",
            context={
                "attributes": attributes_with_stats,
                "total_mappings": total_mappings,
                "total_values": total_values,
                "form": form,
                "title": "Объединение атрибутов",
                "opts": self.model._meta,
                "action_checkbox_name": ACTION_CHECKBOX_NAME,
            },
        )


class AttributeValue1CMappingInline(admin.TabularInline):
    """Inline для отображения маппингов 1С в карточке AttributeValue"""

    model = AttributeValue1CMapping
    extra = 0
    fields = ("onec_id", "onec_value", "source", "created_at")
    readonly_fields = ("created_at",)
    can_delete = False  # Не позволяем удалять маппинги
    show_change_link = True


@admin.register(AttributeValue)
class AttributeValueAdmin(admin.ModelAdmin):
    """Admin для модели AttributeValue с маппингами 1С"""

    list_display = (
        "value",
        "attribute",
        "slug",
        "normalized_value",
        "mappings_count",
        "created_at",
    )
    list_filter = ("attribute", "created_at")
    search_fields = ("value", "slug", "normalized_value", "attribute__name")
    prepopulated_fields = {"slug": ("value",)}
    readonly_fields = ("created_at", "updated_at", "normalized_value", "mappings_count")
    raw_id_fields = ("attribute",)
    ordering = ("attribute", "value")
    inlines = [AttributeValue1CMappingInline]

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "attribute",
                    "value",
                    "slug",
                    "normalized_value",
                )
            },
        ),
        (
            "Статистика",
            {
                "fields": ("mappings_count",),
                "classes": ("collapse",),
            },
        ),
        (
            "Даты",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Кол-во маппингов 1С")
    def mappings_count(self, obj: AttributeValue) -> int:
        """Отображение количества маппингов 1С для значения атрибута"""
        return obj.onec_mappings.count()


@admin.register(Attribute1CMapping)
class Attribute1CMappingAdmin(admin.ModelAdmin):
    """Admin для модели Attribute1CMapping"""

    list_display = ("onec_name", "onec_id", "attribute", "source", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("onec_name", "onec_id", "attribute__name")
    readonly_fields = ("created_at",)
    raw_id_fields = ("attribute",)
    ordering = ("attribute", "onec_name")


@admin.register(AttributeValue1CMapping)
class AttributeValue1CMappingAdmin(admin.ModelAdmin):
    """Admin для модели AttributeValue1CMapping"""

    list_display = ("onec_value", "onec_id", "attribute_value", "source", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("onec_value", "onec_id", "attribute_value__value")
    readonly_fields = ("created_at",)
    raw_id_fields = ("attribute_value",)
    ordering = ("attribute_value", "onec_value")

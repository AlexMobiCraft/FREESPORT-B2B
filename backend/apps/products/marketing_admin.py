"""
Раздел маркетинга `/marketing/` — метки товаров, бренды и категории главной (стори 42.6).

Все три admin-класса — белые списки поверх классов `/admin/`: в разделе нет цен,
остатков, полей 1С, НДС и описания товара. Сохраняются только изменённые
правимые поля (`save(update_fields=…)`): импорт 1С пишет те же строки, и полный
`save()` вернул бы значения, прочитанные в начале запроса.

Модуль импортируется из `ProductsConfig.ready()`: к этому моменту
`admin.autodiscover()` уже загрузил `apps/products/admin.py`.
"""

from __future__ import annotations

from typing import Any

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Model, Prefetch, QuerySet
from django.http import Http404, HttpRequest, HttpResponse
from django.urls import reverse
from django.utils.html import format_html

from apps.products.admin import BrandAdmin, HomepageCategoryAdmin, ProductAdmin
from apps.products.models import Brand, Category, HomepageCategory, Product, ProductVariant
from apps.products.utils.images import product_main_image_url
from freesport.admin_site import marketing_site

# Метки, которые сотрудник правит руками. «Акция» в их число не входит: её
# выводит импорт 1С из акционных цен (services/promo.sync_promo_flags).
EDITABLE_LABEL_FIELDS = ("is_hit", "is_new", "is_sale", "is_premium")
# Метки, которые раздел показывает.
LABEL_FIELDS = ("is_hit", "is_new", "is_sale", "is_promo", "is_premium")
BRAND_FIELDS = ("image", "is_featured", "description")
CATEGORY_FIELDS = ("icon", "image", "sort_order")


class SeenValuesForm(forms.ModelForm):
    """
    Форма, у которой «изменено» считается от значений, увиденных сотрудником.

    Поля `seen_fields` рендерят скрытое начальное значение (`show_hidden_initial`),
    и `changed_data` сравнивает POST с ним, а не с текущей строкой БД. Иначе
    сохранение списка вернуло бы строки, которые после открытия страницы поменял
    другой сотрудник или массовое действие: у них отправленное значение
    отличается от нового значения в БД.

    Устаревшая форма не отклоняется (решение 11 стори 42.6): одновременная
    правка одного и того же поля — «последняя запись выигрывает», как во всей
    штатной админке.
    """

    seen_fields: tuple[str, ...] = ()

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        for name in self.seen_fields:
            if name in self.fields:
                self.fields[name].show_hidden_initial = True


def save_changed_fields(obj: Model, form: forms.ModelForm, editable: tuple[str, ...]) -> None:
    """
    Сохраняет только изменённые правимые поля и `updated_at`.

    Пустое пересечение `changed_data` с правимыми полями — `save()` не вызывается
    вовсе. Зовётся из `save_model`: её вызывают и карточка, и сохранение списка.
    """
    changed = [name for name in editable if name in form.changed_data]
    if not changed:
        return
    obj.save(update_fields=[*changed, "updated_at"])


class CategoryPathListFilter(admin.RelatedFieldListFilter):
    """
    Фильтр по категории с подписями «СПОРТ > Мячи > Футбол» из одного запроса.

    Штатный фильтр подписывает варианты через `str(category)` — это `full_name`,
    рекурсия по `parent` с запросом на каждый уровень. На проде 121 категория
    глубиной до 5 уровней — ~300 запросов на каждое открытие списка товаров.
    Здесь путь строится в памяти обходом `parent_id`.
    """

    def field_choices(self, field: Any, request: HttpRequest, model_admin: admin.ModelAdmin) -> list[tuple[Any, str]]:
        rows = {row.pk: row for row in Category.objects.only("id", "name", "parent_id")}
        choices = []
        for pk, row in rows.items():
            names: list[str] = []
            seen: set[int] = set()
            node: Category | None = row
            while node is not None and node.pk not in seen:
                seen.add(node.pk)
                names.append(node.name)
                node = rows.get(node.parent_id) if node.parent_id else None
            choices.append((pk, " > ".join(reversed(names))))
        return sorted(choices, key=lambda choice: choice[1])


class MarketingProductForm(SeenValuesForm):
    seen_fields = EDITABLE_LABEL_FIELDS


class MarketingProductAdmin(ProductAdmin):
    """
    Товары в разделе маркетинга: правятся четыре метки, «Акция» только показывается.

    Наследование — ради восьми действий меток; всё отображение переопределено
    белым списком. Название, бренд, категория и скидка — только чтение.
    """

    form = MarketingProductForm
    list_display: Any = ("photo", "name", "brand", "category_name", "is_active", *LABEL_FIELDS, "discount_percent")
    list_display_links = ("name",)
    list_editable: Any = EDITABLE_LABEL_FIELDS
    list_filter: Any = (*LABEL_FIELDS, "brand", ("category", CategoryPathListFilter))
    search_fields: Any = ("name", "article")
    fieldsets: Any = (
        ("Товар", {"fields": ("name", "brand_link", "category_name", "discount_percent")}),
        ("Метки", {"fields": LABEL_FIELDS}),
    )
    readonly_fields: Any = ("name", "brand_link", "category_name", "discount_percent", "is_promo")
    inlines = []
    raw_id_fields: Any = ()
    # Без поля slug в форме AdminForm падал бы с KeyError.
    prepopulated_fields: Any = {}
    view_on_site = False

    def get_fieldsets(self, request: HttpRequest, obj: Any = None) -> Any:
        return self.fieldsets

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> Any:
        return self.readonly_fields

    def get_changelist_form(self, request: HttpRequest, **kwargs: Any) -> Any:
        # Форма строки списка строится своей modelform_factory, не из self.form.
        return super().get_changelist_form(request, form=MarketingProductForm, **kwargs)

    def get_queryset(self, request: HttpRequest) -> QuerySet[Product]:
        # Родительский prefetch всех вариантов нужен ценам, которых в разделе нет.
        photo_variants = (
            ProductVariant.objects.exclude(main_image="")
            .exclude(main_image__isnull=True)
            .only("id", "product_id", "main_image")
            .order_by("pk")
        )
        return (
            super(ProductAdmin, self)
            .get_queryset(request)
            .select_related("brand", "category")
            .prefetch_related(Prefetch("variants", queryset=photo_variants, to_attr="marketing_photo_variants"))
        )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def save_model(self, request: HttpRequest, obj: Product, form: Any, change: bool) -> None:
        save_changed_fields(obj, form, EDITABLE_LABEL_FIELDS)

    @admin.display(description="Фото")
    def photo(self, obj: Product) -> str:
        """Миниатюра, чтобы узнать товар: первый вариант с фото, иначе base_images."""
        url = _product_photo_url(obj)
        if not url:
            return "—"
        return format_html('<img src="{}" style="max-height:50px;max-width:80px;" alt="" />', url)

    @admin.display(description="Бренд")
    def brand_link(self, obj: Product) -> str:
        url = reverse(f"{self.admin_site.name}:products_brand_change", args=[obj.brand_id])
        return format_html('<a href="{}">{}</a>', url, obj.brand.name)

    @admin.display(description="Категория", ordering="category__name")
    def category_name(self, obj: Product) -> str:
        # Не str(category): это full_name с запросом на каждый уровень дерева.
        return obj.category.name


def _product_photo_url(obj: Product) -> str | None:
    # Тот же кадр, что в каталоге (ProductListSerializer.get_main_image).
    variants = getattr(obj, "marketing_photo_variants", [])
    return product_main_image_url(obj, variants[0] if variants else None)


class MarketingBrandForm(SeenValuesForm):
    seen_fields = ("is_featured", "description")


class MarketingBrandAdmin(BrandAdmin):
    """
    Бренды в разделе маркетинга: логотип, «Показывать на главной» и описание.

    Название и «Активный» — только чтение (их пишет импорт 1С). Привязок 1С,
    объединения брендов, добавления и удаления нет.
    """

    form = MarketingBrandForm
    list_display: Any = ("image_preview", "name", "is_featured", "is_active")
    list_filter: Any = ("is_featured", "is_active")
    search_fields: Any = ("name",)
    fieldsets: Any = ((None, {"fields": ("name", "is_active", "image", "is_featured", "description")}),)
    readonly_fields: Any = ("name", "is_active")
    prepopulated_fields: Any = {}
    inlines = []
    actions: list[Any] = []
    view_on_site = False

    def get_queryset(self, request: HttpRequest) -> QuerySet[Brand]:
        # Без аннотации числа привязок 1С: колонки в разделе нет.
        return super(BrandAdmin, self).get_queryset(request)

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        return False

    def save_model(self, request: HttpRequest, obj: Brand, form: Any, change: bool) -> None:
        save_changed_fields(obj, form, BRAND_FIELDS)


class MarketingHomepageCategoryForm(SeenValuesForm):
    seen_fields = ("sort_order",)

    def clean_icon(self) -> Any:
        """
        Новая иконка — только растровое изображение (Pillow + расширение, без SVG).

        `icon` — `FileField`, а `/media/` отдаётся на origin сайта: загруженный
        HTML или SVG со скриптом открылся бы рядом с `/admin/`. В `/admin/`
        проверки нет — SVG-иконки загружает суперпользователь.
        """
        icon = self.cleaned_data.get("icon")
        if isinstance(icon, UploadedFile):
            # False — очистка поля, FieldFile — прежний файл: их не проверяем.
            forms.ImageField().clean(icon)
        return icon


class MarketingHomepageCategoryAdmin(HomepageCategoryAdmin):
    """
    Категории главной в разделе маркетинга: иконка, картинка и порядок.

    `is_active` — активность категории каталога целиком (proxy `products.Category`),
    поэтому только для чтения; убрать категорию с главной — порядок 0.
    """

    form = MarketingHomepageCategoryForm
    readonly_fields: Any = ("name", "parent", "is_active")
    list_editable: Any = ("sort_order",)
    list_filter: Any = ("is_active",)
    view_on_site = False

    def get_changelist_form(self, request: HttpRequest, **kwargs: Any) -> Any:
        return super().get_changelist_form(request, form=MarketingHomepageCategoryForm, **kwargs)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        # Корни витрины — тот же круг, что homepage_categories_q(), но без
        # sort_order > 0: категорию можно и убрать с главной, и вернуть.
        # Подкатегории на главную не выводятся, их в разделе нет.
        root_name = getattr(settings, "ROOT_CATEGORY_NAME", "СПОРТ")
        return (
            super()
            .get_queryset(request)
            .select_related("parent")
            .filter(parent__name=root_name, parent__parent__isnull=True, parent__is_active=True)
        )

    def _get_obj_does_not_exist_redirect(self, request: HttpRequest, opts: Any, object_id: str) -> HttpResponse:
        # Категория вне выборки раздела неотличима от несуществующей: 404.
        raise Http404("Категория не найдена")

    def save_model(self, request: HttpRequest, obj: HomepageCategory, form: Any, change: bool) -> None:
        save_changed_fields(obj, form, CATEGORY_FIELDS)


marketing_site.register(Product, MarketingProductAdmin)
marketing_site.register(Brand, MarketingBrandAdmin)
marketing_site.register(HomepageCategory, MarketingHomepageCategoryAdmin)

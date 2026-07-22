"""
Фильтры для каталога товаров
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import django_filters
from django.conf import settings
from django.contrib.postgres.search import SearchQuery, SearchRank, SearchVector
from django.db import connection
from django.db.models import Q, QuerySet

from .models import Attribute, Brand, Category, Product

if TYPE_CHECKING:
    from django.http import HttpRequest


class ProductFilter(django_filters.FilterSet):
    """
    Фильтр для товаров согласно Story 2.4, 2.9 и 14.6 требованиям

    Story 14.6: Динамические фильтры по атрибутам (attr_<slug>=<value>)
    """

    # Фильтр по категории (с учетом дочерних)
    category_id = django_filters.NumberFilter(
        method="filter_category_id",
        help_text="ID категории для фильтрации (включая дочерние категории)",
    )

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Story 14.6: Динамическое создание фильтров для всех активных атрибутов

        Создает фильтры вида attr_<slug> для каждого активного атрибута.
        Например: ?attr_color=red,blue или ?attr_size=xl

        Оптимизировано: кешируем атрибуты для избежания запроса к БД при каждом запросе.
        """
        super().__init__(*args, **kwargs)

        from django.core.cache import cache

        cache_key = "active_attributes_for_filters"
        active_attributes = cache.get(cache_key)

        if active_attributes is None:
            # Загружаем только активные атрибуты для создания фильтров
            active_attributes = list(Attribute.objects.filter(is_active=True).only("id", "slug", "name"))
            # Кешируем на 5 минут
            cache.set(cache_key, active_attributes, 300)

        for attr in active_attributes:
            filter_name = f"attr_{attr.slug}"
            # Создаем CharFilter с методом filter_attribute
            filter_obj = django_filters.CharFilter(
                method="filter_attribute",
                label=attr.name,
                help_text=(
                    f"Фильтр по атрибуту '{attr.name}'. "
                    f"Поддерживает множественные значения: {filter_name}=value1,value2"
                ),
            )
            # Важно: динамически созданный фильтр требует parent и field_name
            filter_obj.parent = self
            filter_obj.field_name = filter_name
            # Сохраняем slug атрибута для использования в filter_attribute
            filter_obj.attribute_slug = attr.slug
            self.filters[filter_name] = filter_obj

    # Фильтр по бренду (поддерживает как ID, так и slug)
    brand = django_filters.CharFilter(
        method="filter_brand",
        help_text=("Бренд по ID или slug. Поддерживает множественный выбор: brand=nike,adidas"),
    )

    def filter_attribute(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        """
        Story 14.6: Фильтрация товаров по динамическим атрибутам

        Поддерживает:
        - Одиночное значение: ?attr_color=red
        - Множественные значения (OR): ?attr_color=red,blue
        - Множественные атрибуты (AND): ?attr_color=red&attr_size=xl

        Args:
            queryset: Исходный QuerySet товаров
            name: Имя фильтра (attr_<slug>)
            value: Значение фильтра (может содержать запятые для OR)

        Returns:
            Отфильтрованный QuerySet
        """
        if not value:
            return queryset

        # Получаем slug атрибута из фильтра
        filter_obj = self.filters.get(name)
        if not filter_obj or not hasattr(filter_obj, "attribute_slug"):
            return queryset

        attribute_slug = filter_obj.attribute_slug

        # Парсим значения (поддержка множественных значений через запятую)
        values = [v.strip() for v in value.split(",") if v.strip()]
        if not values:
            return queryset

        # Фильтрация через M2M relationship
        # Товары, у которых есть атрибут с данным slug и значением из списка
        return queryset.filter(
            attributes__attribute__slug=attribute_slug,
            attributes__slug__in=values,
        ).distinct()

    # Ценовой диапазон
    min_price = django_filters.NumberFilter(
        method="filter_min_price",
        help_text="Минимальная цена (адаптируется к роли пользователя)",
    )

    max_price = django_filters.NumberFilter(
        method="filter_max_price",
        help_text="Максимальная цена (адаптируется к роли пользователя)",
    )

    # Фильтр по наличию
    in_stock = django_filters.BooleanFilter(method="filter_in_stock", help_text="Товары в наличии (true/false)")

    # Дополнительные фильтры
    is_featured = django_filters.BooleanFilter(field_name="is_featured", help_text="Рекомендуемые товары")

    search = django_filters.CharFilter(
        method="filter_search",
        help_text=(
            "Полнотекстовый поиск по названию, описанию и артикулу " "(PostgreSQL FTS с русскоязычной конфигурацией)"
        ),
    )

    # Фильтр по размеру из JSON specifications
    size = django_filters.CharFilter(
        method="filter_size",
        help_text=("Размер из спецификаций товара (XS, S, M, L, XL, XXL, 38, 40, 42 и т.д.)"),
    )

    # Story 11.0: Маркетинговые фильтры для бейджей
    is_hit = django_filters.BooleanFilter(field_name="is_hit", help_text="Хиты продаж")
    is_new = django_filters.BooleanFilter(field_name="is_new", help_text="Новинки")
    is_sale = django_filters.BooleanFilter(field_name="is_sale", help_text="Товары на распродаже")
    is_promo = django_filters.BooleanFilter(field_name="is_promo", help_text="Акционные товары")
    is_premium = django_filters.BooleanFilter(field_name="is_premium", help_text="Премиум товары")
    has_discount = django_filters.BooleanFilter(
        method="filter_has_discount",
        help_text="Товары со скидкой (имеют discount_percent)",
    )

    class Meta:
        model = Product
        fields = [
            "category_id",
            "brand",
            "min_price",
            "max_price",
            "in_stock",
            "is_featured",
            "search",
            "size",
            # Story 11.0: Маркетинговые фильтры
            "is_hit",
            "is_new",
            "is_sale",
            "is_promo",
            "is_premium",
            "has_discount",
        ]

    def filter_brand(self, queryset: QuerySet[Product], name: str, value: str) -> QuerySet[Product]:
        """Фильтр по бренду через ID или slug с поддержкой множественного выбора"""
        if not value:
            return queryset

        # Поддержка множественных значений: brand=nike,adidas
        brand_values = [v.strip() for v in value.split(",") if v.strip()]
        if not brand_values:
            return queryset

        # Создаем Q-объект для множественного выбора
        brand_queries = Q()

        for brand_value in brand_values:
            if brand_value.isdigit():
                # Фильтр по ID
                brand_queries |= Q(brand__id=brand_value)
            else:
                # Фильтр по slug (case-insensitive)
                brand_queries |= Q(brand__slug__iexact=brand_value)

        return queryset.filter(brand_queries)

    def filter_category_id(self, queryset, name, value):
        """
        Фильтрует товары по категории и всем её дочерним категориям.
        Оптимизировано: используем один запрос с get_descendants_ids.
        """
        if not value:
            return queryset

        try:
            category_id = int(value)
        except (TypeError, ValueError):
            return queryset

        # Получаем все ID категорий одним запросом используя MPTT-подобный подход
        # или просто кешируем дерево категорий
        from django.core.cache import cache

        cache_key = f"category_descendants_{category_id}"
        category_ids = cache.get(cache_key)

        if category_ids is None:
            # Проверяем существование категории
            if not Category.objects.filter(id=category_id, is_active=True).exists():
                return queryset.none()

            # Собираем все ID за один проход (максимум 4 уровня вложенности)
            category_ids = {category_id}
            current_level = [category_id]

            for _ in range(4):  # Максимум 4 уровня вложенности
                if not current_level:
                    break
                children = list(
                    Category.objects.filter(parent_id__in=current_level, is_active=True).values_list("id", flat=True)
                )
                if not children:
                    break
                category_ids.update(children)
                current_level = children

            # Кешируем на 5 минут
            cache.set(cache_key, list(category_ids), 300)

        return queryset.filter(category_id__in=category_ids)

    def filter_min_price(self, queryset, name, value):
        """
        Фильтр по минимальной цене с учетом роли пользователя.
        Оптимизировано: использует Exists subquery вместо JOIN для избежания
        декартова произведения.
        """
        from django.db.models import Exists, OuterRef

        from .models import ProductVariant

        if value is None or value < 0:
            return queryset

        # Сохраняем значение для использования в qs property
        # Это будет объединено с max_price и in_stock в одном subquery
        if not hasattr(self, "_variant_filters"):
            self._variant_filters = Q()

        request = self.request
        if not request or not request.user.is_authenticated:
            self._variant_filters &= Q(retail_price__gte=value)
        else:
            user_role = request.user.role
            if user_role == "wholesale_level1":
                self._variant_filters &= Q(opt1_price__gte=value) | Q(opt1_price__isnull=True, retail_price__gte=value)
            elif user_role == "wholesale_level2":
                self._variant_filters &= Q(opt2_price__gte=value) | Q(opt2_price__isnull=True, retail_price__gte=value)
            elif user_role == "wholesale_level3":
                self._variant_filters &= Q(opt3_price__gte=value) | Q(opt3_price__isnull=True, retail_price__gte=value)
            elif user_role == "trainer":
                self._variant_filters &= Q(trainer_price__gte=value) | Q(
                    trainer_price__isnull=True, retail_price__gte=value
                )
            elif user_role == "federation_rep":
                self._variant_filters &= Q(federation_price__gte=value) | Q(
                    federation_price__isnull=True, retail_price__gte=value
                )
            else:
                self._variant_filters &= Q(retail_price__gte=value)

        return queryset

    def filter_max_price(self, queryset, name, value):
        """
        Фильтр по максимальной цене с учетом роли пользователя.
        Оптимизировано: накапливает условия для единого subquery.
        """
        if value is None or value < 0:
            return queryset

        if not hasattr(self, "_variant_filters"):
            self._variant_filters = Q()

        request = self.request
        if not request or not request.user.is_authenticated:
            self._variant_filters &= Q(retail_price__lte=value)
        else:
            user_role = request.user.role
            if user_role == "wholesale_level1":
                self._variant_filters &= Q(opt1_price__lte=value) | Q(opt1_price__isnull=True, retail_price__lte=value)
            elif user_role == "wholesale_level2":
                self._variant_filters &= Q(opt2_price__lte=value) | Q(opt2_price__isnull=True, retail_price__lte=value)
            elif user_role == "wholesale_level3":
                self._variant_filters &= Q(opt3_price__lte=value) | Q(opt3_price__isnull=True, retail_price__lte=value)
            elif user_role == "trainer":
                self._variant_filters &= Q(trainer_price__lte=value) | Q(
                    trainer_price__isnull=True, retail_price__lte=value
                )
            elif user_role == "federation_rep":
                self._variant_filters &= Q(federation_price__lte=value) | Q(
                    federation_price__isnull=True, retail_price__lte=value
                )
            else:
                self._variant_filters &= Q(retail_price__lte=value)

        return queryset

    def filter_in_stock(self, queryset, name, value):
        """
        Фильтр по наличию товара.
        Оптимизировано: накапливает условия для единого subquery.
        """
        if not hasattr(self, "_variant_filters"):
            self._variant_filters = Q()

        if value:
            self._variant_filters &= Q(stock_quantity__gt=0)
        # Для in_stock=False не добавляем условие - покажем все товары

        return queryset

    @property
    def qs(self):
        """
        Переопределяем qs чтобы применить накопленные variant фильтры одним subquery.
        Это критически важно для производительности!
        """
        from django.db.models import Exists, OuterRef

        from .models import ProductVariant

        queryset = super().qs

        # Применяем накопленные фильтры по вариантам одним Exists subquery
        if hasattr(self, "_variant_filters") and self._variant_filters:
            variant_subquery = ProductVariant.objects.filter(
                product=OuterRef("pk"),
            ).filter(self._variant_filters)

            queryset = queryset.filter(Exists(variant_subquery))

        return queryset

    def filter_search(self, queryset, name, value):
        """Полнотекстовый поиск с поддержкой PostgreSQL FTS и fallback для других БД"""
        if not value:
            return queryset

        # Валидация длины запроса и защита от XSS
        search_query = value.strip()
        if len(search_query) > 100 or "<" in search_query or ">" in search_query:
            return queryset.none()

        if len(search_query) < 2:
            return queryset

        # Импортируем необходимые модели
        # Проверяем тип базы данных
        from django.db import connection
        from django.db.models import Exists, OuterRef

        from .models import ProductVariant

        # Subquery для поиска по SKU в вариантах
        sku_subquery = ProductVariant.objects.filter(
            product=OuterRef("pk"),
            sku__icontains=search_query,
        )

        if connection.vendor == "postgresql":
            # PostgreSQL full-text search с русскоязычной конфигурацией
            # Примечание: sku теперь в ProductVariant, не в Product
            search_vector = (
                SearchVector("name", weight="A", config="russian")
                + SearchVector("short_description", weight="B", config="russian")
                + SearchVector("description", weight="C", config="russian")
            )

            search_query_obj = SearchQuery(search_query, config="russian")

            # Возвращаем результаты с ранжированием по релевантности
            # Поиск по SKU выполняется через Exists subquery к ProductVariant
            return (
                queryset.annotate(
                    search=search_vector,
                    rank=SearchRank(search_vector, search_query_obj),
                )
                .filter(Q(search=search_query_obj) | Exists(sku_subquery))
                .order_by("-rank", "-created_at")
            )
        else:
            # Fallback для SQLite и других БД - простой icontains поиск с приоритизацией
            from django.db.models import Case, IntegerField, Value, When

            # Поиск точного совпадения в названии (высший приоритет)
            exact_name = queryset.filter(name__iexact=search_query)
            # Если найдены точные совпадения, возвращаем их
            if exact_name.exists():
                return exact_name.order_by("-created_at")

            # Поиск частичного совпадения с приоритизацией
            # по полям (регистронезависимый)
            # Примечание: sku теперь в ProductVariant, используем Exists
            name_match = Q(name__icontains=search_query)
            sku_match = Exists(sku_subquery)
            desc_match = Q(short_description__icontains=search_query) | Q(description__icontains=search_query)

            # Применяем фильтр
            results = queryset.filter(name_match | sku_match | desc_match)

            # Добавляем аннотацию для приоритизации и сортируем
            # Для sku_match используем простую проверку через Case
            prioritized_results = results.annotate(
                has_sku_match=Exists(sku_subquery),
                priority=Case(
                    When(name__icontains=search_query, then=Value(1)),
                    When(has_sku_match=True, then=Value(2)),
                    When(
                        Q(short_description__icontains=search_query) | Q(description__icontains=search_query),
                        then=Value(3),
                    ),
                    default=Value(4),
                    output_field=IntegerField(),
                ),
            ).order_by("priority", "-created_at")

            return prioritized_results

    def filter_size(self, queryset, name, value):
        """
        Фильтрация по размеру из JSON поля specifications

        ВАЖНО: Работает только с PostgreSQL. SQLite не поддерживается.
        """
        if not value:
            return queryset

        # Нормализуем значение размера
        size_value = value.strip()
        if not size_value:
            return queryset

        # Создаем Q-объекты для различных вариантов хранения размера в JSON
        size_queries = Q()

        # Вариант 1: {"size": "XL"} - одиночный размер
        size_queries |= Q(specifications__size=size_value)

        # Вариант 3: {"размер": "XL"} - русский ключ
        size_queries |= Q(specifications__размер=size_value)

        # Проверяем, используется ли PostgreSQL для поддержки contains lookup
        is_postgresql = connection.vendor == "postgresql"

        if is_postgresql:
            # Вариант 2: {"sizes": ["M", "L", "XL"]} - массив размеров (PostgreSQL)
            size_queries |= Q(specifications__sizes__contains=[size_value])

            # Вариант 4: {"размеры": ["M", "L", "XL"]} - русский массив (PostgreSQL)
            size_queries |= Q(specifications__размеры__contains=[size_value])

            # Вариант 5: Case-insensitive поиск для строковых значений (PostgreSQL)
            size_queries |= Q(specifications__size__iexact=size_value)
            size_queries |= Q(specifications__размер__iexact=size_value)

        return queryset.filter(size_queries)

    def filter_has_discount(self, queryset, name, value):
        """Фильтр товаров со скидкой (discount_percent не null)"""
        if value:
            # Товары со скидкой
            return queryset.filter(discount_percent__isnull=False)
        else:
            # Товары без скидки
            return queryset.filter(discount_percent__isnull=True)


class CategoryFilter(django_filters.FilterSet):
    """
    Фильтр для категорий
    """

    parent = django_filters.NumberFilter(field_name="parent")
    parent__slug = django_filters.CharFilter(field_name="parent__slug")
    is_active = django_filters.BooleanFilter(field_name="is_active")

    # Фильтр для главной страницы: возвращает категории с sort_order > 0
    is_homepage = django_filters.BooleanFilter(method="filter_is_homepage")

    class Meta:
        model = Category
        fields = ["parent", "parent__slug", "is_active", "is_homepage"]

    def filter_is_homepage(self, queryset, name, value):
        """
        Фильтр для категорий на главной странице.
        Если is_homepage=true, возвращаем категории с sort_order > 0.
        """
        if value:
            return queryset.filter(sort_order__gt=0)
        return queryset

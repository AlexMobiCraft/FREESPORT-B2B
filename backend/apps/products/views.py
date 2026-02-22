"""
Views для каталога товаров
"""

from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db.models import Count, Exists, Min, OuterRef, Prefetch, Q, Sum
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import filters, permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response

from .constants import FEATURED_BRANDS_CACHE_KEY, FEATURED_BRANDS_CACHE_TIMEOUT, FEATURED_BRANDS_MAX_ITEMS
from .filters import CategoryFilter, ProductFilter
from .models import Attribute, AttributeValue, Brand, Category, Product, ProductVariant
from .serializers import (
    AttributeFilterSerializer,
    BrandFeaturedSerializer,
    BrandSerializer,
    CategorySerializer,
    CategoryTreeSerializer,
    ProductDetailSerializer,
    ProductListSerializer,
)
from .services.facets import AttributeFacetService


class CustomPageNumberPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


class BrandPageNumberPagination(CustomPageNumberPagination):
    page_size = 100
    max_page_size = 500


class ProductViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для товаров с фильтрацией, сортировкой и ролевым ценообразованием
    """

    permission_classes = [permissions.AllowAny]  # Каталог доступен всем
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_class = ProductFilter
    # После Epic 13: retail_price и stock_quantity перенесены в ProductVariant
    # Используем аннотации: min_retail_price (мин. цена варианта),
    # total_stock (сумма остатков)
    ordering_fields = ["name", "min_retail_price", "created_at", "total_stock"]
    ordering = ["-created_at"]  # Сортировка по умолчанию (override при search)

    pagination_class = CustomPageNumberPagination

    def get_queryset(self):
        """Оптимизированный QuerySet с предзагрузкой связанных объектов"""
        return (
            Product.objects.filter(is_active=True)
            .select_related("brand", "category")
            .prefetch_related(
                "category__parent",
                # Story 14.5: Prefetch атрибутов для избежания N+1 queries
                Prefetch(
                    "attributes",
                    queryset=AttributeValue.objects.select_related("attribute"),
                    to_attr="prefetched_attributes",
                ),
                # Prefetch первого варианта для получения цен (для списка)
                Prefetch(
                    "variants",
                    queryset=ProductVariant.objects.filter(
                        Q(retail_price__gt=0)
                        | Q(opt1_price__gt=0)
                        | Q(opt2_price__gt=0)
                        | Q(opt3_price__gt=0)
                        | Q(trainer_price__gt=0)
                        | Q(federation_price__gt=0)
                    ).order_by("retail_price"),
                    to_attr="first_variant_list",
                ),
            )
            .annotate(
                # Аннотации для использования в ProductListSerializer и сортировки
                total_stock=Sum("variants__stock_quantity"),
                # Min retail_price для сортировки по цене (после Epic 13)
                min_retail_price=Min(
                    "variants__retail_price",
                    filter=Q(variants__retail_price__gt=0),
                ),
                has_stock=Exists(ProductVariant.objects.filter(product=OuterRef("pk"), stock_quantity__gt=0)),
            )
        )

    def get_serializer_class(self):
        """Выбор serializer в зависимости от действия"""
        if self.action == "retrieve":
            return ProductDetailSerializer
        return ProductListSerializer

    @extend_schema(
        summary="Список товаров",
        description=("Получение списка товаров с фильтрацией, сортировкой и ролевым " "ценообразованием"),
        parameters=[
            OpenApiParameter("category_id", OpenApiTypes.INT, description="ID категории"),
            OpenApiParameter(
                "brand",
                OpenApiTypes.STR,
                description=("Бренд (ID или slug). Поддерживает множественный выбор: " "brand=nike,adidas"),
            ),
            OpenApiParameter("min_price", OpenApiTypes.NUMBER, description="Минимальная цена"),
            OpenApiParameter("max_price", OpenApiTypes.NUMBER, description="Максимальная цена"),
            OpenApiParameter("in_stock", OpenApiTypes.BOOL, description="Товары в наличии"),
            OpenApiParameter("is_featured", OpenApiTypes.BOOL, description="Рекомендуемые товары"),
            OpenApiParameter(
                "search",
                OpenApiTypes.STR,
                description=(
                    "Полнотекстовый поиск по названию, описанию, артикулу. "
                    "Поддерживает русский язык, ранжирование по релевантности. "
                    "Мин. 2 символа, макс. 100"
                ),
            ),
            OpenApiParameter(
                "size",
                OpenApiTypes.STR,
                description=("Размер товара из спецификаций (XS, S, M, L, XL, XXL, 38, 40, " "42 и т.д.)"),
            ),
            # Story 11.0: Маркетинговые фильтры для бейджей
            OpenApiParameter("is_hit", OpenApiTypes.BOOL, description="Хиты продаж"),
            OpenApiParameter("is_new", OpenApiTypes.BOOL, description="Новинки"),
            OpenApiParameter("is_sale", OpenApiTypes.BOOL, description="Распродажа"),
            OpenApiParameter("is_promo", OpenApiTypes.BOOL, description="Акции"),
            OpenApiParameter("is_premium", OpenApiTypes.BOOL, description="Премиум товары"),
            OpenApiParameter(
                "has_discount",
                OpenApiTypes.BOOL,
                description="Товары со скидкой (имеют discount_percent)",
            ),
            OpenApiParameter(
                "ordering",
                OpenApiTypes.STR,
                description=("Сортировка: name, -name, retail_price, -retail_price, " "created_at, -created_at"),
            ),
        ],
        tags=["Products"],
    )
    def list(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """
        Список товаров (оптимизированная версия, без facets по умолчанию)

        Facets были удалены из базового запроса для оптимизации производительности.
        Используйте отдельный endpoint для получения facets если нужно.
        """
        # Получаем стандартный response от родительского класса
        response = super().list(request, *args, **kwargs)

        # Возвращаем пустые facets для совместимости с фронтендом
        response.data["facets"] = {}

        return response

    @extend_schema(
        summary="Детали товара",
        description="Получение детальной информации о товаре",
        tags=["Products"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve с prefetch variants и attributes для оптимизации"""
        # Prefetch уже настроен в get_queryset() (Story 14.5)
        return super().retrieve(request, *args, **kwargs)


class CategoryViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для категорий с поддержкой иерархии
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = CategorySerializer
    lookup_field = "slug"
    filterset_class = CategoryFilter

    # filterset_fields больше не нужен, так как используем filterset_class
    # filterset_fields = ["parent", "parent__slug", "is_active"]

    def get_queryset(self):
        """QuerySet с подсчетом товаров в категориях"""
        return (
            Category.objects.filter(is_active=True)
            .annotate(products_count=Count("products", filter=Q(products__is_active=True)))
            .prefetch_related(
                Prefetch(
                    "children",
                    queryset=Category.objects.filter(is_active=True).annotate(
                        products_count=Count("products", filter=Q(products__is_active=True))
                    ),
                    to_attr="prefetched_children",
                )
            )
            .order_by("sort_order", "name")
        )

    @extend_schema(
        summary="Список категорий",
        description="Получение списка всех категорий с иерархией и количеством товаров",
        tags=["Categories"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Детали категории",
        description=("Получение детальной информации о категории с навигационной цепочкой"),
        tags=["Categories"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)


class CategoryTreeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для дерева категорий (только корневые категории)
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = CategoryTreeSerializer

    def get_queryset(self):
        """Только корневые категории с рекурсивной предзагрузкой дочерних"""
        return (
            Category.objects.filter(is_active=True, parent__isnull=True)
            .annotate(products_count=Count("products", filter=Q(products__is_active=True)))
            .order_by("sort_order", "name")
        )

    @extend_schema(
        summary="Дерево категорий",
        description="Получение иерархического дерева категорий для навигации",
        tags=["Categories"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)


class BrandViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для брендов
    """

    permission_classes = [permissions.AllowAny]
    serializer_class = BrandSerializer
    lookup_field = "slug"
    pagination_class = BrandPageNumberPagination
    filter_backends = [filters.SearchFilter]
    search_fields = ["name"]

    def get_queryset(self):
        """Активные бренды с опциональной фильтрацией по is_featured"""
        qs = Brand.objects.active().order_by("name")
        if self.action != "featured":
            is_featured = self.request.query_params.get("is_featured")
            if is_featured is not None:
                qs = qs.filter(is_featured=is_featured.lower() in ("true", "1"))
        return qs

    @extend_schema(
        summary="Список брендов",
        description="Получение списка всех активных брендов с опциональной фильтрацией по is_featured",
        parameters=[
            OpenApiParameter(
                "is_featured",
                OpenApiTypes.BOOL,
                description="Фильтр по featured-статусу бренда (true/false)",
            ),
        ],
        tags=["Brands"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    @extend_schema(
        summary="Детали бренда",
        description="Получение детальной информации о бренде",
        tags=["Brands"],
    )
    def retrieve(self, request, *args, **kwargs):
        return super().retrieve(request, *args, **kwargs)

    @extend_schema(
        summary="Избранные бренды",
        description=(
            "Получение списка избранных брендов для отображения на главной странице. " "Ответ кэшируется на 1 час."
        ),
        tags=["Brands"],
    )
    @action(detail=False, methods=["get"], url_path="featured", pagination_class=None, filter_backends=[])
    def featured(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        """Список избранных брендов с кэшированием на 1 час (flat JSON list).

        filter_backends=[] intentionally bypasses global SearchFilter because
        this action uses a fixed cache key — applying search params would serve
        stale/wrong cached results. Search is available on the list endpoint.
        """
        cached = cache.get(FEATURED_BRANDS_CACHE_KEY)
        if cached is not None:
            return Response(cached)

        queryset = (
            self.get_queryset()
            .filter(is_featured=True)
            .exclude(Q(image="") | Q(image__isnull=True))[:FEATURED_BRANDS_MAX_ITEMS]
        )

        # Не передаем request в контекст, чтобы в кэш не попадал host из заголовка.
        serializer = BrandFeaturedSerializer(queryset, many=True, context={})
        payload = serializer.data
        cache.set(FEATURED_BRANDS_CACHE_KEY, payload, FEATURED_BRANDS_CACHE_TIMEOUT)
        return Response(payload)


class AttributeFilterViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet для фильтров каталога на основе активных атрибутов.

    Возвращает список активных атрибутов для построения фильтров в каталоге.
    Каждый атрибут содержит список значений для формирования UI фильтров.

    Endpoints:
    - GET /api/v1/catalog/filters/ - список активных атрибутов
    - GET /api/v1/catalog/filters/{id}/ - детали атрибута

    Query Parameters:
    - include_inactive: true/false - включить неактивные атрибуты (только для staff)
    """

    serializer_class = AttributeFilterSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """
        Получить queryset атрибутов для фильтрации.

        По умолчанию возвращает только активные атрибуты (is_active=True).
        Staff users могут использовать параметр include_inactive=true
        для получения всех атрибутов.

        Returns:
            QuerySet[Attribute]: Отфильтрованный queryset атрибутов
        """
        queryset = Attribute.objects.prefetch_related("values")

        # Проверяем параметр include_inactive
        include_inactive = self.request.query_params.get("include_inactive", "false")

        if include_inactive.lower() == "true" and self.request.user.is_staff:
            # Staff users могут видеть все атрибуты
            return queryset.order_by("name")

        # По умолчанию только активные атрибуты
        return queryset.filter(is_active=True).order_by("name")

    @extend_schema(
        summary="Фильтры каталога",
        description=(
            "Получение списка активных атрибутов для фильтрации товаров в каталоге. "
            "Возвращает атрибуты с их значениями для построения UI фильтров."
        ),
        parameters=[
            OpenApiParameter(
                "include_inactive",
                OpenApiTypes.BOOL,
                description=(
                    "Включить неактивные атрибуты (только для staff users). "
                    "Для обычных пользователей параметр игнорируется."
                ),
            ),
        ],
        tags=["Catalog Filters"],
    )
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

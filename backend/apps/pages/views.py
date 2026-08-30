"""
Views для статических страниц
"""

from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .cache_keys import (
    PAGES_LIST_CACHE_TTL,
    get_pages_list_version,
    pages_list_cache_key,
)
from .models import Page
from .serializers import PageSerializer


# Параметры запроса, которые не меняют ни состав, ни порядок списка: пагинация
# нарезает уже готовый общий список, а `format` влияет только на рендерер.
# Всё остальное (`ordering`, `search`, фильтры) обязано идти мимо общего кэша.
CACHE_NEUTRAL_QUERY_PARAMS = frozenset({"page", "page_size", "format"})


def _is_cache_neutral_request(request) -> bool:
    """Можно ли обслужить запрос из общего кэша списка"""
    return all(param in CACHE_NEUTRAL_QUERY_PARAMS for param in request.query_params)


class PagesPagination(PageNumberPagination):
    """Пагинация списка страниц с поддержкой `?page_size`.

    Глобальный `PAGE_SIZE_QUERY_PARAM` в DRF не действует — это атрибут класса
    пагинации, а не настройка (как в `apps.bonuses.views`, `apps.products.views`).
    Без этого класса `?page_size=1000` молча игнорируется, выдача обрезается до
    `PAGE_SIZE` = 20, и middleware фронтенда видит лишь первые 20 CMS-слагов:
    21-я и далее опубликованные страницы начали бы отдавать 404.
    """

    page_size_query_param = "page_size"

    # 1000 — не только потолок параметра, но и ПОДДЕРЖИВАЕМЫЙ ПРЕДЕЛ числа
    # опубликованных CMS-страниц (решение владельца по находке ревью стори 41.0).
    # Middleware фронтенда запрашивает ровно столько и отвергает ответ, обрезанный
    # пагинацией: за пределом оно навсегда уходит в fail-open и настоящие 404
    # исчезают молча. Значение продублировано в `SLUGS_PAGE_SIZE`
    # (`frontend/src/middleware.ts`) — менять нужно в обоих местах сразу, а при
    # реальном приближении к пределу переходить на облегчённый endpoint слагов.
    max_page_size = 1000


class PageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для чтения статических страниц"""

    serializer_class = PageSerializer
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    pagination_class = PagesPagination

    def get_queryset(self):
        """Получить только опубликованные страницы"""
        return Page.objects.filter(is_published=True)

    @extend_schema(
        summary="Получить список страниц",
        description="Возвращает список всех опубликованных статических страниц",
        tags=["Pages"],
    )
    def list(self, request, *args, **kwargs):
        """Получить список страниц с кэшированием.

        Кэшируется ПОЛНЫЙ сериализованный список опубликованных страниц в
        каноническом порядке (`Page.Meta.ordering`), а пагинация применяется к
        нему уже на каждом запросе. Раньше кэшировался готовый ответ под одним
        ключом независимо от параметров: клиент, запросивший `?page_size=1000`,
        получал закэшированную первую страницу из 20 записей (`PAGE_SIZE` DRF).
        Для middleware фронтенда, который по этому списку решает, отдавать ли
        настоящий 404, это означало молчаливый 404 на 21-й и далее CMS-странице.

        Запрос с сортировкой, поиском или фильтрами общий кэш НЕ использует и не
        наполняет: состав и порядок его выдачи другие, и первый такой запрос
        отравил бы список своим порядком — последующие варианты `ordering`
        перестали бы применяться вовсе.

        Ключ данных версионирован (`pages_list_cache_key`). Это закрывает гонку
        с «поздним writer'ом»: запрос, начавший сериализацию до публикации
        страницы, допишет устаревший список под старым ключом, который после
        инвалидации уже никто не читает.
        """
        if not _is_cache_neutral_request(request):
            return super().list(request, *args, **kwargs)

        cache_key = pages_list_cache_key(get_pages_list_version())
        serialized_pages = cache.get(cache_key)

        if serialized_pages is None:
            # Осознанно `get_queryset`, а не `filter_queryset`: в кэш обязан
            # попасть канонический список, не зависящий от параметров запроса.
            serialized_pages = list(self.get_serializer(self.get_queryset(), many=True).data)
            cache.set(cache_key, serialized_pages, PAGES_LIST_CACHE_TTL)

        page = self.paginate_queryset(serialized_pages)
        if page is not None:
            return self.get_paginated_response(page)

        return Response(serialized_pages)

    @extend_schema(
        summary="Получить страницу по slug",
        description="Возвращает содержимое статической страницы по URL slug",
        tags=["Pages"],
    )
    def retrieve(self, request, *args, **kwargs):
        """Получить страницу с кэшированием по предсказуемому ключу"""
        slug = kwargs.get(self.lookup_field)
        cache_key = f"page_detail_{slug}"
        cached = cache.get(cache_key)

        if cached is not None:
            return Response(cached)

        response = super().retrieve(request, *args, **kwargs)
        cache.set(cache_key, response.data, 60 * 60 * 24)
        return response

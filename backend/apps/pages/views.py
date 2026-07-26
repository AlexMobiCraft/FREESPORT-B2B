"""
Views для статических страниц
"""

from django.core.cache import cache
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, viewsets
from rest_framework.response import Response

from .models import Page
from .serializers import PageSerializer


class PageViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet для чтения статических страниц"""

    serializer_class = PageSerializer
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        """Получить только опубликованные страницы"""
        return Page.objects.filter(is_published=True)

    @extend_schema(
        summary="Получить список страниц",
        description="Возвращает список всех опубликованных статических страниц",
        tags=["Pages"],
    )
    def list(self, request, *args, **kwargs):
        """Получить список страниц с кэшированием"""
        cache_key = "pages_list"
        cached_result = cache.get(cache_key)

        if cached_result is None:
            result = super().list(request, *args, **kwargs)
            cache.set(cache_key, result.data, 60 * 60 * 24)  # 24 hours
            return result

        return Response(cached_result)

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

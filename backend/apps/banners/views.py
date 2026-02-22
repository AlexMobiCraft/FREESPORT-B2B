"""
API views для баннеров
"""

from __future__ import annotations

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from . import services
from .serializers import BannerSerializer


class ActiveBannersView(viewsets.ViewSet):
    """
    ViewSet для получения активных баннеров

    Возвращает баннеры, отфильтрованные по роли текущего пользователя
    и отсортированные по приоритету
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Получить активные баннеры",
        description=(
            "Возвращает список активных баннеров для текущего пользователя.\n\n"
            "Фильтрация:\n"
            "- Только активные баннеры (is_active=True)\n"
            "- В пределах дат показа (start_date/end_date)\n"
            "- По роли пользователя из JWT токена или гость\n"
            "- По типу баннера через ?type=hero|marketing\n\n"
            "Сортировка: по приоритету (DESC)"
        ),
        parameters=[
            OpenApiParameter(
                name="type",
                description="Фильтр по типу баннера: hero или marketing",
                required=False,
                type=str,
                enum=["hero", "marketing"],
            ),
        ],
        tags=["Banners"],
        responses={
            200: BannerSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                name="success_example",
                summary="Успешный ответ",
                description="Список активных баннеров для пользователя",
                value=[
                    {
                        "id": 1,
                        "type": "hero",
                        "title": "Новая коллекция 2025",
                        "subtitle": "Эксклюзивные новинки для профессионалов",
                        "image_url": "/media/promos/2025/01/hero.webp",
                        "image_alt": "Баннер новой коллекции",
                        "cta_text": "Перейти в каталог",
                        "cta_link": "/catalog",
                    },
                    {
                        "id": 2,
                        "type": "marketing",
                        "title": "Специальные цены для оптовиков",
                        "subtitle": "Скидки до 30% на весь ассортимент",
                        "image_url": "/media/promos/2025/01/wholesale.webp",
                        "image_alt": "Баннер оптовых цен",
                        "cta_text": "Узнать больше",
                        "cta_link": "/wholesale",
                    },
                ],
                response_only=True,
            ),
        ],
    )
    def list(self, request: Request) -> Response:
        """
        Получить список активных баннеров для текущего пользователя

        Args:
            request: HTTP запрос с информацией о пользователе

        Returns:
            Response с сериализованными баннерами
        """
        banner_type_param = request.query_params.get("type")
        banner_type = services.validate_banner_type(banner_type_param if isinstance(banner_type_param, str) else None)
        role_key = services.get_role_key(request.user)
        cache_key = services.build_cache_key(banner_type, role_key)

        cached_data = services.get_cached_banners(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        banners = services.get_active_banners_queryset(request.user, banner_type)
        serializer = BannerSerializer(banners, many=True, context={"request": request})
        data = serializer.data

        ttl = services.compute_cache_ttl(banner_type, role_key)
        services.cache_banner_response(cache_key, data, ttl)

        return Response(data)

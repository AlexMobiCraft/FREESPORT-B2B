"""
API views для баннеров
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework import permissions, viewsets
from rest_framework.request import Request
from rest_framework.response import Response

from .models import Banner
from .serializers import BannerSerializer

if TYPE_CHECKING:
    from django.db.models import QuerySet


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
            "- По роли пользователя из JWT токена или гость\n\n"
            "Сортировка: по приоритету (DESC)"
        ),
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
                        "title": "Новая коллекция 2025",
                        "subtitle": "Эксклюзивные новинки для профессионалов",
                        "image_url": ("http://example.com/media/banners/2025/01/hero.webp"),
                        "image_alt": "Баннер новой коллекции",
                        "cta_text": "Перейти в каталог",
                        "cta_link": "/catalog",
                    },
                    {
                        "id": 2,
                        "title": "Специальные цены для оптовиков",
                        "subtitle": "Скидки до 30% на весь ассортимент",
                        "image_url": ("http://example.com/media/banners/2025/01/" "wholesale.webp"),
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
        user = request.user if request.user.is_authenticated else None
        banners: QuerySet[Banner] = Banner.get_for_user(user)
        serializer = BannerSerializer(banners, many=True, context={"request": request})
        return Response(serializer.data)

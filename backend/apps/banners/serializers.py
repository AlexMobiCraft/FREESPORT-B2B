"""
Сериализаторы для API баннеров
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from rest_framework import serializers

from .models import Banner

if TYPE_CHECKING:
    from django.http import HttpRequest


class BannerSerializer(serializers.ModelSerializer):
    """
    Сериализатор баннера для публичного API

    Возвращает данные для отображения баннера в Hero-секции главной страницы
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = (
            "id",
            "type",
            "title",
            "subtitle",
            "image_url",
            "image_alt",
            "cta_text",
            "cta_link",
        )
        read_only_fields = (
            "id",
            "type",
            "title",
            "subtitle",
            "image_url",
            "image_alt",
            "cta_text",
            "cta_link",
        )

    def get_image_url(self, obj: Banner) -> str:
        """
        Получить URL изображения баннера

        Возвращает относительный путь для совместимости с SSR
        (избегаем проблем с internal Docker hostnames)

        Args:
            obj: Объект баннера

        Returns:
            Относительный URL изображения или пустая строка
        """
        if obj.image:
            return cast(str, obj.image.url)  # Returns /media/banners/...
        return ""

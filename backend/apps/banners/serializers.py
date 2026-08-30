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
    mobile_image_url = serializers.SerializerMethodField()

    class Meta:
        model = Banner
        fields = (
            "id",
            "type",
            "title",
            "subtitle",
            "image_url",
            "mobile_image_url",
            "image_alt",
            "cta_text",
            "cta_link",
            "is_advertisement",
            "advertiser_name",
            "advertiser_inn",
            "erid",
        )
        read_only_fields = (
            "id",
            "type",
            "title",
            "subtitle",
            "image_url",
            "mobile_image_url",
            "image_alt",
            "cta_text",
            "cta_link",
            "is_advertisement",
            "advertiser_name",
            "advertiser_inn",
            "erid",
        )

    def to_representation(self, instance: Banner) -> dict:
        """
        Скрывает реквизиты рекламодателя у нерекламных баннеров.

        Поля остаются в контракте (состав ключей не меняется), но значения гасятся:
        после снятия галочки «Является рекламой» реквизиты остаются в БД, а ИНН ИП или
        физлица — персональные данные, которым нечего делать в публичном ответе гостям.
        """
        data = super().to_representation(instance)
        if not instance.is_advertisement:
            data["advertiser_name"] = ""
            data["advertiser_inn"] = ""
            data["erid"] = ""
        return data

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

    def get_mobile_image_url(self, obj: Banner) -> str:
        """
        Получить URL мобильного изображения баннера

        Args:
            obj: Объект баннера

        Returns:
            Относительный URL мобильного изображения или пустая строка
        """
        if obj.mobile_image:
            return cast(str, obj.mobile_image.url)
        return ""

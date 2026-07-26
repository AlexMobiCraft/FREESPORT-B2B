"""
Serializers для статических страниц
"""

from rest_framework import serializers

from .models import Page


class PageSerializer(serializers.ModelSerializer):
    """Serializer для статической страницы"""

    class Meta:
        model = Page
        fields = [
            "id",
            "title",
            "slug",
            "content",
            "seo_title",
            "seo_description",
            "updated_at",
        ]
        read_only_fields = ["id", "updated_at"]

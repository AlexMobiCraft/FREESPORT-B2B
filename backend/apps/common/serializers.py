"""
Сериализаторы для общих компонентов FREESPORT
Включает Newsletter и News сериализаторы
"""

from __future__ import annotations

from typing import Any, cast

from rest_framework import serializers

from .models import BlogPost, Category, News, Newsletter


class SubscribeSerializer(serializers.Serializer):
    """
    Сериализатор для подписки на email-рассылку.
    Валидирует email и создает запись в Newsletter.
    """

    email = serializers.EmailField(
        required=True,
        max_length=255,
        help_text="Email адрес для подписки",
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Проверяет существование подписки.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        # Проверка на существующую активную подписку
        if Newsletter.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("Этот email уже подписан на рассылку")

        return value

    def create(self, validated_data: dict[str, Any]) -> Newsletter:
        """
        Создание подписки.
        Если email ранее отписался - реактивируем подписку.
        """
        email = validated_data["email"]

        # Получаем IP и User-Agent из контекста (request)
        request = self.context.get("request")
        ip_address = None
        user_agent = ""

        if request:
            # Получаем IP с учетом proxy (X-Forwarded-For)
            x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(",")[0]
            else:
                ip_address = request.META.get("REMOTE_ADDR")

            user_agent = request.META.get("HTTP_USER_AGENT", "")

        # Проверяем существование неактивной подписки
        try:
            subscription = Newsletter.objects.get(email=email, is_active=False)
            # Реактивируем подписку
            subscription.is_active = True
            subscription.unsubscribed_at = None
            subscription.ip_address = ip_address
            subscription.user_agent = user_agent
            subscription.save(
                update_fields=[
                    "is_active",
                    "unsubscribed_at",
                    "ip_address",
                    "user_agent",
                ]
            )
            return subscription
        except Newsletter.DoesNotExist:
            # Создаем новую подписку
            return Newsletter.objects.create(
                email=email,
                ip_address=ip_address,
                user_agent=user_agent,
            )


class SubscribeResponseSerializer(serializers.Serializer):
    """Сериализатор ответа при успешной подписке."""

    message = serializers.CharField()
    email = serializers.EmailField()


class UnsubscribeSerializer(serializers.Serializer):
    """
    Сериализатор для отписки от email-рассылки.
    Валидирует email и деактивирует подписку.
    """

    email = serializers.EmailField(
        required=True,
        max_length=255,
        help_text="Email адрес для отписки",
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Проверяет существование активной подписки.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        # Проверка на существование активной подписки
        if not Newsletter.objects.filter(email=value, is_active=True).exists():
            raise serializers.ValidationError("Этот email не найден в списке подписчиков или уже отписан")

        return value

    def save(self, **kwargs: Any) -> Newsletter:
        """
        Отписка от рассылки.
        Вызывает метод unsubscribe() модели.
        """
        email = self.validated_data["email"]
        subscription = Newsletter.objects.get(email=email, is_active=True)
        subscription.unsubscribe()
        return subscription


class UnsubscribeResponseSerializer(serializers.Serializer):
    """Сериализатор ответа при успешной отписке."""

    message = serializers.CharField()
    email = serializers.EmailField()


class NewsSerializer(serializers.ModelSerializer):
    """
    Сериализатор новости для публичного API.
    Возвращает только опубликованные поля.
    """

    class Meta:
        model = News
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "image",
            "published_at",
            "created_at",
            "updated_at",
            "author",
            "category",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: News) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data: dict[str, Any] = super().to_representation(instance)

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }

        return data


class BlogPostListSerializer(serializers.ModelSerializer):
    """
    Сериализатор статьи блога для списка (компактный формат).
    Используется в BlogPostListView для отображения превью статей.
    """

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "image",
            "author",
            "category",
            "published_at",
        ]
        read_only_fields = [
            "id",
            "slug",
        ]

    def to_representation(self, instance: BlogPost) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data = cast(dict[str, Any], super().to_representation(instance))

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }
        else:
            data["category"] = None

        return data


class BlogPostDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор статьи блога для детальной страницы (полный формат).
    Используется в BlogPostDetailView для отображения полной статьи.
    Включает все поля, включая content и SEO meta-данные.
    """

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "content",
            "image",
            "author",
            "category",
            "published_at",
            "meta_title",
            "meta_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: BlogPost) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data = cast(dict[str, Any], super().to_representation(instance))

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }
        else:
            data["category"] = None

        return data

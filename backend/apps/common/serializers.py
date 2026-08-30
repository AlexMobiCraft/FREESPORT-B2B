"""
Сериализаторы для общих компонентов FREESPORT
Включает Newsletter и News сериализаторы
"""

from __future__ import annotations

from typing import Any, cast

from django.db import IntegrityError, transaction
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from .models import BlogPost, Category, News, Newsletter
from .utils.consent_audit import get_consent_ip_address, sanitize_consent_user_agent


PDP_CONSENT_REQUIRED = "Необходимо согласие на обработку персональных данных."
ALREADY_SUBSCRIBED = "Этот email уже подписан на рассылку"
ALREADY_SUBSCRIBED_CODE = "already_subscribed"


def already_subscribed_error() -> serializers.ValidationError:
    """Вернуть field-level ошибку подписки с устойчивым machine-code."""
    return serializers.ValidationError(
        {
            "email": [
                ErrorDetail(
                    ALREADY_SUBSCRIBED,
                    code=ALREADY_SUBSCRIBED_CODE,
                )
            ]
        }
    )


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
    pdp_consent = serializers.BooleanField(
        write_only=True,
        required=True,
        error_messages={
            "required": PDP_CONSENT_REQUIRED,
            "invalid": PDP_CONSENT_REQUIRED,
            "null": PDP_CONSENT_REQUIRED,
        },
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Нормализует email перед сохранением.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверить обязательное согласие на обработку ПДн."""
        if not isinstance(self.initial_data, dict):
            raise serializers.ValidationError({"non_field_errors": "Ожидался JSON-объект."})

        # BooleanField коэрсит truthy-строки в True; для 152-ФЗ нужен исходный JSON boolean true.
        if self.initial_data.get("pdp_consent") is not True:
            raise serializers.ValidationError({"pdp_consent": PDP_CONSENT_REQUIRED})
        return attrs

    def create(self, validated_data: dict[str, Any]) -> Newsletter:
        """
        Создание подписки.
        Если email ранее отписался - реактивируем подписку.
        """
        validated_data.pop("pdp_consent", False)
        email = validated_data["email"]

        # Получаем IP и User-Agent из контекста (request)
        request = self.context.get("request")
        ip_address = None
        user_agent = ""

        if request is not None:
            ip_address = get_consent_ip_address(request)
            user_agent = sanitize_consent_user_agent(request.META.get("HTTP_USER_AGENT", ""))

        with transaction.atomic():
            try:
                subscription = Newsletter.objects.select_for_update().get(email=email)
            except Newsletter.DoesNotExist:
                try:
                    return Newsletter.objects.create(
                        email=email,
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
                except IntegrityError as exc:
                    raise already_subscribed_error() from exc

            if subscription.is_active:
                raise already_subscribed_error()

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
        Нормализует email без раскрытия наличия активной подписки.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        return value

    def save(self, **kwargs: Any) -> Newsletter | None:
        """
        Отписка от рассылки.
        Возвращает None, если активной подписки нет, чтобы не раскрывать наличие email.
        """
        email = self.validated_data["email"]
        try:
            subscription = Newsletter.objects.get(email=email, is_active=True)
        except Newsletter.DoesNotExist:
            return None

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

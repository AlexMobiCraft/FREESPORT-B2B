"""Именованные компоненты OpenAPI для ответов `400` эндпоинтов с согласием.

Стори 41.9, четвёртый круг ревью. У `POST /api/v1/subscribe/` и
`POST /api/v1/auth/register/` ответ `400` имеет **две** формы:

1. обычный отказ валидации DRF — плоский объект «поле → список сообщений»;
2. структурированный отказ по устаревшей формулировке согласия —
   `{"error": "consent_text_outdated", "details": {"<поле>": ["<сообщение>"]}}`.

Пока обе описывались общим `type: object` с `additionalProperties: {}`,
`openapi-typescript` выдавал `{ [key: string]: unknown }`: машинный код `error` и
структура `details` в типах не существовали, и фронт разбирал ответ без помощи
компилятора — ровно то место, где ошибка не заметна до продакшена.

Плоская форма не описывается обычным сериализатором: набор её ключей зависит от
запроса, а `Serializer` даёт фиксированный `properties`. Поэтому её схема задаётся
`OpenApiSerializerExtension` — штатный механизм drf-spectacular для подмены
отображения; сам класс-маркер нужен лишь затем, чтобы схема попала в
`components.schemas` под именем и на неё можно было сослаться `$ref` (на голый dict
drf-spectacular ссылки не создаёт).
"""

from __future__ import annotations

from typing import Any

from drf_spectacular.extensions import OpenApiSerializerExtension
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    PolymorphicProxySerializer,
    extend_schema_field,
    extend_schema_serializer,
)
from rest_framework import serializers

from .serializers import CONSENT_TEXT_OUTDATED, CONSENT_TEXT_OUTDATED_CODE


# Имена компонентов вынесены в константы: на них ссылаются тесты и они не должны
# расходиться с `component_name` объявлений ниже.
FIELD_VALIDATION_ERROR_COMPONENT = "FieldValidationErrorResponse"
CONSENT_TEXT_OUTDATED_COMPONENT = "ConsentTextOutdatedResponse"
CONSENT_VALIDATION_ERROR_COMPONENT = "ConsentValidationErrorResponse"

# Значения полей ошибки — всегда списки строк: JSONRenderer разворачивает
# `ErrorDetail` в обычную строку, а DRF собирает их в список даже для одной ошибки.
_MESSAGE_LIST_SCHEMA: dict[str, Any] = {"type": "array", "items": {"type": "string"}}


@extend_schema_serializer(component_name=FIELD_VALIDATION_ERROR_COMPONENT)
class FieldValidationErrorResponseSerializer(serializers.Serializer):
    """Маркер компонента плоских ошибок валидации.

    Полей у класса нет намеренно — схему целиком задаёт расширение ниже.
    """


class FieldValidationErrorResponseExtension(OpenApiSerializerExtension):
    """Отображает маркер в объект со свободными ключами и списками сообщений."""

    target_class = FieldValidationErrorResponseSerializer

    def map_serializer(self, auto_schema: Any, direction: Any) -> dict[str, Any]:
        return {
            "type": "object",
            "description": (
                "Обычный отказ валидации: «имя поля → список сообщений». Набор ключей "
                "зависит от запроса; ошибки уровня объекта приходят под "
                "`non_field_errors`."
            ),
            "additionalProperties": dict(_MESSAGE_LIST_SCHEMA),
        }


@extend_schema_field({"type": "string", "const": CONSENT_TEXT_OUTDATED_CODE})
class ConsentTextOutdatedCodeField(serializers.CharField):
    """Машинный код отказа: единственное допустимое значение, а не «какая-то строка».

    `const` вместо `enum`: значение ровно одно, и `enum` из одного элемента
    drf-spectacular вынес бы отдельным компонентом-перечислением (`postprocess_schema_enums`),
    добавив в контракт имя, за которым ничего не стоит.
    """


@extend_schema_serializer(component_name=CONSENT_TEXT_OUTDATED_COMPONENT)
class ConsentTextOutdatedResponseSerializer(serializers.Serializer):
    """Показанная формулировка согласия устарела или версия не передана.

    Отдельная форма ответа нужна потому, что этот отказ лечится обновлением страницы,
    а не правкой ввода: клиент обязан отличать его от прочей валидации. Узнавать
    случай по тексту сообщения нельзя — формулировку правят.
    """

    error = ConsentTextOutdatedCodeField(
        help_text="Машинный код отказа. Всегда `consent_text_outdated`.",
    )
    details = serializers.DictField(
        child=serializers.ListField(child=serializers.CharField()),
        help_text=(
            "Все ошибки запроса, «поле → список сообщений». Поля версии "
            "(`consent_text_version`, `pdp_consent_text_version`, "
            "`marketing_consent_text_version`) показываются человеку первыми: попутная "
            "ошибка email не должна заслонить требование обновить страницу."
        ),
    )


def consent_validation_error_response(description: str, examples: list[OpenApiExample]) -> OpenApiResponse:
    """`OpenApiResponse` для `400` эндпоинта, принимающего согласие.

    Обе формы связаны через `oneOf` (`resource_type_field_name=None` — дискриминатора
    нет: `error` присутствует только в одной из форм, и `propertyName` по нему был бы
    неверен). Экземпляр `PolymorphicProxySerializer` создаётся на каждый вызов, чтобы
    два эндпоинта не делили один объект-аннотацию; имя компонента общее, поэтому в
    контракте он один.
    """
    return OpenApiResponse(
        response=PolymorphicProxySerializer(
            component_name=CONSENT_VALIDATION_ERROR_COMPONENT,
            serializers=[
                FieldValidationErrorResponseSerializer,
                ConsentTextOutdatedResponseSerializer,
            ],
            resource_type_field_name=None,
            many=False,
        ),
        description=description,
        examples=examples,
    )


def consent_text_outdated_example(field: str, name: str = "consent_text_outdated") -> OpenApiExample:
    """Пример структурированного отказа для конкретного поля версии."""
    return OpenApiExample(
        name=name,
        value={
            "error": CONSENT_TEXT_OUTDATED_CODE,
            "details": {field: [CONSENT_TEXT_OUTDATED]},
        },
        response_only=True,
    )

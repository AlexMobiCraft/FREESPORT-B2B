"""Тесты именованных схем ответа `400` и условной обязательности версии согласия.

Стори 41.9, четвёртый круг ревью. Проверяется схема, которую drf-spectacular строит из
кода, а не закоммиченный `docs/api/openapi.yaml`: расхождение между ними ловит отдельная
команда `check_openapi_sync`, и дублировать её здесь незачем. Здесь охраняется другое —
что контракт вообще ОПИСЫВАЕТ обе формы ответа `400` и правило «версия маркетингового
согласия обязательна при `marketing_consent: true`».

Схема строится один раз на модуль: генерация стоит секунды, а тесты от неё только читают.
"""

from typing import Any, cast

import pytest
from drf_spectacular.generators import SchemaGenerator

from apps.common.api_schema import (
    CONSENT_TEXT_OUTDATED_COMPONENT,
    CONSENT_VALIDATION_ERROR_COMPONENT,
    FIELD_VALIDATION_ERROR_COMPONENT,
)
from apps.common.serializers import CONSENT_TEXT_OUTDATED_CODE


# Оба эндпоинта, принимающие согласие, обязаны отвечать одной и той же парой форм.
CONSENT_ENDPOINTS = ["/subscribe/", "/auth/register/"]


@pytest.fixture(scope="module")
def schema() -> dict[str, Any]:
    """Схема OpenAPI, построенная из текущего кода."""
    # cast: `get_schema` не аннотирован, а `warn_return_any` в mypy.ini включён.
    return cast(dict[str, Any], SchemaGenerator().get_schema(request=None, public=True))


def ref(component: str) -> str:
    """Ссылка на компонент в том виде, в каком её пишет drf-spectacular."""
    return f"#/components/schemas/{component}"


class TestErrorResponseComponents:
    """Две формы ответа `400` объявлены именованными компонентами."""

    def test_field_validation_error_allows_any_field_name(self, schema):
        """Плоская форма — свободные ключи со списками строк.

        Именно поэтому её нельзя описать обычным сериализатором: набор полей зависит
        от запроса. Схему задаёт `OpenApiSerializerExtension`.
        """
        component = schema["components"]["schemas"][FIELD_VALIDATION_ERROR_COMPONENT]

        assert component["type"] == "object"
        assert component["additionalProperties"] == {"type": "array", "items": {"type": "string"}}
        # Фиксированных полей у формы нет — иначе `openapi-typescript` сгенерировал бы
        # тип, требующий именно их.
        assert "properties" not in component

    def test_consent_text_outdated_pins_machine_code(self, schema):
        """У структурированного отказа машинный код зафиксирован значением, а не описанием."""
        component = schema["components"]["schemas"][CONSENT_TEXT_OUTDATED_COMPONENT]

        assert component["properties"]["error"]["const"] == CONSENT_TEXT_OUTDATED_CODE

        # Сверяется структура, а не словарь целиком: у `details` есть ещё
        # `description` из `help_text`, и привязывать тест к тексту подсказки —
        # значит ронять его на любой правке формулировки.
        details = component["properties"]["details"]
        assert details["type"] == "object"
        assert details["additionalProperties"] == {"type": "array", "items": {"type": "string"}}

        assert sorted(component["required"]) == ["details", "error"]

    def test_consent_validation_error_is_one_of_both_forms(self, schema):
        """Общий компонент `400` — `oneOf` из двух именованных форм, без свободного объекта."""
        component = schema["components"]["schemas"][CONSENT_VALIDATION_ERROR_COMPONENT]

        assert component["oneOf"] == [
            {"$ref": ref(FIELD_VALIDATION_ERROR_COMPONENT)},
            {"$ref": ref(CONSENT_TEXT_OUTDATED_COMPONENT)},
        ]

    @pytest.mark.parametrize("path", CONSENT_ENDPOINTS)
    def test_consent_endpoints_reference_named_400_schema(self, schema, path):
        """Ни один из двух эндпоинтов больше не отдаёт `400` свободным объектом."""
        response = schema["paths"][path]["post"]["responses"]["400"]
        content = response["content"]["application/json"]

        assert content["schema"] == {"$ref": ref(CONSENT_VALIDATION_ERROR_COMPONENT)}
        # Примеры остаются: без них Swagger UI не показывает ни одной из форм.
        # Ключ — CamelCase от имени `OpenApiExample`, само имя лежит в `summary`.
        outdated = content["examples"]["ConsentTextOutdated"]
        assert outdated["summary"] == "consent_text_outdated"
        assert outdated["value"]["error"] == CONSENT_TEXT_OUTDATED_CODE


class TestConditionalMarketingVersion:
    """Версия маркетинговой формулировки обязательна ровно при данном согласии."""

    def test_registration_request_declares_conditional_requirement(self, schema):
        """Правило выражено средствами JSON Schema, а не только словами в описании.

        `dependentRequired` здесь не подошёл бы: он срабатывает на само присутствие
        `marketing_consent`, тогда как сервер требует версию только при значении `true`
        (форма без отмеченной галочки шлёт `false` и версию не обязана доказывать).
        """
        component = schema["components"]["schemas"]["UserRegistrationRequest"]

        assert component["if"] == {
            "properties": {"marketing_consent": {"const": True}},
            "required": ["marketing_consent"],
        }
        assert component["then"] == {
            "required": ["marketing_consent_text_version"],
            "properties": {"marketing_consent_text_version": {"minLength": 1}},
        }

    def test_marketing_version_stays_optional_by_default(self, schema):
        """Безусловно обязательной версия не становится: без галочки её не требуют."""
        component = schema["components"]["schemas"]["UserRegistrationRequest"]

        assert "marketing_consent_text_version" not in component["required"]
        assert "pdp_consent_text_version" in component["required"]

"""
Unit и Integration тесты для дедупликации атрибутов (Story 14.3)
"""

from __future__ import annotations

import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from django.db import IntegrityError

from apps.products.models import Attribute, Attribute1CMapping, AttributeValue, AttributeValue1CMapping
from apps.products.services.attribute_import import AttributeImportService
from apps.products.utils.attributes import normalize_attribute_name, normalize_attribute_value

# Глобальный счетчик для обеспечения уникальности в тестах
_unique_counter = 0


def get_unique_suffix() -> str:
    """Генерирует абсолютно уникальный суффикс для тестов"""
    global _unique_counter
    _unique_counter += 1
    return f"{int(time.time() * 1000)}-{_unique_counter}-{uuid.uuid4().hex[:6]}"


@pytest.mark.unit
class TestNormalizeAttributeName:
    """Unit тесты для функции normalize_attribute_name()"""

    def test_lowercase_conversion(self) -> None:
        """Тест приведения к нижнему регистру"""
        assert normalize_attribute_name("Размер") == "размер"
        assert normalize_attribute_name("РАЗМЕР") == "размер"
        assert normalize_attribute_name("РаЗмЕр") == "размер"

    def test_whitespace_removal(self) -> None:
        """Тест удаления пробелов"""
        assert normalize_attribute_name(" Размер ") == "размер"
        assert normalize_attribute_name("Размер  Обуви") == "размеробуви"
        assert normalize_attribute_name("  Тест  123  ") == "тест123"

    def test_special_characters_removal(self) -> None:
        """Тест удаления специальных символов"""
        assert normalize_attribute_name("Размер-XL") == "размерxl"
        assert normalize_attribute_name("Цвет (основной)") == "цветосновнои"  # й → и
        assert normalize_attribute_name("Размер/Рост") == "размеррост"

    def test_empty_string(self) -> None:
        """Тест обработки пустой строки"""
        assert normalize_attribute_name("") == ""

    def test_only_numbers(self) -> None:
        """Тест обработки только цифр"""
        assert normalize_attribute_name("12345") == "12345"

    def test_mixed_content(self) -> None:
        """Тест смешанного контента (буквы, цифры, спецсимволы)"""
        assert normalize_attribute_name("Размер-42 (EU)") == "размер42eu"

    def test_unicode_normalization(self) -> None:
        """Тест нормализации unicode символов"""
        # Акценты должны быть удалены
        assert normalize_attribute_name("Café") == "cafe"
        # Немецкий умляут остается (только диакритики удаляются)
        assert normalize_attribute_name("Größe") == "große"


@pytest.mark.unit
class TestNormalizeAttributeValue:
    """Unit тесты для функции normalize_attribute_value()"""

    def test_reuses_same_logic(self) -> None:
        """Тест что normalize_attribute_value использует ту же логику"""
        test_cases = [
            ("XL", "xl"),
            ("Красный", "красныи"),  # й → и при нормализации
            (" Синий ", "синии"),  # й → и при нормализации
            ("42-44", "4244"),
        ]
        for input_val, expected in test_cases:
            assert normalize_attribute_value(input_val) == expected


@pytest.mark.integration
@pytest.mark.django_db
class TestAttribute1CMappingModel:
    """Integration тесты для модели Attribute1CMapping"""

    def test_create_mapping(self) -> None:
        """Тест создания маппинга атрибута из 1С"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Размер-{suffix}",
            type="Справочник",
        )

        mapping = Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"test-{suffix}",
            onec_name="Размер",
            source="goods",
        )

        assert mapping.attribute == attribute
        assert mapping.onec_id == f"test-{suffix}"
        assert mapping.onec_name == "Размер"
        assert mapping.source == "goods"
        assert mapping.created_at is not None

    def test_unique_onec_id_constraint(self) -> None:
        """Тест уникальности onec_id"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute1 = Attribute.objects.create(
            name=f"Размер-{suffix}-1",
            type="Справочник",
        )
        attribute2 = Attribute.objects.create(
            name=f"Размер-{suffix}-2",
            type="Справочник",
        )

        onec_id = f"duplicate-test-{suffix}"
        Attribute1CMapping.objects.create(
            attribute=attribute1,
            onec_id=onec_id,
            onec_name="Размер 1",
            source="goods",
        )

        # Попытка создать второй маппинг с тем же onec_id
        with pytest.raises(IntegrityError):
            Attribute1CMapping.objects.create(
                attribute=attribute2,
                onec_id=onec_id,
                onec_name="Размер 2",
                source="goods",
            )

    def test_cascade_deletion(self) -> None:
        """Тест каскадного удаления маппингов при удалении атрибута"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Цвет-{suffix}",
            type="Справочник",
        )

        mapping = Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"test-cascade-{suffix}",
            onec_name="Цвет",
            source="goods",
        )

        mapping_id = mapping.id
        attribute.delete()

        # Маппинг должен быть удален из-за CASCADE
        assert not Attribute1CMapping.objects.filter(id=mapping_id).exists()

    def test_str_representation(self) -> None:
        """Тест строкового представления маппинга"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Материал-{suffix}",
            type="Справочник",
        )

        mapping = Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"test-str-{suffix}",
            onec_name="МАТЕРИАЛ ВЕРХА",
            source="goods",
        )

        expected = f"МАТЕРИАЛ ВЕРХА (test-str-{suffix}) → Материал-{suffix}"
        assert str(mapping) == expected


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeModelUpdates:
    """Тесты обновленной модели Attribute с новыми полями"""

    def test_normalized_name_auto_generation(self) -> None:
        """Тест автоматической генерации normalized_name"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Размер-{suffix}",
            type="Справочник",
        )

        # Normalized_name удаляет дефисы из suffix
        expected = normalize_attribute_name(f"Размер-{suffix}")
        assert attribute.normalized_name == expected

    def test_normalized_name_uniqueness(self) -> None:
        """Тест уникальности normalized_name"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        Attribute.objects.create(
            name=f"Размер-{suffix}",
            type="Справочник",
        )

        # Попытка создать атрибут с тем же normalized_name
        with pytest.raises(IntegrityError):
            Attribute.objects.create(
                name=f"РАЗМЕР-{suffix}",  # Та же нормализация
                type="Справочник",
            )

    def test_is_active_default_false(self) -> None:
        """Тест что is_active по умолчанию False"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Цвет-{suffix}",
            type="Справочник",
        )

        assert attribute.is_active is False

    def test_is_active_can_be_set_true(self) -> None:
        """Тест что is_active можно установить в True"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Материал-{suffix}",
            type="Справочник",
            is_active=True,
        )

        assert attribute.is_active is True

    def test_slug_generation_with_normalized_name(self) -> None:
        """Тест что slug генерируется корректно"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Размер Обуви-{suffix}",
            type="Справочник",
        )

        # Slug должен быть транслитерацией
        assert attribute.slug.startswith("razmer-obuvi")
        # normalized_name без пробелов и дефисов
        expected = normalize_attribute_name(f"Размер Обуви-{suffix}")
        assert attribute.normalized_name == expected

    def test_related_name_onec_mappings(self) -> None:
        """Тест что related_name работает корректно"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Бренд-{suffix}",
            type="Справочник",
        )

        Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"mapping1-{suffix}",
            onec_name="Бренд 1",
            source="goods",
        )
        Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"mapping2-{suffix}",
            onec_name="БРЕНД 2",
            source="offers",
        )

        # Проверяем reverse relation
        assert attribute.onec_mappings.count() == 2
        assert set(attribute.onec_mappings.values_list("source", flat=True)) == {
            "goods",
            "offers",
        }


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeValueModelUpdates:
    """Тесты для AttributeValue с дедупликацией"""

    def test_normalized_value_auto_generation(self) -> None:
        """Тест автоматической генерации normalized_value"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Цвет-{suffix}",
            type="Справочник",
        )

        value = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Красный-{suffix}",
        )

        # Normalized_value удаляет дефисы
        expected = normalize_attribute_value(f"Красный-{suffix}")
        assert value.normalized_value == expected

    def test_normalized_value_uniqueness_per_attribute(self) -> None:
        """Тест уникальности normalized_value в рамках одного атрибута"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Размер-{suffix}",
            type="Справочник",
        )

        AttributeValue.objects.create(
            attribute=attribute,
            value=f"XL-{suffix}",
        )

        # Попытка создать значение с той же нормализацией
        with pytest.raises(IntegrityError):
            AttributeValue.objects.create(
                attribute=attribute,
                value=f"xl-{suffix}",  # Та же нормализация
            )

    def test_different_attributes_can_have_same_normalized_value(self) -> None:
        """Тест что разные атрибуты могут иметь одинаковые normalized_value"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute1 = Attribute.objects.create(
            name=f"Цвет-{suffix}",
            type="Справочник",
        )
        attribute2 = Attribute.objects.create(
            name=f"Материал-{suffix}",
            type="Справочник",
        )

        value1 = AttributeValue.objects.create(
            attribute=attribute1,
            value=f"Красный-{suffix}",
        )
        value2 = AttributeValue.objects.create(
            attribute=attribute2,
            value=f"красный-{suffix}",  # Та же нормализация, но другой атрибут
        )

        # Оба значения должны существовать
        assert value1.normalized_value == value2.normalized_value
        assert AttributeValue.objects.filter(normalized_value=value1.normalized_value).count() == 2


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeValue1CMappingModel:
    """Integration тесты для модели AttributeValue1CMapping"""

    def test_create_value_mapping(self) -> None:
        """Тест создания маппинга значения атрибута из 1С"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Размер-{suffix}",
            type="Справочник",
        )
        value = AttributeValue.objects.create(
            attribute=attribute,
            value=f"XL-{suffix}",
        )

        mapping = AttributeValue1CMapping.objects.create(
            attribute_value=value,
            onec_id=f"test-value-{suffix}",
            onec_value="XL",
            source="goods",
        )

        assert mapping.attribute_value == value
        assert mapping.onec_id == f"test-value-{suffix}"
        assert mapping.onec_value == "XL"
        assert mapping.source == "goods"

    def test_unique_onec_id_constraint_for_values(self) -> None:
        """Тест уникальности onec_id для значений"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Цвет-{suffix}",
            type="Справочник",
        )
        value1 = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Красный-{suffix}",
        )
        value2 = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Синий-{suffix}",
        )

        onec_id = f"duplicate-value-{suffix}"
        AttributeValue1CMapping.objects.create(
            attribute_value=value1,
            onec_id=onec_id,
            onec_value="Красный",
            source="goods",
        )

        # Попытка создать второй маппинг с тем же onec_id
        with pytest.raises(IntegrityError):
            AttributeValue1CMapping.objects.create(
                attribute_value=value2,
                onec_id=onec_id,
                onec_value="Синий",
                source="goods",
            )

    def test_cascade_deletion_for_values(self) -> None:
        """Тест каскадного удаления маппингов при удалении значения"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Материал-{suffix}",
            type="Справочник",
        )
        value = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Хлопок-{suffix}",
        )

        mapping = AttributeValue1CMapping.objects.create(
            attribute_value=value,
            onec_id=f"test-cascade-value-{suffix}",
            onec_value="Хлопок",
            source="goods",
        )

        mapping_id = mapping.id
        value.delete()

        # Маппинг должен быть удален
        assert not AttributeValue1CMapping.objects.filter(id=mapping_id).exists()

    def test_str_representation_for_value_mapping(self) -> None:
        """Тест строкового представления маппинга значения"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Бренд-{suffix}",
            type="Справочник",
        )
        value = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Nike-{suffix}",
        )

        mapping = AttributeValue1CMapping.objects.create(
            attribute_value=value,
            onec_id=f"test-str-value-{suffix}",
            onec_value="NIKE",
            source="goods",
        )

        expected = f"NIKE (test-str-value-{suffix}) → Бренд-{suffix}: Nike-{suffix}"
        assert str(mapping) == expected

    def test_related_name_onec_mappings_for_values(self) -> None:
        """Тест что related_name работает для значений"""
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Сезон-{suffix}",
            type="Справочник",
        )
        value = AttributeValue.objects.create(
            attribute=attribute,
            value=f"Зима-{suffix}",
        )

        AttributeValue1CMapping.objects.create(
            attribute_value=value,
            onec_id=f"mapping-value-1-{suffix}",
            onec_value="Зима",
            source="goods",
        )
        AttributeValue1CMapping.objects.create(
            attribute_value=value,
            onec_id=f"mapping-value-2-{suffix}",
            onec_value="ЗИМА",
            source="offers",
        )

        # Проверяем reverse relation
        assert value.onec_mappings.count() == 2
        assert set(value.onec_mappings.values_list("source", flat=True)) == {
            "goods",
            "offers",
        }


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeImportServiceDeduplication:
    """Integration тесты для AttributeImportService с дедупликацией"""

    def test_deduplication_by_normalized_name(self) -> None:
        """Тест дедупликации атрибутов по normalized_name"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        # Создаем тестовые properties с разным регистром
        properties = [
            {
                "onec_id": f"attr1-{suffix}",
                "name": f"Размер-{suffix}",
                "type": "Справочник",
                "values": [],
            },
            {
                "onec_id": f"attr2-{suffix}",
                "name": f"РАЗМЕР-{suffix}",  # Тот же normalized_name
                "type": "Справочник",
                "values": [],
            },
        ]

        service = AttributeImportService(source="goods", dry_run=False)
        service._save_properties(properties)

        # Должен быть создан только 1 атрибут
        assert Attribute.objects.filter(normalized_name=normalize_attribute_name(f"Размер-{suffix}")).count() == 1

        # Должно быть создано 2 маппинга
        assert Attribute1CMapping.objects.filter(onec_id__in=[f"attr1-{suffix}", f"attr2-{suffix}"]).count() == 2

        # Проверяем статистику
        stats = service.get_stats()
        assert stats["attributes_created"] == 1
        assert stats["attributes_deduplicated"] == 1
        assert stats["mappings_created"] == 2

    def test_value_deduplication_within_attribute(self) -> None:
        """Тест дедупликации значений атрибута"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        # Создаем тестовые properties со значениями
        properties = [
            {
                "onec_id": f"attr-{suffix}",
                "name": f"Цвет-{suffix}",
                "type": "Справочник",
                "values": [
                    {"onec_id": f"val1-{suffix}", "value": f"Красный-{suffix}"},
                    {
                        "onec_id": f"val2-{suffix}",
                        "value": f"красный-{suffix}",
                    },  # Дубликат
                    {
                        "onec_id": f"val3-{suffix}",
                        "value": f"КРАСНЫЙ-{suffix}",
                    },  # Дубликат
                ],
            },
        ]

        service = AttributeImportService(source="goods", dry_run=False)
        service._save_properties(properties)

        # Должно быть создано только 1 значение
        attribute = Attribute.objects.get(normalized_name=normalize_attribute_name(f"Цвет-{suffix}"))
        assert attribute.values.count() == 1

        # Должно быть создано 3 маппинга значений
        assert (
            AttributeValue1CMapping.objects.filter(
                onec_id__in=[f"val1-{suffix}", f"val2-{suffix}", f"val3-{suffix}"]
            ).count()
            == 3
        )

        # Проверяем статистику
        stats = service.get_stats()
        assert stats["values_created"] == 1
        assert stats["values_deduplicated"] == 2
        assert stats["value_mappings_created"] == 3

    def test_different_sources_create_separate_mappings(self) -> None:
        """Тест что разные источники создают отдельные маппинги"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        properties = [
            {
                "onec_id": f"attr-{suffix}",
                "name": f"Бренд-{suffix}",
                "type": "Справочник",
                "values": [],
            },
        ]

        # Импорт из goods
        service_goods = AttributeImportService(source="goods", dry_run=False)
        service_goods._save_properties(properties)

        # Импорт из offers (тот же onec_id, но другой source)
        properties[0]["onec_id"] = f"attr-offers-{suffix}"
        service_offers = AttributeImportService(source="offers", dry_run=False)
        service_offers._save_properties(properties)

        # Должен быть создан 1 атрибут
        attribute = Attribute.objects.get(normalized_name=normalize_attribute_name(f"Бренд-{suffix}"))

        # Должно быть 2 маппинга с разными source
        assert attribute.onec_mappings.count() == 2
        assert set(attribute.onec_mappings.values_list("source", flat=True)) == {
            "goods",
            "offers",
        }

    def test_dry_run_mode_does_not_save(self) -> None:
        """Тест что dry_run режим не сохраняет данные"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        properties = [
            {
                "onec_id": f"attr-dry-{suffix}",
                "name": f"TestAttr-{suffix}",
                "type": "Справочник",
                "values": [
                    {"onec_id": f"val-dry-{suffix}", "value": f"TestValue-{suffix}"},
                ],
            },
        ]

        # Импорт в dry_run режиме
        service = AttributeImportService(source="goods", dry_run=True)
        service._save_properties(properties)

        # Не должно быть создано атрибутов
        assert not Attribute.objects.filter(normalized_name=normalize_attribute_name(f"TestAttr-{suffix}")).exists()

        # Не должно быть создано маппингов
        assert not Attribute1CMapping.objects.filter(onec_id=f"attr-dry-{suffix}").exists()

    def test_new_attributes_created_with_is_active_false(self) -> None:
        """Тест что новые атрибуты создаются с is_active=False"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        properties = [
            {
                "onec_id": f"attr-inactive-{suffix}",
                "name": f"NewAttribute-{suffix}",
                "type": "Справочник",
                "values": [],
            },
        ]

        service = AttributeImportService(source="goods", dry_run=False)
        service._save_properties(properties)

        # Атрибут должен быть создан с is_active=False
        attribute = Attribute.objects.get(normalized_name=normalize_attribute_name(f"NewAttribute-{suffix}"))
        assert attribute.is_active is False

    def test_existing_mapping_reuses_attribute(self) -> None:
        """Тест что существующий маппинг переиспользует атрибут"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        # Создаем атрибут и маппинг вручную
        attribute = Attribute.objects.create(
            name=f"ExistingAttr-{suffix}",
            type="Справочник",
        )
        Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"existing-{suffix}",
            onec_name=f"ExistingAttr-{suffix}",
            source="goods",
        )

        # Пытаемся импортировать тот же onec_id
        properties = [
            {
                "onec_id": f"existing-{suffix}",
                "name": f"ExistingAttr-{suffix}",
                "type": "Справочник",
                "values": [],
            },
        ]

        service = AttributeImportService(source="goods", dry_run=False)
        service._save_properties(properties)

        # Не должно быть создано новых атрибутов
        stats = service.get_stats()
        assert stats["attributes_created"] == 0
        assert stats["attributes_deduplicated"] == 0
        assert stats["mappings_created"] == 0  # Маппинг уже существовал

    def test_complex_import_scenario(self) -> None:
        """Комплексный тест импорта с множественной дедупликацией"""
        from apps.products.services.attribute_import import AttributeImportService
        from tests.conftest import get_unique_suffix

        suffix = get_unique_suffix()

        # Сложный сценарий: 2 атрибута с дубликатами, каждый со значениями
        properties = [
            {
                "onec_id": f"size1-{suffix}",
                "name": f"Размер-{suffix}",
                "type": "Справочник",
                "values": [
                    {"onec_id": f"xl1-{suffix}", "value": f"XL-{suffix}"},
                    {"onec_id": f"xl2-{suffix}", "value": f"xl-{suffix}"},  # Дубликат
                ],
            },
            {
                "onec_id": f"size2-{suffix}",
                "name": f"РАЗМЕР-{suffix}",  # Дубликат атрибута
                "type": "Справочник",
                "values": [
                    {
                        "onec_id": f"xl3-{suffix}",
                        "value": f"XL-{suffix}",
                    },  # Дубликат значения
                    {"onec_id": f"l1-{suffix}", "value": f"L-{suffix}"},
                ],
            },
        ]

        service = AttributeImportService(source="goods", dry_run=False)
        service._save_properties(properties)

        # Должен быть создан 1 атрибут
        assert Attribute.objects.filter(normalized_name=normalize_attribute_name(f"Размер-{suffix}")).count() == 1

        attribute = Attribute.objects.get(normalized_name=normalize_attribute_name(f"Размер-{suffix}"))

        # Должно быть создано 2 уникальных значения (XL и L)
        assert attribute.values.count() == 2

        # Проверяем статистику
        stats = service.get_stats()
        assert stats["attributes_created"] == 1
        assert stats["attributes_deduplicated"] == 1
        assert stats["mappings_created"] == 2
        assert stats["values_created"] == 2
        assert stats["values_deduplicated"] == 2  # xl и XL дедуплицированы
        assert stats["value_mappings_created"] == 4


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeImportServiceValidation:
    """Тесты валидации и обработки ошибок в AttributeImportService"""

    def test_import_from_directory_raises_on_nonexistent(self) -> None:
        """
        Тест что import_from_directory выбрасывает исключение
        для несуществующей директории
        """
        service = AttributeImportService(source="goods", dry_run=False)

        with pytest.raises(FileNotFoundError, match="Directory not found"):
            service.import_from_directory("/nonexistent/path")

    def test_import_from_directory_raises_on_file_not_dir(self, tmp_path: Path) -> None:
        """
        Тест что import_from_directory выбрасывает исключение
        если путь - файл, а не директория
        """
        # Создаем временный файл
        temp_file = tmp_path / "test.txt"
        temp_file.write_text("test")

        service = AttributeImportService(source="goods", dry_run=False)

        with pytest.raises(ValueError, match="Path is not a directory"):
            service.import_from_directory(str(temp_file))

    def test_import_from_directory_returns_stats_on_no_xml(self, tmp_path: Path) -> None:
        """Тест что import_from_directory возвращает stats если нет XML файлов"""
        # Создаем пустую директорию
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        service = AttributeImportService(source="goods", dry_run=False)
        stats = service.import_from_directory(str(empty_dir))

        assert stats["attributes_created"] == 0
        assert stats["errors"] == 0

    def test_validate_file_raises_on_nonexistent(self) -> None:
        """Тест что _validate_file выбрасывает исключение для несуществующего файла"""
        service = AttributeImportService(source="goods", dry_run=False)

        with pytest.raises(FileNotFoundError, match="File not found"):
            service._validate_file("/nonexistent/file.xml")

    def test_validate_file_raises_on_empty_file(self, tmp_path: Path) -> None:
        """Тест что _validate_file выбрасывает исключение для пустого файла"""
        # Создаем пустой файл
        empty_file = tmp_path / "empty.xml"
        empty_file.write_text("")

        service = AttributeImportService(source="goods", dry_run=False)

        with pytest.raises(ValueError, match="is empty"):
            service._validate_file(str(empty_file))

    def test_import_from_file_increments_errors_on_invalid_xml(self, tmp_path: Path) -> None:
        """Тест что import_from_file увеличивает счетчик ошибок при невалидном XML"""
        # Создаем файл с невалидным XML
        invalid_xml = tmp_path / "invalid.xml"
        invalid_xml.write_text("<invalid><unclosed>")

        service = AttributeImportService(source="goods", dry_run=False)

        with pytest.raises(ET.ParseError):
            service.import_from_file(str(invalid_xml))

        assert service.stats["errors"] == 1

    def test_import_from_directory_continues_on_file_error(self, tmp_path: Path) -> None:
        """
        Тест что import_from_directory продолжает обработку
        после ошибки в одном файле
        """
        # Создаем директорию с двумя файлами - один с ошибкой парсинга
        test_dir = tmp_path / "test"
        test_dir.mkdir()

        # Невалидный XML (ParseError)
        invalid_xml = test_dir / "a_invalid.xml"  # a_ чтобы обработался первым
        invalid_xml.write_text("<invalid><unclosed>")

        # Валидный XML с одним атрибутом
        suffix = "test_continues"
        valid_xml = test_dir / "z_valid.xml"  # z_ чтобы обработался вторым
        valid_xml.write_text(
            f"""<?xml version="1.0" encoding="UTF-8"?>
            <КоммерческаяИнформация xmlns="urn:1C.ru:commerceml_3">
                <Классификатор>
                    <Ид>classifier-{suffix}</Ид>
                    <Наименование>Classifier</Наименование>
                    <Свойства>
                        <Свойство>
                            <Ид>attr-{suffix}</Ид>
                            <Наименование>Size</Наименование>
                            <ТипЗначений>Строка</ТипЗначений>
                        </Свойство>
                    </Свойства>
                </Классификатор>
            </КоммерческаяИнформация>"""
        )

        service = AttributeImportService(source="goods", dry_run=False)
        stats = service.import_from_directory(str(test_dir))

        # Ошибка учитывается дважды: в import_from_file и в import_from_directory
        assert stats["errors"] == 2
        assert stats["attributes_created"] == 1  # Атрибут из valid.xml создан


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeAdminActions:
    """Тесты для admin actions в AttributeAdmin"""

    def test_activate_attributes_action(self) -> None:
        """Тест массовой активации атрибутов через admin action"""
        from django.contrib.admin.sites import site
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from apps.products.admin import AttributeAdmin

        User = get_user_model()

        # Создаем суперпользователя
        admin_user = User.objects.create_superuser(
            email=f"admin-{get_unique_suffix()}@test.com",
            password="test123",
        )

        # Создаем неактивные атрибуты
        suffix = get_unique_suffix()
        attr1 = Attribute.objects.create(
            name=f"Color-{suffix}",
            type="text",
            is_active=False,
        )
        attr2 = Attribute.objects.create(
            name=f"Size-{suffix}",
            type="text",
            is_active=False,
        )

        # Создаем request с messages storage
        factory = RequestFactory()
        request = factory.post("/admin/products/attribute/")
        request.user = admin_user
        # Добавляем фейковое messages storage
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        admin_instance = AttributeAdmin(Attribute, site)
        queryset = Attribute.objects.filter(id__in=[attr1.id, attr2.id])

        # Выполняем action
        admin_instance.activate_attributes(request, queryset)

        # Проверяем что атрибуты активированы
        attr1.refresh_from_db()
        attr2.refresh_from_db()
        assert attr1.is_active is True
        assert attr2.is_active is True

    def test_deactivate_attributes_action(self) -> None:
        """Тест массовой деактивации атрибутов через admin action"""
        from django.contrib.admin.sites import site
        from django.contrib.auth import get_user_model
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.test import RequestFactory

        from apps.products.admin import AttributeAdmin

        User = get_user_model()

        admin_user = User.objects.create_superuser(
            email=f"admin-{get_unique_suffix()}@test.com",
            password="test123",
        )

        # Создаем активные атрибуты
        suffix = get_unique_suffix()
        attr1 = Attribute.objects.create(
            name=f"Color-{suffix}",
            type="text",
            is_active=True,
        )
        attr2 = Attribute.objects.create(
            name=f"Size-{suffix}",
            type="text",
            is_active=True,
        )

        # Создаем request с messages storage
        factory = RequestFactory()
        request = factory.post("/admin/products/attribute/")
        request.user = admin_user
        setattr(request, "session", "session")
        messages = FallbackStorage(request)
        setattr(request, "_messages", messages)

        admin_instance = AttributeAdmin(Attribute, site)
        queryset = Attribute.objects.filter(id__in=[attr1.id, attr2.id])

        admin_instance.deactivate_attributes(request, queryset)

        attr1.refresh_from_db()
        attr2.refresh_from_db()
        assert attr1.is_active is False
        assert attr2.is_active is False


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeAdminDisplay:
    """Тесты для display методов в AttributeAdmin"""

    def test_values_count_display(self) -> None:
        """Тест отображения количества значений атрибута"""
        from django.contrib.admin.sites import site

        from apps.products.admin import AttributeAdmin

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Size-{suffix}",
            type="text",
        )

        # Создаем значения
        AttributeValue.objects.create(attribute=attribute, value=f"S-{suffix}")
        AttributeValue.objects.create(attribute=attribute, value=f"M-{suffix}")
        AttributeValue.objects.create(attribute=attribute, value=f"L-{suffix}")

        admin_instance = AttributeAdmin(Attribute, site)
        count = admin_instance.values_count(attribute)

        assert count == 3

    def test_mappings_count_display(self) -> None:
        """Тест отображения количества маппингов 1С"""
        from django.contrib.admin.sites import site

        from apps.products.admin import AttributeAdmin

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Size-{suffix}",
            type="text",
        )

        # Создаем маппинги
        Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"1c-id-1-{suffix}",
            onec_name=f"Size-1-{suffix}",
            source="goods",
        )
        Attribute1CMapping.objects.create(
            attribute=attribute,
            onec_id=f"1c-id-2-{suffix}",
            onec_name=f"SIZE-2-{suffix}",
            source="offers",
        )

        admin_instance = AttributeAdmin(Attribute, site)
        count = admin_instance.mappings_count(attribute)

        assert count == 2


@pytest.mark.integration
@pytest.mark.django_db
class TestAttributeValueAdminDisplay:
    """Тесты для display методов в AttributeValueAdmin"""

    def test_value_mappings_count_display(self) -> None:
        """Тест отображения количества маппингов для значения атрибута"""
        from django.contrib.admin.sites import site

        from apps.products.admin import AttributeValueAdmin

        suffix = get_unique_suffix()
        attribute = Attribute.objects.create(
            name=f"Size-{suffix}",
            type="text",
        )
        attr_value = AttributeValue.objects.create(attribute=attribute, value=f"Large-{suffix}")

        # Создаем маппинги значений
        AttributeValue1CMapping.objects.create(
            attribute_value=attr_value,
            onec_id=f"1c-val-1-{suffix}",
            onec_value=f"L-{suffix}",
            source="goods",
        )
        AttributeValue1CMapping.objects.create(
            attribute_value=attr_value,
            onec_id=f"1c-val-2-{suffix}",
            onec_value=f"Large-{suffix}",
            source="offers",
        )

        admin_instance = AttributeValueAdmin(AttributeValue, site)
        count = admin_instance.mappings_count(attr_value)

        assert count == 2

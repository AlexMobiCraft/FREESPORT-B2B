# Generated manually for Story 14.3: Attribute Deduplication Clean Slate
# This migration deletes all existing attributes and values to prepare for reimport with deduplication

from __future__ import annotations

import logging

from django.db import migrations

logger = logging.getLogger(__name__)


def clean_slate_attributes(apps, schema_editor) -> None:
    """
    Удаляет все существующие атрибуты и значения для чистого реимпорта.

    КРИТИЧНО: После этой миграции необходимо выполнить полный реимпорт атрибутов из 1С:
    docker-compose -f docker/docker-compose.yml exec backend python manage.py import_attributes --file-type=all
    """
    Attribute = apps.get_model("products", "Attribute")
    AttributeValue = apps.get_model("products", "AttributeValue")

    attr_count = Attribute.objects.count()
    value_count = AttributeValue.objects.count()

    # Удаление всех значений атрибутов
    AttributeValue.objects.all().delete()

    # Удаление всех атрибутов
    Attribute.objects.all().delete()

    logger.warning(
        f"Clean Slate Migration: Удалено {attr_count} атрибутов и {value_count} значений. "
        f"ТРЕБУЕТСЯ реимпорт данных из 1С командой: "
        f"python manage.py import_attributes --file-type=all"
    )


def reverse_clean_slate(apps, schema_editor) -> None:
    """
    Откат невозможен - данные уже удалены.
    При откате необходимо выполнить реимпорт из 1С.
    """
    logger.warning(
        "Reverse Clean Slate Migration: Откат невозможен. "
        "Данные были удалены в forward migration. "
        "Необходимо выполнить реимпорт из 1С."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0028_attribute_deduplication_step1"),
    ]

    operations = [
        migrations.RunPython(clean_slate_attributes, reverse_clean_slate),
    ]

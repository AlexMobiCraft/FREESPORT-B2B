# Generated manually for Story 14.3.2: Finalize AttributeValue Schema
# This migration makes normalized_value NOT NULL and removes old onec_id field

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0031_attribute_value_deduplication_step1"),
    ]

    operations = [
        # Step 1: Make normalized_value NOT NULL
        # Safe because database is empty after clean slate
        migrations.AlterField(
            model_name="attributevalue",
            name="normalized_value",
            field=models.CharField(
                verbose_name="Нормализованное значение",
                max_length=255,
                blank=False,
                null=False,
                db_index=True,
                help_text="Нормализованное значение для дедупликации",
            ),
        ),
        # Step 2: Remove old onec_id field
        # Replaced by AttributeValue1CMapping model
        migrations.RemoveField(
            model_name="attributevalue",
            name="onec_id",
        ),
    ]

# Generated manually for Story 14.3: Finalize Attribute Schema
# This migration makes normalized_name NOT NULL and removes old onec_id field

from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0029_clean_slate_attributes"),
    ]

    operations = [
        # Step 1: Make normalized_name NOT NULL
        # Safe because database is empty after clean slate
        migrations.AlterField(
            model_name="attribute",
            name="normalized_name",
            field=models.CharField(
                verbose_name="Нормализованное название",
                max_length=255,
                unique=True,
                blank=False,
                null=False,
                db_index=True,
                help_text="Нормализованное название для дедупликации атрибутов",
            ),
        ),
        # Step 2: Remove old onec_id field
        # Replaced by Attribute1CMapping model
        migrations.RemoveField(
            model_name="attribute",
            name="onec_id",
        ),
    ]

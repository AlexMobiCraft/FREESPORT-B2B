"""
Migration: Rename Brand.logo → Brand.image, add Brand.is_featured

Story 33.1: Brand Model & Admin Updates
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0042_importsession_unique_active_session_key"),
    ]

    operations = [
        migrations.RenameField(
            model_name="brand",
            old_name="logo",
            new_name="image",
        ),
        migrations.AddField(
            model_name="brand",
            name="is_featured",
            field=models.BooleanField(
                default=False,
                verbose_name="Показывать на главной",
            ),
        ),
    ]

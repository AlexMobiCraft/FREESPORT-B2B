"""
Migration: Make Brand.slug unique

Story 33.1 review follow-up: Ensure slug uniqueness to prevent 500 errors
on duplicate slugs in API.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0043_rename_logo_to_image_add_is_featured"),
    ]

    operations = [
        migrations.AlterField(
            model_name="brand",
            name="slug",
            field=models.SlugField(
                max_length=255,
                unique=True,
                verbose_name="Slug",
            ),
        ),
    ]

# Generated manually for Story 5.1

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add paid_at and shipped_at fields for 1C status import."""

    dependencies = [
        ("orders", "0010_add_export_skipped_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="paid_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Дата оплаты"
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="shipped_at",
            field=models.DateTimeField(
                blank=True, null=True, verbose_name="Дата отгрузки"
            ),
        ),
    ]

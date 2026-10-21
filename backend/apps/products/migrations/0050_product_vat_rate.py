from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0049_productvariant_warehouse_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="vat_rate",
            field=models.DecimalField(
                blank=True,
                db_index=True,
                decimal_places=2,
                help_text=(
                    "Ставка НДС базового товара из goods.xml. "
                    "Используется как устойчивый источник для вариантов при раздельном импорте 1С."
                ),
                max_digits=5,
                null=True,
                verbose_name="Ставка НДС (%)",
            ),
        ),
    ]

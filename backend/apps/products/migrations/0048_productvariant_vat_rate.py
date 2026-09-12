from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("products", "0047_category_icon"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="vat_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text=(
                    "Ставка НДС в % (22 — импортные товары ИП Семерюк, "
                    "5 — российские товары ИП Терещенко). "
                    "Заполняется автоматически при импорте из 1С (<СтавкаНДС>). "
                    "Если не заполнено, используется DEFAULT_VAT_RATE из настроек."
                ),
                max_digits=5,
                null=True,
                verbose_name="Ставка НДС (%)",
            ),
        ),
    ]

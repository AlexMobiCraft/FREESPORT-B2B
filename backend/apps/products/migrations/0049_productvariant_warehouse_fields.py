from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0048_productvariant_vat_rate"),
    ]

    operations = [
        migrations.AddField(
            model_name="productvariant",
            name="warehouse_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="GUID склада из rests.xml, по которому определяется организация и ставка НДС",
                max_length=64,
                null=True,
                verbose_name="Идентификатор склада 1С",
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="warehouse_name",
            field=models.CharField(
                blank=True,
                help_text="Человекочитаемое имя склада 1С, например '1 СДВ склад'",
                max_length=255,
                null=True,
                verbose_name="Склад",
            ),
        ),
    ]

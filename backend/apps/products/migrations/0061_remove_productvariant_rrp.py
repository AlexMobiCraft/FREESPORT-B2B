"""РРЦ = розничная цена из 1С: удаление ProductVariant.rrp.

Вид цен 1С «РРЦ» импорт пишет в retail_price, а колонка rrp хранила устаревшие
числа. Виды цен с маппингом rrp переводятся в «без маппинга», чтобы до следующей
загрузки priceLists в админке не висел недопустимый выбор: process_price_types
перемаппит такой вид в retail_price сам.
"""

from django.db import migrations, models


def unmap_rrp_price_types(apps, schema_editor):
    PriceType = apps.get_model("products", "PriceType")
    PriceType.objects.filter(product_field="rrp").update(product_field="")


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0060_dealer_price"),
    ]

    operations = [
        migrations.RunPython(unmap_rrp_price_types, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="productvariant",
            name="rrp",
        ),
        migrations.AlterField(
            model_name="pricetype",
            name="product_field",
            field=models.CharField(
                choices=[
                    ("retail_price", "Розничная цена"),
                    ("opt1_price", "Оптовая цена уровень 1"),
                    ("opt2_price", "Оптовая цена уровень 2"),
                    ("opt3_price", "Оптовая цена уровень 3"),
                    ("opt4_price", "Оптовая цена уровень 4"),
                    ("trainer_price", "Цена для тренера"),
                    ("federation_price", "Цена для представителя федерации"),
                    ("vip_price", "Цена VIP"),
                    ("special_price", "Специальная цена"),
                    ("dealer_price", "Дилерская цена"),
                    ("msrp", "Максимальная рекомендованная цена"),
                    ("promo_price", "Акционная цена"),
                ],
                help_text="Поле Product, в которое мапится эта цена",
                max_length=50,
                verbose_name="Поле в модели Product",
            ),
        ),
    ]

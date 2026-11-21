"""
Маркировка рекламы на баннерах (ФЗ «О рекламе»).

Все поля добавляются с дефолтами и blank=True — существующие строки
получают is_advertisement=False и пустые реквизиты без даунтайма.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("banners", "0006_banner_mobile_image"),
    ]

    operations = [
        migrations.AddField(
            model_name="banner",
            name="is_advertisement",
            field=models.BooleanField(
                default=False,
                help_text="Показывать на баннере метку «Реклама» с реквизитами рекламодателя",
                verbose_name="Является рекламой",
            ),
        ),
        migrations.AddField(
            model_name="banner",
            name="advertiser_name",
            field=models.CharField(
                blank=True,
                help_text='Например: ООО "Прайм Спорт Рус". Обязательно, если баннер помечен как реклама',
                max_length=255,
                verbose_name="Наименование рекламодателя",
            ),
        ),
        migrations.AddField(
            model_name="banner",
            name="advertiser_inn",
            field=models.CharField(
                blank=True,
                help_text="10 цифр для юрлиц, 12 — для ИП и физлиц. Обязательно, если баннер помечен как реклама",
                max_length=12,
                verbose_name="ИНН рекламодателя",
            ),
        ),
        migrations.AddField(
            model_name="banner",
            name="erid",
            field=models.CharField(
                blank=True,
                help_text="Идентификатор рекламного креатива из ОРД. Необязателен",
                max_length=64,
                verbose_name="Токен ERID",
            ),
        ),
    ]

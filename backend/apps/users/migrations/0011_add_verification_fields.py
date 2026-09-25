# Generated manually for Story 3.2.2

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0010_add_onec_guid_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="last_sync_from_1c",
            field=models.DateTimeField(
                blank=True,
                help_text="Дата и время последнего импорта данных из 1С",
                null=True,
                verbose_name="Последняя синхронизация из 1С",
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="verification_status",
            field=models.CharField(
                choices=[
                    ("unverified", "Не верифицирован"),
                    ("verified", "Верифицирован"),
                    ("pending", "Ожидает верификации"),
                ],
                default="unverified",
                help_text="Статус верификации клиента из 1С",
                max_length=20,
                verbose_name="Статус верификации",
            ),
        ),
    ]

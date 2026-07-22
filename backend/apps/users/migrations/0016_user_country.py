# Generated for Manager Region Routing feature

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0015_add_customer_code"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="country",
            field=models.CharField(
                choices=[
                    ("Россия", "Россия"),
                    ("Беларусь", "Беларусь"),
                    ("Казахстан", "Казахстан"),
                ],
                default="Россия",
                help_text="Страна регистрации B2B-клиента (для маршрутизации на менеджера)",
                max_length=20,
                verbose_name="Страна",
            ),
        ),
    ]

# Роль unregistered для контрагентов 1С без портального аккаунта

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0016_user_country"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="role",
            field=models.CharField(
                choices=[
                    ("retail", "Розничный покупатель"),
                    ("wholesale_level1", "Оптовик уровень 1"),
                    ("wholesale_level2", "Оптовик уровень 2"),
                    ("wholesale_level3", "Оптовик уровень 3"),
                    ("trainer", "Тренер/Фитнес-клуб"),
                    ("federation_rep", "Представитель федерации"),
                    ("admin", "Администратор"),
                    ("unregistered", "Не зарегистрирован на портале"),
                ],
                default="retail",
                max_length=20,
                verbose_name="Роль пользователя",
            ),
        ),
    ]

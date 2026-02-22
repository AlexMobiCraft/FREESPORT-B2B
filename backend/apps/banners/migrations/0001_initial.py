# Generated manually for banners app

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Banner",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "title",
                    models.CharField(
                        help_text="Основной заголовок баннера",
                        max_length=200,
                        verbose_name="Заголовок",
                    ),
                ),
                (
                    "subtitle",
                    models.CharField(
                        blank=True,
                        help_text="Дополнительный текст под заголовком",
                        max_length=500,
                        verbose_name="Подзаголовок",
                    ),
                ),
                (
                    "image",
                    models.ImageField(
                        help_text="Рекомендуемый размер: 1920×600px",
                        upload_to="banners/%Y/%m/",
                        verbose_name="Изображение",
                    ),
                ),
                (
                    "image_alt",
                    models.CharField(
                        blank=True,
                        help_text="Alt-текст для accessibility",
                        max_length=200,
                        verbose_name="Alt-текст изображения",
                    ),
                ),
                (
                    "cta_text",
                    models.CharField(
                        help_text="Текст call-to-action кнопки",
                        max_length=50,
                        verbose_name="Текст кнопки",
                    ),
                ),
                (
                    "cta_link",
                    models.CharField(
                        help_text="URL для перехода по клику",
                        max_length=200,
                        verbose_name="Ссылка кнопки",
                    ),
                ),
                (
                    "show_to_guests",
                    models.BooleanField(
                        default=False,
                        help_text="Показывать неавторизованным пользователям",
                        verbose_name="Показывать гостям",
                    ),
                ),
                (
                    "show_to_authenticated",
                    models.BooleanField(
                        default=False,
                        help_text="Показывать авторизованным пользователям (роль retail)",
                        verbose_name="Показывать авторизованным",
                    ),
                ),
                (
                    "show_to_trainers",
                    models.BooleanField(
                        default=False,
                        help_text="Показывать пользователям с ролью trainer",
                        verbose_name="Показывать тренерам",
                    ),
                ),
                (
                    "show_to_wholesale",
                    models.BooleanField(
                        default=False,
                        help_text="Показывать пользователям с ролями wholesale_level1-3",
                        verbose_name="Показывать оптовикам",
                    ),
                ),
                (
                    "show_to_federation",
                    models.BooleanField(
                        default=False,
                        help_text="Показывать пользователям с ролью federation_rep",
                        verbose_name="Показывать представителям федераций",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        default=True,
                        help_text="Отключить/включить баннер",
                        verbose_name="Активен",
                    ),
                ),
                (
                    "priority",
                    models.IntegerField(
                        default=0,
                        help_text="Баннеры с большим приоритетом показываются первыми",
                        verbose_name="Приоритет",
                    ),
                ),
                (
                    "start_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="Баннер начнёт показываться с этой даты",
                        null=True,
                        verbose_name="Дата начала показа",
                    ),
                ),
                (
                    "end_date",
                    models.DateTimeField(
                        blank=True,
                        help_text="Баннер перестанет показываться после этой даты",
                        null=True,
                        verbose_name="Дата окончания показа",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(auto_now=True, verbose_name="Дата обновления"),
                ),
            ],
            options={
                "verbose_name": "Баннер",
                "verbose_name_plural": "Баннеры",
                "db_table": "banners",
                "ordering": ["-priority", "-created_at"],
            },
        ),
    ]

# Generated for Manager Region Routing feature

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0016_userconsent_review_fixes"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManagerRoutingRule",
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
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True,
                        help_text="Дата и время создания записи",
                        verbose_name="Дата создания",
                    ),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True,
                        help_text="Дата и время последнего обновления записи",
                        verbose_name="Дата обновления",
                    ),
                ),
                (
                    "match_type",
                    models.CharField(
                        choices=[
                            ("inn_region", "Код субъекта РФ (по ИНН)"),
                            ("country", "Страна"),
                            ("fallback", "Резерв (fallback)"),
                        ],
                        db_index=True,
                        help_text="По коду субъекта РФ (первые 2 цифры ИНН), по стране или резерв",
                        max_length=20,
                        verbose_name="Тип совпадения",
                    ),
                ),
                (
                    "match_value",
                    models.CharField(
                        blank=True,
                        help_text='2-значный код региона ("23"), название страны ("Беларусь") или "default" для резерва',
                        max_length=50,
                        verbose_name="Значение",
                    ),
                ),
                (
                    "manager_name",
                    models.CharField(
                        blank=True,
                        help_text="Имя менеджера для персонализации письма",
                        max_length=100,
                        verbose_name="Имя менеджера",
                    ),
                ),
                (
                    "manager_email",
                    models.EmailField(
                        help_text="Адрес, на который уходит уведомление о регистрации",
                        max_length=254,
                        verbose_name="Email менеджера",
                    ),
                ),
                (
                    "federal_district",
                    models.CharField(
                        blank=True,
                        help_text="Справочно: округ / зона ответственности",
                        max_length=30,
                        verbose_name="Федеральный округ",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Неактивные правила исключаются из маршрутизации",
                        verbose_name="Активно",
                    ),
                ),
            ],
            options={
                "verbose_name": "Правило маршрутизации менеджеров",
                "verbose_name_plural": "Правила маршрутизации менеджеров",
                "ordering": ["match_type", "match_value", "manager_email"],
                "indexes": [
                    models.Index(
                        fields=["match_type", "match_value", "is_active"],
                        name="common_mrr_type_val_act_idx",
                    ),
                ],
            },
        ),
    ]

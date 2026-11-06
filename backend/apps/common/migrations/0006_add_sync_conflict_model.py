# Generated manually for Story 3.2.2

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("common", "0005_add_identify_customer_choices"),
    ]

    operations = [
        migrations.CreateModel(
            name="SyncConflict",
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
                    "conflict_type",
                    models.CharField(
                        choices=[
                            (
                                "portal_registration_blocked",
                                "Регистрация на портале заблокирована",
                            ),
                            ("customer_data", "Конфликт данных клиента"),
                            ("order_data", "Конфликт данных заказа"),
                            ("product_data", "Конфликт данных товара"),
                        ],
                        help_text="Тип конфликта синхронизации",
                        max_length=50,
                        verbose_name="Тип конфликта",
                    ),
                ),
                (
                    "platform_data",
                    models.JSONField(
                        default=dict,
                        help_text="Архив данных из портала до разрешения конфликта",
                        verbose_name="Данные портала",
                    ),
                ),
                (
                    "onec_data",
                    models.JSONField(
                        default=dict,
                        help_text="Данные из 1С, вызвавшие конфликт",
                        verbose_name="Данные 1С",
                    ),
                ),
                (
                    "conflicting_fields",
                    models.JSONField(
                        default=list,
                        help_text="Список полей с различиями",
                        verbose_name="Конфликтующие поля",
                    ),
                ),
                (
                    "resolution_strategy",
                    models.CharField(
                        choices=[
                            ("onec_wins", "1С имеет приоритет"),
                            ("portal_wins", "Портал имеет приоритет"),
                            ("manual", "Ручное разрешение"),
                        ],
                        default="onec_wins",
                        help_text="Стратегия разрешения конфликта",
                        max_length=20,
                        verbose_name="Стратегия разрешения",
                    ),
                ),
                (
                    "is_resolved",
                    models.BooleanField(
                        default=False,
                        help_text="Флаг разрешения конфликта",
                        verbose_name="Разрешен",
                    ),
                ),
                (
                    "resolution_details",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Детали примененных изменений и источник конфликта",
                        verbose_name="Детали разрешения",
                    ),
                ),
                (
                    "resolved_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Дата и время разрешения конфликта",
                        null=True,
                        verbose_name="Дата разрешения",
                    ),
                ),
                (
                    "resolved_by",
                    models.CharField(
                        blank=True,
                        help_text="Кем разрешен конфликт (система или пользователь)",
                        max_length=100,
                        verbose_name="Разрешено",
                    ),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        help_text="Клиент, для которого возник конфликт",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="sync_conflicts",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Клиент",
                    ),
                ),
            ],
            options={
                "verbose_name": "Конфликт синхронизации",
                "verbose_name_plural": "Конфликты синхронизации",
                "db_table": "sync_conflicts",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddIndex(
            model_name="syncconflict",
            index=models.Index(
                fields=["customer", "conflict_type"], name="sync_confli_custome_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="syncconflict",
            index=models.Index(
                fields=["is_resolved", "created_at"], name="sync_confli_is_reso_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="syncconflict",
            index=models.Index(
                fields=["conflict_type", "created_at"], name="sync_confli_conflic_idx"
            ),
        ),
    ]

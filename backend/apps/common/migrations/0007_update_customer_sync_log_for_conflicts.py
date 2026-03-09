# Generated manually for Story 3.2.2

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0006_add_sync_conflict_model"),
    ]

    operations = [
        # Add new operation_type choices for conflict resolution
        migrations.AlterField(
            model_name="customersynclog",
            name="operation_type",
            field=models.CharField(
                choices=[
                    ("created", "Создан"),
                    ("updated", "Обновлен"),
                    ("skipped", "Пропущен"),
                    ("error", "Ошибка"),
                    ("identify_customer", "Идентификация клиента"),
                    ("conflict_resolution", "Разрешение конфликта"),
                    ("notification_failed", "Ошибка отправки уведомления"),
                ],
                max_length=20,
                verbose_name="Тип операции",
            ),
        ),
        # Make session nullable for conflict resolution logs
        migrations.AlterField(
            model_name="customersynclog",
            name="session",
            field=models.ForeignKey(
                blank=True,
                help_text="Сессия импорта (опционально для операций разрешения конфликтов)",
                null=True,
                on_delete=models.deletion.CASCADE,
                related_name="customer_logs",
                to="products.importsession",
                verbose_name="Сессия импорта",
            ),
        ),
    ]

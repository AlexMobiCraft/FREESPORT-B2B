# Generated manually for Story 3.2.1.5
# Добавление новых choices для CustomerSyncLog

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0004_add_customer_sync_log"),
    ]

    operations = [
        # Миграция только обновляет choices в коде, не требует изменений в БД
        # так как поле operation_type и status - это CharField без ограничений на уровне БД
    ]

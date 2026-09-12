# Generated manually for Story 3.2.1.5

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0009_update_user_email_nullable"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="onec_guid",
            field=models.UUIDField(
                blank=True,
                help_text="Уникальный GUID клиента в 1С",
                null=True,
                unique=True,
                verbose_name="GUID в 1С",
            ),
        ),
        # Добавляем индекс для оптимизации производительности (PostgreSQL)
        migrations.RunSQL(
            """
            CREATE INDEX idx_users_onec_guid
            ON users (onec_guid)
            WHERE onec_guid IS NOT NULL;
            """.strip(),
            reverse_sql="DROP INDEX IF EXISTS idx_users_onec_guid;",
        ),
    ]

# Generated manually for user performance optimization

from django.db import connection, migrations


def create_user_indexes(apps, schema_editor):
    """
    Создаем индексы для пользователей с учетом SQLite (DEV) vs PostgreSQL
    """
    db_vendor = connection.vendor

    with connection.cursor() as cursor:
        if db_vendor == "postgresql":
            # PostgreSQL частичные индексы
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS users_b2b_users_idx
                ON users (role, is_verified, is_active)
                WHERE role IN (
                    'wholesale_level1', 'wholesale_level2', 'wholesale_level3',
                    'trainer', 'federation_rep'
                );
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS users_email_active_idx
                ON users (email, is_active)
                WHERE is_active = true;
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS addresses_default_idx
                ON addresses (user_id, address_type, is_default)
                WHERE is_default = true;
            """
            )
        else:
            # SQLite совместимые индексы
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS users_b2b_users_idx
                ON users (role, is_verified, is_active);
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS users_email_active_idx
                ON users (email, is_active);
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS addresses_default_idx
                ON addresses (user_id, address_type, is_default);
            """
            )

        # Общие индексы для всех БД
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS companies_tax_id_idx
            ON companies (tax_id);
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS users_role_idx
            ON users (role);
        """
        )


def drop_user_indexes(apps, schema_editor):
    """
    Удаляем созданные индексы
    """
    with connection.cursor() as cursor:
        cursor.execute("DROP INDEX IF EXISTS users_b2b_users_idx;")
        cursor.execute("DROP INDEX IF EXISTS users_email_active_idx;")
        cursor.execute("DROP INDEX IF EXISTS addresses_default_idx;")
        cursor.execute("DROP INDEX IF EXISTS companies_tax_id_idx;")
        cursor.execute("DROP INDEX IF EXISTS users_role_idx;")


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0002_alter_address_unique_together"),
    ]

    operations = [
        migrations.RunPython(create_user_indexes, drop_user_indexes),
    ]

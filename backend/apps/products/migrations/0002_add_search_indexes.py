# Generated manually for search optimization

from django.db import connection, migrations


def create_search_indexes(apps, schema_editor):
    """
    Создаем индексы в зависимости от типа базы данных
    SQLite (DEV) vs PostgreSQL (PROD)
    """
    db_vendor = connection.vendor

    with connection.cursor() as cursor:
        if db_vendor == "postgresql":
            # PostgreSQL специфичные индексы с полнотекстовым поиском
            cursor.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")
            cursor.execute("CREATE EXTENSION IF NOT EXISTS unaccent;")

            # GIN индекс для полнотекстового поиска
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_search_idx 
                ON products 
                USING GIN(to_tsvector('russian', name || ' ' || COALESCE(description, '') || ' ' || COALESCE(short_description, '')));
            """
            )

            # Триграммные индексы
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_name_trgm_idx 
                ON products 
                USING GIN(name gin_trgm_ops);
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_sku_trgm_idx 
                ON products 
                USING GIN(sku gin_trgm_ops);
            """
            )

            # Частичные индексы с WHERE (PostgreSQL)
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_active_price_idx 
                ON products (is_active, retail_price) 
                WHERE is_active = true;
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_featured_created_idx 
                ON products (is_featured, created_at DESC) 
                WHERE is_active = true;
            """
            )

        else:
            # SQLite совместимые индексы для разработки
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_name_search_idx 
                ON products (name);
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_sku_search_idx 
                ON products (sku);
            """
            )

            # Обычные составные индексы без WHERE clause
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_active_price_idx 
                ON products (is_active, retail_price);
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS products_featured_created_idx 
                ON products (is_featured, created_at DESC);
            """
            )

        # Общие индексы для всех БД
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS products_category_active_idx 
            ON products (category_id, is_active);
        """
        )

        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS products_brand_active_idx 
            ON products (brand_id, is_active);
        """
        )


def drop_search_indexes(apps, schema_editor):
    """
    Удаляем созданные индексы
    """
    with connection.cursor() as cursor:
        # PostgreSQL индексы
        cursor.execute("DROP INDEX IF EXISTS products_search_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_name_trgm_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_sku_trgm_idx;")

        # SQLite индексы
        cursor.execute("DROP INDEX IF EXISTS products_name_search_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_sku_search_idx;")

        # Общие индексы
        cursor.execute("DROP INDEX IF EXISTS products_active_price_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_featured_created_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_category_active_idx;")
        cursor.execute("DROP INDEX IF EXISTS products_brand_active_idx;")


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_search_indexes, drop_search_indexes),
    ]

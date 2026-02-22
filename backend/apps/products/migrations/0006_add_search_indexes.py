# Generated manually for Story 2.8: search-api optimization

from django.db import connection, migrations


def add_search_indexes(apps, schema_editor):
    """Добавляет поисковые индексы в зависимости от типа БД"""
    from django.db import connection, transaction

    # Используем отдельную транзакцию для безопасности
    try:
        with transaction.atomic():
            # Получаем модель Product
            Product = apps.get_model("products", "Product")

            # Проверяем, существует ли таблица более безопасным способом
            table_exists = False
            try:
                # Используем introspection для проверки существования таблицы
                table_names = connection.introspection.table_names()
                table_exists = "products_product" in table_names
            except Exception:
                # Если introspection не работает, пробуем простой запрос
                try:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT 1 FROM products_product LIMIT 1")
                        table_exists = True
                except Exception:
                    table_exists = False

            if not table_exists:
                return  # Таблица ещё не создана, пропускаем создание индексов

            db_vendor = connection.vendor

            with connection.cursor() as cursor:
                if db_vendor == "postgresql":
                    # PostgreSQL - полнотекстовые индексы
                    try:
                        cursor.execute(
                            """
                            CREATE INDEX IF NOT EXISTS products_search_gin_idx ON products_product 
                            USING GIN(to_tsvector('russian', 
                            COALESCE(name, '') || ' ' || COALESCE(short_description, '') || ' ' || 
                            COALESCE(description, '') || ' ' || COALESCE(sku, '')))
                        """
                        )
                    except Exception:
                        pass  # Игнорируем ошибки создания GIN индекса

                    try:
                        cursor.execute(
                            """
                            CREATE INDEX IF NOT EXISTS products_search_category_idx ON products_product 
                            (category_id, is_active) WHERE name IS NOT NULL
                        """
                        )
                    except Exception:
                        pass

                    try:
                        cursor.execute(
                            """
                            CREATE INDEX IF NOT EXISTS products_search_brand_idx ON products_product 
                            (brand_id, is_active) WHERE name IS NOT NULL
                        """
                        )
                    except Exception:
                        pass
                else:
                    # SQLite/other databases - обычные индексы
                    indexes = [
                        "CREATE INDEX IF NOT EXISTS products_search_name_idx ON products_product (name)",
                        "CREATE INDEX IF NOT EXISTS products_search_sku_idx ON products_product (sku)",
                        "CREATE INDEX IF NOT EXISTS products_search_category_idx ON products_product (category_id, is_active)",
                        "CREATE INDEX IF NOT EXISTS products_search_brand_idx ON products_product (brand_id, is_active)",
                    ]

                    for index_sql in indexes:
                        try:
                            cursor.execute(index_sql)
                        except Exception:
                            pass  # Игнорируем ошибки создания отдельных индексов

    except Exception as e:
        # В случае критической ошибки просто пропускаем создание индексов
        # Не поднимаем исключение, чтобы не блокировать миграцию
        pass


def remove_search_indexes(apps, schema_editor):
    """Удаляет поисковые индексы"""
    from django.db import connection, transaction

    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                indexes = [
                    "products_search_gin_idx",
                    "products_search_category_idx",
                    "products_search_brand_idx",
                    "products_search_name_idx",
                    "products_search_sku_idx",
                ]

                for index in indexes:
                    try:
                        cursor.execute(f"DROP INDEX IF EXISTS {index}")
                    except Exception:
                        pass  # Ignore errors if index doesn't exist
    except Exception:
        # В случае критической ошибки просто пропускаем удаление индексов
        pass


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0005_product_specifications"),
    ]

    operations = [
        migrations.RunPython(add_search_indexes, remove_search_indexes),
    ]

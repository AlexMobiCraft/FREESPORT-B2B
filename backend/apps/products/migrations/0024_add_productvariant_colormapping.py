# Generated manually for Story 13.1 - ProductVariant and ColorMapping models
# Migration created due to Docker/DB connection issues on Windows

from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0023_add_images_import_type"),
    ]

    operations = [
        # Create ColorMapping model
        migrations.CreateModel(
            name="ColorMapping",
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
                    "name",
                    models.CharField(
                        help_text="Название цвета из 1С",
                        max_length=100,
                        unique=True,
                        verbose_name="Название цвета",
                    ),
                ),
                (
                    "hex_code",
                    models.CharField(
                        help_text="Hex-код цвета (например: #FF0000)",
                        max_length=7,
                        verbose_name="Hex-код",
                    ),
                ),
                (
                    "swatch_image",
                    models.ImageField(
                        blank=True,
                        help_text="Для градиентов и паттернов",
                        upload_to="colors/",
                        verbose_name="Изображение свотча",
                    ),
                ),
            ],
            options={
                "verbose_name": "Маппинг цвета",
                "verbose_name_plural": "Маппинг цветов",
                "db_table": "color_mappings",
                "ordering": ["name"],
            },
        ),
        # Remove price fields from Product
        migrations.RemoveField(
            model_name="product",
            name="retail_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="opt1_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="opt2_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="opt3_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="trainer_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="federation_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="recommended_retail_price",
        ),
        migrations.RemoveField(
            model_name="product",
            name="max_suggested_retail_price",
        ),
        # Remove inventory fields from Product
        migrations.RemoveField(
            model_name="product",
            name="stock_quantity",
        ),
        migrations.RemoveField(
            model_name="product",
            name="reserved_quantity",
        ),
        migrations.RemoveField(
            model_name="product",
            name="min_order_quantity",
        ),
        migrations.RemoveField(
            model_name="product",
            name="sku",
        ),
        # Remove old image fields from Product
        migrations.RemoveField(
            model_name="product",
            name="main_image",
        ),
        migrations.RemoveField(
            model_name="product",
            name="gallery_images",
        ),
        # Add base_images field to Product
        migrations.AddField(
            model_name="product",
            name="base_images",
            field=models.JSONField(
                blank=True,
                default=list,
                help_text="Общие изображения товара из 1С (используются как fallback для вариантов)",
                verbose_name="Базовые изображения",
            ),
        ),
        # Remove index on Product.stock_quantity (already removed via RemoveField)
        # Add sku index removal was handled by RemoveField
        # Create ProductVariant model
        migrations.CreateModel(
            name="ProductVariant",
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
                    "sku",
                    models.CharField(
                        db_index=True,
                        help_text="Уникальный артикул варианта",
                        max_length=100,
                        unique=True,
                        verbose_name="Артикул SKU",
                    ),
                ),
                (
                    "onec_id",
                    models.CharField(
                        db_index=True,
                        help_text="Составной ID: parent_id#variant_id",
                        max_length=100,
                        unique=True,
                        verbose_name="ID в 1С",
                    ),
                ),
                (
                    "color_name",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Название цвета из 1С",
                        max_length=100,
                        verbose_name="Цвет",
                    ),
                ),
                (
                    "size_value",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        help_text="Значение размера",
                        max_length=50,
                        verbose_name="Размер",
                    ),
                ),
                (
                    "retail_price",
                    models.DecimalField(
                        decimal_places=2,
                        help_text="Цена для роли retail",
                        max_digits=10,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Розничная цена",
                    ),
                ),
                (
                    "opt1_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Цена для роли wholesale_level1",
                        max_digits=10,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Оптовая цена уровень 1",
                    ),
                ),
                (
                    "opt2_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Цена для роли wholesale_level2",
                        max_digits=10,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Оптовая цена уровень 2",
                    ),
                ),
                (
                    "opt3_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Цена для роли wholesale_level3",
                        max_digits=10,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Оптовая цена уровень 3",
                    ),
                ),
                (
                    "trainer_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Цена для роли trainer",
                        max_digits=10,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Цена для тренера",
                    ),
                ),
                (
                    "federation_price",
                    models.DecimalField(
                        blank=True,
                        decimal_places=2,
                        help_text="Цена для роли federation_rep",
                        max_digits=10,
                        null=True,
                        validators=[
                            django.core.validators.MinValueValidator(Decimal("0"))
                        ],
                        verbose_name="Цена для представителя федерации",
                    ),
                ),
                (
                    "stock_quantity",
                    models.PositiveIntegerField(
                        db_index=True,
                        default=0,
                        help_text="Доступное количество на складе",
                        verbose_name="Количество на складе",
                    ),
                ),
                (
                    "reserved_quantity",
                    models.PositiveIntegerField(
                        default=0,
                        help_text="Количество, зарезервированное в корзинах и заказах",
                        verbose_name="Зарезервированное количество",
                    ),
                ),
                (
                    "main_image",
                    models.ImageField(
                        blank=True,
                        help_text="Основное изображение варианта (опционально)",
                        null=True,
                        upload_to="products/variants/",
                        verbose_name="Основное изображение",
                    ),
                ),
                (
                    "gallery_images",
                    models.JSONField(
                        blank=True,
                        default=list,
                        help_text="Список URL дополнительных изображений варианта",
                        verbose_name="Галерея изображений",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text="Доступен для заказа",
                        verbose_name="Активный",
                    ),
                ),
                (
                    "last_sync_at",
                    models.DateTimeField(
                        blank=True,
                        help_text="Время последней синхронизации с 1С",
                        null=True,
                        verbose_name="Последняя синхронизация",
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
                (
                    "product",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="variants",
                        to="products.product",
                        verbose_name="Товар",
                    ),
                ),
            ],
            options={
                "verbose_name": "Вариант товара",
                "verbose_name_plural": "Варианты товаров",
                "db_table": "product_variants",
                "ordering": ["color_name", "size_value"],
            },
        ),
        # Add indexes to ProductVariant
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["product", "is_active"], name="product_var_product_a1b2c3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(fields=["sku"], name="product_var_sku_d4e5f6_idx"),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["onec_id"], name="product_var_onec_id_g7h8i9_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["color_name"], name="product_var_color_n_j1k2l3_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["size_value"], name="product_var_size_va_m4n5o6_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["stock_quantity"], name="product_var_stock_q_p7q8r9_idx"
            ),
        ),
        # Composite index for filtering by characteristics
        migrations.AddIndex(
            model_name="productvariant",
            index=models.Index(
                fields=["color_name", "size_value"],
                name="idx_variant_characteristics",
            ),
        ),
    ]

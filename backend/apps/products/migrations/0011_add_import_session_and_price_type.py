# Generated manually for Story 3.1.1

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0010_add_reserved_quantity_field"),
    ]

    operations = [
        # Add parent_onec_id field to Product model
        migrations.AddField(
            model_name="product",
            name="parent_onec_id",
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text="ID базового товара из goods.xml",
                max_length=100,
                null=True,
                verbose_name="ID родительского товара в 1С",
            ),
        ),
        # Add parent_onec_id index
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["parent_onec_id"], name="products_parent__6fa29e_idx"
            ),
        ),
        # Create ImportSession model
        migrations.CreateModel(
            name="ImportSession",
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
                    "import_type",
                    models.CharField(
                        choices=[
                            ("catalog", "Каталог товаров"),
                            ("stocks", "Остатки товаров"),
                            ("prices", "Цены товаров"),
                            ("customers", "Клиенты"),
                        ],
                        default="catalog",
                        max_length=20,
                        verbose_name="Тип импорта",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("started", "Начато"),
                            ("in_progress", "В процессе"),
                            ("completed", "Завершено"),
                            ("failed", "Ошибка"),
                        ],
                        default="started",
                        max_length=20,
                        verbose_name="Статус",
                    ),
                ),
                (
                    "started_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Начало импорта"
                    ),
                ),
                (
                    "finished_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Окончание импорта"
                    ),
                ),
                (
                    "report_details",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Статистика: created, updated, skipped, errors",
                        verbose_name="Детали отчета",
                    ),
                ),
                (
                    "error_message",
                    models.TextField(blank=True, verbose_name="Сообщение об ошибке"),
                ),
            ],
            options={
                "verbose_name": "Сессия импорта",
                "verbose_name_plural": "Сессии импорта",
                "db_table": "import_sessions",
                "ordering": ["-started_at"],
            },
        ),
        # Add ImportSession indexes
        migrations.AddIndex(
            model_name="importsession",
            index=models.Index(
                fields=["import_type", "status"], name="import_sess_import__2f8c7d_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="importsession",
            index=models.Index(
                fields=["-started_at"], name="import_sess_started_9a3b5e_idx"
            ),
        ),
        # Create PriceType model
        migrations.CreateModel(
            name="PriceType",
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
                    "onec_id",
                    models.CharField(
                        help_text="UUID из priceLists.xml",
                        max_length=100,
                        unique=True,
                        verbose_name="UUID типа цены в 1С",
                    ),
                ),
                (
                    "onec_name",
                    models.CharField(
                        help_text='Например: "Опт 1 (300-600 тыс.руб в квартал)"',
                        max_length=200,
                        verbose_name="Название в 1С",
                    ),
                ),
                (
                    "product_field",
                    models.CharField(
                        choices=[
                            ("retail_price", "Розничная цена"),
                            ("opt1_price", "Оптовая цена уровень 1"),
                            ("opt2_price", "Оптовая цена уровень 2"),
                            ("opt3_price", "Оптовая цена уровень 3"),
                            ("trainer_price", "Цена для тренера"),
                            (
                                "federation_price",
                                "Цена для представителя федерации",
                            ),
                            (
                                "recommended_retail_price",
                                "Рекомендованная розничная цена",
                            ),
                            (
                                "max_suggested_retail_price",
                                "Максимальная рекомендованная цена",
                            ),
                        ],
                        help_text="Поле Product, в которое мапится эта цена",
                        max_length=50,
                        verbose_name="Поле в модели Product",
                    ),
                ),
                (
                    "user_role",
                    models.CharField(
                        blank=True,
                        help_text="Роль пользователя, для которой применяется эта цена",
                        max_length=50,
                        verbose_name="Роль пользователя",
                    ),
                ),
                (
                    "is_active",
                    models.BooleanField(default=True, verbose_name="Активный"),
                ),
                (
                    "created_at",
                    models.DateTimeField(
                        auto_now_add=True, verbose_name="Дата создания"
                    ),
                ),
            ],
            options={
                "verbose_name": "Тип цены",
                "verbose_name_plural": "Типы цен",
                "db_table": "price_types",
                "ordering": ["onec_name"],
            },
        ),
    ]

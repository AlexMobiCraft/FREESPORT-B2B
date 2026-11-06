from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0055_product_article"),
    ]

    operations = [
        migrations.AddField(
            model_name="product",
            name="onec_deleted",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Товар в 1С вне дерева якорной категории или помечен на удаление. "
                    "Ставится и снимается импортом; физически удаляет только команда "
                    "purge_products_outside_root."
                ),
                verbose_name="Скрыт импортом 1С",
            ),
        ),
        migrations.AddField(
            model_name="productvariant",
            name="onec_deleted",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "Предложение в 1С помечено на удаление. Ставится и снимается импортом; "
                    "физически удаляет только команда purge_products_outside_root."
                ),
                verbose_name="Скрыт импортом 1С",
            ),
        ),
        migrations.CreateModel(
            name="OnecExcludedItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "onec_id",
                    models.CharField(
                        help_text="Ид группы или товара либо составной Ид предложения (товар#характеристика)",
                        max_length=255,
                        unique=True,
                        verbose_name="Ид в 1С",
                    ),
                ),
                (
                    "kind",
                    models.CharField(
                        choices=[("group", "Группа"), ("product", "Товар"), ("offer", "Предложение")],
                        db_index=True,
                        max_length=10,
                        verbose_name="Вид объекта",
                    ),
                ),
                ("reason", models.CharField(blank=True, max_length=100, verbose_name="Причина исключения")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Дата обновления")),
            ],
            options={
                "verbose_name": "Исключённый Ид 1С",
                "verbose_name_plural": "Реестр исключённых Ид 1С",
                "db_table": "products_onec_excluded_items",
                "ordering": ["kind", "onec_id"],
            },
        ),
    ]

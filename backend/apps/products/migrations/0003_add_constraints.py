# Generated manually for database constraints

from django.db import migrations, models
from django.db.models import CheckConstraint, Q, UniqueConstraint


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0002_add_search_indexes"),
    ]

    operations = [
        # Check constraints для цен
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(retail_price__gte=0), name="products_retail_price_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(opt1_price__gte=0) | Q(opt1_price__isnull=True),
                name="products_opt1_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(opt2_price__gte=0) | Q(opt2_price__isnull=True),
                name="products_opt2_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(opt3_price__gte=0) | Q(opt3_price__isnull=True),
                name="products_opt3_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(trainer_price__gte=0) | Q(trainer_price__isnull=True),
                name="products_trainer_price_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(federation_price__gte=0) | Q(federation_price__isnull=True),
                name="products_federation_price_positive",
            ),
        ),
        # Check constraints для складских остатков
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(stock_quantity__gte=0), name="products_stock_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="product",
            constraint=CheckConstraint(
                condition=Q(min_order_quantity__gte=1),
                name="products_min_order_quantity_positive",
            ),
        ),
        # Уникальные ограничения
        migrations.AddConstraint(
            model_name="brand",
            constraint=UniqueConstraint(
                fields=["name"],
                condition=Q(is_active=True),
                name="brands_unique_active_name",
            ),
        ),
        migrations.AddConstraint(
            model_name="category",
            constraint=UniqueConstraint(
                fields=["name", "parent"],
                condition=Q(is_active=True),
                name="categories_unique_active_name_parent",
            ),
        ),
    ]

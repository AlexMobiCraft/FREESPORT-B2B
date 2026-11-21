from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):

    dependencies = [
        ("users", "0015_add_customer_code"),
        ("orders", "0012_add_vat_split_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="CustomerOrderSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID"),
                ),
                ("customer_code", models.CharField(max_length=5, verbose_name="Код клиента")),
                ("year", models.PositiveSmallIntegerField(verbose_name="Год")),
                (
                    "last_sequence",
                    models.PositiveSmallIntegerField(default=0, verbose_name="Последняя последовательность"),
                ),
            ],
            options={
                "verbose_name": "Счетчик заказов клиента",
                "verbose_name_plural": "Счетчики заказов клиентов",
                "db_table": "customer_order_sequences",
            },
        ),
        migrations.AddField(
            model_name="order",
            name="customer_code_snapshot",
            field=models.CharField(blank=True, db_index=True, max_length=5, verbose_name="Снимок customer_code"),
        ),
        migrations.AddField(
            model_name="order",
            name="customer_year_sequence",
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                verbose_name="Порядковый номер заказа клиента в году",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="order_year",
            field=models.PositiveSmallIntegerField(blank=True, db_index=True, null=True, verbose_name="Год заказа"),
        ),
        migrations.AddField(
            model_name="order",
            name="suborder_sequence",
            field=models.PositiveSmallIntegerField(blank=True, null=True, verbose_name="Порядковый номер субзаказа"),
        ),
        migrations.AddConstraint(
            model_name="customerordersequence",
            constraint=models.UniqueConstraint(
                fields=("customer_code", "year"),
                name="uniq_customer_order_sequence",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=Q(
                    ("is_master", True),
                    ("order_year__isnull", False),
                    ("customer_year_sequence__isnull", False),
                )
                & ~Q(("customer_code_snapshot", "")),
                fields=("customer_code_snapshot", "order_year", "customer_year_sequence"),
                name="uniq_master_order_customer_year_seq",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.UniqueConstraint(
                condition=Q(("is_master", False), ("parent_order__isnull", False), ("suborder_sequence__isnull", False)),
                fields=("parent_order", "suborder_sequence"),
                name="uniq_suborder_parent_sequence",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.CheckConstraint(
                condition=Q(("customer_year_sequence__isnull", True))
                | (Q(("customer_year_sequence__gte", 1)) & Q(("customer_year_sequence__lte", 999))),
                name="check_customer_year_sequence_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="order",
            constraint=models.CheckConstraint(
                condition=Q(("suborder_sequence__isnull", True)) | Q(("suborder_sequence__gte", 1)),
                name="check_suborder_sequence_positive",
            ),
        ),
    ]

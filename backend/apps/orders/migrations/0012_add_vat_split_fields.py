# Generated for Story 34-1: Order/OrderItem — новые поля для VAT-разбивки

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Add VAT split fields: parent_order, is_master, vat_group to Order; vat_rate to OrderItem."""

    dependencies = [
        ("orders", "0011_add_payment_shipment_dates"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="parent_order",
            field=models.ForeignKey(
                blank=True,
                help_text="Заполнено только для дочерних субзаказов",
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="sub_orders",
                to="orders.order",
                verbose_name="Мастер-заказ",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="is_master",
            field=models.BooleanField(
                default=True,
                help_text="True — заказ видит клиент; False — технический субзаказ для 1С",
                verbose_name="Мастер-заказ",
            ),
        ),
        migrations.AddField(
            model_name="order",
            name="vat_group",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Ставка НДС группы товаров в этом субзаказе (5 или 22)",
                max_digits=5,
                null=True,
                verbose_name="Группа НДС (%)",
            ),
        ),
        migrations.AddField(
            model_name="orderitem",
            name="vat_rate",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text="Снимок ставки НДС варианта на момент создания заказа",
                max_digits=5,
                null=True,
                verbose_name="Ставка НДС (%)",
            ),
        ),
    ]

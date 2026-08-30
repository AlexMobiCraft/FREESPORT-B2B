from django.db import migrations


def delete_all_test_orders(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    CustomerOrderSequence = apps.get_model("orders", "CustomerOrderSequence")
    # Delete suborders first to avoid FK constraint issues, then masters
    Order.objects.filter(is_master=False).delete()
    Order.objects.filter(is_master=True).delete()
    CustomerOrderSequence.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0013_order_numbering_v2"),
    ]

    operations = [
        migrations.RunPython(delete_all_test_orders, migrations.RunPython.noop),
    ]

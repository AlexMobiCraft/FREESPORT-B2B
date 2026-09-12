# Справочник видов цен: «Опт 4» для роли wholesale_level4

from django.db import migrations

OPT4_ONEC_ID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"
OPT4_ONEC_NAME = "Опт 4 (до 50 тыс.руб в квартал)"


def seed_opt4_price_type(apps, schema_editor):
    """Заводит вид цен «Опт 4». Идемпотентно: повторный прогон обновляет запись."""
    PriceType = apps.get_model("products", "PriceType")
    PriceType.objects.update_or_create(
        onec_id=OPT4_ONEC_ID,
        defaults={
            "onec_name": OPT4_ONEC_NAME,
            "product_field": "opt4_price",
            "user_role": "wholesale_level4",
            "is_active": True,
        },
    )


def remove_opt4_price_type(apps, schema_editor):
    """Удаляет только запись «Опт 4», остальные шесть видов цен не трогает."""
    PriceType = apps.get_model("products", "PriceType")
    PriceType.objects.filter(onec_id=OPT4_ONEC_ID).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0052_add_opt4_price"),
    ]

    operations = [
        migrations.RunPython(seed_opt4_price_type, reverse_code=remove_opt4_price_type),
    ]

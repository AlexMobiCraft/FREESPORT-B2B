# Generated manually for Story 13.1 - Load 20 basic colors into ColorMapping
# Data migration

from django.db import migrations


def load_basic_colors(apps, schema_editor):
    """Load 20 basic colors into ColorMapping table"""
    ColorMapping = apps.get_model("products", "ColorMapping")

    basic_colors = [
        ("Белый", "#FFFFFF"),
        ("Черный", "#000000"),
        ("Красный", "#FF0000"),
        ("Синий", "#0000FF"),
        ("Зеленый", "#00FF00"),
        ("Желтый", "#FFFF00"),
        ("Серый", "#808080"),
        ("Розовый", "#FFC0CB"),
        ("Оранжевый", "#FFA500"),
        ("Фиолетовый", "#800080"),
        ("Коричневый", "#A52A2A"),
        ("Бежевый", "#F5F5DC"),
        ("Бордовый", "#800000"),
        ("Голубой", "#87CEEB"),
        ("Салатовый", "#7FFF00"),
        ("Сиреневый", "#C8A2C8"),
        ("Тёмно-синий", "#00008B"),
        ("Тёмно-серый", "#A9A9A9"),
        ("Светло-серый", "#D3D3D3"),
        ("Золотой", "#FFD700"),
    ]

    for name, hex_code in basic_colors:
        ColorMapping.objects.get_or_create(
            name=name,
            defaults={"hex_code": hex_code},
        )


def reverse_load_colors(apps, schema_editor):
    """Reverse migration - remove basic colors"""
    ColorMapping = apps.get_model("products", "ColorMapping")

    basic_color_names = [
        "Белый",
        "Черный",
        "Красный",
        "Синий",
        "Зеленый",
        "Желтый",
        "Серый",
        "Розовый",
        "Оранжевый",
        "Фиолетовый",
        "Коричневый",
        "Бежевый",
        "Бордовый",
        "Голубой",
        "Салатовый",
        "Сиреневый",
        "Тёмно-синий",
        "Тёмно-серый",
        "Светло-серый",
        "Золотой",
    ]

    ColorMapping.objects.filter(name__in=basic_color_names).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0024_add_productvariant_colormapping"),
    ]

    operations = [
        migrations.RunPython(load_basic_colors, reverse_load_colors),
    ]

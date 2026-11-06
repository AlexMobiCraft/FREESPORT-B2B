# Порядок категорий в каталоге и на главной, согласованный владельцем витрины

from django.db import migrations

# Корни витрины (прямые дети якоря «СПОРТ») — порядок в сайдбаре и на главной
ROOT_ORDER = {
    "3d148366-bd77-11e4-afc8-20cf3073dde3": 1,  # Единоборства
    "3d148353-bd77-11e4-afc8-20cf3073dde3": 2,  # Фитнес и атлетика
    "442337ff-bd77-11e4-afc8-20cf3073dde3": 3,  # Плавание
    "44233835-bd77-11e4-afc8-20cf3073dde3": 4,  # Спортивные игры
    "812018c4-bd77-11e4-afc8-20cf3073dde3": 5,  # Детский транспорт
    "3d148351-bd77-11e4-afc8-20cf3073dde3": 6,  # Бассейны, пляж, аксессуары
    "3d148347-bd77-11e4-afc8-20cf3073dde3": 7,  # Туризм
    "4a88ea7e-bd77-11e4-afc8-20cf3073dde3": 8,  # Спортивные комплексы и батуты
    "4423384a-bd77-11e4-afc8-20cf3073dde3": 9,  # Гимнастика и танцы
    "4a88eab9-bd77-11e4-afc8-20cf3073dde3": 10,  # Зимние товары
    "442337f8-bd77-11e4-afc8-20cf3073dde3": 11,  # Оборудование
}

# Дети «Фитнес и атлетика». На главную не попадают: is_homepage берёт только корни витрины
FITNESS_CHILDREN_ORDER = {
    "9c5bad99-a802-11e7-8151-00155d87f90d": 1,  # Фитнес
    "fbbe1b5c-bd77-11e4-afc8-20cf3073dde3": 2,  # Акссесуары для фитнеса и атлетики (так в 1С)
    "9c5bad95-a802-11e7-8151-00155d87f90d": 3,  # Тяжелая атлетика
    "4a88e9f4-bd77-11e4-afc8-20cf3073dde3": 4,  # Турники, брусья, упоры для отжимания
}


def apply_category_order(apps, schema_editor):
    """Проставляет sort_order по onec_id. Категории, которых нет в БД, пропускаются."""
    Category = apps.get_model("products", "Category")
    for onec_id, sort_order in {**ROOT_ORDER, **FITNESS_CHILDREN_ORDER}.items():
        Category.objects.filter(onec_id=onec_id).update(sort_order=sort_order)


class Migration(migrations.Migration):
    dependencies = [
        ("products", "0056_onec_deleted_and_excluded_items"),
    ]

    operations = [
        migrations.RunPython(apply_category_order, reverse_code=migrations.RunPython.noop),
    ]

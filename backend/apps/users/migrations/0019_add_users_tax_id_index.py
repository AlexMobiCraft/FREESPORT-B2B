"""
Индекс на users.tax_id.

Поиск непривязанных контрагентов 1С по ИНН выполняется при каждом рендере
changelist пользователей (correlated subquery по строкам страницы) и при каждой
B2B-регистрации. Без индекса каждый такой подзапрос — seq scan по всей таблице.

Индекс обычный, не unique: в проде 65 групп дублей tax_id, до 74 строк на один
ИНН — одно юрлицо ведётся в 1С как несколько контрагентов. Unique-констрейнт
не наложится и не должен накладываться.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0018_migrate_1c_users_to_unregistered"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="user",
            index=models.Index(fields=["tax_id"], name="users_tax_id_idx"),
        ),
    ]

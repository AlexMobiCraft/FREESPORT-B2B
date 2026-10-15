"""
Связать правила регионов с учётными записями сотрудников (стори 42.2).

Только данные: на PostgreSQL UPDATE и ALTER TABLE с отложенными
FK-триггерами в одной транзакции падают на «pending trigger events», поэтому
схема — в 0022, а связывание — здесь.

Правило без ``manager`` связывается с сотрудником (``is_staff``, не
суперпользователь), чей email совпадает с ``manager_email`` без учёта
регистра; из нескольких берётся первый по ``pk``. Резервные правила
обходятся по возрастанию ``pk``, и связывается не больше одного активного:
ответственного по резерву даёт только одно правило. Правило без найденной
учётной записи остаётся как есть — письма по нему идут на ``manager_email``.
Повторный прогон ничего не меняет.
"""

from django.db import migrations

FALLBACK = "fallback"


def link_rules_to_staff(apps, schema_editor):
    ManagerRoutingRule = apps.get_model("common", "ManagerRoutingRule")
    User = apps.get_model("users", "User")
    db_alias = schema_editor.connection.alias

    rules = ManagerRoutingRule.objects.using(db_alias)
    fallback_linked = rules.filter(match_type=FALLBACK, is_active=True, manager__isnull=False).exists()

    for rule in rules.filter(manager__isnull=True).exclude(manager_email="").order_by("pk"):
        if rule.match_type == FALLBACK and rule.is_active and fallback_linked:
            continue
        staff = (
            User.objects.using(db_alias)
            .filter(email__iexact=rule.manager_email, is_staff=True, is_superuser=False)
            .order_by("pk")
            .first()
        )
        if staff is None:
            continue
        rule.manager = staff
        rule.save(update_fields=["manager"])
        if rule.match_type == FALLBACK and rule.is_active:
            fallback_linked = True


class Migration(migrations.Migration):
    dependencies = [
        ("common", "0022_managerroutingrule_manager"),
    ]

    operations = [
        migrations.RunPython(link_rules_to_staff, migrations.RunPython.noop),
    ]

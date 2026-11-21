"""
Право просмотра статистики баннеров (`banners.view_bannerdailystat`) группам
«Маркетинг» и «Руководители» — для отчётности в ОРД в разделе `/marketing/`.

Набор прав — замороженная копия, как в `users/0023_staff_role_groups`:
миграции не импортируют изменяемый код приложения. Группы создаёт `0023`;
если группы нет (удалили вручную), миграция её не создаёт — состав групп
принадлежит `0023`. Повторный прогон идемпотентен, ручные права не снимаются.

Функцию `grant_banner_stat_permissions` зовут и autouse-фикстуры `role_groups`
в тестах после функции `0023`: транзакционные тесты делают `flush`, который
стирает группы и их права.
"""

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

GROUP_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "Маркетинг": ("banners.view_bannerdailystat",),
    "Руководители": ("banners.view_bannerdailystat",),
}


def grant_banner_stat_permissions(apps, schema_editor):
    alias = schema_editor.connection.alias

    # В чистой БД права модели ещё не созданы: `post_migrate` срабатывает после всех
    # миграций. Глобальный app_config — потому что у исторического пуст `models_module`.
    create_permissions(global_apps.get_app_config("banners"), verbosity=0, apps=apps, using=alias)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for group_name, permission_names in GROUP_PERMISSIONS.items():
        group = Group.objects.filter(name=group_name).first()
        if group is None:
            continue
        permissions = []
        for name in permission_names:
            app_label, codename = name.split(".", 1)
            # Ненайденное право — исключение: опечатка должна ронять миграцию и тест.
            permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
        group.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("banners", "0008_bannerdailystat"),
        ("users", "0023_staff_role_groups"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        # Обратная миграция права не снимает: их могли выдать и вручную.
        migrations.RunPython(grant_banner_stat_permissions, migrations.RunPython.noop),
    ]

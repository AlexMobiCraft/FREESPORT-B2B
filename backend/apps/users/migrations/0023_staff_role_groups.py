"""
Группы ролей сотрудников эпика 42: «Менеджеры», «Маркетинг», «Руководители».

Наборы прав — замороженная копия (миграции не импортируют изменяемый код
приложения): если последующей стори понадобится другое право, она добавляет
свою миграцию, а эту после выката не правят. Имена групп — тоже литералы;
те же имена для кода приложения лежат в `apps.users.staff_roles`.

Существующая на проде группа «Менеджер» переиспользуется: переименовывается
в «Менеджеры», её права заменяются набором роли, участники сохраняются.
Повторный прогон идемпотентен: дублей не создаёт, а у уже существующей
группы роли только добавляет недостающие права, ручные не снимает.
Прямые права сотрудников (`user_permissions`) миграция не трогает.
"""

from django.apps import apps as global_apps
from django.contrib.auth.management import create_permissions
from django.db import migrations

# Приложения, права которых входят в наборы ролей.
PERMISSION_APP_LABELS = ("users", "orders", "banners", "common", "products", "bonuses")

_MANAGERS_PERMISSIONS = (
    "users.view_user",
    "users.change_user",
    "users.view_company",
    "users.change_company",
    "users.view_address",
    "users.add_address",
    "users.change_address",
    "users.delete_address",
    "orders.view_order",
    "orders.change_order",
    "orders.view_orderitem",
)

_MARKETING_PERMISSIONS = (
    "banners.view_banner",
    "banners.add_banner",
    "banners.change_banner",
    "banners.delete_banner",
    "common.view_news",
    "common.add_news",
    "common.change_news",
    "common.delete_news",
    "common.view_blogpost",
    "common.add_blogpost",
    "common.change_blogpost",
    "common.delete_blogpost",
    "common.view_category",
    "common.add_category",
    "common.change_category",
    "common.delete_category",
    "products.view_product",
    "products.change_product",
    "products.view_brand",
    "products.change_brand",
    # HomepageCategory — proxy `products.Category`: права proxy живут на его
    # собственном content type, `products.change_category` маркетингу не даётся.
    "products.view_homepagecategory",
    "products.change_homepagecategory",
)

_SUPERVISORS_OWN_PERMISSIONS = (
    "users.add_user",
    "common.view_notificationrecipient",
    "common.add_notificationrecipient",
    "common.change_notificationrecipient",
    "common.delete_notificationrecipient",
    "common.view_managerroutingrule",
    "common.add_managerroutingrule",
    "common.change_managerroutingrule",
    "common.delete_managerroutingrule",
    "common.view_auditlog",
    "bonuses.view_bonusprogramsettings",
    "bonuses.change_bonusprogramsettings",
    "bonuses.view_bonustransaction",
)

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "Менеджеры": _MANAGERS_PERMISSIONS,
    "Маркетинг": _MARKETING_PERMISSIONS,
    # Руководитель — всё из двух других ролей плюс свои права.
    "Руководители": _MANAGERS_PERMISSIONS + _MARKETING_PERMISSIONS + _SUPERVISORS_OWN_PERMISSIONS,
}

# Старые имена, под которыми группа роли могла уже существовать.
LEGACY_NAMES: dict[str, tuple[str, ...]] = {"Менеджеры": ("Менеджер",)}


def _get_permissions(Permission, names):
    """
    Права по строкам `app_label.codename`.

    Ненайденное право — исключение, а не тихий пропуск: опечатка в наборе
    должна ронять миграцию и тест.
    """
    permissions = []
    for name in names:
        app_label, codename = name.split(".", 1)
        permissions.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return permissions


def create_staff_role_groups(apps, schema_editor):
    """Создаёт (или приводит к набору роли) группы трёх ролей сотрудников."""
    alias = schema_editor.connection.alias

    # В чистой БД права ещё не созданы: `post_migrate` срабатывает после всех
    # миграций. Глобальный app_config нужен, потому что у исторического пуст
    # `models_module` и функция молча выходит; `apps=apps` — историческое
    # состояние. Недостающие content types `create_permissions` создаёт сам.
    for label in PERMISSION_APP_LABELS:
        create_permissions(global_apps.get_app_config(label), verbosity=0, apps=apps, using=alias)

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for role, permission_names in ROLE_PERMISSIONS.items():
        permissions = _get_permissions(Permission, permission_names)
        target = Group.objects.filter(name=role).first()
        legacy = Group.objects.filter(name__in=LEGACY_NAMES.get(role, ())).first()

        if target is None and legacy is not None:
            # Переименование старой группы — единственный случай замены прав.
            legacy.name = role
            legacy.save(update_fields=["name"])
            legacy.permissions.set(permissions)
        elif target is not None and legacy is not None:
            target.user_set.add(*legacy.user_set.all())
            legacy.delete()
            target.permissions.add(*permissions)
        elif target is None:
            target = Group.objects.create(name=role)
            target.permissions.set(permissions)
        else:
            # Группа роли уже есть: права, выданные ей вручную, не снимаем.
            target.permissions.add(*permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0022_alter_user_country"),
        ("auth", "0012_alter_user_first_name_max_length"),
        ("contenttypes", "0002_remove_content_type_name"),
        ("orders", "0016_customercodesequence"),
        ("banners", "0007_banner_ad_disclosure"),
        ("common", "0021_newsletter_unsubscribe_token"),
        ("products", "0056_onec_deleted_and_excluded_items"),
        ("bonuses", "0003_bonus_journal_survives_deletion"),
    ]

    operations = [
        # Обратная миграция ничего не удаляет: членство в группах могло быть
        # выдано вручную.
        migrations.RunPython(create_staff_role_groups, migrations.RunPython.noop),
    ]

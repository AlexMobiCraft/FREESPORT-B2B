"""
Конфигурация приложения `django.contrib.admin` для проекта FREESPORT.

Штатный механизм Django «Overriding the default admin site»: подкласс
`AdminConfig` с `default_site` подключается в `INSTALLED_APPS` вместо
`"django.contrib.admin"`. Подкласс лежит здесь, а не в `apps/common/apps.py`:
при двух подклассах `AppConfig` в одном модуле Django перестаёт автоматически
выбирать `CommonConfig` для `"apps.common"`.
"""

from django.contrib.admin.apps import AdminConfig


class FreesportAdminConfig(AdminConfig):
    """Делает `SuperuserAdminSite` сайтом `/admin/` по умолчанию (эпик 42)."""

    default_site = "freesport.admin_site.SuperuserAdminSite"

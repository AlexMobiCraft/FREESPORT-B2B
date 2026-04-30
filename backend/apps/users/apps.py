from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
    verbose_name = "Пользователи"

    def ready(self):
        # Переименование блока "Пользователи и группы" в админке
        from django.contrib.auth.apps import AuthConfig

        import apps.users.signals  # noqa

        AuthConfig.verbose_name = "Группы пользователей"

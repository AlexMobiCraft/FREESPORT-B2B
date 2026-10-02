from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.integrations"
    verbose_name = "ИНТЕГРАЦИИ"

    def ready(self) -> None:
        """
        Инициализация при загрузке приложения.

        Импортирует admin и регистрирует custom URL для страницы импорта.
        """
        import apps.integrations.admin  # noqa: F401
        import apps.integrations.admin_urls  # noqa: F401

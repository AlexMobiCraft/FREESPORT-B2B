from django.apps import AppConfig


class BonusesConfig(AppConfig):
    """Конфигурация приложения бонусной программы."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bonuses"
    verbose_name = "Бонусная программа"

    def ready(self) -> None:
        """Подключение сигналов и регистрация на сайте /supervisor/."""
        import apps.bonuses.signals  # noqa: F401
        import apps.bonuses.supervisor_admin  # noqa: F401

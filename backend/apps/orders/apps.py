from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Конфигурация приложения заказов"""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.orders"
    verbose_name = "Заказы"

    def ready(self):
        """Подключение сигналов при инициализации приложения"""
        import apps.orders.signals  # noqa: F401

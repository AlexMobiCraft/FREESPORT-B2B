from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.products"
    verbose_name = "Товары"

    def ready(self):
        import apps.products.marketing_admin  # noqa: F401 — регистрация на сайте /marketing/
        import apps.products.signals  # noqa: F401

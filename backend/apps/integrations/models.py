from apps.products.models import ImportSession


class Session(ImportSession):
    """
    Proxy модель для отображения сессий импорта в Django Admin.

    URL страницы в admin: /admin/integrations/session/
    (Django генерирует URL на основе app_label + model_name в lowercase)

    Переименована с IntegrationImportSession в Session для получения
    короткого и понятного URL вместо длинного integrationimportsession.
    """

    class Meta:
        proxy = True
        app_label = "integrations"
        verbose_name = "Сессия импорта"
        verbose_name_plural = "Сессии импорта"
        permissions = [
            ("can_exchange_1c", "Can exchange with 1C"),
        ]
        # model_name будет 'session' (lowercase имени класса)
        # Итоговый URL: /admin/integrations/session/

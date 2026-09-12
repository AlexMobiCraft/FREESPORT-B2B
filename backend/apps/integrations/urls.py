"""
URLconf для приложения integrations.
"""

from django.urls import include, path

from .views import import_from_1c_view

app_name = "integrations"

urlpatterns = [
    path("import_1c/", import_from_1c_view, name="import_from_1c"),
    path("1c/exchange/", include("apps.integrations.onec_exchange.urls")),
]

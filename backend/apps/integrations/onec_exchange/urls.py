from django.urls import path

from .views import ICExchangeView

app_name = "onec_exchange"

urlpatterns = [
    path("", ICExchangeView.as_view(), name="exchange"),
]

"""
URL конфигурация для API способов доставки.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DeliveryMethodViewSet

router = DefaultRouter()
router.register(r"methods", DeliveryMethodViewSet, basename="delivery-method")

app_name = "delivery"

urlpatterns = [
    path("", include(router.urls)),
]

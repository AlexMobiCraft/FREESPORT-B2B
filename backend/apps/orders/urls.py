"""
URL маршруты для заказов
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import OrderViewSet

# Router для ViewSets
router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")

app_name = "orders"

urlpatterns = [
    # Включаем router для всех ViewSets
    path("", include(router.urls)),
]

"""
URL маршруты для API баннеров
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActiveBannersView

router = DefaultRouter()
router.register(r"banners", ActiveBannersView, basename="banner")

app_name = "banners"

urlpatterns = [
    path("", include(router.urls)),
]

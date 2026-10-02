"""
URL конфигурация для статических страниц
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import PageViewSet

app_name = "pages"

router = DefaultRouter()
router.register(r"pages", PageViewSet, basename="pages")

urlpatterns = router.urls

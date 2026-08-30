"""
URL маршруты для каталога товаров
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import AttributeFilterViewSet, BrandViewSet, CategoryTreeViewSet, CategoryViewSet, ProductViewSet

# Router для ViewSets
router = DefaultRouter()
router.register(r"products", ProductViewSet, basename="product")
router.register(r"categories", CategoryViewSet, basename="category")
router.register(r"categories-tree", CategoryTreeViewSet, basename="category-tree")
router.register(r"brands", BrandViewSet, basename="brand")
router.register(r"catalog/filters", AttributeFilterViewSet, basename="catalog-filter")

APP_NAME = "products"
app_name = APP_NAME

urlpatterns = [
    # Включаем router для всех ViewSets
    path("", include(router.urls)),
]

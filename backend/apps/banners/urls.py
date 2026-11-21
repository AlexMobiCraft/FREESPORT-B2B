"""
URL маршруты для API баннеров
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import ActiveBannersView, SiteEventsView

router = DefaultRouter()
router.register(r"banners", ActiveBannersView, basename="banner")

app_name = "banners"

urlpatterns = [
    # Без слов banner/ad/promo/collect в пути — их режут блокировщики.
    path("site-events/", SiteEventsView.as_view(), name="site-events"),
    path("", include(router.urls)),
]

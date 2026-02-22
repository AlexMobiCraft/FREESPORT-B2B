"""
URL конфигурация для проекта FREESPORT
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.common.admin import monitoring_dashboard_view

urlpatterns = [
    # Админ панель Django
    path(
        "admin/monitoring/",
        monitoring_dashboard_view,
        name="admin_monitoring_dashboard",
    ),
    path("admin/", admin.site.urls),
    # API документация
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    # API endpoints
    path("api/v1/", include("apps.common.urls")),
    path("api/v1/", include("apps.users.urls")),
    path("api/v1/", include("apps.products.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/cart/", include("apps.cart.urls")),
    path("api/v1/", include("apps.pages.urls")),
    path("api/v1/delivery/", include("apps.delivery.urls")),
    path("api/v1/", include("apps.banners.urls")),
    path("api/integration/", include("apps.integrations.urls")),
]

# Статические и медиа файлы в режиме разработки
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

    # Debug toolbar для разработки
    if "debug_toolbar" in settings.INSTALLED_APPS:
        import debug_toolbar

        urlpatterns.append(path("__debug__/", include(debug_toolbar.urls, namespace="djdt")))

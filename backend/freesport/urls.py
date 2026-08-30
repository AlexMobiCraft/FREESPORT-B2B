"""
URL конфигурация для проекта FREESPORT
"""

import re

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from apps.common.admin import monitoring_dashboard_view

# Story 36.1: runtime-каталоги обмена 1С вынесены в приватный ONEC_PRIVATE_DIR,
# но media-том переживает деплой — файлы незавершённых обменов, записанные до
# переезда, физически остаются под MEDIA_ROOT. В DEBUG весь MEDIA_ROOT целиком
# раздаётся django.conf.urls.static(), поэтому Django обслуживал бы их так же,
# как раньше это делал nginx. Guard повторяет 404-правила из
# docker/nginx/conf.d/*.conf и регистрируется ДО static() — иначе не сработает.
LEGACY_ONEC_MEDIA_DIRS = ("1c_import", "1c_temp")


def legacy_onec_media_gone(request, *args, **kwargs):
    """Всегда 404 для legacy-путей обмена 1С под MEDIA_URL (AC-2 Story 36.1)."""
    raise Http404("1C exchange files are not served from MEDIA_ROOT")


_LEGACY_ONEC_MEDIA_PATTERN = r"^{prefix}(?:{dirs})/".format(
    prefix=re.escape(settings.MEDIA_URL.lstrip("/")),
    dirs="|".join(re.escape(name) for name in LEGACY_ONEC_MEDIA_DIRS),
)

urlpatterns = [
    # Должен стоять первым: перехватывает legacy media-пути обмена 1С
    # раньше, чем их подхватит static() в DEBUG-режиме ниже.
    re_path(_LEGACY_ONEC_MEDIA_PATTERN, legacy_onec_media_gone),
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
    path("api/v1/", include("apps.bonuses.urls")),
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

from django.urls import path

from . import views

app_name = "common"

urlpatterns = [
    path("health/", views.health_check, name="health-check"),
    # Monitoring endpoints
    path(
        "monitoring/metrics/operations/",
        views.operation_metrics,
        name="operation-metrics",
    ),
    path("monitoring/metrics/business/", views.business_metrics, name="business-metrics"),
    path("monitoring/metrics/realtime/", views.realtime_metrics, name="realtime-metrics"),
    path("monitoring/health/", views.system_health, name="system-health"),
    # Newsletter & News endpoints
    path("subscribe/", views.subscribe, name="subscribe"),
    path("unsubscribe/", views.unsubscribe, name="unsubscribe"),
    path("news/", views.NewsListView.as_view(), name="news-list"),
    path("news/<slug:slug>/", views.NewsDetailView.as_view(), name="news-detail"),
    # Blog endpoints
    path("blog/", views.BlogPostListView.as_view(), name="blog-list"),
    path("blog/<slug:slug>/", views.BlogPostDetailView.as_view(), name="blog-detail"),
]

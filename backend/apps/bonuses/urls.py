"""URL маршруты бонусной программы."""

from django.urls import path

from apps.bonuses.views import BonusSummaryView, BonusTransactionListView

app_name = "bonuses"

urlpatterns = [
    path("users/bonuses/", BonusSummaryView.as_view(), name="summary"),
    path(
        "users/bonuses/transactions/",
        BonusTransactionListView.as_view(),
        name="transactions",
    ),
]

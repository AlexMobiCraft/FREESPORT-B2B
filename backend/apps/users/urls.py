"""
URL маршруты для API управления пользователями
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AddressViewSet,
    CompanyView,
    FavoriteViewSet,
    LogoutView,
    OrderHistoryView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    UserDashboardView,
    UserLoginView,
    UserProfileView,
    UserRegistrationView,
    ValidateTokenView,
    user_roles_view,
)

# Router для ViewSets
router = DefaultRouter()
router.register(r"users/addresses", AddressViewSet, basename="address")
router.register(r"users/favorites", FavoriteViewSet, basename="favorite")

app_name = "users"

urlpatterns = [
    # Аутентификация
    path("auth/register/", UserRegistrationView.as_view(), name="register"),
    path("auth/login/", UserLoginView.as_view(), name="login"),
    path("auth/logout/", LogoutView.as_view(), name="logout"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # Password Reset
    path(
        "auth/password-reset/",
        PasswordResetRequestView.as_view(),
        name="password_reset_request",
    ),
    path(
        "auth/password-reset/validate-token/",
        ValidateTokenView.as_view(),
        name="password_reset_validate_token",
    ),
    path(
        "auth/password-reset/confirm/",
        PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    # Профиль пользователя
    path("users/profile/", UserProfileView.as_view(), name="profile"),
    # Личный кабинет
    path(
        "users/profile/dashboard/",
        UserDashboardView.as_view(),
        name="dashboard",
    ),
    path("users/company/", CompanyView.as_view(), name="company"),
    path("users/orders/", OrderHistoryView.as_view(), name="orders"),
    # Системная информация
    path("users/roles/", user_roles_view, name="roles"),
    # Включаем router для ViewSets
    path("", include(router.urls)),
]

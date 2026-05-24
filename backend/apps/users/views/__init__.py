"""
Views для API управления пользователями
Разделенные по модулям для лучшей организации кода
"""

# Импорты для совместимости с существующими URL patterns
from .authentication import (
    LogoutView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    UserLoginView,
    UserRegistrationView,
    ValidateTokenView,
)
from .misc import user_roles_view
from .personal_cabinet import AddressViewSet, CompanyView, FavoriteViewSet, OrderHistoryView, UserDashboardView
from .profile import UserProfileView

__all__ = [
    "UserRegistrationView",
    "UserLoginView",
    "LogoutView",
    "UserProfileView",
    "user_roles_view",
    "UserDashboardView",
    "AddressViewSet",
    "CompanyView",
    "FavoriteViewSet",
    "OrderHistoryView",
    "PasswordResetRequestView",
    "PasswordResetConfirmView",
    "ValidateTokenView",
]

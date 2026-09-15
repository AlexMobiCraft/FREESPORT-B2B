from rest_framework.permissions import BasePermission


class Is1CExchangeUser(BasePermission):
    """
    Restricts access to staff users or those with 'can_exchange_1c' permission.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and (
            request.user.is_staff or request.user.has_perm("integrations.can_exchange_1c")
        )

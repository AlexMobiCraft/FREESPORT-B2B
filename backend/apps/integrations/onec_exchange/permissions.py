from rest_framework.permissions import BasePermission


class Is1CExchangeUser(BasePermission):
    """
    Доступ к обмену с 1С только по праву `integrations.can_exchange_1c`.

    Активный суперпользователь проходит автоматически: `has_perm` у него всегда
    `True`. Флаг `is_staff` доступа к обмену не даёт — с эпика 42 он означает
    «сотрудник», а обмен на проде ходит под роботом с этим правом без `is_staff`.
    """

    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.has_perm("integrations.can_exchange_1c")

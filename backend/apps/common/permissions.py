"""
Классы прав DRF, общие для приложений FREESPORT.
"""

from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsSuperUser(BasePermission):
    """
    Доступ только аутентифицированному суперпользователю.

    Заменяет `IsAdminUser` на служебных эндпоинтах: с эпика 42 `is_staff`
    означает «сотрудник» и служебного доступа не даёт.
    """

    def has_permission(self, request: Request, view: Any) -> bool:
        user = request.user
        return bool(user and user.is_authenticated and user.is_superuser)

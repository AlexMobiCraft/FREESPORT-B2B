"""
Вспомогательные views и утилиты
"""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import User


@extend_schema(
    summary="Информация о ролях пользователей",
    description="Получение списка доступных ролей пользователей в системе",
    responses={
        200: OpenApiResponse(
            description="Список ролей пользователей",
            examples=[
                OpenApiExample(
                    name="Roles Response",
                    value={
                        "roles": [
                            {"key": "retail", "display": "Розничный покупатель"},
                            {"key": "wholesale_level1", "display": "Оптовик уровень 1"},
                            {"key": "trainer", "display": "Тренер/Фитнес-клуб"},
                            {
                                "key": "federation_rep",
                                "display": "Представитель федерации",
                            },
                        ]
                    },
                )
            ],
        ),
    },
    tags=["Users"],
)
@api_view(["GET"])
@permission_classes([permissions.AllowAny])
def user_roles_view(request):
    """
    Возвращает список доступных ролей пользователей
    """
    # Исключаем роль admin из публичного API
    public_roles = [choice for choice in User.ROLE_CHOICES if choice[0] != "admin"]

    roles_data = [{"key": role[0], "display": role[1]} for role in public_roles]

    return Response({"roles": roles_data}, status=status.HTTP_200_OK)

"""
Вспомогательные views и утилиты
"""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response

from ..models import User
from ..serializers import get_self_service_roles


@extend_schema(
    summary="Информация о ролях пользователей",
    description=("Получение списка ролей, доступных при саморегистрации " "(розничная роль недоступна)"),
    responses={
        200: OpenApiResponse(
            description="Список ролей пользователей",
            examples=[
                OpenApiExample(
                    name="Roles Response",
                    value={
                        "roles": [
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
    Возвращает список ролей, доступных при саморегистрации
    """
    # Источник правды — тот же список, по которому регистрацию проверяет
    # UserRegistrationSerializer: служебные роли (`admin`, `unregistered`) в него
    # не входят, а розница появляется вместе с REGISTRATION_ALLOW_RETAIL.
    self_service_roles = get_self_service_roles()
    public_roles = [choice for choice in User.ROLE_CHOICES if choice[0] in self_service_roles]

    roles_data = [{"key": role[0], "display": role[1]} for role in public_roles]

    return Response({"roles": roles_data}, status=status.HTTP_200_OK)

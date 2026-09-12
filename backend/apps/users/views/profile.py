"""
Views для управления профилем пользователя
"""

from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import permissions
from rest_framework.generics import RetrieveUpdateAPIView

from ..serializers import UserProfileSerializer


class UserProfileView(RetrieveUpdateAPIView):
    """
    Просмотр и обновление профиля текущего пользователя
    """

    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Возвращает профиль текущего пользователя"""
        return self.request.user

    @extend_schema(
        summary="Получение профиля пользователя",
        description=("Получение данных профиля " "текущего авторизованного пользователя"),
        responses={
            200: UserProfileSerializer,
            401: OpenApiResponse(
                description="Пользователь не авторизован",
                examples=[
                    OpenApiExample(
                        name="Unauthorized",
                        value={"detail": "Учетные данные не были предоставлены."},
                    )
                ],
            ),
        },
        tags=["Users"],
    )
    def get(self, request, *args, **kwargs):
        """Получение профиля пользователя"""
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Обновление профиля пользователя",
        description="Частичное обновление данных профиля пользователя (PATCH)",
        request=UserProfileSerializer,
        responses={
            200: UserProfileSerializer,
            400: OpenApiResponse(
                description="Ошибки валидации",
                examples=[
                    OpenApiExample(
                        name="Validation Error",
                        value={"tax_id": ["ИНН должен содержать 10 или 12 цифр."]},
                    )
                ],
            ),
            401: OpenApiResponse(description="Пользователь не авторизован"),
        },
        tags=["Users"],
    )
    def patch(self, request, *args, **kwargs):
        """Обновление профиля пользователя"""
        return super().patch(request, *args, **kwargs)

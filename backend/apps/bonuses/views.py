"""API личного кабинета тренера: бонусный счёт и история операций.

`DEFAULT_PERMISSION_CLASSES` проекта — `AllowAny`, поэтому
`permission_classes` указывается явно в каждом view.
"""

from decimal import Decimal

from django.db.models import QuerySet, Sum
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.generics import ListAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.bonuses.models import BonusProgramSettings, BonusTransaction
from apps.bonuses.serializers import BonusSummarySerializer, BonusTransactionSerializer
from apps.bonuses.services.accrual import TRAINER_ROLE, get_balance

FORBIDDEN_RESPONSE = {"detail": "Бонусная программа доступна только тренерам."}
UNVERIFIED_RESPONSE = {"detail": "Учётная запись тренера ещё не подтверждена менеджером."}


class BonusTransactionPagination(PageNumberPagination):
    """Пагинация истории операций.

    Глобальный `PAGE_SIZE_QUERY_PARAM` в DRF не действует — размер страницы
    задаётся на классе пагинации (как в `apps.products.views`).
    """

    page_size_query_param = "page_size"
    max_page_size = 100


class IsTrainer(permissions.BasePermission):
    """Доступ только для подтверждённых тренеров («Тренер / Фитнес-клуб»).

    Реализовано permission-классом, а не проверкой внутри `get()`: иначе любой
    добавленный позже метод остался бы без проверки роли на денежных данных.

    Условие совпадает с условием начисления (`is_eligible`) и с показом пункта
    меню на фронте: неподтверждённый тренер в программе не участвует, поэтому
    получает 403 с объяснением, а не 200 с нулями.
    """

    message = FORBIDDEN_RESPONSE["detail"]

    def has_permission(self, request: Request, view: object) -> bool:
        user = request.user
        if getattr(user, "role", None) != TRAINER_ROLE:
            # message задаётся на экземпляре: DRF создаёт permission на каждый запрос
            self.message = FORBIDDEN_RESPONSE["detail"]
            return False
        if not getattr(user, "is_verified", False):
            self.message = UNVERIFIED_RESPONSE["detail"]
            return False
        return True


class BonusSummaryView(APIView):
    """Сводка по бонусному счёту текущего тренера."""

    permission_classes = [permissions.IsAuthenticated, IsTrainer]

    @extend_schema(
        summary="Сводка по бонусному счёту",
        description="Баланс, суммы начислений и выплат, действующий процент программы.",
        responses={
            200: BonusSummarySerializer,
            401: "Пользователь не авторизован",
            403: "Доступ только для подтверждённых тренеров",
        },
        tags=["Bonuses"],
    )
    def get(self, request: Request) -> Response:
        accrued = BonusTransaction.objects.filter(
            user_id=request.user.pk, transaction_type=BonusTransaction.ACCRUAL
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        spent = BonusTransaction.objects.filter(
            user_id=request.user.pk, transaction_type__in=BonusTransaction.NEGATIVE_TYPES
        ).aggregate(total=Sum("amount"))["total"] or Decimal("0")

        settings = BonusProgramSettings.load()

        serializer = BonusSummarySerializer(
            {
                "balance": get_balance(request.user.pk),
                "total_accrued": accrued,
                "total_paid_out": abs(spent),
                "current_percent": settings.percent,
                "is_active": settings.is_active,
            }
        )
        return Response(serializer.data, status=status.HTTP_200_OK)


class BonusTransactionListView(ListAPIView):
    """История бонусных операций текущего тренера."""

    permission_classes = [permissions.IsAuthenticated, IsTrainer]
    serializer_class = BonusTransactionSerializer
    pagination_class = BonusTransactionPagination

    def get_queryset(self) -> QuerySet[BonusTransaction]:
        queryset = BonusTransaction.objects.filter(user_id=self.request.user.pk).select_related("order")
        transaction_type = self.request.query_params.get("type")
        if transaction_type:
            # Опечатка в типе не должна молча отдавать пустую историю —
            # тренер решил бы, что бонусы пропали
            if transaction_type not in dict(BonusTransaction.TRANSACTION_TYPES):
                raise DRFValidationError({"type": f"Недопустимый тип операции: {transaction_type!r}."})
            queryset = queryset.filter(transaction_type=transaction_type)
        return queryset

    @extend_schema(
        summary="История бонусных операций",
        description="Список операций тренера с пагинацией и фильтром по типу.",
        parameters=[
            OpenApiParameter(
                name="type",
                description="Фильтр по типу операции",
                required=False,
                type=str,
                enum=[BonusTransaction.ACCRUAL, BonusTransaction.PAYOUT, BonusTransaction.WRITEOFF],
            ),
        ],
        responses={
            200: BonusTransactionSerializer(many=True),
            401: "Пользователь не авторизован",
            403: "Доступ только для подтверждённых тренеров",
        },
        tags=["Bonuses"],
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        return super().get(request, *args, **kwargs)

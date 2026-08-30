"""Представления для общего приложения."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema, inline_serializer
from rest_framework import generics, serializers, status
from rest_framework.decorators import api_view, parser_classes, permission_classes, throttle_classes
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.parsers import JSONParser
from rest_framework.permissions import AllowAny, IsAdminUser, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.models import BlogPost, News, UserConsent
from apps.common.serializers import (
    BlogPostDetailSerializer,
    BlogPostListSerializer,
    NewsSerializer,
    SubscribeResponseSerializer,
    SubscribeSerializer,
    ALREADY_SUBSCRIBED_CODE,
    UnsubscribeResponseSerializer,
    UnsubscribeSerializer,
)
from apps.common.services import CustomerSyncMonitor
from apps.common.throttling import SubscribeRateThrottle, UnsubscribeRateThrottle
from apps.common.utils.consent_audit import (
    get_consent_ip_address,
    sanitize_consent_user_agent,
)

logger = logging.getLogger(__name__)


def _has_error_code(detail: object, code: str) -> bool:
    """Проверить DRF ErrorDetail code в nested serializer detail."""
    if isinstance(detail, dict):
        return any(_has_error_code(value, code) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return any(_has_error_code(value, code) for value in detail)
    return getattr(detail, "code", None) == code


@extend_schema(
    summary="Health Check",
    description="Проверка состояния API сервера",
    responses={
        200: OpenApiResponse(
            description="API работает корректно",
            examples=[
                OpenApiExample(
                    "Successful Response",
                    value={
                        "status": "healthy",
                        "version": "1.0.0",
                        "environment": "development",
                    },
                    response_only=True,
                )
            ],
        )
    },
    tags=["System"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(_request):
    """
    Endpoint для проверки состояния API.
    Возвращает информацию о версии и окружении.
    """
    return Response(
        {
            "status": "healthy",
            "version": "1.0.0",
            "environment": getattr(settings, "ENVIRONMENT", "development"),
        },
        status=status.HTTP_200_OK,
    )


# ============================================================================
# Monitoring Views
# ============================================================================


@extend_schema(
    summary="Получить метрики операций синхронизации",
    description=("Возвращает метрики операций за указанный период " "(по умолчанию последние 24 часа)"),
    parameters=[
        OpenApiParameter(
            name="start_date",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Начало периода (ISO 8601 формат)",
            required=False,
        ),
        OpenApiParameter(
            name="end_date",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Конец периода (ISO 8601 формат)",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Метрики операций успешно получены",
            examples=[
                OpenApiExample(
                    name="success_example",
                    value={
                        "total_operations": 1250,
                        "operations_by_type": {
                            "import_from_1c": 800,
                            "export_to_1c": 300,
                            "conflict_resolution": 150,
                        },
                        "success_count": 1180,
                        "error_count": 70,
                        "success_rate": 94.4,
                        "error_rate": 5.6,
                    },
                )
            ],
        ),
    },
    tags=["Monitoring"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def operation_metrics(request: Request) -> Response:
    """Получить метрики операций синхронизации."""
    start_date_str = request.query_params.get("start_date")
    end_date_str = request.query_params.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        else:
            start_date = timezone.now() - timedelta(hours=24)

        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        else:
            end_date = timezone.now()

        if start_date >= end_date:
            return Response(
                {"error": "start_date должна быть меньше " "end_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except ValueError as e:
        return Response(
            {"error": f"Некорректный формат даты: " f"{str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    monitor = CustomerSyncMonitor()
    metrics = monitor.get_operation_metrics(start_date, end_date)

    return Response(metrics, status=status.HTTP_200_OK)


@extend_schema(
    summary="Получить бизнес-метрики синхронизации",
    description="Возвращает бизнес-метрики за указанный период",
    parameters=[
        OpenApiParameter(
            name="start_date",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Начало периода (ISO 8601 формат)",
            required=False,
        ),
        OpenApiParameter(
            name="end_date",
            type=str,
            location=OpenApiParameter.QUERY,
            description="Конец периода (ISO 8601 формат)",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Бизнес-метрики успешно получены",
            examples=[
                OpenApiExample(
                    name="success_example",
                    value={
                        "synced_customers_count": 450,
                        "conflicts_resolved": {"portal_registration": 120},
                        "auto_resolution_rate": 88.5,
                    },
                )
            ],
        ),
    },
    tags=["Monitoring"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def business_metrics(request: Request) -> Response:
    """Получить бизнес-метрики синхронизации."""
    start_date_str = request.query_params.get("start_date")
    end_date_str = request.query_params.get("end_date")

    try:
        if start_date_str:
            start_date = datetime.fromisoformat(start_date_str.replace("Z", "+00:00"))
        else:
            start_date = timezone.now() - timedelta(hours=24)

        if end_date_str:
            end_date = datetime.fromisoformat(end_date_str.replace("Z", "+00:00"))
        else:
            end_date = timezone.now()

        if start_date >= end_date:
            return Response(
                {"error": "start_date должна быть меньше end_date"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    except ValueError as e:
        return Response(
            {"error": f"Некорректный формат даты: {str(e)}"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    monitor = CustomerSyncMonitor()
    metrics = monitor.get_business_metrics(start_date, end_date)

    return Response(metrics, status=status.HTTP_200_OK)


@extend_schema(
    summary="Получить статус здоровья системы",
    description="Возвращает текущий статус всех компонентов системы интеграции",
    responses={
        200: OpenApiResponse(
            description="Статус системы успешно получен",
            examples=[
                OpenApiExample(
                    name="healthy_example",
                    value={
                        "is_healthy": True,
                        "components": {
                            "database": {"component": "database", "available": True},
                            "redis": {"component": "redis", "available": True},
                        },
                        "critical_issues": [],
                    },
                )
            ],
        ),
    },
    tags=["Monitoring"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def system_health(_request: Request) -> Response:
    """Получить статус здоровья системы интеграции."""
    monitor = CustomerSyncMonitor()
    health_status = monitor.get_system_health()

    http_status = status.HTTP_200_OK if health_status["is_healthy"] else status.HTTP_503_SERVICE_UNAVAILABLE

    return Response(health_status, status=http_status)


@extend_schema(
    summary="Получить метрики в реальном времени",
    description="Возвращает метрики за последние 5 минут",
    responses={
        200: OpenApiResponse(
            description="Метрики в реальном времени получены",
            examples=[
                OpenApiExample(
                    name="realtime_example",
                    value={
                        "operations_last_5min": 45,
                        "errors_last_5min": 2,
                        "current_error_rate": 4.44,
                        "throughput_per_minute": 9.0,
                    },
                )
            ],
        ),
    },
    tags=["Monitoring"],
)
@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def realtime_metrics(_request: Request) -> Response:
    """Получить метрики в реальном времени (последние 5 минут)."""
    monitor = CustomerSyncMonitor()
    metrics = monitor.get_real_time_metrics()

    return Response(metrics, status=status.HTTP_200_OK)


# ============================================================================
# Newsletter & News Views
# ============================================================================


@extend_schema(
    summary="Подписка на email-рассылку",
    description=(
        "Подписывает пользователя на email-рассылку о новинках и акциях. "
        "Если email уже подписан - возвращает нейтральный 200 OK."
    ),
    request=SubscribeSerializer,
    examples=[
        OpenApiExample(
            name="successful_subscription_request",
            value={"email": "user@example.com", "pdp_consent": True},
            request_only=True,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Запрос на подписку обработан; новый и уже подписанный email возвращают одинаковый успех",
            examples=[
                OpenApiExample(
                    name="success_response",
                    value={
                        "message": "Вы успешно подписались на рассылку",
                        "email": "user@example.com",
                    },
                    response_only=True,
                )
            ],
        ),
        400: OpenApiResponse(
            description="Ошибка валидации (email или pdp_consent)",
            examples=[
                OpenApiExample(
                    name="validation_error",
                    value={
                        "email": ["Введите корректный email адрес."],
                    },
                    response_only=True,
                ),
                OpenApiExample(
                    name="pdp_consent_required",
                    value={
                        "pdp_consent": ["Необходимо согласие на обработку персональных данных."],
                    },
                    response_only=True,
                ),
            ],
        ),
        503: OpenApiResponse(
            response=inline_serializer(
                name="SubscribeConsentPersistenceErrorResponse",
                fields={
                    "error": serializers.CharField(),
                    "details": serializers.DictField(child=serializers.ListField(child=serializers.CharField())),
                },
            ),
            description="Согласие не удалось сохранить, подписка откатана",
            examples=[
                OpenApiExample(
                    name="consent_persistence_failed",
                    value={
                        "error": "consent_persistence_failed",
                        "details": {
                            "non_field_errors": ["Не удалось сохранить согласие. Попробуйте позже."],
                        },
                    },
                    response_only=True,
                )
            ],
        ),
    },
    tags=["Newsletter"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@parser_classes([JSONParser])
@throttle_classes([SubscribeRateThrottle])
def subscribe(request: Request) -> Response:
    """
    Подписка на email-рассылку.

    Принимает email адрес и создает подписку.
    Если email ранее отписался - реактивирует подписку.
    """
    serializer = SubscribeSerializer(data=request.data, context={"request": request})

    if serializer.is_valid():
        try:
            if not request.user.is_authenticated and not request.session.session_key:
                request.session.save()
        except DatabaseError:
            logger.exception("Failed to materialize anonymous session for consent audit")
            return Response(
                {
                    "error": "consent_persistence_failed",
                    "details": {
                        "non_field_errors": ["Не удалось сохранить согласие. Попробуйте позже."],
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            with transaction.atomic():
                subscription = serializer.save()

                consent_kwargs = {
                    "user": request.user if request.user.is_authenticated else None,
                    "session_key": "" if request.user.is_authenticated else (request.session.session_key or ""),
                    "ip_address": get_consent_ip_address(request),
                    "user_agent": sanitize_consent_user_agent(request.META.get("HTTP_USER_AGENT")),
                }
                UserConsent.objects.create(consent_type="pdp_contract", **consent_kwargs)
                UserConsent.objects.create(consent_type="marketing_email", **consent_kwargs)
        except DRFValidationError as exc:
            if _has_error_code(exc.detail, ALREADY_SUBSCRIBED_CODE):
                response_serializer = SubscribeResponseSerializer(
                    {
                        "message": "Вы успешно подписались на рассылку",
                        "email": serializer.validated_data["email"],
                    }
                )
                return Response(response_serializer.data, status=status.HTTP_200_OK)

            return Response(
                exc.detail,
                status=status.HTTP_400_BAD_REQUEST,
            )
        except DatabaseError:
            logger.exception("Failed to persist newsletter consent audit")
            return Response(
                {
                    "error": "consent_persistence_failed",
                    "details": {
                        "non_field_errors": ["Не удалось сохранить согласие. Попробуйте позже."],
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        response_serializer = SubscribeResponseSerializer(
            {
                "message": "Вы успешно подписались на рассылку",
                "email": subscription.email,
            }
        )

        return Response(
            response_serializer.data,
            status=status.HTTP_200_OK,
        )

    # Обработка ошибки "уже подписан"
    if _has_error_code(serializer.errors, ALREADY_SUBSCRIBED_CODE):
        email = ""
        if isinstance(serializer.initial_data, dict):
            raw_email = serializer.initial_data.get("email", "")
            if isinstance(raw_email, str):
                email = raw_email.lower().strip()
        response_serializer = SubscribeResponseSerializer(
            {
                "message": "Вы успешно подписались на рассылку",
                "email": email,
            }
        )
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    # Другие ошибки валидации
    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


@extend_schema(
    summary="Отписка от email-рассылки",
    description=(
        "Обрабатывает запрос на отписку от email-рассылки. "
        "Для неизвестного или уже отписанного email возвращает такой же нейтральный 200 OK."
    ),
    request=UnsubscribeSerializer,
    responses={
        200: OpenApiResponse(
            description="Запрос на отписку обработан",
            examples=[
                OpenApiExample(
                    name="success_response",
                    value={
                        "message": "Запрос на отписку обработан",
                        "email": "user@example.com",
                    },
                    response_only=True,
                )
            ],
        ),
        400: OpenApiResponse(
            description="Ошибка валидации email",
            examples=[
                OpenApiExample(
                    name="validation_error",
                    value={
                        "email": ["Введите корректный email адрес."],
                    },
                    response_only=True,
                )
            ],
        ),
        503: OpenApiResponse(
            response=inline_serializer(
                name="UnsubscribeProcessingErrorResponse",
                fields={
                    "error": serializers.CharField(),
                    "details": serializers.DictField(child=serializers.ListField(child=serializers.CharField())),
                },
            ),
            description="Запрос на отписку не удалось обработать из-за ошибки БД",
            examples=[
                OpenApiExample(
                    name="unsubscribe_processing_failed",
                    value={
                        "error": "unsubscribe_processing_failed",
                        "details": {
                            "non_field_errors": ["Не удалось обработать запрос. Попробуйте позже."],
                        },
                    },
                    response_only=True,
                )
            ],
        ),
    },
    tags=["Newsletter"],
)
@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([UnsubscribeRateThrottle])
def unsubscribe(request: Request) -> Response:
    """
    Отписка от email-рассылки.

    Принимает email адрес и деактивирует подписку.
    """
    serializer = UnsubscribeSerializer(data=request.data)

    if serializer.is_valid():
        try:
            subscription = serializer.save()
            email = subscription.email if subscription is not None else serializer.validated_data["email"]

            response_serializer = UnsubscribeResponseSerializer(
                {
                    "message": "Запрос на отписку обработан",
                    "email": email,
                }
            )

            return Response(
                response_serializer.data,
                status=status.HTTP_200_OK,
            )
        except DatabaseError:
            logger.exception("Failed to process unsubscribe request")
            return Response(
                {
                    "error": "unsubscribe_processing_failed",
                    "details": {
                        "non_field_errors": ["Не удалось обработать запрос. Попробуйте позже."],
                    },
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    return Response(
        serializer.errors,
        status=status.HTTP_400_BAD_REQUEST,
    )


@extend_schema(
    summary="Получить список новостей",
    description=(
        "Возвращает список опубликованных новостей с пагинацией. "
        "Новости отсортированы по дате публикации (новые первые)."
    ),
    parameters=[
        OpenApiParameter(
            name="page_size",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Количество новостей на странице (по умолчанию: 10, макс: 100)",
            required=False,
        ),
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Номер страницы (по умолчанию: 1)",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Список новостей успешно получен",
            examples=[
                OpenApiExample(
                    name="success_response",
                    value={
                        "count": 15,
                        "next": "http://api.example.com/api/v1/news?page=2",
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "title": "Новая коллекция 2025",
                                "slug": "new-collection-2025",
                                "excerpt": ("Представляем новую коллекцию спортивной " "одежды..."),
                                "content": "Полный текст новости...",
                                "image": ("http://api.example.com/media/news/2025/11/" "collection.jpg"),
                                "published_at": "2025-11-18T10:00:00Z",
                                "created_at": "2025-11-17T15:30:00Z",
                                "updated_at": "2025-11-18T09:00:00Z",
                                "author": "FREESPORT Team",
                                "category": "новинки",
                            },
                            {
                                "id": 2,
                                "title": "Скидки на зимнюю экипировку",
                                "slug": "winter-sale",
                                "excerpt": "До конца месяца скидки до 30%...",
                                "content": "",
                                "image": None,
                                "published_at": "2025-11-17T12:00:00Z",
                                "created_at": "2025-11-16T10:00:00Z",
                                "updated_at": "2025-11-17T11:30:00Z",
                                "author": "",
                                "category": "акции",
                            },
                        ],
                    },
                    response_only=True,
                )
            ],
        ),
    },
    tags=["News"],
)
class NewsListView(generics.ListAPIView):
    """
    API endpoint для получения списка новостей.

    Возвращает только опубликованные новости (is_published=True)
    с датой публикации <= текущего момента.
    """

    serializer_class = NewsSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Возвращает только опубликованные новости.
        Фильтрует по дате публикации (только прошедшие/текущие).
        """
        return News.objects.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        ).order_by("-published_at")


@extend_schema(
    summary="Получить детальную информацию о новости",
    description="""
    Возвращает детальную информацию о новости по её slug.

    Доступны только опубликованные новости (is_published=True)
    с датой публикации <= текущего момента.

    Возвращает 404, если новость не найдена или не опубликована.
    """,
    responses={
        200: OpenApiResponse(
            description="Детальная информация о новости",
            examples=[
                OpenApiExample(
                    name="Успешный ответ",
                    value={
                        "id": 42,
                        "title": "Новый релиз FREESPORT",
                        "slug": "release-2025",
                        "excerpt": "Краткое описание новости",
                        "content": "<p>Полное содержание...</p>",
                        "image": ("https://example.com/media/news/images/2025/12/26/cover.jpg"),
                        "published_at": "2025-12-26T09:00:00Z",
                        "created_at": "2025-12-25T18:00:00Z",
                        "updated_at": "2025-12-25T18:30:00Z",
                        "author": "Редакция FREESPORT",
                        "category": {
                            "id": 3,
                            "name": "Анонсы",
                            "slug": "announcements",
                        },
                    },
                    response_only=True,
                )
            ],
        ),
        404: OpenApiResponse(
            description="Новость не найдена или не опубликована",
            examples=[
                OpenApiExample(
                    name="Новость не найдена",
                    value={"detail": "Not found."},
                    response_only=True,
                )
            ],
        ),
    },
    tags=["News"],
)
class NewsDetailView(generics.RetrieveAPIView):
    """
    API endpoint для получения детальной информации о новости.

    Возвращает только опубликованные новости (is_published=True)
    с датой публикации <= текущего момента.
    Поиск осуществляется по slug.
    """

    serializer_class = NewsSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        """
        Возвращает только опубликованные новости.
        Фильтрует по дате публикации (только прошедшие/текущие).
        """
        return News.objects.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        )


# ============================================================================
# Blog Views
# ============================================================================


@extend_schema(
    summary="Получить список статей блога",
    description=(
        "Возвращает список опубликованных статей блога с пагинацией. "
        "Статьи отсортированы по дате публикации (новые первые)."
    ),
    parameters=[
        OpenApiParameter(
            name="page_size",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Количество статей на странице (по умолчанию: 10, макс: 100)",
            required=False,
        ),
        OpenApiParameter(
            name="page",
            type=int,
            location=OpenApiParameter.QUERY,
            description="Номер страницы (по умолчанию: 1)",
            required=False,
        ),
    ],
    responses={
        200: OpenApiResponse(
            description="Список статей блога успешно получен",
            examples=[
                OpenApiExample(
                    name="success_response",
                    value={
                        "count": 25,
                        "next": "http://api.example.com/api/v1/blog?page=2",
                        "previous": None,
                        "results": [
                            {
                                "id": 1,
                                "title": "Как выбрать спортивную экипировку",
                                "slug": "how-to-choose-sports-equipment",
                                "subtitle": "Полное руководство для начинающих",
                                "excerpt": ("В этой статье мы расскажем о ключевых " "критериях выбора..."),
                                "image": ("http://api.example.com/media/blog/images/" "2025/12/27/equipment.jpg"),
                                "author": "Иван Петров",
                                "category": {
                                    "id": 1,
                                    "name": "Руководства",
                                    "slug": "guides",
                                },
                                "published_at": "2025-12-27T10:00:00Z",
                            },
                        ],
                    },
                    response_only=True,
                )
            ],
        ),
    },
    tags=["Blog"],
)
class BlogPostListView(generics.ListAPIView):
    """
    API endpoint для получения списка статей блога.

    Возвращает только опубликованные статьи (is_published=True)
    с датой публикации <= текущего момента.
    Поддерживает пагинацию и сортировку по дате публикации.
    """

    serializer_class = BlogPostListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        Возвращает только опубликованные статьи блога.
        Фильтрует по дате публикации (только прошедшие/текущие).
        """
        return BlogPost.objects.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        ).order_by("-published_at")


@extend_schema(
    summary="Получить детальную информацию о статье блога",
    description="""
    Возвращает детальную информацию о статье блога по её slug.

    Доступны только опубликованные статьи (is_published=True)
    с датой публикации <= текущего момента.

    Возвращает 404, если статья не найдена или не опубликована.
    """,
    responses={
        200: OpenApiResponse(
            description="Детальная информация о статье блога",
            examples=[
                OpenApiExample(
                    name="Успешный ответ",
                    value={
                        "id": 1,
                        "title": "Как выбрать спортивную экипировку",
                        "slug": "how-to-choose-sports-equipment",
                        "subtitle": "Полное руководство для начинающих",
                        "excerpt": "В этой статье мы расскажем о ключевых критериях...",
                        "content": "<p>Полное содержимое статьи...</p>",
                        "image": ("https://example.com/media/blog/images/" "2025/12/27/equipment.jpg"),
                        "author": "Иван Петров",
                        "category": {
                            "id": 1,
                            "name": "Руководства",
                            "slug": "guides",
                        },
                        "published_at": "2025-12-27T10:00:00Z",
                        "meta_title": "Как выбрать спортивную экипировку | FREESPORT",
                        "meta_description": ("Узнайте как правильно выбрать спортивную экипировку"),
                        "created_at": "2025-12-26T15:00:00Z",
                        "updated_at": "2025-12-26T18:30:00Z",
                    },
                    response_only=True,
                )
            ],
        ),
        404: OpenApiResponse(
            description="Статья не найдена или не опубликована",
            examples=[
                OpenApiExample(
                    name="Статья не найдена",
                    value={"detail": "Not found."},
                    response_only=True,
                )
            ],
        ),
    },
    tags=["Blog"],
)
class BlogPostDetailView(generics.RetrieveAPIView):
    """
    API endpoint для получения детальной информации о статье блога.

    Возвращает только опубликованные статьи (is_published=True)
    с датой публикации <= текущего момента.
    Поиск осуществляется по slug.
    """

    serializer_class = BlogPostDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        """
        Возвращает только опубликованные статьи блога.
        Фильтрует по дате публикации (только прошедшие/текущие).
        """
        return BlogPost.objects.filter(
            is_published=True,
            published_at__lte=timezone.now(),
        )

"""
API views для баннеров
"""

from __future__ import annotations

import re

from drf_spectacular.utils import OpenApiExample, OpenApiParameter, OpenApiResponse, extend_schema
from rest_framework import permissions, status, viewsets
from rest_framework.parsers import JSONParser
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.throttling import SiteEventsThrottle

from . import services
from .serializers import BannerSerializer, SiteEventsBatchSerializer

# Роботы и автоматические браузеры баннер не «видят» — их события не считаются.
BOT_USER_AGENT_RE = re.compile(r"bot|crawl|spider|headless|lighthouse", re.IGNORECASE)


class ActiveBannersView(viewsets.ViewSet):
    """
    ViewSet для получения активных баннеров

    Возвращает баннеры, отфильтрованные по роли текущего пользователя
    и отсортированные по приоритету
    """

    permission_classes = [permissions.AllowAny]

    @extend_schema(
        summary="Получить активные баннеры",
        description=(
            "Возвращает список активных баннеров для текущего пользователя.\n\n"
            "Фильтрация:\n"
            "- Только активные баннеры (is_active=True)\n"
            "- В пределах дат показа (start_date/end_date)\n"
            "- По роли пользователя из JWT токена или гость\n"
            "- По типу баннера через ?type=hero|marketing\n\n"
            "Сортировка: по приоритету (DESC)"
        ),
        parameters=[
            OpenApiParameter(
                name="type",
                description="Фильтр по типу баннера: hero или marketing",
                required=False,
                type=str,
                enum=["hero", "marketing"],
            ),
        ],
        tags=["Banners"],
        responses={
            200: BannerSerializer(many=True),
        },
        examples=[
            OpenApiExample(
                name="success_example",
                summary="Успешный ответ",
                description="Список активных баннеров для пользователя",
                value=[
                    {
                        "id": 1,
                        "type": "hero",
                        "title": "Новая коллекция 2025",
                        "subtitle": "Эксклюзивные новинки для профессионалов",
                        "image_url": "/media/promos/2025/01/hero.webp",
                        "mobile_image_url": "",
                        "image_alt": "Баннер новой коллекции",
                        "cta_text": "Перейти в каталог",
                        "cta_link": "/catalog",
                        "is_advertisement": False,
                        "advertiser_name": "",
                        "advertiser_inn": "",
                        "erid": "",
                    },
                    {
                        "id": 2,
                        "type": "marketing",
                        "title": "Специальные цены для оптовиков",
                        "subtitle": "Скидки до 30% на весь ассортимент",
                        "image_url": "/media/promos/2025/01/wholesale.webp",
                        "mobile_image_url": "/media/promos/2025/01/wholesale_mobile.webp",
                        "image_alt": "Баннер оптовых цен",
                        "cta_text": "Узнать больше",
                        "cta_link": "/wholesale",
                        "is_advertisement": True,
                        "advertiser_name": 'ООО "Прайм Спорт Рус"',
                        "advertiser_inn": "7718933790",
                        "erid": "2VfnxwPqRs7",
                    },
                ],
                response_only=True,
            ),
        ],
    )
    def list(self, request: Request) -> Response:
        """
        Получить список активных баннеров для текущего пользователя

        Args:
            request: HTTP запрос с информацией о пользователе

        Returns:
            Response с сериализованными баннерами
        """
        banner_type_param = request.query_params.get("type")
        banner_type = services.validate_banner_type(banner_type_param if isinstance(banner_type_param, str) else None)
        role_key = services.get_role_key(request.user)
        cache_key = services.build_cache_key(banner_type, role_key)

        cached_data = services.get_cached_banners(cache_key)
        if cached_data is not None:
            return Response(cached_data)

        banners = services.get_active_banners_queryset(request.user, banner_type)
        serializer = BannerSerializer(banners, many=True, context={"request": request})
        data = serializer.data

        ttl = services.compute_cache_ttl(banner_type, role_key)
        services.cache_banner_response(cache_key, data, ttl)

        return Response(data)


class PlainTextJSONParser(JSONParser):
    """
    JSON в теле с `Content-Type: text/plain`.

    Фронтенд шлёт события как text/plain: это CORS-safelisted тип, запрос уходит
    без preflight, и `fetch(..., {keepalive: true})` надёжно доставляет его при
    уходе со страницы.
    """

    media_type = "text/plain"


class SiteEventsView(APIView):
    """
    Приём событий баннеров (показы и клики) для отчётности в ОРД.

    Без аутентификации, cookie и CSRF: в БД попадают только дневные суммы по
    баннеру. Путь намеренно без слов `banner`, `ad`, `promo`, `collect` —
    их режут блокировщики рекламы.
    """

    permission_classes = [permissions.AllowAny]
    authentication_classes: list = []
    # Явно: глобальные anon/user из DEFAULT_THROTTLE_CLASSES к endpoint не применяются.
    throttle_classes = [SiteEventsThrottle]
    parser_classes = [JSONParser, PlainTextJSONParser]

    @extend_schema(
        summary="Принять события баннеров",
        description=(
            "Пачка событий «показ» (`view`) и «клик» (`click`) баннеров, не больше 50 за запрос. "
            "Тело — JSON с `Content-Type: application/json` или `text/plain`. "
            "Неизвестные, выключенные, вне дат показа и не маркетинговые (шапка) баннеры "
            "молча отбрасываются — статистика ведётся только по баннерам слайдера "
            "(`type = marketing`); "
            "запросы роботов (по User-Agent) не учитываются. Успешный ответ 204 — без тела; "
            "400 и 429 возвращают JSON с описанием ошибки."
        ),
        tags=["Banners"],
        auth=[],
        request=SiteEventsBatchSerializer,
        responses={
            204: OpenApiResponse(description="События приняты"),
            400: OpenApiResponse(description="Невалидное тело запроса"),
            429: OpenApiResponse(description="Превышен лимит запросов"),
        },
    )
    def post(self, request: Request) -> Response:
        if BOT_USER_AGENT_RE.search(request.META.get("HTTP_USER_AGENT", "")):
            return Response(status=status.HTTP_204_NO_CONTENT)

        serializer = SiteEventsBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.record_events(serializer.validated_data["events"])
        return Response(status=status.HTTP_204_NO_CONTENT)

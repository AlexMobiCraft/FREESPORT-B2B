"""
Сериализаторы для общих компонентов FREESPORT
Включает Newsletter и News сериализаторы
"""

from __future__ import annotations

from typing import Any, cast

from django.db import IntegrityError, transaction
from rest_framework import serializers

from .consent_texts import MAX_VERSION_LENGTH, is_current_consent_text_version
from .models import BlogPost, Category, News, Newsletter, UserConsent
from .utils.consent_audit import get_consent_ip_address, sanitize_consent_user_agent


PDP_CONSENT_REQUIRED = "Необходимо согласие на обработку персональных данных."
# С шестого круга ревью стори 41.9 `SubscribeSerializer` этот код не выдаёт:
# активный подписчик получает свою подписку и запись согласия, как новый.
# Константу читает нейтральная ветка ответа в `subscribe` (защита от enumeration).
ALREADY_SUBSCRIBED_CODE = "already_subscribed"

# Формулировку согласия правят; вкладка, открытая до правки, продолжает
# показывать прежний текст. Такой запрос отклоняется, а не записывается
# действующей версией — см. `is_current_consent_text_version`.
CONSENT_TEXT_OUTDATED = "Текст согласия обновился. Обновите страницу и подтвердите согласие заново."
CONSENT_TEXT_OUTDATED_CODE = "consent_text_outdated"

# Поля, которыми клиент заявляет версию формулировки согласия. Официальная
# форма берёт её из константы своего бандла — это отсекает вкладку, открытую
# до правки текста. Факт показа текста человеку сервер отсюда не выводит:
# произвольный API-клиент пришлёт ту же строку, ничего не отрисовав.
# Любая ошибка на этих полях — устаревшая версия, пустая, слишком длинная, не
# строка или вовсе не переданная — означает одно: действующую формулировку запрос не
# подтвердил. Клиент обязан развести этот случай с прочей валидацией (человеку
# нужно обновить страницу, а не править ввод), поэтому машинный код выносится
# на верхний уровень ответа.
CONSENT_TEXT_VERSION_FIELDS = frozenset(
    {
        "consent_text_version",
        "pdp_consent_text_version",
        "marketing_consent_text_version",
    }
)


def consent_text_outdated_error() -> serializers.ValidationError:
    """Field-level ошибка устаревшей формулировки с устойчивым machine-code.

    Поднимается из `validate_<поле версии>`, а не из object-level `validate()`:
    DRF собирает field-level ошибки всех полей, а `validate()` при любой из них
    не вызывает. Сверка версии там пропадала бы рядом с ошибкой email, роли или
    галочки, и ответ ушёл бы без машинного кода `consent_text_outdated`.
    """
    return serializers.ValidationError(CONSENT_TEXT_OUTDATED, code=CONSENT_TEXT_OUTDATED_CODE)


def has_error_code(detail: object, code: str) -> bool:
    """Проверить DRF ErrorDetail code в nested serializer detail."""
    if isinstance(detail, dict):
        return any(has_error_code(value, code) for value in detail.values())
    if isinstance(detail, (list, tuple)):
        return any(has_error_code(value, code) for value in detail)
    return getattr(detail, "code", None) == code


def _error_messages(value: object) -> list[str]:
    """Свести любое DRF-значение ошибки к плоскому списку строк."""
    if isinstance(value, dict):
        return [message for nested in value.values() for message in _error_messages(nested)]
    if isinstance(value, (list, tuple)):
        return [message for item in value for message in _error_messages(item)]
    return [str(value)]


def consent_text_outdated_payload(errors: object) -> dict[str, Any] | None:
    """Тело ответа `400`, если ошибки касаются версии показанной формулировки.

    Возвращает `{"error": "consent_text_outdated", "details": {...}}` — тот же
    вид, что у `consent_persistence_failed`. Машинный код обязан доходить до
    клиента: `ErrorDetail.code` живёт только внутри Python, JSONRenderer отдаёт
    голые массивы строк, а у пропущенного поля код и вовсе `required`. Без
    верхнеуровневого кода фронт вынужден узнавать этот случай по тексту
    сообщения — то есть ломаться от любой правки формулировки ошибки.

    `details` сохраняет ВСЕ ошибки запроса массивами строк: заодно пришедшая
    ошибка email не должна пропадать из-за того, что форма ещё и устарела.
    У полей версии сообщение всегда одно — `CONSENT_TEXT_OUTDATED`: фронт
    показывает его человеку как требование обновить страницу.
    None — ошибки к версии формулировки не относятся, ответ прежний.
    """
    if not isinstance(errors, dict):
        return None

    relevant = any(field in CONSENT_TEXT_VERSION_FIELDS for field in errors) or has_error_code(
        errors, CONSENT_TEXT_OUTDATED_CODE
    )
    if not relevant:
        return None

    details: dict[str, list[str]] = {}
    for field, value in errors.items():
        if field in CONSENT_TEXT_VERSION_FIELDS:
            # Ключи `error_messages` поля переопределяют не всё: ноль-байт и
            # одиночный суррогат `CharField` отсекает своими валидаторами, и их
            # текст остался бы в ответе вместо требования обновить страницу.
            details[str(field)] = [CONSENT_TEXT_OUTDATED]
        else:
            details[str(field)] = _error_messages(value)

    return {"error": CONSENT_TEXT_OUTDATED_CODE, "details": details}


class SubscribeSerializer(serializers.Serializer):
    """
    Сериализатор для подписки на email-рассылку.
    Валидирует email и создает запись в Newsletter.
    """

    email = serializers.EmailField(
        required=True,
        max_length=255,
        help_text="Email адрес для подписки",
    )
    pdp_consent = serializers.BooleanField(
        write_only=True,
        required=True,
        error_messages={
            "required": PDP_CONSENT_REQUIRED,
            "invalid": PDP_CONSENT_REQUIRED,
            "null": PDP_CONSENT_REQUIRED,
        },
    )
    # Версия формулировки, которую показывает официальная форма (стори 41.9).
    # Значение приходит из константы фронта, собранной в тот же бандл, что и сам
    # текст: вкладка, открытая до правки формулировки, пришлёт прежнюю версию и
    # будет отклонена. Факт показа текста человеку сервер отсюда не выводит —
    # ту же строку пришлёт и клиент, ничего не отрисовавший.
    consent_text_version = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_VERSION_LENGTH,
        error_messages={
            "required": CONSENT_TEXT_OUTDATED,
            "blank": CONSENT_TEXT_OUTDATED,
            "null": CONSENT_TEXT_OUTDATED,
            # Массив, объект или boolean — тот же отказ, что и прочие ошибки поля версии.
            "invalid": CONSENT_TEXT_OUTDATED,
            "max_length": CONSENT_TEXT_OUTDATED,
        },
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Нормализует email перед сохранением.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        return value

    def validate_consent_text_version(self, value: str) -> str:
        """Сверить заявленную версию с действующей формулировкой подписки.

        Проверка на уровне поля, а не в `validate()`: рядом с ошибкой email или
        галочки `validate()` не вызывается, и ответ ушёл бы без машинного кода
        `consent_text_outdated` (см. `consent_text_outdated_error`).

        Чекбокс формы подписки один и покрывает оба согласия (редакция 2 стори
        41.3), но версия сверяется для каждого типа отдельно: при будущем
        расщеплении чекбоксов одна проверка молча пропустила бы устаревшую
        половину формы.
        """
        for consent_type, _label in UserConsent.CONSENT_TYPE_CHOICES:
            if not is_current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, consent_type, value):
                raise consent_text_outdated_error()
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Проверить обязательное согласие на обработку ПДн."""
        if not isinstance(self.initial_data, dict):
            raise serializers.ValidationError({"non_field_errors": "Ожидался JSON-объект."})

        # BooleanField коэрсит truthy-строки в True; для 152-ФЗ нужен исходный JSON boolean true.
        if self.initial_data.get("pdp_consent") is not True:
            raise serializers.ValidationError({"pdp_consent": PDP_CONSENT_REQUIRED})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Newsletter:
        """
        Создание подписки.
        Если email ранее отписался - реактивируем подписку.
        Активную подписку возвращаем как есть: запись согласия делает view.
        """
        validated_data.pop("pdp_consent", False)
        # Версия уже сверена `validate_consent_text_version()`; в `Newsletter` она не хранится —
        # доказательство согласия живёт в `UserConsent` (пишет view).
        validated_data.pop("consent_text_version", None)
        email = validated_data["email"]

        # Получаем IP и User-Agent из контекста (request)
        request = self.context.get("request")
        ip_address = None
        user_agent = ""

        if request is not None:
            ip_address = get_consent_ip_address(request)
            user_agent = sanitize_consent_user_agent(request.META.get("HTTP_USER_AGENT", ""))

        with transaction.atomic():
            try:
                subscription = Newsletter.objects.select_for_update().get(email=email)
            except Newsletter.DoesNotExist:
                try:
                    # Savepoint: без него IntegrityError оставил бы транзакцию
                    # прерванной, и перечитать строку ниже было бы нельзя.
                    with transaction.atomic():
                        return Newsletter.objects.create(
                            email=email,
                            ip_address=ip_address,
                            user_agent=user_agent,
                        )
                except IntegrityError:
                    # Параллельный запрос успел создать подписку между чтением и
                    # вставкой — для этого запроса это тот же «уже подписан».
                    # Строка перечитывается под блокировкой, согласие ниже пишется.
                    raced = Newsletter.objects.select_for_update().filter(email=email).first()
                    if raced is None:
                        # Строки нет — нарушено не уникальное ограничение email.
                        # Нейтральный успех был бы неправдой; view ответит 503.
                        raise
                    subscription = raced

            if subscription.is_active:
                # Активный подписчик снова поставил галочку и отправил форму — это
                # новый явный факт согласия (ФЗ-152 ст. 9): после правки формулировки
                # только он доказывает согласие на новую редакцию. Подписка
                # возвращается как есть, view пишет обе записи `UserConsent`, а ответ
                # неотличим от новой подписки (enumeration). `Newsletter` не журнал
                # согласий, поэтому строку не трогаем (стори 41.9, шестой круг ревью).
                return subscription

            # Реактивируем подписку
            subscription.is_active = True
            subscription.unsubscribed_at = None
            subscription.ip_address = ip_address
            subscription.user_agent = user_agent
            subscription.save(
                update_fields=[
                    "is_active",
                    "unsubscribed_at",
                    "ip_address",
                    "user_agent",
                ]
            )
            return subscription


class SubscribeResponseSerializer(serializers.Serializer):
    """Сериализатор ответа при успешной подписке."""

    message = serializers.CharField()
    email = serializers.EmailField()


class UnsubscribeSerializer(serializers.Serializer):
    """
    Сериализатор для отписки от email-рассылки.
    Валидирует email и деактивирует подписку.
    """

    email = serializers.EmailField(
        required=True,
        max_length=255,
        help_text="Email адрес для отписки",
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Нормализует email без раскрытия наличия активной подписки.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        return value

    def save(self, **kwargs: Any) -> Newsletter | None:
        """
        Отписка от рассылки.
        Возвращает None, если активной подписки нет, чтобы не раскрывать наличие email.
        """
        email = self.validated_data["email"]
        try:
            subscription = Newsletter.objects.get(email=email, is_active=True)
        except Newsletter.DoesNotExist:
            return None

        subscription.unsubscribe()
        return subscription


class UnsubscribeResponseSerializer(serializers.Serializer):
    """Сериализатор ответа при успешной отписке."""

    message = serializers.CharField()
    email = serializers.EmailField()


class NewsSerializer(serializers.ModelSerializer):
    """
    Сериализатор новости для публичного API.
    Возвращает только опубликованные поля.
    """

    class Meta:
        model = News
        fields = [
            "id",
            "title",
            "slug",
            "excerpt",
            "content",
            "image",
            "published_at",
            "created_at",
            "updated_at",
            "author",
            "category",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: News) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data: dict[str, Any] = super().to_representation(instance)

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }

        return data


class BlogPostListSerializer(serializers.ModelSerializer):
    """
    Сериализатор статьи блога для списка (компактный формат).
    Используется в BlogPostListView для отображения превью статей.
    """

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "image",
            "author",
            "category",
            "published_at",
        ]
        read_only_fields = [
            "id",
            "slug",
        ]

    def to_representation(self, instance: BlogPost) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data = cast(dict[str, Any], super().to_representation(instance))

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }
        else:
            data["category"] = None

        return data


class BlogPostDetailSerializer(serializers.ModelSerializer):
    """
    Сериализатор статьи блога для детальной страницы (полный формат).
    Используется в BlogPostDetailView для отображения полной статьи.
    Включает все поля, включая content и SEO meta-данные.
    """

    class Meta:
        model = BlogPost
        fields = [
            "id",
            "title",
            "slug",
            "subtitle",
            "excerpt",
            "content",
            "image",
            "author",
            "category",
            "published_at",
            "meta_title",
            "meta_description",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "slug",
            "created_at",
            "updated_at",
        ]

    def to_representation(self, instance: BlogPost) -> dict[str, Any]:
        """
        Кастомизация вывода.
        Преобразуем image в полный URL и category в детальную информацию.
        """
        data = cast(dict[str, Any], super().to_representation(instance))

        # Преобразуем image в полный URL
        request = self.context.get("request")
        if instance.image and request:
            data["image"] = request.build_absolute_uri(instance.image.url)
        elif not instance.image:
            data["image"] = None

        # Добавляем детальную информацию о категории
        if instance.category:
            data["category"] = {
                "id": instance.category.id,
                "name": instance.category.name,
                "slug": instance.category.slug,
            }
        else:
            data["category"] = None

        return data

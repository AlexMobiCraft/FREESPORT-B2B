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
# Согласие на рассылку при подписке обязательно и берётся отдельным чекбоксом
# (стори 41.11): подписки без согласия на письма не бывает.
MARKETING_CONSENT_REQUIRED = "Необходимо согласие на получение рассылок по электронной почте."
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
# Со стори 41.11 подписка шлёт те же поля, что и регистрация; прежнее
# `consent_text_version` запроса подписки из контракта удалено.
CONSENT_TEXT_VERSION_FIELDS = frozenset(
    {
        "pdp_consent_text_version",
        "marketing_consent_text_version",
    }
)

# `error_messages` безусловно обязательного поля версии. Все ключи — одно
# требование обновить страницу: массив, объект или boolean (`invalid`), пустая
# строка, `null`, слишком длинное значение и отсутствие поля означают одно —
# действующую формулировку запрос не подтвердил.
# `dict[str, Any]`, а не `dict[str, str]`: `dict` инвариантен, а стаб DRF ждёт
# значения типа «строка или lazy-строка».
CONSENT_TEXT_VERSION_ERROR_MESSAGES: dict[str, Any] = {
    "required": CONSENT_TEXT_OUTDATED,
    "blank": CONSENT_TEXT_OUTDATED,
    "null": CONSENT_TEXT_OUTDATED,
    "invalid": CONSENT_TEXT_OUTDATED,
    "max_length": CONSENT_TEXT_OUTDATED,
}


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
    # Согласие на рассылку — отдельный обязательный чекбокс (стори 41.11): ст. 9
    # ч. 1 152-ФЗ требует оформлять согласие на ПДн отдельно от согласия на рекламу.
    marketing_consent = serializers.BooleanField(
        write_only=True,
        required=True,
        error_messages={
            "required": MARKETING_CONSENT_REQUIRED,
            "invalid": MARKETING_CONSENT_REQUIRED,
            "null": MARKETING_CONSENT_REQUIRED,
        },
    )
    # Версии формулировок, которые показывает официальная форма (стори 41.9) —
    # по одной на чекбокс (стори 41.11). Значения приходят из константы фронта,
    # собранной в тот же бандл, что и сами тексты: вкладка, открытая до правки
    # формулировки, пришлёт прежнюю версию и будет отклонена. Факт показа текста
    # человеку сервер отсюда не выводит — ту же строку пришлёт и клиент, ничего не
    # отрисовавший. Обе версии обязательны безусловно, в отличие от регистрации:
    # согласие на рассылку при подписке обязательно.
    pdp_consent_text_version = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_VERSION_LENGTH,
        error_messages=CONSENT_TEXT_VERSION_ERROR_MESSAGES,
    )
    marketing_consent_text_version = serializers.CharField(
        write_only=True,
        required=True,
        max_length=MAX_VERSION_LENGTH,
        error_messages=CONSENT_TEXT_VERSION_ERROR_MESSAGES,
    )

    def validate_email(self, value: str) -> str:
        """
        Валидация email адреса.
        Нормализует email перед сохранением.
        """
        # Нормализация email (lowercase)
        value = value.lower().strip()

        return value

    def validate_pdp_consent_text_version(self, value: str) -> str:
        """Сверить версию чекбокса ПДн с действующей формулировкой подписки.

        Проверка на уровне поля, а не в `validate()`: рядом с ошибкой email или
        галочки `validate()` не вызывается, и ответ ушёл бы без машинного кода
        `consent_text_outdated` (см. `consent_text_outdated_error`). Каждое поле
        версии сверяется со своей привязкой реестра: версия рассылки, присланная
        в поле ПДн, отклоняется.
        """
        if not is_current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract", value):
            raise consent_text_outdated_error()
        return value

    def validate_marketing_consent_text_version(self, value: str) -> str:
        """Сверить версию чекбокса рассылки с действующей формулировкой подписки.

        Field-level по той же причине, что и `validate_pdp_consent_text_version`.
        """
        if not is_current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "marketing_email", value):
            raise consent_text_outdated_error()
        return value

    def validate_pdp_consent(self, value: bool) -> bool:
        """Согласие на обработку ПДн — только исходный JSON `true`.

        `BooleanField` превращает `"true"`, `"on"`, `1` в `True`, а 152-ФЗ требует
        явного согласия. Проверка на уровне поля, а не в `validate()`: DRF
        собирает field-level ошибки всех полей, а `validate()` при любой из них не
        вызывает. Там ошибка email или соседнего флага скрыла бы эту, и клиент
        узнавал бы об отказах по одному на попытку (ревью стори 41.11).
        """
        if self.initial_data.get("pdp_consent") is not True:
            raise serializers.ValidationError(PDP_CONSENT_REQUIRED)
        return value

    def validate_marketing_consent(self, value: bool) -> bool:
        """Согласие на рассылку (38-ФЗ) — только исходный JSON `true`.

        Field-level по той же причине, что и `validate_pdp_consent`.
        """
        if self.initial_data.get("marketing_consent") is not True:
            raise serializers.ValidationError(MARKETING_CONSENT_REQUIRED)
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Отклонить тело запроса, которое не является JSON-объектом."""
        if not isinstance(self.initial_data, dict):
            raise serializers.ValidationError({"non_field_errors": "Ожидался JSON-объект."})

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Newsletter:
        """
        Создание подписки.
        Если email ранее отписался - реактивируем подписку.
        Активную подписку возвращаем как есть: запись согласия делает view.
        """
        validated_data.pop("pdp_consent", False)
        validated_data.pop("marketing_consent", False)
        # Версии уже сверены `validate_pdp_consent_text_version()` и
        # `validate_marketing_consent_text_version()`; в `Newsletter` они не хранятся —
        # доказательство согласия живёт в `UserConsent` (пишет view).
        validated_data.pop("pdp_consent_text_version", None)
        validated_data.pop("marketing_consent_text_version", None)
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

            subscription.rotate_unsubscribe_token()
            if subscription.is_active:
                # Активный подписчик снова поставил галочку и отправил форму — это
                # новый явный факт согласия (ФЗ-152 ст. 9): после правки формулировки
                # только он доказывает согласие на новую редакцию. Подписка
                # возвращается как есть, view пишет обе записи `UserConsent`, а ответ
                # неотличим от новой подписки (enumeration). `Newsletter` не журнал
                # согласий, поэтому изменяется только bearer-токен новой ссылки.
                subscription.save(update_fields=["unsubscribe_token"])
                return subscription

            # Реактивируем подписку
            subscription.is_active = True
            subscription.unsubscribed_at = None
            subscription.ip_address = ip_address
            subscription.user_agent = user_agent
            subscription.save(
                update_fields=[
                    "unsubscribe_token",
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


class TokenUnsubscribeSerializer(serializers.Serializer):
    """Принимает только непрозрачный bearer-токен отписки."""

    token = serializers.RegexField(r"^[A-Za-z0-9_-]{43}$", max_length=43)


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

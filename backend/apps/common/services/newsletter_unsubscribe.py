"""Атомарная token-based отписка от маркетинговой рассылки."""

import re

from django.db import transaction
from django.db.models import Q, QuerySet

from apps.common.models import Newsletter

TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")


class InvalidUnsubscribeToken(ValueError):
    """Токен повреждён, неизвестен или заменён новым согласием."""


def unsubscribe_by_token(token: object) -> Newsletter:
    """Блокирует подписку и идемпотентно применяет отписку."""
    if not isinstance(token, str) or TOKEN_PATTERN.fullmatch(token) is None:
        raise InvalidUnsubscribeToken

    with transaction.atomic():
        subscription = Newsletter.objects.select_for_update().filter(unsubscribe_token=token).first()
        if subscription is None:
            raise InvalidUnsubscribeToken
        subscription.unsubscribe()
        return subscription


def normalize_subscription_email(email: str | None) -> str:
    """Нормализация адреса подписки — одна для регистрации и личного кабинета.

    `Newsletter.email` хранится в нижнем регистре (`SubscribeSerializer`, регистрация);
    поиск при этом всё равно регистронезависимый — на случай исторических строк.
    """
    return (email or "").lower().strip()


def _user_subscriptions(user: object) -> QuerySet[Newsletter]:
    """Подписки пользователя: по адресу учётной записи или по привязке `Newsletter.user`.

    Привязка нужна, когда email учётной записи сменили (админка, привязка 1С):
    подписка на прежний адрес остаётся его, и отозвать её он должен мочь из
    кабинета. Email из тела запроса не принимается — только собственные подписки.
    """
    # Пустое `Q()` не годится как стартовое: `filter(Q())` вернул бы все подписки.
    conditions = []
    user_pk = getattr(user, "pk", None)
    if user_pk is not None:
        conditions.append(Q(user_id=user_pk))
    email = normalize_subscription_email(getattr(user, "email", ""))
    if email:
        conditions.append(Q(email__iexact=email))
    if not conditions:
        return Newsletter.objects.none()

    condition = conditions[0]
    for extra in conditions[1:]:
        condition |= extra
    return Newsletter.objects.filter(condition)


def is_user_subscribed(user: object) -> bool:
    """Есть ли у пользователя активная подписка на рассылку."""
    return _user_subscriptions(user).filter(is_active=True).exists()


def unsubscribe_user(user: object) -> None:
    """Идемпотентно отписывает все подписки пользователя; нет подписок — ничего не делает.

    Журнал `UserConsent` не трогается: факт отзыва фиксирует
    `Newsletter.unsubscribed_at`, как и при отписке по ссылке из письма.
    """
    with transaction.atomic():
        for subscription in _user_subscriptions(user).select_for_update().order_by("pk"):
            subscription.unsubscribe()

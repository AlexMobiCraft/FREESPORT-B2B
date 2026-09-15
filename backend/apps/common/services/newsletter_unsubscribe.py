"""Атомарная token-based отписка от маркетинговой рассылки."""

import re

from django.db import transaction

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

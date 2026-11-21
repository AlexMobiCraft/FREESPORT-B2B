"""Создание и реактивация подписки на маркетинговую рассылку.

Общая точка для формы подписки (`SubscribeSerializer.create`) и регистрации с
согласием на рассылку (`UserRegistrationView.post`). Доказательство согласия
здесь не пишется — это журнал `UserConsent`, его ведут вызывающие.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import IntegrityError, transaction

from apps.common.models import Newsletter

if TYPE_CHECKING:
    from apps.users.models import User


def activate_newsletter_subscription(
    email: str,
    ip_address: str | None,
    user_agent: str,
    user: User | None = None,
) -> Newsletter:
    """Создаёт подписку или реактивирует прежнюю; активную возвращает как есть.

    Каждый вызов — новый явный факт согласия, поэтому токен отписки меняется
    всегда: прежние ссылки из писем перестают действовать. `user` проставляется,
    только если у записи его ещё нет, — чужую привязку вызов не перезаписывает.
    """
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
                        user=user,
                    )
            except IntegrityError:
                # Параллельный запрос успел создать подписку между чтением и
                # вставкой — для этого запроса это тот же «уже подписан».
                # Строка перечитывается под блокировкой, согласие пишет вызывающий.
                raced = Newsletter.objects.select_for_update().filter(email=email).first()
                if raced is None:
                    # Строки нет — нарушено не уникальное ограничение email.
                    # Нейтральный успех был бы неправдой — ошибка уходит вызывающему
                    # (подписка отвечает 503, регистрация откатывается целиком).
                    raise
                subscription = raced

        subscription.rotate_unsubscribe_token()
        update_fields = ["unsubscribe_token"]
        if user is not None and subscription.user_id is None:
            subscription.user = user
            update_fields.append("user")

        if subscription.is_active:
            # Активный подписчик снова дал согласие — это новый явный факт согласия
            # (ФЗ-152 ст. 9): после правки формулировки только он доказывает согласие
            # на новую редакцию. Ответ неотличим от новой подписки (enumeration).
            # `Newsletter` не журнал согласий, поэтому меняется только bearer-токен
            # новой ссылки (и привязка к пользователю, если её не было).
            subscription.save(update_fields=update_fields)
            return subscription

        subscription.is_active = True
        subscription.unsubscribed_at = None
        subscription.ip_address = ip_address
        subscription.user_agent = user_agent
        subscription.save(update_fields=[*update_fields, "is_active", "unsubscribed_at", "ip_address", "user_agent"])
        return subscription

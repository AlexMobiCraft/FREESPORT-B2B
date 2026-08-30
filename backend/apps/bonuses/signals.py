"""Сигналы бонусной программы.

Начисление привязано к `post_save` на `Order`, а не к сервису импорта:
так оно срабатывает и при импорте статусов из 1С (агрегация мастера
вызывает `master.save()`), и при ручной смене статуса в админке.
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.orders.models import Order

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Order, dispatch_uid="bonuses_accrue_on_order_status")
def accrue_bonus_on_order_status(sender, instance: Order, **kwargs) -> None:
    """Начисляет бонус тренеру при переходе мастер-заказа в целевой статус.

    Все проверки (активность программы, роль, верификация, целевой статус,
    идемпотентность) выполняются внутри `accrue_for_order`. Здесь только
    дешёвый отсев не-мастеров, чтобы не ходить в БД на каждое сохранение
    субзаказа.
    """
    # loaddata/фикстуры не должны создавать денежные операции
    if kwargs.get("raw"):
        return

    if not instance.is_master:
        return

    from apps.bonuses.services.accrual import accrue_for_order

    try:
        accrue_for_order(instance)
    except Exception:
        # Ошибка начисления не должна ронять сохранение заказа и импорт из 1С
        logger.exception("Ошибка начисления бонуса по заказу %s", instance.pk)

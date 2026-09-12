# backend/apps/cart/tasks.py

import logging

from celery import shared_task
from django.core.management import call_command

logger = logging.getLogger(__name__)


@shared_task(name="apps.cart.tasks.clear_abandoned_carts_task")
def clear_abandoned_carts_task(hours: int = 24) -> None:
    """
    Асинхронная задача Celery для запуска команды очистки "брошенных" корзин.

    Args:
        hours (int): Количество часов, после которых корзина считается "брошенной".
    """
    try:
        logger.info("Запуск задачи clear_abandoned_carts_task с параметром hours=%s", hours)
        call_command("clear_abandoned_carts", f"--hours={hours}")
        logger.info("Задача clear_abandoned_carts_task успешно завершена.")
    except Exception as e:
        logger.error(
            "Ошибка при выполнении задачи clear_abandoned_carts_task: %s",
            e,
            exc_info=True,
        )
        # В реальном проекте здесь можно добавить механизм повторных попыток
        # или систему уведомлений об ошибках
        raise

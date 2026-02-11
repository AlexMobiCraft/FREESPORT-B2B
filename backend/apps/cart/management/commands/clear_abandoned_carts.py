# backend/apps/cart/management/commands/clear_abandoned_carts.py

import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cart.models import CartItem

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """
    Django management-команда для очистки "брошенных" корзин.

    "Брошенной" считается корзина, товары в которой не обновлялись
    дольше определенного времени (по умолчанию 24 часа).

    При удалении CartItem автоматически срабатывает сигнал post_delete,
    который освобождает зарезервированное количество товара (reserved_quantity).
    """

    help = 'Удаляет старые "брошенные" корзины для освобождения резервов товаров.'

    def add_arguments(self, parser):
        parser.add_argument(
            "--hours",
            type=int,
            default=24,
            help='Количество часов, после которых корзина считается "брошенной".',
        )

    def handle(self, *args, **options):
        hours = options["hours"]
        time_threshold = timezone.now() - timedelta(hours=hours)

        self.stdout.write(self.style.NOTICE(f"Начинаю поиск корзин, неактивных более {hours} часов..."))

        # Находим все элементы корзин, которые старше заданного порога
        # Мы используем `added_at` из CartItem, так как это поле отражает
        # время добавления товара в корзину.
        abandoned_cart_items = CartItem.objects.filter(added_at__lt=time_threshold)

        count = abandoned_cart_items.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS('"Брошенных" корзин не найдено. Завершаю работу.'))

        self.stdout.write(self.style.WARNING(f"Найдено {count} устаревших позиций в корзинах. Начинаю удаление..."))
        # Удаляем найденные элементы. Сигнал post_delete на CartItem
        # позаботится об обновлении reserved_quantity у товаров.
        deleted_count, _ = abandoned_cart_items.delete()

        self.stdout.write(
            self.style.SUCCESS(
                (f'Успешно удалено {deleted_count} позиций из "брошенных" корзин. ' "Резервы освобождены.")
            )
        )
        logger.info(f"Task clear_abandoned_carts: удалено {deleted_count} позиций.")

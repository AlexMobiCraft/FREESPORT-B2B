"""
Команда для очистки старых гостевых корзин
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.cart.models import Cart


class Command(BaseCommand):
    help = "Очистка старых гостевых корзин (старше 30 дней)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--days",
            type=int,
            default=30,
            help='Количество дней для определения "старых" корзин (по умолчанию 30)',
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать количество корзин для удаления без фактического удаления",
        )

    def handle(self, *args, **options):
        days = options["days"]
        dry_run = options["dry_run"]

        # Дата отсечки
        cutoff_date = timezone.now() - timedelta(days=days)

        # Находим старые гостевые корзины
        old_guest_carts = Cart.objects.filter(
            user__isnull=True,  # Только гостевые корзины
            session_key__isnull=False,
            updated_at__lt=cutoff_date,
        )

        count = old_guest_carts.count()

        if dry_run:
            self.stdout.write(
                self.style.WARNING(f"Найдено {count} гостевых корзин старше {days} дней " f"для удаления")
            )
            return

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Нет старых гостевых корзин для удаления"))
            return

        # Удаляем старые корзины
        deleted_count, _ = old_guest_carts.delete()

        self.stdout.write(self.style.SUCCESS(f"Успешно удалено {deleted_count} старых гостевых корзин"))

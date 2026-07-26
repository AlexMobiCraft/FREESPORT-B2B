"""
Management команда для полной очистки каталога товаров, брендов и категорий
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Полная очистка каталога товаров, брендов и категорий"

    def add_arguments(self, parser):
        parser.add_argument("--confirm", action="store_true", help="Подтверждение очистки всех данных")

    def handle(self, *args, **options):
        if not options["confirm"]:
            raise CommandError("Используйте --confirm для подтверждения очистки")

        self.stdout.write(self.style.WARNING("⚠️  ВНИМАНИЕ: Удаление ВСЕХ данных..."))
        self.stdout.write(self.style.WARNING("Это удалит все товары, бренды, категории и связанные данные!"))
        self.stdout.write(self.style.WARNING("Действие необратимо!"))

        # Дополнительное предупреждение
        self.stdout.write(self.style.WARNING("Рекомендуется создать бэкап перед очисткой: python manage.py backup_db"))

        # Запрос подтверждения
        self.stdout.write(self.style.WARNING('Для подтверждения введите "yes" и нажмите Enter:'))

        # В реальном проекте здесь можно добавить интерактивный ввод
        # Но для безопасности используем простое подтверждение
        confirm = input().strip().lower()

        if confirm != "yes":
            self.stdout.write(self.style.ERROR("❌ Операция отменена"))
            return

        self.stdout.write(self.style.SUCCESS("\n🔄 Начинаю очистку..."))

        with transaction.atomic():
            from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductImage

            # Очистка в правильном порядке с учетом foreign key constraints
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()
            ImportSession.objects.all().delete()
            PriceType.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("✅ Каталог полностью очищен"))
        self.stdout.write(self.style.SUCCESS("💡 Теперь можно выполнить повторный импорт с чистой базой"))

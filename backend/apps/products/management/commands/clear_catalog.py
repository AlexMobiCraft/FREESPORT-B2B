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
            from apps.products.models import Brand, Category, ImportSession, Product, ProductImage

            # Очистка в правильном порядке с учетом foreign key constraints
            ProductImage.objects.all().delete()
            Product.objects.all().delete()
            Brand.objects.all().delete()
            Category.objects.all().delete()
            ImportSession.objects.all().delete()

        # Справочник PriceType НЕ чистится намеренно. Импорт priceLists
        # восстанавливает из XML только onec_name, is_active и product_field;
        # колонки, которые ведёт человек, из выгрузки не выводятся и теряются
        # безвозвратно:
        #   user_role     — маппинг «вид цен 1С → роль портала», заполнен
        #                   миграцией 0054 и правится менеджером из админки;
        #                   миграция повторно не выполняется, роли не вернутся;
        #   product_field — ручная правка для видов цен, которые
        #                   _map_price_type_to_field не опознаёт по названию.
        # После чистки + импорта каталог выглядит здоровым, а роли молча
        # перестают назначаться — заметить это без счётчиков невозможно.
        # Ссылок по внешнему ключу на PriceType нет, удалять его для
        # целостности каталога не требуется.

        self.stdout.write(self.style.SUCCESS("✅ Каталог полностью очищен"))
        self.stdout.write(self.style.SUCCESS("💡 Теперь можно выполнить повторный импорт с чистой базой"))
        self.stdout.write(self.style.SUCCESS("ℹ️  Справочник видов цен (PriceType) сохранён вместе с маппингом ролей"))

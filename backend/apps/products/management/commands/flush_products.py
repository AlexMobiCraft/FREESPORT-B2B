"""
Management команда для очистки товаров и вариантов перед миграцией.

Story 13.4: Миграция данных в production
AC3: Старые данные Products очищены через management command

Эта команда удаляет:
- ProductVariant (все записи)
- Product (все записи)

НЕ удаляет (сохраняет):
- ColorMapping (20 базовых цветов остаются)
- Brand (бренды сохраняются)
- Category (категории сохраняются)
- ImportSession (история импортов сохраняется)
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

if TYPE_CHECKING:
    from argparse import ArgumentParser

logger = logging.getLogger("flush_products")


class Command(BaseCommand):
    """
    Очистка товаров и вариантов перед миграцией на ProductVariant систему.

    Использование:
        python manage.py flush_products --confirm

    Опции:
        --confirm: Обязательный флаг для подтверждения удаления
        --dry-run: Показать что будет удалено без фактического удаления
        --skip-interactive: Пропустить интерактивное подтверждение (для CI/CD)
    """

    help = "Очистка товаров и вариантов перед миграцией " "(сохраняет ColorMapping, бренды, категории)"

    def add_arguments(self, parser: ArgumentParser) -> None:
        """Добавление аргументов командной строки."""
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Подтвердить удаление (обязательно)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет удалено без фактического удаления",
        )
        parser.add_argument(
            "--skip-interactive",
            action="store_true",
            help="Пропустить интерактивное подтверждение (для CI/CD)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Основная логика команды."""
        dry_run: bool = options["dry_run"]
        confirm: bool = options["confirm"]
        skip_interactive: bool = options["skip_interactive"]

        # Проверка флага --confirm
        if not confirm and not dry_run:
            raise CommandError(
                "Необходимо подтвердить удаление: --confirm\n" "Или используйте --dry-run для просмотра без удаления"
            )

        # Импорт моделей
        from apps.products.models import ColorMapping, Product, ProductVariant

        # Подсчёт записей
        variant_count = ProductVariant.objects.count()
        product_count = Product.objects.count()
        color_count = ColorMapping.objects.count()

        # Вывод информации
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(self.style.WARNING("⚠️  FLUSH PRODUCTS - Очистка товаров перед миграцией"))
        self.stdout.write("=" * 60)

        self.stdout.write("\n📊 Текущее состояние БД:")
        self.stdout.write(f"   • ProductVariant: {variant_count} записей")
        self.stdout.write(f"   • Product: {product_count} записей")
        self.stdout.write(f"   • ColorMapping: {color_count} записей (будут сохранены)")

        self.stdout.write("\n🗑️  Будет удалено:")
        self.stdout.write(self.style.ERROR(f"   • {variant_count} ProductVariant записей"))
        self.stdout.write(self.style.ERROR(f"   • {product_count} Product записей"))

        self.stdout.write("\n✅ Будет сохранено:")
        self.stdout.write(self.style.SUCCESS(f"   • {color_count} ColorMapping записей"))
        self.stdout.write(self.style.SUCCESS("   • Все Brand записи"))
        self.stdout.write(self.style.SUCCESS("   • Все Category записи"))
        self.stdout.write(self.style.SUCCESS("   • Все ImportSession записи"))

        # Dry run - только показать
        if dry_run:
            self.stdout.write(self.style.WARNING("\n🔍 DRY RUN: Никакие данные не были удалены"))
            return

        # Интерактивное подтверждение
        if not skip_interactive:
            self.stdout.write(self.style.WARNING('\n⚠️  Для подтверждения введите "yes" и нажмите Enter:'))
            user_input = input().strip().lower()

            if user_input != "yes":
                self.stdout.write(self.style.ERROR("\n❌ Операция отменена"))
                return

        # Выполнение удаления
        self.stdout.write(self.style.WARNING("\n🔄 Начинаю удаление..."))

        try:
            with transaction.atomic():
                # Удаляем ProductVariant первым (FK на Product)
                deleted_variants = ProductVariant.objects.all().delete()[0]
                self.stdout.write(f"   ✓ Удалено ProductVariant: {deleted_variants}")
                logger.info(f"Deleted {deleted_variants} ProductVariant records")

                # Удаляем Product
                deleted_products = Product.objects.all().delete()[0]
                self.stdout.write(f"   ✓ Удалено Product: {deleted_products}")
                logger.info(f"Deleted {deleted_products} Product records")

            # Финальная статистика
            self.stdout.write("\n" + "=" * 60)
            self.stdout.write(self.style.SUCCESS("✅ FLUSH COMPLETED SUCCESSFULLY"))
            self.stdout.write("=" * 60)

            self.stdout.write("\n📊 Итого удалено:")
            self.stdout.write(f"   • ProductVariant: {deleted_variants}")
            self.stdout.write(f"   • Product: {deleted_products}")

            # Проверка ColorMapping
            remaining_colors = ColorMapping.objects.count()
            self.stdout.write(f"\n✅ ColorMapping сохранены: {remaining_colors} записей")

            self.stdout.write(
                self.style.SUCCESS(
                    "\n💡 Теперь можно выполнить импорт из 1С:\n" "   python manage.py import_products_from_1c --full"
                )
            )

            logger.info(
                f"Flush completed: {deleted_variants} variants, "
                f"{deleted_products} products deleted. "
                f"{remaining_colors} colors preserved."
            )

        except Exception as e:
            logger.error(f"Flush failed: {e}")
            raise CommandError(f"Ошибка при удалении: {e}")

"""
Management команда для очистки некорректных значений size_value в ProductVariant.

Очищает size_value='Да' и подобные невалидные значения.
После очистки нужно запустить повторный импорт из offers.xml для обновления данных.

Использование:
    python manage.py fix_variant_sizes --dry-run    # Тестовый запуск
    python manage.py fix_variant_sizes              # Очистка данных

После очистки:
    python manage.py import_products_from_1c --file-type=offers \
        --data-dir=data/import_1c
"""

import re

from django.core.management.base import BaseCommand

from apps.products.models import ProductVariant


class Command(BaseCommand):
    help = "Очистка некорректных значений size_value в ProductVariant"

    # Невалидные значения размера (булевые флаги)
    INVALID_VALUES = [
        "Да",
        "да",
        "Нет",
        "нет",
        "Yes",
        "yes",
        "No",
        "no",
        "True",
        "true",
        "False",
        "false",
        "-",
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без записи в БД",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== ТЕСТОВЫЙ ЗАПУСК (dry-run) ===\n"))

        # Поиск вариантов с невалидными значениями size_value
        invalid_variants = ProductVariant.objects.filter(size_value__in=self.INVALID_VALUES)

        count = invalid_variants.count()
        self.stdout.write(f"Найдено вариантов с невалидным size_value: {count}\n")

        if count == 0:
            self.stdout.write(self.style.SUCCESS("Нет вариантов для очистки."))
            return

        # Очистка size_value
        if not dry_run:
            updated = invalid_variants.update(size_value="")
            self.stdout.write(self.style.SUCCESS(f"\nОчищено вариантов: {updated}"))
            self.stdout.write(
                self.style.WARNING(
                    "\nТеперь запустите повторный импорт:\n"
                    "  python manage.py import_products_from_1c "
                    "--file-type=offers --data-dir=data/import_1c"
                )
            )
        else:
            self.stdout.write(f"\nБудет очищено: {count} вариантов")
            self.stdout.write(self.style.WARNING("\nДля применения изменений запустите без --dry-run"))

"""
Management команда для полной очистки атрибутов и значений атрибутов.

Использование:
    python manage.py clear_attributes
    python manage.py clear_attributes --confirm  # Без интерактивного подтверждения
"""

from typing import Any

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.products.models import Attribute, AttributeValue


class Command(BaseCommand):
    help = "Полная очистка всех атрибутов и значений атрибутов"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--confirm",
            action="store_true",
            help="Выполнить очистку без интерактивного подтверждения",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        """Выполнить очистку атрибутов и значений."""
        confirm = options.get("confirm", False)

        # Подсчет текущих записей
        attr_count = Attribute.objects.count()
        value_count = AttributeValue.objects.count()

        self.stdout.write(self.style.WARNING("\n⚠️  ВНИМАНИЕ: Будут удалены все атрибуты и значения атрибутов!"))
        self.stdout.write(f"   Атрибутов: {attr_count}")
        self.stdout.write(f"   Значений атрибутов: {value_count}\n")

        # Запрос подтверждения, если не указан флаг --confirm
        if not confirm:
            response = input("Продолжить удаление? (yes/no): ")
            if response.lower() not in ["yes", "y", "да"]:
                self.stdout.write(self.style.ERROR("❌ Операция отменена"))
                return

        try:
            with transaction.atomic():
                # Сначала удаляем значения атрибутов (из-за FK)
                deleted_values = AttributeValue.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Удалено значений атрибутов: {deleted_values[0]}"))

                # Затем удаляем атрибуты
                deleted_attrs = Attribute.objects.all().delete()
                self.stdout.write(self.style.SUCCESS(f"✓ Удалено атрибутов: {deleted_attrs[0]}"))

                # Подтверждаем результат
                remaining_attrs = Attribute.objects.count()
                remaining_values = AttributeValue.objects.count()

                if remaining_attrs == 0 and remaining_values == 0:
                    self.stdout.write(self.style.SUCCESS("\n✅ Все атрибуты и значения успешно удалены!"))
                else:
                    self.stdout.write(
                        self.style.ERROR(
                            f"\n⚠️  Остались записи: атрибутов={remaining_attrs}, " f"значений={remaining_values}"
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"\n❌ Ошибка при удалении: {str(e)}"))
            raise

"""
Django management команда для синхронизации клиентов с 1С

Пример использования:
    python manage.py sync_customers_with_1c --export-new
    python manage.py sync_customers_with_1c --import-updates --dry-run
    python manage.py sync_customers_with_1c --full-sync --chunk-size=100
"""

import time
from typing import Dict, List

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from tqdm import tqdm

from apps.users.models import User


class Command(BaseCommand):
    """
    Команда синхронизации клиентов с 1С (двусторонняя синхронизация)
    """

    help = "Синхронизация клиентов с 1С (экспорт новых, импорт обновлений)"

    def add_arguments(self, parser):
        """Добавление аргументов команды"""
        parser.add_argument(
            "--export-new",
            action="store_true",
            help="Экспортировать новых клиентов в 1С",
        )

        parser.add_argument(
            "--import-updates",
            action="store_true",
            help="Импортировать обновления клиентов из 1С",
        )

        parser.add_argument(
            "--full-sync",
            action="store_true",
            help="Полная двусторонняя синхронизация (экспорт + импорт)",
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Тестовый запуск без сохранения данных",
        )

        parser.add_argument(
            "--chunk-size",
            type=int,
            default=50,
            help="Размер батча для обработки клиентов (по умолчанию: 50)",
        )

        parser.add_argument(
            "--force-all",
            action="store_true",
            help="Принудительно синхронизировать всех клиентов",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""

        self.dry_run = options["dry_run"]
        self.chunk_size = options["chunk_size"]
        self.force_all = options["force_all"]
        self.export_new = options["export_new"]
        self.import_updates = options["import_updates"]
        self.full_sync = options["full_sync"]

        # Валидация параметров
        if not any([self.export_new, self.import_updates, self.full_sync]):
            raise CommandError(("Укажите режим синхронизации: --export-new, " "--import-updates или --full-sync"))

        # Заголовок
        self.stdout.write(self.style.SUCCESS("🔄 Запуск синхронизации клиентов с 1С"))

        if self.dry_run:
            self.stdout.write(self.style.WARNING("⚠️  РЕЖИМ DRY-RUN: изменения НЕ будут сохранены"))

        try:
            exported_count = 0
            imported_count = 0

            with transaction.atomic():
                if self.dry_run:
                    savepoint = transaction.savepoint()

                # Экспорт новых клиентов в 1С
                if self.export_new or self.full_sync:
                    exported_count = self._export_new_customers()

                # Импорт обновлений клиентов из 1С
                if self.import_updates or self.full_sync:
                    imported_count = self._import_customer_updates()

                if self.dry_run:
                    transaction.savepoint_rollback(savepoint)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ DRY-RUN завершен: {exported_count} " f"экспортировано, {imported_count} импортировано"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Синхронизация завершена: {exported_count} "
                            f"экспортировано, {imported_count} импортировано"
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"❌ Ошибка синхронизации: {str(e)}"))
            raise

    def _export_new_customers(self) -> int:
        """Экспорт новых клиентов в 1С"""
        self.stdout.write("📤 Экспорт новых клиентов в 1С...")

        # Поиск клиентов, которые нужно экспортировать
        if self.force_all:
            customers_to_export = User.objects.filter(is_active=True)
        else:
            customers_to_export = User.objects.filter(needs_1c_export=True, is_active=True)

        total_count = customers_to_export.count()
        self.stdout.write(f"📊 Найдено клиентов для экспорта: {total_count}")

        if total_count == 0:
            return 0

        # Progress bar
        progress_bar = tqdm(
            customers_to_export.iterator(chunk_size=self.chunk_size),
            total=total_count,
            desc="Экспорт клиентов",
            unit="клиентов",
            ncols=100,
            leave=True,
        )

        exported_count = 0

        for customer in progress_bar:
            try:
                # Имитация экспорта в 1С (заглушка)
                export_result = self._export_customer_to_1c(customer)

                if export_result["success"]:
                    # Обновляем статус клиента после успешного экспорта
                    customer.onec_id = export_result.get("onec_id", customer.onec_id)
                    customer.needs_1c_export = False
                    customer.sync_status = "synced"
                    customer.last_sync_at = timezone.now()
                    customer.sync_error_message = ""
                    customer.save(
                        update_fields=[
                            "onec_id",
                            "needs_1c_export",
                            "sync_status",
                            "last_sync_at",
                            "sync_error_message",
                        ]
                    )
                    exported_count += 1
                else:
                    # Обновляем статус с ошибкой
                    customer.sync_status = "error"
                    customer.sync_error_message = export_result.get("error", "Неизвестная ошибка")
                    customer.save(update_fields=["sync_status", "sync_error_message"])

            except Exception as e:
                self.stdout.write(self.style.ERROR(f"❌ Ошибка экспорта клиента {customer.id}: {e}"))
                customer.sync_status = "error"
                customer.sync_error_message = str(e)
                customer.save(update_fields=["sync_status", "sync_error_message"])

            # Небольшая задержка для демонстрации
            time.sleep(0.01)

        progress_bar.close()
        return exported_count

    def _export_customer_to_1c(self, customer: User) -> Dict:
        """Экспорт одного клиента в 1С (заглушка)"""
        # TODO: Реализовать реальный экспорт через API 1С

        # Имитация успешного экспорта
        import uuid

        return {
            "success": True,
            "onec_id": customer.onec_id or f"1C-EXPORTED-{uuid.uuid4().hex[:8].upper()}",
            "message": "Клиент успешно экспортирован в 1С",
        }

        # Пример обработки ошибки:
        # return {
        #     'success': False,
        #     'error': 'Ошибка соединения с 1С'
        # }

    def _import_customer_updates(self) -> int:
        """Импорт обновлений клиентов из 1С"""
        self.stdout.write("📥 Импорт обновлений клиентов из 1С...")

        # Получение списка обновлений из 1С (заглушка)
        customer_updates = self._fetch_customer_updates_from_1c()

        total_count = len(customer_updates)
        self.stdout.write(f"📊 Найдено обновлений от 1С: {total_count}")

        if total_count == 0:
            return 0

        # Progress bar
        progress_bar = tqdm(
            customer_updates,
            desc="Импорт обновлений",
            unit="обновлений",
            ncols=100,
            leave=True,
        )

        imported_count = 0

        for update_data in progress_bar:
            try:
                # Импорт обновления клиента
                if self._import_customer_update(update_data):
                    imported_count += 1

            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"❌ Ошибка импорта обновления " f'{update_data.get("onec_id", "UNKNOWN")}: {str(e)}'
                    )
                )

            # Небольшая задержка для демонстрации
            time.sleep(0.01)

        progress_bar.close()
        return imported_count

    def _fetch_customer_updates_from_1c(self) -> List[Dict]:
        """Получение списка обновлений клиентов из 1С (заглушка)"""
        # TODO: Реализовать реальный запрос к API 1С

        # Имитация данных от 1С
        mock_updates = []

        # Находим клиентов с onec_id для имитации обновлений
        synced_customers = User.objects.filter(onec_id__isnull=False, sync_status="synced")[
            :5
        ]  # Берем первые 5 для примера

        for customer in synced_customers:
            mock_updates.append(
                {
                    "onec_id": customer.onec_id,
                    "email": str(customer.email or ""),
                    "first_name": customer.first_name + " (обновлено)",
                    "phone_number": customer.phone,
                    "company_name": (customer.company_name + " (обновлено)" if customer.company_name else ""),
                    "is_active": customer.is_active,
                    "last_updated_in_1c": timezone.now().isoformat(),
                }
            )

        return mock_updates

    def _import_customer_update(self, update_data: Dict) -> bool:
        """Импорт обновления одного клиента"""
        onec_id = update_data.get("onec_id")
        if not onec_id:
            return False

        try:
            customer = User.objects.get(onec_id=onec_id)

            # Обновляем только измененные поля
            updated_fields = []

            if update_data.get("first_name") != customer.first_name:
                customer.first_name = update_data.get("first_name", customer.first_name)
                updated_fields.append("first_name")

            if update_data.get("phone_number") != customer.phone:
                customer.phone = update_data.get("phone_number", customer.phone)
                updated_fields.append("phone")

            if update_data.get("company_name") != customer.company_name:
                customer.company_name = update_data.get("company_name", customer.company_name)
                updated_fields.append("company_name")

            if update_data.get("is_active") != customer.is_active:
                customer.is_active = update_data.get("is_active", customer.is_active)
                updated_fields.append("is_active")

            if updated_fields:
                # Обновляем метаданные синхронизации
                customer.last_sync_at = timezone.now()
                customer.sync_status = "synced"
                customer.sync_error_message = ""
                updated_fields.extend(["last_sync_at", "sync_status", "sync_error_message"])

                customer.save(update_fields=updated_fields)

                if getattr(self, "verbosity", 1) >= 2:
                    self.stdout.write(f"✅ Обновлен клиент {onec_id}: " f'{", ".join(updated_fields)}')

                return True

            return False  # Нет изменений

        except User.DoesNotExist:
            self.stdout.write(self.style.WARNING(f"⚠️  Клиент с onec_id {onec_id} не найден в базе"))
            return False

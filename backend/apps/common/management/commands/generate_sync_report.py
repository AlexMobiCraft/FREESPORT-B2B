"""
Management команда для генерации и отправки отчетов по синхронизации
"""

import os
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.common.services import SyncReportGenerator


class Command(BaseCommand):
    """Генерирует и отправляет отчеты по синхронизации клиентов"""

    help = "Генерирует и отправляет отчеты по синхронизации клиентов"

    def add_arguments(self, parser):
        """Добавляет аргументы команды"""
        parser.add_argument(
            "--type",
            type=str,
            choices=["daily", "weekly"],
            default="daily",
            help="Тип отчета: daily (ежедневный) или weekly (еженедельный)",
        )

        parser.add_argument(
            "--date",
            type=str,
            help="Дата для отчета в формате YYYY-MM-DD (по умолчанию - сегодня)",
        )

        parser.add_argument(
            "--recipients",
            type=str,
            help="Email получателей через запятую (по умолчанию из настроек)",
        )

        parser.add_argument(
            "--no-send",
            action="store_true",
            help="Только сгенерировать отчет, не отправлять email",
        )

    def handle(self, *args, **options):
        """Основная логика команды"""
        report_type = options["type"]
        no_send = options["no_send"]

        # Определяем получателей
        recipients = self._get_recipients(options.get("recipients"))

        # Определяем дату
        target_date = self._parse_date(options.get("date"))

        # Создаем генератор отчетов
        generator = SyncReportGenerator()

        try:
            if report_type == "daily":
                self._generate_daily_report(generator, target_date, recipients, no_send)
            elif report_type == "weekly":
                self._generate_weekly_report(generator, target_date, recipients, no_send)
            else:
                raise CommandError(f"Неизвестный тип отчета: {report_type}")

        except Exception as e:
            raise CommandError(f"Ошибка при генерации отчета: {str(e)}")

    def _get_recipients(self, recipients_arg):
        """Получает список email получателей"""
        if recipients_arg:
            return [email.strip() for email in recipients_arg.split(",")]

        # Получаем из настроек
        env_recipients = os.getenv("SYNC_REPORT_EMAILS", "")
        if env_recipients:
            return [email.strip() for email in env_recipients.split(",")]

        # Используем email администраторов из settings
        if hasattr(settings, "ADMINS"):
            return [email for name, email in settings.ADMINS]

        raise CommandError(
            "Не указаны получатели. Используйте --recipients или " "установите SYNC_REPORT_EMAILS в .env"
        )

    def _parse_date(self, date_str):
        """Парсит строку даты"""
        if not date_str:
            return None

        try:
            return datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            raise CommandError(f"Неверный формат даты: {date_str}. " f"Используйте формат YYYY-MM-DD")

    def _generate_daily_report(self, generator, target_date, recipients, no_send):
        """Генерирует ежедневный отчет"""
        self.stdout.write("Генерация ежедневного отчета...")

        # Генерируем отчет
        report_data = generator.generate_daily_summary(target_date)

        # Выводим в консоль
        self._display_daily_report(report_data)

        # Отправляем email если требуется
        if not no_send:
            self.stdout.write("Отправка отчета по email...")
            success = generator.send_daily_report(recipients, target_date)

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Отчет успешно отправлен {len(recipients)} получателям"))
            else:
                self.stdout.write(self.style.ERROR("✗ Ошибка при отправке отчета"))
        else:
            self.stdout.write(self.style.WARNING("Отчет не отправлен (--no-send)"))

    def _generate_weekly_report(self, generator, start_date, recipients, no_send):
        """Генерирует еженедельный отчет"""
        self.stdout.write("Генерация еженедельного отчета...")

        # Генерируем отчет
        report_data = generator.generate_weekly_error_analysis(start_date)

        # Выводим в консоль
        self._display_weekly_report(report_data)

        # Отправляем email если требуется
        if not no_send:
            self.stdout.write("Отправка отчета по email...")
            success = generator.send_weekly_error_report(recipients, start_date)

            if success:
                self.stdout.write(self.style.SUCCESS(f"✓ Отчет успешно отправлен {len(recipients)} получателям"))
            else:
                self.stdout.write(self.style.ERROR("✗ Ошибка при отправке отчета"))
        else:
            self.stdout.write(self.style.WARNING("Отчет не отправлен (--no-send)"))

    def _display_daily_report(self, report):
        """Отображает ежедневный отчет в консоли"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"ЕЖЕДНЕВНЫЙ ОТЧЕТ - {report['date']}")
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nВсего операций: {report['total_operations']}")
        self.stdout.write(f"Успешных: {report['success_count']} " f"({report['success_rate']}%)")
        self.stdout.write(f"Средняя длительность: {report['avg_duration_ms']} мс")

        if report["by_type"]:
            self.stdout.write("\nОперации по типам:")
            for item in report["by_type"]:
                self.stdout.write(f"  - {item['operation_type']}: {item['count']}")

        if report["by_status"]:
            self.stdout.write("\nОперации по статусам:")
            for item in report["by_status"]:
                self.stdout.write(f"  - {item['status']}: {item['count']}")

        if report["top_errors"]:
            self.stdout.write("\nТоп-5 ошибок:")
            for error in report["top_errors"][:5]:
                msg = error["error_message"][:60]
                self.stdout.write(f"  - {msg}... ({error['count']})")

        self.stdout.write("=" * 60 + "\n")

    def _display_weekly_report(self, report):
        """Отображает еженедельный отчет в консоли"""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write(f"ЕЖЕНЕДЕЛЬНЫЙ ОТЧЕТ - {report['period']}")
        self.stdout.write("=" * 60)
        self.stdout.write(f"\nВсего операций: {report['total_operations']}")
        self.stdout.write(f"Ошибок: {report['total_errors']}")
        self.stdout.write(f"Процент ошибок: {report['error_rate']}%")
        self.stdout.write(f"Затронуто клиентов: {report['affected_customers']}")

        if report["errors_by_type"]:
            self.stdout.write("\nОшибки по типам операций:")
            for item in report["errors_by_type"]:
                self.stdout.write(f"  - {item['operation_type']}: {item['count']}")

        if report["common_errors"]:
            self.stdout.write("\nЧастые ошибки (топ-5):")
            for error in report["common_errors"][:5]:
                msg = error["message"][:60]
                types = ", ".join(error["operation_types"][:3])
                self.stdout.write(f"  - {msg}... ({error['count']} раз)")
                self.stdout.write(f"    Типы: {types}")

        self.stdout.write("=" * 60 + "\n")

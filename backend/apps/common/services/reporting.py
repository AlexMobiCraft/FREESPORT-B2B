"""
Сервис генерации отчетов по синхронизации клиентов
"""

import logging
from datetime import date, timedelta
from typing import Any

from django.core.mail import send_mail
from django.db.models import Avg, Count, Q
from django.template.loader import render_to_string
from django.utils import timezone

from apps.common.models import CustomerSyncLog

logger = logging.getLogger(__name__)


class SyncReportGenerator:
    """Генератор отчетов по синхронизации клиентов"""

    def generate_daily_summary(self, target_date: date | None = None) -> dict[str, Any]:
        """
        Генерирует ежедневный сводный отчет по синхронизации.

        Args:
            target_date: Дата для отчета (по умолчанию - сегодня)

        Returns:
            Словарь с данными отчета
        """
        target_date = target_date or timezone.now().date()
        logs = CustomerSyncLog.objects.filter(created_at__date=target_date)

        # Основная статистика
        total_operations = logs.count()

        # Статистика по типам операций
        by_type = list(logs.values("operation_type").annotate(count=Count("id")).order_by("-count"))

        # Статистика по статусам
        by_status = list(logs.values("status").annotate(count=Count("id")).order_by("-count"))

        # Средняя длительность операций
        avg_duration = logs.aggregate(avg_duration=Avg("duration_ms"))["avg_duration"]

        # Топ-10 ошибок
        top_errors = list(
            logs.filter(Q(status=CustomerSyncLog.StatusType.ERROR) | Q(status=CustomerSyncLog.StatusType.FAILED))
            .values("error_message")
            .annotate(count=Count("id"))
            .order_by("-count")[:10]
        )

        # Успешность операций
        success_count = logs.filter(status=CustomerSyncLog.StatusType.SUCCESS).count()
        error_count = logs.filter(
            status__in=[
                CustomerSyncLog.StatusType.ERROR,
                CustomerSyncLog.StatusType.FAILED,
            ]
        ).count()
        success_rate = (success_count / total_operations * 100) if total_operations > 0 else 0

        return {
            "date": target_date,
            "total_operations": total_operations,
            "by_type": by_type,
            "by_status": by_status,
            "avg_duration_ms": round(avg_duration, 2) if avg_duration else 0,
            "top_errors": top_errors,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": round(success_rate, 2),
        }

    def generate_weekly_error_analysis(self, start_date: date | None = None) -> dict[str, Any]:
        """
        Генерирует еженедельный анализ ошибок синхронизации.

        Args:
            start_date: Начальная дата периода (по умолчанию - неделя назад)

        Returns:
            Словарь с данными анализа ошибок
        """
        if start_date is None:
            start_date = (timezone.now() - timedelta(days=7)).date()

        end_date = start_date + timedelta(days=7)

        # Фильтруем только ошибки
        error_logs = CustomerSyncLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lt=end_date,
        ).filter(Q(status=CustomerSyncLog.StatusType.ERROR) | Q(status=CustomerSyncLog.StatusType.FAILED))

        total_errors = error_logs.count()

        # Общее количество операций за период
        all_logs = CustomerSyncLog.objects.filter(
            created_at__date__gte=start_date,
            created_at__date__lt=end_date,
        )
        total_operations = all_logs.count()

        # Процент ошибок
        error_rate = (total_errors / total_operations * 100) if total_operations > 0 else 0

        # Ошибки по типам операций
        errors_by_type = list(error_logs.values("operation_type").annotate(count=Count("id")).order_by("-count"))

        # Частые ошибки
        common_errors = self._analyze_common_errors(error_logs)

        # Затронутые клиенты
        affected_customers = error_logs.filter(customer__isnull=False).values("customer").distinct().count()

        return {
            "period": f"{start_date} - {end_date}",
            "start_date": start_date,
            "end_date": end_date,
            "total_errors": total_errors,
            "total_operations": total_operations,
            "error_rate": round(error_rate, 2),
            "errors_by_type": errors_by_type,
            "common_errors": common_errors,
            "affected_customers": affected_customers,
        }

    def _analyze_common_errors(self, error_logs: Any) -> list[dict[str, Any]]:
        """
        Анализирует частые ошибки и группирует похожие.

        Args:
            error_logs: QuerySet с ошибочными логами

        Returns:
            Список словарей с информацией об ошибках
        """
        # Группируем по тексту ошибки
        error_groups: dict[str, dict[str, Any]] = {}
        for log in error_logs:
            error_text = log.error_message[:100] if log.error_message else "Unknown"

            if error_text not in error_groups:
                error_groups[error_text] = {
                    "message": error_text,
                    "count": 0,
                    "operation_types": set(),
                }

            error_groups[error_text]["count"] += 1
            error_groups[error_text]["operation_types"].add(log.get_operation_type_display())

        # Конвертируем sets в lists для JSON
        result = []
        for error_data in error_groups.values():
            result.append(
                {
                    "message": error_data["message"],
                    "count": error_data["count"],
                    "operation_types": list(error_data["operation_types"]),
                }
            )

        # Сортируем по частоте
        result.sort(key=lambda x: x["count"], reverse=True)
        return result[:10]  # Топ-10

    def send_daily_report(self, recipients: list[str], target_date: date | None = None) -> bool:
        """
        Отправляет ежедневный отчет по email.

        Args:
            recipients: Список email адресов получателей
            target_date: Дата для отчета

        Returns:
            True если отчет успешно отправлен
        """
        try:
            report_data = self.generate_daily_summary(target_date)
            target_date = report_data["date"]

            # Формируем текст email
            subject = f"Ежедневный отчет синхронизации клиентов - {target_date}"

            # Формируем HTML версию (если есть шаблон)
            try:
                html_message = render_to_string("common/emails/daily_sync_report.html", {"report": report_data})
            except Exception:
                html_message = None

            # Формируем текстовую версию
            text_message = self._format_daily_report_text(report_data)

            # Отправляем email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=None,  # Использует DEFAULT_FROM_EMAIL из settings
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(
                "Ежедневный отчет отправлен %s получателям за %s",
                len(recipients),
                target_date,
            )
            return True

        except Exception as e:
            logger.error("Ошибка при отправке ежедневного отчета: %s", str(e), exc_info=True)
            return False

    def send_weekly_error_report(self, recipients: list[str], start_date: date | None = None) -> bool:
        """
        Отправляет еженедельный отчет по ошибкам.

        Args:
            recipients: Список email адресов получателей
            start_date: Начальная дата периода

        Returns:
            True если отчет успешно отправлен
        """
        try:
            report_data = self.generate_weekly_error_analysis(start_date)

            # Формируем текст email
            subject = f"Еженедельный анализ ошибок синхронизации - {report_data['period']}"

            # Формируем HTML версию (если есть шаблон)
            try:
                html_message = render_to_string("common/emails/weekly_error_report.html", {"report": report_data})
            except Exception:
                html_message = None

            # Формируем текстовую версию
            text_message = self._format_weekly_report_text(report_data)

            # Отправляем email
            send_mail(
                subject=subject,
                message=text_message,
                from_email=None,
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False,
            )

            logger.info(
                "Еженедельный отчет отправлен %s получателям за период %s",
                len(recipients),
                report_data["period"],
            )
            return True

        except Exception as e:
            logger.error("Ошибка при отправке еженедельного отчета: %s", str(e), exc_info=True)
            return False

    def _format_daily_report_text(self, report: dict[str, Any]) -> str:
        """Форматирует ежедневный отчет в текстовом виде"""
        lines = [
            "Ежедневный отчет синхронизации клиентов",
            f"Дата: {report['date']}",
            "=" * 50,
            "",
            f"Всего операций: {report['total_operations']}",
            f"Успешных: {report['success_count']} ({report['success_rate']}%)",
            f"Средняя длительность: {report['avg_duration_ms']} мс",
            "",
            "Операции по типам:",
        ]

        for item in report["by_type"]:
            lines.append(f"  - {item['operation_type']}: {item['count']}")

        lines.extend(
            [
                "",
                "Операции по статусам:",
            ]
        )

        for item in report["by_status"]:
            lines.append(f"  - {item['status']}: {item['count']}")

        if report["top_errors"]:
            lines.extend(
                [
                    "",
                    "Топ-10 ошибок:",
                ]
            )
            for error in report["top_errors"]:
                lines.append(f"  - {error['error_message'][:80]}... ({error['count']})")

        return "\n".join(lines)

    def _format_weekly_report_text(self, report: dict[str, Any]) -> str:
        """Форматирует еженедельный отчет в текстовом виде"""
        lines = [
            "Еженедельный анализ ошибок синхронизации",
            f"Период: {report['period']}",
            "=" * 50,
            "",
            f"Всего операций: {report['total_operations']}",
            f"Ошибок: {report['total_errors']}",
            f"Процент ошибок: {report['error_rate']}%",
            f"Затронуто клиентов: {report['affected_customers']}",
            "",
            "Ошибки по типам операций:",
        ]

        for item in report["errors_by_type"]:
            lines.append(f"  - {item['operation_type']}: {item['count']}")

        if report["common_errors"]:
            lines.extend(
                [
                    "",
                    "Частые ошибки:",
                ]
            )
            for error in report["common_errors"]:
                lines.append(f"  - {error['message'][:80]}... ({error['count']} раз)")
                lines.append(f"    Типы операций: {', '.join(error['operation_types'])}")

        return "\n".join(lines)

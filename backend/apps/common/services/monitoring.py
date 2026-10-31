"""
Мониторинг и метрики для синхронизации клиентов
Включает поддержку Prometheus и webhook алертов
"""

import json
import logging
import os
from datetime import timedelta
from typing import Any

import requests
from django.conf import settings
from django.db.models import Avg, Count
from django.utils import timezone

from apps.common.models import CustomerSyncLog

logger = logging.getLogger(__name__)


class PrometheusMetrics:
    """
    Сбор метрик для Prometheus.
    В production используется библиотека prometheus_client.
    """

    @staticmethod
    def is_enabled() -> bool:
        """Проверяет включены ли метрики Prometheus"""
        enabled_env = os.getenv("PROMETHEUS_METRICS_ENABLED", "false")
        return enabled_env.lower() in ("true", "1", "yes")

    @classmethod
    def get_sync_metrics(cls) -> dict[str, Any]:
        """
        Собирает метрики синхронизации для Prometheus.

        Returns:
            Словарь с метриками
        """
        if not cls.is_enabled():
            return {}

        # Метрики за последние 24 часа
        since = timezone.now() - timedelta(hours=24)
        recent_logs = CustomerSyncLog.objects.filter(created_at__gte=since)

        # Общее количество операций
        total_operations = recent_logs.count()

        # Количество по типам операций
        operations_by_type = {}
        for item in recent_logs.values("operation_type").annotate(count=Count("id")):
            operations_by_type[item["operation_type"]] = item["count"]

        # Количество ошибок
        error_count = recent_logs.filter(
            status__in=[
                CustomerSyncLog.StatusType.ERROR,
                CustomerSyncLog.StatusType.FAILED,
            ]
        ).count()

        # Средняя длительность операций
        avg_duration = recent_logs.aggregate(avg=Avg("duration_ms"))["avg"] or 0

        # Количество успешных операций
        success_count = recent_logs.filter(status=CustomerSyncLog.StatusType.SUCCESS).count()

        return {
            "sync_operations_total": total_operations,
            "sync_operations_by_type": operations_by_type,
            "sync_errors_total": error_count,
            "sync_success_total": success_count,
            "sync_duration_avg_ms": round(avg_duration, 2),
            "sync_success_rate": (round(success_count / total_operations * 100, 2) if total_operations > 0 else 0),
            "timestamp": timezone.now().isoformat(),
        }

    @classmethod
    def export_metrics_text(cls) -> str:
        """
        Экспортирует метрики в текстовом формате Prometheus.

        Returns:
            Строка с метриками в формате Prometheus
        """
        metrics = cls.get_sync_metrics()

        if not metrics:
            return "# Prometheus metrics disabled\n"

        lines = [
            "# HELP sync_operations_total Total number of sync operations",
            "# TYPE sync_operations_total counter",
            f"sync_operations_total {metrics['sync_operations_total']}",
            "",
            "# HELP sync_errors_total Total number of sync errors",
            "# TYPE sync_errors_total counter",
            f"sync_errors_total {metrics['sync_errors_total']}",
            "",
            "# HELP sync_success_total Total number of successful sync operations",
            "# TYPE sync_success_total counter",
            f"sync_success_total {metrics['sync_success_total']}",
            "",
            "# HELP sync_duration_avg_ms Average duration of sync operations in milliseconds",  # noqa
            "# TYPE sync_duration_avg_ms gauge",
            f"sync_duration_avg_ms {metrics['sync_duration_avg_ms']}",
            "",
            "# HELP sync_success_rate Success rate of sync operations",
            "# TYPE sync_success_rate gauge",
            f"sync_success_rate {metrics['sync_success_rate']}",
            "",
        ]

        # Добавляем метрики по типам операций
        for op_type, count in metrics["sync_operations_by_type"].items():
            lines.append(f'sync_operations_by_type{{type="{op_type}"}} {count}')

        return "\n".join(lines) + "\n"


class WebhookAlerts:
    """Отправка алертов через webhooks"""

    @staticmethod
    def get_webhook_url() -> str | None:
        """Получает URL webhook из настроек"""
        return os.getenv("WEBHOOK_ALERT_URL")

    @classmethod
    def is_enabled(cls) -> bool:
        """Проверяет настроены ли webhooks"""
        return cls.get_webhook_url() is not None

    @classmethod
    def send_critical_alert(
        cls,
        title: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """
        Отправляет критический алерт через webhook.

        Args:
            title: Заголовок алерта
            message: Сообщение алерта
            details: Дополнительные детали

        Returns:
            True если алерт успешно отправлен
        """
        webhook_url = cls.get_webhook_url()

        if not webhook_url:
            logger.warning("Webhook URL не настроен, алерт не отправлен")
            return False

        try:
            payload = {
                "alert_type": "critical",
                "title": title,
                "message": message,
                "details": details or {},
                "timestamp": timezone.now().isoformat(),
                "source": "freesport_sync_system",
            }

            response = requests.post(
                webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )

            response.raise_for_status()

            logger.info("Критический алерт отправлен: %s", title)
            return True

        except requests.exceptions.RequestException as e:
            logger.error("Ошибка при отправке webhook алерта: %s", str(e), exc_info=True)
            return False

    @classmethod
    def send_sync_failure_alert(
        cls,
        operation_type: str,
        customer_email: str,
        error_message: str,
    ) -> bool:
        """
        Отправляет алерт о критической ошибке синхронизации.

        Args:
            operation_type: Тип операции
            customer_email: Email клиента
            error_message: Сообщение об ошибке

        Returns:
            True если алерт успешно отправлен
        """
        title = f"Критическая ошибка синхронизации: {operation_type}"
        message = f"Ошибка при синхронизации клиента {customer_email}"

        details = {
            "operation_type": operation_type,
            "customer_email": customer_email,
            "error_message": error_message,
        }

        return cls.send_critical_alert(title, message, details)

    @classmethod
    def send_batch_failure_alert(
        cls,
        total_errors: int,
        error_rate: float,
    ) -> bool:
        """
        Отправляет алерт о высоком проценте ошибок.

        Args:
            total_errors: Количество ошибок
            error_rate: Процент ошибок

        Returns:
            True если алерт успешно отправлен
        """
        title = "Высокий процент ошибок синхронизации"
        message = f"Обнаружено {total_errors} ошибок " f"({error_rate:.1f}% от всех операций)"

        details = {
            "total_errors": total_errors,
            "error_rate": error_rate,
            "threshold": 10.0,  # Порог 10%
        }

        return cls.send_critical_alert(title, message, details)


class StructuredLogger:
    """Структурированное логирование в JSON формате для ELK"""

    @staticmethod
    def is_json_logging_enabled() -> bool:
        """Проверяет включено ли JSON логирование"""
        return os.getenv("SYNC_LOG_FORMAT", "").lower() == "json"

    @classmethod
    def log_sync_operation(
        cls,
        operation_type: str,
        status: str,
        customer_email: str = "",
        onec_id: str = "",
        duration_ms: int | None = None,
        error_message: str = "",
        **extra_fields: Any,
    ) -> None:
        """
        Логирует операцию синхронизации в структурированном формате.

        Args:
            operation_type: Тип операции
            status: Статус операции
            customer_email: Email клиента
            onec_id: ID в 1С
            duration_ms: Длительность операции
            error_message: Сообщение об ошибке
            **extra_fields: Дополнительные поля
        """
        if not cls.is_json_logging_enabled():
            # Обычное логирование
            logger.info(
                "Sync operation: type=%s, status=%s, customer=%s, duration=%s",
                operation_type,
                status,
                customer_email,
                duration_ms,
            )
            return

        # JSON логирование
        log_data = {
            "timestamp": timezone.now().isoformat(),
            "event_type": "sync_operation",
            "operation_type": operation_type,
            "status": status,
            "customer_email": customer_email,
            "onec_id": onec_id,
            "duration_ms": duration_ms,
            "error_message": error_message,
            **extra_fields,
        }

        # Используем logger с JSON форматом
        if status in ("error", "failed"):
            logger.error(json.dumps(log_data))
        elif status == "warning":
            logger.warning(json.dumps(log_data))
        else:
            logger.info(json.dumps(log_data))

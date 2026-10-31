"""
Система алертинга для мониторинга интеграции с 1С.
Автоматически отправляет уведомления при критических событиях.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any

from django.core.cache import cache
from django.utils import timezone

from apps.common.services.monitoring import WebhookAlerts

from .customer_sync_monitor import CustomerSyncMonitor

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class AlertManager:
    """
    Менеджер алертов для системы мониторинга.
    Проверяет пороговые значения метрик и отправляет уведомления.
    """

    # Пороговые значения для алертов (можно переопределить через ENV)
    ERROR_RATE_THRESHOLD = float(os.getenv("ALERT_ERROR_RATE_THRESHOLD", "10.0"))  # %
    RESPONSE_TIME_P95_THRESHOLD = int(os.getenv("ALERT_RESPONSE_TIME_P95_THRESHOLD", "2000"))  # мс
    FAILED_OPERATIONS_THRESHOLD = int(os.getenv("ALERT_FAILED_OPERATIONS_THRESHOLD", "50"))

    # Время между повторными алертами (дедупликация)
    ALERT_COOLDOWN_MINUTES = int(os.getenv("ALERT_COOLDOWN_MINUTES", "15"))

    def __init__(self) -> None:
        """Инициализация AlertManager."""
        self.monitor = CustomerSyncMonitor()
        self.webhook_alerts = WebhookAlerts()

    def check_all_alerts(self) -> dict[str, Any]:
        """
        Проверяет все условия для алертов и отправляет уведомления.

        Returns:
            Словарь с результатами проверки алертов
        """
        now = timezone.now()
        start_time = now - timedelta(hours=1)  # Проверяем последний час

        alerts_sent: list[str] = []
        alerts_suppressed: list[str] = []

        # 1. Проверка high error rate
        error_rate_alert = self._check_high_error_rate(start_time, now)
        if error_rate_alert:
            if self._should_send_alert("high_error_rate"):
                self._send_alert(**error_rate_alert)
                alerts_sent.append("high_error_rate")
            else:
                alerts_suppressed.append("high_error_rate")

        # 2. Проверка slow response times
        slow_response_alert = self._check_slow_response_times(start_time, now)
        if slow_response_alert:
            if self._should_send_alert("slow_response"):
                self._send_alert(**slow_response_alert)
                alerts_sent.append("slow_response")
            else:
                alerts_suppressed.append("slow_response")

        # 3. Проверка system health
        health_alert = self._check_system_health()
        if health_alert:
            if self._should_send_alert("system_unhealthy"):
                self._send_alert(**health_alert)
                alerts_sent.append("system_unhealthy")
            else:
                alerts_suppressed.append("system_unhealthy")

        # 4. Проверка failed operations spike
        failed_ops_alert = self._check_failed_operations_spike(start_time, now)
        if failed_ops_alert:
            if self._should_send_alert("failed_operations_spike"):
                self._send_alert(**failed_ops_alert)
                alerts_sent.append("failed_operations_spike")
            else:
                alerts_suppressed.append("failed_operations_spike")

        logger.info(
            "Alert check completed: %d sent, %d suppressed",
            len(alerts_sent),
            len(alerts_suppressed),
        )

        return {
            "timestamp": now.isoformat(),
            "alerts_sent": alerts_sent,
            "alerts_suppressed": alerts_suppressed,
        }

    def _check_high_error_rate(self, start_date: datetime, end_date: datetime) -> dict[str, Any] | None:
        """
        Проверяет превышение порога error rate.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь с данными алерта или None
        """
        metrics = self.monitor.get_operation_metrics(start_date, end_date)

        error_rate = metrics.get("error_rate", 0.0)

        if error_rate > self.ERROR_RATE_THRESHOLD:
            message_parts = [
                "Error rate превысил пороговое значение",
                f"{self.ERROR_RATE_THRESHOLD}%.",
                f"Текущее значение: {error_rate:.1f}%.",
                "Детали:",
                f"{metrics['error_count']} ошибок из",
                f"{metrics['total_operations']} операций.",
            ]

            return {
                "title": f"Высокий Error Rate: {error_rate:.1f}%",
                "message": " ".join(message_parts),
                "details": {
                    "error_rate": error_rate,
                    "threshold": self.ERROR_RATE_THRESHOLD,
                    "error_count": metrics["error_count"],
                    "total_operations": metrics["total_operations"],
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                },
            }

        return None

    def _check_slow_response_times(self, start_date: datetime, end_date: datetime) -> dict[str, Any] | None:
        """
        Проверяет превышение порога времени ответа (p95).

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь с данными алерта или None
        """
        metrics = self.monitor.get_operation_metrics(start_date, end_date)

        p95_duration = metrics.get("duration_p95_ms", 0.0)

        if p95_duration > self.RESPONSE_TIME_P95_THRESHOLD:
            return {
                "title": f"Медленный Response Time: P95 = {p95_duration:.0f}мс",
                "message": (
                    "P95 времени выполнения операций превысило "
                    f"{self.RESPONSE_TIME_P95_THRESHOLD}мс. "
                    f"Текущее значение: {p95_duration:.0f}мс"
                ),
                "details": {
                    "p95_duration_ms": p95_duration,
                    "threshold_ms": self.RESPONSE_TIME_P95_THRESHOLD,
                    "avg_duration_ms": metrics.get("duration_avg_ms", 0.0),
                    "max_duration_ms": metrics.get("duration_max_ms", 0.0),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                },
            }

        return None

    def _check_system_health(self) -> dict[str, Any] | None:
        """
        Проверяет статус здоровья системы.

        Returns:
            Словарь с данными алерта или None
        """
        health = self.monitor.get_system_health()

        if not health["is_healthy"]:
            critical_issues = health.get("critical_issues", [])

            issue_descriptions = []
            for issue in critical_issues:
                issue_descriptions.append(f"- {issue['component']}: {issue['message']}")

            return {
                "title": "Проблемы со здоровьем системы",
                "message": (
                    f"Обнаружено {len(critical_issues)} критических проблем:\n" + "\n".join(issue_descriptions)
                ),
                "details": {
                    "critical_issues": critical_issues,
                    "components": health.get("components", {}),
                },
            }

        return None

    def _check_failed_operations_spike(self, start_date: datetime, end_date: datetime) -> dict[str, Any] | None:
        """
        Проверяет всплеск количества неудачных операций.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь с данными алерта или None
        """
        metrics = self.monitor.get_operation_metrics(start_date, end_date)

        error_count = metrics.get("error_count", 0)

        if error_count > self.FAILED_OPERATIONS_THRESHOLD:
            return {
                "title": f"Всплеск неудачных операций: {error_count}",
                "message": (
                    f"Количество неудачных операций ({error_count}) "
                    f"превысило пороговое значение {self.FAILED_OPERATIONS_THRESHOLD} "
                    f"за последний час"
                ),
                "details": {
                    "error_count": error_count,
                    "threshold": self.FAILED_OPERATIONS_THRESHOLD,
                    "total_operations": metrics.get("total_operations", 0),
                    "error_rate": metrics.get("error_rate", 0.0),
                    "period_start": start_date.isoformat(),
                    "period_end": end_date.isoformat(),
                },
            }

        return None

    def _should_send_alert(self, alert_key: str) -> bool:
        """
        Проверяет, нужно ли отправлять алерт (дедупликация).

        Args:
            alert_key: Уникальный ключ алерта

        Returns:
            True если алерт нужно отправить
        """
        cache_key = f"alert_sent:{alert_key}"
        last_sent = cache.get(cache_key)

        if last_sent is not None:
            # Алерт уже отправлялся недавно
            logger.debug("Alert %s suppressed (cooldown period)", alert_key)
            return False

        # Устанавливаем флаг отправки на период cooldown
        cache.set(
            cache_key,
            timezone.now().isoformat(),
            timeout=self.ALERT_COOLDOWN_MINUTES * 60,
        )

        return True

    def _send_alert(self, title: str, message: str, details: dict[str, Any]) -> None:
        """
        Отправляет алерт через webhook.

        Args:
            title: Заголовок алерта
            message: Текст сообщения
            details: Детали алерта
        """
        success = self.webhook_alerts.send_critical_alert(title, message, details)

        if success:
            logger.warning("Critical alert sent: %s", title)
        else:
            logger.error("Failed to send critical alert: %s", title)


class RealTimeAlertMonitor:
    """
    Мониторинг метрик в реальном времени для немедленного реагирования.
    Используется для проверки метрик с высокой частотой (каждую минуту).
    """

    # Пороги для real-time мониторинга
    REALTIME_ERROR_RATE_THRESHOLD = float(os.getenv("REALTIME_ERROR_RATE_THRESHOLD", "20.0"))  # %
    REALTIME_PENDING_THRESHOLD = int(os.getenv("REALTIME_PENDING_THRESHOLD", "100"))  # операций

    def __init__(self) -> None:
        """Инициализация RealTimeAlertMonitor."""
        self.monitor = CustomerSyncMonitor()
        self.webhook_alerts = WebhookAlerts()

    def check_realtime_metrics(self) -> dict[str, Any]:
        """
        Проверяет метрики в реальном времени (последние 5 минут).

        Returns:
            Словарь с результатами проверки
        """
        metrics = self.monitor.get_real_time_metrics()

        alerts_sent: list[str] = []

        # Проверка текущего error rate
        current_error_rate = metrics.get("current_error_rate", 0.0)
        if current_error_rate > self.REALTIME_ERROR_RATE_THRESHOLD:
            self.webhook_alerts.send_critical_alert(
                title=f"СРОЧНО: Error Rate {current_error_rate:.1f}%",
                message=(
                    f"Текущий error rate ({current_error_rate:.1f}%) "
                    f"превысил критический порог {self.REALTIME_ERROR_RATE_THRESHOLD}% "
                    f"за последние 5 минут"
                ),
                details={
                    "current_error_rate": current_error_rate,
                    "threshold": self.REALTIME_ERROR_RATE_THRESHOLD,
                    "errors_last_5min": metrics.get("errors_last_5min", 0),
                    "operations_last_5min": metrics.get("operations_last_5min", 0),
                },
            )
            alerts_sent.append("realtime_high_error_rate")

        # Проверка количества pending операций
        pending_operations = metrics.get("pending_operations", 0)
        if pending_operations > self.REALTIME_PENDING_THRESHOLD:
            self.webhook_alerts.send_critical_alert(
                title=f"Большая очередь: {pending_operations} операций",
                message=(
                    f"Количество операций в процессе ({pending_operations}) "
                    f"превысило порог {self.REALTIME_PENDING_THRESHOLD}. "
                    f"Возможна перегрузка системы."
                ),
                details={
                    "pending_operations": pending_operations,
                    "threshold": self.REALTIME_PENDING_THRESHOLD,
                    "throughput_per_minute": metrics.get("throughput_per_minute", 0),
                },
            )
            alerts_sent.append("high_pending_operations")
        return {
            "timestamp": timezone.now().isoformat(),
            "alerts_sent": alerts_sent,
        }

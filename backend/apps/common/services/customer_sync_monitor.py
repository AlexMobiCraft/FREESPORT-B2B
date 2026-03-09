"""
Мониторинг системы синхронизации клиентов с 1С.
Предоставляет метрики операций, бизнес-метрики и health checks.
"""

from __future__ import annotations

import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, cast

import requests
from django.core.cache import cache
from django.db import connection
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDate, TruncHour
from django.utils import timezone
from requests.exceptions import RequestException

if TYPE_CHECKING:
    from django.db.models import QuerySet

from apps.common.models import CustomerSyncLog

logger = logging.getLogger(__name__)


class CustomerSyncMonitor:
    """
    Мониторинг операций синхронизации клиентов.
    Собирает метрики операций, бизнес-метрики и статус здоровья системы.
    """

    # Настройки кэширования
    CACHE_TTL = int(os.getenv("METRICS_CACHE_TTL", 300))  # 5 минут по умолчанию

    def get_operation_metrics(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """
        Получает метрики операций за заданный период.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь с метриками операций
        """
        cache_key = f"metrics:operations:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug("Возвращены кэшированные метрики операций")
            return cast("dict[str, Any]", cached)

        logs = CustomerSyncLog.objects.filter(created_at__gte=start_date, created_at__lt=end_date)

        # Общее количество операций
        total_operations = logs.count()

        # Количество операций по типам
        operations_by_type = {}
        for item in logs.values("operation_type").annotate(count=Count("id")):
            operations_by_type[item["operation_type"]] = item["count"]

        # Success/Error rates
        success_count = logs.filter(status=CustomerSyncLog.StatusType.SUCCESS).count()
        error_count = logs.filter(
            status__in=[
                CustomerSyncLog.StatusType.ERROR,
                CustomerSyncLog.StatusType.FAILED,
            ]
        ).count()
        warning_count = logs.filter(status=CustomerSyncLog.StatusType.WARNING).count()

        success_rate = round(success_count / total_operations * 100, 2) if total_operations > 0 else 0.0
        error_rate = round(error_count / total_operations * 100, 2) if total_operations > 0 else 0.0

        # Время выполнения
        duration_stats = logs.exclude(duration_ms__isnull=True).aggregate(
            avg=Avg("duration_ms"),
            min=Min("duration_ms"),
            max=Max("duration_ms"),
        )

        # Percentiles (приблизительные через PostgreSQL)
        p95_duration = self._calculate_percentile(logs, 95)
        p99_duration = self._calculate_percentile(logs, 99)

        metrics = {
            "total_operations": total_operations,
            "operations_by_type": operations_by_type,
            "success_count": success_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "success_rate": success_rate,
            "error_rate": error_rate,
            "duration_avg_ms": round(duration_stats["avg"] or 0, 2),
            "duration_min_ms": duration_stats["min"] or 0,
            "duration_max_ms": duration_stats["max"] or 0,
            "duration_p95_ms": p95_duration,
            "duration_p99_ms": p99_duration,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }

        # Кэшировать на 5 минут
        cache.set(cache_key, metrics, timeout=self.CACHE_TTL)

        logger.info(
            "Собраны метрики операций: %d операций, success rate: %.2f%%",
            total_operations,
            success_rate,
        )

        return metrics

    def _calculate_percentile(self, queryset: QuerySet, percentile: int) -> float:
        """
        Рассчитывает percentile для duration_ms используя PostgreSQL.

        Args:
            queryset: QuerySet с CustomerSyncLog
            percentile: Процентиль (например, 95 или 99)

        Returns:
            Значение percentile или 0 если данных нет
        """
        logs_with_duration = queryset.exclude(duration_ms__isnull=True)

        if not logs_with_duration.exists():
            return 0.0

        # Используем window function для расчета percentile
        table_name = CustomerSyncLog._meta.db_table
        with connection.cursor() as cursor:
            cursor.execute(
                f"""
                SELECT PERCENTILE_CONT(%s) WITHIN GROUP (ORDER BY duration_ms)
                FROM {table_name}
                WHERE created_at >= %s AND created_at < %s
                AND duration_ms IS NOT NULL
                """,
                [
                    percentile / 100.0,
                    queryset.query.where.children[0].rhs,  # type: ignore[union-attr]
                    queryset.query.where.children[1].rhs,  # type: ignore[union-attr]
                ],
            )
            result = cursor.fetchone()
            return float(round(result[0], 2)) if result and result[0] else 0.0

    def get_business_metrics(self, start_date: datetime, end_date: datetime) -> dict[str, Any]:
        """
        Получает бизнес-метрики за заданный период.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Словарь с бизнес-метриками
        """
        cache_key = f"metrics:business:{start_date.isoformat()}:{end_date.isoformat()}"
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug("Возвращены кэшированные бизнес-метрики")
            return cast("dict[str, Any]", cached)

        logs = CustomerSyncLog.objects.filter(created_at__gte=start_date, created_at__lt=end_date)

        # Количество синхронизированных клиентов
        synced_customers = logs.filter(status=CustomerSyncLog.StatusType.SUCCESS).values("customer").distinct().count()

        # Автоматически разрешенные конфликты по типам
        conflicts_resolved: dict[str, int] = {}
        conflict_logs = logs.filter(
            operation_type=CustomerSyncLog.OperationType.CONFLICT_RESOLUTION,
            status=CustomerSyncLog.StatusType.SUCCESS,
        )

        for log in conflict_logs:
            conflict_type = log.details.get("conflict_type", "unknown")
            conflicts_resolved[conflict_type] = conflicts_resolved.get(conflict_type, 0) + 1

        # Успешная идентификация клиентов по методам
        identification_methods: dict[str, int] = {}
        identification_logs = logs.filter(
            operation_type=CustomerSyncLog.OperationType.CUSTOMER_IDENTIFICATION,
            status=CustomerSyncLog.StatusType.SUCCESS,
        )

        for log in identification_logs:
            method = log.details.get("identification_method", "unknown")
            identification_methods[method] = identification_methods.get(method, 0) + 1

        # Новые регистрации vs импорт из 1С
        new_registrations = logs.filter(
            operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
            status=CustomerSyncLog.StatusType.SUCCESS,
        ).count()

        imports_from_1c = logs.filter(
            operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
            status=CustomerSyncLog.StatusType.SUCCESS,
        ).count()

        # Email уведомления отправлены администраторам
        notification_logs = logs.filter(
            Q(operation_type=CustomerSyncLog.OperationType.CONFLICT_RESOLUTION)
            | Q(operation_type=CustomerSyncLog.OperationType.ERROR)
        )
        admin_notifications_sent = notification_logs.count()

        # ROI от автоматизации (процент автоматических разрешений)
        total_conflicts = logs.filter(operation_type=CustomerSyncLog.OperationType.CONFLICT_RESOLUTION).count()

        auto_resolution_rate = round(len(conflicts_resolved) / total_conflicts * 100, 2) if total_conflicts > 0 else 0.0

        metrics = {
            "synced_customers_count": synced_customers,
            "conflicts_resolved": conflicts_resolved,
            "total_conflicts_resolved": sum(conflicts_resolved.values()),
            "identification_methods": identification_methods,
            "total_identifications": sum(identification_methods.values()),
            "new_registrations": new_registrations,
            "imports_from_1c": imports_from_1c,
            "admin_notifications_sent": admin_notifications_sent,
            "auto_resolution_rate": auto_resolution_rate,
            "period_start": start_date.isoformat(),
            "period_end": end_date.isoformat(),
        }

        # Кэшировать на 5 минут
        cache.set(cache_key, metrics, timeout=self.CACHE_TTL)

        logger.info(
            "Собраны бизнес-метрики: %d клиентов синхронизировано, " "автоматическое разрешение конфликтов: %.2f%%",
            synced_customers,
            auto_resolution_rate,
        )

        return metrics

    def get_system_health(self) -> dict[str, Any]:
        """
        Получает статус здоровья системы интеграции.

        Returns:
            Словарь со статусом системы и компонентов
        """
        cache_key = "metrics:system_health"
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug("Возвращен кэшированный system health")
            return cast("dict[str, Any]", cached)

        health_checker = IntegrationHealthCheck()

        # Проверяем все компоненты
        db_health = health_checker.check_database_connection()
        redis_health = health_checker.check_redis_connection()
        disk_health = health_checker.check_disk_space()

        # Опционально проверяем 1С API (если URL настроен)
        api_1c_url = os.getenv("HEALTH_CHECK_1C_API_URL")
        api_1c_health = health_checker.check_1c_api_availability() if api_1c_url else None

        # Агрегированный статус
        components = [db_health, redis_health, disk_health]
        if api_1c_health:
            components.append(api_1c_health)

        is_healthy = all(c["available"] for c in components)

        # Собираем критические проблемы
        critical_issues = []
        for component in components:
            if not component["available"]:
                critical_issues.append(
                    {
                        "component": component["component"],
                        "message": component.get("message", "Component unavailable"),
                        "details": component.get("error", ""),
                    }
                )

        health_status: dict[str, Any] = {
            "is_healthy": is_healthy,
            "components": {
                "database": db_health,
                "redis": redis_health,
                "disk": disk_health,
            },
            "critical_issues": critical_issues,
            "timestamp": timezone.now().isoformat(),
        }

        if api_1c_health:
            health_status["components"]["1c_api"] = api_1c_health

        # Кэшировать на 1 минуту (health check должен быть актуальным)
        cache.set(cache_key, health_status, timeout=60)

        if not is_healthy:
            logger.warning(
                "System health check FAILED: %d критических проблем",
                len(critical_issues),
            )
        else:
            logger.debug("System health check OK")

        return health_status

    def get_real_time_metrics(self) -> dict[str, Any]:
        """
        Получает метрики в реальном времени (последние 5 минут).

        Returns:
            Словарь с актуальными метриками
        """
        now = timezone.now()
        start_time = now - timedelta(minutes=5)

        cache_key = "metrics:realtime"
        cached = cache.get(cache_key)

        if cached is not None:
            logger.debug("Возвращены кэшированные realtime метрики")
            return cast("dict[str, Any]", cached)

        recent_logs = CustomerSyncLog.objects.filter(created_at__gte=start_time)

        # Текущая активность
        operations_last_5min = recent_logs.count()
        errors_last_5min = recent_logs.filter(
            status__in=[
                CustomerSyncLog.StatusType.ERROR,
                CustomerSyncLog.StatusType.FAILED,
            ]
        ).count()

        # Текущий error rate
        current_error_rate = (
            round(errors_last_5min / operations_last_5min * 100, 2) if operations_last_5min > 0 else 0.0
        )

        # Операции в процессе
        pending_operations = CustomerSyncLog.objects.filter(status=CustomerSyncLog.StatusType.PENDING).count()

        # Throughput (операций в минуту)
        throughput = operations_last_5min / 5.0  # За 5 минут

        metrics = {
            "operations_last_5min": operations_last_5min,
            "errors_last_5min": errors_last_5min,
            "current_error_rate": current_error_rate,
            "pending_operations": pending_operations,
            "throughput_per_minute": round(throughput, 2),
            "timestamp": now.isoformat(),
        }

        # Кэшировать на 30 секунд (realtime данные)
        cache.set(cache_key, metrics, timeout=30)

        return metrics

    def get_hourly_breakdown(self, start_date: datetime, end_date: datetime) -> list[dict[str, Any]]:
        """
        Получает почасовую разбивку метрик.

        Args:
            start_date: Начало периода
            end_date: Конец периода

        Returns:
            Список с метриками по часам
        """
        logs = CustomerSyncLog.objects.filter(created_at__gte=start_date, created_at__lt=end_date)

        hourly_data = (
            logs.annotate(hour=TruncHour("created_at"))
            .values("hour")
            .annotate(
                total=Count("id"),
                success=Count("id", filter=Q(status=CustomerSyncLog.StatusType.SUCCESS)),
                errors=Count(
                    "id",
                    filter=Q(
                        status__in=[
                            CustomerSyncLog.StatusType.ERROR,
                            CustomerSyncLog.StatusType.FAILED,
                        ]
                    ),
                ),
                avg_duration=Avg("duration_ms"),
            )
            .order_by("hour")
        )

        return [
            {
                "hour": item["hour"].isoformat(),
                "total_operations": item["total"],
                "successful_operations": item["success"],
                "failed_operations": item["errors"],
                "avg_duration_ms": round(item["avg_duration"] or 0, 2),
                "success_rate": (round(item["success"] / item["total"] * 100, 2) if item["total"] > 0 else 0.0),
            }
            for item in hourly_data
        ]


class IntegrationHealthCheck:
    """
    Health checks для компонентов системы интеграции.
    """

    def check_1c_api_availability(self) -> dict[str, Any]:
        """
        Проверяет доступность API 1С.

        Returns:
            Словарь с результатом проверки
        """
        api_url = os.getenv("HEALTH_CHECK_1C_API_URL")
        timeout = int(os.getenv("HEALTH_CHECK_TIMEOUT", 5))

        if not api_url:
            return {
                "component": "1c_api",
                "available": False,
                "message": "1C API URL не настроен",
            }

        try:
            response = requests.get(api_url, timeout=timeout)
            is_available = response.status_code == 200

            return {
                "component": "1c_api",
                "available": is_available,
                "response_time_ms": round(response.elapsed.total_seconds() * 1000, 2),
                "status_code": response.status_code,
                "message": "OK" if is_available else f"HTTP {response.status_code}",
            }

        except RequestException as e:
            logger.error("1C API health check failed: %s", str(e))
            return {
                "component": "1c_api",
                "available": False,
                "error": str(e),
                "message": "1C API недоступен",
            }

    def check_database_connection(self) -> dict[str, Any]:
        """
        Проверяет подключение к PostgreSQL.

        Returns:
            Словарь с результатом проверки
        """
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
                cursor.fetchone()

            return {
                "component": "database",
                "available": True,
                "message": "OK",
            }

        except Exception as e:
            logger.error("Database health check failed: %s", str(e))
            return {
                "component": "database",
                "available": False,
                "error": str(e),
                "message": "Database недоступна",
            }

    def check_redis_connection(self) -> dict[str, Any]:
        """
        Проверяет подключение к Redis.

        Returns:
            Словарь с результатом проверки
        """
        try:
            # Пытаемся записать и прочитать тестовое значение
            test_key = "health_check:redis"
            cache.set(test_key, "OK", timeout=10)
            result = cache.get(test_key)

            is_available = result == "OK"

            return {
                "component": "redis",
                "available": is_available,
                "message": "OK" if is_available else "Redis test failed",
            }

        except Exception as e:
            logger.error("Redis health check failed: %s", str(e))
            return {
                "component": "redis",
                "available": False,
                "error": str(e),
                "message": "Redis недоступен",
            }

    def check_celery_workers(self) -> dict[str, Any]:
        """
        Проверяет статус Celery workers.

        Returns:
            Словарь с результатом проверки
        """
        # Эта проверка требует celery inspect
        # Для упрощения пока возвращаем placeholder
        return {
            "component": "celery_workers",
            "available": True,
            "message": "Check not implemented",
        }

    def check_disk_space(self) -> dict[str, Any]:
        """
        Проверяет свободное место на диске для логов.

        Returns:
            Словарь с результатом проверки
        """
        threshold = int(os.getenv("HEALTH_CHECK_DISK_THRESHOLD", 90))

        try:
            # Получаем статистику диска
            stat = shutil.disk_usage("/")
            total_gb = stat.total / (1024**3)
            used_gb = stat.used / (1024**3)
            free_gb = stat.free / (1024**3)
            used_percent = (stat.used / stat.total) * 100

            is_available = used_percent < threshold

            return {
                "component": "disk_space",
                "available": is_available,
                "total_gb": round(total_gb, 2),
                "used_gb": round(used_gb, 2),
                "free_gb": round(free_gb, 2),
                "used_percent": round(used_percent, 2),
                "threshold_percent": threshold,
                "message": (
                    "OK" if is_available else (f"Disk usage {used_percent:.1f}% " f"exceeds threshold {threshold}%")
                ),
            }

        except Exception as e:
            logger.error("Disk space health check failed: %s", str(e))
            return {
                "component": "disk_space",
                "available": False,
                "error": str(e),
                "message": "Не удалось проверить место на диске",
            }

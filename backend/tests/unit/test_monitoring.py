"""
Unit тесты для системы мониторинга синхронизации.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.common.services import AlertManager, CustomerSyncMonitor, IntegrationHealthCheck

User = get_user_model()


@pytest.mark.unit
class TestCustomerSyncMonitor(TestCase):
    """Тесты для класса CustomerSyncMonitor."""

    def setUp(self) -> None:
        """Подготовка тестовых данных."""
        self.monitor = CustomerSyncMonitor()
        self.start_date = timezone.now() - timedelta(hours=24)

        # Создаем тестового пользователя
        self.user = User.objects.create_user(
            email=f"test_{timezone.now().timestamp()}@example.com",
            password="testpass123",
            role="retail",
        )

        # Создаем тестовые логи
        self._create_test_logs()
        self.now = timezone.now() + timedelta(seconds=1)

    def _create_test_logs(self) -> None:
        """Создает тестовые логи синхронизации."""
        # Успешные операции
        for i in range(80):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=self.user,
                onec_id=f"1C-{i}",
                duration_ms=100 + i * 10,
                correlation_id=uuid.uuid4(),
                details={"test": "data"},
            )

        # Ошибочные операции
        for i in range(20):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=self.user,
                onec_id=f"1C-ERR-{i}",
                duration_ms=50 + i * 5,
                correlation_id=uuid.uuid4(),
                error_message=f"Test error {i}",
            )

    def test_get_operation_metrics_success(self) -> None:
        """Тест получения метрик операций."""
        metrics = self.monitor.get_operation_metrics(self.start_date, self.now)

        # Проверяем основные метрики
        self.assertEqual(metrics["total_operations"], 100)
        self.assertEqual(metrics["success_count"], 80)
        self.assertEqual(metrics["error_count"], 20)
        self.assertEqual(metrics["success_rate"], 80.0)
        self.assertEqual(metrics["error_rate"], 20.0)

        # Проверяем наличие всех полей
        self.assertIn("duration_avg_ms", metrics)
        self.assertIn("duration_p95_ms", metrics)
        self.assertIn("duration_p99_ms", metrics)
        self.assertIn("operations_by_type", metrics)

    def test_get_business_metrics_success(self) -> None:
        """Тест получения бизнес-метрик."""
        metrics = self.monitor.get_business_metrics(self.start_date, self.now)

        # Проверяем наличие ключевых полей
        self.assertIn("synced_customers_count", metrics)
        self.assertIn("conflicts_resolved", metrics)
        self.assertIn("identification_methods", metrics)
        self.assertIn("auto_resolution_rate", metrics)

    def test_get_real_time_metrics_success(self) -> None:
        """Тест получения метрик в реальном времени."""
        metrics = self.monitor.get_real_time_metrics()

        # Проверяем структуру ответа
        self.assertIn("operations_last_5min", metrics)
        self.assertIn("errors_last_5min", metrics)
        self.assertIn("current_error_rate", metrics)
        self.assertIn("pending_operations", metrics)
        self.assertIn("throughput_per_minute", metrics)

    @patch("apps.common.services.customer_sync_monitor.cache")
    def test_metrics_caching(self, mock_cache: MagicMock) -> None:
        """Тест кэширования метрик."""
        mock_cache.get.return_value = None

        # Первый вызов - должен сохранить в кэш
        self.monitor.get_operation_metrics(self.start_date, self.now)

        # Проверяем что cache.set был вызван
        mock_cache.set.assert_called_once()

    def test_get_hourly_breakdown(self) -> None:
        """Тест почасовой разбивки метрик."""
        breakdown = self.monitor.get_hourly_breakdown(self.start_date, self.now)

        # Проверяем что вернулся список
        self.assertIsInstance(breakdown, list)

        # Если есть данные, проверяем структуру
        if breakdown:
            first_item = breakdown[0]
            self.assertIn("hour", first_item)
            self.assertIn("total_operations", first_item)
            self.assertIn("successful_operations", first_item)
            self.assertIn("failed_operations", first_item)
            self.assertIn("success_rate", first_item)


@pytest.mark.unit
class TestIntegrationHealthCheck(TestCase):
    """Тесты для класса IntegrationHealthCheck."""

    def setUp(self) -> None:
        """Подготовка к тестам."""
        self.health_checker = IntegrationHealthCheck()

    def test_check_database_connection_success(self) -> None:
        """Тест проверки подключения к БД."""
        result = self.health_checker.check_database_connection()

        self.assertEqual(result["component"], "database")
        self.assertTrue(result["available"])
        self.assertEqual(result["message"], "OK")

    @patch("apps.common.services.customer_sync_monitor.cache")
    def test_check_redis_connection_success(self, mock_cache: MagicMock) -> None:
        """Тест проверки подключения к Redis."""
        mock_cache.get.return_value = "OK"

        result = self.health_checker.check_redis_connection()

        self.assertEqual(result["component"], "redis")
        self.assertTrue(result["available"])

    @patch("apps.common.services.customer_sync_monitor.cache")
    def test_check_redis_connection_failure(self, mock_cache: MagicMock) -> None:
        """Тест неудачной проверки Redis."""
        mock_cache.set.side_effect = Exception("Redis connection failed")

        result = self.health_checker.check_redis_connection()

        self.assertEqual(result["component"], "redis")
        self.assertFalse(result["available"])
        self.assertIn("error", result)

    def test_check_disk_space_success(self) -> None:
        """Тест проверки места на диске."""
        result = self.health_checker.check_disk_space()

        self.assertEqual(result["component"], "disk_space")
        self.assertIn("total_gb", result)
        self.assertIn("used_gb", result)
        self.assertIn("free_gb", result)
        self.assertIn("used_percent", result)

    @patch("apps.common.services.customer_sync_monitor.requests.get")
    @patch.dict("os.environ", {"HEALTH_CHECK_1C_API_URL": "http://test.com"})
    def test_check_1c_api_availability_success(self, mock_get: MagicMock) -> None:
        """Тест проверки доступности 1C API."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.1
        mock_get.return_value = mock_response

        result = self.health_checker.check_1c_api_availability()

        self.assertEqual(result["component"], "1c_api")
        self.assertTrue(result["available"])
        self.assertEqual(result["status_code"], 200)


@pytest.mark.unit
class TestAlertManager(TestCase):
    """Тесты для класса AlertManager."""

    def setUp(self) -> None:
        """Подготовка к тестам."""
        self.alert_manager = AlertManager()
        self.now = timezone.now()
        self.user = User.objects.create_user(
            email=f"test_alert_{self.now.timestamp()}@example.com",
            password="testpass123",
            role="retail",
        )

    @patch("apps.common.services.alerting.WebhookAlerts.send_critical_alert")
    def test_check_high_error_rate_alert(self, mock_send_alert: MagicMock) -> None:
        """Тест алерта при высоком error rate."""
        # Создаем много ошибочных операций
        for i in range(15):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=self.user,
                onec_id=f"1C-ERR-{i}",
                correlation_id=uuid.uuid4(),
                error_message=f"Test error {i}",
            )

        # Создаем несколько успешных
        for i in range(5):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                onec_id=f"1C-OK-{i}",
                correlation_id=uuid.uuid4(),
                customer=self.user,
            )

        mock_send_alert.return_value = True

        # Запускаем проверку
        check_now = timezone.now() + timedelta(seconds=1)
        start_time = check_now - timedelta(hours=1)
        alert = self.alert_manager._check_high_error_rate(start_time, check_now)

        # Проверяем что алерт был создан (error rate > 10%)
        self.assertIsNotNone(alert)
        self.assertIn("Error Rate", alert["title"])
        self.assertIn("details", alert)

    @patch("apps.common.services.alerting.cache")
    def test_alert_cooldown_deduplication(self, mock_cache: MagicMock) -> None:
        """Тест дедупликации алертов через cooldown."""
        # Первый раз - нет в кэше
        mock_cache.get.return_value = None
        should_send = self.alert_manager._should_send_alert("test_alert")
        self.assertTrue(should_send)

        # Второй раз - есть в кэше (недавно отправлялся)
        mock_cache.get.return_value = self.now.isoformat()
        should_send = self.alert_manager._should_send_alert("test_alert")
        self.assertFalse(should_send)


@pytest.mark.unit
class TestSystemHealth(TestCase):
    """Тесты для get_system_health."""

    def setUp(self) -> None:
        """Подготовка к тестам."""
        self.monitor = CustomerSyncMonitor()

    @patch("apps.common.services.customer_sync_monitor.cache")
    @patch("apps.common.services.customer_sync_monitor.IntegrationHealthCheck")
    def test_system_health_all_ok(self, mock_health_check: MagicMock, mock_cache: MagicMock) -> None:
        """Тест когда все компоненты здоровы."""
        mock_cache.get.return_value = None
        mock_checker = MagicMock()
        mock_checker.check_database_connection.return_value = {
            "component": "database",
            "available": True,
            "message": "OK",
        }
        mock_checker.check_redis_connection.return_value = {
            "component": "redis",
            "available": True,
            "message": "OK",
        }
        mock_checker.check_disk_space.return_value = {
            "component": "disk_space",
            "available": True,
            "message": "OK",
        }
        mock_health_check.return_value = mock_checker

        health = self.monitor.get_system_health()

        self.assertTrue(health["is_healthy"])
        self.assertEqual(len(health["critical_issues"]), 0)
        self.assertIn("components", health)

    @patch("apps.common.services.customer_sync_monitor.cache")
    @patch("apps.common.services.customer_sync_monitor.IntegrationHealthCheck")
    def test_system_health_with_issues(self, mock_health_check: MagicMock, mock_cache: MagicMock) -> None:
        """Тест когда есть проблемы с компонентами."""
        mock_cache.get.return_value = None
        mock_checker = MagicMock()
        mock_checker.check_database_connection.return_value = {
            "component": "database",
            "available": False,
            "message": "Connection failed",
            "error": "Timeout",
        }
        mock_checker.check_redis_connection.return_value = {
            "component": "redis",
            "available": True,
            "message": "OK",
        }
        mock_checker.check_disk_space.return_value = {
            "component": "disk_space",
            "available": True,
            "message": "OK",
        }
        mock_health_check.return_value = mock_checker

        health = self.monitor.get_system_health()

        self.assertFalse(health["is_healthy"])
        self.assertGreater(len(health["critical_issues"]), 0)
        self.assertEqual(health["critical_issues"][0]["component"], "database")

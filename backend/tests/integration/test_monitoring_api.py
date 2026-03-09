"""
Integration тесты для API мониторинга.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import CustomerSyncLog

User = get_user_model()


@pytest.mark.integration
class TestMonitoringAPIEndpoints(TestCase):
    """Интеграционные тесты для endpoints мониторинга."""

    def setUp(self) -> None:
        """Подготовка тестовых данных."""
        self.client = APIClient()
        self.now = timezone.now()

        # Создаем админ пользователя
        self.admin_user = User.objects.create_superuser(
            email=f"admin_{self.now.timestamp()}@example.com",
            password="adminpass123",
        )

        # Создаем обычного пользователя
        self.regular_user = User.objects.create_user(
            email=f"user_{self.now.timestamp()}@example.com",
            password="userpass123",
            role="retail",
        )

        # Создаем тестовые логи
        self._create_test_logs()

    def _create_test_logs(self) -> None:
        """Создает тестовые логи синхронизации."""
        # Успешные операции
        for i in range(10):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=self.regular_user,
                onec_id=f"1C-SUCCESS-{i}",
                duration_ms=100 + i * 10,
                correlation_id=uuid.uuid4(),
            )

        # Ошибочные операции
        for i in range(3):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=self.regular_user,
                onec_id=f"1C-ERROR-{i}",
                error_message=f"Test error {i}",
                correlation_id=uuid.uuid4(),
            )

    def test_operation_metrics_requires_admin(self) -> None:
        """Тест что endpoints требуют права администратора."""
        url = reverse("common:operation-metrics")

        # Без авторизации
        response = self.client.get(url)
        self.assertIn(
            response.status_code,
            [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN],
        )

        # С обычным пользователем
        self.client.force_authenticate(user=self.regular_user)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operation_metrics_success(self) -> None:
        """Тест успешного получения метрик операций."""
        url = reverse("common:operation-metrics")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем структуру ответа
        self.assertIn("total_operations", data)
        self.assertIn("success_count", data)
        self.assertIn("error_count", data)
        self.assertIn("success_rate", data)
        self.assertIn("operations_by_type", data)

        # Проверяем значения
        self.assertEqual(data["total_operations"], 13)
        self.assertEqual(data["success_count"], 10)
        self.assertEqual(data["error_count"], 3)

    def test_operation_metrics_with_date_range(self) -> None:
        """Тест метрик с указанием диапазона дат."""
        url = reverse("common:operation-metrics")
        self.client.force_authenticate(user=self.admin_user)

        start_date = (self.now - timedelta(hours=1)).isoformat()
        end_date = self.now.isoformat()

        response = self.client.get(url, {"start_date": start_date, "end_date": end_date})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("period_start", data)
        self.assertIn("period_end", data)

    def test_business_metrics_success(self) -> None:
        """Тест получения бизнес-метрик."""
        url = reverse("common:business-metrics")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем наличие ключевых полей
        self.assertIn("synced_customers_count", data)
        self.assertIn("conflicts_resolved", data)
        self.assertIn("auto_resolution_rate", data)

    def test_system_health_success(self) -> None:
        """Тест получения статуса здоровья системы."""
        url = reverse("common:system-health")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(url)

        # Может быть 200 (healthy) или 503 (unhealthy)
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE],
        )
        data = response.json()

        # Проверяем структуру
        self.assertIn("is_healthy", data)
        self.assertIn("components", data)
        self.assertIn("critical_issues", data)

        # Проверяем компоненты
        components = data["components"]
        self.assertIn("database", components)
        self.assertIn("redis", components)
        self.assertIn("disk", components)

    def test_realtime_metrics_success(self) -> None:
        """Тест получения метрик в реальном времени."""
        url = reverse("common:realtime-metrics")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        # Проверяем структуру
        self.assertIn("operations_last_5min", data)
        self.assertIn("errors_last_5min", data)
        self.assertIn("current_error_rate", data)
        self.assertIn("pending_operations", data)
        self.assertIn("throughput_per_minute", data)

    def test_invalid_date_format(self) -> None:
        """Тест обработки некорректного формата даты."""
        url = reverse("common:operation-metrics")
        self.client.force_authenticate(user=self.admin_user)

        response = self.client.get(url, {"start_date": "invalid-date", "end_date": "also-invalid"})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("error", data)

    def test_invalid_date_range(self) -> None:
        """Тест когда start_date > end_date."""
        url = reverse("common:operation-metrics")
        self.client.force_authenticate(user=self.admin_user)

        start_date = self.now.isoformat()
        end_date = (self.now - timedelta(hours=1)).isoformat()

        response = self.client.get(url, {"start_date": start_date, "end_date": end_date})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.json()
        self.assertIn("error", data)


@pytest.mark.integration
class TestHealthCheckEndpoint(TestCase):
    """Тесты для публичного health check endpoint."""

    def setUp(self) -> None:
        """Подготовка к тестам."""
        self.client = APIClient()

    def test_health_check_public_access(self) -> None:
        """Тест что health check доступен без авторизации."""
        url = reverse("common:health-check")

        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()

        self.assertIn("status", data)
        self.assertEqual(data["status"], "healthy")

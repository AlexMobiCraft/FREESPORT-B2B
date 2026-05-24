"""
Тесты для общих моделей FREESPORT Platform
"""

import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase

from apps.common.models import AuditLog, SyncLog
from tests.conftest import AuditLogFactory, ProductFactory, SyncLogFactory, UserFactory

User = get_user_model()


class TestAuditLogModel(TestCase):
    """Тесты модели AuditLog"""

    def test_audit_log_creation(self):
        """Тест создания записи аудита"""
        user = UserFactory.create()
        audit_log = AuditLogFactory.create(
            user=user,
            action="create",
            resource_type="Product",
            resource_id="123",
            details={"name": "Новый товар", "price": "1000.00"},
            ip_address="192.168.1.1",
        )

        self.assertEqual(audit_log.user, user)
        self.assertEqual(audit_log.action, "create")
        self.assertEqual(audit_log.resource_type, "Product")
        self.assertEqual(audit_log.resource_id, "123")
        self.assertEqual(audit_log.details, {"name": "Новый товар", "price": "1000.00"})
        self.assertEqual(audit_log.ip_address, "192.168.1.1")
        # Check str representation contains key info
        self.assertIn("create", str(audit_log))
        self.assertIn("Product", str(audit_log))

    def test_audit_log_without_user(self):
        """Тест создания записи аудита без пользователя (системные операции)"""
        audit_log = AuditLogFactory.create(
            user=None,
            action="sync",
            resource_type="Product",
            resource_id="batch_123",
            details={"imported": 100},
        )

        assert audit_log.user is None
        assert audit_log.action == "sync"
        # Check str representation contains 'sync' and 'Product'
        assert "sync" in str(audit_log)
        assert "Product" in str(audit_log)

    def test_audit_log_action_choices(self):
        """Тест валидных действий аудита"""
        valid_actions = ["create", "update", "delete", "login", "logout", "sync"]

        for action in valid_actions:
            audit_log = AuditLogFactory.create(action=action)
            audit_log.full_clean()  # Не должно вызывать ValidationError
            assert audit_log.action == action

    def test_audit_log_json_changes_field(self):
        """Тест JSON поля изменений"""
        complex_changes = {
            "old_values": {"name": "Старое название", "price": 500.00},
            "new_values": {"name": "Новое название", "price": 750.00},
            "metadata": {"editor": "admin", "timestamp": "2024-01-01T10:00:00"},
        }

        audit_log = AuditLogFactory.create(details=complex_changes)

        # Проверяем что JSON правильно сериализуется/десериализуется
        assert audit_log.details == complex_changes
        assert audit_log.details["old_values"]["name"] == "Старое название"
        assert audit_log.details["new_values"]["price"] == 750.00

    def test_audit_log_ip_address_validation(self):
        """Тест валидации IP адресов"""
        # Валидные IPv4 адреса
        valid_ips = ["192.168.1.1", "127.0.0.1", "10.0.0.1", "172.16.0.1"]

        for ip in valid_ips:
            audit_log = AuditLogFactory.create(ip_address=ip)
            audit_log.full_clean()
            assert audit_log.ip_address == ip

    def test_audit_log_for_product_operations(self):
        """Тест аудита операций с товарами"""
        user = UserFactory.create(role="admin")
        product = ProductFactory.create()

        # Имитируем создание товара
        create_log = AuditLogFactory.create(
            user=user,
            action="create",
            resource_type="Product",
            resource_id=str(product.id),
            details={"name": product.name},
        )

        # Имитируем обновление товара
        update_log = AuditLogFactory.create(
            user=user,
            action="update",
            resource_type="Product",
            resource_id=str(product.id),
            details={"old": {"price": "1000.00"}, "new": {"price": "1200.00"}},
        )

        assert create_log.resource_type == "Product"
        assert create_log.action == "create"
        assert update_log.resource_type == "Product"
        assert update_log.action == "update"
        assert create_log.resource_id == update_log.resource_id

    def test_audit_log_user_actions(self):
        """Тест аудита действий пользователей"""
        user = UserFactory.create()

        login_log = AuditLogFactory.create(
            user=user,
            action="login",
            resource_type="User",
            resource_id=str(user.id),
            details={"login_time": "2024-01-01T09:00:00"},
            ip_address="192.168.1.100",
        )

        logout_log = AuditLogFactory.create(
            user=user,
            action="logout",
            resource_type="User",
            resource_id=str(user.id),
            details={"logout_time": "2024-01-01T17:00:00"},
            ip_address="192.168.1.100",
        )

        assert login_log.action == "login"
        assert logout_log.action == "logout"
        assert login_log.ip_address == logout_log.ip_address

    def test_audit_log_timestamps(self):
        """Тест автоматических временных меток"""
        audit_log = AuditLogFactory.create()

        assert audit_log.created_at is not None
        # created_at должен устанавливаться автоматически при создании

    def test_audit_log_meta_configuration(self):
        """Тест настроек Meta класса AuditLog"""
        assert AuditLog._meta.verbose_name == "Аудит лог"
        assert AuditLog._meta.verbose_name_plural == "Аудит логи"
        # db_table is not explicitly set, Django generates it
        assert AuditLog._meta.ordering == ["-created_at"]


@pytest.mark.django_db
class TestSyncLogModel:
    """Тесты модели SyncLog"""

    def test_sync_log_creation(self):
        """Тест создания лога синхронизации"""
        sync_log = SyncLogFactory.create(
            sync_type="products",
            status="completed",
            records_processed=150,
            errors_count=2,
            error_details=["Error 1", "Error 2"],
        )

        assert sync_log.sync_type == "products"
        assert sync_log.status == "completed"
        assert sync_log.records_processed == 150
        assert sync_log.errors_count == 2
        assert sync_log.error_details == ["Error 1", "Error 2"]
        # Проверяем что строковое представление содержит ключевую информацию
        str_repr = str(sync_log)
        assert "products" in str_repr  # sync_type raw value

    def test_sync_log_sync_types(self):
        """Тест типов синхронизации"""
        sync_types = ["products", "stocks", "orders", "prices"]

        for sync_type in sync_types:
            sync_log = SyncLogFactory.create(sync_type=sync_type)
            sync_log.full_clean()
            assert sync_log.sync_type == sync_type

    def test_sync_log_status_choices(self):
        """Тест статусов синхронизации"""
        statuses = ["started", "completed", "failed"]

        for status in statuses:
            sync_log = SyncLogFactory.create(status=status)
            sync_log.full_clean()
            assert sync_log.status == status

    def test_sync_log_successful_sync(self):
        """Тест успешной синхронизации"""
        sync_log = SyncLogFactory.create(
            sync_type="products",
            status="completed",
            records_processed=1000,
            errors_count=0,
            error_details={
                "started_at": "2024-01-01T10:00:00",
                "completed_at": "2024-01-01T10:05:00",
                "source": "external_api",
                "imported": 1000,
                "updated": 850,
                "created": 150,
            },
        )

        assert sync_log.records_processed == 1000
        assert sync_log.errors_count == 0
        assert sync_log.status == "completed"
        assert sync_log.error_details["imported"] == 1000

    def test_sync_log_failed_sync(self):
        """Тест неудачной синхронизации"""
        sync_log = SyncLogFactory.create(
            sync_type="orders",
            status="failed",
            records_processed=0,
            errors_count=1,
            error_details={
                "error_type": "ConnectionError",
                "retry_count": 3,
                "last_retry": "2024-01-01T10:15:00",
            },
        )

        assert sync_log.status == "failed"
        assert sync_log.records_processed == 0
        assert sync_log.errors_count == 1
        assert sync_log.error_details["error_type"] == "ConnectionError"

    def test_sync_log_partial_sync(self):
        """Тест частично успешной синхронизации"""
        sync_log = SyncLogFactory.create(
            sync_type="inventory",
            status="completed",
            records_processed=500,
            errors_count=50,
            error_details={
                "total_attempted": 550,
                "successful": 500,
                "failed": 50,
                "errors": [
                    {"record_id": "INV001", "error": "Invalid data format"},
                    {"record_id": "INV002", "error": "Missing required field"},
                ],
            },
        )

        assert sync_log.records_processed == 500
        assert sync_log.errors_count == 50
        assert sync_log.status == "completed"
        assert len(sync_log.error_details["errors"]) == 2

    def test_sync_log_validation_non_negative_counts(self):
        """Тест корректных неотрицательных счетчиков"""
        # PositiveIntegerField автоматически поддерживают только неотрицательные
        # значения
        sync_log = SyncLogFactory.create(records_processed=100, errors_count=5)
        sync_log.full_clean()  # Должно пройти без ошибок

        assert sync_log.records_processed >= 0
        assert sync_log.errors_count >= 0

    def test_sync_log_json_details_field(self):
        """Тест JSON поля деталей"""
        complex_details = {
            "api_endpoint": "https://api.supplier.com/v1/products",
            "authentication": {"method": "API_KEY", "user": "freesport"},
            "filters": {"category": "sports", "active": True},
            "pagination": {"page_size": 100, "total_pages": 10},
            "performance": {
                "avg_response_time": 1.2,
                "total_duration": 45.8,
                "rate_limit_hits": 0,
            },
            "mapping_errors": [
                {"field": "brand_id", "value": "unknown_brand", "record": 15},
                {"field": "category_id", "value": None, "record": 23},
            ],
        }

        sync_log = SyncLogFactory.create(error_details=complex_details)

        assert sync_log.error_details == complex_details
        assert sync_log.error_details["performance"]["avg_response_time"] == 1.2
        assert len(sync_log.error_details["mapping_errors"]) == 2

    def test_sync_log_timestamps(self):
        """Тест автоматических временных меток"""
        sync_log = SyncLogFactory.create()

        assert sync_log.started_at is not None
        assert sync_log.completed_at is None  # По умолчанию None до завершения
        # completed_at может быть равен started_at если синхронизация очень быстрая

    def test_sync_log_running_status_without_finish_time(self):
        """Тест лога с статусом running без времени завершения"""
        sync_log = SyncLogFactory.create(status="running", completed_at=None)

        assert sync_log.status == "running"
        assert sync_log.started_at is not None
        assert sync_log.completed_at is None

    def test_sync_log_meta_configuration(self):
        """Тест настроек Meta класса SyncLog"""
        assert SyncLog._meta.verbose_name == "Лог синхронизации"
        assert SyncLog._meta.verbose_name_plural == "Логи синхронизации"
        assert SyncLog._meta.db_table == "common_synclog"
        assert SyncLog._meta.ordering == ["-started_at"]

    def test_sync_log_bulk_operations(self):
        """Тест логирования массовых операций"""
        # Имитируем большую синхронизацию товаров
        bulk_sync = SyncLogFactory.create(
            sync_type="products",
            status="completed",
            records_processed=10000,
            errors_count=25,
            error_details={
                "batch_size": 1000,
                "total_batches": 10,
                "failed_batches": [],
                "summary": {
                    "new_products": 2500,
                    "updated_products": 7475,
                    "deactivated_products": 100,
                    "validation_errors": 25,
                },
            },
        )

        assert bulk_sync.records_processed == 10000
        assert bulk_sync.error_details["summary"]["new_products"] == 2500
        assert bulk_sync.error_details["total_batches"] == 10

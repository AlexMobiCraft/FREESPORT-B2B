"""
Unit тесты для CustomerSyncLogger
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.common.services import CustomerSyncLogger

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestCustomerSyncLogger:
    """Тесты для CustomerSyncLogger"""

    @pytest.fixture
    def sync_logger(self):
        """Фикстура для создания логгера"""
        return CustomerSyncLogger()

    @pytest.fixture
    def test_user(self):
        """Фикстура для создания тестового пользователя"""
        return User.objects.create_user(
            email="test@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )

    def test_generate_correlation_id(self, sync_logger):
        """Тест генерации correlation ID"""
        assert sync_logger.correlation_id is not None
        assert len(sync_logger.correlation_id) > 0
        assert isinstance(sync_logger.correlation_id, str)

    def test_log_customer_import_success(self, sync_logger, test_user):
        """Тест логирования успешного импорта клиента"""
        customer_data = {
            "id": "1C_12345",
            "email": "customer@example.com",
            "customer_type": "Опт 1",
        }

        result = {
            "success": True,
            "customer": test_user,
            "created": True,
        }

        log = sync_logger.log_customer_import(customer_data, result, duration_ms=150)

        assert log.operation_type == CustomerSyncLog.OperationType.IMPORT_FROM_1C
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.customer == test_user
        assert log.customer_email == test_user.email
        assert log.onec_id == "1C_12345"
        assert log.duration_ms == 150
        assert log.correlation_id == sync_logger.correlation_id

    def test_log_customer_import_error(self, sync_logger):
        """Тест логирования ошибки при импорте"""
        customer_data = {
            "id": "1C_ERROR",
            "email": "error@example.com",
        }

        result = {
            "success": False,
            "error_message": "Invalid email format",
        }

        log = sync_logger.log_customer_import(customer_data, result)

        assert log.operation_type == CustomerSyncLog.OperationType.IMPORT_FROM_1C
        assert log.status == CustomerSyncLog.StatusType.ERROR
        assert log.customer is None
        assert log.error_message == "Invalid email format"

    def test_log_customer_export(self, sync_logger, test_user):
        """Тест логирования экспорта клиента"""
        result = {
            "success": True,
            "onec_id": "1C_EXPORTED_123",
            "export_format": "json",
            "exported_fields": ["email", "first_name", "last_name"],
        }

        log = sync_logger.log_customer_export(test_user, result, duration_ms=200)

        assert log.operation_type == CustomerSyncLog.OperationType.EXPORT_TO_1C
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.customer == test_user
        assert log.duration_ms == 200

    def test_log_customer_identification_found(self, sync_logger, test_user):
        """Тест логирования успешной идентификации"""
        onec_data = {
            "email": "test@example.com",
            "onec_id": "1C_123",
        }

        identification_result = {
            "found": True,
            "customer": test_user,
            "method": "email",
            "search_value": "test@example.com",
            "normalized_value": "test@example.com",
        }

        log = sync_logger.log_customer_identification(onec_data, identification_result, duration_ms=50)

        assert log.operation_type == CustomerSyncLog.OperationType.CUSTOMER_IDENTIFICATION  # noqa
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.customer == test_user
        assert log.details["search_method"] == "email"

    def test_log_customer_identification_not_found(self, sync_logger):
        """Тест логирования неуспешной идентификации"""
        onec_data = {
            "email": "notfound@example.com",
            "onec_id": "1C_NOTFOUND",
        }

        identification_result = {
            "found": False,
            "customer": None,
            "method": "email",
            "search_value": "notfound@example.com",
        }

        log = sync_logger.log_customer_identification(onec_data, identification_result)

        assert log.status == CustomerSyncLog.StatusType.SKIPPED
        assert log.customer is None
        assert log.details["found"] is False

    def test_log_conflict_resolution(self, sync_logger, test_user):
        """Тест логирования разрешения конфликта"""
        onec_data = {"onec_id": "1C_CONFLICT"}

        resolution_result = {
            "success": True,
            "conflicting_fields": ["email", "phone"],
            "changes_made": {"email": "new@example.com"},
            "action": "confirmed_client",
            "email_sent": True,
            "sync_conflict_id": 123,
        }

        log = sync_logger.log_conflict_resolution(
            test_user,
            onec_data,
            "portal_registration",
            resolution_result,
            duration_ms=300,
        )

        assert log.operation_type == CustomerSyncLog.OperationType.CONFLICT_RESOLUTION  # noqa
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.details["conflict_source"] == "portal_registration"
        assert log.details["resolution_strategy"] == "onec_wins"

    def test_log_batch_operation(self, sync_logger):
        """Тест логирования пакетной операции"""
        log = sync_logger.log_batch_operation(
            operation_name="Import customers from 1C",
            total_count=100,
            success_count=95,
            error_count=5,
            duration_ms=5000,
        )

        assert log.operation_type == CustomerSyncLog.OperationType.BATCH_OPERATION
        assert log.status == CustomerSyncLog.StatusType.WARNING
        assert log.details["total_count"] == 100
        assert log.details["success_count"] == 95
        assert log.details["success_rate"] == 95.0

    def test_log_data_validation(self, sync_logger):
        """Тест логирования валидации данных"""
        validation_result = {
            "is_valid": False,
            "errors": ["Invalid email format", "Phone number too short"],
            "warnings": ["Missing tax_id"],
            "validated_fields": ["email", "phone", "tax_id"],
        }

        log = sync_logger.log_data_validation(
            customer_email="invalid@",
            onec_id="1C_INVALID",
            validation_result=validation_result,
            duration_ms=10,
        )

        assert log.operation_type == CustomerSyncLog.OperationType.DATA_VALIDATION
        assert log.status == CustomerSyncLog.StatusType.ERROR
        assert len(log.details["errors"]) == 2
        assert "Invalid email format" in log.error_message

    def test_correlation_id_consistency(self, test_user):
        """Тест согласованности correlation ID для связанных операций"""
        logger = CustomerSyncLogger()
        correlation_id = logger.correlation_id

        # Все логи должны иметь одинаковый correlation ID
        log1 = logger.log_sync_changes(test_user, {"email": "new@test.com"})
        log2 = logger.log_batch_operation("test", 10, 10, 0)

        assert log1.correlation_id == correlation_id
        assert log2.correlation_id == correlation_id
        assert log1.correlation_id == log2.correlation_id

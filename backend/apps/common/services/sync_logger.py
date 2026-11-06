"""
Специализированный логгер для синхронизации клиентов
"""

import logging
import uuid
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog

User = get_user_model()
logger = logging.getLogger(__name__)


class CustomerSyncLogger:
    """Специализированное логирование синхронизации клиентов"""

    def __init__(self, correlation_id: str | None = None):
        """
        Инициализация логгера с корреляционным ID.

        Args:
            correlation_id: Уникальный ID для группировки связанных операций
        """
        self.correlation_id = correlation_id or self._generate_correlation_id()

    @staticmethod
    def _generate_correlation_id() -> str:
        """Генерирует уникальный correlation ID"""
        return str(uuid.uuid4())

    def log_customer_import(
        self,
        customer_data: dict[str, Any],
        result: dict[str, Any],
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование импорта клиента из 1С.

        Args:
            customer_data: Данные клиента из 1С
            result: Результат операции импорта
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        success = result.get("success", False)
        customer = result.get("customer")

        details = {
            "source": "1c_export",
            "import_timestamp": timezone.now().isoformat(),
            "onec_customer_id": customer_data.get("id"),
            "customer_type": customer_data.get("customer_type"),
            "data_fields": list(customer_data.keys()),
        }

        if success and customer:
            details.update(
                {
                    "platform_customer_id": customer.id,
                    "assigned_role": customer.role,
                    "created_new": result.get("created", False),
                }
            )

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
            customer=customer if success else None,
            onec_id=customer_data.get("id", ""),
            status=(CustomerSyncLog.StatusType.SUCCESS if success else CustomerSyncLog.StatusType.ERROR),
            details=details,
            error_message=result.get("error_message", ""),
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_customer_export(
        self,
        platform_customer: Any,
        result: dict[str, Any],
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование экспорта клиента в 1С.

        Args:
            platform_customer: Объект User из платформы
            result: Результат операции экспорта
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        success = result.get("success", False)

        details = {
            "destination": "1c_api",
            "export_timestamp": timezone.now().isoformat(),
            "platform_customer_id": platform_customer.id,
            "customer_role": platform_customer.role,
            "export_format": result.get("export_format", "json"),
            "exported_fields": result.get("exported_fields", []),
        }

        if success:
            details.update(
                {
                    "assigned_1c_id": result.get("onec_id"),
                    "response_data": result.get("response_data", {}),
                }
            )

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
            customer=platform_customer,
            onec_id=result.get("onec_id", platform_customer.onec_id or ""),
            status=(CustomerSyncLog.StatusType.SUCCESS if success else CustomerSyncLog.StatusType.ERROR),
            details=details,
            error_message=result.get("error_message", ""),
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_customer_identification(
        self,
        onec_data: dict[str, Any],
        identification_result: dict[str, Any],
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование идентификации клиента (Story 3.2.1.5).

        Args:
            onec_data: Данные из 1С для идентификации
            identification_result: Результат операции идентификации
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        customer = identification_result.get("customer")
        found = identification_result.get("found", False)

        details = {
            "search_method": identification_result.get("method"),
            "search_value": identification_result.get("search_value"),
            "normalized_value": identification_result.get("normalized_value"),
            "found": found,
            "customer_id": customer.id if customer else None,
        }

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.CUSTOMER_IDENTIFICATION,
            customer=customer,
            onec_id=onec_data.get("onec_id", ""),
            status=(CustomerSyncLog.StatusType.SUCCESS if found else CustomerSyncLog.StatusType.SKIPPED),
            details=details,
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_conflict_resolution(
        self,
        existing_customer: Any,
        onec_data: dict[str, Any],
        conflict_source: str,
        resolution_result: dict[str, Any],
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование разрешения конфликтов (стратегия onec_wins).

        Args:
            existing_customer: Существующий объект User
            onec_data: Данные из 1С
            conflict_source: Источник конфликта ('portal_registration' или
                             'data_import')
            resolution_result: Результат операции разрешения
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        success = resolution_result.get("success", False)

        details = {
            "conflict_source": conflict_source,
            "resolution_strategy": "onec_wins",
            "conflicting_fields": resolution_result.get("conflicting_fields", []),
            "changes_made": resolution_result.get("changes_made", {}),
            "action": resolution_result.get("action"),
            "email_sent": resolution_result.get("email_sent", False),
            "sync_conflict_id": resolution_result.get("sync_conflict_id"),
        }

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.CONFLICT_RESOLUTION,
            customer=existing_customer,
            onec_id=onec_data.get("onec_id", ""),
            status=(CustomerSyncLog.StatusType.SUCCESS if success else CustomerSyncLog.StatusType.ERROR),
            details=details,
            error_message=resolution_result.get("error_message", ""),
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_sync_changes(
        self,
        customer: Any,
        changes: dict[str, Any],
        success: bool = True,
        error_message: str = "",
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование синхронизации изменений.

        Args:
            customer: Объект User
            changes: Словарь с изменениями
            success: Флаг успешности операции
            error_message: Сообщение об ошибке
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        details = {
            "changes": changes,
            "timestamp": timezone.now().isoformat(),
            "customer_id": customer.id,
        }

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.SYNC_CHANGES,
            customer=customer,
            onec_id=customer.onec_id or "",
            status=(CustomerSyncLog.StatusType.SUCCESS if success else CustomerSyncLog.StatusType.ERROR),
            details=details,
            error_message=error_message,
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_batch_operation(
        self,
        operation_name: str,
        total_count: int,
        success_count: int,
        error_count: int,
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование пакетной операции.

        Args:
            operation_name: Название операции
            total_count: Общее количество записей
            success_count: Количество успешных операций
            error_count: Количество ошибок
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        details = {
            "operation_name": operation_name,
            "total_count": total_count,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": (round(success_count / total_count * 100, 2) if total_count > 0 else 0),
            "timestamp": timezone.now().isoformat(),
        }

        status = CustomerSyncLog.StatusType.SUCCESS
        if error_count > 0:
            if success_count == 0:
                status = CustomerSyncLog.StatusType.ERROR
            else:
                status = CustomerSyncLog.StatusType.WARNING

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.BATCH_OPERATION,
            customer=None,
            onec_id="",
            status=status,
            details=details,
            error_message=(f"{error_count} ошибок из {total_count}" if error_count > 0 else ""),
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

    def log_data_validation(
        self,
        customer_email: str,
        onec_id: str,
        validation_result: dict[str, Any],
        duration_ms: int | None = None,
    ) -> CustomerSyncLog:
        """
        Логирование валидации данных.

        Args:
            customer_email: Email клиента
            onec_id: ID в 1С
            validation_result: Результат валидации
            duration_ms: Длительность операции в миллисекундах

        Returns:
            Созданная запись лога
        """
        is_valid = validation_result.get("is_valid", False)
        errors = validation_result.get("errors", [])

        details = {
            "validation_timestamp": timezone.now().isoformat(),
            "customer_email": customer_email,
            "is_valid": is_valid,
            "errors": errors,
            "warnings": validation_result.get("warnings", []),
            "validated_fields": validation_result.get("validated_fields", []),
        }

        return CustomerSyncLog.objects.create(
            operation_type=CustomerSyncLog.OperationType.DATA_VALIDATION,
            customer=None,
            onec_id=onec_id,
            status=(CustomerSyncLog.StatusType.SUCCESS if is_valid else CustomerSyncLog.StatusType.ERROR),
            details=details,
            error_message="; ".join(errors) if errors else "",
            duration_ms=duration_ms,
            correlation_id=self.correlation_id,
        )

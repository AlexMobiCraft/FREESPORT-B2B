"""
Integration тесты для системы логирования синхронизации
"""

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import RequestFactory
from django.utils import timezone

from apps.common.admin import CustomerSyncLogAdmin
from apps.common.models import CustomerSyncLog
from apps.common.services import CustomerSyncLogger, SyncReportGenerator

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestSyncLoggingSystem:
    """Integration тесты для полной системы логирования"""

    @pytest.fixture
    def test_user(self):
        """Создает тестового пользователя"""
        return User.objects.create_user(
            email="integration@test.com",
            password="testpass123",
        )

    @pytest.fixture
    def admin_user(self):
        """Создает админского пользователя"""
        return User.objects.create_superuser(
            email="admin@test.com",
            password="adminpass123",
        )

    @pytest.fixture
    def create_sync_logs(self, test_user):
        """Создает набор тестовых логов"""
        logger = CustomerSyncLogger()

        # Успешные импорты
        for i in range(5):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=test_user,
                onec_id=f"1C_IMPORT_{i}",
                duration_ms=100,
                correlation_id=logger.correlation_id,
            )

        # Ошибки экспорта
        for i in range(2):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=test_user,
                onec_id=f"1C_EXPORT_{i}",
                error_message="Connection failed",
                duration_ms=200,
                correlation_id=logger.correlation_id,
            )

        return logger.correlation_id

    def test_full_sync_logging_workflow(self, test_user):
        """Тест полного workflow логирования"""
        # 1. Создаем logger с correlation ID
        logger = CustomerSyncLogger()
        correlation_id = logger.correlation_id

        # 2. Логируем импорт
        import_result = {
            "success": True,
            "customer": test_user,
            "created": False,
        }
        import_log = logger.log_customer_import(
            {"id": "1C_WORKFLOW", "email": test_user.email},
            import_result,
            duration_ms=150,
        )

        # 3. Логируем идентификацию
        identification_result = {
            "found": True,
            "customer": test_user,
            "method": "email",
            "search_value": test_user.email,
        }
        identification_log = logger.log_customer_identification(
            {"email": test_user.email, "onec_id": "1C_WORKFLOW"},
            identification_result,
            duration_ms=50,
        )

        # 4. Логируем экспорт
        export_result = {
            "success": True,
            "onec_id": "1C_EXPORTED",
            "export_format": "json",
            "exported_fields": ["email"],
        }
        export_log = logger.log_customer_export(test_user, export_result, duration_ms=200)

        # Проверяем что все логи связаны через correlation ID
        assert import_log.correlation_id == correlation_id
        assert identification_log.correlation_id == correlation_id
        assert export_log.correlation_id == correlation_id

        # Проверяем что можем найти все логи по correlation ID
        related_logs = CustomerSyncLog.objects.filter(correlation_id=correlation_id)
        assert related_logs.count() == 3

    def test_django_admin_filters(self, create_sync_logs, admin_user):
        """Тест фильтров Django Admin"""
        request_factory = RequestFactory()
        request = request_factory.get("/admin/common/customersynclog/")
        request.user = admin_user

        admin_site = AdminSite()
        log_admin = CustomerSyncLogAdmin(CustomerSyncLog, admin_site)

        # Получаем queryset с фильтрами
        queryset = log_admin.get_queryset(request)

        assert queryset.count() == 7  # 5 успешных + 2 ошибки

        # Проверяем что можем фильтровать по operation_type
        import_logs = queryset.filter(operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C)
        assert import_logs.count() == 5

        # Проверяем фильтрацию по статусу
        error_logs = queryset.filter(status=CustomerSyncLog.StatusType.ERROR)
        assert error_logs.count() == 2

    def test_django_admin_export_csv(self, create_sync_logs, admin_user):
        """Тест экспорта в CSV через админку"""
        request_factory = RequestFactory()
        request = request_factory.get("/admin/common/customersynclog/")
        request.user = admin_user

        admin_site = AdminSite()
        log_admin = CustomerSyncLogAdmin(CustomerSyncLog, admin_site)

        queryset = CustomerSyncLog.objects.all()[:5]
        response = log_admin.export_to_csv(request, queryset)

        assert response.status_code == 200
        assert response["Content-Type"] == "text/csv; charset=utf-8-sig"
        assert b"sync_logs.csv" in response["Content-Disposition"].encode()

    def test_generate_sync_report_command(self, create_sync_logs):
        """Тест management команды generate_sync_report"""
        out = StringIO()

        call_command(
            "generate_sync_report",
            "--type=daily",
            "--no-send",
            stdout=out,
        )

        output = out.getvalue()
        assert "Всего операций: 7" in output
        assert "Успешных: 5" in output

    def test_cleanup_sync_logs_command(self, test_user):
        """Тест management команды cleanup_sync_logs"""
        # Создаем старые логи
        old_date = timezone.now() - timedelta(days=100)
        for i in range(3):
            log = CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=test_user,
                onec_id=f"1C_OLD_{i}",
                correlation_id=uuid.uuid4(),
            )
            # Принудительно устанавливаем старую дату
            CustomerSyncLog.objects.filter(pk=log.pk).update(created_at=old_date)

        # Создаем свежие логи
        for i in range(2):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=test_user,
                onec_id=f"1C_NEW_{i}",
                correlation_id=uuid.uuid4(),
            )

        assert CustomerSyncLog.objects.count() == 5

        # Запускаем очистку с retention 90 дней
        out = StringIO()
        call_command(
            "cleanup_sync_logs",
            "--days=90",
            "--force",
            stdout=out,
        )

        # Старые логи должны быть удалены
        assert CustomerSyncLog.objects.count() == 2
        assert CustomerSyncLog.objects.filter(operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C).count() == 2

    def test_report_generation_with_real_data(self, create_sync_logs):
        """Тест генерации отчета с реальными данными"""
        generator = SyncReportGenerator()
        today = timezone.now().date()

        # Генерируем ежедневный отчет
        daily_report = generator.generate_daily_summary(today)

        assert daily_report["total_operations"] == 7
        assert daily_report["success_count"] == 5
        assert daily_report["success_rate"] > 70

        # Генерируем еженедельный анализ ошибок
        weekly_report = generator.generate_weekly_error_analysis(today)

        assert weekly_report["total_errors"] == 2
        assert len(weekly_report["common_errors"]) > 0

    def test_correlation_id_tracking(self, test_user):
        """Тест отслеживания связанных операций через correlation ID"""
        logger = CustomerSyncLogger()

        # Создаем цепочку операций
        logger.log_customer_import(
            {"id": "1C_CHAIN", "email": "chain@test.com"},
            {"success": True, "customer": test_user},
        )
        logger.log_customer_identification(
            {"email": "chain@test.com", "onec_id": "1C_CHAIN"},
            {"found": True, "customer": test_user, "method": "email"},
        )
        logger.log_customer_export(
            test_user,
            {"success": True, "onec_id": "1C_EXPORTED"},
        )

        # Все операции должны иметь одинаковый correlation ID
        chain_logs = CustomerSyncLog.objects.filter(correlation_id=logger.correlation_id)
        assert chain_logs.count() == 3

        # Проверяем хронологию
        logs_list = list(chain_logs.order_by("created_at"))
        assert logs_list[0].operation_type == CustomerSyncLog.OperationType.IMPORT_FROM_1C  # noqa
        assert logs_list[1].operation_type == CustomerSyncLog.OperationType.CUSTOMER_IDENTIFICATION  # noqa
        assert logs_list[2].operation_type == CustomerSyncLog.OperationType.EXPORT_TO_1C  # noqa

    def test_error_aggregation_and_reporting(self, test_user):
        """Тест агрегации ошибок и генерации отчета"""
        # Создаем множество ошибок одного типа
        for i in range(10):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=test_user,
                onec_id=f"1C_ERROR_{i}",
                error_message="Connection timeout to 1C API",
                correlation_id=uuid.uuid4(),
            )

        generator = SyncReportGenerator()
        today = timezone.now().date()

        # Генерируем отчет по ошибкам
        weekly_report = generator.generate_weekly_error_analysis(today)

        assert weekly_report["total_errors"] >= 10

        # Проверяем что частые ошибки правильно идентифицированы
        common_errors = weekly_report["common_errors"]
        assert len(common_errors) > 0
        assert "Connection timeout" in common_errors[0]["message"]

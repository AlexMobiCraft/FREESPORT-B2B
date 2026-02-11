"""
Unit тесты для SyncReportGenerator
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.common.services import SyncReportGenerator

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestSyncReportGenerator:
    """Тесты для SyncReportGenerator"""

    @pytest.fixture
    def generator(self):
        """Фикстура для создания генератора отчетов"""
        return SyncReportGenerator()

    @pytest.fixture
    def test_user(self):
        """Фикстура для создания тестового пользователя"""
        return User.objects.create_user(
            email="test@example.com",
            password="testpass123",
        )

    @pytest.fixture
    def create_test_logs(self, test_user):
        """Создает тестовые логи для отчетов"""
        today = timezone.now().date()

        # Успешные операции
        for i in range(10):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.SUCCESS,
                customer=test_user,
                onec_id=f"1C_SUCCESS_{i}",
                duration_ms=100 + i * 10,
                correlation_id=uuid.uuid4(),
                created_at=timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
            )

        # Ошибочные операции
        for i in range(5):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=test_user,
                onec_id=f"1C_ERROR_{i}",
                duration_ms=50 + i * 5,
                error_message="Connection failed",
                correlation_id=uuid.uuid4(),
                created_at=timezone.make_aware(timezone.datetime.combine(today, timezone.datetime.min.time())),
            )

    def test_generate_daily_summary_structure(self, generator, create_test_logs):
        """Тест структуры ежедневного отчета"""
        today = timezone.now().date()
        report = generator.generate_daily_summary(today)

        assert "date" in report
        assert "total_operations" in report
        assert "by_type" in report
        assert "by_status" in report
        assert "avg_duration_ms" in report
        assert "top_errors" in report
        assert "success_count" in report
        assert "success_rate" in report

    def test_generate_daily_summary_counts(self, generator, create_test_logs):
        """Тест подсчетов в ежедневном отчете"""
        today = timezone.now().date()
        report = generator.generate_daily_summary(today)

        assert report["total_operations"] == 15  # 10 успешных + 5 ошибок
        assert report["success_count"] == 10
        assert report["error_count"] == 5

    def test_generate_daily_summary_no_data(self, generator):
        """Тест отчета при отсутствии данных"""
        future_date = timezone.now().date() + timedelta(days=365)
        report = generator.generate_daily_summary(future_date)

        assert report["total_operations"] == 0
        assert report["success_rate"] == 0
        assert report["avg_duration_ms"] == 0

    def test_generate_weekly_error_analysis_structure(self, generator, create_test_logs):
        """Тест структуры еженедельного анализа ошибок"""
        start_date = timezone.now().date() - timedelta(days=7)
        report = generator.generate_weekly_error_analysis(start_date)

        assert "period" in report
        assert "total_errors" in report
        assert "error_rate" in report
        assert "errors_by_type" in report
        assert "common_errors" in report
        assert "affected_customers" in report

    def test_generate_weekly_error_analysis_counts(self, generator, create_test_logs):
        """Тест подсчетов в еженедельном анализе"""
        today = timezone.now().date()
        report = generator.generate_weekly_error_analysis(today)

        assert report["total_errors"] == 5
        assert len(report["common_errors"]) > 0

    def test_analyze_common_errors(self, generator, test_user):
        """Тест анализа частых ошибок"""
        # Создаем логи с разными ошибками
        for i in range(5):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.IMPORT_FROM_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=test_user,
                onec_id=f"1C_{i}",
                error_message="Duplicate email detected",
                correlation_id=uuid.uuid4(),
            )

        for i in range(3):
            CustomerSyncLog.objects.create(
                operation_type=CustomerSyncLog.OperationType.EXPORT_TO_1C,
                status=CustomerSyncLog.StatusType.ERROR,
                customer=test_user,
                onec_id=f"1C_{i}",
                error_message="Connection timeout",
                correlation_id=uuid.uuid4(),
            )

        error_logs = CustomerSyncLog.objects.filter(status=CustomerSyncLog.StatusType.ERROR)
        common_errors = generator._analyze_common_errors(error_logs)

        assert len(common_errors) > 0
        # Самая частая ошибка должна быть первой
        assert common_errors[0]["count"] >= common_errors[-1]["count"]

    @patch("apps.common.services.reporting.send_mail")
    def test_send_daily_report_success(self, mock_send_mail, generator, create_test_logs):
        """Тест успешной отправки ежедневного отчета"""
        recipients = ["admin@example.com"]
        result = generator.send_daily_report(recipients)

        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args.kwargs
        assert "admin@example.com" in call_kwargs["recipient_list"]
        assert "Ежедневный отчет" in call_kwargs["subject"]

    @patch("apps.common.services.reporting.send_mail")
    def test_send_daily_report_failure(self, mock_send_mail, generator):
        """Тест обработки ошибки при отправке отчета"""
        mock_send_mail.side_effect = Exception("SMTP error")
        recipients = ["admin@example.com"]

        result = generator.send_daily_report(recipients)

        assert result is False

    @patch("apps.common.services.reporting.send_mail")
    def test_send_weekly_error_report(self, mock_send_mail, generator, create_test_logs):
        """Тест отправки еженедельного отчета"""
        recipients = ["admin@example.com", "manager@example.com"]
        result = generator.send_weekly_error_report(recipients)

        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args.kwargs
        assert len(call_kwargs["recipient_list"]) == 2

    def test_format_daily_report_text(self, generator, create_test_logs):
        """Тест форматирования текстового отчета"""
        today = timezone.now().date()
        report = generator.generate_daily_summary(today)
        text = generator._format_daily_report_text(report)

        assert "Ежедневный отчет" in text
        assert str(today) in text
        assert "Всего операций" in text
        assert "Успешных" in text

    def test_format_weekly_report_text(self, generator, create_test_logs):
        """Тест форматирования еженедельного текстового отчета"""
        start_date = timezone.now().date()
        report = generator.generate_weekly_error_analysis(start_date)
        text = generator._format_weekly_report_text(report)

        assert "Еженедельный анализ" in text
        assert "Период" in text
        assert "Ошибок" in text

"""
Unit тесты для Celery email tasks (Story 29.4).

Тестирует:
- Отправку email админам при B2B регистрации
- Отправку email пользователю о pending статусе
- Обработку несуществующих пользователей
- Retry логику при SMTP ошибках
"""

from smtplib import SMTPException
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone

from apps.users.models import User
from apps.users.tasks import monitor_pending_verification_queue, send_admin_verification_email, send_user_pending_email
from tests.factories import UserFactory


@pytest.fixture
def verification_recipient(db):
    """Fixture to create a notification recipient for B2B verification."""
    from apps.common.models import NotificationRecipient

    return NotificationRecipient.objects.create(
        email="admin@example.com",
        name="Admin",
        is_active=True,
        notify_user_verification=True,
        notify_pending_queue=True,
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestSendAdminVerificationEmail:
    """Unit тесты для send_admin_verification_email task."""

    @patch("apps.users.tasks.send_mail")
    def test_send_admin_verification_email_success(self, mock_send_mail, settings, verification_recipient):
        """Успешная отправка email админу при B2B регистрации."""
        # Настраиваем ADMINS (хотя теперь используется NotificationRecipient)
        settings.ADMINS = [("Admin", "admin@example.com")]
        settings.SITE_URL = "http://localhost:3000"

        # Создаем B2B пользователя
        user = UserFactory(
            role="wholesale_level1",
            company_name="Test Company",
            email="b2b@example.com",
            first_name="Иван",
            last_name="Петров",
        )

        result = send_admin_verification_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()

        # Проверяем параметры вызова
        call_kwargs = mock_send_mail.call_args
        assert "Test Company" in call_kwargs.kwargs["subject"]
        assert "admin@example.com" in call_kwargs.kwargs["recipient_list"]
        assert call_kwargs.kwargs["html_message"] is not None

    @patch("apps.users.tasks.send_mail")
    def test_send_admin_email_no_admins_configured(self, mock_send_mail, settings):
        """Пропуск отправки если нет получателей в БД."""
        # Очищаем получателей (в этом тесте нам не нужен verification_recipient)
        from apps.common.models import NotificationRecipient

        NotificationRecipient.objects.all().delete()

        user = UserFactory(role="trainer", company_name="Fitness Club")

        result = send_admin_verification_email(user.id)

        assert result is False
        mock_send_mail.assert_not_called()

    def test_send_admin_email_user_not_found(self):
        """Обработка несуществующего пользователя."""
        result = send_admin_verification_email(99999)

        assert result is False

    @patch("apps.users.tasks.send_mail")
    def test_send_admin_email_with_tax_id(self, mock_send_mail, settings, verification_recipient):
        """Email с ИНН для wholesale пользователей."""
        settings.ADMINS = [("Admin", "admin@test.com")]
        settings.SITE_URL = "http://localhost"

        user = UserFactory(
            role="wholesale_level2",
            company_name="ООО Тест",
            tax_id="1234567890",
            email="wholesale@test.com",
        )

        result = send_admin_verification_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
class TestSendUserPendingEmail:
    """Unit тесты для send_user_pending_email task."""

    @patch("apps.users.tasks.send_mail")
    def test_send_user_pending_email_success(self, mock_send_mail):
        """Успешная отправка pending email пользователю."""
        user = UserFactory(
            first_name="Алексей",
            email="user@example.com",
            role="trainer",
            company_name="Sport Club",
        )

        result = send_user_pending_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()

        call_kwargs = mock_send_mail.call_args
        assert user.email in call_kwargs.kwargs["recipient_list"]
        assert "[FREESPORT]" in call_kwargs.kwargs["subject"]

    def test_send_user_email_user_not_found(self):
        """Обработка несуществующего пользователя."""
        result = send_user_pending_email(99999)

        assert result is False

    @patch("apps.users.tasks.send_mail")
    def test_send_user_email_federation_rep(self, mock_send_mail):
        """Email для представителя федерации."""
        user = UserFactory(
            role="federation_rep",
            company_name="Федерация тенниса",
            email="federation@test.com",
        )

        result = send_user_pending_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()


@pytest.mark.unit
@pytest.mark.django_db
class TestMonitorPendingVerificationQueue:
    """Unit тесты для monitor_pending_verification_queue task."""

    @patch("apps.users.tasks.send_mail")
    def test_no_alert_below_threshold(self, mock_send_mail, settings):
        """Нет alert если pending < threshold."""
        settings.ADMINS = [("Admin", "admin@test.com")]

        # Создаем 5 pending пользователей (ниже threshold=10)
        for i in range(5):
            UserFactory(
                role="trainer",
                verification_status="pending",
                email=f"user{i}@test.com",
            )

        result = monitor_pending_verification_queue()

        assert result["pending_count"] == 5
        assert result["alert_sent"] is False
        mock_send_mail.assert_not_called()

    @patch("apps.users.tasks.send_mail")
    def test_alert_above_threshold(self, mock_send_mail, settings, verification_recipient):
        """Alert отправляется если pending > threshold."""
        settings.ADMINS = [("Admin", "admin@test.com")]

        # Создаем 11 pending пользователей (выше threshold=10)
        for i in range(11):
            UserFactory(
                role="wholesale_level1",
                verification_status="pending",
                email=f"pending{i}@test.com",
            )

        result = monitor_pending_verification_queue()

        assert result["pending_count"] == 11
        assert result["alert_sent"] is True
        mock_send_mail.assert_called_once()

        # Проверяем subject содержит количество
        call_kwargs = mock_send_mail.call_args
        assert "11" in call_kwargs.kwargs["subject"]

    @patch("apps.users.tasks.send_mail")
    def test_no_alert_if_no_admins(self, mock_send_mail, settings):
        """Нет alert если нет получателей в БД."""
        from apps.common.models import NotificationRecipient

        NotificationRecipient.objects.all().delete()

        for i in range(15):
            UserFactory(
                role="trainer",
                verification_status="pending",
                email=f"noadmin{i}@test.com",
            )

        result = monitor_pending_verification_queue()

        assert result["pending_count"] == 15
        assert result["alert_sent"] is False
        mock_send_mail.assert_not_called()


@pytest.mark.unit
@pytest.mark.django_db
class TestEmailRetryLogic:
    """Тесты для retry логики при SMTP ошибках."""

    @patch("apps.users.tasks.send_mail")
    def test_smtp_error_triggers_retry(self, mock_send_mail, settings, verification_recipient):
        """SMTP ошибка должна вызывать retry."""
        settings.ADMINS = [("Admin", "admin@test.com")]
        settings.SITE_URL = "http://localhost"

        mock_send_mail.side_effect = SMTPException("Connection refused")

        user = UserFactory(role="trainer", company_name="Test Club")

        # Task должен поднять исключение для retry
        with pytest.raises(Exception):
            # Вызываем task напрямую (без .delay) для тестирования
            send_admin_verification_email(user.id)
        """SMTP ошибка должна вызывать retry."""
        settings.ADMINS = [("Admin", "admin@test.com")]
        settings.SITE_URL = "http://localhost"

        mock_send_mail.side_effect = SMTPException("Connection refused")

        user = UserFactory(role="trainer", company_name="Test Club")

        # Task должен поднять исключение для retry
        with pytest.raises(Exception):
            # Вызываем task напрямую (без .delay) для тестирования
            send_admin_verification_email(user.id)

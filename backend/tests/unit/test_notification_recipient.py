"""
Unit тесты для модели NotificationRecipient и Celery tasks уведомлений о заказах.

Тестирует:
- Создание и фильтрацию получателей уведомлений
- Отправку email о новых заказах
- Интеграцию с существующими tasks (user_verification, pending_queue)
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ValidationError

from apps.common.models import NotificationRecipient
from apps.orders.tasks import send_order_notification_email


@pytest.fixture
def notification_recipient(db):
    """Фикстура для создания тестового получателя уведомлений."""
    return NotificationRecipient.objects.create(
        email="admin@freesport.ru",
        name="Admin",
        is_active=True,
        notify_new_orders=True,
        notify_order_cancelled=False,
        notify_user_verification=True,
        notify_pending_queue=True,
        notify_low_stock=False,
        notify_daily_summary=False,
    )


@pytest.fixture
def inactive_recipient(db):
    """Фикстура для неактивного получателя."""
    return NotificationRecipient.objects.create(
        email="inactive@freesport.ru",
        name="Inactive Admin",
        is_active=False,
        notify_new_orders=True,
    )


@pytest.mark.unit
@pytest.mark.django_db
class TestNotificationRecipientModel:
    """Unit тесты для модели NotificationRecipient."""

    def test_create_recipient_with_all_flags(self, notification_recipient):
        """Тест создания получателя со всеми флагами."""
        assert notification_recipient.email == "admin@freesport.ru"
        assert notification_recipient.name == "Admin"
        assert notification_recipient.is_active is True
        assert notification_recipient.notify_new_orders is True
        assert notification_recipient.notify_user_verification is True
        assert notification_recipient.notify_pending_queue is True
        assert notification_recipient.notify_low_stock is False

    def test_email_must_be_unique(self, notification_recipient):
        """Тест уникальности email."""
        with pytest.raises(Exception):  # IntegrityError
            NotificationRecipient.objects.create(
                email="admin@freesport.ru",
                name="Another Admin",
            )

    def test_email_normalized_to_lowercase(self, db):
        """Тест нормализации email в нижний регистр."""
        recipient = NotificationRecipient(
            email="ADMIN@FREESPORT.RU",
            name="Caps Admin",
        )
        recipient.clean()
        assert recipient.email == "admin@freesport.ru"

    def test_str_representation_with_name(self, notification_recipient):
        """Тест строкового представления с именем."""
        assert str(notification_recipient) == "Admin <admin@freesport.ru>"

    def test_str_representation_without_name(self, db):
        """Тест строкового представления без имени."""
        recipient = NotificationRecipient.objects.create(
            email="noname@freesport.ru",
            is_active=True,
        )
        assert str(recipient) == "noname@freesport.ru"

    def test_default_values(self, db):
        """Тест значений по умолчанию."""
        recipient = NotificationRecipient.objects.create(
            email="default@freesport.ru",
        )
        assert recipient.is_active is True
        assert recipient.notify_new_orders is False
        assert recipient.notify_order_cancelled is False
        assert recipient.notify_user_verification is False
        assert recipient.notify_pending_queue is False
        assert recipient.notify_low_stock is False
        assert recipient.notify_daily_summary is False

    def test_filter_by_notification_type(self, notification_recipient, inactive_recipient):
        """Тест фильтрации по типу уведомления."""
        # Только активные получатели с notify_new_orders
        active_order_recipients = NotificationRecipient.objects.filter(
            is_active=True,
            notify_new_orders=True,
        )
        assert active_order_recipients.count() == 1
        assert active_order_recipients.first() == notification_recipient

    def test_filter_by_verification_type(self, notification_recipient):
        """Тест фильтрации по типу верификации."""
        verification_recipients = NotificationRecipient.objects.filter(
            is_active=True,
            notify_user_verification=True,
        )
        assert verification_recipients.count() == 1


@pytest.mark.unit
@pytest.mark.django_db
class TestSendOrderNotificationEmail:
    """Unit тесты для send_order_notification_email task."""

    @pytest.fixture
    def order(self, db):
        """Фикстура для создания тестового заказа."""
        from apps.orders.models import Order
        from tests.factories import UserFactory

        user = UserFactory()
        order = Order.objects.create(
            user=user,
            customer_name="Test Customer",
            customer_email="customer@test.com",
            customer_phone="+79001234567",
            delivery_address="Test Address",
            delivery_method="courier",
            total_amount=Decimal("1000.00"),
        )
        return order

    @patch("apps.orders.tasks.send_mail")
    def test_send_order_notification_success(self, mock_send_mail, notification_recipient, order):
        """Успешная отправка уведомления о заказе."""
        result = send_order_notification_email(order.id)

        assert result is True
        mock_send_mail.assert_called_once()

        call_kwargs = mock_send_mail.call_args
        assert order.order_number in call_kwargs.kwargs["subject"]
        assert notification_recipient.email in call_kwargs.kwargs["recipient_list"]

    @patch("apps.orders.tasks.send_mail")
    def test_skip_when_no_recipients(self, mock_send_mail, order):
        """Пропуск отправки если нет активных получателей."""
        # Удаляем всех получателей
        NotificationRecipient.objects.all().delete()

        result = send_order_notification_email(order.id)

        assert result is False
        mock_send_mail.assert_not_called()

    @patch("apps.orders.tasks.send_mail")
    def test_skip_inactive_recipients(self, mock_send_mail, inactive_recipient, order):
        """Неактивные получатели не получают уведомления."""
        result = send_order_notification_email(order.id)

        assert result is False
        mock_send_mail.assert_not_called()

    def test_order_not_found(self):
        """Обработка несуществующего заказа."""
        result = send_order_notification_email(99999)
        assert result is False

    @patch("apps.orders.tasks.send_mail")
    def test_multiple_recipients(self, mock_send_mail, notification_recipient, order, db):
        """Отправка нескольким получателям."""
        # Создаём второго получателя
        NotificationRecipient.objects.create(
            email="admin2@freesport.ru",
            name="Admin 2",
            is_active=True,
            notify_new_orders=True,
        )

        result = send_order_notification_email(order.id)

        assert result is True
        mock_send_mail.assert_called_once()

        call_kwargs = mock_send_mail.call_args
        recipient_list = call_kwargs.kwargs["recipient_list"]
        assert len(recipient_list) == 2
        assert "admin@freesport.ru" in recipient_list
        assert "admin2@freesport.ru" in recipient_list


@pytest.mark.unit
@pytest.mark.django_db
class TestMigratedUserVerificationTasks:
    """Тесты для мигрированных tasks user_verification на NotificationRecipient."""

    @patch("apps.users.tasks.send_mail")
    def test_send_admin_verification_uses_notification_recipient(
        self, mock_send_mail, notification_recipient, settings
    ):
        """
        Проверка что send_admin_verification_email использует NotificationRecipient.
        """
        from apps.users.tasks import send_admin_verification_email
        from tests.factories import UserFactory

        settings.SITE_URL = "http://localhost:3000"

        user = UserFactory(
            role="wholesale_level1",
            company_name="Test Company",
        )

        result = send_admin_verification_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()

        call_kwargs = mock_send_mail.call_args
        assert notification_recipient.email in call_kwargs.kwargs["recipient_list"]

    @patch("apps.users.tasks.send_mail")
    def test_monitor_pending_queue_uses_notification_recipient(self, mock_send_mail, db):
        """
        Проверка что monitor_pending_verification_queue
        использует NotificationRecipient.

        Этот тест проверяет, что функция monitor_pending_verification_queue
        использует NotificationRecipient для отправки уведомлений.
        """
        from apps.users.tasks import monitor_pending_verification_queue
        from tests.factories import UserFactory

        # Создаём получателя для pending_queue alerts
        NotificationRecipient.objects.create(
            email="alerts@freesport.ru",
            is_active=True,
            notify_pending_queue=True,
        )

        # Создаём 11 pending пользователей (выше threshold=10)
        for i in range(11):
            UserFactory(
                role="trainer",
                verification_status="pending",
                email=f"pending{i}@test.com",
            )

        result = monitor_pending_verification_queue()

        assert result["pending_count"] == 11
        assert result["alert_sent"] is True
        mock_send_mail.assert_called_once()

        call_kwargs = mock_send_mail.call_args
        assert "alerts@freesport.ru" in call_kwargs.kwargs["recipient_list"]

"""
Тесты алерта о заказах, которые 1С не забирает (`alert_orders_stuck_in_1c`).

Покрывают матрицу стори 1c-orders-pull-schedule-and-stuck-alert: зависший заказ,
повторный запуск, новый заказ в наборе, напоминание, сброс состояния, исключения
из выборки, отсутствие получателей, сбой SMTP, регистрацию в beat и флаг в админке.
"""

import logging
from datetime import timedelta
from decimal import Decimal
from smtplib import SMTPException
from unittest.mock import patch

import pytest
from django.conf import settings
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.utils import timezone

from apps.common.admin import NotificationRecipientAdmin
from apps.common.models import NotificationRecipient
from apps.orders.models import Order
from apps.orders.tasks import _STUCK_ALERT_CACHE_KEY, alert_orders_stuck_in_1c

pytestmark = [pytest.mark.unit, pytest.mark.django_db]


@pytest.fixture(autouse=True)
def isolated_state():
    """Письма о новом заказе — без брокера Celery; состояние алерта — чистое."""
    cache.delete(_STUCK_ALERT_CACHE_KEY)
    with (
        patch("apps.orders.tasks.send_order_confirmation_to_customer"),
        patch("apps.orders.tasks.send_order_notification_email"),
    ):
        yield
    cache.delete(_STUCK_ALERT_CACHE_KEY)


@pytest.fixture
def recipient():
    return NotificationRecipient.objects.create(email="ops@optisport.ru", is_active=True, notify_exchange_alerts=True)


def make_order(age_minutes: int = 60, **extra) -> Order:
    """Создаёт заказ нужного возраста (по умолчанию — зависший субзаказ)."""
    defaults = {
        "user": None,
        "total_amount": Decimal("100.00"),
        "delivery_address": "Адрес",
        "delivery_method": "courier",
        "payment_method": "card",
        "is_master": False,
        "sent_to_1c": False,
        "export_skipped": False,
    }
    defaults.update(extra)
    if not defaults["is_master"] and "parent_order" not in defaults:
        # 1С получает только субзаказы, привязанные к мастер-заказу
        defaults["parent_order"] = Order.objects.create(
            user=None,
            total_amount=Decimal("100.00"),
            delivery_address="Адрес",
            delivery_method="courier",
            payment_method="card",
            is_master=True,
        )
    order = Order.objects.create(**defaults)
    # created_at — auto_now_add, поэтому возраст задаём обновлением
    Order.objects.filter(pk=order.pk).update(created_at=timezone.now() - timedelta(minutes=age_minutes))
    order.refresh_from_db()
    return order


class TestStuckOrdersAlert:
    def test_stuck_order_sends_one_email_with_number_and_age(self, recipient):
        order = make_order(age_minutes=65)

        result = alert_orders_stuck_in_1c()

        assert result == {"stuck": 1, "sent": True}
        assert len(mail.outbox) == 1
        message = mail.outbox[0]
        assert message.to == ["ops@optisport.ru"]
        assert order.order_number in message.body
        assert "1 ч 05 мин" in message.body

    def test_same_set_does_not_resend(self, recipient):
        make_order()
        alert_orders_stuck_in_1c()

        result = alert_orders_stuck_in_1c()

        assert result["sent"] is False
        assert len(mail.outbox) == 1

    def test_new_stuck_order_sends_full_list(self, recipient):
        first = make_order()
        alert_orders_stuck_in_1c()
        second = make_order()

        result = alert_orders_stuck_in_1c()

        assert result == {"stuck": 2, "sent": True}
        assert len(mail.outbox) == 2
        assert first.order_number in mail.outbox[1].body
        assert second.order_number in mail.outbox[1].body

    def test_reminder_after_repeat_interval(self, recipient):
        make_order()
        alert_orders_stuck_in_1c()
        state = cache.get(_STUCK_ALERT_CACHE_KEY)
        state["sent_at"] = (timezone.now() - timedelta(hours=6, minutes=1)).isoformat()
        cache.set(_STUCK_ALERT_CACHE_KEY, state)

        result = alert_orders_stuck_in_1c()

        assert result["sent"] is True
        assert len(mail.outbox) == 2

    def test_no_reminder_before_repeat_interval(self, recipient):
        make_order()
        alert_orders_stuck_in_1c()
        state = cache.get(_STUCK_ALERT_CACHE_KEY)
        state["sent_at"] = (timezone.now() - timedelta(hours=5, minutes=50)).isoformat()
        cache.set(_STUCK_ALERT_CACHE_KEY, state)

        assert alert_orders_stuck_in_1c()["sent"] is False
        assert len(mail.outbox) == 1

    def test_state_reset_when_everything_delivered(self, recipient):
        order = make_order()
        alert_orders_stuck_in_1c()
        Order.objects.filter(pk=order.pk).update(sent_to_1c=True)

        result = alert_orders_stuck_in_1c()

        assert result == {"stuck": 0, "sent": False}
        assert cache.get(_STUCK_ALERT_CACHE_KEY) is None
        # следующий инцидент — сразу письмо
        make_order()
        assert alert_orders_stuck_in_1c()["sent"] is True
        assert len(mail.outbox) == 2

    def test_shrunk_set_does_not_resend(self, recipient):
        keep = make_order()
        gone = make_order()
        alert_orders_stuck_in_1c()
        Order.objects.filter(pk=gone.pk).update(sent_to_1c=True)

        result = alert_orders_stuck_in_1c()

        assert result == {"stuck": 1, "sent": False}
        assert cache.get(_STUCK_ALERT_CACHE_KEY)["ids"] == [keep.pk]

    @pytest.mark.parametrize(
        "extra, age",
        [
            ({"is_master": True}, 60),
            ({"export_skipped": True}, 60),
            ({"sent_to_1c": True}, 60),
            ({}, 5),
        ],
        ids=["master", "export_skipped", "sent", "younger_than_threshold"],
    )
    def test_excluded_orders_are_ignored(self, recipient, extra, age):
        make_order(age_minutes=age, **extra)

        result = alert_orders_stuck_in_1c()

        assert result == {"stuck": 0, "sent": False}
        assert mail.outbox == []

    @override_settings(ADMINS=[])
    def test_no_recipients_logs_error_and_keeps_state_empty(self, caplog):
        make_order()

        with caplog.at_level(logging.ERROR, logger="apps.orders.tasks"):
            result = alert_orders_stuck_in_1c()

        assert result["sent"] is False
        assert mail.outbox == []
        assert cache.get(_STUCK_ALERT_CACHE_KEY) is None
        assert any(r.levelno == logging.ERROR for r in caplog.records)

    @override_settings(ADMINS=[("Admin", "admin@optisport.ru")])
    def test_falls_back_to_settings_admins(self):
        make_order()

        assert alert_orders_stuck_in_1c()["sent"] is True
        assert mail.outbox[0].to == ["admin@optisport.ru"]

    def test_inactive_recipient_is_skipped(self):
        NotificationRecipient.objects.create(email="off@optisport.ru", is_active=False, notify_exchange_alerts=True)
        make_order()

        with override_settings(ADMINS=[]):
            assert alert_orders_stuck_in_1c()["sent"] is False

    def test_smtp_failure_does_not_write_state(self, recipient):
        make_order()

        with patch("apps.orders.tasks.send_mail", side_effect=SMTPException("boom")):
            with pytest.raises(SMTPException):
                alert_orders_stuck_in_1c.run()

        assert cache.get(_STUCK_ALERT_CACHE_KEY) is None


class TestStuckAlertWiring:
    def test_registered_in_beat_every_10_minutes(self):
        entry = settings.CELERY_BEAT_SCHEDULE["alert-orders-stuck-in-1c"]

        assert entry["task"] == "apps.orders.tasks.alert_orders_stuck_in_1c"
        assert entry["schedule"] == 600

    def test_default_thresholds(self):
        assert settings.ORDERS_STUCK_ALERT_THRESHOLD_MINUTES == 30
        assert settings.ORDERS_STUCK_ALERT_REPEAT_HOURS == 6

    def test_flag_default_false_and_in_admin(self):
        recipient = NotificationRecipient.objects.create(email="x@optisport.ru")
        assert recipient.notify_exchange_alerts is False
        assert "notify_exchange_alerts" in NotificationRecipientAdmin.list_editable
        fields = [f for _title, opts in NotificationRecipientAdmin.fieldsets for f in opts["fields"]]
        assert "notify_exchange_alerts" in fields

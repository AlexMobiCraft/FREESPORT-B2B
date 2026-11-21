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
        email="admin@optisport.ru",
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
        email="inactive@optisport.ru",
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
        assert notification_recipient.email == "admin@optisport.ru"
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
                email="admin@optisport.ru",
                name="Another Admin",
            )

    def test_email_normalized_to_lowercase(self, db):
        """Тест нормализации email в нижний регистр."""
        recipient = NotificationRecipient(
            email="ADMIN@OPTISPORT.RU",
            name="Caps Admin",
        )
        recipient.clean()
        assert recipient.email == "admin@optisport.ru"

    def test_str_representation_with_name(self, notification_recipient):
        """Тест строкового представления с именем."""
        assert str(notification_recipient) == "Admin <admin@optisport.ru>"

    def test_str_representation_without_name(self, db):
        """Тест строкового представления без имени."""
        recipient = NotificationRecipient.objects.create(
            email="noname@optisport.ru",
            is_active=True,
        )
        assert str(recipient) == "noname@optisport.ru"

    def test_default_values(self, db):
        """Тест значений по умолчанию."""
        recipient = NotificationRecipient.objects.create(
            email="default@optisport.ru",
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
            email="admin2@optisport.ru",
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
        assert "admin@optisport.ru" in recipient_list
        assert "admin2@optisport.ru" in recipient_list

    @patch("apps.orders.tasks.send_mail")
    def test_supervisor_gets_manager_section_link(self, mock_send_mail, notification_recipient, order, settings):
        """Руководитель получает ссылку на заказ в /manager/: /admin/ его не пускает."""
        from django.contrib.auth.models import Group

        from apps.users.staff_roles import SUPERVISORS_GROUP
        from tests.factories import UserFactory

        settings.SITE_URL = "https://optisport.ru"
        supervisor = UserFactory(email="boss@optisport.ru", is_staff=True)
        supervisor.groups.add(Group.objects.get_or_create(name=SUPERVISORS_GROUP)[0])
        NotificationRecipient.objects.create(email="boss@optisport.ru", name="Boss", notify_new_orders=True)

        assert send_order_notification_email(order.id) is True

        assert mock_send_mail.call_count == 2
        by_recipients = {tuple(call.kwargs["recipient_list"]): call.kwargs for call in mock_send_mail.call_args_list}
        admin_mail = by_recipients[(notification_recipient.email,)]
        manager_mail = by_recipients[("boss@optisport.ru",)]
        for part in ("message", "html_message"):
            assert f"https://optisport.ru/admin/orders/order/{order.id}/change/" in admin_mail[part]
            assert f"https://optisport.ru/manager/orders/order/{order.id}/change/" in manager_mail[part]


@pytest.mark.unit
@pytest.mark.django_db
class TestOrderNotificationResponsibleManager:
    """CAP-3 и CAP-4: письмо о новом заказе получает ответственный менеджер клиента."""

    GENERAL_EMAIL = "general@optisport.ru"

    @pytest.fixture(autouse=True)
    def _site_url(self, settings):
        settings.SITE_URL = "https://optisport.ru"

    @pytest.fixture
    def general(self, db):
        """Общий список: один активный получатель с notify_new_orders=True."""
        return NotificationRecipient.objects.create(email=self.GENERAL_EMAIL, name="General", notify_new_orders=True)

    @staticmethod
    def _staff(email, group_name, **extra):
        from django.contrib.auth.models import Group

        from tests.factories import UserFactory

        user = UserFactory(email=email, is_staff=True, **extra)
        user.groups.add(Group.objects.get_or_create(name=group_name)[0])
        return user

    @staticmethod
    def _client_order(manager=None, manual=False, tax_id=""):
        """Клиент с заданным ответственным менеджером и его заказ.

        Без `manager` значение берётся как есть из правила региона (по `tax_id`);
        с `manager` ответственный задаётся напрямую, как при ручном назначении.
        """
        from apps.orders.models import Order
        from apps.users.models import User
        from tests.factories import UserFactory

        client = UserFactory(tax_id=tax_id) if tax_id else UserFactory()
        if manager is not None or manual:
            User.objects.filter(pk=client.pk).update(responsible_manager=manager, responsible_manager_manual=manual)
        return Order.objects.create(
            user=client,
            customer_name="Test Customer",
            customer_email="customer@test.com",
            customer_phone="+79001234567",
            delivery_address="Test Address",
            delivery_method="courier",
            total_amount=Decimal("1000.00"),
        )

    @staticmethod
    def _region_rule(code, manager):
        from apps.common.models import ManagerRoutingRule

        # Тестовая БД строится с миграциями: правило региона может уже существовать
        rule, _ = ManagerRoutingRule.objects.update_or_create(
            match_type="inn_region", match_value=code, defaults={"manager": manager, "is_active": True}
        )
        return rule

    @staticmethod
    def _by_recipients(mock_send_mail):
        return {tuple(call.kwargs["recipient_list"]): call.kwargs for call in mock_send_mail.call_args_list}

    @staticmethod
    def _all_recipients(mock_send_mail):
        return [email for call in mock_send_mail.call_args_list for email in call.kwargs["recipient_list"]]

    @patch("apps.orders.tasks.send_mail")
    def test_responsible_manager_gets_manager_section_link(self, mock_send_mail, general):
        """Менеджер региона клиента получает письмо со ссылкой на /manager/, менеджер другого региона — нет."""
        from apps.users.staff_roles import MANAGERS_GROUP

        manager = self._staff("manager.krd@freesportopt.ru", MANAGERS_GROUP)
        other = self._staff("manager.msk@freesportopt.ru", MANAGERS_GROUP)
        self._region_rule("23", manager)
        self._region_rule("77", other)
        order = self._client_order(tax_id="2312345678")
        # Предусловие: ответственного выставило правило региона, а не тест
        order.user.refresh_from_db()
        assert order.user.responsible_manager == manager

        assert send_order_notification_email(order.id) is True

        sent = self._by_recipients(mock_send_mail)
        assert set(sent) == {(self.GENERAL_EMAIL,), ("manager.krd@freesportopt.ru",)}
        manager_mail = sent[("manager.krd@freesportopt.ru",)]
        for part in ("message", "html_message"):
            assert f"https://optisport.ru/manager/orders/order/{order.id}/change/" in manager_mail[part]
        assert "manager.msk@freesportopt.ru" not in self._all_recipients(mock_send_mail)

    @patch("apps.orders.tasks.send_mail")
    def test_manual_assignment_wins_over_region_rule_manager(self, mock_send_mail, general):
        """При ручном назначении письмо получает назначенный вручную, а не менеджер правила региона."""
        from apps.users.staff_roles import MANAGERS_GROUP

        manual = self._staff("manual@freesportopt.ru", MANAGERS_GROUP)
        rule_manager = self._staff("rule@freesportopt.ru", MANAGERS_GROUP)
        self._region_rule("23", rule_manager)
        order = self._client_order(manual, manual=True, tax_id="2312345678")
        # Предусловие: клиент региона 23, но ответственный назначен вручную
        order.user.refresh_from_db()
        assert order.user.responsible_manager_manual is True

        assert send_order_notification_email(order.id) is True

        recipients = self._all_recipients(mock_send_mail)
        assert "manual@freesportopt.ru" in recipients
        assert "rule@freesportopt.ru" not in recipients

    @patch("apps.orders.tasks.send_mail")
    def test_manager_gets_mail_when_general_list_is_empty(self, mock_send_mail, db):
        """Пустой общий список: письмо уходит менеджеру, задача возвращает True."""
        from apps.users.staff_roles import MANAGERS_GROUP

        assert not NotificationRecipient.objects.filter(notify_new_orders=True).exists()
        manager = self._staff("only.manager@freesportopt.ru", MANAGERS_GROUP)
        order = self._client_order(manager)

        assert send_order_notification_email(order.id) is True

        mock_send_mail.assert_called_once()
        assert mock_send_mail.call_args.kwargs["recipient_list"] == ["only.manager@freesportopt.ru"]

    @patch("apps.orders.tasks.send_mail")
    def test_address_in_both_lists_gets_single_mail(self, mock_send_mail, general):
        """Адрес из общего списка и у менеджера получает одно письмо; регистр email не важен."""
        from apps.users.staff_roles import MANAGERS_GROUP

        manager = self._staff("shared@freesportopt.ru", MANAGERS_GROUP)
        NotificationRecipient.objects.create(email="Shared@FreeSportOpt.ru", name="Shared", notify_new_orders=True)
        order = self._client_order(manager)

        assert send_order_notification_email(order.id) is True

        recipients = self._all_recipients(mock_send_mail)
        assert sorted(email.lower() for email in recipients) == sorted([self.GENERAL_EMAIL, "shared@freesportopt.ru"])

    @pytest.mark.parametrize("case", ["blocked", "no_groups", "no_email", "not_set"])
    @patch("apps.orders.tasks.send_mail")
    def test_unsuitable_manager_falls_back_to_general_list(self, mock_send_mail, general, case, caplog):
        """Менеджер не годится: письмо общему списку, задача не падает, в логе предупреждение с номером заказа."""
        from apps.users.staff_roles import MANAGERS_GROUP

        if case == "blocked":
            manager = self._staff("blocked@freesportopt.ru", MANAGERS_GROUP, is_active=False)
        elif case == "no_groups":
            manager = self._staff("nogroups@freesportopt.ru", "Прочие")
        elif case == "no_email":
            manager = self._staff("", MANAGERS_GROUP)
        else:
            manager = None
        order = self._client_order(manager)

        with caplog.at_level("WARNING", logger="apps.orders.tasks"):
            assert send_order_notification_email(order.id) is True

        assert self._all_recipients(mock_send_mail) == [self.GENERAL_EMAIL]
        assert order.order_number in caplog.text

    @patch("apps.orders.tasks.send_mail")
    def test_order_without_client_goes_to_general_list_without_warning(self, mock_send_mail, general, caplog):
        """У заказа нет клиента: письмо общему списку, предупреждения о менеджере нет."""
        from apps.orders.models import Order

        order = Order.objects.create(
            user=None,
            customer_name="Guest",
            customer_email="guest@test.com",
            customer_phone="+79001234567",
            delivery_address="Test Address",
            delivery_method="courier",
            total_amount=Decimal("100.00"),
        )

        with caplog.at_level("WARNING", logger="apps.orders.tasks"):
            assert send_order_notification_email(order.id) is True

        assert self._all_recipients(mock_send_mail) == [self.GENERAL_EMAIL]
        assert "ответственного менеджера" not in caplog.text

    @patch("apps.orders.tasks.send_mail")
    def test_supervisor_with_flag_off_gets_only_own_clients_orders(self, mock_send_mail, general):
        """Флаг руководителя выключен: письмо о заказе своего клиента приходит, о чужом — нет."""
        from apps.users.staff_roles import MANAGERS_GROUP, SUPERVISORS_GROUP

        supervisor = self._staff("boss@freesportopt.ru", SUPERVISORS_GROUP)
        NotificationRecipient.objects.create(email="boss@freesportopt.ru", name="Boss", notify_new_orders=False)
        other = self._staff("other@freesportopt.ru", MANAGERS_GROUP)
        own_order = self._client_order(supervisor)
        foreign_order = self._client_order(other)

        assert send_order_notification_email(own_order.id) is True
        own_sent = self._by_recipients(mock_send_mail)
        assert ("boss@freesportopt.ru",) in own_sent
        assert (
            f"https://optisport.ru/manager/orders/order/{own_order.id}/change/"
            in own_sent[("boss@freesportopt.ru",)]["message"]
        )

        mock_send_mail.reset_mock()
        assert send_order_notification_email(foreign_order.id) is True
        assert "boss@freesportopt.ru" not in self._all_recipients(mock_send_mail)

    @patch("apps.orders.tasks.send_mail")
    def test_supervisor_with_flag_on_gets_every_order(self, mock_send_mail, general):
        """Флаг руководителя включён: письмо о любом заказе со ссылкой, которая открывается в /manager/."""
        from apps.users.staff_roles import MANAGERS_GROUP, SUPERVISORS_GROUP

        self._staff("boss@freesportopt.ru", SUPERVISORS_GROUP)
        NotificationRecipient.objects.create(email="boss@freesportopt.ru", name="Boss", notify_new_orders=True)
        other = self._staff("other@freesportopt.ru", MANAGERS_GROUP)
        order = self._client_order(other)

        assert send_order_notification_email(order.id) is True

        # Руководитель и менеджер клиента делят одно письмо раздела /manager/
        boss_mails = [
            call.kwargs
            for call in mock_send_mail.call_args_list
            if "boss@freesportopt.ru" in call.kwargs["recipient_list"]
        ]
        assert len(boss_mails) == 1
        assert f"https://optisport.ru/manager/orders/order/{order.id}/change/" in boss_mails[0]["message"]


@pytest.mark.unit
@pytest.mark.django_db
class TestSupervisorNotificationRecipientHint:
    """CAP-4: форма записи в разделе руководителя объясняет, что делает флаг."""

    def test_new_orders_flag_has_hint(self):
        from django.contrib import admin
        from django.test import RequestFactory

        from apps.common.supervisor_admin import NEW_ORDERS_FLAG_HINT, SupervisorNotificationRecipientAdmin

        model_admin = SupervisorNotificationRecipientAdmin(NotificationRecipient, admin.site)
        field = NotificationRecipient._meta.get_field("notify_new_orders")

        form_field = model_admin.formfield_for_dbfield(field, RequestFactory().get("/"))

        assert form_field.help_text == NEW_ORDERS_FLAG_HINT
        assert "общий список" in form_field.help_text


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
            email="alerts@optisport.ru",
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
        assert "alerts@optisport.ru" in call_kwargs.kwargs["recipient_list"]

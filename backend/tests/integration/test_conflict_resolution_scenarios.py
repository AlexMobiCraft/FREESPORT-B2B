"""
Integration-тесты для сценариев разрешения конфликтов (Story 3.2.2)
"""

from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog, SyncConflict
from apps.users.services.conflict_resolution import CustomerConflictResolver

User = get_user_model()


@pytest.mark.integration
@pytest.mark.django_db
class TestPortalRegistrationScenario:
    """Тесты сценария регистрации на портале"""

    @pytest.fixture
    def resolver(self):
        return CustomerConflictResolver()

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_b2b_client_registration_with_inn(self, mock_send_mail, resolver):
        """
        Сценарий: B2B клиент пытается зарегистрироваться с ИНН из 1С
        """
        # Создаем клиента из 1С
        existing_customer = User.objects.create(
            email="company@example.com",
            first_name="Иван",
            last_name="Петров",
            tax_id="1234567890",
            company_name="ООО Компания",
            created_in_1c=True,
            onec_id="1C-456",
        )

        # Данные регистрации на портале
        registration_data = {
            "email": "company@example.com",
            "password": "securepass123",
            "tax_id": "1234567890",
            "first_name": "Петр",  # Пытается изменить
            "last_name": "Иванов",  # Пытается изменить
        }

        # Разрешаем конфликт
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(existing_customer, registration_data, "portal_registration")

        # Проверяем результат
        assert result["action"] == "verified_client"

        # Проверяем что клиент верифицирован
        existing_customer.refresh_from_db()
        assert existing_customer.verification_status == "verified"
        assert existing_customer.check_password("securepass123")

        # Данные НЕ изменились
        assert existing_customer.first_name == "Иван"
        assert existing_customer.last_name == "Петров"

        # Проверяем SyncConflict
        conflict = SyncConflict.objects.get(customer=existing_customer)
        assert conflict.conflict_type == "portal_registration_blocked"
        assert conflict.is_resolved is True

        # Проверяем что email отправлен
        assert mock_send_mail.called

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_b2c_client_registration_with_email(self, mock_send_mail, resolver):
        """
        Сценарий: B2C клиент пытается зарегистрироваться с email из 1С
        """
        # Создаем клиента из 1С
        existing_customer = User.objects.create(
            email="user@example.com",
            first_name="Мария",
            last_name="Сидорова",
            created_in_1c=True,
            onec_id="1C-789",
        )

        # Данные регистрации на портале
        registration_data = {
            "email": "user@example.com",
            "password": "mypassword",
            "first_name": "Анна",  # Пытается изменить
        }

        # Разрешаем конфликт
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(existing_customer, registration_data, "portal_registration")

        # Проверяем результат
        existing_customer.refresh_from_db()
        assert existing_customer.verification_status == "verified"
        assert existing_customer.first_name == "Мария"  # Не изменилось


@pytest.mark.integration
@pytest.mark.django_db
class TestDataImportScenario:
    """Тесты сценария импорта данных из 1С"""

    @pytest.fixture
    def resolver(self):
        return CustomerConflictResolver()

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_update_existing_portal_customer(self, mock_send_mail, resolver):
        """
        Сценарий: Импорт из 1С обновляет данные клиента с портала
        """
        # Создаем клиента на портале
        portal_customer = User.objects.create(
            email="old@example.com",
            first_name="Старое",
            last_name="Имя",
            phone="+79001111111",
            created_in_1c=False,
        )

        # Данные из 1С
        onec_data = {
            "onec_id": "1C-NEW-123",
            "onec_guid": "550e8400-e29b-41d4-a716-446655440000",
            "email": "new@example.com",
            "first_name": "Новое",
            "last_name": "Имя",
            "phone": "+79002222222",
            "company_name": "ООО Новая",
        }

        # Разрешаем конфликт
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(portal_customer, onec_data, "data_import")

        # Проверяем результат
        assert result["action"] == "data_updated"
        assert len(result["changes_made"]) > 0

        # Проверяем обновление данных
        portal_customer.refresh_from_db()
        assert portal_customer.email == "new@example.com"
        assert portal_customer.first_name == "Новое"
        assert portal_customer.last_name == "Имя"
        assert portal_customer.phone == "+79002222222"
        assert portal_customer.onec_id == "1C-NEW-123"
        assert portal_customer.onec_guid is not None
        assert portal_customer.last_sync_from_1c is not None

        # Проверяем SyncConflict с архивом
        conflict = SyncConflict.objects.get(customer=portal_customer)
        assert conflict.conflict_type == "customer_data"
        assert conflict.details["platform_data"]["email"] == "old@example.com"
        assert conflict.details["onec_data"]["email"] == "new@example.com"
        assert "email" in conflict.details["conflicting_fields"]

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_import_without_conflicts(self, mock_send_mail, resolver):
        """
        Сценарий: Импорт из 1С без конфликтов (только обогащение)
        """
        # Создаем клиента с идентичными данными
        customer = User.objects.create(
            email="same@example.com",
            first_name="Иван",
            last_name="Иванов",
            phone="+79003333333",
        )

        # Данные из 1С (идентичные)
        onec_data = {
            "onec_id": "1C-SAME-456",
            "onec_guid": "660e8400-e29b-41d4-a716-446655440000",
            "email": "same@example.com",
            "first_name": "Иван",
            "last_name": "Иванов",
            "phone": "+79003333333",
        }

        # Разрешаем конфликт
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(customer, onec_data, "data_import")

        # Проверяем результат
        customer.refresh_from_db()
        assert customer.onec_id == "1C-SAME-456"
        assert customer.onec_guid is not None

        # Email все равно должен быть отправлен
        assert mock_send_mail.called

        # Проверяем SyncConflict
        conflict = SyncConflict.objects.get(customer=customer)
        assert len(conflict.details["conflicting_fields"]) == 0  # Нет конфликтов


@pytest.mark.integration
@pytest.mark.django_db
class TestEdgeCases:
    """Тесты edge cases"""

    @pytest.fixture
    def resolver(self):
        return CustomerConflictResolver()

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_smtp_error_does_not_block_resolution(self, mock_send_mail, resolver):
        """
        Сценарий: Ошибка SMTP не блокирует разрешение конфликта
        """
        mock_send_mail.side_effect = Exception("SMTP connection failed")

        customer = User.objects.create(
            email="test@example.com",
            first_name="Test",
            created_in_1c=True,
        )

        onec_data = {
            "onec_id": "1C-ERROR-789",
            "email": "test@example.com",
            "password": "pass123",
        }

        # Не должно вызвать исключение
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(customer, onec_data, "portal_registration")

        # Конфликт разрешен
        assert result["action"] == "verified_client"

        # Ошибка залогирована
        error_log = CustomerSyncLog.objects.filter(operation_type="notification_failed").first()
        assert error_log is not None

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_partial_data_from_1c(self, mock_send_mail, resolver):
        """
        Сценарий: Частичные данные из 1С (некоторые поля None)
        """
        customer = User.objects.create(
            email="partial@example.com",
            first_name="Иван",
            last_name="Петров",
            phone="+79004444444",
            company_name="ООО Старая",
        )

        # Частичные данные из 1С
        onec_data = {
            "onec_id": "1C-PARTIAL-999",
            "first_name": "Петр",  # Обновляется
            "phone": None,  # Игнорируется
            "company_name": None,  # Игнорируется
        }

        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            result = resolver.resolve_conflict(customer, onec_data, "data_import")

        # Проверяем обновление
        customer.refresh_from_db()
        assert customer.first_name == "Петр"  # Обновлено
        assert customer.phone == "+79004444444"  # Не изменилось
        assert customer.company_name == "ООО Старая"  # Не изменилось

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_no_email_config(self, mock_send_mail, resolver):
        """
        Сценарий: CONFLICT_NOTIFICATION_EMAIL не настроен
        """
        customer = User.objects.create(email="noconfig@example.com", created_in_1c=True)

        onec_data = {"email": "noconfig@example.com", "password": "pass"}

        # Email не настроен
        with patch("django.conf.settings.CONFLICT_NOTIFICATION_EMAIL", None):
            result = resolver.resolve_conflict(customer, onec_data, "portal_registration")

        # Конфликт разрешен
        assert result["action"] == "verified_client"

        # Email НЕ отправлен
        assert not mock_send_mail.called


@pytest.mark.integration
@pytest.mark.django_db
class TestAuditTrail:
    """Тесты audit trail (логирование и архивирование)"""

    @pytest.fixture
    def resolver(self):
        return CustomerConflictResolver()

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_complete_audit_trail(self, mock_send_mail, resolver):
        """
        Проверка полного audit trail для конфликта
        """
        customer = User.objects.create(
            email="audit@example.com",
            first_name="Старое",
            last_name="Имя",
        )

        onec_data = {
            "onec_id": "1C-AUDIT-111",
            "email": "audit@example.com",
            "first_name": "Новое",
            "last_name": "Имя",
        }

        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            resolver.resolve_conflict(customer, onec_data, "data_import")

        # Проверяем SyncConflict
        conflict = SyncConflict.objects.get(customer=customer)
        assert conflict.is_resolved is True
        assert conflict.details["resolved_by"] == "CustomerConflictResolver"
        assert conflict.resolved_at is not None
        assert "source" in conflict.details

        # Проверяем архивные данные
        assert conflict.details["platform_data"]["first_name"] == "Старое"
        assert conflict.details["onec_data"]["first_name"] == "Новое"

        # Проверяем CustomerSyncLog
        log = CustomerSyncLog.objects.filter(customer=customer, operation_type="conflict_resolution").first()
        assert log is not None
        assert log.status == "success"

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_rollback_capability(self, mock_send_mail, resolver):
        """
        Проверка возможности отката через архивные данные
        """
        customer = User.objects.create(
            email="rollback@example.com",
            first_name="Оригинал",
            last_name="Фамилия",
            phone="+79005555555",
        )

        onec_data = {
            "onec_id": "1C-ROLLBACK-222",
            "first_name": "Изменено",
            "last_name": "Фамилия",
            "phone": "+79006666666",
        }

        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@test.com",
        ):
            resolver.resolve_conflict(customer, onec_data, "data_import")

        # Получаем архивные данные
        conflict = SyncConflict.objects.get(customer=customer)
        archived_data = conflict.details["platform_data"]

        # Проверяем что можно откатить
        assert archived_data["first_name"] == "Оригинал"
        assert archived_data["phone"] == "+79005555555"

        # Симулируем откат
        customer.first_name = archived_data["first_name"]
        customer.phone = archived_data["phone"]
        customer.save()

        customer.refresh_from_db()
        assert customer.first_name == "Оригинал"
        assert customer.phone == "+79005555555"

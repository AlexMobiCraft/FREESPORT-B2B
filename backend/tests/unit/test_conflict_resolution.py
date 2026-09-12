"""
Unit-тесты для CustomerConflictResolver (Story 3.2.2)
"""

from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog, SyncConflict
from apps.users.services.conflict_resolution import CustomerConflictResolver

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestCustomerConflictResolver:
    """Тесты для CustomerConflictResolver"""

    @pytest.fixture
    def resolver(self):
        """Фикстура для создания resolver"""
        return CustomerConflictResolver()

    @pytest.fixture
    def existing_customer(self):
        """Фикстура для создания существующего клиента"""
        return User.objects.create(
            email="test@example.com",
            first_name="Иван",
            last_name="Иванов",
            phone="+79001234567",
            company_name="ООО Тест",
            tax_id="1234567890",
            created_in_1c=True,
            onec_id="1C-123",
        )

    @pytest.fixture
    def onec_data_portal_registration(self):
        """Данные для сценария portal_registration"""
        return {
            "email": "test@example.com",
            "password": "newpassword123",
            "first_name": "Петр",  # Отличается
            "last_name": "Петров",  # Отличается
        }

    @pytest.fixture
    def onec_data_import(self):
        """Данные для сценария data_import"""
        return {
            "onec_id": "1C-123",
            "onec_guid": "550e8400-e29b-41d4-a716-446655440000",
            "email": "newemail@example.com",  # Отличается
            "first_name": "Петр",  # Отличается
            "last_name": "Петров",  # Отличается
            "phone": "+79007654321",  # Отличается
            "company_name": "ООО Новая компания",  # Отличается
        }

    def test_serialize_customer(self, resolver, existing_customer):
        """Тест сериализации данных клиента"""
        serialized = resolver._serialize_customer(existing_customer)

        assert serialized["id"] == existing_customer.id
        assert serialized["email"] == "test@example.com"
        assert serialized["first_name"] == "Иван"
        assert serialized["last_name"] == "Иванов"
        assert serialized["phone"] == "+79001234567"
        assert serialized["company_name"] == "ООО Тест"
        assert serialized["tax_id"] == "1234567890"
        assert serialized["onec_id"] == "1C-123"
        assert serialized["created_in_1c"] is True

    def test_detect_conflicting_fields(self, resolver, existing_customer, onec_data_import):
        """Тест определения конфликтующих полей"""
        conflicting = resolver._detect_conflicting_fields(existing_customer, onec_data_import)

        # Должны быть обнаружены различия
        assert "email" in conflicting
        assert "first_name" in conflicting
        assert "last_name" in conflicting
        assert "phone" in conflicting
        assert "company_name" in conflicting

        # tax_id не должен быть в списке (одинаковый)
        assert "tax_id" not in conflicting

    def test_detect_no_conflicts(self, resolver, existing_customer):
        """Тест когда конфликтов нет"""
        onec_data = {
            "email": "test@example.com",
            "first_name": "Иван",
            "last_name": "Иванов",
            "phone": "+79001234567",
        }

        conflicting = resolver._detect_conflicting_fields(existing_customer, onec_data)

        assert len(conflicting) == 0

    def test_handle_portal_registration(self, resolver, existing_customer, onec_data_portal_registration):
        """Тест обработки регистрации на портале"""
        result = resolver._handle_portal_registration(existing_customer, onec_data_portal_registration)

        # Проверяем результат
        assert result["action"] == "verified_client"
        assert "password set" in result["message"]

        # Проверяем что клиент обновлен
        existing_customer.refresh_from_db()
        assert existing_customer.verification_status == "verified"
        assert existing_customer.check_password("newpassword123")

        # Данные НЕ должны измениться
        assert existing_customer.first_name == "Иван"
        assert existing_customer.last_name == "Иванов"

    def test_handle_data_import(self, resolver, existing_customer, onec_data_import):
        """Тест обработки импорта данных из 1С"""
        conflicting_fields = ["email", "first_name", "last_name", "phone"]

        result = resolver._handle_data_import(existing_customer, onec_data_import, conflicting_fields)

        # Проверяем результат
        assert result["action"] == "data_updated"
        assert len(result["changes_made"]) > 0

        # Проверяем что клиент обновлен
        existing_customer.refresh_from_db()
        assert existing_customer.email == "newemail@example.com"
        assert existing_customer.first_name == "Петр"
        assert existing_customer.last_name == "Петров"
        assert existing_customer.phone == "+79007654321"
        assert existing_customer.onec_guid is not None
        assert existing_customer.last_sync_from_1c is not None

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_resolve_conflict_portal_registration(
        self,
        mock_send_mail,
        resolver,
        existing_customer,
        onec_data_portal_registration,
    ):
        """Тест полного цикла разрешения конфликта при регистрации"""
        result = resolver.resolve_conflict(
            existing_customer,
            onec_data_portal_registration,
            "portal_registration",
        )

        # Проверяем результат
        assert result["action"] == "verified_client"

        # Проверяем создание записи в SyncConflict
        conflict = SyncConflict.objects.filter(customer=existing_customer).first()
        assert conflict is not None
        assert conflict.conflict_type == "portal_registration_blocked"
        assert conflict.is_resolved is True
        assert conflict.resolution_strategy == "onec_wins"

        # Проверяем создание записи в CustomerSyncLog
        log = CustomerSyncLog.objects.filter(customer=existing_customer, operation_type="conflict_resolution").first()
        assert log is not None
        assert log.status == "success"

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_resolve_conflict_data_import(self, mock_send_mail, resolver, existing_customer, onec_data_import):
        """Тест полного цикла разрешения конфликта при импорте"""
        result = resolver.resolve_conflict(existing_customer, onec_data_import, "data_import")

        # Проверяем результат
        assert result["action"] == "data_updated"
        assert len(result["changes_made"]) > 0

        # Проверяем создание записи в SyncConflict
        conflict = SyncConflict.objects.filter(customer=existing_customer).first()
        assert conflict is not None
        assert conflict.conflict_type == "customer_data"
        assert conflict.is_resolved is True

        # Проверяем архивные данные в details
        assert "email" in conflict.details["platform_data"]
        assert conflict.details["platform_data"]["email"] == "test@example.com"
        assert conflict.details["onec_data"]["email"] == "newemail@example.com"

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_email_notification_sent(self, mock_send_mail, resolver, existing_customer, onec_data_import):
        """Тест отправки email уведомления"""
        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@example.com",
        ):
            with patch(
                "django.conf.settings.DEFAULT_FROM_EMAIL",
                "noreply@example.com",
            ):
                resolver.resolve_conflict(existing_customer, onec_data_import, "data_import")

                # Email должен быть отправлен (через on_commit)
                # В тестах on_commit выполняется сразу
                assert mock_send_mail.called

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_email_notification_no_config(self, mock_send_mail, resolver, existing_customer, onec_data_import):
        """Тест когда email не настроен"""
        with patch("django.conf.settings.CONFLICT_NOTIFICATION_EMAIL", None):
            resolver.resolve_conflict(existing_customer, onec_data_import, "data_import")

            # Email НЕ должен быть отправлен
            assert not mock_send_mail.called

    @patch("apps.users.services.conflict_resolution.send_mail")
    def test_email_notification_error_handling(self, mock_send_mail, resolver, existing_customer, onec_data_import):
        """Тест обработки ошибки отправки email"""
        mock_send_mail.side_effect = Exception("SMTP Error")

        with patch(
            "django.conf.settings.CONFLICT_NOTIFICATION_EMAIL",
            "admin@example.com",
        ):
            # Не должно вызвать исключение
            result = resolver.resolve_conflict(existing_customer, onec_data_import, "data_import")

            # Конфликт должен быть разрешен несмотря на ошибку email
            assert result["action"] == "data_updated"

            # Должна быть создана запись об ошибке
            error_log = CustomerSyncLog.objects.filter(operation_type="notification_failed").first()
            assert error_log is not None
            assert "SMTP Error" in error_log.error_message

    def test_invalid_conflict_source(self, resolver, existing_customer, onec_data_import):
        """Тест обработки неверного источника конфликта"""
        with pytest.raises(ValueError) as exc_info:
            resolver.resolve_conflict(existing_customer, onec_data_import, "invalid_source")

        assert "Unknown conflict_source" in str(exc_info.value)

    def test_conflicting_fields_with_none_values(self, resolver, existing_customer):
        """Тест обработки None значений в данных из 1С"""
        onec_data = {
            "email": None,
            "first_name": "Петр",
            "phone": None,
        }

        conflicting = resolver._detect_conflicting_fields(existing_customer, onec_data)

        # Только first_name должен быть в конфликтах (None игнорируются)
        assert "first_name" in conflicting
        assert "email" not in conflicting
        assert "phone" not in conflicting

    def test_handle_data_import_partial_data(self, resolver, existing_customer):
        """Тест импорта с частичными данными"""
        onec_data = {
            "onec_id": "1C-123",
            "first_name": "Петр",  # Только это поле отличается
        }

        conflicting_fields = ["first_name"]

        result = resolver._handle_data_import(existing_customer, onec_data, conflicting_fields)

        # Проверяем что обновлено только одно поле
        existing_customer.refresh_from_db()
        assert existing_customer.first_name == "Петр"
        assert existing_customer.last_name == "Иванов"  # Не изменилось
        assert existing_customer.email == "test@example.com"  # Не изменилось

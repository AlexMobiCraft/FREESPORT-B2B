"""
Unit-тесты для CustomerDataProcessor
Тестирует бизнес-логику обработки клиентов
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.common.models import CustomerSyncLog
from apps.products.models import ImportSession
from apps.users.services.processor import CustomerDataProcessor

User = get_user_model()


@pytest.mark.unit
@pytest.mark.django_db
class TestCustomerDataProcessor:
    """Unit-тесты для процессора клиентов"""

    @pytest.fixture
    def session(self):
        """Фикстура для создания сессии импорта"""
        return ImportSession.objects.create(
            import_type=ImportSession.ImportType.CUSTOMERS,
            status=ImportSession.ImportStatus.STARTED,
        )

    @pytest.fixture
    def processor(self, session):
        """Фикстура для создания процессора"""
        return CustomerDataProcessor(session_id=session.pk)

    def test_role_mapping_wholesale_level1(self, processor):
        """Тест маппинга роли Опт 1"""
        assert processor.map_role("Опт 1") == "wholesale_level1"

    def test_role_mapping_wholesale_level2(self, processor):
        """Тест маппинга роли Опт 2"""
        assert processor.map_role("Опт 2") == "wholesale_level2"

    def test_role_mapping_wholesale_level3(self, processor):
        """Тест маппинга роли Опт 3"""
        assert processor.map_role("Опт 3") == "wholesale_level3"

    def test_role_mapping_trainer(self, processor):
        """Тест маппинга роли Тренерская"""
        assert processor.map_role("Тренерская") == "trainer"

    def test_role_mapping_retail(self, processor):
        """Тест маппинга роли РРЦ"""
        assert processor.map_role("РРЦ") == "retail"

    def test_role_mapping_unknown_fallback(self, processor):
        """Тест fallback к retail для неизвестной роли"""
        assert processor.map_role("Неизвестная роль") == "retail"
        assert processor.map_role("") == "retail"

    def test_create_new_customer_with_email(self, processor):
        """Тест создания нового клиента с email"""
        customer_data = {
            "onec_id": "TEST-NEW-001",
            "email": "newcustomer@example.com",
            "first_name": "Иван",
            "last_name": "Петров",
            "customer_type": "Опт 1",
            "phone": "+79001234567",
            "company_name": "ООО Тест",
            "tax_id": "1234567890",
        }

        user = processor.process_customer(customer_data)

        assert user is not None
        assert user.onec_id == "TEST-NEW-001"
        assert user.email == "newcustomer@example.com"
        assert user.first_name == "Иван"
        assert user.last_name == "Петров"
        assert user.role == "wholesale_level1"
        assert user.phone == "+79001234567"
        assert user.company_name == "ООО Тест"
        assert user.tax_id == "1234567890"
        assert user.created_in_1c is True
        assert user.sync_status == "synced"
        assert user.last_sync_at is not None

        # Проверка логирования
        log = CustomerSyncLog.objects.filter(onec_id="TEST-NEW-001").first()
        assert log is not None
        assert log.operation_type == CustomerSyncLog.OperationType.CREATED
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.customer == user

    def test_create_new_customer_without_email(self, processor):
        """Тест создания нового клиента без email"""
        customer_data = {
            "onec_id": "TEST-NO-EMAIL-001",
            "email": "",  # Пустой email
            "first_name": "Петр",
            "last_name": "Сидоров",
            "customer_type": "Опт 2",
        }

        user = processor.process_customer(customer_data)

        # Клиент должен быть создан с пустым email (NULL для уникальности)
        assert user is not None
        assert user.onec_id == "TEST-NO-EMAIL-001"
        assert user.email is None  # None вместо пустой строки для уникальности
        assert user.role == "wholesale_level2"
        assert user.created_in_1c is True

        # Проверка логирования success с warning
        logs = CustomerSyncLog.objects.filter(onec_id="TEST-NO-EMAIL-001")
        assert logs.count() >= 1

        # Должна быть хотя бы одна запись с успехом
        success_log = logs.filter(
            operation_type=CustomerSyncLog.OperationType.CREATED,
            status=CustomerSyncLog.StatusType.SUCCESS,
        ).first()
        assert success_log is not None

    def test_skip_invalid_email_format(self, processor):
        """Тест пропуска клиента с невалидным форматом email"""
        customer_data = {
            "onec_id": "TEST-INVALID-EMAIL-001",
            "email": "invalid-email-format",  # Невалидный формат
            "first_name": "Тест",
            "last_name": "Тестов",
            "customer_type": "РРЦ",
        }

        user = processor.process_customer(customer_data)

        assert user is None

        # Проверка логирования ошибки
        log = CustomerSyncLog.objects.filter(onec_id="TEST-INVALID-EMAIL-001").first()
        assert log is not None
        assert log.operation_type == CustomerSyncLog.OperationType.ERROR
        assert log.status == CustomerSyncLog.StatusType.FAILED
        assert "email" in log.error_message.lower()

    def test_update_existing_customer_by_onec_id(self, processor):
        """Тест обновления существующего клиента по onec_id"""
        # Создать существующего клиента
        existing_user = User.objects.create(
            email="existing@example.com",
            onec_id="TEST-EXISTING-001",
            first_name="Старое",
            last_name="Имя",
            role="retail",
        )

        customer_data = {
            "onec_id": "TEST-EXISTING-001",
            "email": "existing@example.com",
            "first_name": "Новое",
            "last_name": "Имя",
            "customer_type": "Опт 3",
        }

        user = processor.process_customer(customer_data)

        assert user.pk == existing_user.pk
        assert user.first_name == "Новое"
        assert user.last_name == "Имя"
        assert user.role == "wholesale_level3"
        assert user.sync_status == "synced"

        # Проверка логирования
        log = CustomerSyncLog.objects.filter(onec_id="TEST-EXISTING-001").first()
        assert log.operation_type == CustomerSyncLog.OperationType.UPDATED
        assert log.status == CustomerSyncLog.StatusType.SUCCESS

    def test_find_duplicate_by_email(self, processor):
        """Тест поиска дубликата по email"""
        # Создать пользователя с email но без onec_id
        existing_user = User.objects.create(
            email="duplicate@example.com",
            first_name="Существующий",
            last_name="Пользователь",
        )

        customer_data = {
            "onec_id": "TEST-DUP-EMAIL-001",
            "email": "duplicate@example.com",
            "first_name": "Новое имя",
            "last_name": "Новая фамилия",
            "customer_type": "Опт 1",
        }

        user = processor.process_customer(customer_data)

        # Должен обновить существующего пользователя
        assert user.pk == existing_user.pk
        assert user.onec_id == "TEST-DUP-EMAIL-001"
        assert user.first_name == "Новое имя"

        # Проверка логирования как обновление
        log = CustomerSyncLog.objects.filter(onec_id="TEST-DUP-EMAIL-001").first()
        assert log.operation_type == CustomerSyncLog.OperationType.UPDATED

    def test_process_customers_batch(self, processor):
        """Тест пакетной обработки клиентов"""
        customers_data = [
            {
                "onec_id": f"TEST-BATCH-{i:03d}",
                "email": f"batch{i}@example.com",
                "first_name": f"Клиент{i}",
                "last_name": "Тестовый",
                "customer_type": "Опт 1",
            }
            for i in range(10)
        ]

        result = processor.process_customers(customers_data, chunk_size=5)

        assert result["total"] == 10
        assert result["created"] == 10
        assert result["updated"] == 0
        assert result["errors"] == 0

        # Проверяем что все клиенты созданы
        for i in range(10):
            assert User.objects.filter(onec_id=f"TEST-BATCH-{i:03d}").exists()

    def test_process_customers_with_errors(self, processor):
        """Тест обработки клиентов с ошибками"""
        customers_data = [
            {
                "onec_id": "TEST-VALID-001",
                "email": "valid@example.com",
                "first_name": "Валидный",
                "last_name": "Клиент",
                "customer_type": "РРЦ",
            },
            {
                "onec_id": "TEST-INVALID-001",
                "email": "invalid-email",  # Невалидный email
                "first_name": "Невалидный",
                "last_name": "Клиент",
                "customer_type": "РРЦ",
            },
        ]

        result = processor.process_customers(customers_data)

        assert result["total"] == 2
        assert result["created"] == 1  # Только валидный клиент
        assert result["errors"] == 1  # Один с ошибкой

        # Проверяем что валидный клиент создан
        assert User.objects.filter(onec_id="TEST-VALID-001").exists()
        # Невалидный не создан
        assert not User.objects.filter(onec_id="TEST-INVALID-001").exists()

    def test_validate_email_correct_format(self, processor):
        """Тест валидации корректного email"""
        assert processor._validate_email("test@example.com") is True
        assert processor._validate_email("user.name@domain.co.uk") is True

    def test_validate_email_incorrect_format(self, processor):
        """Тест валидации некорректного email"""
        assert processor._validate_email("invalid-email") is False
        assert processor._validate_email("no-at-sign.com") is False
        assert processor._validate_email("@nodomain.com") is False

    def test_validate_email_empty(self, processor):
        """Тест валидации пустого email"""
        assert processor._validate_email("") is False

    def test_log_operation_creates_record(self, processor):
        """Тест создания записи в CustomerSyncLog"""
        user = User.objects.create(email="logtest@example.com", onec_id="TEST-LOG-001")

        processor._log_operation(
            user=user,
            onec_id="TEST-LOG-001",
            operation_type=CustomerSyncLog.OperationType.CREATED,
            status=CustomerSyncLog.StatusType.SUCCESS,
            details={"test": "data"},
        )

        log = CustomerSyncLog.objects.filter(onec_id="TEST-LOG-001").first()
        assert log is not None
        assert log.customer == user
        assert log.session == str(processor.session.pk)
        assert log.operation_type == CustomerSyncLog.OperationType.CREATED
        assert log.status == CustomerSyncLog.StatusType.SUCCESS
        assert log.details == {"test": "data"}

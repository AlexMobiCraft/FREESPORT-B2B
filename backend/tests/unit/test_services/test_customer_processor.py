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

    def test_is_buyer_accepts_purchaser_role(self, processor):
        """Контрагент с ролью Покупатель подлежит импорту"""
        assert processor.is_buyer({"role": "Покупатель"}) is True

    def test_is_buyer_rejects_other_roles(self, processor):
        """Поставщики и контрагенты без роли клиентами портала не становятся"""
        assert processor.is_buyer({"role": "Поставщик"}) is False
        assert processor.is_buyer({"role": ""}) is False
        assert processor.is_buyer({}) is False

    def test_skip_non_buyer_customer(self, processor):
        """Контрагент-поставщик пропускается импортом"""
        customer_data = {
            "onec_id": "TEST-SUPPLIER-001",
            "role": "Поставщик",
            "email": "supplier@example.com",
            "first_name": "Иван",
            "last_name": "Поставщиков",
            "customer_type": "legal_entity",
        }

        assert processor.process_customer(customer_data) is None
        assert not User.objects.filter(onec_id="TEST-SUPPLIER-001").exists()

    def test_new_customer_gets_unregistered_role(self, processor):
        """Новый контрагент получает нейтральную роль, а не retail"""
        customer_data = {
            "onec_id": "TEST-ROLE-001",
            "role": "Покупатель",
            "email": "roletest@example.com",
            "first_name": "Роль",
            "last_name": "Тестов",
            "customer_type": "legal_entity",
            "company_name": "ООО Роль",
            "tax_id": "7707083893",
        }

        user = processor.process_customer(customer_data)

        assert user.role == "unregistered"
        assert user.is_b2b_user is False

    def test_created_customer_satisfies_unlinked_invariant(self, processor):
        """
        Импорт обязан создавать запись, которую регистрация считает
        непривязанной, — иначе ИНН заблокирует регистрацию всей компании.
        """
        customer_data = {
            "onec_id": "TEST-INVARIANT-001",
            "role": "Покупатель",
            "email": "invariant@example.com",
            "first_name": "Инвариант",
            "last_name": "Тестов",
            "customer_type": "legal_entity",
            "tax_id": "7707083893",
        }

        user = processor.process_customer(customer_data)

        assert user.is_unlinked_1c_record is True

    def test_is_buyer_accepts_multiple_roles(self, processor):
        """Контрагент, совмещающий роли, остаётся покупателем."""
        assert processor.is_buyer({"role": "Поставщик,Покупатель"}) is True
        assert processor.is_buyer({"role": " покупатель "}) is True

    def test_skip_non_buyer_is_logged_as_skipped(self, processor):
        """Пропуск должен попасть в skipped, а не в errors."""
        customer_data = {
            "onec_id": "TEST-SKIPLOG-001",
            "role": "Поставщик",
            "email": "skiplog@example.com",
            "first_name": "Иван",
            "last_name": "Поставщиков",
            "customer_type": "legal_entity",
        }

        assert processor.process_customer(customer_data) is None

        log = CustomerSyncLog.objects.filter(onec_id="TEST-SKIPLOG-001").first()
        assert log is not None
        assert log.operation_type == CustomerSyncLog.OperationType.SKIPPED

    def test_import_preserves_role_assigned_by_manager(self, processor):
        """
        Роль сохраняется, ПОТОМУ ЧТО данных о виде цен в выгрузке нет.

        С 40.4 импорт роль привязанного аккаунта меняет (FR-40-12), но
        только когда 1С отдала вид цен: здесь customer_data собран без
        price_type_ids и agreement_status, резолвер отвечает no_data.
        """
        existing_user = User.objects.create(
            email="wholesale@example.com",
            onec_id="TEST-PRESERVE-001",
            first_name="Опт",
            last_name="Клиентов",
            role="wholesale_level2",
            verification_status="verified",
        )

        customer_data = {
            "onec_id": "TEST-PRESERVE-001",
            "role": "Покупатель",
            "email": "wholesale@example.com",
            "first_name": "Опт",
            "last_name": "Обновлённый",
            "customer_type": "legal_entity",
        }

        user = processor.process_customer(customer_data)

        assert user.pk == existing_user.pk
        assert user.role == "wholesale_level2"
        assert user.last_name == "Обновлённый"

    def test_create_new_customer_with_email(self, processor):
        """Тест создания нового клиента с email"""
        customer_data = {
            "onec_id": "TEST-NEW-001",
            "email": "newcustomer@example.com",
            "first_name": "Иван",
            "last_name": "Петров",
            "role": "Покупатель",
            "customer_type": "legal_entity",
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
        assert user.role == "unregistered"
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
            "role": "Покупатель",
            "customer_type": "legal_entity",
        }

        user = processor.process_customer(customer_data)

        # Клиент должен быть создан с пустым email (NULL для уникальности)
        assert user is not None
        assert user.onec_id == "TEST-NO-EMAIL-001"
        assert user.email is None  # None вместо пустой строки для уникальности
        assert user.role == "unregistered"
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
            "role": "Покупатель",
            "customer_type": "legal_entity",
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
            "role": "Покупатель",
            "customer_type": "legal_entity",
        }

        user = processor.process_customer(customer_data)

        assert user.pk == existing_user.pk
        assert user.first_name == "Новое"
        assert user.last_name == "Имя"
        # Роль не меняется, потому что вида цен в данных нет (reason=no_data),
        # а не потому, что импорт роль не трогает: с 40.4 трогает.
        assert user.role == "retail"
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
            "role": "Покупатель",
            "customer_type": "legal_entity",
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
                "role": "Покупатель",
                "customer_type": "legal_entity",
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
                "role": "Покупатель",
                "customer_type": "legal_entity",
            },
            {
                "onec_id": "TEST-INVALID-001",
                "email": "invalid-email",  # Невалидный email
                "first_name": "Невалидный",
                "last_name": "Клиент",
                "role": "Покупатель",
                "customer_type": "legal_entity",
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


# ---------------------------------------------------------------------------
# Стори 40.3: хранение вида цен из 1С (onec_price_type_id)
# ---------------------------------------------------------------------------
#
# Данные берутся из реального снимка выгрузки (NFR-3940-01). Путь считается
# напрямую из settings.BASE_DIR, а не через фикстуру onec_data_dir: та зависит
# от function-scoped фикстуры settings, и scope="module" дал бы ScopeMismatch.


# GUID видов цен из реального снимка (замер стори 40.1). «Опт 4» засеян
# миграцией products/0053 с user_role="wholesale_level4" — тестовая БД
# строится С миграциями, поэтому создавать его заново нельзя, только
# get_or_create. Остальные справочнику неизвестны.
OPT4_GUID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"
OPT2_GUID = "a91bdb02-b3f2-11ea-81c3-00155d3cae02"
RRP_GUID = "3d1482c4-bd77-11e4-afc8-20cf3073dde3"


def _snapshot_customers(subdir: str) -> list[dict]:
    """
    Разбирает первый файл снимка выгрузки контрагентов.

    Имена файлов задаёт 1С (contragents_<пакет>_<GUID>.xml, GUID новый при
    каждой выгрузке) — зашивать имя нельзя. Одного файла достаточно: тесты
    проверяют логику на контрагенте, а не объём снимка.
    """
    from pathlib import Path

    from django.conf import settings

    from apps.users.services.parser import CustomerDataParser

    snapshot = Path(settings.BASE_DIR) / "data" / "import_1c" / subdir
    files = sorted(snapshot.glob("contragents*.xml"))
    if not files:
        pytest.skip(f"Нет снимка выгрузки контрагентов: {snapshot}")

    # parse(file_path) → list[dict], БД не трогает
    return CustomerDataParser().parse(str(files[0]))


@pytest.fixture(scope="module")
def real_customers():
    """Контрагенты из реального снимка второй редакции патча БУС."""
    return _snapshot_customers("contragents_pricetype")


@pytest.fixture(scope="module")
def real_customers_without_block():
    """Снимок 11.04.2026: блока <ЗначенияРеквизитов> нет ни у кого."""
    return _snapshot_customers("contragents")


@pytest.fixture(scope="module")
def customer_with_price_type(real_customers):
    """Контрагент-покупатель ровно с одним видом цен."""
    for data in real_customers:
        if len(set(data.get("price_type_ids") or [])) == 1 and "Покупатель" in str(data.get("role") or ""):
            return data
    pytest.skip("В снимке нет контрагента-покупателя с одним ТипЦенId")


@pytest.fixture(scope="module")
def customer_without_agreement(real_customers):
    """Контрагент-покупатель со статусом «НетСоглашения»."""
    for data in real_customers:
        if data.get("agreement_status") == "НетСоглашения" and "Покупатель" in str(data.get("role") or ""):
            return data
    pytest.skip("В снимке нет контрагента-покупателя со статусом НетСоглашения")


@pytest.fixture(scope="module")
def customer_without_attributes_block(real_customers_without_block):
    """Контрагент-покупатель без блока реквизитов: ни вида цен, ни статуса."""
    for data in real_customers_without_block:
        if (
            not data.get("price_type_ids")
            and not data.get("agreement_status")
            and "Покупатель" in str(data.get("role") or "")
        ):
            return data
    pytest.skip("В старом снимке нет контрагента-покупателя без блока реквизитов")


@pytest.fixture(scope="module")
def snapshot_price_type_guids(real_customers):
    """Все различные GUID видов цен, встреченные в снимке."""
    guids = sorted({guid for data in real_customers for guid in (data.get("price_type_ids") or [])})
    if len(guids) < 2:
        pytest.skip("В снимке меньше двух различных ТипЦенId")
    return guids


@pytest.fixture(scope="module")
def customer_with_opt4(customer_with_price_type):
    """
    Контрагент снимка с подменённым видом цен на «Опт 4».

    GUID «Опт 4» — единственный, засеянный миграцией products/0053 с
    непустым user_role, поэтому только он гарантированно разрешается в
    роль без правки справочника. Искать такого контрагента в снимке
    нельзя: состав видов цен внутри конкретного файла не зафиксирован,
    и поиск дал бы недетерминированный skip. Подмена price_type_ids —
    вариация входа сервиса, а не синтетический XML.
    """
    data = dict(customer_with_price_type)
    data["price_type_ids"] = [OPT4_GUID]
    data["price_type_meta"] = [
        {
            "price_type_id": OPT4_GUID,
            "price_type_name": "Опт 4 (до 50 тыс.руб в квартал)",
            "agreement_name": "Соглашение Опт 4",
            "agreement_is_standard": True,
        }
    ]
    return data


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.data_dependent
class TestCustomerPriceTypeStorage:
    """
    Хранение вида цен из 1С в User.onec_price_type_id (стори 40.3).

    Роль здесь не меняется ни в одном сценарии — её применение заводит
    стори 40.4. Тесты проверяют это явно.
    """

    # Фикстуры session/processor объявлены методами TestCustomerDataProcessor
    # и этому классу не видны — дублируем, чтобы не править существующий класс.
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

    def test_create_stores_single_price_type(self, processor, customer_with_price_type):
        """AC2: при создании контрагента вид цен записывается, роль — unregistered."""
        expected_guid = customer_with_price_type["price_type_ids"][0]

        user = processor.process_customer(dict(customer_with_price_type))

        assert user is not None
        assert user.onec_price_type_id == expected_guid
        assert user.role == User.ROLE_UNREGISTERED

    def test_update_stores_price_type_for_linked_account(self, processor, customer_with_price_type):
        """AC3: привязанный аккаунт с выданной ролью тоже получает вид цен."""
        expected_guid = customer_with_price_type["price_type_ids"][0]
        existing = User.objects.create(
            email="linked-price-type@example.com",
            onec_id=customer_with_price_type["onec_id"],
            role="wholesale_level1",
            created_in_1c=False,
        )

        user = processor.process_customer(dict(customer_with_price_type))

        assert user is not None
        assert user.pk == existing.pk
        assert user.onec_price_type_id == expected_guid
        # Роль не меняется, потому что GUID снимка роли не несёт: его нет в
        # справочнике PriceType (это утверждает соседний
        # test_price_type_stored_even_if_unknown_to_reference), резолвер
        # отвечает unknown_price_type. Правило «импорт роль не трогает»
        # отменено стори 40.4 — см. TestCustomerRoleFromPriceType.
        assert user.role == "wholesale_level1"

    def test_price_type_stored_even_if_unknown_to_reference(self, processor, customer_with_price_type):
        """AC3: GUID, которого нет в справочнике PriceType, всё равно записан."""
        from apps.products.models import PriceType

        guid = customer_with_price_type["price_type_ids"][0]
        assert not PriceType.objects.filter(onec_id__iexact=guid).exists(), (
            "Тест проверяет запись вида цен в обход справочника — GUID не должен "
            "быть в PriceType; поправьте выбор контрагента, если справочник пополнился"
        )

        user = processor.process_customer(dict(customer_with_price_type))

        assert user is not None
        assert user.onec_price_type_id == guid

    def test_no_agreement_clears_price_type(self, processor, customer_without_agreement, snapshot_price_type_guids):
        """AC4: статус «НетСоглашения» гасит ранее сохранённое значение."""
        existing = User.objects.create(
            email="no-agreement@example.com",
            onec_id=customer_without_agreement["onec_id"],
            onec_price_type_id=snapshot_price_type_guids[0],
            created_in_1c=True,
        )

        user = processor.process_customer(dict(customer_without_agreement))

        assert user is not None
        assert user.pk == existing.pk
        assert user.onec_price_type_id == ""

    def test_missing_attributes_block_keeps_price_type(
        self, processor, customer_without_attributes_block, snapshot_price_type_guids
    ):
        """AC5: блока реквизитов нет — сохранённое значение не затирается."""
        stored_guid = snapshot_price_type_guids[0]
        existing = User.objects.create(
            email="no-block@example.com",
            onec_id=customer_without_attributes_block["onec_id"],
            onec_price_type_id=stored_guid,
            created_in_1c=True,
        )

        user = processor.process_customer(dict(customer_without_attributes_block))

        assert user is not None
        assert user.pk == existing.pk
        assert user.onec_price_type_id == stored_guid

    def test_ambiguous_price_types_leave_stored_value(
        self, processor, customer_with_price_type, snapshot_price_type_guids
    ):
        """AC6: два различных GUID — сохранённое значение не меняется."""
        stored_guid = snapshot_price_type_guids[0]
        ambiguous_data = dict(customer_with_price_type)
        ambiguous_data["price_type_ids"] = snapshot_price_type_guids[:2]
        existing = User.objects.create(
            email="ambiguous-stored@example.com",
            onec_id=customer_with_price_type["onec_id"],
            onec_price_type_id=stored_guid,
            created_in_1c=True,
        )

        user = processor.process_customer(ambiguous_data)

        assert user is not None
        assert user.pk == existing.pk
        assert user.onec_price_type_id == stored_guid

    def test_ambiguous_price_types_leave_field_empty_on_create(
        self, processor, customer_with_price_type, snapshot_price_type_guids
    ):
        """AC6: два различных GUID при создании — поле остаётся пустым."""
        ambiguous_data = dict(customer_with_price_type)
        ambiguous_data["price_type_ids"] = snapshot_price_type_guids[:2]

        user = processor.process_customer(ambiguous_data)

        assert user is not None
        assert user.onec_price_type_id == ""
        assert user.role == User.ROLE_UNREGISTERED

    def test_repeated_run_is_idempotent(self, processor, customer_with_price_type):
        """AC9: повторный прогон не меняет значение и не плодит записи журнала."""
        from apps.common.models import AuditLog

        expected_guid = customer_with_price_type["price_type_ids"][0]

        first = processor.process_customer(dict(customer_with_price_type))
        assert first is not None
        logs_after_first = CustomerSyncLog.objects.count()

        second = processor.process_customer(dict(customer_with_price_type))

        assert second is not None
        assert second.pk == first.pk
        assert second.onec_price_type_id == expected_guid
        # Обновление пишет ровно одну запись журнала синхронизации
        assert CustomerSyncLog.objects.count() == logs_after_first + 1
        # Запись создана импортом и остаётся непривязанной записью 1С, роль
        # для неё не разрешается вовсе (§5) — журнала смены роли нет.
        assert AuditLog.objects.count() == 0


# ---------------------------------------------------------------------------
# Стори 40.4: импорт применяет роль привязанным аккаунтам
# ---------------------------------------------------------------------------


@pytest.mark.unit
@pytest.mark.django_db
@pytest.mark.data_dependent
class TestCustomerRoleFromPriceType:
    """
    Применение роли портала по виду цен из 1С (стори 40.4).

    Ключевое правило: роль получают ТОЛЬКО записи, не проходящие
    unlinked_1c_record_q(). Непривязанная запись 1С роли не получает
    никогда — иначе она выпадает из выборки кандидатов на привязку.
    """

    # Фикстуры session/processor объявлены методами TestCustomerDataProcessor
    # и этому классу не видны — дублируем, чтобы не править существующий класс.
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

    @staticmethod
    def _linked_account(onec_id: str, role: str, email: str) -> "User":
        """
        Живой портальный аккаунт, привязанный к контрагенту 1С.

        Предикат unlinked_1c_record_q() не проходит по трём признакам сразу
        (created_in_1c=False, роль не unregistered, пароль задан) — так же,
        как аккаунт после ручной привязки менеджером.
        """
        user = User.objects.create(
            email=email,
            onec_id=onec_id,
            role=role,
            created_in_1c=False,
            verification_status="verified",
        )
        user.set_password("Passw0rd!")
        user.save(update_fields=["password"])
        assert user.is_unlinked_1c_record is False
        return user

    @staticmethod
    def _ensure_price_type(guid: str, name: str, user_role: str, product_field: str) -> None:
        """
        Заводит вид цен в справочнике, если его там ещё нет.

        get_or_create, а не create: «Опт 4» засеян миграцией products/0053,
        а тестовая БД строится с миграциями — create дал бы duplicate key.
        """
        from apps.products.models import PriceType

        PriceType.objects.get_or_create(
            onec_id=guid,
            defaults={
                "onec_name": name,
                "product_field": product_field,
                "user_role": user_role,
                "is_active": True,
            },
        )

    # -- AC1: непривязанная запись 1С роли не получает ----------------------

    def test_unlinked_1c_record_keeps_unregistered_role(self, processor, customer_with_opt4):
        """
        AC1: запись 1С без портального аккаунта роли не получает никогда.

        Смена роли выбила бы её из unlinked_1c_record_q(), то есть из всех
        путей привязки разом — баг, чинившийся миграцией 0018.
        """
        from apps.common.models import AuditLog

        # Первый прогон создаёт непривязанную запись 1С
        created = processor.process_customer(dict(customer_with_opt4))
        assert created.is_unlinked_1c_record is True

        # Второй прогон обновляет её — роль обязана остаться прежней
        user = processor.process_customer(dict(customer_with_opt4))

        assert user.pk == created.pk
        assert user.role == User.ROLE_UNREGISTERED
        assert user.onec_price_type_id == OPT4_GUID
        assert user.is_unlinked_1c_record is True
        assert processor.last_role_outcome == "roles_skipped_unlinked_record"
        assert AuditLog.objects.count() == 0

    # -- AC2, AC4: роль привязанного аккаунта приезжает из 1С ---------------

    def test_linked_account_gets_role_from_opt4(self, processor, customer_with_opt4):
        """AC2/AC4: соглашение «Опт 4» → роль wholesale_level4."""
        existing = self._linked_account(customer_with_opt4["onec_id"], "wholesale_level1", "opt4-linked@example.com")

        user = processor.process_customer(dict(customer_with_opt4))

        assert user.pk == existing.pk
        assert user.role == "wholesale_level4"
        assert processor.last_role_outcome == "roles_updated_from_assigned"

    def test_linked_account_gets_role_from_opt2(self, processor, customer_with_price_type):
        """AC2/AC4: соглашение «Опт 2» → роль wholesale_level2 (маппинг из справочника)."""
        self._ensure_price_type(OPT2_GUID, "Опт 2 (150-300 тыс.руб в квартал)", "wholesale_level2", "opt2_price")
        data = dict(customer_with_price_type)
        data["price_type_ids"] = [OPT2_GUID]
        existing = self._linked_account(data["onec_id"], "wholesale_level1", "opt2-linked@example.com")

        user = processor.process_customer(data)

        assert user.pk == existing.pk
        assert user.role == "wholesale_level2"

    # -- AC3, AC5: перетирание ручной роли и журнал -------------------------

    def test_manual_role_is_overwritten_and_audited(self, processor, customer_with_opt4):
        """AC3/AC5: 1С — источник истины, прежняя роль уходит в AuditLog."""
        from apps.common.models import AuditLog

        existing = self._linked_account(customer_with_opt4["onec_id"], "wholesale_level3", "manual-role@example.com")

        user = processor.process_customer(dict(customer_with_opt4))

        assert user.pk == existing.pk
        assert user.role == "wholesale_level4"

        logs = AuditLog.objects.filter(action="role_from_1c")
        assert logs.count() == 1

        log = logs.first()
        assert log.user is None
        assert log.resource_type == "User"
        assert log.resource_id == str(user.pk)
        assert log.changes["previous_role"] == "wholesale_level3"
        assert log.changes["new_role"] == "wholesale_level4"
        assert log.changes["price_type_id"] == OPT4_GUID
        assert log.changes["price_type_name"]
        assert log.changes["agreement_name"]

    # -- AC6: идемпотентность ----------------------------------------------

    def test_actual_role_is_not_rewritten(self, processor, customer_with_opt4):
        """AC6: роль уже совпадает — журнал не пишется, исход roles_already_actual."""
        from apps.common.models import AuditLog

        self._linked_account(customer_with_opt4["onec_id"], "wholesale_level4", "actual-role@example.com")

        user = processor.process_customer(dict(customer_with_opt4))

        assert user.role == "wholesale_level4"
        assert processor.last_role_outcome == "roles_already_actual"
        assert AuditLog.objects.count() == 0

    def test_repeated_run_does_not_multiply_audit_records(self, processor, customer_with_opt4):
        """AC6: повторный прогон той же выгрузки не дёргает роль и не плодит журнал."""
        from apps.common.models import AuditLog

        self._linked_account(customer_with_opt4["onec_id"], "wholesale_level3", "repeat-role@example.com")

        first = processor.process_customer(dict(customer_with_opt4))
        assert first.role == "wholesale_level4"
        assert AuditLog.objects.filter(action="role_from_1c").count() == 1

        second = processor.process_customer(dict(customer_with_opt4))

        assert second.role == "wholesale_level4"
        assert processor.last_role_outcome == "roles_already_actual"
        assert AuditLog.objects.filter(action="role_from_1c").count() == 1

    # -- AC11: вид цен не даёт роли ----------------------------------------

    def test_unknown_price_type_leaves_role(self, processor, customer_with_price_type):
        """AC11: GUID, которого нет в справочнике, роль не меняет."""
        from apps.products.models import PriceType

        guid = customer_with_price_type["price_type_ids"][0]
        assert not PriceType.objects.filter(onec_id__iexact=guid).exists()
        existing = self._linked_account(
            customer_with_price_type["onec_id"], "wholesale_level1", "unknown-pt@example.com"
        )

        user = processor.process_customer(dict(customer_with_price_type))

        assert user.pk == existing.pk
        assert user.role == "wholesale_level1"
        assert processor.last_role_outcome == "roles_skipped_unknown_price_type"

    def test_known_price_type_without_role_leaves_role(self, processor, customer_with_price_type):
        """AC11: РРЦ известен порталу, но роли не несёт — роль не меняется."""
        self._ensure_price_type(RRP_GUID, "РРЦ", "", "rrp")
        data = dict(customer_with_price_type)
        data["price_type_ids"] = [RRP_GUID]
        existing = self._linked_account(data["onec_id"], "wholesale_level1", "rrp-pt@example.com")

        user = processor.process_customer(data)

        assert user.pk == existing.pk
        assert user.role == "wholesale_level1"
        assert processor.last_role_outcome == "roles_skipped_unknown_price_type"

    # -- AC12: несколько видов цен -----------------------------------------

    def test_ambiguous_price_types_leave_role(self, processor, customer_with_price_type):
        """AC12: два вида цен, каждый с ролью — роль не меняется."""
        self._ensure_price_type(OPT2_GUID, "Опт 2 (150-300 тыс.руб в квартал)", "wholesale_level2", "opt2_price")
        data = dict(customer_with_price_type)
        data["price_type_ids"] = [OPT4_GUID, OPT2_GUID]
        existing = self._linked_account(data["onec_id"], "wholesale_level1", "ambiguous-role@example.com")

        user = processor.process_customer(data)

        assert user.pk == existing.pk
        assert user.role == "wholesale_level1"
        assert processor.last_role_outcome == "roles_skipped_ambiguous"

    # -- AC13, AC14: нет данных / нет соглашения ---------------------------

    def test_missing_attributes_block_leaves_role(self, processor, customer_without_attributes_block):
        """AC13: блока <ЗначенияРеквизитов> нет — роль не меняется."""
        existing = self._linked_account(
            customer_without_attributes_block["onec_id"], "wholesale_level1", "no-block-role@example.com"
        )

        user = processor.process_customer(dict(customer_without_attributes_block))

        assert user.pk == existing.pk
        assert user.role == "wholesale_level1"
        assert processor.last_role_outcome == "roles_skipped_no_data"

    def test_no_agreement_leaves_role_and_clears_price_type(self, processor, customer_without_agreement):
        """
        AC14: снятие соглашения не означает «клиент больше не оптовик».

        Роль остаётся прежней, вид цен гасится по правилу 40.3.
        """
        existing = self._linked_account(
            customer_without_agreement["onec_id"], "wholesale_level1", "no-agreement-role@example.com"
        )
        existing.onec_price_type_id = OPT4_GUID
        existing.save(update_fields=["onec_price_type_id"])

        user = processor.process_customer(dict(customer_without_agreement))

        assert user.pk == existing.pk
        assert user.role == "wholesale_level1"
        assert user.onec_price_type_id == ""
        assert processor.last_role_outcome == "roles_skipped_no_agreement"

    # -- AC17: справочник читается один раз на сессию ----------------------

    def test_role_map_is_read_once_per_session(self, processor):
        """AC17: property role_map кэшируется на экземпляре процессора."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as ctx:
            first = processor.role_map
            second = processor.role_map

        assert first is second
        price_type_queries = [q for q in ctx.captured_queries if "price_types" in q["sql"]]
        assert len(price_type_queries) == 1

    def test_batch_reads_price_types_once(self, processor, customer_with_opt4):
        """AC17: пакет из 20+ контрагентов не порождает запрос на контрагента."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        customers = []
        for i in range(20):
            data = dict(customer_with_opt4)
            data["onec_id"] = f"ROLE-BATCH-{i:03d}"
            data["email"] = f"role-batch-{i:03d}@example.com"
            customers.append(data)
            self._linked_account(data["onec_id"], "wholesale_level1", f"linked-batch-{i:03d}@example.com")

        with CaptureQueriesContext(connection) as ctx:
            processor.process_customers(customers)

        price_type_queries = [q for q in ctx.captured_queries if "price_types" in q["sql"]]
        assert len(price_type_queries) == 1

    # -- AC7, AC8, AC9, AC10: счётчики отчёта ------------------------------

    def test_role_counters_cover_every_updated_record(self, processor, real_customers, customer_with_opt4):
        """
        AC10: исходы взаимно исключающие, сумма равна числу обновлённых.

        AC8: roles_updated разложен на два слагаемых.
        """
        buyers = [dict(data) for data in real_customers if "Покупатель" in str(data.get("role") or "")][:30]
        assert buyers, "В снимке нет контрагентов-покупателей"

        # Первый прогон создаёт записи, второй — обновляет их: ролевые
        # счётчики считают только обновления.
        processor.process_customers([dict(data) for data in buyers])

        # Один аккаунт делаем привязанным, чтобы ветка roles_updated_* была
        # покрыта наравне с пропусками.
        linked_source = dict(customer_with_opt4)
        linked_source["onec_id"] = "ROLE-COUNTER-LINKED"
        linked_source["email"] = "role-counter-linked@example.com"
        self._linked_account("ROLE-COUNTER-LINKED", "wholesale_level1", "linked-counter@example.com")

        stats = processor.process_customers([dict(data) for data in buyers] + [linked_source])

        role_outcomes = sum(
            stats[key]
            for key in (
                "roles_updated",
                "roles_already_actual",
                "roles_skipped_unlinked_record",
                "roles_skipped_no_data",
                "roles_skipped_no_agreement",
                "roles_skipped_unknown_price_type",
                "roles_skipped_ambiguous",
            )
        )
        assert role_outcomes == stats["updated"]
        assert stats["roles_updated"] == (
            stats["roles_updated_from_unregistered"] + stats["roles_updated_from_assigned"]
        )
        assert stats["roles_updated_from_assigned"] == 1
        assert stats["roles_skipped_unlinked_record"] > 0

    def test_stats_contain_all_role_keys(self, processor, customer_with_opt4):
        """AC7/AC9: process_customers отдаёт весь набор ролевых счётчиков."""
        from apps.users.services.processor import ROLE_STATS_KEYS

        stats = processor.process_customers([dict(customer_with_opt4)])

        for key in ROLE_STATS_KEYS:
            assert key in stats, f"В статистике нет ключа {key}"

    def test_created_records_do_not_touch_role_counters(self, processor, customer_with_opt4):
        """AC10: у созданной записи роль не разрешается — счётчики нулевые."""
        from apps.users.services.processor import ROLE_STATS_KEYS

        stats = processor.process_customers([dict(customer_with_opt4)])

        assert stats["created"] == 1
        assert stats["updated"] == 0
        assert all(stats[key] == 0 for key in ROLE_STATS_KEYS)

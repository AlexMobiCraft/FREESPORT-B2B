"""
Unit-тесты сервиса связывания B2B-заявки с контрагентом 1С.

Покрывают I/O-матрицу спеки: перенос идентификаторов и реквизитов, обе ветки
customer_code, onec_guid=None, отказы и двойную отправку формы.
"""

from __future__ import annotations

import itertools
import time
import uuid
from unittest.mock import patch

import pytest

from apps.common.models import AuditLog
from apps.products.models import PriceType
from apps.users.models import Company, User
from apps.users.services.link_1c_customer import (
    LinkCandidateError,
    SourceNotLinkableError,
    TargetAlreadyLinkedError,
    find_link_candidates,
    link_1c_customer,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

_counter = itertools.count()


def unique_suffix() -> str:
    return f"{time.time_ns()}_{next(_counter)}"


def unique_tax_id() -> str:
    return str(1000000000 + ((time.time_ns() + next(_counter) * 7919) % 900000000))


def make_1c_record(tax_id: str, **overrides) -> User:
    """Контрагент, импортированный из 1С и не заведённый на портале."""
    defaults = {
        "email": f"1c_{unique_suffix()}@example.com",
        "first_name": "Контрагент",
        "last_name": "Из1С",
        "company_name": "ООО Импортированное",
        "tax_id": tax_id,
        "role": User.ROLE_UNREGISTERED,
        "created_in_1c": True,
        "verification_status": "unverified",
        "onec_id": f"1C-{unique_suffix()}",
        # Импорт оставляет пустой пароль — войти по такой записи нельзя.
        "password": "",
    }
    defaults.update(overrides)
    record = User(**defaults)
    record.save()
    return record


def make_applicant(tax_id: str, **overrides) -> User:
    """B2B-заявка, созданная регистрацией на портале."""
    defaults = {
        "email": f"applicant_{unique_suffix()}@example.com",
        "first_name": "Заявитель",
        "last_name": "Портальный",
        "role": "wholesale_level1",
        "company_name": "Форма Компани",
        "tax_id": tax_id,
        "verification_status": "pending",
    }
    defaults.update(overrides)
    password = defaults.pop("password", "StrongPassword123!")
    return User.objects.create_user(password=password, **defaults)


class TestFindLinkCandidates:
    def test_returns_unlinked_1c_records_with_same_tax_id(self):
        tax_id = unique_tax_id()
        record = make_1c_record(tax_id)
        applicant = make_applicant(tax_id)

        assert find_link_candidates(applicant) == [record]

    def test_returns_all_candidates_for_shared_tax_id(self):
        """На один ИНН в 1С приходятся десятки контрагентов — нужны все."""
        tax_id = unique_tax_id()
        records = [make_1c_record(tax_id) for _ in range(3)]
        applicant = make_applicant(tax_id)

        assert find_link_candidates(applicant) == records

    def test_empty_tax_id_returns_empty_list(self):
        applicant = make_applicant("")

        assert find_link_candidates(applicant) == []

    def test_excludes_live_accounts(self):
        """Живой аккаунт с тем же ИНН источником быть не может."""
        tax_id = unique_tax_id()
        make_applicant(tax_id)
        applicant = make_applicant(tax_id)

        assert find_link_candidates(applicant) == []

    def test_excludes_deactivated_records(self):
        tax_id = unique_tax_id()
        make_1c_record(tax_id, is_active=False)
        applicant = make_applicant(tax_id)

        assert find_link_candidates(applicant) == []

    def test_excludes_self(self):
        tax_id = unique_tax_id()
        record = make_1c_record(tax_id)

        assert find_link_candidates(record) == []

    def test_includes_record_with_unusable_password(self):
        """create_user(password=None) пишет '!<случайное>' — это тоже «войти нельзя»."""
        tax_id = unique_tax_id()
        record = make_1c_record(tax_id)
        record.set_password(None)
        record.save(update_fields=["password"])
        applicant = make_applicant(tax_id)

        assert find_link_candidates(applicant) == [record]


class TestLink1CCustomer:
    def test_transfers_identifiers_and_requisites(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_guid=uuid.uuid4())
        Company.objects.create(
            user=source,
            legal_name="ООО Полное Наименование",
            tax_id=tax_id,
            kpp="770101001",
            legal_address="г. Москва, ул. Тестовая, 1",
        )
        target = make_applicant(tax_id)
        onec_id, onec_guid = source.onec_id, source.onec_guid

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=onec_id,
        )

        linked.refresh_from_db()
        source.refresh_from_db()
        assert linked.onec_id == onec_id
        assert linked.onec_guid == onec_guid
        assert linked.company_name == "ООО Импортированное"
        assert linked.tax_id == tax_id
        assert linked.company.legal_name == "ООО Полное Наименование"
        assert linked.company.kpp == "770101001"
        assert linked.company.legal_address == "г. Москва, ул. Тестовая, 1"
        assert source.onec_id is None
        assert source.onec_guid is None
        assert source.is_active is False

    def test_survives_null_onec_guid(self):
        """Импорт onec_guid не заполняет — перенос обязан это переживать."""
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_guid=None)
        target = make_applicant(tax_id)

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert linked.onec_guid is None
        assert linked.onec_id == source.onec_id

    def test_writes_audit_log(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        actor = User.objects.create_superuser(
            email=f"manager_{unique_suffix()}@example.com",
            password="StrongPassword123!",
            first_name="Менеджер",
            last_name="Тестов",
        )

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
            actor=actor,
            ip_address="10.0.0.1",
            user_agent="pytest",
        )

        entry = AuditLog.objects.get(action="link_1c_customer")
        assert entry.user == actor
        assert entry.resource_type == "User"
        assert entry.resource_id == str(target.pk)
        assert entry.changes["target_id"] == target.pk
        assert entry.changes["source_id"] == source.pk
        assert "onec_id" in entry.changes["transferred_fields"]

    def test_actor_is_optional_for_shell_usage(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert AuditLog.objects.get(action="link_1c_customer").user is None

    def test_creates_company_when_target_has_none(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        Company.objects.create(user=source, legal_name="ИП Тестов", tax_id=tax_id)
        target = make_applicant(tax_id)
        assert Company.objects.filter(user=target).count() == 0

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert Company.objects.get(user=target).legal_name == "ИП Тестов"

    def test_empty_source_requisites_do_not_wipe_target(self):
        """
        Выгрузка 1С не заполняет КПП и адрес для ИП и физлиц. Привязка
        необратима, поэтому затирать ими данные заявителя нельзя.
        """
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        Company.objects.create(user=source, legal_name="ИП Из 1С", tax_id=tax_id, kpp="", legal_address="")
        target = make_applicant(tax_id)
        Company.objects.create(
            user=target,
            legal_name="Форма Компани",
            tax_id=tax_id,
            kpp="770101001",
            legal_address="г. Москва, ул. Лесная, 5",
        )

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        company = Company.objects.get(user=target)
        assert company.legal_name == "ИП Из 1С"
        assert company.kpp == "770101001"
        assert company.legal_address == "г. Москва, ул. Лесная, 5"

    def test_audit_log_records_previous_values_and_real_changes(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, company_name="ООО Из 1С")
        Company.objects.create(user=source, legal_name="ООО Из 1С полное", tax_id=tax_id)
        target = make_applicant(tax_id, company_name="Форма Компани")

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        changes = AuditLog.objects.get(action="link_1c_customer").changes
        assert changes["previous_values"]["company_name"] == "Форма Компани"
        assert "company_name" in changes["transferred_fields"]
        assert "company.legal_name" in changes["transferred_fields"]
        # tax_id совпадал — переносить было нечего, и аудит этого не утверждает.
        assert "tax_id" not in changes["transferred_fields"]

    def test_tax_id_with_whitespace_is_linkable(self):
        """
        Поиск кандидатов и сверка под блокировкой используют одно правило
        нормализации: иначе заявка залипает — кандидат показан, привязка падает.
        """
        tax_id = unique_tax_id()
        source = make_1c_record(f" {tax_id} ")
        target = make_applicant(tax_id)

        assert find_link_candidates(target) == []

        source.tax_id = tax_id
        source.save(update_fields=["tax_id"])
        target.tax_id = f"{tax_id} "
        target.save(update_fields=["tax_id"])

        assert find_link_candidates(target) == [source]
        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )
        assert linked.onec_id == source.onec_id

    def test_source_without_company_leaves_target_company_untouched(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert Company.objects.filter(user=target).count() == 0

    def test_customer_code_transferred_when_target_has_none(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, customer_code="12345")
        target = make_applicant(tax_id)

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        source.refresh_from_db()
        assert linked.customer_code == "12345"
        assert source.customer_code is None

    def test_customer_code_of_target_is_never_overwritten(self):
        """Код заявителя уже вшит в номера его заказов."""
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, customer_code="12345")
        target = make_applicant(tax_id, customer_code="54321")

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        source.refresh_from_db()
        assert linked.customer_code == "54321"
        assert source.customer_code == "12345"

    def test_does_not_touch_identity_fields_of_target(self):
        """
        ⚠️ Роль здесь сохраняется не «по правилу», а по данным: с 40.5 привязка
        выводит роль из перенесённого вида цен, а `make_1c_record` его не задаёт
        (`onec_price_type_id=""` → резолвер отвечает `no_data` → роль не меняется).
        Ассерт про `role` остаётся осмысленным как проверка ветки «вида цен нет»;
        утверждения про email, password, verification_status и is_active — это
        по-прежнему безусловный запрет спеки, ослаблять их нельзя.
        """
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        email, role, status, password = target.email, target.role, target.verification_status, target.password

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert (linked.email, linked.role, linked.verification_status) == (email, role, status)
        assert linked.password == password
        assert linked.is_active is target.is_active


class TestLinkAppliesPriceTypeAndRole:
    """
    Привязка переносит вид цен из соглашения 1С и выводит из него роль (FR-40-11).

    До стори 40.5 роль приезжала только следующим обменом: менеджер связывал
    заявку, а клиент до ближайшего импорта видел чужой уровень цен.
    """

    # GUID из реального снимка contragents_pricetype/. «Опт 4» засеян
    # миграцией products/0053, РРЦ — нет; оба заводятся через get_or_create,
    # потому что тестовая БД строится С миграциями (create даст duplicate key).
    OPT4_GUID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"
    RRP_GUID = "3d1482c4-bd77-11e4-afc8-20cf3073dde3"

    @staticmethod
    def ensure_price_type(onec_id: str, user_role: str, *, product_field: str = "opt4_price") -> PriceType:
        """
        Вид цен в справочнике с нужной ролью — независимо от того, засеян он миграцией или нет.

        ``is_active`` довзводится наравне с ``user_role``: ``defaults``
        применяются только при создании, а ``load_price_type_role_map``
        читает исключительно активные записи. Иначе тест зависел бы от
        состояния справочника в тестовой БД и мог бы упасть ложно.
        """
        price_type, _ = PriceType.objects.get_or_create(
            onec_id=onec_id,
            defaults={
                "onec_name": f"Вид цен {onec_id[:8]}",
                "product_field": product_field,
                "user_role": user_role,
                "is_active": True,
            },
        )
        stale_fields = []
        if price_type.user_role != user_role:
            price_type.user_role = user_role
            stale_fields.append("user_role")
        if not price_type.is_active:
            price_type.is_active = True
            stale_fields.append("is_active")
        if stale_fields:
            price_type.save(update_fields=stale_fields)
        return price_type

    def test_transfers_price_type_and_applies_resolved_role(self):
        """AC1, AC3, AC4: вид цен перенесён, роль выведена из него — в одной транзакции."""
        price_type = self.ensure_price_type(self.OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=self.OPT4_GUID)
        target = make_applicant(tax_id, role="wholesale_level1")

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        assert linked.onec_price_type_id == self.OPT4_GUID
        assert linked.role == price_type.user_role == "wholesale_level4"
        # refresh_from_db доказывает, что оба поля попали в update_fields,
        # а не остались изменёнными только в памяти.
        linked.refresh_from_db()
        assert linked.onec_price_type_id == self.OPT4_GUID
        assert linked.role == "wholesale_level4"

    def test_empty_source_price_type_does_not_wipe_target(self):
        """
        AC2: пустое значение источника не затирает вид цен цели и роль не меняет.

        У цели вид цен намеренно непустой: на пустой цели ассерт не отличал бы
        «не затёрли» от «затёрли пустым». GUID взят «говорящий» — «Опт 4» даёт
        wholesale_level4, и сохранение роли wholesale_level2 заодно доказывает,
        что резолвер читает источник, а не уже присвоенное значение цели.
        """
        self.ensure_price_type(self.OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id="")
        target = make_applicant(tax_id, role="wholesale_level2", onec_price_type_id=self.OPT4_GUID)

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        linked.refresh_from_db()
        assert linked.onec_price_type_id == self.OPT4_GUID
        assert linked.role == "wholesale_level2"
        assert linked.onec_id is not None

        changes = AuditLog.objects.get(action="link_1c_customer").changes
        assert "onec_price_type_id" not in changes["transferred_fields"]
        assert "role" not in changes["transferred_fields"]
        assert changes["previous_values"]["onec_price_type_id"] == self.OPT4_GUID

    def test_unknown_price_type_transfers_field_but_keeps_role(self):
        """
        AC5: GUID неизвестен справочнику → роль не меняется, но вид цен перенесён.

        Перенос и применение роли независимы: менеджер должен видеть в карточке,
        какой вид цен пришёл из 1С, даже если справочник его ещё не знает.
        """
        guid = f"unknown-{uuid.uuid4()}"
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=guid)
        target = make_applicant(tax_id, role="wholesale_level1")

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        linked.refresh_from_db()
        assert linked.onec_price_type_id == guid
        assert linked.role == "wholesale_level1"

    def test_known_price_type_without_role_keeps_role(self):
        """
        AC5: вид цен известен, но роли не несёт (РРЦ, МРЦ) — та же ветка unknown_price_type.

        Такие виды цен не попадают в маппинг вовсе: иначе маркетплейсы на РРЦ
        уехали бы в retail.
        """
        self.ensure_price_type(self.RRP_GUID, "", product_field="rrp")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=self.RRP_GUID)
        target = make_applicant(tax_id, role="wholesale_level1")

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        linked.refresh_from_db()
        assert linked.onec_price_type_id == self.RRP_GUID
        assert linked.role == "wholesale_level1"

    def test_non_b2b_resolved_role_is_not_applied(self):
        """
        AC6: не-B2B роль из справочника не применяется, привязка при этом выполняется.

        Сценарий реален: PriceTypeAdminForm предлагает менеджеру весь
        ROLE_CHOICES. Применённый retail выбил бы аккаунт из link_target_q(),
        is_b2b_user и всех B2B-сценариев разом.
        """
        price_type = self.ensure_price_type(f"retail-{uuid.uuid4()}", "retail", product_field="retail_price")
        assert price_type.user_role not in User.B2B_ROLES
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=price_type.onec_id)
        target = make_applicant(tax_id, role="wholesale_level1")

        linked = link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        linked.refresh_from_db()
        assert linked.role == "wholesale_level1"
        assert linked.onec_price_type_id == price_type.onec_id
        assert linked.onec_id is not None

    def test_audit_log_records_role_change_and_previous_values(self):
        """AC7, AC8, AC9: смена роли и перенос вида цен попадают в журнал вместе с «что было»."""
        self.ensure_price_type(self.OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=self.OPT4_GUID)
        target = make_applicant(tax_id, role="wholesale_level1")

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        changes = AuditLog.objects.get(action="link_1c_customer").changes
        assert "role" in changes["transferred_fields"]
        assert "onec_price_type_id" in changes["transferred_fields"]
        assert changes["previous_values"]["role"] == "wholesale_level1"
        assert changes["previous_values"]["onec_price_type_id"] == ""

    def test_unchanged_role_is_not_listed_as_transferred(self):
        """
        AC7: список перенесённых полей отражает реальные изменения.

        Прежняя роль при этом всё равно записана: previous_values пишется
        безусловно — привязка необратима.
        """
        self.ensure_price_type(self.OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=self.OPT4_GUID)
        target = make_applicant(tax_id, role="wholesale_level4")

        link_1c_customer(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
        )

        changes = AuditLog.objects.get(action="link_1c_customer").changes
        assert "role" not in changes["transferred_fields"]
        assert "onec_price_type_id" in changes["transferred_fields"]
        assert changes["previous_values"]["role"] == "wholesale_level4"

    def test_failure_after_role_applied_rolls_back_everything(self):
        """
        AC11: сбой после применения роли откатывает и роль, и вид цен.

        Частичное состояние здесь опаснее отказа: у цели была бы роль из 1С
        без идентификаторов, а у источника — идентификаторы при is_active=False.
        """
        self.ensure_price_type(self.OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=self.OPT4_GUID)
        target = make_applicant(tax_id, role="wholesale_level1")
        onec_id = source.onec_id

        with patch(
            "apps.users.services.link_1c_customer.AuditLog.log_action",
            side_effect=RuntimeError("сбой на последнем шаге"),
        ):
            with pytest.raises(RuntimeError):
                link_1c_customer(
                    target_id=target.pk,
                    source_id=source.pk,
                    expected_onec_id=onec_id,
                )

        target.refresh_from_db()
        source.refresh_from_db()
        assert target.role == "wholesale_level1"
        assert target.onec_price_type_id == ""
        assert source.onec_id == onec_id
        assert source.is_active is True


class TestLink1CCustomerRefusals:
    def test_target_with_onec_id_is_rejected(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id, onec_id=f"1C-target-{unique_suffix()}")

        with pytest.raises(TargetAlreadyLinkedError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id=source.onec_id,
            )

        source.refresh_from_db()
        assert source.onec_id is not None
        assert source.is_active is True

    def test_target_with_only_onec_guid_is_rejected(self):
        """Признак «уже несёт идентичность 1С» — любой из двух идентификаторов."""
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id, onec_guid=uuid.uuid4())

        with pytest.raises(TargetAlreadyLinkedError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id=source.onec_id,
            )

    @pytest.mark.parametrize("role", ["retail", User.ROLE_UNREGISTERED, "admin"])
    def test_non_b2b_target_is_rejected(self, role):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id, role=role)

        with pytest.raises(LinkCandidateError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id=source.onec_id,
            )

        source.refresh_from_db()
        assert source.onec_id is not None

    def test_live_account_as_source_is_rejected(self):
        tax_id = unique_tax_id()
        source = make_applicant(tax_id, onec_id=f"1C-live-{unique_suffix()}")
        target = make_applicant(tax_id)

        with pytest.raises(SourceNotLinkableError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id=source.onec_id,
            )

    def test_stale_expected_onec_id_is_rejected(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        with pytest.raises(SourceNotLinkableError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id="1C-устаревший",
            )

        target.refresh_from_db()
        assert target.onec_id is None

    def test_tax_id_mismatch_is_rejected(self):
        source = make_1c_record(unique_tax_id())
        target = make_applicant(unique_tax_id())

        with pytest.raises(SourceNotLinkableError):
            link_1c_customer(
                target_id=target.pk,
                source_id=source.pk,
                expected_onec_id=source.onec_id,
            )

    def test_double_submit_is_rejected_without_partial_write(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        onec_id = source.onec_id

        link_1c_customer(target_id=target.pk, source_id=source.pk, expected_onec_id=onec_id)

        with pytest.raises(LinkCandidateError):
            link_1c_customer(target_id=target.pk, source_id=source.pk, expected_onec_id=onec_id)

        target.refresh_from_db()
        source.refresh_from_db()
        assert target.onec_id == onec_id
        assert source.onec_id is None
        assert AuditLog.objects.filter(action="link_1c_customer").count() == 1

    def test_failure_mid_transfer_rolls_back_both_rows(self):
        """
        Откат обязан вернуть обе записи в исходное состояние: иначе останется
        источник со снятым onec_id и цель без него — идентичность 1С потеряна.
        """
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        onec_id = source.onec_id

        with patch(
            "apps.users.services.link_1c_customer.AuditLog.log_action",
            side_effect=RuntimeError("сбой на последнем шаге"),
        ):
            with pytest.raises(RuntimeError):
                link_1c_customer(
                    target_id=target.pk,
                    source_id=source.pk,
                    expected_onec_id=onec_id,
                )

        source.refresh_from_db()
        target.refresh_from_db()
        assert source.onec_id == onec_id
        assert source.is_active is True
        assert target.onec_id is None
        assert not AuditLog.objects.filter(action="link_1c_customer").exists()

    def test_self_link_is_rejected(self):
        record = make_1c_record(unique_tax_id())

        with pytest.raises(LinkCandidateError):
            link_1c_customer(
                target_id=record.pk,
                source_id=record.pk,
                expected_onec_id=record.onec_id,
            )

    def test_missing_source_is_rejected(self):
        target = make_applicant(unique_tax_id())

        with pytest.raises(SourceNotLinkableError):
            link_1c_customer(target_id=target.pk, source_id=10**9, expected_onec_id="")

    def test_source_without_identifiers_is_rejected(self):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_id=None, onec_guid=None)
        target = make_applicant(tax_id)

        with pytest.raises(SourceNotLinkableError):
            link_1c_customer(target_id=target.pk, source_id=source.pk, expected_onec_id="")

"""
Unit-тесты сервиса подтверждения и отклонения B2B-заявки.

Покрывают каждую ветку I/O-матрицы спеки spec-admin-b2b-verification-card:
привязку с ролью из 1С и ролью менеджера, подтверждение без привязки,
уже связанную заявку, режим «только привязка», отказы под блокировкой,
откаты и отсутствие письма о верификации при откате.
"""

from __future__ import annotations

import itertools
import time
import uuid
from unittest.mock import patch

import pytest

from apps.common.models import AuditLog
from apps.products.models import PriceType
from apps.users.models import User
from apps.users.services.link_1c_customer import LinkCandidateError
from apps.users.services.verify_b2b_application import (
    MODE_DECISION,
    MODE_LINK_ONLY,
    NO_1C_LINK,
    ROLE_SOURCE_1C,
    ROLE_SOURCE_MANAGER,
    VerificationError,
    reject_b2b_application,
    verify_b2b_application,
)

pytestmark = [pytest.mark.unit, pytest.mark.django_db]

_counter = itertools.count()

# GUID «Опт 4» из реального снимка contragents_pricetype/ (засеян миграцией
# products/0053) — заводится через get_or_create: тестовая БД строится с миграциями.
OPT4_GUID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"
UNKNOWN_GUID = "00000000-0000-0000-0000-00000000dead"


def unique_suffix() -> str:
    return f"{time.time_ns()}_{next(_counter)}"


def unique_tax_id() -> str:
    return str(1000000000 + ((time.time_ns() + next(_counter) * 7919) % 900000000))


def ensure_price_type(onec_id: str, user_role: str) -> PriceType:
    price_type, _ = PriceType.objects.get_or_create(
        onec_id=onec_id,
        defaults={
            "onec_name": f"Вид цен {onec_id[:8]}",
            "product_field": "opt4_price",
            "user_role": user_role,
            "is_active": True,
        },
    )
    if price_type.user_role != user_role or not price_type.is_active:
        price_type.user_role = user_role
        price_type.is_active = True
        price_type.save(update_fields=["user_role", "is_active"])
    return price_type


def make_1c_record(tax_id: str, **overrides) -> User:
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
        "password": "",
    }
    defaults.update(overrides)
    record = User(**defaults)
    record.save()
    return record


def make_applicant(tax_id: str | None = None, **overrides) -> User:
    defaults = {
        "email": f"applicant_{unique_suffix()}@example.com",
        "first_name": "Заявитель",
        "last_name": "Портальный",
        "role": "wholesale_level1",
        "company_name": "Форма Компани",
        "tax_id": tax_id or unique_tax_id(),
        "verification_status": "pending",
        "is_active": False,
    }
    defaults.update(overrides)
    return User.objects.create_user(password="StrongPassword123!", **defaults)


@pytest.fixture(autouse=True)
def verified_email_task():
    """Письмо о верификации ставится в очередь сигналом — следим за .delay."""
    with patch("apps.users.signals.send_user_verified_email") as task:
        yield task


@pytest.fixture
def actor():
    return User.objects.create_superuser(
        email=f"manager_{unique_suffix()}@example.com",
        password="StrongPassword123!",
        first_name="Менеджер",
        last_name="Тестов",
    )


def assert_untouched(target: User, *, status: str = "pending", role: str = "wholesale_level1") -> None:
    target.refresh_from_db()
    assert target.verification_status == status
    assert target.is_verified is (status == "verified")
    assert target.role == role
    assert not target.onec_id


class TestVerifyWithLink:
    def test_single_candidate_role_from_1c_price_type(self, actor, verified_email_task):
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID)
        target = make_applicant(tax_id)

        result = verify_b2b_application(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=source.onec_id,
            # Выбор менеджера не применяется: вид цен разрешился в B2B-роль.
            role="wholesale_level2",
            actor=actor,
            ip_address="127.0.0.1",
        )

        target.refresh_from_db()
        source.refresh_from_db()
        assert result.linked is True
        assert result.mode == MODE_DECISION
        assert target.onec_id == result.user.onec_id and target.onec_id
        assert source.is_active is False
        assert target.role == "wholesale_level4"
        assert target.is_verified is True
        assert target.verification_status == "verified"
        assert target.is_active is True

        link_entry = AuditLog.objects.get(action="link_1c_customer")
        verify_entry = AuditLog.objects.get(action="verify_b2b")
        assert link_entry.user == actor
        assert verify_entry.user == actor
        assert verify_entry.changes["role_before"] == "wholesale_level1"
        assert verify_entry.changes["role_after"] == "wholesale_level4"
        assert verify_entry.changes["role_source"] == ROLE_SOURCE_1C
        assert verify_entry.changes["onec_id"] == target.onec_id
        verified_email_task.delay.assert_called_once_with(target.pk)

    def test_unresolved_price_type_applies_manager_role(self, actor):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=UNKNOWN_GUID)
        target = make_applicant(tax_id)
        onec_id = source.onec_id

        result = verify_b2b_application(
            target_id=target.pk,
            source_id=source.pk,
            expected_onec_id=onec_id,
            role="wholesale_level3",
            actor=actor,
        )

        target.refresh_from_db()
        assert result.role_source == ROLE_SOURCE_MANAGER
        assert target.role == "wholesale_level3"
        assert target.onec_id == onec_id
        assert AuditLog.objects.get(action="verify_b2b").changes["role_source"] == ROLE_SOURCE_MANAGER

    def test_role_none_keeps_current_role(self, actor):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id, role="trainer")

        result = verify_b2b_application(
            target_id=target.pk, source_id=source.pk, expected_onec_id=source.onec_id, actor=actor
        )

        assert result.role_after == "trainer"
        target.refresh_from_db()
        assert target.role == "trainer"

    def test_source_customer_code_is_returned_for_mismatch_warning(self, actor):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, customer_code="54321")
        target = make_applicant(tax_id, customer_code="12345")

        result = verify_b2b_application(
            target_id=target.pk, source_id=source.pk, expected_onec_id=source.onec_id, actor=actor
        )

        assert result.source_customer_code == "54321"
        assert result.user.customer_code == "12345"

    def test_does_not_touch_sync_and_staff_fields(self, actor):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        before = User.objects.values("created_in_1c", "sync_status", "is_staff", "is_superuser").get(pk=target.pk)

        verify_b2b_application(target_id=target.pk, source_id=source.pk, expected_onec_id=source.onec_id, actor=actor)

        after = User.objects.values("created_in_1c", "sync_status", "is_staff", "is_superuser").get(pk=target.pk)
        assert after == before


class TestVerifyWithoutLink:
    def test_no_candidates_requires_explicit_confirmation(self, actor, verified_email_task):
        target = make_applicant()

        with pytest.raises(VerificationError, match="без привязки"):
            verify_b2b_application(target_id=target.pk, source_id=None, actor=actor)

        assert_untouched(target)
        assert not AuditLog.objects.filter(action="verify_b2b").exists()
        verified_email_task.delay.assert_not_called()

    def test_no_candidates_confirmed_without_1c(self, actor):
        target = make_applicant()

        result = verify_b2b_application(
            target_id=target.pk, source_id=None, role="federation_rep", confirm_without_1c=True, actor=actor
        )

        target.refresh_from_db()
        assert result.linked is False
        assert target.verification_status == "verified"
        assert target.is_active is True
        assert target.role == "federation_rep"
        assert target.created_in_1c is False
        entry = AuditLog.objects.get(action="verify_b2b")
        assert entry.changes["onec_id"] == NO_1C_LINK
        assert not AuditLog.objects.filter(action="link_1c_customer").exists()

    def test_already_linked_pending_needs_no_second_checkbox(self, actor):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)  # кандидат есть, но связанной цели он не показывается
        target = make_applicant(tax_id, onec_id=f"1C-own-{unique_suffix()}")

        result = verify_b2b_application(target_id=target.pk, source_id=None, actor=actor)

        target.refresh_from_db()
        assert result.linked is False
        assert target.verification_status == "verified"
        assert AuditLog.objects.get(action="verify_b2b").changes["onec_id"] == target.onec_id

    def test_linked_by_guid_only_is_logged_with_guid(self, actor):
        onec_guid = uuid.uuid4()
        target = make_applicant(onec_guid=onec_guid)

        result = verify_b2b_application(target_id=target.pk, source_id=None, actor=actor)

        assert result.linked is False
        assert AuditLog.objects.get(action="verify_b2b").changes["onec_id"] == str(onec_guid)

    def test_already_linked_role_follows_own_price_type(self, actor):
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        target = make_applicant(onec_id=f"1C-own-{unique_suffix()}", onec_price_type_id=OPT4_GUID)

        result = verify_b2b_application(target_id=target.pk, source_id=None, role="trainer", actor=actor)

        assert result.role_source == ROLE_SOURCE_1C
        target.refresh_from_db()
        assert target.role == "wholesale_level4"

    def test_stale_page_candidates_appeared(self, actor, verified_email_task):
        tax_id = unique_tax_id()
        target = make_applicant(tax_id)
        # Страница показала «кандидатов нет», а импорт успел завести контрагента.
        make_1c_record(tax_id)

        with pytest.raises(VerificationError, match="появились"):
            verify_b2b_application(target_id=target.pk, source_id=None, confirm_without_1c=True, actor=actor)

        assert_untouched(target)
        verified_email_task.delay.assert_not_called()


class TestLinkOnlyMode:
    def test_verified_unlinked_with_candidates_only_links(self, actor, verified_email_task):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        # Верифицирован, но заблокирован: привязка не должна его разблокировать.
        target = make_applicant(tax_id, verification_status="verified", is_verified=True, is_active=False)

        result = verify_b2b_application(
            target_id=target.pk, source_id=source.pk, expected_onec_id=source.onec_id, actor=actor
        )

        target.refresh_from_db()
        assert result.mode == MODE_LINK_ONLY
        assert target.onec_id
        assert target.is_active is False
        assert target.verification_status == "verified"
        assert AuditLog.objects.get(action="verify_b2b").changes["mode"] == MODE_LINK_ONLY
        verified_email_task.delay.assert_not_called()

    def test_reject_is_unavailable_in_link_only_mode(self, actor):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        target = make_applicant(tax_id, verification_status="verified", is_verified=True)

        with pytest.raises(VerificationError):
            reject_b2b_application(target_id=target.pk, actor=actor)

        target.refresh_from_db()
        assert target.verification_status == "verified"


class TestAccessRefusals:
    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"verification_status": "verified", "is_verified": True}, id="verified-no-candidates"),
            pytest.param(
                {"verification_status": "verified", "is_verified": True, "onec_id": "1C-linked"},
                id="verified-linked",
            ),
            pytest.param({"role": "retail"}, id="not-b2b"),
            pytest.param({"is_superuser": True, "is_staff": True}, id="superuser"),
        ],
    )
    def test_no_grounds(self, actor, overrides):
        if "onec_id" in overrides:
            overrides = {**overrides, "onec_id": f"1C-linked-{unique_suffix()}"}
        target = make_applicant(**overrides)

        with pytest.raises(VerificationError):
            verify_b2b_application(target_id=target.pk, source_id=None, confirm_without_1c=True, actor=actor)

        assert not AuditLog.objects.filter(action="verify_b2b").exists()

    def test_is_verified_flag_alone_does_not_block(self, actor):
        """Условие — verification_status: на проде флаги расходятся."""
        target = make_applicant(is_verified=True, verification_status="pending")

        verify_b2b_application(target_id=target.pk, source_id=None, confirm_without_1c=True, actor=actor)

        target.refresh_from_db()
        assert target.verification_status == "verified"

    def test_double_submit_is_rejected(self, actor, verified_email_task):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        kwargs = {"target_id": target.pk, "source_id": source.pk, "expected_onec_id": source.onec_id, "actor": actor}

        verify_b2b_application(**kwargs)
        # Повтор отсекается проверкой доступа под блокировкой, до link_1c_customer.
        with pytest.raises(VerificationError):
            verify_b2b_application(**kwargs)

        assert AuditLog.objects.filter(action="verify_b2b").count() == 1
        assert AuditLog.objects.filter(action="link_1c_customer").count() == 1
        verified_email_task.delay.assert_called_once()

    def test_source_not_among_candidates(self, actor):
        target = make_applicant()
        foreign = make_1c_record(unique_tax_id())

        with pytest.raises(VerificationError):
            verify_b2b_application(
                target_id=target.pk, source_id=foreign.pk, expected_onec_id=foreign.onec_id, actor=actor
            )

        assert_untouched(target)

    def test_stale_onec_id_rolls_back(self, actor, verified_email_task):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        with pytest.raises(LinkCandidateError):
            verify_b2b_application(
                target_id=target.pk, source_id=source.pk, expected_onec_id="1C-устаревший", actor=actor
            )

        assert_untouched(target)
        verified_email_task.delay.assert_not_called()


class TestRollback:
    @pytest.mark.parametrize("bad_role", ["retail", "admin", "unregistered", "nonsense"])
    def test_role_outside_b2b_roles_rolls_back_link(self, actor, verified_email_task, bad_role):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=UNKNOWN_GUID)
        target = make_applicant(tax_id)
        onec_id = source.onec_id

        with pytest.raises(VerificationError, match="B2B"):
            verify_b2b_application(
                target_id=target.pk, source_id=source.pk, expected_onec_id=onec_id, role=bad_role, actor=actor
            )

        assert_untouched(target)
        source.refresh_from_db()
        assert source.onec_id == onec_id
        assert source.is_active is True
        assert not AuditLog.objects.filter(action__in=["link_1c_customer", "verify_b2b"]).exists()
        verified_email_task.delay.assert_not_called()

    def test_failure_on_audit_log_rolls_back_everything_and_sends_no_email(self, actor, verified_email_task):
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID)
        target = make_applicant(tax_id)
        onec_id = source.onec_id
        original = AuditLog.log_action

        def failing_log_action(**kwargs):
            if kwargs.get("action") == "verify_b2b":
                raise RuntimeError("сбой при записи AuditLog")
            return original(**kwargs)

        with patch.object(AuditLog, "log_action", side_effect=failing_log_action):
            with pytest.raises(RuntimeError):
                verify_b2b_application(target_id=target.pk, source_id=source.pk, expected_onec_id=onec_id, actor=actor)

        target.refresh_from_db()
        source.refresh_from_db()
        assert target.verification_status == "pending"
        assert target.is_active is False
        assert target.role == "wholesale_level1"
        assert not target.onec_id
        assert target.onec_price_type_id == ""
        assert source.onec_id == onec_id
        assert source.is_active is True
        assert not AuditLog.objects.filter(action="link_1c_customer").exists()
        verified_email_task.delay.assert_not_called()


class TestReject:
    def test_reject_pending_application(self, actor, verified_email_task):
        target = make_applicant(role="trainer")

        reject_b2b_application(target_id=target.pk, actor=actor, ip_address="127.0.0.1")

        target.refresh_from_db()
        assert target.verification_status == "unverified"
        assert target.is_verified is False
        assert target.role == "trainer"
        assert target.is_active is False
        entry = AuditLog.objects.get(action="reject_b2b")
        assert entry.user == actor
        assert entry.changes["verified"] is False
        verified_email_task.delay.assert_not_called()

    def test_reject_keeps_existing_link(self, actor):
        onec_id = f"1C-own-{unique_suffix()}"
        target = make_applicant(onec_id=onec_id)

        reject_b2b_application(target_id=target.pk, actor=actor)

        target.refresh_from_db()
        assert target.onec_id == onec_id

    def test_reject_verified_is_refused(self, actor):
        target = make_applicant(verification_status="verified", is_verified=True)

        with pytest.raises(VerificationError):
            reject_b2b_application(target_id=target.pk, actor=actor)

        target.refresh_from_db()
        assert target.verification_status == "verified"
        assert not AuditLog.objects.filter(action="reject_b2b").exists()

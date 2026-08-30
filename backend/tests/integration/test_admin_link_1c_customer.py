"""
Integration-тесты HTTP-слоя привязки заявки к контрагенту 1С.

Покрывают права доступа, отказы, AuditLog, агрегированное предупреждение при
массовом одобрении и стоимость колонки-индикатора в changelist.
"""

from __future__ import annotations

import itertools
import time

import pytest
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import AuditLog
from apps.users.models import Company, User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

CHANGELIST_URL = reverse("admin:users_user_changelist")
ACTION_NAME = "link_1c_customer"

_counter = itertools.count()


def unique_suffix() -> str:
    return f"{time.time_ns()}_{next(_counter)}"


def unique_tax_id() -> str:
    return str(1000000000 + ((time.time_ns() + next(_counter) * 7919) % 900000000))


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


def make_applicant(**overrides) -> User:
    defaults = {
        "email": f"applicant_{unique_suffix()}@example.com",
        "first_name": "Заявитель",
        "last_name": "Портальный",
        "role": "wholesale_level1",
        "company_name": "Форма Компани",
        "tax_id": unique_tax_id(),
        "verification_status": "pending",
    }
    defaults.update(overrides)
    return User.objects.create_user(password="StrongPassword123!", **defaults)


@pytest.fixture
def manager(django_user_model):
    return django_user_model.objects.create_superuser(
        email=f"manager_{unique_suffix()}@example.com",
        password="StrongPassword123!",
        first_name="Менеджер",
        last_name="Тестов",
    )


@pytest.fixture
def manager_client(client, manager):
    client.force_login(manager)
    return client


def post_action(client, target: User, **extra):
    payload = {"action": ACTION_NAME, "_selected_action": [str(target.pk)]}
    payload.update(extra)
    return client.post(CHANGELIST_URL, payload, follow=True)


def message_texts(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


class TestLinkActionConfirmation:
    def test_confirmation_page_lists_candidates(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        Company.objects.create(user=source, legal_name="ООО Полное", tax_id=tax_id, legal_address="г. Москва")
        target = make_applicant(tax_id=tax_id)

        response = post_action(manager_client, target)

        content = response.content.decode()
        assert response.status_code == 200
        assert source.onec_id in content
        assert "ООО Импортированное" in content
        assert "г. Москва" in content
        assert target.email in content

    def test_link_transfers_identity_and_writes_audit_log(self, manager_client, manager):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id=tax_id)

        response = post_action(
            manager_client,
            target,
            apply="1",
            candidate=f"{source.pk}:{source.onec_id}",
        )

        target.refresh_from_db()
        source.refresh_from_db()
        assert response.status_code == 200
        assert target.onec_id is not None
        assert source.onec_id is None
        assert source.is_active is False

        entry = AuditLog.objects.get(action="link_1c_customer")
        assert entry.user == manager
        assert entry.changes["source_id"] == source.pk

    def test_double_submit_is_rejected(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id=tax_id)
        onec_id = source.onec_id

        post_action(manager_client, target, apply="1", candidate=f"{source.pk}:{onec_id}")
        response = post_action(manager_client, target, apply="1", candidate=f"{source.pk}:{onec_id}")

        target.refresh_from_db()
        assert target.onec_id == onec_id
        assert AuditLog.objects.filter(action="link_1c_customer").count() == 1
        assert any("уже связан" in text for text in message_texts(response))


class TestChangeFormCandidatesBlock:
    def test_card_shows_candidate_in_1c_block(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        Company.objects.create(user=source, legal_name="ООО Полное", tax_id=tax_id, legal_address="г. Москва")
        target = make_applicant(tax_id=tax_id)

        response = manager_client.get(reverse("admin:users_user_change", args=[target.pk]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "Непривязанные контрагенты 1С" in content
        assert source.onec_id in content
        assert "ООО Импортированное" in content
        assert "г. Москва" in content

    def test_card_hides_block_without_candidates(self, manager_client):
        target = make_applicant()

        response = manager_client.get(reverse("admin:users_user_change", args=[target.pk]))

        assert response.status_code == 200
        assert "Непривязанные контрагенты 1С" not in response.content.decode()

    def test_card_hides_block_for_ineligible_target(self, manager_client):
        """
        Блок не должен звать связать аккаунт, которому действие всегда откажет:
        карточка использует тот же критерий цели, что колонка и сервис.
        """
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        already_linked = make_applicant(tax_id=tax_id, onec_id=f"1C-target-{unique_suffix()}")
        not_b2b = make_applicant(tax_id=tax_id, role="retail")

        for user in (already_linked, not_b2b):
            response = manager_client.get(reverse("admin:users_user_change", args=[user.pk]))
            assert response.status_code == 200
            assert "Непривязанные контрагенты 1С" not in response.content.decode()


class TestLinkActionRefusals:
    def test_multiple_targets_are_rejected(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        first = make_applicant(tax_id=tax_id)
        second = make_applicant(tax_id=tax_id)

        response = manager_client.post(
            CHANGELIST_URL,
            {"action": ACTION_NAME, "_selected_action": [str(first.pk), str(second.pk)]},
            follow=True,
        )

        source.refresh_from_db()
        assert source.onec_id is not None
        assert any("по одной заявке" in text for text in message_texts(response))

    def test_non_b2b_target_is_rejected(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id=tax_id, role="retail")

        response = post_action(manager_client, target)

        source.refresh_from_db()
        assert source.onec_id is not None
        assert any("B2B" in text for text in message_texts(response))

    def test_target_without_candidates_gets_warning(self, manager_client):
        target = make_applicant()

        response = post_action(manager_client, target)

        assert any("не найдено" in text for text in message_texts(response))

    def test_action_requires_change_user_permission(self, client, django_user_model):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id=tax_id)
        viewer = django_user_model.objects.create_user(
            email=f"viewer_{unique_suffix()}@example.com",
            password="StrongPassword123!",
            first_name="Наблюдатель",
            last_name="Тестов",
            role="admin",
            is_staff=True,
        )
        viewer.user_permissions.add(Permission.objects.get(codename="view_user"))
        client.force_login(viewer)

        response = client.post(
            CHANGELIST_URL,
            {
                "action": ACTION_NAME,
                "_selected_action": [str(target.pk)],
                "apply": "1",
                "candidate": f"{source.pk}:{source.onec_id}",
            },
            follow=True,
        )

        target.refresh_from_db()
        source.refresh_from_db()
        assert target.onec_id is None
        assert source.onec_id is not None
        assert source.is_active is True
        assert not AuditLog.objects.filter(action="link_1c_customer").exists()
        assert response.status_code == 200

        # Позитивный контроль: тот же payload с правом change_user срабатывает.
        # Без него тест был бы зелёным и при полностью нерабочем действии
        # (например, при опечатке в имени в `actions`).
        viewer.user_permissions.add(Permission.objects.get(codename="change_user"))
        client.force_login(viewer)
        client.post(
            CHANGELIST_URL,
            {
                "action": ACTION_NAME,
                "_selected_action": [str(target.pk)],
                "apply": "1",
                "candidate": f"{source.pk}:{source.onec_id}",
            },
            follow=True,
        )

        target.refresh_from_db()
        assert target.onec_id is not None
        assert AuditLog.objects.filter(action="link_1c_customer").count() == 1


class TestApproveWarningAggregation:
    def test_single_aggregated_warning_for_batch(self, manager_client):
        with_candidates = []
        for _ in range(3):
            tax_id = unique_tax_id()
            make_1c_record(tax_id)
            with_candidates.append(make_applicant(tax_id=tax_id))
        without_candidates = [make_applicant() for _ in range(5)]
        selected = with_candidates + without_candidates

        response = manager_client.post(
            CHANGELIST_URL,
            {
                "action": "approve_b2b_users",
                "_selected_action": [str(user.pk) for user in selected],
            },
            follow=True,
        )

        for user in selected:
            user.refresh_from_db()
            assert user.is_verified is True

        warnings = [text for text in message_texts(response) if "непривязанные контрагенты 1С" in text]
        assert len(warnings) == 1
        for user in with_candidates:
            assert user.email in warnings[0]
        for user in without_candidates:
            assert user.email not in warnings[0]


class TestChangelistIndicatorCost:
    def test_query_count_does_not_grow_with_rows(self, manager_client, django_assert_num_queries):
        for _ in range(3):
            tax_id = unique_tax_id()
            make_1c_record(tax_id)
            make_applicant(tax_id=tax_id)

        with CaptureQueriesContext(connection) as captured:
            first = manager_client.get(CHANGELIST_URL)
        assert first.status_code == 200
        baseline = len(captured)

        for _ in range(12):
            tax_id = unique_tax_id()
            make_1c_record(tax_id)
            make_applicant(tax_id=tax_id)

        with django_assert_num_queries(baseline):
            second = manager_client.get(CHANGELIST_URL)
        assert second.status_code == 200

    def test_linked_application_leaves_the_queue(self, manager_client):
        """
        После привязки заявка обязана уйти из очереди: иначе фильтр копил бы
        уже обработанные строки и перестал быть рабочим списком.
        """
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id=tax_id)

        before = manager_client.get(CHANGELIST_URL, {"has_1c_candidate": "yes"})
        assert target in before.context["cl"].result_list

        post_action(manager_client, target, apply="1", candidate=f"{source.pk}:{source.onec_id}")

        after = manager_client.get(CHANGELIST_URL, {"has_1c_candidate": "yes"})
        assert target not in after.context["cl"].result_list

    def test_filter_shows_only_applications_with_candidates(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        flagged = make_applicant(tax_id=tax_id)
        plain = make_applicant()

        response = manager_client.get(CHANGELIST_URL, {"has_1c_candidate": "yes"})

        rows = response.context["cl"].result_list
        assert flagged in rows
        assert plain not in rows

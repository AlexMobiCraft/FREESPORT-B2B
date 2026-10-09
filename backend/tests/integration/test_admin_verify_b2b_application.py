"""
Integration-тесты страницы «Подтверждение заявки» в админке.

Проходят строки I/O-матрицы спеки spec-admin-b2b-verification-card через HTTP:
права, режимы страницы, ошибки формы, экранирование данных 1С, кнопку в
полной карточке, колонку списка и стоимость страницы и списка в запросах.
"""

from __future__ import annotations

import itertools
import re
import time
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from apps.common.models import AuditLog
from apps.products.models import PriceType
from apps.users.models import Company, User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

CHANGELIST_URL = reverse("admin:users_user_changelist")
OPT4_GUID = "4c1962d2-f8ed-11eb-81f3-00155d3cae02"

_counter = itertools.count()


def unique_suffix() -> str:
    return f"{time.time_ns()}_{next(_counter)}"


def unique_tax_id() -> str:
    return str(1000000000 + ((time.time_ns() + next(_counter) * 7919) % 900000000))


def verify_url(user: User) -> str:
    return reverse("admin:users_user_verify", args=[user.pk])


def change_url(user: User) -> str:
    return reverse("admin:users_user_change", args=[user.pk])


def ensure_price_type(onec_id: str, user_role: str, name: str = "") -> PriceType:
    price_type, _ = PriceType.objects.get_or_create(
        onec_id=onec_id,
        defaults={
            "onec_name": name or f"Вид цен {onec_id[:8]}",
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


def is_checked(content: str, candidate: User) -> bool:
    return bool(re.search(rf'value="{candidate.pk}:{re.escape(candidate.onec_id or "")}"\s+checked', content))


def message_texts(response) -> list[str]:
    return [str(message) for message in response.context["messages"]]


@pytest.fixture(autouse=True)
def verified_email_task():
    with patch("apps.users.signals.send_user_verified_email") as task:
        yield task


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


def make_staff(django_user_model, *codenames: str) -> User:
    staff = django_user_model.objects.create_user(
        email=f"staff_{unique_suffix()}@example.com",
        password="StrongPassword123!",
        first_name="Сотрудник",
        last_name="Тестов",
        role="admin",
        is_staff=True,
    )
    for codename in codenames:
        staff.user_permissions.add(Permission.objects.get(codename=codename))
    return staff


class TestPageContent:
    def test_single_candidate_is_preselected_and_fields_are_limited(self, manager_client):
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID, customer_code="54321")
        Company.objects.create(
            user=source, legal_name="ООО Полное", tax_id=tax_id, kpp="770101001", legal_address="г. Москва"
        )
        target = make_applicant(tax_id, phone="+79001234567")

        response = manager_client.get(verify_url(target))

        content = response.content.decode()
        assert response.status_code == 200
        assert target.email in content
        assert "+79001234567" in content
        assert source.onec_id in content
        assert "770101001" in content
        assert "г. Москва" in content
        assert "54321" in content
        assert "из соглашения 1С" in content
        assert is_checked(content, source)
        assert "Отклонить" in content
        # Только данные заявки: ни групп и прав, ни пароля, ни полей синхронизации.
        for forbidden in ("user_permissions", "groups", "password", "sync_status", "created_in_1c", "is_staff"):
            assert f'name="{forbidden}"' not in content
        assert "Права доступа" not in content

    def test_multiple_candidates_have_no_preselection(self, manager_client):
        price_type = ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        first = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID)
        second = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        response = manager_client.get(verify_url(target))

        content = response.content.decode()
        assert first.onec_id in content
        assert second.onec_id in content
        assert not is_checked(content, first)
        assert not is_checked(content, second)
        # У каждой строки — вид цен и роль по нему.
        assert price_type.onec_name in content
        assert "Оптовик уровень 4" in content
        assert "не определена" in content
        # У второго роль по виду цен не определена — менеджер выбирает её сам.
        assert 'name="role"' in content

    def test_no_candidates_shows_warning_and_second_checkbox(self, manager_client):
        target = make_applicant()

        content = manager_client.get(verify_url(target)).content.decode()

        assert "при первом заказе" in content
        assert 'name="confirm_without_1c"' in content
        assert 'name="role"' in content

    def test_price_type_name_is_matched_case_insensitively(self, manager_client):
        price_type = ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        make_1c_record(tax_id, onec_price_type_id=OPT4_GUID.upper())
        target = make_applicant(tax_id)

        content = manager_client.get(verify_url(target)).content.decode()

        assert price_type.onec_name in content
        assert OPT4_GUID.upper() not in content

    def test_1c_data_is_escaped(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, company_name="<script>alert(1)</script>")
        Company.objects.create(user=source, tax_id=tax_id, legal_address="<b>адрес</b>")
        target = make_applicant(tax_id)

        content = manager_client.get(verify_url(target)).content.decode()

        assert "<script>alert(1)</script>" not in content
        assert "&lt;script&gt;alert(1)&lt;/script&gt;" in content
        assert "<b>адрес</b>" not in content


class TestVerifyFlow:
    def test_single_candidate_confirm_links_and_verifies(self, manager_client, manager):
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID)
        target = make_applicant(tax_id)

        response = manager_client.post(
            verify_url(target),
            {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}", "role": "wholesale_level2"},
        )

        assert response.status_code == 302
        assert response.url == change_url(target)
        target.refresh_from_db()
        assert target.onec_id
        assert target.role == "wholesale_level4"
        assert target.verification_status == "verified"
        assert target.is_verified is True
        assert target.is_active is True
        assert AuditLog.objects.get(action="link_1c_customer").user == manager
        verify_entry = AuditLog.objects.get(action="verify_b2b")
        assert verify_entry.user == manager
        assert verify_entry.changes["role_before"] == "wholesale_level1"

    def test_multiple_candidates_without_choice_is_form_error(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        make_1c_record(tax_id)
        target = make_applicant(tax_id)

        response = manager_client.post(verify_url(target), {"confirm": "on", "role": "wholesale_level1"})

        assert response.status_code == 200
        assert "Выберите контрагента 1С" in response.content.decode()
        target.refresh_from_db()
        assert target.verification_status == "pending"
        assert not target.onec_id

    def test_multiple_candidates_chosen_with_manager_role(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        chosen = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        onec_id = chosen.onec_id

        manager_client.post(
            verify_url(target),
            {"confirm": "on", "candidate": f"{chosen.pk}:{onec_id}", "role": "wholesale_level3"},
        )

        target.refresh_from_db()
        assert target.onec_id == onec_id
        assert target.role == "wholesale_level3"

    def test_no_candidates_without_second_checkbox_is_form_error(self, manager_client):
        target = make_applicant()

        response = manager_client.post(verify_url(target), {"confirm": "on", "role": "wholesale_level1"})

        assert response.status_code == 200
        assert "Подтвердить без привязки к 1С" in response.content.decode()
        target.refresh_from_db()
        assert target.verification_status == "pending"

    def test_no_candidates_with_second_checkbox(self, manager_client):
        target = make_applicant()

        response = manager_client.post(
            verify_url(target), {"confirm": "on", "confirm_without_1c": "on", "role": "trainer"}, follow=True
        )

        target.refresh_from_db()
        assert target.verification_status == "verified"
        assert target.role == "trainer"
        assert any("при первом заказе" in text for text in message_texts(response))

    def test_linked_pending_confirms_without_second_checkbox(self, manager_client):
        target = make_applicant(onec_id=f"1C-own-{unique_suffix()}")

        page = manager_client.get(verify_url(target)).content.decode()
        assert 'name="confirm_without_1c"' not in page
        assert target.onec_id in page

        manager_client.post(verify_url(target), {"confirm": "on", "role": "wholesale_level1"})

        target.refresh_from_db()
        assert target.verification_status == "verified"

    def test_verified_unlinked_with_candidates_only_links(self, manager_client, verified_email_task):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id, verification_status="verified", is_verified=True, is_active=False)

        page = manager_client.get(verify_url(target)).content.decode()
        assert "Отклонить" not in page

        manager_client.post(verify_url(target), {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}"})

        target.refresh_from_db()
        assert target.onec_id
        assert target.is_active is False
        verified_email_task.delay.assert_not_called()

    def test_missing_confirm_is_form_error(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)

        response = manager_client.post(verify_url(target), {"candidate": f"{source.pk}:{source.onec_id}"})

        assert response.status_code == 200
        assert "Отметьте «Подтвердить»" in response.content.decode()
        target.refresh_from_db()
        assert target.verification_status == "pending"
        assert not target.onec_id

    def test_double_submit_shows_error_and_changes_nothing(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        payload = {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}"}

        manager_client.post(verify_url(target), payload)
        # Устаревшая вкладка: форма отправляется повторно мимо GET.
        response = manager_client.post(verify_url(target), payload, follow=True)

        assert AuditLog.objects.filter(action="verify_b2b").count() == 1
        assert response.redirect_chain[-1][0] == change_url(target)

    def test_stale_page_candidate_taken(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        other = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        stale_onec_id = source.onec_id
        # Между рендером и отправкой запись 1С ушла другой заявке/деактивирована.
        User.objects.filter(pk=source.pk).update(is_active=False)

        response = manager_client.post(
            verify_url(target), {"confirm": "on", "candidate": f"{source.pk}:{stale_onec_id}"}
        )

        assert response.status_code == 200  # выбора больше нет в списке — ошибка формы
        target.refresh_from_db()
        assert target.verification_status == "pending"
        assert not target.onec_id
        assert other.onec_id in response.content.decode()

    def test_customer_code_mismatch_warning_and_success_message(self, manager_client):
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id, customer_code="54321")
        target = make_applicant(tax_id, customer_code="12345")

        response = manager_client.post(
            verify_url(target),
            {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}", "role": "wholesale_level1"},
            follow=True,
        )

        texts = message_texts(response)
        assert any("Код клиента расходится с 1С: у заявителя 12345, у контрагента 54321" in text for text in texts)
        assert any("подтверждена" in text and f"ID в 1С: {source.onec_id}" in text for text in texts)

    def test_reject_refused_in_link_only_mode(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        target = make_applicant(tax_id, verification_status="verified", is_verified=True, is_active=False)

        response = manager_client.post(verify_url(target), {"_reject": "Отклонить"}, follow=True)

        assert any("Отклонить можно только заявку, ждущую решения" in text for text in message_texts(response))
        target.refresh_from_db()
        assert target.verification_status == "verified"
        assert target.is_verified is True
        assert target.is_active is False
        assert not AuditLog.objects.filter(action="reject_b2b").exists()

    def test_reject(self, manager_client, manager):
        target = make_applicant(role="trainer")

        response = manager_client.post(verify_url(target), {"_reject": "Отклонить"})

        assert response.status_code == 302
        target.refresh_from_db()
        assert target.verification_status == "unverified"
        assert target.is_verified is False
        assert target.role == "trainer"
        assert AuditLog.objects.get(action="reject_b2b").user == manager


class TestAccess:
    @pytest.mark.parametrize(
        "overrides",
        [
            pytest.param({"verification_status": "verified", "is_verified": True}, id="verified-no-candidates"),
            pytest.param({"verification_status": "verified", "onec_id": "linked"}, id="verified-linked"),
            pytest.param({"role": "retail"}, id="not-b2b"),
            pytest.param({"is_superuser": True, "is_staff": True}, id="superuser"),
        ],
    )
    def test_no_grounds_redirects_to_full_card(self, manager_client, overrides):
        if "onec_id" in overrides:
            overrides = {**overrides, "onec_id": f"1C-linked-{unique_suffix()}"}
        target = make_applicant(**overrides)

        response = manager_client.get(verify_url(target), follow=True)

        assert response.redirect_chain == [(change_url(target), 302)]
        assert any("не ждёт подтверждения" in text for text in message_texts(response))

    def test_staff_is_redirected_to_login(self, client, django_user_model):
        # Эпик 42: `/admin/` только суперпользователю — сотрудник отсекается
        # сайтом (302 на вход) при любых правах. Проверка «страница подтверждения
        # требует change_user» вернётся тестами раздела менеджера (стори 42.4).
        tax_id = unique_tax_id()
        source = make_1c_record(tax_id)
        target = make_applicant(tax_id)
        viewer = make_staff(django_user_model, "view_user")
        client.force_login(viewer)

        response = client.get(verify_url(target))
        assert response.status_code == 302
        assert "/admin/login/" in response.url
        response = client.post(verify_url(target), {"confirm": "on", "candidate": f"{source.pk}:{source.onec_id}"})
        assert response.status_code == 302
        assert "/admin/login/" in response.url
        target.refresh_from_db()
        assert target.verification_status == "pending"
        assert not target.onec_id

        # Право change_user сотруднику `/admin/` тоже не открывает.
        editor = make_staff(django_user_model, "view_user", "change_user")
        client.force_login(editor)
        response = client.get(verify_url(target))
        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_missing_user_redirects(self, manager_client):
        response = manager_client.get(reverse("admin:users_user_verify", args=[987654321]))
        assert response.status_code == 302


class TestEntryPoints:
    def test_change_form_button_shown_only_when_eligible(self, manager_client):
        pending = make_applicant()
        done = make_applicant(verification_status="verified", is_verified=True)

        assert verify_url(pending) in manager_client.get(change_url(pending)).content.decode()
        assert verify_url(done) not in manager_client.get(change_url(done)).content.decode()

    def test_change_form_button_in_link_only_mode(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        link_only = make_applicant(tax_id, verification_status="verified", is_verified=True)

        assert verify_url(link_only) in manager_client.get(change_url(link_only)).content.decode()

    def test_change_form_closed_for_staff(self, client, django_user_model):
        # Эпик 42: сотрудник с view_user карточку в `/admin/` не открывает вовсе —
        # 302 на вход. Скрытие кнопки без change_user вернётся тестами раздела
        # менеджера (стори 42.4).
        pending = make_applicant()
        viewer = make_staff(django_user_model, "view_user")
        client.force_login(viewer)

        response = client.get(change_url(pending))

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_changelist_column_links_only_eligible_rows(self, manager_client):
        tax_id = unique_tax_id()
        make_1c_record(tax_id)
        pending = make_applicant()
        link_only = make_applicant(tax_id, verification_status="verified", is_verified=True)
        done = make_applicant(verification_status="verified", is_verified=True)
        retail = make_applicant(role="retail")

        content = manager_client.get(CHANGELIST_URL).content.decode()

        assert verify_url(pending) in content
        assert verify_url(link_only) in content
        assert verify_url(done) not in content
        assert verify_url(retail) not in content


class TestQueryCost:
    def _page_queries(self, client, count: int) -> int:
        ensure_price_type(OPT4_GUID, "wholesale_level4")
        tax_id = unique_tax_id()
        for _ in range(count):
            source = make_1c_record(tax_id, onec_price_type_id=OPT4_GUID)
            Company.objects.create(user=source, tax_id=tax_id, legal_address="г. Москва", kpp="770101001")
        target = make_applicant(tax_id)
        with CaptureQueriesContext(connection) as captured:
            response = client.get(verify_url(target))
        assert response.status_code == 200
        return len(captured)

    def test_page_queries_do_not_grow_with_candidates(self, manager_client):
        # Два кандидата против восьми: при одном кандидате роль показывается
        # только для чтения, а выбор роли и ветка рендера одинаковы для 2+.
        assert self._page_queries(manager_client, 2) == self._page_queries(manager_client, 8)

    def test_changelist_queries_do_not_grow_with_rows(self, manager_client, django_assert_num_queries):
        def add_rows(count: int) -> None:
            for index in range(count):
                tax_id = unique_tax_id()
                make_1c_record(tax_id)
                status = "pending" if index % 2 else "verified"
                make_applicant(tax_id, verification_status=status)

        add_rows(3)
        with CaptureQueriesContext(connection) as captured:
            assert manager_client.get(CHANGELIST_URL).status_code == 200
        baseline = len(captured)

        add_rows(12)
        with django_assert_num_queries(baseline):
            assert manager_client.get(CHANGELIST_URL).status_code == 200

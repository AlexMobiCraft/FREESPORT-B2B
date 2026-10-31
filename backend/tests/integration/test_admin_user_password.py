"""
Integration-тесты создания и смены пароля пользователя в Django-админке.

Формы и вьюхи стандартные (BaseUserAdmin), но доступность смены пароля из
карточки зависит от наших fieldsets: без поля `password` ссылки на форму нет.
"""

from __future__ import annotations

import itertools
import time
from urllib.parse import urljoin

import pytest
from django.contrib.admin.models import CHANGE, LogEntry
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.common.models import AuditLog
from apps.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

ADD_URL = reverse("admin:users_user_add")
NEW_PASSWORD = "NewStrongPass-2026"

_counter = itertools.count()


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}_{next(_counter)}@example.com"


def password_url(user: User) -> str:
    # Имя маршрута BaseUserAdmin зашито в Django и не зависит от модели.
    return reverse("admin:auth_user_password_change", args=[user.pk])


def change_url(user: User) -> str:
    return reverse("admin:users_user_change", args=[user.pk])


def make_user(**overrides) -> User:
    defaults = {
        "email": unique_email("customer"),
        "first_name": "Покупатель",
        "last_name": "Тестов",
        "role": "wholesale_level1",
    }
    defaults.update(overrides)
    return User.objects.create_user(password="OldStrongPass-2025", **defaults)


def make_1c_record_without_password() -> User:
    """Запись импорта 1С: импорт оставляет пустую строку в `password`."""
    record = User(
        email=unique_email("1c"),
        first_name="Контрагент",
        last_name="Из1С",
        role=User.ROLE_UNREGISTERED,
        created_in_1c=True,
        verification_status="unverified",
        password="",
    )
    record.save()
    return record


@pytest.fixture
def manager(django_user_model):
    return django_user_model.objects.create_superuser(
        email=unique_email("manager"),
        password="StrongPassword123!",
        first_name="Менеджер",
        last_name="Тестов",
    )


@pytest.fixture
def manager_client(client, manager):
    client.force_login(manager)
    return client


def add_form_payload(client, **fields) -> dict[str, str]:
    """POST-данные формы добавления вместе с пустыми management-формами inline'ов."""
    response = client.get(ADD_URL)
    assert response.status_code == 200
    payload: dict[str, str] = {}
    for inline_admin_formset in response.context["inline_admin_formsets"]:
        management_form = inline_admin_formset.formset.management_form
        for name in management_form.fields:
            payload[management_form.add_prefix(name)] = str(management_form[name].value())
        payload[management_form.add_prefix("TOTAL_FORMS")] = "0"
    payload.update(fields)
    return payload


class TestCreateUserWithPassword:
    def test_created_user_can_log_in_with_given_password(self, manager_client):
        email = unique_email("new")
        payload = add_form_payload(
            manager_client,
            email=email,
            first_name="Новый",
            last_name="Клиент",
            role="wholesale_level1",
            password1=NEW_PASSWORD,
            password2=NEW_PASSWORD,
        )

        response = manager_client.post(ADD_URL, payload)

        assert response.status_code == 302
        user = User.objects.get(email=email)
        assert user.has_usable_password()
        assert user.check_password(NEW_PASSWORD)

    def test_mismatched_passwords_do_not_create_user(self, manager_client):
        email = unique_email("mismatch")
        payload = add_form_payload(
            manager_client,
            email=email,
            first_name="Новый",
            last_name="Клиент",
            role="wholesale_level1",
            password1=NEW_PASSWORD,
            password2=NEW_PASSWORD + "x",
        )

        response = manager_client.post(ADD_URL, payload)

        assert response.status_code == 200
        assert "password2" in response.context["adminform"].form.errors
        assert not User.objects.filter(email=email).exists()


class TestChangePasswordFromCard:
    def test_card_links_to_password_form(self, manager_client):
        user = make_user()

        response = manager_client.get(change_url(user))

        assert response.status_code == 200
        assert "password" in response.context["adminform"].form.fields
        # Кнопка ReadOnlyPasswordHashWidget ведёт на относительный адрес формы.
        assert 'href="../password/"' in response.content.decode()
        assert urljoin(change_url(user), "../password/") == password_url(user)

    def test_password_is_changed_and_logged(self, manager_client, manager):
        user = make_user()

        response = manager_client.post(
            password_url(user),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        assert response.status_code == 302
        assert response.url == change_url(user)
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)
        log_entry = LogEntry.objects.get(user=manager, object_id=str(user.pk), action_flag=CHANGE)
        assert '"password"' in log_entry.change_message
        audit = AuditLog.objects.get(action="change_password", resource_id=str(user.pk))
        assert audit.user == manager
        assert audit.changes == {"email": user.email, "usable_password": True}
        assert audit.ip_address == "127.0.0.1"

    def test_weak_password_is_rejected(self, manager_client):
        user = make_user()

        response = manager_client.post(
            password_url(user),
            {"usable_password": "true", "password1": "12345", "password2": "12345"},
        )

        assert response.status_code == 200
        assert "password2" in response.context["form"].errors
        user.refresh_from_db()
        assert user.check_password("OldStrongPass-2025")
        assert not AuditLog.objects.filter(action="change_password", resource_id=str(user.pk)).exists()

    def test_password_is_set_for_1c_record_without_password(self, manager_client):
        record = make_1c_record_without_password()
        assert User.objects.unlinked_1c_records().filter(pk=record.pk).exists()

        card = manager_client.get(change_url(record))
        assert 'href="../password/"' in card.content.decode()

        response = manager_client.post(
            password_url(record),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        assert response.status_code == 302
        record.refresh_from_db()
        assert record.check_password(NEW_PASSWORD)
        # Запись с паролем — живой аккаунт и больше не кандидат на привязку.
        assert not User.objects.unlinked_1c_records().filter(pk=record.pk).exists()

    def test_password_is_set_for_user_with_unusable_password(self, manager_client):
        user = make_user()
        user.set_unusable_password()
        user.save(update_fields=["password"])

        response = manager_client.post(
            password_url(user),
            {"password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        assert response.status_code == 302
        user.refresh_from_db()
        assert user.check_password(NEW_PASSWORD)

    def test_password_form_requires_change_permission(self, client):
        viewer = User.objects.create_user(
            email=unique_email("viewer"),
            password="StrongPassword123!",
            first_name="Только",
            last_name="Просмотр",
            is_staff=True,
        )
        viewer.user_permissions.add(Permission.objects.get(codename="view_user", content_type__app_label="users"))
        client.force_login(viewer)
        user = make_user()

        response = client.post(
            password_url(user),
            {"usable_password": "true", "password1": NEW_PASSWORD, "password2": NEW_PASSWORD},
        )

        # Эпик 42: `/admin/` только суперпользователю — сотрудника сайт отсекает
        # редиректом на вход раньше, чем дойдёт до проверки права change_user.
        assert response.status_code == 302
        assert "/admin/login/" in response.url
        user.refresh_from_db()
        assert user.check_password("OldStrongPass-2025")

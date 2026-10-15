"""
Транзакционная целостность регистрации.

- Письма B2B-заявки уходят в Celery только после commit: откат регистрации
  (например, сбой записи согласия) не должен оставлять задач с id
  несуществующего пользователя.
- Гонка двух регистраций с одним email: проверка дубля в `validate()` —
  read-then-write, второй запрос упирается в unique БД и обязан получить
  тот же 400, что и при последовательной регистрации, а не 500.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.db import DatabaseError, IntegrityError
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.common.models import UserConsent
from apps.users.models import User
from apps.users.serializers import EMAIL_ALREADY_REGISTERED_MESSAGE, UserRegistrationSerializer
from tests.consent_versions import REGISTRATION_MARKETING_TEXT_VERSION, REGISTRATION_PDP_TEXT_VERSION

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

REGISTER_URL = "/api/v1/auth/register/"


def trainer_payload() -> dict:
    suffix = uuid.uuid4().hex[:10]
    return {
        "email": f"race_{suffix}@example.com",
        "password": "StrongPassword123!",
        "password_confirm": "StrongPassword123!",
        "first_name": "Race",
        "last_name": "Trainer",
        "role": "trainer",
        "company_name": "Race Club",
        "tax_id": f"77{int(suffix, 16) % 10**8:08d}",
        "pdp_consent": True,
        "pdp_consent_text_version": REGISTRATION_PDP_TEXT_VERSION,
        "marketing_consent_text_version": REGISTRATION_MARKETING_TEXT_VERSION,
        "marketing_consent": False,
    }


@pytest.fixture
def notification_tasks():
    with (
        patch("apps.users.serializers.send_admin_verification_email.delay") as admin_email,
        patch("apps.users.serializers.send_user_pending_email.delay") as pending_email,
        patch("apps.users.serializers.send_manager_region_email.delay") as manager_email,
    ):
        yield admin_email, pending_email, manager_email


def test_b2b_notification_tasks_are_not_queued_when_registration_rolls_back(notification_tasks):
    """Сбой записи согласия откатывает пользователя — и письма о нём не уходят."""
    client = APIClient()
    payload = trainer_payload()

    with patch(
        "apps.users.views.authentication.UserConsent.objects.create",
        side_effect=DatabaseError("consent insert failed"),
    ):
        with pytest.raises(DatabaseError):
            client.post(REGISTER_URL, payload, format="json")

    assert not User.objects.filter(email=payload["email"]).exists()
    for task in notification_tasks:
        task.assert_not_called()


def test_b2b_notification_tasks_are_queued_after_commit(notification_tasks):
    """Успешная заявка ставит все три письма — с id уже закоммиченной записи."""
    client = APIClient()
    payload = trainer_payload()

    response = client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    user = User.objects.get(email=payload["email"])
    for task in notification_tasks:
        task.assert_called_once_with(user.id)


def test_concurrent_registration_with_same_email_returns_400(notification_tasks):
    """Второй из параллельных запросов получает штатный отказ по email, а не 500.

    Конкурент имитируется вставкой строки с тем же email сразу после `validate()`:
    ровно в это окно попадает параллельный запрос в проде.
    """
    client = APIClient()
    payload = trainer_payload()
    original_validate = UserRegistrationSerializer.validate

    def validate_then_race(self, attrs):
        attrs = original_validate(self, attrs)
        User.objects.create_user(email=attrs["email"], password="OtherPassword123!", role="trainer")
        return attrs

    with patch.object(UserRegistrationSerializer, "validate", validate_then_race):
        response = client.post(REGISTER_URL, payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data == {"email": [EMAIL_ALREADY_REGISTERED_MESSAGE]}
    assert not UserConsent.objects.exists()
    for task in notification_tasks:
        task.assert_not_called()


def test_email_race_in_serializer_raises_validation_error_and_keeps_competitor():
    """Строка конкурента остаётся, заявка отклоняется ошибкой поля email."""
    payload = trainer_payload()
    serializer = UserRegistrationSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors

    # Конкурент закоммитил регистрацию между validate() и create().
    competitor = User.objects.create_user(email=payload["email"], password="OtherPassword123!", role="trainer")

    with pytest.raises(ValidationError) as exc_info:
        serializer.save()

    assert exc_info.value.detail == {"email": [EMAIL_ALREADY_REGISTERED_MESSAGE]}
    assert list(User.objects.filter(email=payload["email"])) == [competitor]


def test_integrity_error_not_about_email_is_not_masked():
    """Иной конфликт уникальности — не дубль email: его не превращаем в 400."""
    payload = trainer_payload()
    serializer = UserRegistrationSerializer(data=payload)
    assert serializer.is_valid(), serializer.errors

    with patch.object(
        User.objects,
        "create_user",
        side_effect=IntegrityError('duplicate key value violates unique constraint "users_onec_id_key"'),
    ):
        with pytest.raises(IntegrityError):
            serializer.save()

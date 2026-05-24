"""Интеграционные тесты публичного API подписки на рассылку."""

from unittest.mock import patch
from uuid import uuid4

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.core.cache import cache
from django.db import IntegrityError, OperationalError, connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import ErrorDetail

from apps.common.models import Newsletter, UserConsent
from apps.common.serializers import ALREADY_SUBSCRIBED_CODE, SubscribeSerializer
from apps.common.throttling import SubscribeRateThrottle, UnsubscribeRateThrottle

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

User = get_user_model()

PDP_CONSENT_REQUIRED = "Необходимо согласие на обработку персональных данных."


class TestSubscribeEndpoint:
    """Набор кейсов для POST /api/v1/subscribe."""

    def test_subscribe_success(self, api_client):
        """Проверяет успешное создание подписки."""
        url = reverse("common:subscribe")
        data = {"email": "newuser@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Вы успешно подписались на рассылку"
        assert response.data["email"] == "newuser@example.com"
        assert Newsletter.objects.filter(email="newuser@example.com").exists()

    def test_subscribe_duplicate_email(self, api_client):
        """Повторная подписка возвращает нейтральный успех без enumeration leak."""
        Newsletter.objects.create(email="existing@example.com", is_active=True)

        url = reverse("common:subscribe")
        data = {"email": "existing@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Вы успешно подписались на рассылку",
            "email": "existing@example.com",
        }
        assert UserConsent.objects.count() == 0

    def test_subscribe_duplicate_non_string_email_is_not_echoed(self, api_client):
        """Нейтральный already_subscribed-ответ не эхоит list/dict из raw request."""

        class FakeSubscribeSerializer:
            initial_data = {"email": ["existing@example.com"]}
            errors = {
                "email": [
                    ErrorDetail(
                        "Этот email уже подписан на рассылку",
                        code=ALREADY_SUBSCRIBED_CODE,
                    )
                ]
            }

            def __init__(self, *args, **kwargs):
                pass

            def is_valid(self):
                return False

        url = reverse("common:subscribe")

        with patch("apps.common.views.SubscribeSerializer", FakeSubscribeSerializer):
            response = api_client.post(
                url,
                {"email": ["existing@example.com"], "pdp_consent": True},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Вы успешно подписались на рассылку",
            "email": "",
        }

    def test_subscribe_missing_pdp_consent_does_not_leak_subscriber_status(self, api_client):
        """Без pdp_consent известный email не должен раскрывать статус подписки."""
        Newsletter.objects.create(email="known-subscriber@example.com", is_active=True)

        url = reverse("common:subscribe")
        data = {"email": "known-subscriber@example.com"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "pdp_consent" in response.data
        assert "email" not in response.data
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert UserConsent.objects.count() == 0

    def test_subscribe_reactivate_unsubscribed(self, api_client):
        """Проверяет реактивацию ранее отписавшегося email."""
        Newsletter.objects.create(
            email="unsubscribed@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )

        url = reverse("common:subscribe")
        data = {"email": "unsubscribed@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="unsubscribed@example.com")
        assert subscription.is_active is True
        assert subscription.unsubscribed_at is None

    @pytest.mark.django_db(transaction=True)
    def test_subscribe_serializer_save_can_run_outside_view_atomic(self):
        """SubscribeSerializer.save() сам открывает transaction для select_for_update."""
        serializer = SubscribeSerializer(data={"email": "serializer-direct@example.com", "pdp_consent": True})

        assert serializer.is_valid(), serializer.errors
        subscription = serializer.save()

        assert subscription.email == "serializer-direct@example.com"
        assert Newsletter.objects.filter(email="serializer-direct@example.com").exists()

    def test_subscribe_invalid_email(self, api_client):
        """Возвращает 400 для некорректного email."""
        url = reverse("common:subscribe")
        data = {"email": "invalid-email", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_subscribe_email_normalization(self, api_client):
        """Подтверждает нормализацию email в lowercase."""
        url = reverse("common:subscribe")
        data = {"email": "TestUser@EXAMPLE.COM", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="testuser@example.com")
        assert subscription.email == "testuser@example.com"

    def test_subscribe_requires_pdp_consent(self, api_client):
        """Без явного согласия подписка отклоняется."""
        url = reverse("common:subscribe")
        data = {"email": "missing-consent@example.com"}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert not Newsletter.objects.filter(email="missing-consent@example.com").exists()

    def test_subscribe_serializer_validate_rejects_non_mapping_initial_data(self):
        """Strict consent guard не должен падать на non-object JSON payload."""
        serializer = SubscribeSerializer()
        serializer.initial_data = []

        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.validate({"email": "array-payload@example.com", "pdp_consent": True})

        assert "non_field_errors" in exc_info.value.detail

    @pytest.mark.parametrize("payload", [[], "string"])
    def test_subscribe_rejects_non_object_json_payload(self, api_client, payload):
        """JSONParser может принять не-object JSON, но endpoint обязан вернуть 400."""
        url = reverse("common:subscribe")

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "non_field_errors" in response.data
        assert Newsletter.objects.count() == 0

    def test_subscribe_rejects_pdp_consent_false(self, api_client):
        """False в pdp_consent не считается согласием."""
        url = reverse("common:subscribe")
        data = {"email": "false-consent@example.com", "pdp_consent": False}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert not Newsletter.objects.filter(email="false-consent@example.com").exists()

    @pytest.mark.parametrize("truthy_value", ["on", "yes", "1", 1])
    def test_subscribe_rejects_pdp_consent_truthy_non_boolean(self, api_client, truthy_value):
        """Только JSON boolean true считается явным согласием."""
        url = reverse("common:subscribe")
        data = {
            "email": f"truthy-consent-{truthy_value}@example.com",
            "pdp_consent": truthy_value,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert not Newsletter.objects.filter(email=data["email"]).exists()

    def test_subscribe_creates_two_consent_records_for_anonymous(self, api_client):
        """Анонимная подписка пишет два согласия с session_key."""
        url = reverse("common:subscribe")
        data = {"email": "anonymous-consent@example.com", "pdp_consent": True}

        response = api_client.post(
            url,
            data,
            format="json",
            HTTP_X_FORWARDED_FOR="203.0.113.5",
            HTTP_USER_AGENT="SubscribeTest/1.0",
        )

        assert response.status_code == status.HTTP_200_OK
        consents = list(UserConsent.objects.order_by("consent_type"))
        assert len(consents) == 2
        assert {consent.consent_type for consent in consents} == {
            "marketing_email",
            "pdp_contract",
        }
        assert all(consent.user is None for consent in consents)
        assert all(consent.session_key for consent in consents)
        assert len({consent.session_key for consent in consents}) == 1
        assert {str(consent.ip_address) for consent in consents} == {"203.0.113.5"}
        assert all(consent.user_agent == "SubscribeTest/1.0" for consent in consents)
        assert all(consent.policy_version == "1.0" for consent in consents)

    def test_subscribe_newsletter_ip_uses_normalized_audit_ip(self, api_client):
        """Newsletter.latest IP использует REMOTE_ADDR fallback при невалидном proxy-IP."""
        url = reverse("common:subscribe")
        data = {"email": "invalid-newsletter-ip@example.com", "pdp_consent": True}

        response = api_client.post(
            url,
            data,
            format="json",
            HTTP_X_FORWARDED_FOR="bad-ip, 203.0.113.5",
            HTTP_USER_AGENT="SubscribeTest/1.0",
            REMOTE_ADDR="198.51.100.77",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="invalid-newsletter-ip@example.com")
        assert subscription.ip_address == "198.51.100.77"
        assert {str(consent.ip_address) for consent in UserConsent.objects.all()} == {"198.51.100.77"}

    def test_subscribe_accepts_private_forwarded_ip_for_audit(self, api_client):
        """Audit сохраняет любой валидный IP, включая private/loopback."""
        url = reverse("common:subscribe")
        data = {"email": "private-ip-consent@example.com", "pdp_consent": True}

        response = api_client.post(
            url,
            data,
            format="json",
            HTTP_X_FORWARDED_FOR="10.0.0.1",
            HTTP_USER_AGENT="SubscribeTest/1.0",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="private-ip-consent@example.com")
        assert subscription.ip_address == "10.0.0.1"
        assert {str(consent.ip_address) for consent in UserConsent.objects.all()} == {"10.0.0.1"}

    def test_subscribe_creates_two_consent_records_for_authenticated(self, api_client):
        """Авторизованная подписка пишет согласия на user без session_key."""
        user = User.objects.create_user(
            email=f"subscribe-user-{uuid4().hex}@example.com",
            password="testpass123",
        )
        api_client.force_authenticate(user=user)

        url = reverse("common:subscribe")
        data = {"email": "authenticated-consent@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        consents = list(UserConsent.objects.order_by("consent_type"))
        assert len(consents) == 2
        assert {consent.consent_type for consent in consents} == {
            "marketing_email",
            "pdp_contract",
        }
        assert all(consent.user == user for consent in consents)
        assert all(consent.session_key == "" for consent in consents)

    def test_subscribe_consent_records_capture_ip_and_user_agent(self, api_client):
        """Audit-записи используют валидный first hop X-Forwarded-For и User-Agent."""
        url = reverse("common:subscribe")
        data = {"email": "ip-user-agent@example.com", "pdp_consent": True}

        response = api_client.post(
            url,
            data,
            format="json",
            HTTP_X_FORWARDED_FOR="1.2.3.4, 5.6.7.8",
            HTTP_USER_AGENT="SubscribeAudit/1.0",
        )

        assert response.status_code == status.HTTP_200_OK
        consents = UserConsent.objects.all()
        assert consents.count() == 2
        assert {consent.ip_address for consent in consents} == {"1.2.3.4"}
        assert {consent.user_agent for consent in consents} == {"SubscribeAudit/1.0"}

    def test_subscribe_consent_records_prefer_x_real_ip_over_forwarded_for(self, api_client):
        """Audit-записи и Newsletter.latest IP должны совпадать с throttle ident priority."""
        url = reverse("common:subscribe")
        data = {"email": "x-real-ip-consent@example.com", "pdp_consent": True}

        response = api_client.post(
            url,
            data,
            format="json",
            HTTP_X_REAL_IP="198.51.100.10",
            HTTP_X_FORWARDED_FOR="203.0.113.5, 198.51.100.10",
            HTTP_USER_AGENT="SubscribeAudit/1.0",
        )

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="x-real-ip-consent@example.com")
        assert subscription.ip_address == "198.51.100.10"
        consents = UserConsent.objects.all()
        assert consents.count() == 2
        assert {consent.ip_address for consent in consents} == {"198.51.100.10"}

    def test_subscribe_user_agent_truncated_to_512(self, api_client):
        """User-Agent для audit-записи очищается от surrogate и режется до 512 символов."""
        url = reverse("common:subscribe")
        data = {"email": "long-user-agent@example.com", "pdp_consent": True}
        user_agent = "A" * 510 + "\ud800" + "B" * 600

        response = api_client.post(url, data, format="json", HTTP_USER_AGENT=user_agent)

        assert response.status_code == status.HTTP_200_OK
        newsletter = Newsletter.objects.get(email="long-user-agent@example.com")
        assert len(newsletter.user_agent) == 512
        assert "\ud800" not in newsletter.user_agent
        assert UserConsent.objects.count() == 2
        for consent in UserConsent.objects.all():
            assert len(consent.user_agent) == 512
            assert "\ud800" not in consent.user_agent

    def test_subscribe_reactivation_creates_new_consent_records(self, api_client):
        """Реактивация append-only добавляет новые consent-записи."""
        Newsletter.objects.create(
            email="reactivation-consent@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )
        UserConsent.objects.create(
            session_key="old-reactivation-session",
            consent_type="pdp_contract",
        )
        initial_consent_count = UserConsent.objects.count()

        url = reverse("common:subscribe")
        data = {"email": "reactivation-consent@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="reactivation-consent@example.com")
        assert subscription.is_active is True
        assert subscription.unsubscribed_at is None
        assert UserConsent.objects.count() == initial_consent_count + 2

    def test_subscribe_reactivation_locks_existing_subscription(self, api_client):
        """Реактивация должна брать row lock, чтобы concurrent POST не дублировал audit."""
        Newsletter.objects.create(
            email="locked-reactivation@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )

        url = reverse("common:subscribe")
        data = {"email": "locked-reactivation@example.com", "pdp_consent": True}

        with CaptureQueriesContext(connection) as captured_queries:
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert any(" FOR UPDATE" in query["sql"].upper() for query in captured_queries.captured_queries)

    def test_subscribe_atomic_rollback_on_consent_failure(self, api_client):
        """Если consent audit не записался, клиент получает JSON 503 и Newsletter откатывается."""
        url = reverse("common:subscribe")
        data = {"email": "rollback-consent@example.com", "pdp_consent": True}
        original_create = UserConsent.objects.create

        def create_first_consent_then_fail(*args, **kwargs):
            if UserConsent.objects.count() == 0:
                return original_create(*args, **kwargs)
            raise IntegrityError("consent failed")

        with patch.object(
            UserConsent.objects,
            "create",
            side_effect=create_first_consent_then_fail,
        ):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["error"] == "consent_persistence_failed"
        assert not Newsletter.objects.filter(email="rollback-consent@example.com").exists()
        assert UserConsent.objects.count() == 0

    def test_subscribe_returns_structured_503_on_operational_consent_failure(self, api_client):
        """DatabaseError-подклассы при записи согласия возвращают JSON 503."""
        url = reverse("common:subscribe")
        data = {"email": "operational-consent@example.com", "pdp_consent": True}

        with patch.object(UserConsent.objects, "create", side_effect=OperationalError("db unavailable")):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data == {
            "error": "consent_persistence_failed",
            "details": {
                "non_field_errors": ["Не удалось сохранить согласие. Попробуйте позже."],
            },
        }
        assert not Newsletter.objects.filter(email="operational-consent@example.com").exists()

    def test_subscribe_anonymous_session_is_saved_before_atomic_consent_write(self, api_client, monkeypatch):
        """session_key для audit создается до локального atomic-блока с Newsletter/UserConsent."""
        url = reverse("common:subscribe")
        data = {"email": "session-before-atomic@example.com", "pdp_consent": True}
        original_save = SessionStore.save
        baseline_savepoint_depth = len(connection.savepoint_ids)
        save_atomic_depths = []

        def tracking_save(self, *args, **kwargs):
            save_atomic_depths.append(len(connection.savepoint_ids))
            return original_save(self, *args, **kwargs)

        monkeypatch.setattr(SessionStore, "save", tracking_save)

        with patch.object(UserConsent.objects, "create", side_effect=IntegrityError("consent failed")):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert save_atomic_depths
        assert save_atomic_depths[0] == baseline_savepoint_depth

    def test_subscribe_logs_session_materialization_failure_separately(self, api_client, monkeypatch, caplog):
        """Ошибка session.save() логируется отдельно от ошибок записи UserConsent."""
        url = reverse("common:subscribe")
        data = {"email": "session-failure@example.com", "pdp_consent": True}

        def fail_session_save(self, *args, **kwargs):
            raise OperationalError("session store unavailable")

        monkeypatch.setattr(SessionStore, "save", fail_session_save)

        with caplog.at_level("ERROR", logger="apps.common.views"):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["error"] == "consent_persistence_failed"
        assert "Failed to materialize anonymous session for consent audit" in caplog.text
        assert "Failed to persist newsletter consent audit" not in caplog.text
        assert not Newsletter.objects.filter(email="session-failure@example.com").exists()

    def test_subscribe_returns_200_when_newsletter_unique_race_hits_integrity_error(self, api_client):
        """Race на unique email должен возвращать нейтральный 200, а не enumeration leak."""
        url = reverse("common:subscribe")
        data = {"email": "unique-race@example.com", "pdp_consent": True}

        with patch.object(Newsletter.objects, "create", side_effect=IntegrityError("duplicate")):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Вы успешно подписались на рассылку",
            "email": "unique-race@example.com",
        }
        assert UserConsent.objects.count() == 0

    def test_subscribe_anonymous_creates_session_key(self, api_client):
        """У анонимной подписки обе consent-записи получают непустой session_key."""
        url = reverse("common:subscribe")
        data = {"email": "anonymous-session@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert UserConsent.objects.count() == 2
        assert all(consent.session_key for consent in UserConsent.objects.all())

    def test_subscribe_scope_throttle_kicks_in_during_valid_payload_flood(self, api_client):
        """Scope-specific subscribe throttle ограничивает валидный flood до serializer side effects."""
        assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["subscribe"] == "100000/min"
        cache.clear()
        url = reverse("common:subscribe")
        statuses = []

        with patch.object(
            SubscribeRateThrottle,
            "THROTTLE_RATES",
            {"subscribe": "5/min"},
        ):
            for index in range(40):
                response = api_client.post(
                    url,
                    {"email": f"throttle-{index}@example.com", "pdp_consent": True},
                    format="json",
                    REMOTE_ADDR="198.51.100.77",
                )
                statuses.append(response.status_code)

        cache.clear()
        assert statuses[:5] == [status.HTTP_200_OK] * 5
        assert statuses.count(status.HTTP_429_TOO_MANY_REQUESTS) >= 10


class TestUnsubscribeEndpoint:
    """Набор кейсов для POST /api/v1/unsubscribe."""

    def test_unsubscribe_unknown_email_returns_200(self, api_client):
        """Неизвестный email возвращает нейтральный 200 без создания подписки."""
        url = reverse("common:unsubscribe")

        response = api_client.post(url, {"email": "unknown-unsubscribe@example.com"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Запрос на отписку обработан",
            "email": "unknown-unsubscribe@example.com",
        }
        assert not Newsletter.objects.filter(email="unknown-unsubscribe@example.com").exists()

    def test_unsubscribe_already_unsubscribed_returns_200(self, api_client):
        """Уже отписанный email возвращает такой же нейтральный 200."""
        Newsletter.objects.create(
            email="already-unsubscribed@example.com",
            is_active=False,
            unsubscribed_at=timezone.now(),
        )
        url = reverse("common:unsubscribe")

        response = api_client.post(url, {"email": "already-unsubscribed@example.com"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Запрос на отписку обработан",
            "email": "already-unsubscribed@example.com",
        }
        subscription = Newsletter.objects.get(email="already-unsubscribed@example.com")
        assert subscription.is_active is False

    def test_unsubscribe_success_returns_200(self, api_client):
        """Активная подписка деактивируется и возвращает нейтральный 200."""
        Newsletter.objects.create(email="active-unsubscribe@example.com", is_active=True)
        url = reverse("common:unsubscribe")

        response = api_client.post(url, {"email": "active-unsubscribe@example.com"}, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Запрос на отписку обработан",
            "email": "active-unsubscribe@example.com",
        }
        subscription = Newsletter.objects.get(email="active-unsubscribe@example.com")
        assert subscription.is_active is False
        assert subscription.unsubscribed_at is not None

    def test_unsubscribe_invalid_email(self, api_client):
        """Возвращает 400 для некорректного email при отписке."""
        url = reverse("common:unsubscribe")

        response = api_client.post(url, {"email": "invalid-email"}, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_unsubscribe_returns_structured_503_on_database_failure(self, api_client):
        """DatabaseError-подклассы при обработке отписки возвращают JSON 503."""
        url = reverse("common:unsubscribe")

        with patch.object(Newsletter.objects, "get", side_effect=OperationalError("db unavailable")):
            response = api_client.post(url, {"email": "db-failure-unsubscribe@example.com"}, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data == {
            "error": "unsubscribe_processing_failed",
            "details": {
                "non_field_errors": ["Не удалось обработать запрос. Попробуйте позже."],
            },
        }

    @pytest.mark.parametrize(
        "payload",
        [
            {"email": ["list-value@example.com"]},
            {},
            {"email": None},
        ],
    )
    def test_unsubscribe_rejects_invalid_email_shapes(self, api_client, payload):
        """Отписка возвращает 400 для нестрокового, отсутствующего и null email."""
        url = reverse("common:unsubscribe")

        response = api_client.post(url, payload, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_unsubscribe_throttle_kicks_in(self, api_client):
        """Scope-specific unsubscribe throttle ограничивает flood по отдельному bucket."""
        assert settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["unsubscribe"] == "100000/min"
        cache.clear()
        url = reverse("common:unsubscribe")
        statuses = []

        with patch.object(
            UnsubscribeRateThrottle,
            "THROTTLE_RATES",
            {"unsubscribe": "5/min"},
        ):
            for index in range(40):
                response = api_client.post(
                    url,
                    {"email": f"unsubscribe-throttle-{index}@example.com"},
                    format="json",
                    REMOTE_ADDR="198.51.100.88",
                )
                statuses.append(response.status_code)

        cache.clear()
        assert statuses[:5] == [status.HTTP_200_OK] * 5
        assert statuses.count(status.HTTP_429_TOO_MANY_REQUESTS) >= 10

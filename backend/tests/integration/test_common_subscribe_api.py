"""Интеграционные тесты публичного API подписки на рассылку."""

import json
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

from apps.common.consent_texts import current_consent_text_version
from apps.common.models import Newsletter, UserConsent
from apps.common.serializers import (
    ALREADY_SUBSCRIBED_CODE,
    CONSENT_TEXT_OUTDATED,
    CONSENT_TEXT_OUTDATED_CODE,
    SubscribeSerializer,
)
from apps.common.throttling import SubscribeRateThrottle, UnsubscribeRateThrottle

pytestmark = [pytest.mark.django_db, pytest.mark.integration]

User = get_user_model()

PDP_CONSENT_REQUIRED = "Необходимо согласие на обработку персональных данных."
# Версия формулировки, которую показала форма. Берётся из реестра, а не литералом:
# при правке текста подписки версия меняется сама, и тесты не придётся править.
NEWSLETTER_TEXT_VERSION = current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract")


class TestSubscribeEndpoint:
    """Набор кейсов для POST /api/v1/subscribe."""

    def test_subscribe_success(self, api_client):
        """Проверяет успешное создание подписки."""
        url = reverse("common:subscribe")
        data = {"email": "newuser@example.com", "pdp_consent": True, "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Вы успешно подписались на рассылку"
        assert response.data["email"] == "newuser@example.com"
        assert Newsletter.objects.filter(email="newuser@example.com").exists()

    def test_subscribe_duplicate_email(self, api_client):
        """Повторная подписка: нейтральный успех без enumeration leak — и согласие записано.

        Активный подписчик снова поставил галочку и отправил форму — это новый
        явный факт согласия (ФЗ-152 ст. 9). После правки формулировки именно он
        доказывает согласие на новую редакцию, поэтому терять его нельзя (шестой
        круг ревью стори 41.9). Ответ тот же, что у новой подписки, а строка
        `Newsletter` активного подписчика не меняется.
        """
        Newsletter.objects.create(
            email="existing@example.com",
            is_active=True,
            ip_address="192.0.2.10",
            user_agent="Original/1.0",
        )

        url = reverse("common:subscribe")
        data = {"email": "existing@example.com", "pdp_consent": True, "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json", REMOTE_ADDR="198.51.100.20", HTTP_USER_AGENT="Repeat/2.0")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Вы успешно подписались на рассылку",
            "email": "existing@example.com",
        }
        consents = list(UserConsent.objects.order_by("consent_type"))
        assert [consent.consent_type for consent in consents] == ["marketing_email", "pdp_contract"]
        assert all(consent.source == UserConsent.SOURCE_NEWSLETTER for consent in consents)
        assert {consent.consent_text_version for consent in consents} == {NEWSLETTER_TEXT_VERSION}
        assert {consent.user_agent for consent in consents} == {"Repeat/2.0"}
        subscription = Newsletter.objects.get(email="existing@example.com")
        assert subscription.ip_address == "192.0.2.10"
        assert subscription.user_agent == "Original/1.0"

    def test_active_subscriber_reconfirmation_lands_next_to_old_records(self, api_client):
        """Подтверждение новой редакции ложится рядом, прежние записи сохраняют свою версию (AC5)."""
        Newsletter.objects.create(email="reconfirm@example.com", is_active=True)
        old_version = "2026-01-01-" + "0" * 32
        for consent_type in ("pdp_contract", "marketing_email"):
            UserConsent.objects.create(
                session_key="old-session",
                consent_type=consent_type,
                source=UserConsent.SOURCE_NEWSLETTER,
                consent_text_version=old_version,
            )

        url = reverse("common:subscribe")
        data = {"email": "reconfirm@example.com", "pdp_consent": True, "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert UserConsent.objects.filter(consent_text_version=old_version).count() == 2
        assert UserConsent.objects.filter(consent_text_version=NEWSLETTER_TEXT_VERSION).count() == 2

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
                {
                    "email": ["existing@example.com"],
                    "pdp_consent": True,
                    "consent_text_version": NEWSLETTER_TEXT_VERSION,
                },
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
        # Версия формулировки передаётся действующая: тест про утечку статуса
        # подписки, а не про устаревшую форму. Без неё ответ ушёл бы в ветку
        # `consent_text_outdated` и проверял бы не то.
        data = {"email": "known-subscriber@example.com", "consent_text_version": NEWSLETTER_TEXT_VERSION}

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
        data = {
            "email": "unsubscribed@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="unsubscribed@example.com")
        assert subscription.is_active is True
        assert subscription.unsubscribed_at is None

    @pytest.mark.django_db(transaction=True)
    def test_subscribe_serializer_save_can_run_outside_view_atomic(self):
        """SubscribeSerializer.save() сам открывает transaction для select_for_update."""
        serializer = SubscribeSerializer(
            data={
                "email": "serializer-direct@example.com",
                "pdp_consent": True,
                "consent_text_version": NEWSLETTER_TEXT_VERSION,
            }
        )

        assert serializer.is_valid(), serializer.errors
        subscription = serializer.save()

        assert subscription.email == "serializer-direct@example.com"
        assert Newsletter.objects.filter(email="serializer-direct@example.com").exists()

    def test_subscribe_invalid_email(self, api_client):
        """Возвращает 400 для некорректного email."""
        url = reverse("common:subscribe")
        data = {"email": "invalid-email", "pdp_consent": True, "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in response.data

    def test_subscribe_email_normalization(self, api_client):
        """Подтверждает нормализацию email в lowercase."""
        url = reverse("common:subscribe")
        data = {"email": "TestUser@EXAMPLE.COM", "pdp_consent": True, "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        subscription = Newsletter.objects.get(email="testuser@example.com")
        assert subscription.email == "testuser@example.com"

    def test_subscribe_requires_pdp_consent(self, api_client):
        """Без явного согласия подписка отклоняется."""
        url = reverse("common:subscribe")
        # Версия действующая: проверяется отсутствие галочки, а не устаревшая форма.
        data = {"email": "missing-consent@example.com", "consent_text_version": NEWSLETTER_TEXT_VERSION}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert not Newsletter.objects.filter(email="missing-consent@example.com").exists()

    def test_subscribe_serializer_validate_rejects_non_mapping_initial_data(self):
        """Strict consent guard не должен падать на non-object JSON payload."""
        serializer = SubscribeSerializer()
        serializer.initial_data = []

        with pytest.raises(serializers.ValidationError) as exc_info:
            serializer.validate(
                {
                    "email": "array-payload@example.com",
                    "pdp_consent": True,
                    "consent_text_version": NEWSLETTER_TEXT_VERSION,
                }
            )

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
        data = {
            "email": "false-consent@example.com",
            "pdp_consent": False,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert str(response.data["pdp_consent"][0]) == PDP_CONSENT_REQUIRED
        assert not Newsletter.objects.filter(email=data["email"]).exists()

    def test_subscribe_rejects_outdated_consent_text_version(self, api_client):
        """Вкладка с прежним текстом согласия отклоняется, а не пишет чужую формулировку.

        Форма присылает версию текста, который показала. Если формулировку с тех
        пор поправили, согласие относится к тому, чего человек не видел, — такой
        запрос обязан быть отклонён с требованием обновить страницу.
        """
        url = reverse("common:subscribe")
        data = {
            "email": "outdated-version@example.com",
            "pdp_consent": True,
            "consent_text_version": "2020-01-01-deadbeef",
        }

        response = api_client.post(url, data, format="json")

        # Проверка идёт по отрендеренному JSON, а не по `response.data`:
        # `ErrorDetail.code` живёт только внутри Python и до клиента не доходит,
        # поэтому машинный код обязан стоять верхним уровнем ответа.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": CONSENT_TEXT_OUTDATED_CODE,
            "details": {"consent_text_version": [CONSENT_TEXT_OUTDATED]},
        }
        assert not Newsletter.objects.filter(email=data["email"]).exists()
        assert UserConsent.objects.count() == 0

    def test_subscribe_rejects_missing_consent_text_version(self, api_client):
        """Форма старого бандла версии не присылает — это тоже устаревшая форма.

        Внутренний код DRF у пропущенного поля — `required`, а не
        `consent_text_outdated`. Клиенту от этого не легче: случай тот же, и
        машинный код в ответе обязан быть тем же.
        """
        url = reverse("common:subscribe")
        data = {"email": "no-version@example.com", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": CONSENT_TEXT_OUTDATED_CODE,
            "details": {"consent_text_version": [CONSENT_TEXT_OUTDATED]},
        }
        assert not Newsletter.objects.filter(email=data["email"]).exists()
        assert UserConsent.objects.count() == 0

    def test_subscribe_outdated_version_response_keeps_other_field_errors(self, api_client):
        """Попутные ошибки запроса не пропадают из-за переезда полей в `details`."""
        url = reverse("common:subscribe")
        data = {"email": "not-an-email", "pdp_consent": True}

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["error"] == CONSENT_TEXT_OUTDATED_CODE
        assert body["details"]["consent_text_version"] == [CONSENT_TEXT_OUTDATED]
        assert body["details"]["email"], "ошибка email обязана остаться в ответе"

    @pytest.mark.parametrize(
        ("overrides", "other_field"),
        [
            ({"email": "not-an-email"}, "email"),
            ({"pdp_consent": None}, "pdp_consent"),
        ],
        ids=["invalid-email", "null-pdp-consent"],
    )
    def test_subscribe_outdated_version_survives_other_field_error(self, api_client, overrides, other_field):
        """Синтаксически валидная, но устаревшая версия не теряется рядом с ошибкой другого поля.

        DRF собирает field-level ошибки всех полей, а object-level `validate()` при
        любой из них не вызывает. Сверка версии в `validate()` пропадала бы молча:
        ответ ушёл бы плоским, без машинного кода, по которому фронт требует
        обновить страницу, — и человек правил бы email на устаревшей форме.
        """
        url = reverse("common:subscribe")
        data = {
            "email": "outdated-and-invalid@example.com",
            "pdp_consent": True,
            "consent_text_version": "2020-01-01-deadbeef",
            **overrides,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert body["error"] == CONSENT_TEXT_OUTDATED_CODE
        assert body["details"]["consent_text_version"] == [CONSENT_TEXT_OUTDATED]
        assert body["details"][other_field], f"ошибка {other_field} обязана остаться в ответе"
        assert UserConsent.objects.count() == 0

    @pytest.mark.parametrize(
        "version",
        [["2020-01-01-deadbeef"], {"version": "2020-01-01-deadbeef"}, True, 20200101],
        ids=["list", "object", "boolean", "number"],
    )
    def test_subscribe_non_string_consent_text_version_asks_to_refresh_page(self, api_client, version):
        """Нестроковая версия получает то же требование обновить страницу, что и устаревшая.

        Любая ошибка поля версии помечает ответ `consent_text_outdated`, а фронт
        показывает текст из этого поля. DRF `CharField` на массив, объект и boolean
        отвечает кодом `invalid` со своим «Not a valid string.» — без
        переопределения человек увидел бы его вместо требования обновить страницу
        (седьмой круг ревью стори 41.9). Число DRF приводит к строке, и его
        отклоняет сверка с реестром — вариант фиксирует, что сообщение то же.
        """
        url = reverse("common:subscribe")
        data = {
            "email": "non-string-version@example.com",
            "pdp_consent": True,
            "consent_text_version": version,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": CONSENT_TEXT_OUTDATED_CODE,
            "details": {"consent_text_version": [CONSENT_TEXT_OUTDATED]},
        }
        assert not Newsletter.objects.filter(email=data["email"]).exists()
        assert UserConsent.objects.count() == 0

    @pytest.mark.parametrize(
        "version",
        ["2020-01-01-dead\x00beef", "2020-01-01-\ud800"],
        ids=["null-character", "lone-surrogate"],
    )
    def test_subscribe_version_rejected_by_field_validator_asks_to_refresh_page(self, api_client, version):
        """Строка, отсечённая валидатором `CharField`, получает то же требование обновить страницу.

        Ноль-байт и одиночный суррогат `CharField` отклоняет собственными
        валидаторами, и их сообщения ключами `error_messages` поля не
        переопределяются. Текст выравнивает `consent_text_outdated_payload()` —
        единая точка для любого отказа по полю версии (седьмой круг ревью
        стори 41.9, решение Alex).
        """
        url = reverse("common:subscribe")
        data = {
            "email": "validator-rejected-version@example.com",
            "pdp_consent": True,
            "consent_text_version": version,
        }

        # Одиночный суррогат в UTF-8 не кодируется, поэтому тело собирается
        # `json.dumps` с ASCII-экранированием — так его пришлёт внешний клиент.
        response = api_client.post(url, json.dumps(data), content_type="application/json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.json() == {
            "error": CONSENT_TEXT_OUTDATED_CODE,
            "details": {"consent_text_version": [CONSENT_TEXT_OUTDATED]},
        }
        assert not Newsletter.objects.filter(email=data["email"]).exists()
        assert UserConsent.objects.count() == 0

    def test_subscribe_plain_validation_error_keeps_flat_shape(self, api_client):
        """Обычная валидация возвращается плоским объектом — контракт не сдвинут."""
        url = reverse("common:subscribe")
        data = {
            "email": "flat-shape@example.com",
            "pdp_consent": False,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        body = response.json()
        assert "error" not in body
        assert body["pdp_consent"] == [PDP_CONSENT_REQUIRED]

    def test_subscribe_creates_two_consent_records_for_anonymous(self, api_client):
        """Анонимная подписка пишет два согласия с session_key."""
        url = reverse("common:subscribe")
        data = {
            "email": "anonymous-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        # Story 41.9: источник у обеих записей — подписка; версия одна на обе,
        # потому что чекбокс формы подписки один и покрывает оба согласия.
        assert all(consent.source == UserConsent.SOURCE_NEWSLETTER for consent in consents)
        expected_version = current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract")
        assert {consent.consent_text_version for consent in consents} == {expected_version}

    def test_subscribe_newsletter_ip_uses_normalized_audit_ip(self, api_client):
        """Newsletter.latest IP использует REMOTE_ADDR fallback при невалидном proxy-IP."""
        url = reverse("common:subscribe")
        data = {
            "email": "invalid-newsletter-ip@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "private-ip-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "authenticated-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        # Story 41.9: источник и версия не зависят от того, авторизован ли подписчик.
        assert all(consent.source == UserConsent.SOURCE_NEWSLETTER for consent in consents)
        expected_version = current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "marketing_email")
        assert {consent.consent_text_version for consent in consents} == {expected_version}

    def test_subscribe_consent_records_capture_ip_and_user_agent(self, api_client):
        """Audit-записи используют валидный first hop X-Forwarded-For и User-Agent."""
        url = reverse("common:subscribe")
        data = {
            "email": "ip-user-agent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "x-real-ip-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "long-user-agent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }
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
            source=UserConsent.SOURCE_NEWSLETTER,
            consent_text_version=current_consent_text_version(UserConsent.SOURCE_NEWSLETTER, "pdp_contract"),
        )
        initial_consent_count = UserConsent.objects.count()

        url = reverse("common:subscribe")
        data = {
            "email": "reactivation-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "locked-reactivation@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        with CaptureQueriesContext(connection) as captured_queries:
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert any(" FOR UPDATE" in query["sql"].upper() for query in captured_queries.captured_queries)

    def test_subscribe_atomic_rollback_on_consent_failure(self, api_client):
        """Если consent audit не записался, клиент получает JSON 503 и Newsletter откатывается."""
        url = reverse("common:subscribe")
        data = {
            "email": "rollback-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }
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
        data = {
            "email": "operational-consent@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
        data = {
            "email": "session-before-atomic@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }
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
        data = {
            "email": "session-failure@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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

    def test_subscribe_unique_race_records_consent_of_second_request(self, api_client):
        """Гонка на уникальном email: нейтральный 200 — и согласие второго запроса записано.

        Параллельный запрос успел создать подписку между чтением строки и вставкой.
        Прежде второй запрос отвечал «уже подписан» и не писал ни одной записи —
        явное согласие терялось (шестой круг ревью стори 41.9). Гонка воспроизводится
        по-настоящему: строка уже есть, первое чтение её «не видит» (как до коммита
        конкурента), а вставка падает на реальном уникальном ограничении.
        """
        Newsletter.objects.create(email="unique-race@example.com", is_active=True)
        original_select_for_update = Newsletter.objects.select_for_update
        lookups = []

        def racing_select_for_update(*args, **kwargs):
            lookups.append(True)
            queryset = original_select_for_update(*args, **kwargs)
            # Первое чтение — снимок до коммита параллельного запроса.
            return queryset.none() if len(lookups) == 1 else queryset

        url = reverse("common:subscribe")
        data = {
            "email": "unique-race@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        with patch.object(Newsletter.objects, "select_for_update", side_effect=racing_select_for_update):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_200_OK
        assert response.data == {
            "message": "Вы успешно подписались на рассылку",
            "email": "unique-race@example.com",
        }
        assert len(lookups) == 2, "после IntegrityError строка подписки не перечитана"
        assert Newsletter.objects.filter(email="unique-race@example.com").count() == 1
        consents = list(UserConsent.objects.order_by("consent_type"))
        assert [consent.consent_type for consent in consents] == ["marketing_email", "pdp_contract"]
        assert {consent.consent_text_version for consent in consents} == {NEWSLETTER_TEXT_VERSION}

    def test_subscribe_integrity_error_without_subscription_row_is_not_success(self, api_client):
        """IntegrityError, после которого строки подписки нет, — не гонка: 503 и ничего не записано.

        Нейтральный успех здесь был бы неправдой: подписка не создана, согласие
        не сохранено. Enumeration это не открывает — строки с этим email нет.
        """
        url = reverse("common:subscribe")
        data = {
            "email": "integrity-no-row@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

        with patch.object(Newsletter.objects, "create", side_effect=IntegrityError("not a unique race")):
            response = api_client.post(url, data, format="json")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert response.data["error"] == "consent_persistence_failed"
        assert not Newsletter.objects.filter(email="integrity-no-row@example.com").exists()
        assert UserConsent.objects.count() == 0

    def test_subscribe_anonymous_creates_session_key(self, api_client):
        """У анонимной подписки обе consent-записи получают непустой session_key."""
        url = reverse("common:subscribe")
        data = {
            "email": "anonymous-session@example.com",
            "pdp_consent": True,
            "consent_text_version": NEWSLETTER_TEXT_VERSION,
        }

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
                    {
                        "email": f"throttle-{index}@example.com",
                        "pdp_consent": True,
                        "consent_text_version": NEWSLETTER_TEXT_VERSION,
                    },
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

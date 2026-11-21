"""Письмо заявителю об отклонении B2B-заявки: текст и обработка сбоя отправки."""

from __future__ import annotations

from smtplib import SMTPException
from unittest.mock import patch

import pytest
from celery.exceptions import Retry
from django.core import mail

from apps.users.tasks import send_b2b_rejection_email

pytestmark = pytest.mark.unit


def test_email_tells_about_rejection_and_points_to_site_contacts():
    sent = send_b2b_rejection_email.apply(args=("applicant@example.com", "Иван", "Тренер")).get()

    assert sent is True
    assert len(mail.outbox) == 1
    message = mail.outbox[0]
    assert message.to == ["applicant@example.com"]
    assert message.subject == "[OPTISPORT] Ваша заявка отклонена"
    assert "Иван" in message.body
    assert "отклонена" in message.body
    assert "контактам, указанным на сайте" in message.body
    assert "info@optisport.ru" in message.body
    html_body, mimetype = message.alternatives[0]
    assert mimetype == "text/html"
    assert "отклонена" in html_body


def test_email_without_name_still_has_greeting():
    send_b2b_rejection_email.apply(args=("applicant@example.com", "", "Тренер")).get()

    assert "Уважаемый(ая) клиент," in mail.outbox[0].body


def test_plain_text_body_is_not_html_escaped():
    send_b2b_rejection_email.apply(args=("applicant@example.com", "О'Брайен & Ко", "Тренер")).get()

    assert "О'Брайен & Ко" in mail.outbox[0].body


def test_smtp_failure_is_retried():
    with patch("apps.users.tasks.send_mail", side_effect=SMTPException("сервер почты недоступен")):
        with pytest.raises(Retry):
            send_b2b_rejection_email.apply(
                args=("applicant@example.com", "Иван", "Тренер"), throw=True, retries=0
            ).get()

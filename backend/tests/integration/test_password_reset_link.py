"""
Ссылка восстановления пароля обязана вести на публичный адрес сайта.

Story 36.3 (tech-debt #7): базовый адрес был захардкожен как
`http://localhost:3000`, поэтому на продакшене письмо сброса пароля уводило
получателя на его собственную машину — восстановить пароль было нельзя.
Тесты закрывают AC-1..AC-3 стори: адрес берётся из `settings.SITE_URL`,
склейка устойчива к завершающему слэшу, а путь остаётся тем, который
обслуживает фронт (`/password-reset/confirm/[uid]/[token]`).
"""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APIClient

from apps.users.models import User

pytestmark = [pytest.mark.integration, pytest.mark.django_db]

PASSWORD_RESET_URL = "/api/v1/auth/password-reset/"
PROD_SITE_URL = "https://optisport.ru"


def unique_email(prefix: str) -> str:
    return f"{prefix}_{time.time_ns()}@example.com"


@pytest.fixture
def account() -> User:
    return User.objects.create_user(
        email=unique_email("reset_link"),
        password="StrongPassword123!",
        role="retail",
    )


def post_reset(email: str) -> tuple[int, MagicMock]:
    """Запрашивает сброс пароля, возвращая код ответа и мок задачи отправки."""
    with patch("apps.users.views.authentication.send_password_reset_email.delay") as send_email:
        response = APIClient().post(PASSWORD_RESET_URL, {"email": email}, format="json")

    return response.status_code, send_email


def request_reset_link(account: User) -> str:
    """Возвращает ссылку, ушедшую в задачу отправки письма."""
    status_code, send_email = post_reset(account.email)

    assert status_code == status.HTTP_200_OK
    send_email.assert_called_once()
    return send_email.call_args.args[1]


@pytest.mark.parametrize(
    "site_url",
    [PROD_SITE_URL, f"{PROD_SITE_URL}/"],
    ids=["без завершающего слэша", "с завершающим слэшем"],
)
def test_reset_link_host_comes_from_site_url(settings, account, site_url):
    """
    Хост ссылки — тот, что настроен в окружении, а не машина разработчика.

    Завершающий слэш в `SITE_URL` не должен давать `//password-reset` (AC-3):
    двойной слэш ломает сопоставление маршрута на фронте.
    """
    settings.SITE_URL = site_url

    link = request_reset_link(account)

    assert link.startswith(f"{PROD_SITE_URL}/password-reset/confirm/")
    assert "localhost" not in link
    assert "//password-reset" not in link


def test_reset_link_path_matches_frontend_route(settings, account):
    """
    Путь обязан совпасть с маршрутом фронта.

    Иначе смена хоста чинит письмо и ломает переход: страница
    `password-reset/confirm/[uid]/[token]` ждёт оба сегмента.
    """
    settings.SITE_URL = PROD_SITE_URL

    link = request_reset_link(account)

    uid = urlsafe_base64_encode(force_bytes(account.pk))
    prefix = f"{PROD_SITE_URL}/password-reset/confirm/{uid}/"
    assert link.startswith(prefix)
    assert link.endswith("/")
    assert link[len(prefix) : -1], "Токен в ссылке пуст"


def test_unknown_email_gets_generic_ok_without_sending(settings):
    """
    Регресс: смена источника адреса не должна раскрывать существование email.

    Ответ обезличен (200), письмо не уходит — иначе появляется вектор
    перечисления зарегистрированных адресов.
    """
    settings.SITE_URL = PROD_SITE_URL

    status_code, send_email = post_reset(unique_email("does_not_exist"))

    assert status_code == status.HTTP_200_OK
    send_email.assert_not_called()

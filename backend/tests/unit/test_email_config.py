"""
Unit тесты для email конфигурации.
Story 29.3: Email Server Configuration

Тестирует:
- Наличие и корректность EMAIL_* settings
- Формат ADMINS списка
- DEFAULT_FROM_EMAIL формат
"""

import pytest
from django.conf import settings


@pytest.mark.unit
class TestEmailConfiguration:
    """Unit тесты для проверки email конфигурации Django."""

    def test_email_backend_is_configured(self):
        """EMAIL_BACKEND должен быть настроен."""
        assert hasattr(settings, "EMAIL_BACKEND")
        assert settings.EMAIL_BACKEND is not None
        assert "EmailBackend" in settings.EMAIL_BACKEND

    def test_email_host_is_configured(self):
        """EMAIL_HOST должен быть настроен."""
        assert hasattr(settings, "EMAIL_HOST")
        assert settings.EMAIL_HOST is not None
        assert len(settings.EMAIL_HOST) > 0

    def test_email_port_is_integer(self):
        """EMAIL_PORT должен быть целым числом."""
        assert hasattr(settings, "EMAIL_PORT")
        assert isinstance(settings.EMAIL_PORT, int)
        assert settings.EMAIL_PORT > 0

    def test_email_use_tls_is_boolean(self):
        """EMAIL_USE_TLS должен быть булевым значением."""
        assert hasattr(settings, "EMAIL_USE_TLS")
        assert isinstance(settings.EMAIL_USE_TLS, bool)

    def test_default_from_email_is_set(self):
        """DEFAULT_FROM_EMAIL должен быть настроен и содержать @."""
        assert hasattr(settings, "DEFAULT_FROM_EMAIL")
        assert settings.DEFAULT_FROM_EMAIL
        assert "@" in settings.DEFAULT_FROM_EMAIL

    def test_server_email_is_set(self):
        """SERVER_EMAIL должен быть настроен."""
        assert hasattr(settings, "SERVER_EMAIL")
        assert settings.SERVER_EMAIL is not None

    def test_admins_list_format(self):
        """ADMINS должен быть списком кортежей (name, email)."""
        assert hasattr(settings, "ADMINS")
        assert isinstance(settings.ADMINS, list)

        for admin in settings.ADMINS:
            assert isinstance(admin, tuple), f"ADMINS entry должен быть tuple: {admin}"
            assert len(admin) == 2, f"ADMINS tuple должен иметь 2 элемента: {admin}"
            name, email = admin
            assert isinstance(name, str), f"Admin name должен быть строкой: {name}"
            assert "@" in email, f"Admin email должен содержать @: {email}"

    def test_managers_equals_admins(self):
        """MANAGERS должен быть равен ADMINS."""
        assert hasattr(settings, "MANAGERS")
        assert settings.MANAGERS == settings.ADMINS


@pytest.mark.unit
class TestEmailBackendTypes:
    """Тесты для проверки допустимых типов email backend."""

    VALID_BACKENDS = [
        "django.core.mail.backends.smtp.EmailBackend",
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.locmem.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    ]

    def test_email_backend_is_valid_django_backend(self):
        """EMAIL_BACKEND должен быть валидным Django backend."""
        backend = settings.EMAIL_BACKEND
        assert any(
            valid in backend for valid in self.VALID_BACKENDS
        ), f"EMAIL_BACKEND '{backend}' не является стандартным Django backend"


@pytest.mark.unit
class TestEmailPortConfiguration:
    """Тесты для проверки конфигурации портов."""

    COMMON_SMTP_PORTS = [25, 465, 587, 1025, 2525]

    def test_email_port_is_common_smtp_port(self):
        """EMAIL_PORT должен быть одним из стандартных SMTP портов."""
        port = settings.EMAIL_PORT
        assert port in self.COMMON_SMTP_PORTS, (
            f"EMAIL_PORT {port} не является стандартным SMTP портом. " f"Ожидается один из: {self.COMMON_SMTP_PORTS}"
        )

    def test_tls_ssl_mutual_exclusion(self):
        """EMAIL_USE_TLS и EMAIL_USE_SSL не должны быть True одновременно."""
        use_tls = getattr(settings, "EMAIL_USE_TLS", False)
        use_ssl = getattr(settings, "EMAIL_USE_SSL", False)

        assert not (use_tls and use_ssl), (
            "EMAIL_USE_TLS и EMAIL_USE_SSL не могут быть True одновременно. "
            "Используйте TLS для порта 587, SSL для порта 465."
        )

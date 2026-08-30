"""Unit-тесты proxy-aware throttling helpers."""

from types import SimpleNamespace

import pytest
from django.conf import settings

from apps.common.throttling import (
    ProxyAwareAnonRateThrottle,
    ProxyAwareUserRateThrottle,
    SubscribeRateThrottle,
)


pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "throttle_cls",
    [ProxyAwareAnonRateThrottle, ProxyAwareUserRateThrottle, SubscribeRateThrottle],
)
@pytest.mark.parametrize(
    ("raw_ident", "expected_ident"),
    [
        ("[::1]:8080", "::1"),
        ("::ffff:192.0.2.1", "192.0.2.1"),
        ("fe80::1%eth0", "fe80::1"),
        (" 198.51.100.77 ", "198.51.100.77"),
    ],
)
def test_proxy_aware_throttle_sanitizes_to_canonical_ip(throttle_cls, raw_ident, expected_ident):
    """Throttle cache key использует canonical IP, а не raw variant из proxy header."""
    assert throttle_cls()._sanitize_ident(raw_ident) == expected_ident


def test_proxy_aware_throttle_falls_back_to_log_safe_value_for_invalid_ident():
    """Невалидный ident остается Redis-safe через log sanitizer."""
    assert ProxyAwareAnonRateThrottle()._sanitize_ident("bad\r\nip") == "bad\\r\\nip"


def test_proxy_aware_throttle_remote_addr_fallback_is_sanitized():
    """REMOTE_ADDR fallback тоже должен проходить через Redis-safe sanitizer."""
    request = SimpleNamespace(META={"REMOTE_ADDR": "bad\r\nip"})

    assert ProxyAwareAnonRateThrottle().get_ident(request) == "bad\\r\\nip"


@pytest.mark.parametrize(
    "header_name",
    ["HTTP_X_REAL_IP", "HTTP_X_FORWARDED_FOR"],
)
def test_proxy_aware_throttle_uses_remote_addr_for_malformed_proxy_header(header_name):
    """Malformed proxy header не должен создавать отдельный throttle bucket."""
    request = SimpleNamespace(
        META={
            header_name: "rotating-bad-header",
            "REMOTE_ADDR": "198.51.100.77",
        }
    )

    assert ProxyAwareAnonRateThrottle().get_ident(request) == "198.51.100.77"


def test_test_settings_use_high_throttle_rates():
    """Тестовое окружение не должно наследовать production-like лимиты из base.py."""
    rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]

    assert rates["anon"] == "100000/min"
    assert rates["user"] == "100000/min"
    assert rates["subscribe"] == "100000/min"

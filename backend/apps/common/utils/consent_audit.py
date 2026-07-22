"""Audit-helpers для записи UserConsent (152-ФЗ)."""

from __future__ import annotations

import logging
import re
from ipaddress import ip_address as parse_ip_address
from typing import Any, cast

from rest_framework.request import Request

logger = logging.getLogger("apps.common.consent_audit")

MAX_CONSENT_USER_AGENT_LENGTH = 512
MAX_LOG_VALUE_LENGTH = 128
IPV4_OCTET_RE = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4_PORT_RE = r"(?:6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3})"
IPV4_WITH_PORT_RE = re.compile(rf"^(?P<ip>{IPV4_OCTET_RE}(?:\.{IPV4_OCTET_RE}){{3}}):(?P<port>{IPV4_PORT_RE})$")
UNSAFE_LOG_CHAR_ESCAPES = {
    "\x00": "\\x00",
    "\r": "\\r",
    "\n": "\\n",
    "\x1b": "\\x1b",
    "\u200b": "\\u200b",
    "\u200c": "\\u200c",
    "\u200d": "\\u200d",
    "\u2028": "\\u2028",
    "\u2029": "\\u2029",
    "\u202a": "\\u202a",
    "\u202b": "\\u202b",
    "\u202c": "\\u202c",
    "\u202d": "\\u202d",
    "\u202e": "\\u202e",
    "\u2066": "\\u2066",
    "\u2067": "\\u2067",
    "\u2068": "\\u2068",
    "\u2069": "\\u2069",
    "\ufeff": "\\ufeff",
}


def get_client_ip(request: Request) -> str:
    """Извлечь IP клиента (X-Real-IP, X-Forwarded-For first hop или REMOTE_ADDR)."""
    x_real_ip = request.META.get("HTTP_X_REAL_IP")
    if x_real_ip:
        ip = str(x_real_ip).strip()
        if ip:
            return cast(str, ip)

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0].strip()
        if ip:
            return cast(str, ip)

    ip = request.META.get("REMOTE_ADDR", "unknown")
    return cast(str, ip)


def normalize_consent_ip(raw_ip: str) -> str | None:
    """Нормализовать IP из audit-заголовка перед записью в PostgreSQL inet."""
    candidate = raw_ip.strip()
    if not candidate:
        return None

    if candidate.startswith("["):
        closing_bracket_index = candidate.find("]")
        if closing_bracket_index == -1:
            return None

        host = candidate[1:closing_bracket_index]
        port_suffix = candidate[closing_bracket_index + 1 :]
        if port_suffix:
            if not port_suffix.startswith(":"):
                return None

            port = port_suffix[1:]
            if not port.isdigit() or not (1 <= int(port) <= 65535):
                return None
        candidate = host
    else:
        ipv4_with_port_match = IPV4_WITH_PORT_RE.match(candidate)
        if ipv4_with_port_match:
            candidate = ipv4_with_port_match.group("ip")

    if "%" in candidate:
        candidate = candidate.split("%", 1)[0]

    try:
        parsed_ip = parse_ip_address(candidate)
    except ValueError:
        return None

    mapped_ipv4 = getattr(parsed_ip, "ipv4_mapped", None)
    if mapped_ipv4 is not None:
        return str(mapped_ipv4)

    if getattr(parsed_ip, "scope_id", None):
        return None

    return str(parsed_ip)


def sanitize_log_value(value: str) -> str:
    """Сжать и экранировать внешнее значение перед записью в structured log."""
    value = value.encode("utf-8", "ignore").decode("utf-8")
    sanitized_parts: list[str] = []
    sanitized_length = 0

    for char in value:
        token = UNSAFE_LOG_CHAR_ESCAPES.get(char, char)
        if sanitized_length + len(token) > MAX_LOG_VALUE_LENGTH:
            break

        sanitized_parts.append(token)
        sanitized_length += len(token)

    return "".join(sanitized_parts)


def sanitize_consent_user_agent(user_agent: Any) -> str:
    """Удалить невалидные UTF-8 surrogate-символы и ограничить длину User-Agent."""
    safe_user_agent = str(user_agent or "").encode("utf-8", "ignore").decode("utf-8")
    return safe_user_agent[:MAX_CONSENT_USER_AGENT_LENGTH]


def get_consent_ip_address(request: Request) -> str | None:
    """
    Получить валидный IP для audit-записи согласия.

    Заголовок X-Forwarded-For приходит извне, поэтому невалидное значение
    нельзя напрямую сохранять в PostgreSQL inet-поле.
    """
    client_ip = get_client_ip(request)
    if client_ip == "unknown":
        logger.warning("Unknown client IP skipped for consent audit")
        return None

    normalized_ip = normalize_consent_ip(client_ip)
    if normalized_ip is None:
        remote_addr = request.META.get("REMOTE_ADDR")
        if remote_addr:
            normalized_remote_addr = normalize_consent_ip(str(remote_addr))
            if normalized_remote_addr is not None:
                return normalized_remote_addr

        logger.warning(
            "Invalid client IP skipped for consent audit",
            extra={"client_ip": sanitize_log_value(client_ip)},
        )
        return None

    return normalized_ip

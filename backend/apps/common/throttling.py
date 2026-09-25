from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle, UserRateThrottle

from apps.common.utils.consent_audit import normalize_consent_ip, sanitize_log_value


class ProxyAwareThrottleIdentMixin:
    """Единый proxy-aware ident для DRF throttle cache keys."""

    def _sanitize_ident(self, ident):
        """Вернуть Redis-safe throttle ident из внешнего IP-заголовка."""
        raw_ident = str(ident).strip()
        return normalize_consent_ip(raw_ident) or sanitize_log_value(raw_ident)

    def _get_proxy_ident_or_remote_addr(self, request, ident):
        raw_ident = str(ident).strip()
        normalized_ident = normalize_consent_ip(raw_ident)
        if normalized_ident is not None:
            return normalized_ident

        return self._sanitize_ident(request.META.get("REMOTE_ADDR", ""))

    def get_ident(self, request):
        # Nginx sets X-Real-IP to the client's IP address
        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return self._get_proxy_ident_or_remote_addr(request, x_real_ip)

        # Fallback to X-Forwarded-For
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # The first IP in the list is usually the client's IP
            return self._get_proxy_ident_or_remote_addr(request, x_forwarded_for.split(",")[0])

        # Fallback to standard behavior (REMOTE_ADDR)
        return self._sanitize_ident(request.META.get("REMOTE_ADDR", ""))


class ProxyAwareAnonRateThrottle(ProxyAwareThrottleIdentMixin, AnonRateThrottle):
    """
    Throttle class that correctly identifies the client IP address
    when running behind a reverse proxy (Nginx).
    Uses HTTP_X_REAL_IP or HTTP_X_FORWARDED_FOR headers.
    """

    pass


class ProxyAwareUserRateThrottle(ProxyAwareThrottleIdentMixin, UserRateThrottle):
    """User throttle с тем же безопасным proxy-aware ident для anonymous fallback."""

    pass


class SubscribeRateThrottle(ProxyAwareThrottleIdentMixin, SimpleRateThrottle):
    """Отдельный лимит для write-endpoint подписки на рассылку."""

    scope = "subscribe"

    def get_cache_key(self, request, view):
        """Сформировать cache key: SimpleRateThrottle оставляет этот метод abstract."""
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class UnsubscribeRateThrottle(ProxyAwareThrottleIdentMixin, SimpleRateThrottle):
    """Отдельный лимит для write-endpoint отписки от рассылки."""

    scope = "unsubscribe"

    def get_cache_key(self, request, view):
        """Сформировать cache key: SimpleRateThrottle оставляет этот метод abstract."""
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }

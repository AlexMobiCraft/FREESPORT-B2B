"""
Rate limiting for 1C Exchange endpoints (Story 5.2, AC12).

OWASP API Security: Unrestricted Resource Consumption protection.
"""

from rest_framework.throttling import SimpleRateThrottle


class OneCExchangeThrottle(SimpleRateThrottle):
    """General rate limit for all 1C exchange operations: 60 requests/min."""

    rate = "60/min"
    scope = "1c_exchange"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {
                "scope": self.scope,
                "ident": request.user.pk,
            }
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class OneCAuthThrottle(SimpleRateThrottle):
    """Stricter rate limit for authentication attempts: 10 requests/min."""

    rate = "10/min"
    scope = "1c_auth"

    def get_cache_key(self, request, view):
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }

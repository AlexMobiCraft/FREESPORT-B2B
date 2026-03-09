from rest_framework.throttling import AnonRateThrottle


class ProxyAwareAnonRateThrottle(AnonRateThrottle):
    """
    Throttle class that correctly identifies the client IP address
    when running behind a reverse proxy (Nginx).
    Uses HTTP_X_REAL_IP or HTTP_X_FORWARDED_FOR headers.
    """

    def get_ident(self, request):
        # Nginx sets X-Real-IP to the client's IP address
        x_real_ip = request.META.get("HTTP_X_REAL_IP")
        if x_real_ip:
            return x_real_ip

        # Fallback to X-Forwarded-For
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            # The first IP in the list is usually the client's IP
            return x_forwarded_for.split(",")[0].strip()

        # Fallback to standard behavior (REMOTE_ADDR)
        return super().get_ident(request)

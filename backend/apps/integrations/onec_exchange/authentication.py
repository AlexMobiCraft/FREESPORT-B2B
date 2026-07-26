from django.conf import settings
from django.contrib.auth import login
from rest_framework.authentication import BasicAuthentication, SessionAuthentication


class Basic1CAuthentication(BasicAuthentication):
    """
    Custom Basic Authentication for 1C Exchange.

    Inherits standard BasicAuthentication logic but serves as a distinct
    authentication class for 1C integration points. This separation allows
    future extensions specific to 1C auth quirks (e.g. handling specific 1C
    User-Agent or non-standard headers) without affecting global auth.
    """

    pass


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """
    SessionAuthentication that ignores CSRF check.
    Required because 1C does not send the standard Django CSRF header/cookie structure
    during file uploads (POST), but relies on the session cookie established in
    checkauth.
    """

    def enforce_csrf(self, request):
        return  # To not perform the csrf check checks

"""
Conftest for unit tests.

Overrides autouse fixtures from parent conftest to allow running
unit tests without Django database setup.
"""
import os
import sys

import pytest

# Configure Django settings before anything else
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "freesport.settings.development")

# Configure minimal Django settings
import django
from django.conf import settings

if not settings.configured:
    settings.configure(
        DEBUG=True,
        DATABASES={},
        INSTALLED_APPS=[],
        MEDIA_ROOT="/tmp/media",
        ONEC_EXCHANGE={
            "TEMP_DIR": "/tmp/1c_temp",
            "IMPORT_DIR": "/tmp/1c_import",
        },
    )


# Override autouse fixtures from parent conftest
@pytest.fixture(autouse=True)
def clear_db_before_test():
    """No-op for unit tests - no DB clearing needed."""
    yield


@pytest.fixture(autouse=True)
def enable_db_access_for_all_tests():
    """No-op for unit tests - no DB access needed."""
    yield

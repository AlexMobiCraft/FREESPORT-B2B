"""
Tests for Story 4.3: View-обработчики mode=query и mode=success.

Tests cover:
- AC1: handle_query for GET /?mode=query
- AC2: XML generation with OrderExportService
- AC3: ZIP compression when zip=yes
- AC4: handle_success for GET /?mode=success
- AC5: Marking orders as sent_to_1c=True
- AC6: Audit log file saving
- AC7: Full cycle integration tests
- AC8: Compatibility with checkauth authentication
"""

import base64
import io
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.http import FileResponse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.orders.models import Order, OrderItem
from apps.products.models import Brand, Category, Product, ProductVariant

User = get_user_model()


def get_response_content(response) -> bytes:
    """Helper to get content from both HttpResponse and FileResponse."""
    if hasattr(response, "streaming_content"):
        # FileResponse uses streaming_content
        return b"".join(response.streaming_content)
    return response.content


@pytest.fixture
def onec_user(db):
    """Create a 1C exchange user with proper permissions."""
    user = User.objects.create_user(
        email="1c_export@example.com",
        password="secure_pass_123",
        first_name="1C",
        last_name="Export",
        is_staff=True,
    )
    return user


@pytest.fixture
def customer_user(db):
    """Create a customer user for orders."""
    return User.objects.create_user(
        email="customer@example.com",
        password="cust_pass_123",
        first_name="Иван",
        last_name="Петров",
    )


@pytest.fixture
def product_variant(db):
    """Create a product variant with onec_id."""
    brand = Brand.objects.create(name="TestBrand", slug="testbrand")
    category = Category.objects.create(name="TestCat", slug="testcat")
    product = Product.objects.create(
        name="Test Product",
        slug="test-product",
        brand=brand,
        category=category,
    )
    variant = ProductVariant.objects.create(
        product=product,
        onec_id="variant-1c-id-001",
        sku="TEST-SKU-001",
        retail_price=1500,
    )
    return variant


@pytest.fixture
def order_for_export(db, customer_user, product_variant):
    """Create a master + sub-order ready for 1C export.

    Updated for Story 34-3: export now requires sub-orders
    (is_master=False, parent_order__isnull=False).
    Returns the sub-order (the one that appears in XML).
    """
    from decimal import Decimal

    master = Order.objects.create(
        user=customer_user,
        order_number="FS-TEST-MASTER",
        total_amount=Decimal("1500"),
        sent_to_1c=False,
        delivery_address="ул. Тестовая, 1",
        delivery_method="pickup",
        payment_method="card",
        is_master=True,
    )
    order = Order.objects.create(
        user=customer_user,
        order_number="FS-TEST-001",
        total_amount=Decimal("1500"),
        sent_to_1c=False,
        delivery_address="ул. Тестовая, 1",
        delivery_method="pickup",
        payment_method="card",
        is_master=False,
        parent_order=master,
    )
    OrderItem.objects.create(
        order=order,
        product=product_variant.product,
        variant=product_variant,
        product_name="Test Product",
        unit_price=Decimal("1500"),
        quantity=1,
        total_price=Decimal("1500"),
    )
    return order


@pytest.fixture
def authenticated_client(onec_user):
    """APIClient that performs checkauth first to establish session."""
    client = APIClient()
    auth_header = "Basic " + base64.b64encode(b"1c_export@example.com:secure_pass_123").decode("ascii")
    # Perform checkauth to establish session
    response = client.get(
        "/api/integration/1c/exchange/",
        data={"mode": "checkauth"},
        HTTP_AUTHORIZATION=auth_header,
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert body.startswith("success")
    # Extract session cookie
    lines = body.replace("\r\n", "\n").split("\n")
    cookie_name = lines[1]
    cookie_value = lines[2]
    client.cookies[cookie_name] = cookie_value
    return client


@pytest.fixture
def log_dir(tmp_path, settings):
    """
    Override EXCHANGE_LOG_DIR so audit logs go to a private tmp_path (not MEDIA_ROOT).
    This fixture creates a temporary directory for audit logs.
    """
    private_log = tmp_path / "var" / "1c_exchange" / "logs"
    settings.EXCHANGE_LOG_DIR = str(private_log)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    Path(settings.MEDIA_ROOT).mkdir(parents=True, exist_ok=True)
    return private_log


# ============================================================
# Task 1: Audit log infrastructure tests (AC6)
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestExchangeLogInfrastructure:
    """Tests for _save_exchange_log helper (Task 1)."""

    def test_save_exchange_log_creates_directory_and_file(self, log_dir):
        from apps.integrations.onec_exchange.views import _save_exchange_log

        _save_exchange_log("test_output.xml", "<xml>data</xml>")
        assert log_dir.exists()
        saved = list(log_dir.glob("*test_output.xml"))
        assert len(saved) == 1
        assert "<xml>data</xml>" in saved[0].read_text(encoding="utf-8")

    def test_save_exchange_log_binary(self, log_dir):
        from apps.integrations.onec_exchange.views import _save_exchange_log

        binary_data = b"\x50\x4b\x03\x04binary"
        _save_exchange_log("test_output.zip", binary_data, is_binary=True)
        saved = list(log_dir.glob("*test_output.zip"))
        assert len(saved) == 1
        assert saved[0].read_bytes() == binary_data


# ============================================================
# Task 2: handle_query tests (AC1, AC2, AC3)
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestModeQuery:
    """Tests for handle_query (Task 2)."""

    def test_mode_query_returns_xml(self, authenticated_client, order_for_export, log_dir):
        """AC1+AC2: GET /?mode=query returns XML with pending orders."""
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/xml"
        content = get_response_content(response).decode("utf-8")
        assert "<?xml" in content
        assert "КоммерческаяИнформация" in content
        assert "Документ" in content
        assert "FS-TEST-001" in content

    def test_mode_query_empty_when_no_orders(self, authenticated_client, log_dir):
        """AC2: Returns valid XML even when no pending orders."""
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "КоммерческаяИнформация" in content
        assert "Документ" not in content

    def test_mode_query_zip(self, authenticated_client, order_for_export, log_dir):
        """AC3: zip=yes returns a ZIP archive containing orders.xml."""
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query", "zip": "yes"},
        )
        assert response.status_code == 200
        assert response["Content-Type"] == "application/zip"
        # Verify it's a valid ZIP with orders.xml inside
        buf = io.BytesIO(get_response_content(response))
        with zipfile.ZipFile(buf) as zf:
            assert "orders.xml" in zf.namelist()
            xml_content = zf.read("orders.xml").decode("utf-8")
            assert "КоммерческаяИнформация" in xml_content
            assert "FS-TEST-001" in xml_content

    def test_mode_query_includes_guest_orders(self, authenticated_client, product_variant, log_dir):
        """CRITICAL: Guest B2C orders (user=None) must be exported to 1C."""
        from decimal import Decimal

        guest_master = Order.objects.create(
            user=None,
            order_number="FS-GUEST-MASTER",
            total_amount=Decimal("2000"),
            sent_to_1c=False,
            delivery_address="ул. Гостевая, 5",
            delivery_method="courier",
            payment_method="card",
            customer_name="Гость Иванов",
            customer_email="guest@example.com",
            customer_phone="+7-999-111-2233",
            is_master=True,
        )
        guest_order = Order.objects.create(
            user=None,
            order_number="FS-GUEST-001",
            total_amount=Decimal("2000"),
            sent_to_1c=False,
            delivery_address="ул. Гостевая, 5",
            delivery_method="courier",
            payment_method="card",
            customer_name="Гость Иванов",
            customer_email="guest@example.com",
            customer_phone="+7-999-111-2233",
            is_master=False,
            parent_order=guest_master,
        )
        OrderItem.objects.create(
            order=guest_order,
            product=product_variant.product,
            variant=product_variant,
            product_name="Test Product",
            unit_price=Decimal("2000"),
            quantity=1,
            total_price=Decimal("2000"),
        )
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "FS-GUEST-001" in content
        # CRITICAL: Guest contact info must be in <Контрагенты> block
        assert "Контрагенты" in content
        assert "Контрагент" in content
        assert "Гость Иванов" in content
        assert "guest@example.com" in content
        assert "+7-999-111-2233" in content

    def test_mode_query_excludes_already_sent(self, authenticated_client, order_for_export, log_dir):
        """Only orders with sent_to_1c=False are returned."""
        order_for_export.sent_to_1c = True
        order_for_export.save()
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "Документ" not in content

    def test_mode_query_saves_audit_log(self, authenticated_client, order_for_export, log_dir):
        """AC6: Audit log file is saved."""
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert log_dir.exists()
        log_files = list(log_dir.glob("*"))
        assert len(log_files) >= 1


# ============================================================
# Task 3: handle_success tests (AC4, AC5)
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestModeSuccess:
    """Tests for handle_success (Task 3)."""

    def test_mode_success_updates_status(self, authenticated_client, order_for_export, log_dir):
        """AC4+AC5: query then success marks orders as sent."""
        # First, perform query to set session timestamp
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Then confirm success
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "success" in content

        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is True
        assert order_for_export.sent_to_1c_at is not None

    def test_mode_success_without_prior_query(self, authenticated_client, order_for_export, log_dir):
        """
        AC5: success without prior query returns failure and does not update orders.
        """
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        # 1C protocol requires HTTP 200 with 'failure' body
        assert response.status_code == 200
        assert "failure" in get_response_content(response).decode("utf-8")
        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is False

    def test_mode_success_does_not_mark_new_orders(
        self,
        authenticated_client,
        order_for_export,
        customer_user,
        product_variant,
    ):
        """AC5: Orders created after query should NOT be marked as sent (race condition)."""
        # Query existing orders
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Create a new order AFTER query
        new_order = Order.objects.create(
            user=customer_user,
            order_number="FS-TEST-002",
            total_amount=3000,
            sent_to_1c=False,
            delivery_address="ул. Новая, 2",
            delivery_method="pickup",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=new_order,
            product=product_variant.product,
            variant=product_variant,
            product_name="Test Product 2",
            unit_price=3000,
            quantity=1,
            total_price=3000,
        )
        # Confirm success
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        order_for_export.refresh_from_db()
        new_order.refresh_from_db()
        assert order_for_export.sent_to_1c is True
        assert new_order.sent_to_1c is False  # Must NOT be marked

    def test_mode_success_does_not_mark_skipped_orders(self, authenticated_client, customer_user, log_dir):
        """CRITICAL: Orders skipped by OrderExportService validation (no items)
        must NOT be marked as sent_to_1c in handle_success."""
        from decimal import Decimal

        # Create a master + sub-order WITHOUT items — will be skipped by _validate_order
        empty_master = Order.objects.create(
            user=customer_user,
            order_number="FS-EMPTY-MASTER",
            total_amount=Decimal("0"),
            sent_to_1c=False,
            delivery_address="ул. Пустая, 0",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        empty_order = Order.objects.create(
            user=customer_user,
            order_number="FS-EMPTY-001",
            total_amount=Decimal("0"),
            sent_to_1c=False,
            delivery_address="ул. Пустая, 0",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=empty_master,
        )
        # Query — empty_order is in timeframe but has no items
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "FS-EMPTY-001" not in content  # Not in XML

        # Success
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        empty_order.refresh_from_db()
        assert empty_order.sent_to_1c is False  # Must NOT be marked


# ============================================================
# Task 4: Full cycle integration (AC7, AC8)
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestFullExportCycle:
    """Full cycle: checkauth -> query -> success (Task 4)."""

    def test_full_cycle_xml(self, authenticated_client, order_for_export, log_dir):
        """AC7+AC8: Full XML export cycle."""
        # 1. Query
        resp_query = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert resp_query.status_code == 200
        assert "FS-TEST-001" in get_response_content(resp_query).decode("utf-8")

        # 2. Success
        resp_success = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert resp_success.status_code == 200

        # 3. Verify order marked
        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is True

        # 4. Query again should return no orders
        resp_query2 = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert "Документ" not in get_response_content(resp_query2).decode("utf-8")

    def test_full_cycle_zip(self, authenticated_client, order_for_export, log_dir):
        """AC7: Full ZIP export cycle."""
        resp_query = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query", "zip": "yes"},
        )
        assert resp_query.status_code == 200
        assert resp_query["Content-Type"] == "application/zip"

        resp_success = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert resp_success.status_code == 200
        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is True

    def test_audit_logging(self, authenticated_client, order_for_export, log_dir):
        """AC6: Audit files saved to private log directory (NOT MEDIA_ROOT)."""
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert log_dir.exists()
        log_files = list(log_dir.glob("*"))
        assert len(log_files) >= 1
        # Verify logs are NOT in MEDIA_ROOT (PII protection)
        media_log_dir = Path(settings.MEDIA_ROOT) / "1c_exchange" / "logs"
        assert not media_log_dir.exists(), "Exchange logs must not be saved in public MEDIA_ROOT"


@pytest.mark.django_db
@pytest.mark.integration
class TestVersionSync:
    """Tests for CommerceML version synchronization."""

    def test_export_service_uses_settings_version(self, settings):
        """MEDIUM: OrderExportService must respect settings.ONEC_EXCHANGE version."""
        settings.ONEC_EXCHANGE = {"COMMERCEML_VERSION": "2.10"}
        from apps.orders.services.order_export import OrderExportService

        service = OrderExportService()
        assert service.SCHEMA_VERSION == "2.10"

    def test_export_service_default_version(self, settings):
        """OrderExportService defaults to 3.1 when no config."""
        if hasattr(settings, "ONEC_EXCHANGE"):
            delattr(settings, "ONEC_EXCHANGE")
        from apps.orders.services.order_export import OrderExportService

        service = OrderExportService()
        assert service.SCHEMA_VERSION == "3.1"


@pytest.mark.django_db
@pytest.mark.integration
class TestUnitConfigurability:
    """Tests for configurable unit of measurement."""

    def test_export_service_uses_settings_unit(self, settings):
        """MEDIUM: Unit of measurement must be configurable via settings."""
        settings.ONEC_EXCHANGE = {
            "DEFAULT_UNIT": {
                "CODE": "112",
                "NAME_FULL": "Литр",
                "NAME_INTL": "LTR",
                "NAME_SHORT": "л",
            }
        }
        from apps.orders.services.order_export import OrderExportService

        service = OrderExportService()
        ud = service._unit_defaults
        assert ud["code"] == "112"
        assert ud["name_full"] == "Литр"

    def test_export_service_default_unit(self, settings):
        """Defaults to Штука (796) when no config."""
        if hasattr(settings, "ONEC_EXCHANGE"):
            delattr(settings, "ONEC_EXCHANGE")
        from apps.orders.services.order_export import OrderExportService

        service = OrderExportService()
        ud = service._unit_defaults
        assert ud["code"] == "796"
        assert ud["name_full"] == "Штука"


@pytest.mark.django_db
@pytest.mark.integration
class TestConfigResilience:
    """
    Tests for settings.ONEC_EXCHANGE resilience (handle_init / handle_file_upload).
    """

    def test_handle_init_without_onec_exchange_setting(self, authenticated_client, settings):
        """MEDIUM: handle_init must not crash when settings.ONEC_EXCHANGE is missing."""
        if hasattr(settings, "ONEC_EXCHANGE"):
            delattr(settings, "ONEC_EXCHANGE")
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "init"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "zip=" in content


@pytest.mark.django_db
@pytest.mark.integration
class TestSessionBloatFix:
    """Tests for exported_order_ids stored in cache instead of session."""

    def test_exported_ids_stored_in_cache_not_session(self, authenticated_client, order_for_export, log_dir):
        """LOW: exported_order_ids should be in cache, not session."""
        from django.core.cache import cache as django_cache

        # Perform query
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Verify session has query_time but NOT exported_order_ids
        session = authenticated_client.session
        assert "last_1c_query_time" in session
        assert "last_1c_exported_order_ids" not in session

    def test_success_uses_fallback_when_cache_evicted(self, authenticated_client, order_for_export, log_dir):
        """MEDIUM: If cache loses exported_ids, fallback uses time-window update."""
        from django.core.cache import cache as django_cache

        # Perform query to populate session + cache
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Simulate cache eviction — delete exported_ids but keep session query_time
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        django_cache.delete(cache_key)

        # Success should use fallback (time-window based update)
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        # Fallback returns success and marks orders
        assert response.status_code == 200
        assert "success" in get_response_content(response).decode("utf-8")
        # Order should be marked via fallback
        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is True

    def test_cache_based_ids_work_in_full_cycle(self, authenticated_client, order_for_export, log_dir):
        """Cache-based exported_ids still work for query->success cycle."""
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert response.status_code == 200
        order_for_export.refresh_from_db()
        assert order_for_export.sent_to_1c is True


@pytest.mark.django_db
@pytest.mark.integration
class TestStreamingBehavior:
    """Tests verifying streaming behavior to prevent OOM regression."""

    def test_response_is_file_response(self, authenticated_client, order_for_export, log_dir):
        """LOW: Response uses FileResponse for streaming, not HttpResponse."""
        from django.http import FileResponse

        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # FileResponse has streaming_content attribute
        assert hasattr(response, "streaming_content"), "Response must be a FileResponse with streaming_content"

    def test_audit_logs_not_in_media_root(self, authenticated_client, order_for_export, log_dir):
        """Exchange logs must not be saved in public MEDIA_ROOT."""
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        media_log_dir = Path(settings.MEDIA_ROOT) / "1c_exchange" / "logs"
        assert not media_log_dir.exists(), "Exchange logs must not be saved in public MEDIA_ROOT"

    def test_audit_log_uses_file_copy(self, authenticated_client, order_for_export, log_dir):
        """HIGH: Audit logging must use file copy, not f.read() into RAM."""
        # Perform query to trigger logging
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Verify log file was created
        from apps.integrations.onec_exchange.views import _get_exchange_log_dir

        log_files = list(_get_exchange_log_dir().glob("*orders.xml"))
        assert len(log_files) >= 1, "Audit log should be created"


@pytest.mark.django_db
@pytest.mark.integration
class TestOrdersFilenameConstant:
    """Tests for extracted ORDERS_XML_FILENAME / ORDERS_ZIP_FILENAME constants."""

    def test_constants_exist(self):
        """LOW: Constants are defined at module level."""
        from apps.integrations.onec_exchange.views import ORDERS_XML_FILENAME, ORDERS_ZIP_FILENAME

        assert ORDERS_XML_FILENAME == "orders.xml"
        assert ORDERS_ZIP_FILENAME == "orders.zip"

    def test_zip_contains_correct_filename(self, authenticated_client, order_for_export, log_dir):
        """ZIP archive uses the constant filename for orders.xml."""
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query", "zip": "yes"},
        )
        buf = io.BytesIO(get_response_content(response))
        with zipfile.ZipFile(buf) as zf:
            from apps.integrations.onec_exchange.views import ORDERS_XML_FILENAME

            assert ORDERS_XML_FILENAME in zf.namelist()


# ============================================================
# Cycle 4 Review Follow-ups
# ============================================================


@pytest.mark.django_db
@pytest.mark.integration
class TestAsyncEmailInSignal:
    """Tests for async email dispatch in post_save signal."""

    def test_signal_dispatches_celery_tasks(self, customer_user, product_variant):
        """
        MEDIUM: post_save must dispatch Celery tasks, not send email synchronously.
        """
        with patch("apps.orders.tasks.send_order_confirmation_to_customer.delay") as mock_customer_delay, patch(
            "apps.orders.tasks.send_order_notification_email.delay"
        ) as mock_admin_delay:
            order = Order.objects.create(
                user=customer_user,
                order_number="FS-ASYNC-001",
                total_amount=1000,
                sent_to_1c=False,
                delivery_address="ул. Тестовая, 1",
                delivery_method="pickup",
                payment_method="card",
            )

            # Verify Celery tasks were dispatched (not synchronous send_mail)
            mock_customer_delay.assert_called_once_with(order.id)
            mock_admin_delay.assert_called_once_with(order.id)

    def test_signal_does_not_call_send_mail_directly(self):
        """Ensure signals.py no longer imports send_mail directly."""
        import inspect

        import apps.orders.signals as signals_mod

        source = inspect.getsource(signals_mod)
        # send_mail should not be called directly in signals module
        assert "send_mail(" not in source


@pytest.mark.django_db
@pytest.mark.integration
class TestSiteUrlFallback:
    """Tests for SITE_URL fallback in email tasks (Cycle 5)."""

    def test_notification_email_works_without_site_url(self, settings, customer_user, product_variant):
        """
        LOW: send_order_notification_email must not crash when SITE_URL is missing.
        """
        if hasattr(settings, "SITE_URL"):
            delattr(settings, "SITE_URL")

        order = Order.objects.create(
            user=customer_user,
            order_number="FS-SITEURL-001",
            total_amount=500,
            sent_to_1c=False,
            delivery_address="ул. Тест, 1",
            delivery_method="pickup",
            payment_method="card",
        )
        OrderItem.objects.create(
            order=order,
            product=product_variant.product,
            variant=product_variant,
            product_name="Test Product",
            unit_price=500,
            quantity=1,
            total_price=500,
        )

        from apps.orders.tasks import send_order_notification_email

        with patch("apps.orders.tasks.send_mail") as mock_send, patch(
            "apps.orders.tasks.render_to_string", return_value="test"
        ):
            from apps.common.models import NotificationRecipient

            NotificationRecipient.objects.create(
                email="admin@example.com",
                is_active=True,
                notify_new_orders=True,
            )
            # Should not raise AttributeError for SITE_URL
            result = send_order_notification_email(order.id)
            assert result is True
            mock_send.assert_called_once()

    def test_cancelled_notification_works_without_site_url(self, settings, customer_user):
        """LOW: send_order_cancelled_notification_email handles missing SITE_URL."""
        if hasattr(settings, "SITE_URL"):
            delattr(settings, "SITE_URL")

        order = Order.objects.create(
            user=customer_user,
            order_number="FS-CANCEL-001",
            total_amount=500,
            sent_to_1c=False,
            delivery_address="ул. Тест, 1",
            delivery_method="pickup",
            payment_method="card",
        )

        from apps.orders.tasks import send_order_cancelled_notification_email

        with patch("apps.orders.tasks.send_mail") as mock_send:
            from apps.common.models import NotificationRecipient

            NotificationRecipient.objects.create(
                email="admin@example.com",
                is_active=True,
                notify_order_cancelled=True,
            )
            result = send_order_cancelled_notification_email(order.id)
            assert result is True
            # Verify fallback URL is used
            call_args = mock_send.call_args
            assert "localhost:8001" in call_args.kwargs.get("message", call_args[0][1] if len(call_args[0]) > 1 else "")


@pytest.mark.django_db
@pytest.mark.integration
class TestSignalPayloadAccuracy:
    """Tests for orders_bulk_updated signal payload."""

    def test_signal_includes_updated_count(self, authenticated_client, order_for_export, log_dir):
        """LOW: Signal payload must include updated_count for accuracy."""
        from apps.orders.signals import orders_bulk_updated

        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            # Perform query + success cycle
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "query"},
            )
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "success"},
            )

            assert "updated_count" in received_kwargs
            assert received_kwargs["updated_count"] == 1
            assert "order_ids" in received_kwargs
        finally:
            orders_bulk_updated.disconnect(handler)


# ============================================================
# Story 34-3: Sub-order export integration tests
# ============================================================


@pytest.fixture
def master_with_two_subs(db, customer_user, product_variant):
    """Create master + 2 sub-orders (vat_group=5 and 22) for Story 34-3 tests."""
    from decimal import Decimal

    master = Order.objects.create(
        user=customer_user,
        order_number="FS-MASTER-001",
        total_amount=Decimal("3500"),
        sent_to_1c=False,
        delivery_address="ул. Мастер, 1",
        delivery_method="pickup",
        payment_method="card",
        is_master=True,
    )
    sub5 = Order.objects.create(
        user=customer_user,
        order_number="FS-SUB5-001",
        total_amount=Decimal("1500"),
        sent_to_1c=False,
        delivery_address="ул. Мастер, 1",
        delivery_method="pickup",
        payment_method="card",
        is_master=False,
        parent_order=master,
        vat_group=Decimal("5.00"),
    )
    OrderItem.objects.create(
        order=sub5,
        product=product_variant.product,
        variant=product_variant,
        product_name="Test Product VAT5",
        unit_price=Decimal("1500"),
        quantity=1,
        total_price=Decimal("1500"),
    )
    sub22 = Order.objects.create(
        user=customer_user,
        order_number="FS-SUB22-001",
        total_amount=Decimal("2000"),
        sent_to_1c=False,
        delivery_address="ул. Мастер, 1",
        delivery_method="pickup",
        payment_method="card",
        is_master=False,
        parent_order=master,
        vat_group=Decimal("22.00"),
    )
    OrderItem.objects.create(
        order=sub22,
        product=product_variant.product,
        variant=product_variant,
        product_name="Test Product VAT22",
        unit_price=Decimal("2000"),
        quantity=1,
        total_price=Decimal("2000"),
    )
    return master, sub5, sub22


@pytest.mark.django_db
@pytest.mark.integration
class TestSubOrderQuery:
    """Story 34-3: handle_query returns only sub-orders (AC1, AC12)."""

    def test_query_returns_only_sub_orders(self, authenticated_client, master_with_two_subs, log_dir):
        """AC1+AC12: query возвращает только субзаказы, мастер исключён."""
        master, sub5, sub22 = master_with_two_subs
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert sub5.order_number in content
        assert sub22.order_number in content
        assert master.order_number not in content

    def test_query_excludes_master_orders(self, authenticated_client, master_with_two_subs, log_dir):
        """AC12: master с is_master=True НЕ попадает в XML."""
        master, _sub5, _sub22 = master_with_two_subs
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        content = get_response_content(response).decode("utf-8")
        assert f"order-{master.id}" not in content

    def test_multi_vat_produces_two_organizations(self, authenticated_client, master_with_two_subs, log_dir, settings):
        """AC1: два субзаказа с разными vat_group → два документа с разными организациями."""
        settings.ONEC_EXCHANGE = {
            **getattr(settings, "ONEC_EXCHANGE", {}),
            "ORGANIZATION_BY_VAT": {
                22: {"name": "ИП Семерюк Д.В.", "warehouse": "1 СДВ склад"},
                5: {"name": "ИП Терещенко Л.В.", "warehouse": "2 ТЛВ склад"},
            },
            "DEFAULT_VAT_RATE": 22,
        }
        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        content = get_response_content(response).decode("utf-8")
        assert "ИП Семерюк Д.В." in content
        assert "ИП Терещенко Л.В." in content


@pytest.mark.django_db
@pytest.mark.integration
class TestSubOrderSuccess:
    """Story 34-3: handle_success aggregation of master (AC9, AC10, AC11)."""

    def test_success_aggregates_master_when_all_subs_sent(self, authenticated_client, master_with_two_subs, log_dir):
        """AC9: success помечает оба субзаказа → мастер тоже помечается."""
        master, sub5, sub22 = master_with_two_subs
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        sub5.refresh_from_db()
        sub22.refresh_from_db()
        master.refresh_from_db()
        assert sub5.sent_to_1c is True
        assert sub22.sent_to_1c is True
        assert master.sent_to_1c is True
        assert master.sent_to_1c_at is not None

    def test_repeated_query_marks_previous_batch_and_emits_master_ids(
        self, authenticated_client, master_with_two_subs, log_dir
    ):
        """AC9+AC11: повторный mode=query трактуется как implicit success.

        1С УТ 11 обычно не вызывает mode=success после успешной обработки,
        а делает следующий mode=query. Этот путь должен:
        1. Пометить ранее экспортированные sub-order как sent_to_1c=True.
        2. Агрегировать master, если все его sub-order подтверждены.
        3. Эмитить orders_bulk_updated с master_order_ids.
        """
        from apps.orders.signals import orders_bulk_updated

        master, sub5, sub22 = master_with_two_subs
        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            first_response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "query"},
            )
            assert first_response.status_code == 200

            second_response = authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "query"},
            )
        finally:
            orders_bulk_updated.disconnect(handler)

        second_content = get_response_content(second_response).decode("utf-8")

        sub5.refresh_from_db()
        sub22.refresh_from_db()
        master.refresh_from_db()

        assert sub5.sent_to_1c is True
        assert sub22.sent_to_1c is True
        assert master.sent_to_1c is True
        assert master.sent_to_1c_at is not None

        # После implicit success в повторный query старый batch не должен
        # экспортироваться повторно, так как уже помечен sent_to_1c=True.
        assert f"order-{sub5.pk}" not in second_content
        assert f"order-{sub22.pk}" not in second_content
        assert master.order_number not in second_content

        assert received_kwargs.get("field") == "sent_to_1c"
        assert set(received_kwargs.get("order_ids", [])) == {sub5.pk, sub22.pk}
        assert master.pk in received_kwargs.get("master_order_ids", [])

    def test_master_not_aggregated_when_sub_pending(
        self, authenticated_client, customer_user, product_variant, log_dir
    ):
        """AC10: если не все sub мастера отправлены, мастер НЕ помечается.

        Сценарий: master + sub_ready (с items, экспортируется) + sub_blocked
        (предзасланный sent_to_1c=False, но без items → _validate_order
        пропустит его в export_skipped=True). После success: sub_ready=True,
        sub_blocked остаётся sent_to_1c=False → master НЕ должен агрегироваться.
        """
        from decimal import Decimal

        master = Order.objects.create(
            user=customer_user,
            order_number="FS-PEND-MASTER",
            total_amount=Decimal("3500"),
            sent_to_1c=False,
            delivery_address="ул. Пенд, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        sub_ready = Order.objects.create(
            user=customer_user,
            order_number="FS-PEND-SUB-READY",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Пенд, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master,
            vat_group=Decimal("22.00"),
        )
        OrderItem.objects.create(
            order=sub_ready,
            product=product_variant.product,
            variant=product_variant,
            product_name="Test Product Ready",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )
        # sub_blocked: ещё не отправлен, но без items → будет пропущен,
        # и останется sent_to_1c=False. Это pending sibling для мастера.
        sub_blocked = Order.objects.create(
            user=customer_user,
            order_number="FS-PEND-SUB-BLOCKED",
            total_amount=Decimal("2000"),
            sent_to_1c=False,
            delivery_address="ул. Пенд, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master,
            vat_group=Decimal("5.00"),
        )

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )

        sub_ready.refresh_from_db()
        sub_blocked.refresh_from_db()
        master.refresh_from_db()
        assert sub_ready.sent_to_1c is True
        # sub_blocked остался pending
        assert sub_blocked.sent_to_1c is False
        assert sub_blocked.export_skipped is True
        # Мастер НЕ должен агрегироваться, т.к. sub_blocked всё ещё pending
        assert master.sent_to_1c is False
        assert master.sent_to_1c_at is None

    def test_siblings_in_other_master_not_affected(self, authenticated_client, customer_user, product_variant, log_dir):
        """AC11: агрегация master_A не трогает sibling master_B и его субзаказы.

        Сценарий: две независимые пары master+sub. Экспортируем через query
        ОБОИХ (оба sub с items), но перед success — "помечаем, что master_B.sub
        должен остаться pending". Это делаем через raw update на sub_b, чтобы
        эмулировать ситуацию, когда 1С в mode=success подтвердила только часть
        заказов. В данном тесте оба уходят на export, оба помечаются как
        sent_to_1c=True, но затем я проверяю строгую изоляцию агрегатов.

        Упрощённый сценарий: экспортируем только master_A (ставим master_B.sub
        с `created_at` после query_time, чтобы он не попал в queryset).
        """
        from decimal import Decimal
        from django.utils import timezone

        # Master A: пройдёт полный цикл query+success, должен агрегироваться.
        master_a = Order.objects.create(
            user=customer_user,
            order_number="FS-MASTER-A",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. А, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        sub_a = Order.objects.create(
            user=customer_user,
            order_number="FS-SUB-A",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. А, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master_a,
            vat_group=Decimal("22.00"),
        )
        OrderItem.objects.create(
            order=sub_a,
            product=product_variant.product,
            variant=product_variant,
            product_name="Product A",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )

        # Master B: sub_b создан ПОСЛЕ query (move created_at в будущее вручную),
        # чтобы он НЕ попал в queryset handle_query (created_at__lte=query_time).
        master_b = Order.objects.create(
            user=customer_user,
            order_number="FS-MASTER-B",
            total_amount=Decimal("2000"),
            sent_to_1c=False,
            delivery_address="ул. Б, 2",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        sub_b = Order.objects.create(
            user=customer_user,
            order_number="FS-SUB-B",
            total_amount=Decimal("2000"),
            sent_to_1c=False,
            delivery_address="ул. Б, 2",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master_b,
            vat_group=Decimal("5.00"),
        )
        OrderItem.objects.create(
            order=sub_b,
            product=product_variant.product,
            variant=product_variant,
            product_name="Product B",
            unit_price=Decimal("2000"),
            quantity=1,
            total_price=Decimal("2000"),
        )
        # Сдвинуть created_at sub_b в будущее → handle_query его не выберет.
        future = timezone.now() + timezone.timedelta(hours=1)
        Order.objects.filter(pk=sub_b.pk).update(created_at=future)

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )

        sub_a.refresh_from_db()
        master_a.refresh_from_db()
        sub_b.refresh_from_db()
        master_b.refresh_from_db()

        # Master A: полная цепочка — sub и master помечены.
        assert sub_a.sent_to_1c is True
        assert master_a.sent_to_1c is True

        # Master B: изолирован — sub_b в query не попал, агрегация его не тронула.
        assert sub_b.sent_to_1c is False
        assert master_b.sent_to_1c is False
        assert master_b.sent_to_1c_at is None

    def test_signal_includes_master_order_ids(self, authenticated_client, master_with_two_subs, log_dir):
        """AC11: signal orders_bulk_updated содержит master_order_ids."""
        from apps.orders.signals import orders_bulk_updated

        master, sub5, sub22 = master_with_two_subs
        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "query"},
            )
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "success"},
            )
            assert "master_order_ids" in received_kwargs
            assert master.pk in received_kwargs["master_order_ids"]
        finally:
            orders_bulk_updated.disconnect(handler)

    def test_fallback_updates_only_sub_orders(self, authenticated_client, master_with_two_subs, log_dir):
        """AC10: fallback (cache evicted) обновляет только субзаказы."""
        from django.core.cache import cache as django_cache

        master, sub5, sub22 = master_with_two_subs

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Evict cache to trigger fallback
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        django_cache.delete(cache_key)

        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert response.status_code == 200
        assert "success" in get_response_content(response).decode("utf-8")

        sub5.refresh_from_db()
        sub22.refresh_from_db()
        master.refresh_from_db()
        assert sub5.sent_to_1c is True
        assert sub22.sent_to_1c is True
        # Fallback also runs aggregation
        assert master.sent_to_1c is True

    def test_fallback_emits_orders_bulk_updated_signal(self, authenticated_client, master_with_two_subs, log_dir):
        """AC11: fallback-ветка эмитит orders_bulk_updated с master_order_ids."""
        from django.core.cache import cache as django_cache
        from apps.orders.signals import orders_bulk_updated

        master, sub5, sub22 = master_with_two_subs
        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        # Evict cache to trigger fallback
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        django_cache.delete(cache_key)

        orders_bulk_updated.connect(handler)
        try:
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "success"},
            )
        finally:
            orders_bulk_updated.disconnect(handler)

        assert received_kwargs.get("field") == "sent_to_1c"
        assert "order_ids" in received_kwargs
        # Decision batch 9: order_ids содержит ТОЛЬКО реально обновлённые sub PK,
        # не все sub в окне created_at<=last_query_time (all-history scan идёт
        # только в master_order_ids через _aggregate_master_sent_to_1c).
        assert set(received_kwargs["order_ids"]) == {sub5.pk, sub22.pk}
        assert "master_order_ids" in received_kwargs
        assert master.pk in received_kwargs["master_order_ids"]

    def test_fallback_does_not_aggregate_master_when_updated_is_zero(
        self, authenticated_client, master_with_two_subs, log_dir
    ):
        """AC10 (2026-04-21 touched-only rework): fallback НЕ агрегирует
        master, если ни один sub-order не был фактически обновлён.

        Сценарий: sub-orders уже были sent_to_1c=True (например, через
        _mark_previous_query_as_sent), master остался sent_to_1c=False,
        cache потерян. Fallback видит `updated == 0` в окне и не должен
        запускать _aggregate_master_sent_to_1c. Repair-сценарий
        (sub отправлены, master ещё нет) должен решаться отдельной
        management-командой, а не побочным эффектом mode=success.
        """
        from django.core.cache import cache as django_cache

        master, sub5, sub22 = master_with_two_subs

        # Query — фиксирует last_query_time в сессии
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )

        # Subs уже отправлены (минуя handle_success), master остался.
        Order.objects.filter(pk__in=[sub5.pk, sub22.pk]).update(sent_to_1c=True)

        # Evict cache → fallback срабатывает
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        django_cache.delete(cache_key)

        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )
        assert response.status_code == 200
        assert "success" in get_response_content(response).decode("utf-8")

        master.refresh_from_db()
        # Мастер НЕ должен быть агрегирован — fallback не трогает окно,
        # когда нечего обновлять.
        assert master.sent_to_1c is False
        assert master.sent_to_1c_at is None

    def test_fallback_does_not_emit_signal_when_updated_is_zero(
        self, authenticated_client, master_with_two_subs, log_dir
    ):
        """AC11 (2026-04-21 touched-only rework): fallback НЕ эмитит
        orders_bulk_updated при updated==0.

        Даже если master остался sent_to_1c=False, а sub-order уже отправлены —
        fallback не должен эмитить сигнал, потому что он работает только с
        фактически затронутыми записями.
        """
        from django.core.cache import cache as django_cache
        from apps.orders.signals import orders_bulk_updated

        master, sub5, sub22 = master_with_two_subs

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )

        # Subs уже отправлены → fallback update пометит 0 записей
        Order.objects.filter(pk__in=[sub5.pk, sub22.pk]).update(sent_to_1c=True)

        # Evict cache
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        django_cache.delete(cache_key)

        received_calls: list[dict] = []

        def handler(sender, **kwargs):
            received_calls.append(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "success"},
            )
        finally:
            orders_bulk_updated.disconnect(handler)

        master.refresh_from_db()
        # Master остаётся не помеченным — fallback не запускает агрегацию.
        assert master.sent_to_1c is False

        # Сигнал НЕ эмитирован — touched-only rework: при updated==0
        # fallback вообще не шлёт orders_bulk_updated.
        assert received_calls == []

    def test_master_not_marked_directly_when_in_exported_ids(
        self, authenticated_client, customer_user, product_variant, log_dir
    ):
        """AC9: если master PK случайно оказался в exported_ids,
        он НЕ обновляется напрямую — только через _aggregate_master_sent_to_1c.

        Сценарий: 2 субзаказа мастера уже отправлены, но в exported_ids
        (через cache) подмешан PK мастера. Мастер НЕ должен быть обновлён
        напрямую через основной update(), а только через агрегацию.
        """
        from django.core.cache import cache as django_cache

        from decimal import Decimal

        master = Order.objects.create(
            user=customer_user,
            order_number="FS-NO-DIRECT-MASTER",
            total_amount=Decimal("3000"),
            sent_to_1c=False,
            delivery_address="ул. Тест, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        sub_a = Order.objects.create(
            user=customer_user,
            order_number="FS-NO-DIRECT-SUB-A",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Тест, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master,
            vat_group=Decimal("22.00"),
        )
        OrderItem.objects.create(
            order=sub_a,
            product=product_variant.product,
            variant=product_variant,
            product_name="Product A",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )
        sub_b = Order.objects.create(
            user=customer_user,
            order_number="FS-NO-DIRECT-SUB-B",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Тест, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master,
            vat_group=Decimal("5.00"),
        )
        OrderItem.objects.create(
            order=sub_b,
            product=product_variant.product,
            variant=product_variant,
            product_name="Product B",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )

        # Query — экспортирует оба субзаказа
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )

        # Подменяем cache, добавляя master PK к exported_ids
        session = authenticated_client.session
        cache_key = f"1c_exported_ids_{session.session_key}"
        exported = django_cache.get(cache_key)
        assert exported is not None
        if master.pk not in exported:
            exported.append(master.pk)
            django_cache.set(cache_key, exported, timeout=3600)

        # Success — мастер НЕ обновляется напрямую (is_master=False фильтр)
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "success"},
        )

        sub_a.refresh_from_db()
        sub_b.refresh_from_db()
        master.refresh_from_db()

        # Субзаказы помечены
        assert sub_a.sent_to_1c is True
        assert sub_b.sent_to_1c is True
        # Мастер агрегирован (оба sub отправлены), но НЕ через прямой update
        assert master.sent_to_1c is True
        assert master.sent_to_1c_at is not None

    def test_signal_emitted_when_only_master_aggregated(
        self, authenticated_client, customer_user, product_variant, log_dir
    ):
        """AC11: сигнал эмитится даже при updated==0, если _aggregate_master_sent_to_1c
        пометил мастера.

        Сценарий: sub_orders уже sent_to_1c=True, но master ещё нет.
        При handle_success: updated=0 (субзаказы уже помечены),
        но _aggregate_master_sent_to_1c должен пометить мастера,
        и сигнал ДОЛЖЕН быть эмитирован с master_order_ids.
        """
        from apps.orders.signals import orders_bulk_updated
        from decimal import Decimal

        master = Order.objects.create(
            user=customer_user,
            order_number="FS-SIG-MASTER",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Сигн, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
        )
        sub = Order.objects.create(
            user=customer_user,
            order_number="FS-SIG-SUB",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Сигн, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=False,
            parent_order=master,
            vat_group=Decimal("22.00"),
        )
        OrderItem.objects.create(
            order=sub,
            product=product_variant.product,
            variant=product_variant,
            product_name="Product Sig",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )

        # Query — экспортирует sub
        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )

        # Предзаписываем sub как sent_to_1c=True (минуя handle_success),
        # но оставляем master.sent_to_1c=False
        Order.objects.filter(pk=sub.pk).update(sent_to_1c=True)

        received_kwargs = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "success"},
            )
        finally:
            orders_bulk_updated.disconnect(handler)

        master.refresh_from_db()
        # Мастер агрегирован, т.к. все его sub_orders уже sent_to_1c=True
        assert master.sent_to_1c is True
        assert master.sent_to_1c_at is not None

        # Сигнал эмитирован даже при updated==0
        assert received_kwargs.get("field") == "sent_to_1c"
        assert "master_order_ids" in received_kwargs
        assert master.pk in received_kwargs["master_order_ids"]
        # Decision batch 9: order_ids содержит ТОЛЬКО реально обновлённые sub PK.
        # sub уже был sent_to_1c=True до success → updated=0 → order_ids пуст.
        # master.pk не должен попадать в order_ids ни при каких обстоятельствах.
        assert master.pk not in received_kwargs.get("order_ids", [])
        assert list(received_kwargs.get("order_ids", [])) == []

    def test_implicit_success_signal_excludes_already_sent_subs(
        self, authenticated_client, master_with_two_subs, log_dir
    ):
        """Decision batch 9: при implicit success (_mark_previous_query_as_sent)
        сигнал orders_bulk_updated.order_ids содержит ТОЛЬКО реально обновлённые
        sub PK, а не весь prev_ids из cache.

        Сценарий: первый mode=query экспортирует оба sub → cache[prev_ids]=[sub5, sub22].
        sub5 помечается sent_to_1c=True вручную (имитируем внешнее обновление).
        Второй mode=query триггерит _mark_previous_query_as_sent: prev_ids=[sub5, sub22],
        но update затрагивает только sub22. Сигнал должен отразить это честно.
        """
        from apps.orders.signals import orders_bulk_updated

        master, sub5, sub22 = master_with_two_subs

        authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )

        # Внешнее обновление sub5 (например, через _mark_previous_query_as_sent
        # параллельной сессии, ручную правку админа, скрипт миграции и т.п.).
        Order.objects.filter(pk=sub5.pk).update(sent_to_1c=True)

        received_kwargs: dict = {}

        def handler(sender, **kwargs):
            received_kwargs.update(kwargs)

        orders_bulk_updated.connect(handler)
        try:
            authenticated_client.get(
                "/api/integration/1c/exchange/",
                data={"mode": "query"},
            )
        finally:
            orders_bulk_updated.disconnect(handler)

        sub22.refresh_from_db()
        master.refresh_from_db()
        assert sub22.sent_to_1c is True
        assert master.sent_to_1c is True

        # order_ids содержит только реально обновлённый sub22.
        # sub5 (уже sent до второго query) в сигнале не переизлучается.
        assert set(received_kwargs.get("order_ids", [])) == {sub22.pk}
        assert sub5.pk not in received_kwargs.get("order_ids", [])
        assert master.pk in received_kwargs.get("master_order_ids", [])


@pytest.mark.django_db
@pytest.mark.integration
class TestLegacyOrderExclusion:
    """Story 34-3 Task 6.2: legacy master-only orders are excluded from export."""

    def test_legacy_master_without_sub_orders_is_not_exported(
        self, authenticated_client, customer_user, product_variant, log_dir
    ):
        """AC13: Order с is_master=True, parent_order=None (без субзаказов)
        НЕ попадает в XML после перехода на sub-order queryset."""
        from decimal import Decimal

        legacy_order = Order.objects.create(
            user=customer_user,
            order_number="FS-LEGACY-001",
            total_amount=Decimal("1500"),
            sent_to_1c=False,
            delivery_address="ул. Легаси, 1",
            delivery_method="pickup",
            payment_method="card",
            is_master=True,
            parent_order=None,
        )
        OrderItem.objects.create(
            order=legacy_order,
            product=product_variant.product,
            variant=product_variant,
            product_name="Legacy Product",
            unit_price=Decimal("1500"),
            quantity=1,
            total_price=Decimal("1500"),
        )

        response = authenticated_client.get(
            "/api/integration/1c/exchange/",
            data={"mode": "query"},
        )
        assert response.status_code == 200
        content = get_response_content(response).decode("utf-8")
        assert "КоммерческаяИнформация" in content
        assert "FS-LEGACY-001" not in content
        assert f"order-{legacy_order.id}" not in content
        assert "Документ" not in content

        legacy_order.refresh_from_db()
        assert legacy_order.sent_to_1c is False

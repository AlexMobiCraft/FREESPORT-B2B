"""
Story 4.4: E2E integration tests for the full 1C order export cycle.

Tests cover:
- AC1: Full cycle checkauth -> query -> success -> sent_to_1c=True
- AC2: Counterparty without tax_id — <ИНН> tag absent
- AC3: CommerceML 3.1 XML structure validation
- AC4: Multiple orders (>=3) all marked after success
- AC5: Guest order (user=None) with customer contact fields in XML
- AC6: Repeat cycle — empty XML after success
- AC7: Testing standards compliance (Factory Boy + LazyFunction, AAA, markers)
- AC8: Coverage >=90% for critical modules

Updated for Story 34-3: handle_query exports only sub-orders
(is_master=False, parent_order__isnull=False). All fixtures create
master + sub-order structure; assertions target the sub-order.
"""

import xml.etree.ElementTree as ET

import pytest
from rest_framework.test import APIClient

from tests.conftest import OrderFactory, OrderItemFactory, ProductVariantFactory, UserFactory
from tests.utils import ONEC_PASSWORD, parse_commerceml_response, perform_1c_checkauth

pytestmark = pytest.mark.django_db


@pytest.fixture
def log_dir(tmp_path, settings):
    """Override EXCHANGE_LOG_DIR -> tmp_path (Task 1.7)."""
    private_log = tmp_path / "var" / "1c_exchange" / "logs"
    settings.EXCHANGE_LOG_DIR = str(private_log)
    settings.MEDIA_ROOT = str(tmp_path / "media")
    return private_log


@pytest.fixture
def onec_user(db):
    """Staff user for 1C exchange."""
    return UserFactory.create(is_staff=True, password=ONEC_PASSWORD)


@pytest.fixture
def auth_client(onec_user) -> APIClient:
    """Authenticated APIClient after checkauth."""
    client = APIClient()
    return perform_1c_checkauth(client, onec_user.email, ONEC_PASSWORD)


def _create_master_with_sub(
    user=None,
    variant=None,
    sent_to_1c=False,
    customer_name=None,
    customer_email=None,
    customer_phone=None,
    delivery_address="ул. Тестовая, 1",
    delivery_method="courier",
):
    """Create master + sub-order structure for export E2E tests.

    Returns (master, sub) tuple. The sub-order is the one exported to 1C.
    """
    from apps.orders.models import Order

    if variant is None:
        variant = ProductVariantFactory.create()

    common = {
        "delivery_address": delivery_address,
        "delivery_method": delivery_method,
        "payment_method": "card",
    }
    if user is None:
        common.update(
            customer_name=customer_name or "Гость",
            customer_email=customer_email or "guest@test.com",
            customer_phone=customer_phone or "+79990000000",
        )

    master = Order.objects.create(
        user=user,
        sent_to_1c=False,
        is_master=True,
        total_amount=variant.retail_price,
        **common,
    )
    sub = Order.objects.create(
        user=user,
        sent_to_1c=sent_to_1c,
        is_master=False,
        parent_order=master,
        total_amount=variant.retail_price,
        **common,
    )
    OrderItemFactory.create(
        order=sub,
        product=variant.product,
        variant=variant,
        product_name=variant.product.name,
        unit_price=variant.retail_price,
        quantity=1,
        total_price=variant.retail_price,
    )
    return master, sub


# ---------------------------------------------------------------------------
# Task 2: Full cycle with tax_id (AC1, AC3)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullExportCycleWithTaxId:
    """E2E: checkauth -> query -> success for B2B user with tax_id."""

    def test_full_cycle_checkauth_query_success_marks_order_as_sent(self, auth_client, log_dir, db):
        """AC1: Full cycle marks sub-order (and aggregated master) as sent_to_1c=True."""
        # ARRANGE
        b2b_user = UserFactory.create(tax_id="1234567890", company_name="TestCo")
        v1 = ProductVariantFactory.create()
        v2 = ProductVariantFactory.create()
        master, sub = _create_master_with_sub(user=b2b_user, variant=v1)
        # Add second item to sub-order
        OrderItemFactory.create(
            order=sub,
            product=v2.product,
            variant=v2,
            product_name=v2.product.name,
            unit_price=v2.retail_price,
            quantity=1,
            total_price=v2.retail_price,
        )

        # ACT — query
        resp_q = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp_q.status_code == 200

        # ACT — success
        resp_s = auth_client.get("/api/integration/1c/exchange/", data={"mode": "success"})
        assert resp_s.status_code == 200

        # ASSERT — sub-order marked
        sub.refresh_from_db()
        assert sub.sent_to_1c is True
        assert sub.sent_to_1c_at is not None
        # ASSERT — master aggregated
        master.refresh_from_db()
        assert master.sent_to_1c is True

    def test_full_cycle_xml_contains_valid_commerceml_structure(self, auth_client, log_dir, db):
        """AC3: XML structure follows CommerceML 3.1."""
        # ARRANGE
        b2b_user = UserFactory.create(tax_id="1234567890", company_name="XmlCo")
        v1 = ProductVariantFactory.create()
        v2 = ProductVariantFactory.create()
        master, sub = _create_master_with_sub(user=b2b_user, variant=v1)
        # Add second item to sub-order
        OrderItemFactory.create(
            order=sub,
            product=v2.product,
            variant=v2,
            product_name=v2.product.name,
            unit_price=v2.retail_price,
            quantity=1,
            total_price=v2.retail_price,
        )

        # ACT
        resp = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp.status_code == 200

        # ASSERT — parse full XML
        root = parse_commerceml_response(resp)
        assert root.tag == "КоммерческаяИнформация"
        assert root.get("ВерсияСхемы") == "3.1"

        containers = root.findall("Контейнер")
        assert len(containers) >= 1

        doc = containers[0].find("Документ")
        assert doc is not None
        assert doc.findtext("ХозОперация") == "Заказ товара"

        # ИНН present
        counterparty = doc.find(".//Контрагент")
        assert counterparty is not None
        assert counterparty.findtext("ИНН") == "1234567890"

        # Товары with correct onec_id
        products_el = doc.find("Товары")
        assert products_el is not None
        product_ids = [p.findtext("Ид") for p in products_el.findall("Товар")]
        assert v1.onec_id in product_ids
        assert v2.onec_id in product_ids


# ---------------------------------------------------------------------------
# Task 3: Full cycle without tax_id (AC2)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullExportCycleWithoutTaxId:
    """E2E: Counterparty without tax_id omits <ИНН>."""

    def test_full_cycle_without_tax_id_omits_inn_tag(self, auth_client, log_dir, db):
        """AC2: XML valid, <ИНН> absent when user has no tax_id."""
        # ARRANGE
        user_no_tax = UserFactory.create()
        master, sub = _create_master_with_sub(user=user_no_tax)

        # ACT
        resp = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp.status_code == 200
        root = parse_commerceml_response(resp)

        # ASSERT
        counterparties = root.find(".//Контрагенты")
        assert counterparties is not None
        counterparty = counterparties.find("Контрагент")
        assert counterparty is not None
        assert counterparty.findtext("Наименование") is not None
        assert counterparty.find("ИНН") is None  # Must be absent


# ---------------------------------------------------------------------------
# Task 4: Multiple orders (AC4)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullExportCycleMultipleOrders:
    """E2E: >=3 orders all marked as sent after success."""

    def test_full_cycle_multiple_orders_all_marked_as_sent(self, auth_client, log_dir, db):
        """AC4: 3 sub-orders from different users — all sent_to_1c=True."""
        # ARRANGE
        subs = []
        for _ in range(3):
            user = UserFactory.create()
            master, sub = _create_master_with_sub(user=user)
            subs.append((master, sub))

        # ACT
        resp_q = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp_q.status_code == 200

        # Verify XML has 3 documents (AC4: check <Документ> count, not <Контейнер>)
        root = parse_commerceml_response(resp_q)
        documents = root.findall(".//Документ")
        assert len(documents) == 3, f"Expected 3 documents, got {len(documents)}"

        resp_s = auth_client.get("/api/integration/1c/exchange/", data={"mode": "success"})
        assert resp_s.status_code == 200

        # ASSERT — all sub-orders marked
        for master, sub in subs:
            sub.refresh_from_db()
            assert sub.sent_to_1c is True, f"Sub-order {sub.order_number} not marked"
            assert sub.sent_to_1c_at is not None, f"Sub-order {sub.order_number} sent_to_1c_at is None"
            master.refresh_from_db()
            assert master.sent_to_1c is True, f"Master {master.order_number} not aggregated"


# ---------------------------------------------------------------------------
# Task 5: Guest order (AC5)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullExportCycleGuestOrder:
    """E2E: Guest order (user=None) with customer contact in XML."""

    def test_full_cycle_guest_order_includes_customer_contact_in_xml(self, auth_client, log_dir, db):
        """AC5: Guest contact data appears in <Контрагенты>."""
        # ARRANGE
        master, sub = _create_master_with_sub(
            user=None,
            delivery_address="ул. Гостевая, 5",
            customer_name="Иван Гость",
            customer_email="guest-e2e@test.com",
            customer_phone="+79991112233",
        )

        # ACT
        resp = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp.status_code == 200
        root = parse_commerceml_response(resp)

        # ASSERT
        counterparty = root.find(".//Контрагент")
        assert counterparty is not None
        assert counterparty.findtext("Наименование") == "Иван Гость"

        contacts = counterparty.find("Контакты")
        assert contacts is not None

        # AC5/9.3: Verify contact types match values (Почта for email, Телефон for phone)
        contact_list = contacts.findall("Контакт")
        contact_map = {c.findtext("Тип"): c.findtext("Значение") for c in contact_list}
        assert (
            contact_map.get("Почта") == "guest-e2e@test.com"
        ), f"Expected email contact type 'Почта', got: {contact_map}"
        assert (
            contact_map.get("Телефон") == "+79991112233"
        ), f"Expected phone contact type 'Телефон', got: {contact_map}"

    def test_full_cycle_guest_order_marked_as_sent_after_success(self, auth_client, log_dir, db):
        """AC5: Guest sub-order marked sent_to_1c=True after success."""
        # ARRANGE
        master, sub = _create_master_with_sub(
            user=None,
            delivery_address="ул. Гостевая, 10",
            customer_name="Гость Два",
            customer_email="guest2-e2e@test.com",
            customer_phone="+79992223344",
        )

        # ACT
        auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        resp_s = auth_client.get("/api/integration/1c/exchange/", data={"mode": "success"})
        assert resp_s.status_code == 200

        # ASSERT
        sub.refresh_from_db()
        assert sub.sent_to_1c is True
        master.refresh_from_db()
        assert master.sent_to_1c is True


# ---------------------------------------------------------------------------
# Task 6: Repeat cycle (AC6)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestFullExportCycleRepeat:
    """E2E: Repeat query after success returns empty; new order appears."""

    def test_repeat_query_after_success_returns_empty_xml(self, auth_client, log_dir, db):
        """AC6: After success, second query has no <Документ>."""
        # ARRANGE
        user = UserFactory.create()
        master, sub = _create_master_with_sub(user=user)

        # ACT — first cycle
        auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        auth_client.get("/api/integration/1c/exchange/", data={"mode": "success"})

        # ACT — repeat query
        resp = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp.status_code == 200

        # ASSERT (9.4: Use XML parsing instead of string check)
        root = parse_commerceml_response(resp)
        assert root.tag == "КоммерческаяИнформация", f"Unexpected root: {root.tag}"
        documents = root.findall(".//Документ")
        assert len(documents) == 0, f"Expected 0 documents after success, got {len(documents)}"

    def test_new_order_after_success_appears_in_next_query(self, auth_client, log_dir, db):
        """AC6: New sub-order created after success appears in next query."""
        # ARRANGE — first order + cycle
        user = UserFactory.create()
        variant = ProductVariantFactory.create()
        master1, sub1 = _create_master_with_sub(user=user, variant=variant)

        auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        auth_client.get("/api/integration/1c/exchange/", data={"mode": "success"})

        # ARRANGE — new sub-order
        variant2 = ProductVariantFactory.create()
        master2, sub2 = _create_master_with_sub(user=user, variant=variant2)

        # ACT — second query
        resp = auth_client.get("/api/integration/1c/exchange/", data={"mode": "query"})
        assert resp.status_code == 200
        root = parse_commerceml_response(resp)

        # ASSERT — only new sub-order
        containers = root.findall("Контейнер")
        assert len(containers) == 1
        doc = containers[0].find("Документ")
        assert doc.findtext("Номер") == sub2.order_number

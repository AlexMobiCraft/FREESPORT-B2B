"""
Вид цены в строке заказа и соглашение акции для 1С (spec-order-line-price-type-1c).

При оформлении строка заказа получает снимок: поле варианта, давшее цену
(`price_source_field`), и активный вид цен 1С этого поля (`price_type_onec_id`,
`price_type_name`). Выгрузка пишет его в `<ВидЦены>` и реквизит строки `ВидЦеныИд`,
а соглашение субзаказа — имя вида цен акции, если среди выгружаемых строк есть
акционная, иначе «Стандартное». Строка без снимка выгружается по-старому.
"""

import logging
import xml.etree.ElementTree as ET
from decimal import Decimal

import pytest
from django.conf import settings
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.admin import OrderItemInline
from apps.orders.models import Order, OrderItem
from apps.orders.serializers import OrderItemSerializer
from apps.orders.services import OrderExportService
from apps.products.factories import ProductVariantFactory
from apps.products.models import PriceType, ProductVariant
from tests.conftest import get_unique_suffix

User = get_user_model()

ORDERS_URL = "/api/v1/orders/"
B2B_ORDER = {
    "delivery_address": "г. Москва, ул. Тестовая, д. 1",
    "delivery_method": "pickup",
    "payment_method": "bank_transfer",
}
CREATE_LOGGER = "apps.orders.services.order_create"

PROMO_GUID = "e07feed3-d75a-11f1-9765-e734d5c16693"
PROMO_NAME = "АКЦИЯ НОЯБРЬ-26"
RRP_GUID = "3d1482c4-bd77-11e4-afc8-20cf3073dde3"
RRP_NAME = "РРЦ"
OPT1_GUID = "90d2c899-b3f2-11ea-81c3-00155d3cae02"
OPT1_NAME = "Опт 1 B"
OPT2_GUID = "a91bdb02-b3f2-11ea-81c3-00155d3cae02"
OPT2_NAME = "Опт 2 B"
DEALER_GUID = "190b6b22-bcac-11ea-81c4-00155d3cae02"
DEALER_NAME = "Дилерская цена"
DEFAULT_AGREEMENT = "Стандартное"


@pytest.fixture
def price_types(db):
    """
    Справочник видов цен как на проде, без строки для `federation_price`.

    Неактивные виды заведены раньше активных (меньший `pk`) и раньше по имени:
    выбор без фильтра `is_active` взял бы именно их.
    """
    PriceType.objects.all().delete()
    PriceType.objects.create(
        onec_id="11111111-0000-11f1-0000-000000000001",
        onec_name="АКЦИЯ ОКТЯБРЬ-26",
        product_field="promo_price",
        is_active=False,
    )
    PriceType.objects.create(
        onec_id="11111111-0000-11f1-0000-000000000002",
        onec_name="Опт 2 A архив",
        product_field="opt2_price",
        is_active=False,
    )
    return {
        "promo": PriceType.objects.create(
            onec_id=PROMO_GUID, onec_name=PROMO_NAME, product_field="promo_price", is_active=True
        ),
        "retail": PriceType.objects.create(onec_id=RRP_GUID, onec_name=RRP_NAME, product_field="retail_price"),
        "opt1": PriceType.objects.create(onec_id=OPT1_GUID, onec_name=OPT1_NAME, product_field="opt1_price"),
        "opt2": PriceType.objects.create(onec_id=OPT2_GUID, onec_name=OPT2_NAME, product_field="opt2_price"),
        "dealer": PriceType.objects.create(
            onec_id=DEALER_GUID, onec_name=DEALER_NAME, product_field="dealer_price", user_role="dealer"
        ),
    }


def _user(role):
    return User.objects.create_user(
        email=f"pricetype-{get_unique_suffix()}@example.com",
        password="testpass123",
        role=role,
        is_verified=True,
    )


def _variant(**prices):
    """Вариант с явными ценами: незаданные цены ролей пусты, акции нет."""
    defaults = {
        "retail_price": Decimal("1000.00"),
        "opt1_price": None,
        "opt2_price": None,
        "opt3_price": None,
        "opt4_price": None,
        "trainer_price": None,
        "federation_price": None,
        "special_price": None,
        "dealer_price": None,
        "promo_price": None,
        "vat_rate": Decimal("22"),
        "stock_quantity": 100,
        "reserved_quantity": 0,
    }
    return ProductVariantFactory(**{**defaults, **prices})


def _checkout(user, *lines):
    """Оформляет заказ через API; `lines` — пары (вариант, цена снимка корзины)."""
    cart = Cart.objects.create(user=user)
    for variant, snapshot in lines:
        CartItem.objects.create(cart=cart, variant=variant, quantity=1, price_snapshot=Decimal(snapshot))
    api = APIClient()
    api.force_authenticate(user=user)
    response = api.post(ORDERS_URL, B2B_ORDER, format="json")
    assert response.status_code == 201, response.data
    return Order.objects.get(pk=response.data["id"])


def _item(master, variant):
    return OrderItem.objects.get(order__parent_order=master, variant=variant)


def _snapshot(item):
    return (item.price_source_field, item.price_type_onec_id, item.price_type_name)


def _export(sub):
    orders = Order.objects.filter(pk=sub.pk).prefetch_related("items__variant", "items__product", "user")
    root = ET.fromstring(OrderExportService().generate_xml(orders))
    document = root.find("Контейнер/Документ")
    assert document is not None
    return document


def _line(document, variant):
    for product in document.findall("Товары/Товар"):
        if product.findtext("Ид") == variant.onec_id:
            return product
    raise AssertionError(f"строки {variant.onec_id} нет в XML")


def _line_price_type(product):
    """(<ВидЦены><Ид>, <ВидЦены><Наименование>) или None, если тега нет."""
    tag = product.find("ВидЦены")
    if tag is None:
        return None
    return (tag.findtext("Ид"), tag.findtext("Наименование"))


def _requisites(element):
    return {req.findtext("Наименование"): req.findtext("Значение") for req in element.findall("ЗначениеРеквизита")}


def _line_requisites(product):
    return _requisites(product.find("ЗначенияРеквизитов"))


def _agreement(document):
    """(<Соглашение><Наименование>, реквизит «Соглашение» шапки)."""
    return (
        document.findtext("Соглашение/Наименование"),
        _requisites(document.find("ЗначенияРеквизитов"))["Соглашение"],
    )


@pytest.mark.django_db
class TestPriceTypeSnapshotOnCheckout:
    def test_promo_and_role_lines_in_one_suborder(self, price_types):
        """AC: Опт 2, в одном субзаказе акционный и неакционный товар."""
        user = _user("wholesale_level2")
        promo_variant = _variant(opt2_price=Decimal("900.00"), promo_price=Decimal("700.00"))
        role_variant = _variant(opt2_price=Decimal("800.00"))

        master = _checkout(user, (promo_variant, "700.00"), (role_variant, "800.00"))

        assert _snapshot(_item(master, promo_variant)) == ("promo_price", PROMO_GUID, PROMO_NAME)
        assert _snapshot(_item(master, role_variant)) == ("opt2_price", OPT2_GUID, OPT2_NAME)

        (sub,) = master.sub_orders.all()
        document = _export(sub)
        promo_line = _line(document, promo_variant)
        role_line = _line(document, role_variant)
        assert _line_price_type(promo_line) == (PROMO_GUID, PROMO_NAME)
        assert _line_requisites(promo_line)["ВидЦеныИд"] == PROMO_GUID
        assert _line_price_type(role_line) == (OPT2_GUID, OPT2_NAME)
        assert _line_requisites(role_line)["ВидЦеныИд"] == OPT2_GUID
        assert _agreement(document) == (PROMO_NAME, PROMO_NAME)
        # Номер позиции корзины БУС подставил бы вместо КодСтроки, по которому ищет алгоритм
        assert "НомерПозицииКорзины" not in _line_requisites(promo_line)
        assert promo_line.find("НомерПозицииКорзины") is None

    def test_promo_equal_to_role_price_is_promo(self, price_types):
        """Равенство цены роли и акции — источник акция (spec-checkout-price-recalc)."""
        user = _user("wholesale_level2")
        variant = _variant(opt2_price=Decimal("800.00"), promo_price=Decimal("800.00"))

        master = _checkout(user, (variant, "800.00"))

        assert _snapshot(_item(master, variant)) == ("promo_price", PROMO_GUID, PROMO_NAME)
        assert _agreement(_export(master.sub_orders.get())) == (PROMO_NAME, PROMO_NAME)

    @pytest.mark.parametrize(
        ("role", "prices", "snapshot", "expected"),
        [
            pytest.param(
                "wholesale_level2",
                {"opt2_price": Decimal("900.00")},
                "900.00",
                ("opt2_price", OPT2_GUID, OPT2_NAME),
                id="role-price",
            ),
            pytest.param(
                "wholesale_level2",
                {},
                "1000.00",
                ("retail_price", RRP_GUID, RRP_NAME),
                id="retail-fallback",
            ),
            pytest.param(
                "special_price",
                {"opt1_price": Decimal("950.00")},
                "950.00",
                ("opt1_price", OPT1_GUID, OPT1_NAME),
                id="special-without-own",
            ),
            pytest.param(
                "dealer",
                {"dealer_price": Decimal("520.00"), "opt1_price": Decimal("570.00")},
                "520.00",
                ("dealer_price", DEALER_GUID, DEALER_NAME),
                id="dealer-own",
            ),
            pytest.param(
                "dealer",
                {"opt1_price": Decimal("570.00")},
                "570.00",
                ("opt1_price", OPT1_GUID, OPT1_NAME),
                id="dealer-without-own",
            ),
        ],
    )
    def test_role_chain_field_gives_price_type(self, price_types, role, prices, snapshot, expected):
        user = _user(role)
        variant = _variant(**prices)

        master = _checkout(user, (variant, snapshot))

        item = _item(master, variant)
        assert _snapshot(item) == expected
        document = _export(master.sub_orders.get())
        line = _line(document, variant)
        assert _line_price_type(line) == expected[1:]
        assert _line_requisites(line)["ВидЦеныИд"] == expected[1]
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)

    def test_field_without_active_price_type(self, price_types, caplog):
        """`federation_price`: вида цен нет — ни `<ВидЦены>`, ни `ВидЦеныИд`, warning."""
        user = _user("federation_rep")
        variant = _variant(federation_price=Decimal("850.00"))

        with caplog.at_level(logging.WARNING, logger=CREATE_LOGGER):
            master = _checkout(user, (variant, "850.00"))

        assert _snapshot(_item(master, variant)) == ("federation_price", "", "")
        assert any("federation_price" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
        document = _export(master.sub_orders.get())
        line = _line(document, variant)
        assert _line_price_type(line) is None
        assert "ВидЦеныИд" not in _line_requisites(line)
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)

    def test_promo_without_active_promo_type(self, price_types, caplog):
        """Акционная цена есть, активного вида акции нет: вид не пишется, шапка «Стандартное»."""
        PriceType.objects.filter(pk=price_types["promo"].pk).update(is_active=False)
        user = _user("wholesale_level2")
        variant = _variant(opt2_price=Decimal("900.00"), promo_price=Decimal("700.00"))

        with caplog.at_level(logging.WARNING, logger=CREATE_LOGGER):
            master = _checkout(user, (variant, "700.00"))

        assert _snapshot(_item(master, variant)) == ("promo_price", "", "")
        assert any("promo_price" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)
        document = _export(master.sub_orders.get())
        line = _line(document, variant)
        assert _line_price_type(line) is None
        assert "ВидЦеныИд" not in _line_requisites(line)
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)

    def test_several_active_types_take_first_by_name(self, price_types, caplog):
        PriceType.objects.filter(pk=price_types["opt1"].pk).update(is_active=False)
        PriceType.objects.create(
            onec_id="22222222-0000-11f1-0000-00000000000b", onec_name="Опт 1 Y", product_field="opt1_price"
        )
        PriceType.objects.create(
            onec_id="22222222-0000-11f1-0000-00000000000a", onec_name="Опт 1 X", product_field="opt1_price"
        )
        user = _user("wholesale_level1")
        variant = _variant(opt1_price=Decimal("900.00"))

        with caplog.at_level(logging.WARNING, logger=CREATE_LOGGER):
            master = _checkout(user, (variant, "900.00"))

        assert _snapshot(_item(master, variant)) == ("opt1_price", "22222222-0000-11f1-0000-00000000000a", "Опт 1 X")
        assert any("opt1_price" in r.getMessage() for r in caplog.records if r.levelno == logging.WARNING)

    def test_export_keeps_snapshot_after_price_types_change(self, price_types):
        """
        Между оформлением и выгрузкой сменились текущая акция и активный «Опт 2»:
        строки и соглашение выгружаются по снимку, а не по текущему справочнику.
        """
        user = _user("wholesale_level2")
        promo_variant = _variant(opt2_price=Decimal("900.00"), promo_price=Decimal("700.00"))
        role_variant = _variant(opt2_price=Decimal("800.00"))
        master = _checkout(user, (promo_variant, "700.00"), (role_variant, "800.00"))

        PriceType.objects.filter(pk__in=[price_types["promo"].pk, price_types["opt2"].pk]).update(is_active=False)
        PriceType.objects.create(
            onec_id="33333333-0000-11f1-0000-000000000001",
            onec_name="АКЦИЯ ДЕКАБРЬ-26",
            product_field="promo_price",
            is_active=True,
        )
        PriceType.objects.create(
            onec_id="33333333-0000-11f1-0000-000000000002", onec_name="Опт 2 C", product_field="opt2_price"
        )

        document = _export(master.sub_orders.get())

        promo_line = _line(document, promo_variant)
        role_line = _line(document, role_variant)
        assert _line_price_type(promo_line) == (PROMO_GUID, PROMO_NAME)
        assert _line_requisites(promo_line)["ВидЦеныИд"] == PROMO_GUID
        assert _line_price_type(role_line) == (OPT2_GUID, OPT2_NAME)
        assert _line_requisites(role_line)["ВидЦеныИд"] == OPT2_GUID
        assert _agreement(document) == (PROMO_NAME, PROMO_NAME)

    def test_agreement_is_decided_per_suborder(self, price_types):
        """Два субзаказа (НДС 22 и 5), акционная строка в одном: «АКЦИЯ …» только у него."""
        user = _user("wholesale_level2")
        promo_variant = _variant(opt2_price=Decimal("900.00"), promo_price=Decimal("700.00"), vat_rate=Decimal("22"))
        role_variant = _variant(opt2_price=Decimal("800.00"), vat_rate=Decimal("5"))

        master = _checkout(user, (promo_variant, "700.00"), (role_variant, "800.00"))

        promo_sub = master.sub_orders.get(items__variant=promo_variant)
        role_sub = master.sub_orders.get(items__variant=role_variant)
        assert promo_sub.pk != role_sub.pk
        promo_document = _export(promo_sub)
        role_document = _export(role_sub)
        assert _agreement(promo_document) == (PROMO_NAME, PROMO_NAME)
        assert _agreement(role_document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)
        assert _line_price_type(_line(role_document, role_variant)) == (OPT2_GUID, OPT2_NAME)


def _suborder(user):
    master = Order.objects.create(
        user=user,
        total_amount=Decimal("2000.00"),
        delivery_address="Москва",
        delivery_method="courier",
        payment_method="card",
        is_master=True,
    )
    return Order.objects.create(
        user=user,
        total_amount=Decimal("2000.00"),
        delivery_address="Москва",
        delivery_method="courier",
        payment_method="card",
        is_master=False,
        parent_order=master,
        vat_group=Decimal("22.00"),
    )


def _order_item(order, variant, **snapshot):
    product = variant.product if variant else ProductVariantFactory().product
    return OrderItem.objects.create(
        order=order,
        product=product,
        variant=variant,
        quantity=1,
        unit_price=Decimal("1000.00"),
        **snapshot,
    )


PROMO_SNAPSHOT = {"price_source_field": "promo_price", "price_type_onec_id": PROMO_GUID, "price_type_name": PROMO_NAME}


@pytest.mark.django_db
class TestExportOfStoredSnapshot:
    def test_line_without_snapshot_exports_as_before(self):
        """Строка до снимка вида цены: `<ВидЦены>` по роли, без `ВидЦеныИд`, «Стандартное»."""
        role_map = settings.ONEC_EXCHANGE["PRICE_TYPE_BY_ROLE"]
        id_map = settings.ONEC_EXCHANGE["PRICE_TYPE_ID_BY_NAME"]
        sub = _suborder(_user("wholesale_level2"))
        variant = _variant()
        _order_item(sub, variant)

        document = _export(sub)

        line = _line(document, variant)
        role_name = role_map["wholesale_level2"]
        assert _line_price_type(line) == (id_map[role_name], role_name)
        assert "ВидЦеныИд" not in _line_requisites(line)
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)

    @pytest.mark.parametrize("unexported", ["no-onec-id", "variant-deleted"])
    def test_unexported_promo_line_does_not_set_agreement(self, unexported):
        """Соглашение решают только строки, которые реально уходят в XML."""
        sub = _suborder(_user("wholesale_level2"))
        exported = _variant()
        _order_item(
            sub,
            exported,
            price_source_field="opt2_price",
            price_type_onec_id=OPT2_GUID,
            price_type_name=OPT2_NAME,
        )
        if unexported == "no-onec-id":
            skipped = _variant()
            ProductVariant.objects.filter(pk=skipped.pk).update(onec_id="")
            _order_item(sub, skipped, **PROMO_SNAPSHOT)
        else:
            _order_item(sub, None, **PROMO_SNAPSHOT)

        document = _export(sub)

        assert len(document.findall("Товары/Товар")) == 1
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)

    def test_promo_line_without_name_keeps_default_agreement(self):
        sub = _suborder(_user("wholesale_level2"))
        variant = _variant()
        _order_item(sub, variant, price_source_field="promo_price")

        document = _export(sub)

        assert _line_price_type(_line(document, variant)) is None
        assert _agreement(document) == (DEFAULT_AGREEMENT, DEFAULT_AGREEMENT)


class TestPriceTypeSnapshotVisibility:
    FIELDS = ("price_source_field", "price_type_onec_id", "price_type_name")

    def test_admin_inline_shows_snapshot_read_only(self):
        for field in self.FIELDS:
            assert field in OrderItemInline.fields
            assert field in OrderItemInline.readonly_fields

    @pytest.mark.django_db
    @pytest.mark.parametrize(
        ("snapshot", "expected_price"),
        [
            pytest.param(PROMO_SNAPSHOT, Decimal("1000.00"), id="snapshot-price-locked"),
            pytest.param({}, Decimal("500.00"), id="no-snapshot-price-editable"),
        ],
    )
    def test_admin_inline_price_change(self, snapshot, expected_price):
        """Цена строки со снимком не меняется из админки: вид цены и соглашение остались бы от прежней цены."""
        sub = _suborder(_user("wholesale_level2"))
        item = _order_item(sub, _variant(), **snapshot)

        formset = _post_inline_price(sub, item, "500.00")

        assert formset.is_valid(), formset.errors
        formset.save()
        item.refresh_from_db()
        assert item.unit_price == expected_price
        assert item.total_price == expected_price * item.quantity

    def test_api_does_not_expose_snapshot(self):
        """Имена видов цен клиенту не показываются."""
        assert not set(self.FIELDS) & set(OrderItemSerializer.Meta.fields)


def _post_inline_price(order, item, unit_price):
    """Формсет `OrderItemInline` в том виде, в каком его отправляет админка, с новой ценой строки."""
    admin_user = User.objects.create_superuser(email=f"admin-{get_unique_suffix()}@example.com", password="x")
    request = RequestFactory().post("/")
    request.user = admin_user
    inline = OrderItemInline(Order, django_admin.site)
    formset_class = inline.get_formset(request, order)
    prefix = formset_class.get_default_prefix()
    data = {
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "1",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-id": str(item.pk),
        f"{prefix}-0-order": str(order.pk),
        f"{prefix}-0-product_name": item.product_name,
        f"{prefix}-0-product_sku": item.product_sku,
        f"{prefix}-0-quantity": str(item.quantity),
        f"{prefix}-0-unit_price": unit_price,
    }
    return formset_class(data, instance=order, prefix=prefix)

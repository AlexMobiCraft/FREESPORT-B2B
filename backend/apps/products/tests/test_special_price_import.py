"""
Виды цен «VIP цены» и «СПЕЦЦЕНА» из 1С (spec-roles-vip-special-price).

Импорт проверяется на уровне `VariantImportProcessor` со словарями, которые отдаёт
парсер: в реальных выгрузках этих видов цен пока нет, синтетические XML для тестов
импорта не создаются. Разбор названий — `unit/test_parser_helpers.py`.
"""

from __future__ import annotations

import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any, cast

import pytest
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory
from django.utils import timezone

from apps.products.admin import ProductVariantAdmin
from apps.products.forms import PriceTypeAdminForm
from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services.variant_import import VariantImportProcessor
from apps.users.models import User

pytestmark = [pytest.mark.django_db]

LOGGER = "import_products"

RETAIL_ID = "price-type-retail"
VIP_ID = "0b0b0001-0001-11f0-81c3-00155d3cae02"
SPECIAL_ID = "0b0b0002-0001-11f0-81c3-00155d3cae02"
SPECIAL_NEW_ID = "0b0b0003-0001-11f1-81c3-00155d3cae02"


@pytest.fixture
def processor() -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.STARTED,
    )
    return VariantImportProcessor(session_id=session.pk)


_counter = 0


def make_variant(**prices: Any) -> ProductVariant:
    global _counter
    _counter += 1
    brand, _ = Brand.objects.get_or_create(name="Бренд спеццены", slug="special-brand")
    category, _ = Category.objects.get_or_create(name="Категория спеццены", slug="special-category")
    product = Product.objects.create(
        name=f"Товар спеццены {_counter}",
        slug=f"special-product-{_counter}",
        brand=brand,
        category=category,
        onec_id=f"special-product-{_counter}",
        is_active=True,
    )
    prices.setdefault("retail_price", Decimal("1200.00"))
    return ProductVariant.objects.create(
        product=product,
        sku=f"SPECIAL-{_counter}",
        onec_id=f"special-product-{_counter}#v1",
        stock_quantity=10,
        **prices,
    )


def price_type(onec_id: str, name: str, field: str, *, active: bool = True, user_role: str = "") -> PriceType:
    return PriceType.objects.create(
        onec_id=onec_id, onec_name=name, product_field=field, is_active=active, user_role=user_role
    )


def type_data(onec_id: str, name: str, field: str) -> dict:
    return {"onec_id": onec_id, "onec_name": name, "product_field": field, "is_deleted": False}


def offer(variant: ProductVariant, **prices_by_type_id: str) -> dict:
    return {
        "id": variant.onec_id,
        "prices": [{"price_type_id": pt_id, "value": Decimal(value)} for pt_id, value in prices_by_type_id.items()],
    }


@pytest.fixture
def retail_type() -> PriceType:
    return price_type(RETAIL_ID, "РРЦ", "retail_price")


@pytest.fixture
def special_type(retail_type: PriceType) -> PriceType:
    return price_type(SPECIAL_ID, "СПЕЦЦЕНА", "special_price", user_role="special_price")


@pytest.fixture
def vip_type(retail_type: PriceType) -> PriceType:
    return price_type(VIP_ID, "VIP цены", "vip_price", user_role="vip")


class TestProcessPriceTypes:
    def test_new_types_get_field_and_role(self, processor):
        """Новый вид цен: «СПЕЦЦЕНА» → special_price, «VIP цены» → vip_price, роли проставлены."""
        processor.process_price_types(
            [
                type_data(SPECIAL_ID, "СПЕЦЦЕНА", "special_price"),
                type_data(VIP_ID, "VIP цены", "vip_price"),
            ]
        )

        special = PriceType.objects.get(onec_id=SPECIAL_ID)
        vip = PriceType.objects.get(onec_id=VIP_ID)
        assert (special.product_field, special.user_role, special.is_active) == ("special_price", "special_price", True)
        assert (vip.product_field, vip.user_role, vip.is_active) == ("vip_price", "vip", True)

    def test_existing_type_with_empty_field_and_role_is_filled(self, processor):
        """Запись уже была (поле и роль пусты): обе проставляются."""
        PriceType.objects.create(onec_id=SPECIAL_ID, onec_name="СПЕЦЦЕНА", product_field="", user_role="")

        processor.process_price_types([type_data(SPECIAL_ID, "СПЕЦЦЕНА", "special_price")])

        price = PriceType.objects.get(onec_id=SPECIAL_ID)
        assert (price.product_field, price.user_role) == ("special_price", "special_price")

    def test_role_set_by_manager_is_kept(self, processor):
        price_type(SPECIAL_ID, "СПЕЦЦЕНА", "special_price", user_role="wholesale_level1")

        processor.process_price_types([type_data(SPECIAL_ID, "СПЕЦЦЕНА", "special_price")])

        assert PriceType.objects.get(onec_id=SPECIAL_ID).user_role == "wholesale_level1"

    def test_unrecognized_name_gets_neither_field_nor_role(self, processor):
        """«Особые»: парсер вернул пустое поле, роль не угадывается."""
        processor.process_price_types([type_data("0b0b00ff-0001-11f0-81c3-00155d3cae02", "Особые", "")])

        price = PriceType.objects.get(onec_id="0b0b00ff-0001-11f0-81c3-00155d3cae02")
        assert (price.product_field, price.user_role) == ("", "")

    def test_other_types_do_not_get_these_roles(self, processor):
        processor.process_price_types([type_data(RETAIL_ID, "РРЦ", "retail_price")])

        assert PriceType.objects.get(onec_id=RETAIL_ID).user_role == ""


class TestUpdateVariantPrices:
    def test_vip_and_special_prices_are_written(self, processor, retail_type, special_type, vip_type):
        variant = make_variant()

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", VIP_ID: "900", SPECIAL_ID: "800"}))

        variant.refresh_from_db()
        assert (variant.vip_price, variant.special_price) == (Decimal("900.00"), Decimal("800.00"))
        assert variant.retail_price == Decimal("1200.00")

    def test_special_price_is_removed_when_package_has_no_special_type(self, processor, retail_type, special_type):
        """Спеццена убрана в 1С: пакет цен без вида «СПЕЦЦЕНА» → NULL, дальше «Опт 1»."""
        variant = make_variant(special_price=Decimal("800.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200"}))

        variant.refresh_from_db()
        assert variant.special_price is None

    @pytest.mark.parametrize("value", ["0", "0.00", "-5"])
    def test_non_positive_special_price_is_null(self, processor, retail_type, special_type, value):
        variant = make_variant(special_price=Decimal("800.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_ID: value}))

        variant.refresh_from_db()
        assert variant.special_price is None

    def test_special_price_stays_without_active_special_type(self, processor, retail_type):
        """В справочнике нет активного вида: снимать нечего, цену не трогаем."""
        price_type(SPECIAL_ID, "СПЕЦЦЕНА", "special_price", active=False)
        variant = make_variant(special_price=Decimal("800.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_ID: "700"}))

        variant.refresh_from_db()
        assert variant.special_price == Decimal("800.00")

    def test_vip_price_is_not_removed(self, processor, retail_type, vip_type):
        """Для VIP, как для «Опт 1…4», сброса нет: цена задана на всех товарах."""
        variant = make_variant(vip_price=Decimal("900.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200"}))

        variant.refresh_from_db()
        assert variant.vip_price == Decimal("900.00")

    def test_offer_outside_of_package_is_untouched(self, processor, retail_type, special_type):
        """Предложение не пришло в пакете цен — update_variant_prices для него не вызывался."""
        outside = make_variant(special_price=Decimal("800.00"))
        inside = make_variant(special_price=Decimal("700.00"))

        processor.update_variant_prices(offer(inside, **{RETAIL_ID: "1200"}))

        outside.refresh_from_db()
        assert outside.special_price == Decimal("800.00")

    def test_new_type_price_is_not_wiped_when_two_types_are_active(self, processor, retail_type, special_type):
        """Два активных вида (старый и пересозданный), в предложении цена нового: сброс её не затирает."""
        price_type(SPECIAL_NEW_ID, "СПЕЦЦЕНА", "special_price", user_role="special_price")
        variant = make_variant(special_price=Decimal("800.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_NEW_ID: "850"}))

        variant.refresh_from_db()
        assert variant.special_price == Decimal("850.00")

    def test_both_prices_in_offer_take_the_later_type_and_warn(self, processor, retail_type, special_type, caplog):
        """Старый вид 800, новый (позже по `created_at`) 850: берётся 850, в лог — артикул, GUID и цены."""
        new_type = price_type(SPECIAL_NEW_ID, "СПЕЦЦЕНА", "special_price", user_role="special_price")
        variant = make_variant()

        with caplog.at_level(logging.WARNING, logger=LOGGER):
            processor.update_variant_prices(
                offer(variant, **{RETAIL_ID: "1200", SPECIAL_ID: "800", SPECIAL_NEW_ID: "850"})
            )

        variant.refresh_from_db()
        assert variant.special_price == Decimal("850.00")
        assert new_type.created_at > special_type.created_at
        message = next(r.getMessage() for r in caplog.records if "Две цены special_price" in r.getMessage())
        assert variant.sku in message
        assert f"{SPECIAL_ID}=800" in message
        assert f"{SPECIAL_NEW_ID}=850" in message
        assert processor.stats["warnings"] == 1

    def test_later_type_wins_whatever_the_order_in_the_offer(self, processor, retail_type, special_type):
        price_type(SPECIAL_NEW_ID, "СПЕЦЦЕНА", "special_price", user_role="special_price")
        variant = make_variant()

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_NEW_ID: "850", SPECIAL_ID: "800"}))

        variant.refresh_from_db()
        assert variant.special_price == Decimal("850.00")

    def test_equal_created_at_is_resolved_by_larger_pk(self, processor, retail_type, special_type):
        newer_pk = price_type(SPECIAL_NEW_ID, "СПЕЦЦЕНА", "special_price", user_role="special_price")
        same_moment = timezone.now() - timedelta(days=1)
        PriceType.objects.filter(pk__in=[special_type.pk, newer_pk.pk]).update(created_at=same_moment)
        variant = make_variant()

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_ID: "800", SPECIAL_NEW_ID: "850"}))

        variant.refresh_from_db()
        assert newer_pk.pk > special_type.pk
        assert variant.special_price == Decimal("850.00")

    def test_inactive_special_type_in_offer_is_ignored(self, processor, retail_type, special_type):
        """Цена отключённого вида не применяется; активного вида в предложении нет — спеццена снята."""
        price_type(SPECIAL_NEW_ID, "СПЕЦЦЕНА", "special_price", active=False)
        variant = make_variant(special_price=Decimal("800.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_NEW_ID: "850"}))

        variant.refresh_from_db()
        assert variant.special_price is None

    def test_special_price_does_not_touch_retail_or_opt1(self, processor, retail_type, special_type):
        """Цена вида «СПЕЦЦЕНА» не попадает ни в розницу, ни в «Опт 1»."""
        variant = make_variant(opt1_price=Decimal("1000.00"))

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", SPECIAL_ID: "800"}))

        variant.refresh_from_db()
        assert (variant.retail_price, variant.opt1_price) == (Decimal("1200.00"), Decimal("1000.00"))


class TestEndToEndFromDictionaries:
    """Справочник и цены одним проходом, как в `import_products_from_1c`."""

    def test_types_and_prices_flow(self, processor):
        processor.process_price_types(
            [
                type_data(RETAIL_ID, "РРЦ", "retail_price"),
                type_data(SPECIAL_ID, "СПЕЦЦЕНА", "special_price"),
                type_data(VIP_ID, "VIP цены", "vip_price"),
            ]
        )
        variant = make_variant()

        processor.update_variant_prices(offer(variant, **{RETAIL_ID: "1200", VIP_ID: "900", SPECIAL_ID: "800"}))

        variant.refresh_from_db()
        assert (variant.vip_price, variant.special_price) == (Decimal("900.00"), Decimal("800.00"))
        roles = dict(PriceType.objects.values_list("onec_id", "user_role"))
        assert roles[SPECIAL_ID] == "special_price"
        assert roles[VIP_ID] == "vip"
        assert roles[RETAIL_ID] == ""


class TestAdmin:
    """`special_price` в админке только для чтения (источник истины — 1С), `vip_price` правится."""

    @staticmethod
    def _request():
        request = RequestFactory().get("/admin/products/productvariant/")
        request.user = User(is_staff=True, is_superuser=True)
        return request

    def test_special_price_is_readonly_and_vip_price_is_editable(self):
        model_admin = ProductVariantAdmin(ProductVariant, AdminSite())
        request = self._request()

        assert "special_price" in model_admin.get_readonly_fields(request)
        assert "vip_price" not in model_admin.get_readonly_fields(request)

    def test_both_prices_are_shown_in_pricing_fieldset(self):
        model_admin = ProductVariantAdmin(ProductVariant, AdminSite())

        fields = [name for _, options in model_admin.get_fieldsets(self._request()) for name in options["fields"]]

        assert "vip_price" in fields
        assert "special_price" in fields

    def test_vip_price_is_in_the_admin_form_and_special_price_is_not(self):
        model_admin = ProductVariantAdmin(ProductVariant, AdminSite())

        form_fields = model_admin.get_form(self._request())().fields

        assert "vip_price" in form_fields
        assert "special_price" not in form_fields

    def test_price_type_form_offers_new_roles_and_fields(self):
        form = PriceTypeAdminForm()

        role_values = {value for value, _ in cast(Any, form.fields["user_role"]).choices}
        field_values = {value for value, _ in cast(Any, form.fields["product_field"]).choices}
        assert {"vip", "special_price"} <= role_values
        assert {"vip_price", "special_price"} <= field_values

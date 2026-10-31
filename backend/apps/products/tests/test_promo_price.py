"""
Акционная цена из 1С отдельным видом цен (spec-1c-promo-price-type).

Покрывает матрицу сценариев спеки: правило текущей акции при импорте
priceLists, применение и снятие акционной цены в prices, вывод флага
`is_promo`, цену для ролей и в API, хуки админки, constraint и data-шаг
миграции 0058.

Импорт проверяется на уровне `VariantImportProcessor` со словарями, которые
отдаёт парсер: разбор самих XML (`ПометкаУдаления`, ветка «акция») проверен на
копиях реальных выгрузок в `unit/test_parser_helpers.py`.
"""

from __future__ import annotations

import importlib
import logging
import threading
from decimal import Decimal
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pytest
from django.apps import apps as django_apps
from django.contrib.admin.sites import AdminSite
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.db import IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from apps.products.admin import PriceTypeAdmin, ProductAdmin, ProductVariantAdmin, ProductVariantInline
from apps.products.forms import PriceTypeAdminForm
from apps.products.models import Brand, Category, ImportSession, PriceType, Product, ProductVariant
from apps.products.services import promo
from apps.products.services.variant_import import VariantImportProcessor
from apps.users.models import User

pytestmark = [pytest.mark.django_db]

# GUID версии 1, как у видов цен 1С: в них зашито время создания.
# Ноябрьская акция заведена позже октябрьской (старшие биты времени 0x1f1 > 0x1f0).
OCT_ID = "0a0a0001-0001-11f0-81c3-00155d3cae02"
NOV_ID = "0a0a0002-0001-11f1-81c3-00155d3cae02"
DEC_ID = "0a0a0003-0001-11f2-81c3-00155d3cae02"
RETAIL_ID = "price-type-retail"
OPT2_ID = "price-type-opt2"
LOGGER = "import_products"


# --------------------------------------------------------------------------
# Помощники
# --------------------------------------------------------------------------


@pytest.fixture
def processor() -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.STARTED,
    )
    return VariantImportProcessor(session_id=session.pk)


@pytest.fixture
def regular_price_types() -> None:
    PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
    PriceType.objects.create(onec_id=OPT2_ID, onec_name="Опт 2", product_field="opt2_price")


_counter = 0


def make_variant(**prices: Any) -> ProductVariant:
    global _counter
    _counter += 1
    brand, _ = Brand.objects.get_or_create(name="Бренд акции", slug="promo-brand")
    category, _ = Category.objects.get_or_create(name="Категория акции", slug="promo-category")
    product = Product.objects.create(
        name=f"Товар акции {_counter}",
        slug=f"promo-product-{_counter}",
        brand=brand,
        category=category,
        onec_id=f"promo-product-{_counter}",
        is_active=True,
    )
    prices.setdefault("retail_price", Decimal("1200.00"))
    return ProductVariant.objects.create(
        product=product,
        sku=f"PROMO-{_counter}",
        onec_id=f"promo-product-{_counter}#v1",
        stock_quantity=10,
        **prices,
    )


def promo_type(onec_id: str, name: str, *, active: bool) -> PriceType:
    return PriceType.objects.create(onec_id=onec_id, onec_name=name, product_field="promo_price", is_active=active)


def type_data(onec_id: str, name: str, *, deleted: bool = False, field: str = "promo_price") -> dict:
    return {"onec_id": onec_id, "onec_name": name, "product_field": field, "is_deleted": deleted}


def price_data(variant: ProductVariant, **prices_by_type_id: str) -> dict:
    return {
        "id": variant.onec_id,
        "prices": [{"price_type_id": pt_id, "value": Decimal(value)} for pt_id, value in prices_by_type_id.items()],
    }


def active_promo_ids() -> list[str]:
    return list(PriceType.objects.filter(product_field="promo_price", is_active=True).values_list("onec_id", flat=True))


def make_user(role: str, *, verified: bool = True) -> User:
    global _counter
    _counter += 1
    return User.objects.create_user(
        email=f"promo-{role}-{_counter}@example.com",
        password="testpass123",
        role=role,
        is_verified=verified,
        customer_code=f"{70000 + _counter:05d}",
    )


def seen_values(price_type: PriceType) -> dict[str, str]:
    """Скрытые `initial-*` поля формы админки: то, что менеджер увидел при открытии страницы."""
    return {
        "initial-onec_id": price_type.onec_id,
        "initial-onec_name": price_type.onec_name,
        "initial-product_field": price_type.product_field,
        "initial-user_role": price_type.user_role,
        "initial-is_active": str(price_type.is_active),
    }


class _BrowserForm(HTMLParser):
    """Поля формы так, как их отправит браузер: значения input/select, отмеченные чекбоксы, без disabled."""

    def __init__(self) -> None:
        super().__init__()
        self.data: dict[str, str] = {}
        self._select: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        name = attributes.get("name")
        if tag == "select" and name:
            self._select = name
        elif tag == "option" and self._select and "selected" in attributes:
            self.data[self._select] = attributes.get("value") or ""
        elif tag == "input" and name and "disabled" not in attributes:
            kind = (attributes.get("type") or "text").lower()
            if kind in ("submit", "button", "file", "image"):
                return
            if kind in ("checkbox", "radio"):
                if "checked" in attributes:
                    self.data[name] = attributes.get("value") or "on"
                return
            self.data[name] = attributes.get("value") or ""

    def handle_endtag(self, tag: str) -> None:
        if tag == "select":
            self._select = None


def browser_post_data(page: Any) -> dict[str, str]:
    """Данные POST из HTML страницы изменения — как отправил бы браузер по кнопке «Сохранить»."""
    parser = _BrowserForm()
    parser.feed(page.content.decode())
    return {**parser.data, "_save": "Сохранить"}


def staff_login(client: Any) -> None:
    admin_user = make_user("retail")
    User.objects.filter(pk=admin_user.pk).update(is_staff=True, is_superuser=True)
    client.force_login(admin_user)


# --------------------------------------------------------------------------
# promo.is_newer
# --------------------------------------------------------------------------


class TestIsNewer:
    def test_later_guid_is_newer(self):
        assert promo.is_newer(NOV_ID, OCT_ID) is True
        assert promo.is_newer(OCT_ID, NOV_ID) is False

    def test_same_guid_is_not_newer(self):
        assert promo.is_newer(OCT_ID, OCT_ID) is False

    def test_no_current_promo(self):
        assert promo.is_newer(OCT_ID, None) is True

    @pytest.mark.parametrize("candidate", ["9f0a7c4e-3b1d-4e6f-8a2b-1c3d5e7f9a0b", "не-guid"])
    def test_non_v1_candidate_is_newer(self, candidate):
        assert promo.is_newer(candidate, NOV_ID) is True

    def test_name_rule(self):
        assert promo.is_promo_name("  АКЦИЯ ОКТЯБРЬ-26") is True
        assert promo.is_promo_name("акция") is True
        assert promo.is_promo_name("Распродажа АКЦИЯ") is False
        assert promo.is_promo_name("") is False


# --------------------------------------------------------------------------
# Правило текущей акции при импорте priceLists
# --------------------------------------------------------------------------


class TestPriceTypesImport:
    def test_promo_start(self, processor):
        """Старт акции: новый тип становится текущим, цены прошлой акции обнулены, флаг пересчитан."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("900.00"))
        promo.sync_promo_flags()
        assert Product.objects.get(pk=variant.product_id).is_promo is True

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26"), type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False

        # Цены новой акции записываются заново
        processor.update_variant_prices(price_data(variant, **{NOV_ID: "800.00"}))
        processor_flags = promo.sync_promo_flags()
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert processor_flags == 1
        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_first_promo_ever(self, processor):
        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26")])

        assert active_promo_ids() == [OCT_ID]

    def test_old_type_in_full_export_changes_nothing(self, processor, caplog):
        """Старый тип без пометки в полной выгрузке не активируется, его цены пропускаются молча."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26"), type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")

        with caplog.at_level(logging.WARNING, logger=LOGGER):
            processor.update_variant_prices(price_data(variant, **{OCT_ID: "500.00", NOV_ID: "800.00"}))
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert not [r for r in caplog.records if r.levelno >= logging.WARNING], "Ложный warning на цены прошлой акции"

    def test_known_inactive_promo_is_never_activated(self, processor):
        """Уже известный тип импорт не активирует, даже если текущей акции нет."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26")])

        assert active_promo_ids() == []

    def test_deletion_mark_on_inactive_resets_nothing(self, processor):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", deleted=True)])

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")

    def test_promo_end(self, processor):
        """Конец акции: пометка удаления на текущем типе обнуляет цены и флаги."""
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        other = make_variant(promo_price=Decimal("300.00"))
        promo.sync_promo_flags()

        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26", deleted=True)])

        assert active_promo_ids() == []
        assert not ProductVariant.objects.filter(promo_price__isnull=False).exists()
        assert not Product.objects.filter(pk__in=[variant.product_id, other.product_id], is_promo=True).exists()

    @pytest.mark.parametrize("order", [(NOV_ID, DEC_ID), (DEC_ID, NOV_ID)])
    def test_two_new_in_one_file_newest_wins(self, processor, order):
        names = {NOV_ID: "АКЦИЯ НОЯБРЬ-26", DEC_ID: "АКЦИЯ ДЕКАБРЬ-26"}

        processor.process_price_types([type_data(pt_id, names[pt_id]) for pt_id in order])

        assert active_promo_ids() == [DEC_ID]
        assert PriceType.objects.get(onec_id=NOV_ID).is_active is False

    def test_new_but_older_than_current_stays_inactive(self, processor):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26")])

        assert active_promo_ids() == [NOV_ID]
        assert PriceType.objects.get(onec_id=OCT_ID).product_field == "promo_price"

    def test_new_with_deletion_mark_is_created_inactive(self, processor):
        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26", deleted=True)])

        price_type = PriceType.objects.get(onec_id=NOV_ID)
        assert price_type.product_field == "promo_price"
        assert price_type.is_active is False

    def test_unmapped_type_turning_promo_is_new(self, processor):
        """Тип лёг с пустым полем до деплоя, затем распознан как акция — это новый акционный тип."""
        PriceType.objects.create(onec_id=OCT_ID, onec_name="АКЦИЯ ОКТЯБРЬ-26", product_field="", is_active=True)

        processor.process_price_types([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26")])

        assert active_promo_ids() == [OCT_ID]

    def test_regular_types_stay_active_as_before(self, processor):
        PriceType.objects.create(onec_id=OPT2_ID, onec_name="Опт 2", product_field="opt2_price", is_active=False)

        processor.process_price_types([type_data(OPT2_ID, "Опт 2", field="opt2_price", deleted=True)])

        assert PriceType.objects.get(onec_id=OPT2_ID).is_active is True


# --------------------------------------------------------------------------
# Применение цен из prices.xml
# --------------------------------------------------------------------------


@pytest.mark.usefixtures("regular_price_types")
class TestPromoPricesImport:
    def test_promo_price_is_applied(self, processor):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(opt2_price=Decimal("1000.00"))

        assert processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert variant.retail_price == Decimal("1200.00")

    @pytest.mark.parametrize("value", ["0", "0.00", "-1", "-0.01"])
    def test_non_positive_promo_price_is_null(self, processor, value):
        """R44: и ноль, и отрицательное значение — «акционной цены нет»; прежняя положительная снимается."""
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))

        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00", NOV_ID: value}))

        variant.refresh_from_db()
        assert variant.promo_price is None
        assert variant.retail_price == Decimal("1200.00")

    def test_offer_without_promo_price_leaves_promo(self, processor):
        """Товар снят с акции: у пришедшего предложения нет цены акции; не пришедшие не трогаются."""
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        dropped = make_variant(promo_price=Decimal("800.00"))
        untouched = make_variant(promo_price=Decimal("700.00"))
        promo.sync_promo_flags()

        processor.update_variant_prices(price_data(dropped, **{RETAIL_ID: "1200.00", OPT2_ID: "1000.00"}))
        promo.sync_promo_flags()

        dropped.refresh_from_db()
        untouched.refresh_from_db()
        assert dropped.promo_price is None
        assert dropped.opt2_price == Decimal("1000.00")
        assert untouched.promo_price == Decimal("700.00")
        assert Product.objects.get(pk=dropped.product_id).is_promo is False
        assert Product.objects.get(pk=untouched.product_id).is_promo is True

    def test_without_current_promo_nothing_is_reset(self, processor):
        variant = make_variant()

        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00"}))

        variant.refresh_from_db()
        assert variant.promo_price is None

    def test_unknown_guid_is_skipped_with_single_warning(self, processor, caplog):
        """Цены раньше типа: GUID не в справочнике — пропуск и одна подсказка о полной выгрузке."""
        variant = make_variant()
        other = make_variant()

        with caplog.at_level(logging.WARNING, logger=LOGGER):
            processor.update_variant_prices(price_data(variant, **{NOV_ID: "800.00"}))
            processor.update_variant_prices(price_data(other, **{NOV_ID: "800.00"}))

        variant.refresh_from_db()
        assert variant.promo_price is None
        warnings = [r.getMessage() for r in caplog.records if NOV_ID in r.getMessage()]
        assert len(warnings) == 1
        assert "полную выгрузку" in warnings[0]

    def test_cache_is_reset_by_price_types_step(self, processor):
        """Шаги 1 и 4 идут в одном процессоре: тип из priceLists виден ценам того же прогона."""
        variant = make_variant()
        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00"}))

        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])
        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")


@pytest.mark.usefixtures("regular_price_types")
class TestPromoStateConsistency:
    """R2: кэш видов цен на прогон не должен переживать отключение или смену акции."""

    def test_disabled_promo_price_is_not_restored_from_cache(self, processor):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        warm = make_variant()
        target = make_variant()
        processor.update_variant_prices(price_data(warm, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        promo.deactivate_promo(current)
        processor.update_variant_prices(price_data(target, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))
        promo.sync_promo_flags()

        target.refresh_from_db()
        assert target.promo_price is None
        assert Product.objects.get(pk=target.product_id).is_promo is False

    def test_prices_follow_live_current_promo_after_switch(self, processor):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        warm = make_variant()
        target = make_variant()
        processor.update_variant_prices(price_data(warm, **{RETAIL_ID: "1200.00", OCT_ID: "800.00"}))

        promo.activate(nov)
        processor.update_variant_prices(
            price_data(target, **{RETAIL_ID: "1200.00", OCT_ID: "800.00", NOV_ID: "700.00"})
        )

        target.refresh_from_db()
        assert target.promo_price == Decimal("700.00")

    def test_cached_variant_with_stale_promo_price_is_rewritten(self, processor):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00", OCT_ID: "800.00"}))

        promo.activate(nov)
        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")


class TestPromoActivationAtomicity:
    """R3: регистрация нового акционного типа и выбор текущей акции — одна операция."""

    def test_failed_activation_is_retried_by_next_import(self, processor, monkeypatch):
        def broken_activate(price_type: PriceType) -> bool:
            raise RuntimeError("сбой активации")

        monkeypatch.setattr(promo, "activate", broken_activate)
        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])
        monkeypatch.undo()

        assert active_promo_ids() == []
        assert not PriceType.objects.filter(onec_id=NOV_ID, product_field="promo_price").exists()

        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])

        assert active_promo_ids() == [NOV_ID]


def advisory_locks_held() -> int:
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_locks WHERE locktype = 'advisory' AND pid = pg_backend_pid() AND granted"
        )
        return int(cursor.fetchone()[0])


class TestPromoStateLock:
    """R7: смена текущей акции сериализована общей блокировкой, в том числе без активной строки."""

    def test_switch_without_active_promo_takes_lock(self):
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)

        with transaction.atomic():
            assert advisory_locks_held() == 0
            promo.activate(nov)
            assert advisory_locks_held() == 1

    def test_delete_takes_lock(self):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)

        with transaction.atomic():
            promo.delete_price_types([current])
            assert advisory_locks_held() == 1

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_switch_waits_for_lock_holder(self):
        """Второе переключение ждёт первое и не падает на уникальном индексе."""
        import threading

        from django.db import connection

        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        outcome: dict[str, Any] = {}

        def switch_to_nov() -> None:
            try:
                promo.activate(PriceType.objects.get(onec_id=NOV_ID))
                outcome["ok"] = True
            except Exception as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                outcome["error"] = exc
            finally:
                connection.close()

        worker = threading.Thread(target=switch_to_nov)
        with transaction.atomic():
            promo.activate(PriceType.objects.get(onec_id=OCT_ID))
            worker.start()
            worker.join(timeout=1.0)
            assert worker.is_alive(), "второе переключение не дождалось блокировки"

        worker.join(timeout=10.0)
        assert not worker.is_alive()
        assert outcome == {"ok": True}
        assert active_promo_ids() == [NOV_ID]


class TestSyncPromoFlags:
    def test_inactive_variant_does_not_count(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        ProductVariant.objects.filter(pk=variant.pk).update(is_active=False)

        promo.sync_promo_flags()

        assert Product.objects.get(pk=variant.product_id).is_promo is False

    def test_variant_activity_change_recomputes_flag_in_both_directions(self):
        """R6: отключение последнего акционного варианта снимает флаг, включение возвращает."""
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        product_id = variant.product_id
        assert Product.objects.get(pk=product_id).is_promo is True

        variant.is_active = False
        variant.save()
        assert Product.objects.get(pk=product_id).is_promo is False

        variant.is_active = True
        variant.save(update_fields=["is_active"])
        assert Product.objects.get(pk=product_id).is_promo is True

    def test_other_active_promo_variant_keeps_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        ProductVariant.objects.create(
            product=variant.product,
            sku="PROMO-SECOND-ACTIVE",
            onec_id=f"{variant.product.onec_id}#second",
            retail_price=Decimal("1500.00"),
            promo_price=Decimal("700.00"),
        )
        promo.sync_promo_flags()

        variant.is_active = False
        variant.save()

        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_deleting_last_promo_variant_clears_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()

        variant.delete()

        assert Product.objects.get(pk=variant.product_id).is_promo is False

    def test_activity_change_without_promo_price_runs_no_recompute(self, monkeypatch):
        """Импорт переключает активность тысяч вариантов без акции: пересчёта по ним быть не должно."""
        variant = make_variant()
        calls: list[Any] = []
        monkeypatch.setattr(promo, "sync_promo_flags", lambda *args, **kwargs: calls.append((args, kwargs)))

        variant.is_active = False
        variant.save()

        assert calls == []

    def test_manual_flag_is_removed_and_only_diverging_rows_change(self):
        """Ручные отметки «Акция» без акционной цены снимает первый же пересчёт."""
        manual = make_variant()
        Product.objects.filter(pk=manual.product_id).update(is_promo=True)
        make_variant(promo_price=Decimal("800.00"))

        assert promo.sync_promo_flags() == 2
        assert promo.sync_promo_flags() == 0
        assert Product.objects.get(pk=manual.product_id).is_promo is False


# --------------------------------------------------------------------------
# Цена для ролей и API
# --------------------------------------------------------------------------


class TestPriceForUser:
    """Клиент платит меньшую из цен: своей или акционной (решение владельца 2026-10-26)."""

    @pytest.mark.parametrize(
        ("role", "field", "regular", "expected"),
        [
            ("wholesale_level2", "opt2_price", "1000.00", "800.00"),  # акция ниже цены — платит акцию
            ("wholesale_level1", "opt1_price", "700.00", "700.00"),  # акция выше цены — своя цена
            ("wholesale_level3", "opt3_price", "800.00", "800.00"),  # акция равна цене
            ("special_price", "special_price", "850.00", "800.00"),
            ("special_price", "special_price", "700.00", "700.00"),
            ("vip", "vip_price", "900.00", "800.00"),
            ("vip", "vip_price", "750.00", "750.00"),
        ],
    )
    def test_client_pays_the_lower_of_role_and_promo_price(self, role, field, regular, expected):
        variant = make_variant(promo_price=Decimal("800.00"), **{field: Decimal(regular)})
        user = make_user(role)

        assert variant.get_price_for_user(user) == Decimal(expected)
        assert variant.get_regular_price_for_user(user) == Decimal(regular)

    @pytest.mark.parametrize("role", ["retail", "trainer", "federation_rep"])
    def test_promo_for_every_role(self, role):
        variant = make_variant(
            promo_price=Decimal("800.00"), trainer_price=Decimal("900.00"), federation_price=Decimal("950.00")
        )

        assert variant.get_price_for_user(make_user(role)) == Decimal("800.00")
        assert variant.get_price_for_user(None) == Decimal("800.00")

    def test_promo_price_above_retail_keeps_retail(self):
        """Акция выше розницы клиенту не выгодна: гость платит розницу."""
        variant = make_variant(retail_price=Decimal("700.00"), promo_price=Decimal("800.00"))

        assert variant.get_price_for_user(None) == Decimal("700.00")

    def test_promo_price_is_used_when_role_price_is_not_positive(self):
        """Цены роли нет (розница 0): платит акцию, а не 0."""
        variant = make_variant(retail_price=Decimal("0"), promo_price=Decimal("500.00"))

        assert variant.get_price_for_user(None) == Decimal("500.00")
        assert variant.get_price_for_user(make_user("wholesale_level1")) == Decimal("500.00")

    def test_unverified_client_pays_min_of_retail_and_promo(self):
        """Неверифицированный B2B понижен до розницы, и `min` считается от неё."""
        variant = make_variant(
            retail_price=Decimal("1200.00"), special_price=Decimal("500.00"), promo_price=Decimal("800.00")
        )

        assert variant.get_price_for_user(make_user("special_price", verified=False)) == Decimal("800.00")

    def test_no_promo_keeps_role_price(self):
        variant = make_variant(opt2_price=Decimal("1000.00"))

        assert variant.get_price_for_user(make_user("wholesale_level2")) == Decimal("1000.00")


class TestApi:
    def test_list_for_guest(self):
        variant = make_variant(retail_price=Decimal("1200.00"), promo_price=Decimal("800.00"))

        response = APIClient().get(reverse("products:product-list"))

        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        assert item["promo_price"] == "800.00"
        assert item["regular_price"] == "1200.00"
        assert item["current_price"] == "800.00"

    def test_list_without_promo(self):
        variant = make_variant(retail_price=Decimal("1200.00"))

        response = APIClient().get(reverse("products:product-list"))

        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        assert item["promo_price"] is None
        assert item["current_price"] == item["regular_price"] == "1200.00"

    def test_list_prefers_promo_variant(self):
        """Список отдаёт цены первого варианта, а вариант с акцией идёт первым даже при большей рознице."""
        variant = make_variant(retail_price=Decimal("500.00"))
        ProductVariant.objects.create(
            product=variant.product,
            sku="PROMO-SECOND",
            onec_id=f"{variant.product.onec_id}#v2",
            retail_price=Decimal("2000.00"),
            promo_price=Decimal("1500.00"),
        )

        response = APIClient().get(reverse("products:product-list"))

        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        assert item["promo_price"] == "1500.00"
        assert item["regular_price"] == "2000.00"

    def test_list_shows_variant_with_only_promo_price(self):
        """R4: вариант, у которого есть только акционная цена, доходит до списка."""
        from apps.products.serializers import ProductListSerializer

        variant = make_variant(retail_price=Decimal("0"), promo_price=Decimal("800.00"))

        response = APIClient().get(reverse("products:product-list"))
        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        without_prefetch = ProductListSerializer(Product.objects.get(pk=variant.product_id)).data

        for data in (item, without_prefetch):
            assert data["promo_price"] == "800.00"
            assert data["current_price"] == "800.00"

    @pytest.mark.parametrize("role, field", [("vip", "vip_price"), ("special_price", "special_price")])
    def test_list_shows_variant_with_only_role_price(self, role, field):
        """Вариант, у которого положительна только цена VIP или спеццена, доходит до списка."""
        from apps.products.serializers import ProductListSerializer

        variant = make_variant(retail_price=Decimal("0"), **{field: Decimal("900.00")})
        user = make_user(role)
        client = APIClient()
        client.force_authenticate(user=user)

        response = client.get(reverse("products:product-list"))
        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        request = RequestFactory().get("/")
        request.user = user
        without_prefetch = ProductListSerializer(
            Product.objects.get(pk=variant.product_id), context={"request": request}
        ).data

        for data in (item, without_prefetch):
            assert data["current_price"] == "900.00"
            assert data["regular_price"] == "900.00"

    def test_list_ignores_inactive_promo_variant(self):
        """R5: отключённый акционный вариант не вытесняет доступный обычный."""
        from apps.products.serializers import ProductListSerializer

        variant = make_variant(retail_price=Decimal("1200.00"))
        ProductVariant.objects.create(
            product=variant.product,
            sku="PROMO-INACTIVE",
            onec_id=f"{variant.product.onec_id}#inactive",
            retail_price=Decimal("1500.00"),
            promo_price=Decimal("700.00"),
            is_active=False,
        )

        response = APIClient().get(reverse("products:product-list"))
        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        without_prefetch = ProductListSerializer(Product.objects.get(pk=variant.product_id)).data

        for data in (item, without_prefetch):
            assert data["promo_price"] is None
            assert data["current_price"] == "1200.00"

    def test_detail_variants_for_wholesale(self):
        variant = make_variant(opt2_price=Decimal("1000.00"), promo_price=Decimal("800.00"))
        client = APIClient()
        client.force_authenticate(user=make_user("wholesale_level2"))

        response = client.get(reverse("products:product-detail", kwargs={"slug": variant.product.slug}))

        data = response.json()
        row = data["variants"][0]
        assert row["promo_price"] == "800.00"
        assert row["regular_price"] == "1000.00"
        assert row["current_price"] == "800.00"
        assert data["current_price"] == "800.00"


# --------------------------------------------------------------------------
# Constraint и миграция
# --------------------------------------------------------------------------


class TestConstraint:
    def test_second_active_promo_is_rejected(self):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)

        with pytest.raises(IntegrityError), transaction.atomic():
            promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)

    def test_inactive_promos_and_regular_types_are_free(self):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        promo_type(DEC_ID, "АКЦИЯ ДЕКАБРЬ-26", active=True)
        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")

        assert PriceType.objects.filter(onec_id__in=[OCT_ID, NOV_ID, DEC_ID, RETAIL_ID]).count() == 4


class TestMigration0058:
    migration = importlib.import_module("apps.products.migrations.0058_promo_price")

    def test_maps_promo_names_and_keeps_newest_active(self):
        PriceType.objects.create(onec_id=OCT_ID, onec_name="АКЦИЯ ОКТЯБРЬ-26", product_field="", is_active=True)
        PriceType.objects.create(onec_id=NOV_ID, onec_name=" акция ноябрь-26", product_field="", is_active=True)
        PriceType.objects.create(onec_id=DEC_ID, onec_name="АКЦИЯ ДЕКАБРЬ-26", product_field="", is_active=False)
        PriceType.objects.create(onec_id=OPT2_ID, onec_name="Опт 2", product_field="opt2_price", is_active=True)

        self.migration.map_promo_price_types(django_apps, None)

        assert set(PriceType.objects.filter(product_field="promo_price").values_list("onec_id", flat=True)) == {
            OCT_ID,
            NOV_ID,
            DEC_ID,
        }
        assert active_promo_ids() == [NOV_ID]
        assert PriceType.objects.get(onec_id=OPT2_ID).product_field == "opt2_price"

    def test_without_promo_types_changes_nothing(self):
        PriceType.objects.create(onec_id=OPT2_ID, onec_name="Опт 2", product_field="opt2_price", is_active=True)

        self.migration.map_promo_price_types(django_apps, None)

        assert PriceType.objects.get(onec_id=OPT2_ID).product_field == "opt2_price"

    def test_reverse_unmaps(self):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)

        self.migration.unmap_promo_price_types(django_apps, None)

        assert PriceType.objects.get(onec_id=OCT_ID).product_field == ""

    def test_resets_manual_promo_flags_in_catalog_without_promo_types(self):
        """R50: акционных цен ещё нет, а ручное управление флагом убрано — прежние отметки не остаются."""
        manual = make_variant()
        Product.objects.filter(pk=manual.product_id).update(is_promo=True)

        self.migration.map_promo_price_types(django_apps, None)

        assert Product.objects.get(pk=manual.product_id).is_promo is False

    def test_resets_manual_promo_flags_when_promo_types_exist(self):
        PriceType.objects.create(onec_id=OCT_ID, onec_name="АКЦИЯ ОКТЯБРЬ-26", product_field="", is_active=True)
        manual = make_variant()
        Product.objects.filter(pk=manual.product_id).update(is_promo=True)

        self.migration.map_promo_price_types(django_apps, None)

        assert Product.objects.get(pk=manual.product_id).is_promo is False

    def test_keeps_flag_backed_by_active_promo_price(self):
        backed = make_variant(promo_price=Decimal("800.00"))
        Product.objects.filter(pk=backed.product_id).update(is_promo=True)

        self.migration.map_promo_price_types(django_apps, None)

        assert Product.objects.get(pk=backed.product_id).is_promo is True


BEFORE_PROMO_MIGRATION = ("products", "0057_catalog_category_order")
PROMO_MIGRATION = ("products", "0058_promo_price")


def migrate_schema_to(*targets: tuple[str, str]) -> Any:
    """Переводит схему тестовой БД к узлам миграций; отдаёт исторические модели этого состояния."""
    from django.db import connection

    MigrationExecutor(connection).migrate(list(targets))
    return MigrationExecutor(connection).loader.project_state(list(targets)).apps


@pytest.fixture
def catalog_before_promo_migration(transactional_db: Any) -> Any:
    """
    Схема на миграции 0057 — до `promo_price`: каталог так, как он лежит на проде перед деплоем.

    Выход возвращает схему к последним миграциям, даже если тест упал: иначе соседние тесты
    воркера пойдут по БД без колонки `promo_price` и без частичного ограничения.
    """
    from django.db import connection

    historical_apps = migrate_schema_to(BEFORE_PROMO_MIGRATION)
    try:
        yield historical_apps
    finally:
        MigrationExecutor(connection).migrate(list(MigrationExecutor(connection).loader.graph.leaf_nodes()))


@pytest.mark.django_db(transaction=True)
class TestMigration0058AppliedToExistingCatalog:
    """
    R68: переход 0057 → 0058 на уже заполненной БД, настоящим исполнителем миграций.

    Тесты выше вызывают data-функции напрямую и не заметят, что `RunPython` пропал из
    `Migration.operations`: на пустой CI-БД он ничего не меняет, а на проде остались бы
    прежние маппинги и ручные отметки «Акция». Данные «до» создаются историческими моделями.
    """

    @staticmethod
    def seed_price_types(historical_apps: Any, rows: list[tuple[str, str, str, bool]]) -> None:
        historical_price_type = historical_apps.get_model("products", "PriceType")
        for onec_id, name, field, active in rows:
            historical_price_type.objects.create(onec_id=onec_id, onec_name=name, product_field=field, is_active=active)

    def test_promo_types_are_mapped_and_only_newest_active_stays(self, catalog_before_promo_migration):
        self.seed_price_types(
            catalog_before_promo_migration,
            [
                (OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", "", True),
                (NOV_ID, " акция ноябрь-26", "", True),
                (DEC_ID, "АКЦИЯ ДЕКАБРЬ-26", "", False),
                ("price-type-not-promo", "Акционный прайс", "", True),  # «акционный» не начинается с «акция»
                (OPT2_ID, "Опт 2", "opt2_price", True),
            ],
        )

        migrate_schema_to(PROMO_MIGRATION)

        fields = dict(PriceType.objects.values_list("onec_id", "product_field"))
        assert [fields[pk] for pk in (OCT_ID, NOV_ID, DEC_ID)] == ["promo_price"] * 3
        assert fields["price-type-not-promo"] == ""
        assert fields[OPT2_ID] == "opt2_price"
        assert active_promo_ids() == [NOV_ID]
        # Неакционные типы миграция не гасит
        assert PriceType.objects.get(onec_id=OPT2_ID).is_active is True
        assert PriceType.objects.get(onec_id="price-type-not-promo").is_active is True

    def test_without_active_promo_type_none_becomes_current(self, catalog_before_promo_migration):
        self.seed_price_types(
            catalog_before_promo_migration,
            [(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", "", False), (NOV_ID, "АКЦИЯ НОЯБРЬ-26", "", False)],
        )

        migrate_schema_to(PROMO_MIGRATION)

        assert set(PriceType.objects.filter(product_field="promo_price").values_list("onec_id", flat=True)) == {
            OCT_ID,
            NOV_ID,
        }
        assert active_promo_ids() == []

    def test_manual_promo_flags_are_reset_and_catalog_survives(self, catalog_before_promo_migration):
        historical = catalog_before_promo_migration
        brand = historical.get_model("products", "Brand").objects.create(name="Бренд акции", slug="promo-brand")
        category = historical.get_model("products", "Category").objects.create(
            name="Категория акции", slug="promo-category"
        )
        products = {}
        for key, is_promo in (("flagged", True), ("flagged-bare", True), ("plain", False)):
            products[key] = historical.get_model("products", "Product").objects.create(
                name=f"Товар {key}",
                slug=f"promo-migration-{key}",
                onec_id=f"promo-migration-{key}",
                brand=brand,
                category=category,
                is_active=True,
                is_promo=is_promo,
            )
        for key in ("flagged", "plain"):  # у «flagged-bare» вариантов нет вовсе
            historical.get_model("products", "ProductVariant").objects.create(
                product=products[key],
                sku=f"PROMO-MIGRATION-{key}",
                onec_id=f"promo-migration-{key}#v1",
                retail_price=Decimal("1200.00"),
                stock_quantity=10,
            )

        migrate_schema_to(PROMO_MIGRATION)

        flags = dict(Product.objects.filter(pk__in=[p.pk for p in products.values()]).values_list("slug", "is_promo"))
        assert flags == {
            "promo-migration-flagged": False,
            "promo-migration-flagged-bare": False,
            "promo-migration-plain": False,
        }
        variants = ProductVariant.objects.filter(sku__startswith="PROMO-MIGRATION-")
        assert variants.count() == 2
        assert set(variants.values_list("retail_price", "promo_price")) == {(Decimal("1200.00"), None)}

    def test_single_active_promo_constraint_is_in_place(self, catalog_before_promo_migration):
        from django.db import connection

        self.seed_price_types(catalog_before_promo_migration, [(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", "", True)])

        migrate_schema_to(PROMO_MIGRATION)

        with connection.cursor() as cursor:
            constraints = connection.introspection.get_constraints(cursor, PriceType._meta.db_table)
        assert constraints["price_types_single_active_promo"]["unique"] is True
        with pytest.raises(IntegrityError), transaction.atomic():
            promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        # Ограничение частичное: неактивные акции и обычные типы им не заняты
        promo_type(DEC_ID, "АКЦИЯ ДЕКАБРЬ-26", active=False)
        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
        assert active_promo_ids() == [OCT_ID]


# --------------------------------------------------------------------------
# Админка
# --------------------------------------------------------------------------


def admin_request(data: dict[str, str] | None = None) -> Any:
    request: Any = RequestFactory().post("/admin/products/pricetype/", data or {})
    request.user = User(is_staff=True, is_superuser=True)
    request.session = {}
    request._messages = FallbackStorage(request)
    return request


def messages_of(request: Any) -> list[str]:
    return [str(message) for message in request._messages]


class TestPriceTypeAdmin:
    model_admin = PriceTypeAdmin(PriceType, AdminSite())

    def test_unchecking_active_on_current_promo_resets(self):
        """AC: менеджер снял «Активный» у текущей акции — акционных цен и флагов нет."""
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        request = admin_request()

        current.is_active = False
        self.model_admin.save_model(request, current, form=None, change=True)

        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False
        assert messages_of(request) == [PriceTypeAdmin.PROMO_RESET_MESSAGE]

    def test_delete_current_promo_resets(self):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        request = admin_request()

        self.model_admin.delete_model(request, current)

        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False
        assert messages_of(request) == [PriceTypeAdmin.PROMO_RESET_MESSAGE]

    def test_delete_queryset_with_current_promo_resets(self):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        request = admin_request()

        self.model_admin.delete_queryset(request, PriceType.objects.filter(product_field="promo_price"))

        assert not PriceType.objects.filter(product_field="promo_price").exists()
        variant.refresh_from_db()
        assert variant.promo_price is None

    def test_delete_inactive_promo_keeps_prices(self):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        old = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        request = admin_request()

        self.model_admin.delete_model(request, old)

        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert messages_of(request) == []

    def test_enabling_second_promo_switches_current(self):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        request = admin_request()

        nov.is_active = True
        self.model_admin.save_model(request, nov, form=None, change=True)

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert messages_of(request) == [PriceTypeAdmin.PROMO_RESET_MESSAGE]

    def test_form_accepts_enabling_second_promo(self):
        """R1: стандартная проверка ограничений модели не должна отклонять форму до save_model."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)

        form = PriceTypeAdminForm(
            data={
                "onec_id": NOV_ID,
                "onec_name": "АКЦИЯ НОЯБРЬ-26",
                "product_field": "promo_price",
                "user_role": "",
                "is_active": "on",
            },
            instance=nov,
        )

        assert form.is_valid(), form.errors

    def test_real_admin_post_switches_current_promo(self, client):
        """R1: настоящий POST в форму админки включает вторую акцию и выключает прежнюю."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        nov = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        admin_user = make_user("retail")
        User.objects.filter(pk=admin_user.pk).update(is_staff=True, is_superuser=True)
        client.force_login(admin_user)

        response = client.post(
            reverse("admin:products_pricetype_change", args=[nov.pk]),
            {
                "onec_id": NOV_ID,
                "onec_name": "АКЦИЯ НОЯБРЬ-26",
                "product_field": "promo_price",
                "user_role": "",
                "is_active": "on",
            },
        )

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price is None

    def test_switching_field_to_promo_via_admin(self):
        """Смена product_field на «Акционная цена» — тоже через правило одной акции."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        other = PriceType.objects.create(onec_id=NOV_ID, onec_name="Ноябрь", product_field="", is_active=True)
        request = admin_request()

        other.product_field = "promo_price"
        self.model_admin.save_model(request, other, form=None, change=True)

        assert active_promo_ids() == [NOV_ID]

    def test_saving_regular_type_resets_nothing(self):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        opt2 = PriceType.objects.create(onec_id=OPT2_ID, onec_name="Опт 2", product_field="opt2_price")
        variant = make_variant(promo_price=Decimal("800.00"))
        request = admin_request()

        opt2.user_role = "wholesale_level2"
        self.model_admin.save_model(request, opt2, form=None, change=True)

        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert messages_of(request) == []


class TestProductAdmins:
    def test_promo_fields_are_readonly(self):
        request = admin_request()
        product_admin = ProductAdmin(Product, AdminSite())
        variant_admin = ProductVariantAdmin(ProductVariant, AdminSite())

        assert "is_promo" in product_admin.get_readonly_fields(request)
        assert "promo_price" in variant_admin.get_readonly_fields(request)
        inline = next(i for i in product_admin.inlines if i.model is ProductVariant)
        assert "promo_price" in inline.readonly_fields

    def test_manual_promo_actions_removed(self):
        assert "mark_as_promo" not in ProductAdmin.actions
        assert "unmark_as_promo" not in ProductAdmin.actions
        assert not hasattr(ProductAdmin, "mark_as_promo")


# --------------------------------------------------------------------------
# Команда импорта на копии реального priceLists.xml
# --------------------------------------------------------------------------

# Реальные GUID видов цен из закоммиченного среза tests/fixtures/1c-data
TRAINER_REAL_ID = "b86fb8c5-ea2d-11eb-81f3-00155d3cae02"  # «Тренерская», создан в 2021
OPT3_REAL_ID = "c05f0e2b-b3f2-11ea-81c3-00155d3cae02"  # «Опт 3», создан в 2020


def promo_price_lists(tmp_path: Path, *, renames: dict[str, str], deleted: tuple[str, ...] = ()) -> str:
    """Каталог обмена с копией реального priceLists.xml: виды цен переименованы в акции."""
    import re

    from tests.onec_corpus import ONEC_FIXTURES, edit_copy

    def transform(text: str) -> str:
        for onec_id, name in renames.items():
            block = re.compile(rf"(<Ид>{onec_id}</Ид>.*?<Наименование>)[^<]*(</Наименование>)", re.S)
            text = block.sub(rf"\g<1>{name}\g<2>", text, count=1)
        for onec_id in deleted:
            mark = re.compile(rf"(<Ид>{onec_id}</Ид>.*?<ПометкаУдаления>)false", re.S)
            text = mark.sub(r"\g<1>true", text, count=1)
        return text

    data_dir = tmp_path / "exchange"
    edit_copy(ONEC_FIXTURES / "priceLists" / "priceLists.xml", data_dir / "priceLists" / "priceLists.xml", transform)
    return str(data_dir)


def run_price_lists_import(data_dir: str) -> None:
    from io import StringIO

    from django.core.management import call_command

    call_command(
        "import_products_from_1c",
        data_dir=data_dir,
        file_type="prices",
        skip_backup=True,
        stdout=StringIO(),
        stderr=StringIO(),
    )


class TestImportCommand:
    def test_two_new_promos_in_real_file_newest_wins(self, tmp_path):
        """Команда передаёт файл целиком: из двух новых акций текущей становится более новая по GUID."""
        data_dir = promo_price_lists(
            tmp_path, renames={OPT3_REAL_ID: "АКЦИЯ ОКТЯБРЬ-26", TRAINER_REAL_ID: "АКЦИЯ НОЯБРЬ-26"}
        )

        run_price_lists_import(data_dir)

        assert active_promo_ids() == [TRAINER_REAL_ID]
        assert PriceType.objects.get(onec_id=OPT3_REAL_ID).product_field == "promo_price"

    def test_deletion_mark_on_current_promo_ends_it(self, tmp_path):
        """AC: пометка удаления на текущем «АКЦИЯ …» — после priceLists.xml акции на сайте нет."""
        promo_type(TRAINER_REAL_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        data_dir = promo_price_lists(tmp_path, renames={TRAINER_REAL_ID: "АКЦИЯ НОЯБРЬ-26"}, deleted=(TRAINER_REAL_ID,))

        run_price_lists_import(data_dir)

        assert active_promo_ids() == []
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False


# --------------------------------------------------------------------------
# Команда импорта цен: пересчёт флага «Акция» без ручного вызова
# --------------------------------------------------------------------------

# Предложения реальной копии prices.xml; тренерская цена есть у первых трёх, у четвёртого её нет
OFFER_PLAIN = "038bca5a-747e-11ea-81c1-00155d3cae02"
OFFER_SIZE_A = "0339bffe-ed53-11ec-a302-04421a23d8e8#0a25daeb-ed53-11ec-a302-04421a23d8e8"
OFFER_SIZE_B = "0339bffe-ed53-11ec-a302-04421a23d8e8#3de8964f-ed53-11ec-a302-04421a23d8e8"
OFFER_NO_TRAINER = "069efcc9-a098-11ed-a325-04421a23d8e8"


def real_offer_variants() -> dict[str, ProductVariant]:
    """Варианты с onec_id предложений копии prices.xml, у каждого свой товар."""
    variants: dict[str, ProductVariant] = {}
    for offer_id in (OFFER_PLAIN, OFFER_SIZE_A, OFFER_SIZE_B, OFFER_NO_TRAINER):
        variant = make_variant()
        ProductVariant.objects.filter(pk=variant.pk).update(onec_id=offer_id)
        variant.refresh_from_db()
        variants[offer_id] = variant
    return variants


def prices_exchange_dir(tmp_path: Path, name: str, *, price_lists: bool, transform: Any = None) -> str:
    """Каталог обмена: копия prices.xml (с правкой) и, если нужно, priceLists.xml с акцией «Тренерская»."""
    from tests.onec_corpus import ONEC_FIXTURES, edit_copy

    data_dir = tmp_path / name
    if transform is None:
        (data_dir / "prices").mkdir(parents=True)
        (data_dir / "prices" / "prices.xml").write_text(
            (ONEC_FIXTURES / "prices" / "prices.xml").read_text(encoding="utf-8-sig"), encoding="utf-8"
        )
    else:
        edit_copy(ONEC_FIXTURES / "prices" / "prices.xml", data_dir / "prices" / "prices.xml", transform)
    if price_lists:
        promo_price_lists(data_dir.parent, renames={TRAINER_REAL_ID: "АКЦИЯ НОЯБРЬ-26"})
        (data_dir / "priceLists").mkdir(exist_ok=True)
        (data_dir.parent / "exchange" / "priceLists" / "priceLists.xml").replace(
            data_dir / "priceLists" / "priceLists.xml"
        )
    return str(data_dir)


def drop_offer_prices(offer_id: str, *, trainer_only: bool) -> Any:
    """Правка копии prices.xml: у предложения убрана тренерская цена или весь блок цен."""
    import re

    def transform(text: str) -> str:
        offer = re.compile(rf"(<Ид>{re.escape(offer_id)}</Ид>\s*)<Цены>.*?</Цены>", re.S)
        if not trainer_only:
            return offer.sub(r"\1", text, count=1)
        trainer = re.compile(rf"<Цена>(?:(?!<Цена>).)*?<ИдТипаЦены>{TRAINER_REAL_ID}</ИдТипаЦены>.*?</Цена>", re.S)
        match = re.search(rf"<Ид>{re.escape(offer_id)}</Ид>.*?</Предложение>", text, re.S)
        assert match
        return text[: match.start()] + trainer.sub("", match.group(0), count=1) + text[match.end() :]

    return transform


def run_prices_import(data_dir: str) -> None:
    run_price_lists_import(data_dir)


class TestImportCommandPromoFlags:
    """R8, R10: команда сама пересчитывает `is_promo`, а предложение без цен снимает акцию."""

    def test_promo_price_appears_and_flags_follow_without_manual_sync(self, tmp_path):
        variants = real_offer_variants()
        # Ручная отметка у товара без тренерской цены — первый же импорт её снимает
        stale = variants[OFFER_NO_TRAINER]
        ProductVariant.objects.filter(pk=stale.pk).update(promo_price=Decimal("500.00"))
        Product.objects.filter(pk=stale.product_id).update(is_promo=True)

        run_prices_import(prices_exchange_dir(tmp_path, "first", price_lists=True))

        assert active_promo_ids() == [TRAINER_REAL_ID]
        for offer_id, price in ((OFFER_PLAIN, "5592.00"), (OFFER_SIZE_A, "910.00"), (OFFER_SIZE_B, "910.00")):
            variants[offer_id].refresh_from_db()
            assert variants[offer_id].promo_price == Decimal(price)
            assert Product.objects.get(pk=variants[offer_id].product_id).is_promo is True
        stale.refresh_from_db()
        assert stale.promo_price is None
        assert Product.objects.get(pk=stale.product_id).is_promo is False

    def test_promo_price_disappears_and_flags_follow(self, tmp_path):
        variants = real_offer_variants()
        run_prices_import(prices_exchange_dir(tmp_path, "first", price_lists=True))
        assert Product.objects.get(pk=variants[OFFER_PLAIN].product_id).is_promo is True

        # Второй пакет: у одного предложения нет тренерской цены, у другого нет цен вовсе (R8)
        no_trainer = drop_offer_prices(OFFER_PLAIN, trainer_only=True)
        no_prices = drop_offer_prices(OFFER_SIZE_A, trainer_only=False)
        run_prices_import(
            prices_exchange_dir(
                tmp_path, "second", price_lists=False, transform=lambda text: no_prices(no_trainer(text))
            )
        )

        for offer_id in (OFFER_PLAIN, OFFER_SIZE_A):
            variants[offer_id].refresh_from_db()
            assert variants[offer_id].promo_price is None
            assert Product.objects.get(pk=variants[offer_id].product_id).is_promo is False
        variants[OFFER_SIZE_B].refresh_from_db()
        assert variants[OFFER_SIZE_B].promo_price == Decimal("910.00")
        assert Product.objects.get(pk=variants[OFFER_SIZE_B].product_id).is_promo is True


# --------------------------------------------------------------------------
# Повторное ревью 2026-10-22 (R11–R21)
# --------------------------------------------------------------------------


def intervene_after_first_lock(monkeypatch: pytest.MonkeyPatch, action: Any) -> None:
    """
    Выполняет `action` сразу после первого взятия блокировки состояния акции.

    Имитирует чужую транзакцию, которая зафиксировалась, пока мы ждали блокировку:
    всё, что код прочитал ДО блокировки, после неё уже устарело.
    """
    original = promo.lock_promo_state
    state = {"done": False}

    def wrapper(*args: Any, **kwargs: Any) -> None:
        original(*args, **kwargs)
        if not state["done"]:
            state["done"] = True
            action()

    monkeypatch.setattr(promo, "lock_promo_state", wrapper)


class TestKnownPromoTypeIsReadUnderLock:
    """R11: известную отключённую акцию импорт не включает, даже если её отключили во время ожидания блокировки."""

    def test_disabled_while_waiting_stays_disabled(self, processor, monkeypatch):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        intervene_after_first_lock(
            monkeypatch, lambda: PriceType.objects.filter(onec_id=NOV_ID).update(is_active=False)
        )

        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26 (новое имя)")])

        assert active_promo_ids() == []
        assert PriceType.objects.get(onec_id=NOV_ID).onec_name == "АКЦИЯ НОЯБРЬ-26 (новое имя)"

    def test_switched_while_waiting_keeps_the_new_current(self, processor, monkeypatch):
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=False)

        def admin_switches_to_october() -> None:
            PriceType.objects.filter(onec_id=NOV_ID).update(is_active=False)
            PriceType.objects.filter(onec_id=OCT_ID).update(is_active=True)

        intervene_after_first_lock(monkeypatch, admin_switches_to_october)

        processor.process_price_types([type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])

        assert active_promo_ids() == [OCT_ID]


@pytest.mark.usefixtures("regular_price_types")
class TestPriceTypesAreReadFresh:
    """R13, R14: справочник и текущая акция читаются заново под блокировкой, а не из прогретого кэша."""

    def test_stale_cached_null_does_not_hide_stored_promo_price(self, processor):
        """Другой прогон записал акционную цену после загрузки варианта: предложение без акции её снимает."""
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant()
        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1100.00"}))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("800.00"))

        processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1100.00"}))

        variant.refresh_from_db()
        assert variant.promo_price is None

    def test_promo_type_created_after_warm_up_is_applied(self, processor):
        warm = make_variant()
        target = make_variant()
        processor.update_variant_prices(price_data(warm, **{RETAIL_ID: "1200.00"}))

        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        processor.update_variant_prices(price_data(target, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        target.refresh_from_db()
        assert target.promo_price == Decimal("800.00")

    def test_remapped_price_type_does_not_write_promo_into_regular_price(self, processor):
        """Вид цен переназначили на акцию после прогрева: акционные 800 не должны уехать в opt1_price."""
        mapped = PriceType.objects.create(onec_id=NOV_ID, onec_name="АКЦИЯ НОЯБРЬ-26", product_field="opt1_price")
        warm = make_variant()
        target = make_variant(opt1_price=Decimal("700.00"))
        processor.update_variant_prices(price_data(warm, **{RETAIL_ID: "1200.00", NOV_ID: "650.00"}))

        promo.activate(PriceType.objects.get(pk=mapped.pk))
        processor.update_variant_prices(price_data(target, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"}))

        target.refresh_from_db()
        assert target.promo_price == Decimal("800.00")
        assert target.opt1_price == Decimal("700.00")


class TestStaleVariantSaveKeepsPromoPrice:
    """R12: сохранение устаревшего экземпляра варианта не возвращает сброшенную акционную цену."""

    def test_full_save_does_not_write_promo_price(self):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        stale = ProductVariant.objects.get(pk=variant.pk)

        promo.deactivate_promo(current)
        stale.size_value = "XL"
        stale.save()

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.size_value == "XL"
        assert stored.promo_price is None
        assert stored.get_price_for_user(None) == stored.retail_price

    def test_admin_save_model_does_not_write_promo_price(self):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        stale = ProductVariant.objects.get(pk=variant.pk)
        promo.deactivate_promo(current)

        stale.stock_quantity = 99
        ProductVariantAdmin(ProductVariant, AdminSite()).save_model(admin_request(), stale, form=None, change=True)

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.stock_quantity == 99
        assert stored.promo_price is None

    def test_creation_and_explicit_update_fields_still_write_promo_price(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        assert ProductVariant.objects.get(pk=variant.pk).promo_price == Decimal("800.00")

        variant.promo_price = Decimal("700.00")
        variant.save(update_fields=["promo_price"])

        assert ProductVariant.objects.get(pk=variant.pk).promo_price == Decimal("700.00")

    def test_deferred_fields_are_not_written_on_full_save(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        deferred = ProductVariant.objects.defer("stock_quantity").get(pk=variant.pk)
        ProductVariant.objects.filter(pk=variant.pk).update(stock_quantity=5)

        deferred.size_value = "M"
        deferred.save()

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.stock_quantity == 5
        assert stored.size_value == "M"


class TestStaleVariantSaveKeepsSpecialPrice:
    """Сохранение устаревшего экземпляра варианта не возвращает спеццену, которую снял импорт."""

    def test_full_save_does_not_write_special_price(self):
        variant = make_variant(special_price=Decimal("800.00"), opt1_price=Decimal("1000.00"))
        stale = ProductVariant.objects.get(pk=variant.pk)

        ProductVariant.objects.filter(pk=variant.pk).update(special_price=None)  # пакет цен без «СПЕЦЦЕНА»
        stale.vip_price = Decimal("900.00")
        stale.save()

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.vip_price == Decimal("900.00")
        assert stored.special_price is None

    def test_admin_save_model_does_not_write_special_price(self):
        variant = make_variant(special_price=Decimal("800.00"))
        stale = ProductVariant.objects.get(pk=variant.pk)
        ProductVariant.objects.filter(pk=variant.pk).update(special_price=None)

        stale.stock_quantity = 99
        ProductVariantAdmin(ProductVariant, AdminSite()).save_model(admin_request(), stale, form=None, change=True)

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.stock_quantity == 99
        assert stored.special_price is None

    def test_creation_and_explicit_update_fields_still_write_special_price(self):
        variant = make_variant(special_price=Decimal("800.00"))
        assert ProductVariant.objects.get(pk=variant.pk).special_price == Decimal("800.00")

        variant.special_price = Decimal("750.00")
        variant.save(update_fields=["special_price"])

        assert ProductVariant.objects.get(pk=variant.pk).special_price == Decimal("750.00")

    def test_full_save_still_writes_vip_price(self):
        """`vip_price` правится в админке как `opt1–4`: полное сохранение его пишет."""
        variant = make_variant(vip_price=Decimal("900.00"))
        loaded = ProductVariant.objects.get(pk=variant.pk)

        loaded.vip_price = Decimal("850.00")
        loaded.save()

        assert ProductVariant.objects.get(pk=variant.pk).vip_price == Decimal("850.00")


class TestVariantSignalsEdgeCases:
    """R15–R17: флаг «Акция» следует за активностью и товаром варианта при любых способах сохранения."""

    @staticmethod
    def flag(product_id: int) -> bool:
        return Product.objects.get(pk=product_id).is_promo

    def test_partial_save_does_not_swallow_pending_activity_change(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()

        variant.is_active = False
        variant.save(update_fields=["stock_quantity"])
        assert self.flag(variant.product_id) is True  # is_active ещё не записан

        variant.save(update_fields=["is_active"])
        assert self.flag(variant.product_id) is False

    def test_deferred_promo_price_does_not_skip_recompute(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()

        loaded = ProductVariant.objects.defer("promo_price").get(pk=variant.pk)
        loaded.is_active = False
        loaded.save()

        assert self.flag(variant.product_id) is False

    def test_deleting_variant_with_deferred_activity_clears_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()

        ProductVariant.objects.defer("is_active").get(pk=variant.pk).delete()

        assert self.flag(variant.product_id) is False

    def test_moving_variant_recomputes_both_products(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        target_product = make_variant().product
        promo.sync_promo_flags()
        old_product_id = variant.product_id
        assert self.flag(old_product_id) is True
        assert self.flag(target_product.pk) is False

        variant.product = target_product
        variant.save()

        assert self.flag(old_product_id) is False
        assert self.flag(target_product.pk) is True


class TestSyncPromoFlagsConcurrency:
    """R19: одновременное отключение последних акционных вариантов не оставляет флаг."""

    @pytest.mark.django_db(transaction=True)
    def test_two_connections_disabling_last_variants_clear_flag(self):
        import threading

        from django.db import connection

        first = make_variant(promo_price=Decimal("800.00"))
        second = ProductVariant.objects.create(
            product=first.product,
            sku="PROMO-CONCURRENT",
            onec_id=f"{first.product.onec_id}#concurrent",
            retail_price=Decimal("1500.00"),
            promo_price=Decimal("700.00"),
        )
        promo.sync_promo_flags()
        product_id = first.product_id
        assert Product.objects.get(pk=product_id).is_promo is True

        both_disabled = threading.Barrier(2, timeout=10)
        errors: list[BaseException] = []

        def disable(variant_pk: int) -> None:
            try:
                with transaction.atomic():
                    ProductVariant.objects.filter(pk=variant_pk).update(is_active=False)
                    both_disabled.wait()  # каждая транзакция уже отключила свой вариант, но не зафиксировала
                    promo.sync_promo_flags(product_id=product_id)
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=disable, args=(pk,)) for pk in (first.pk, second.pk)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=30)

        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        assert not ProductVariant.objects.filter(product_id=product_id, is_active=True).exists()
        assert Product.objects.get(pk=product_id).is_promo is False


class TestImportSharedLockAgainstDisable:
    """R20: пока импорт цен пишет акционную цену, отключение акции ждёт; итог — NULL и False."""

    @pytest.mark.django_db(transaction=True)
    def test_disable_waits_for_import_and_resets_written_price(self, processor, monkeypatch):
        import threading

        from django.db import connection

        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant()
        payload = price_data(variant, **{RETAIL_ID: "1200.00", NOV_ID: "800.00"})

        resolved = threading.Event()
        release = threading.Event()
        original = VariantImportProcessor._resolve_promo_price

        def paused_resolve(self: VariantImportProcessor, *args: Any, **kwargs: Any) -> Any:
            result = original(self, *args, **kwargs)
            resolved.set()  # текущая акция прочитана, цена ещё не записана
            assert release.wait(timeout=10)
            return result

        monkeypatch.setattr(VariantImportProcessor, "_resolve_promo_price", paused_resolve)

        imported: dict[str, Any] = {}

        def run_import() -> None:
            try:
                imported["written"] = processor.update_variant_prices(payload)
            finally:
                connection.close()

        disabled = threading.Event()

        def run_disable() -> None:
            try:
                promo.deactivate_promo(PriceType.objects.get(pk=current.pk))
                disabled.set()
            finally:
                connection.close()

        importer = threading.Thread(target=run_import)
        importer.start()
        assert resolved.wait(timeout=10)

        disabler = threading.Thread(target=run_disable)
        disabler.start()
        disabler.join(timeout=1.0)
        assert disabler.is_alive(), "отключение не дождалось импорта цен"
        assert not disabled.is_set()

        release.set()
        importer.join(timeout=10)
        disabler.join(timeout=10)

        # R30: импорт должен именно записать цену — ошибка записи, перехваченная
        # `update_variant_prices`, тоже оставила бы NULL/False и тест прошёл бы вхолостую
        assert not importer.is_alive()
        assert not disabler.is_alive()
        assert imported == {"written": True}
        assert processor.stats["errors"] == 0
        assert processor.stats["prices_updated"] == 1
        assert disabled.is_set()
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False


class TestListSelectionAndRoleRegularPrice:
    """R18, R21: единый выбор первого варианта и ролевая `regular_price` самого товара."""

    def test_prefetch_and_fallback_pick_the_same_variant(self):
        from apps.products.serializers import ProductListSerializer

        variant = make_variant(retail_price=Decimal("0"), promo_price=Decimal("700.00"))
        ProductVariant.objects.create(
            product=variant.product,
            sku="PROMO-SELECT",
            onec_id=f"{variant.product.onec_id}#select",
            retail_price=Decimal("1200.00"),
            promo_price=Decimal("800.00"),
        )

        response = APIClient().get(reverse("products:product-list"))
        item = next(row for row in response.json()["results"] if row["id"] == variant.product_id)
        without_prefetch = ProductListSerializer(Product.objects.get(pk=variant.product_id)).data

        assert item["promo_price"] == without_prefetch["promo_price"] == "800.00"
        assert item["regular_price"] == without_prefetch["regular_price"] == "1200.00"

    def test_product_regular_price_follows_role_in_list_and_detail(self):
        variant = make_variant(retail_price=Decimal("1200.00"), opt1_price=Decimal("700.00"))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("800.00"))
        client = APIClient()
        client.force_authenticate(user=make_user("wholesale_level1"))

        listing = client.get(reverse("products:product-list")).json()
        item = next(row for row in listing["results"] if row["id"] == variant.product_id)
        detail = client.get(reverse("products:product-detail", kwargs={"slug": variant.product.slug})).json()

        # Акция 800 выше цены клиента 700: он платит свою цену, акция в ответе остаётся как данные
        for data in (item, detail):
            assert data["regular_price"] == "700.00"
            assert data["promo_price"] == "800.00"
            assert data["current_price"] == "700.00"

    def test_product_current_price_is_promo_when_it_is_lower_than_role_price(self):
        variant = make_variant(retail_price=Decimal("1200.00"), opt1_price=Decimal("900.00"))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("800.00"))
        client = APIClient()
        client.force_authenticate(user=make_user("wholesale_level1"))

        listing = client.get(reverse("products:product-list")).json()
        item = next(row for row in listing["results"] if row["id"] == variant.product_id)
        detail = client.get(reverse("products:product-detail", kwargs={"slug": variant.product.slug})).json()

        for data in (item, detail):
            assert data["regular_price"] == "900.00"
            assert data["promo_price"] == "800.00"
            assert data["current_price"] == "800.00"


# --------------------------------------------------------------------------
# Третье ревью 2026-10-22 (R22–R32)
# --------------------------------------------------------------------------


def join_all(*threads: threading.Thread, timeout: float = 30.0) -> None:
    for thread in threads:
        thread.join(timeout=timeout)
    assert not any(thread.is_alive() for thread in threads), "поток не завершился"


def new_processor() -> VariantImportProcessor:
    session = ImportSession.objects.create(
        import_type=ImportSession.ImportType.CATALOG,
        status=ImportSession.ImportStatus.STARTED,
    )
    return VariantImportProcessor(session_id=session.pk)


class TestConcurrentImportsKeepOnePackage:
    """R22: цены одного варианта читаются и пишутся под блокировкой его строки."""

    @pytest.mark.django_db(transaction=True)
    def test_second_import_waits_for_the_variant_and_wins_the_whole_package(self, monkeypatch):
        from django.db import connection

        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        first, second = new_processor(), new_processor()
        # Пакет A не меняет акционную цену (800 уже записана), пакет B меняет обе цены
        package_a = price_data(variant, **{RETAIL_ID: "1250.00", NOV_ID: "800.00"})
        package_b = price_data(variant, **{RETAIL_ID: "1300.00", NOV_ID: "900.00"})

        resolved = threading.Event()
        release = threading.Event()
        original = VariantImportProcessor._resolve_promo_price

        def paused_resolve(self: VariantImportProcessor, *args: Any, **kwargs: Any) -> Any:
            result = original(self, *args, **kwargs)
            if self is first:
                resolved.set()  # прежнюю акционную цену прочитали, записи ещё нет
                assert release.wait(timeout=10)
            return result

        monkeypatch.setattr(VariantImportProcessor, "_resolve_promo_price", paused_resolve)
        outcome: dict[str, Any] = {}

        def run(name: str, processor: VariantImportProcessor, payload: dict) -> None:
            try:
                outcome[name] = processor.update_variant_prices(payload)
            finally:
                connection.close()

        thread_a = threading.Thread(target=run, args=("a", first, package_a))
        thread_a.start()
        assert resolved.wait(timeout=10)
        thread_b = threading.Thread(target=run, args=("b", second, package_b))
        thread_b.start()
        thread_b.join(timeout=1.0)
        second_waited = thread_b.is_alive()
        release.set()
        join_all(thread_a, thread_b)

        assert second_waited, "второй импорт не дождался записи первого в строку варианта"
        assert outcome == {"a": True, "b": True}
        stored = ProductVariant.objects.get(pk=variant.pk)
        assert (stored.retail_price, stored.promo_price) == (Decimal("1300.00"), Decimal("900.00"))


class PausedAfterFirst(list):
    """Файл видов цен, чей разбор замирает после первой записи: имитирует долгий прогон."""

    def __init__(self, items: list[dict]) -> None:
        super().__init__(items)
        self.started = threading.Event()
        self.release = threading.Event()

    def __iter__(self):
        items = list.__iter__(self)
        yield next(items)
        self.started.set()
        assert self.release.wait(timeout=10)
        yield from items


class TestPromoRegistrationUnderOneLock:
    """R23: чужая регистрация не вклинивается между чтением новых акций и их сохранением."""

    @pytest.mark.django_db(transaction=True)
    def test_other_process_cannot_register_between_read_and_save(self):
        from django.db import connection

        first, second = new_processor(), new_processor()
        file_a = PausedAfterFirst([type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26"), type_data(NOV_ID, "АКЦИЯ НОЯБРЬ-26")])
        outcome: dict[str, Any] = {}

        def run(name: str, processor: VariantImportProcessor, payload: Any) -> None:
            try:
                outcome[name] = processor.process_price_types(payload)
            finally:
                connection.close()

        thread_a = threading.Thread(target=run, args=("a", first, file_a))
        thread_a.start()
        assert file_a.started.wait(timeout=10)
        thread_b = threading.Thread(target=run, args=("b", second, [type_data(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26")]))
        thread_b.start()
        thread_b.join(timeout=1.0)
        second_waited = thread_b.is_alive()
        file_a.release.set()
        join_all(thread_a, thread_b)

        assert second_waited, "чужая регистрация вклинилась посреди разбора файла"
        assert (first.stats["errors"], second.stats["errors"]) == (0, 0)
        assert active_promo_ids() == [NOV_ID]
        registered = set(PriceType.objects.filter(product_field="promo_price").values_list("onec_id", flat=True))
        assert registered == {OCT_ID, NOV_ID}


class TestStaleAdminObject:
    """R24: сохранение устаревшей формы меняет только то, что менеджер правил."""

    model_admin = PriceTypeAdmin(PriceType, AdminSite())

    @staticmethod
    def stale_form(price_type: PriceType, **changes: str) -> PriceTypeAdminForm:
        data = {
            "onec_id": price_type.onec_id,
            "onec_name": price_type.onec_name,
            "product_field": price_type.product_field,
            "user_role": "",
            "is_active": "on" if price_type.is_active else "",
            # Браузер отправляет и то, что менеджер видел при открытии формы (R33)
            **seen_values(price_type),
        }
        data.update(changes)
        form = PriceTypeAdminForm(data=data, instance=price_type)
        assert form.is_valid(), form.errors
        return form

    def test_renaming_stale_previous_promo_keeps_the_new_current(self):
        october = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        form = self.stale_form(PriceType.objects.get(pk=october.pk), onec_name="АКЦИЯ ОКТЯБРЬ-26 (правка)")
        assert form.changed_data == ["onec_name"]

        # Другой запрос переключил акцию, пока форма была открыта
        promo.activate(PriceType.objects.get(pk=november.pk))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("700.00"))
        request = admin_request()
        self.model_admin.save_model(request, form.instance, form, change=True)

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("700.00")
        assert PriceType.objects.get(pk=october.pk).onec_name == "АКЦИЯ ОКТЯБРЬ-26 (правка)"
        assert messages_of(request) == []

    def test_explicit_activation_in_form_is_still_applied(self):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        form = self.stale_form(PriceType.objects.get(pk=november.pk), is_active="on")
        assert form.changed_data == ["is_active"]
        request = admin_request()

        self.model_admin.save_model(request, form.instance, form, change=True)

        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert messages_of(request) == [PriceTypeAdmin.PROMO_RESET_MESSAGE]


class TestVariantSignalsStaleInstances:
    """R25–R27: сигналы сверяются с БД, а не с устаревшим экземпляром."""

    @staticmethod
    def flag(product_id: int) -> bool:
        return Product.objects.get(pk=product_id).is_promo

    @staticmethod
    def import_writes_promo_price(variant: ProductVariant) -> None:
        """Импорт цен записал акционную цену, пока экземпляр лежал в памяти без неё."""
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_disabling_instance_loaded_without_promo_price_clears_flag(self):
        variant = make_variant()
        stale = ProductVariant.objects.get(pk=variant.pk)
        assert stale.promo_price is None
        self.import_writes_promo_price(variant)

        stale.is_active = False
        stale.save()

        assert self.flag(variant.product_id) is False

    def test_deleting_instance_loaded_without_promo_price_clears_flag(self):
        variant = make_variant()
        stale = ProductVariant.objects.get(pk=variant.pk)
        self.import_writes_promo_price(variant)

        stale.delete()

        assert self.flag(variant.product_id) is False

    def test_reenabling_after_refresh_from_db_recomputes_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        loaded = ProductVariant.objects.get(pk=variant.pk)

        other_request = ProductVariant.objects.get(pk=variant.pk)
        other_request.is_active = False
        other_request.save()
        assert self.flag(variant.product_id) is False

        loaded.refresh_from_db()
        assert loaded.is_active is False
        loaded.is_active = True
        loaded.save()

        assert self.flag(variant.product_id) is True

    def test_partial_refresh_keeps_the_pending_activity_change(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        loaded = ProductVariant.objects.get(pk=variant.pk)

        loaded.is_active = False
        loaded.refresh_from_db(fields=["stock_quantity"])
        loaded.is_active = False
        loaded.save()

        assert self.flag(variant.product_id) is False

    def test_moving_variant_with_deferred_product_recomputes_both_products(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        target_product = make_variant().product
        promo.sync_promo_flags()
        old_product_id = variant.product_id

        loaded = ProductVariant.objects.only("id", "is_active", "promo_price").get(pk=variant.pk)
        loaded.product_id = target_product.pk
        loaded.save()

        assert self.flag(old_product_id) is False
        assert self.flag(target_product.pk) is True

    def test_deleting_variant_of_unflagged_product_runs_no_recompute(self, monkeypatch):
        variant = make_variant()
        calls: list[Any] = []
        monkeypatch.setattr(promo, "sync_promo_flags", lambda *args, **kwargs: calls.append((args, kwargs)))

        variant.delete()

        assert calls == []


class TestSyncPromoFlagsMany:
    def test_recomputes_several_products_and_ignores_empty_ids(self):
        first = make_variant(promo_price=Decimal("800.00"))
        second = make_variant()
        Product.objects.filter(pk=second.product_id).update(is_promo=True)

        changed = promo.sync_promo_flags(product_ids=[second.product_id, first.product_id, second.product_id])

        assert changed == 2
        assert Product.objects.get(pk=first.product_id).is_promo is True
        assert Product.objects.get(pk=second.product_id).is_promo is False
        assert promo.sync_promo_flags(product_ids=[]) == 0

    @pytest.mark.django_db(transaction=True)
    def test_product_lock_does_not_block_variant_insert(self):
        """Блокировка товара `FOR NO KEY UPDATE`: вставка варианта (FK `KEY SHARE`) её не ждёт."""
        from django.db import connection

        variant = make_variant(promo_price=Decimal("800.00"))
        outcome: dict[str, Any] = {}

        def insert_variant() -> None:
            try:
                ProductVariant.objects.create(
                    product_id=variant.product_id,
                    sku="PROMO-FK-CHECK",
                    onec_id=f"{variant.product.onec_id}#fk-check",
                    retail_price=Decimal("100.00"),
                )
                outcome["done"] = True
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                outcome["error"] = exc
            finally:
                connection.close()

        worker = threading.Thread(target=insert_variant)
        with transaction.atomic():
            promo.sync_promo_flags(product_id=variant.product_id)  # строка товара заблокирована до конца транзакции
            worker.start()
            worker.join(timeout=10.0)
            insert_finished_under_lock = not worker.is_alive()
        join_all(worker)

        assert outcome == {"done": True}
        assert insert_finished_under_lock, "вставка варианта ждала блокировку товара"


class TestGlobalRecomputeAgainstSingle:
    """R28: глобальный пересчёт после ожидания блокировки товара считает по свежим данным."""

    @pytest.mark.django_db(transaction=True)
    def test_global_recompute_waits_and_sees_committed_activation(self):
        from django.db import connection

        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        product_id = variant.product_id
        # Без сигналов: вариант отключён, флаг ещё True (окно между ценами и завершающим пересчётом)
        ProductVariant.objects.filter(pk=variant.pk).update(is_active=False)
        assert Product.objects.get(pk=product_id).is_promo is True
        outcome: dict[str, Any] = {}

        def run_global_recompute() -> None:
            try:
                outcome["changed"] = promo.sync_promo_flags()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                outcome["error"] = exc
            finally:
                connection.close()

        worker = threading.Thread(target=run_global_recompute)
        with transaction.atomic():
            fresh = ProductVariant.objects.get(pk=variant.pk)
            fresh.is_active = True
            fresh.save()  # сигнал: пересчёт товара под блокировкой его строки
            worker.start()
            worker.join(timeout=1.0)
            assert worker.is_alive(), "глобальный пересчёт не дождался блокировки товара"
        join_all(worker)

        assert "error" not in outcome, outcome
        assert ProductVariant.objects.filter(product_id=product_id, is_active=True, promo_price__gt=0).exists()
        assert Product.objects.get(pk=product_id).is_promo is True


class TestOppositeMovesDoNotDeadlock:
    """R29: встречные переносы вариантов берут блокировки товаров в одном порядке."""

    @pytest.mark.django_db(transaction=True)
    def test_two_connections_moving_variants_in_opposite_directions(self, monkeypatch):
        from django.db import connection

        first = make_variant(promo_price=Decimal("800.00"))
        second = make_variant(promo_price=Decimal("700.00"))
        product_a, product_b = first.product_id, second.product_id
        promo.sync_promo_flags()

        # Обе транзакции после пересчёта ждут друг друга: так встречные переносы сталкиваются
        # при любом порядке блокировок. Барьер не вечный — если вторая транзакция ждёт
        # блокировку первой, первая идёт дальше по таймауту.
        rendezvous = threading.Barrier(2)
        original = promo.sync_promo_flags

        def synced(*args: Any, **kwargs: Any) -> int:
            result = original(*args, **kwargs)
            try:
                rendezvous.wait(timeout=3)
            except threading.BrokenBarrierError:
                pass
            return result

        monkeypatch.setattr(promo, "sync_promo_flags", synced)
        errors: list[BaseException] = []

        def move(variant_pk: int, target_product_id: int) -> None:
            try:
                with transaction.atomic():
                    variant = ProductVariant.objects.get(pk=variant_pk)
                    variant.product_id = target_product_id
                    variant.save()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        threads = [
            threading.Thread(target=move, args=(first.pk, product_b)),
            threading.Thread(target=move, args=(second.pk, product_a)),
        ]
        for thread in threads:
            thread.start()
        join_all(*threads)

        assert errors == []
        assert Product.objects.get(pk=product_a).is_promo is True
        assert Product.objects.get(pk=product_b).is_promo is True


class TestRemappingCurrentPromoType:
    """R31: перевод текущей акции на обычное поле при сохранённом «Активный» сбрасывает цены."""

    def test_real_admin_post_remapping_to_regular_field_resets_prices_and_flags(self, client):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        assert Product.objects.get(pk=variant.product_id).is_promo is True
        admin_user = make_user("retail")
        User.objects.filter(pk=admin_user.pk).update(is_staff=True, is_superuser=True)
        client.force_login(admin_user)

        response = client.post(
            reverse("admin:products_pricetype_change", args=[current.pk]),
            {
                "onec_id": NOV_ID,
                "onec_name": "АКЦИЯ НОЯБРЬ-26",
                "product_field": "opt2_price",
                "user_role": "",
                "is_active": "on",
            },
        )

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert PriceType.objects.get(pk=current.pk).product_field == "opt2_price"
        assert active_promo_ids() == []
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False


# --------------------------------------------------------------------------
# Четвёртый прогон ревью: R33, R38, R39 — форма и сервис видов цен
# --------------------------------------------------------------------------


class TestStaleFormPost:
    """R33: настоящий цикл GET → POST. Форма, открытая до переключения акции, не возвращает прежнюю."""

    def test_stale_post_renaming_previous_promo_keeps_the_new_current(self, client):
        october = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        staff_login(client)
        url = reverse("admin:products_pricetype_change", args=[october.pk])

        data = browser_post_data(client.get(url))  # менеджер видит активный октябрь
        assert data["is_active"] == "on"
        data["onec_name"] = "АКЦИЯ ОКТЯБРЬ-26 (правка)"
        # Другой запрос переключил акцию, пока страница была открыта
        promo.activate(PriceType.objects.get(pk=november.pk))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("700.00"))

        response = client.post(url, data)

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("700.00")
        assert PriceType.objects.get(pk=october.pk).onec_name == "АКЦИЯ ОКТЯБРЬ-26 (правка)"

    def test_stale_post_still_applies_what_the_manager_changed(self, client):
        """Менеджер включил ноябрь на устаревшей странице — это его осознанное действие."""
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        staff_login(client)
        url = reverse("admin:products_pricetype_change", args=[november.pk])

        data = browser_post_data(client.get(url))
        assert "is_active" not in data
        data["is_active"] = "on"
        response = client.post(url, data)

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price is None

    def test_post_without_seen_values_compares_with_the_stored_record(self):
        """POST без скрытых `initial-*` (не браузер): снятая галочка — осознанное действие, а не «не менялось»."""
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        form = PriceTypeAdminForm(
            data={"onec_id": NOV_ID, "onec_name": "АКЦИЯ НОЯБРЬ-26", "product_field": "promo_price", "user_role": ""},
            instance=current,
        )

        assert form.is_valid(), form.errors
        assert form.changed_data == ["is_active"]


class TestVanishedPriceType:
    """R38: запись исчезла между открытием формы и сохранением — конфликт, а не создание заново."""

    def test_service_refuses_to_recreate_deleted_type(self):
        old = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        new = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        stale = PriceType.objects.get(pk=old.pk)

        promo.delete_price_types([PriceType.objects.get(pk=old.pk)])  # другой запрос удалил прежнюю акцию
        promo.activate(PriceType.objects.get(pk=new.pk))
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("700.00"))
        stale.onec_name = "АКЦИЯ ОКТЯБРЬ-26 (правка)"

        with pytest.raises(promo.PriceTypeConflict):
            promo.save_price_type(stale, changed_fields=["onec_name"])
        with pytest.raises(promo.PriceTypeConflict):
            promo.save_price_type(stale)

        assert not PriceType.objects.filter(pk=old.pk).exists()
        assert active_promo_ids() == [NOV_ID]
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("700.00")

    def test_new_type_is_still_created(self):
        created = PriceType(onec_id=OCT_ID, onec_name="АКЦИЯ ОКТЯБРЬ-26", product_field="promo_price")

        assert promo.save_price_type(created) is True
        assert active_promo_ids() == [OCT_ID]

    def test_admin_post_reports_conflict(self, client, monkeypatch):
        old = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        staff_login(client)
        url = reverse("admin:products_pricetype_change", args=[old.pk])
        data = browser_post_data(client.get(url))
        data["onec_name"] = "АКЦИЯ ОКТЯБРЬ-26 (правка)"
        original = PriceTypeAdmin.save_model

        def vanish_then_save(model_admin: Any, request: Any, obj: Any, form: Any, change: bool) -> None:
            PriceType.objects.filter(pk=obj.pk).delete()  # форма уже проверена, запись удалил другой запрос
            original(model_admin, request, obj, form, change)

        monkeypatch.setattr(PriceTypeAdmin, "save_model", vanish_then_save)

        response = client.post(url, data)

        assert response.status_code == 302
        assert response.url == reverse("admin:products_pricetype_changelist")
        assert [str(message) for message in get_messages(response.wsgi_request)] == [PriceTypeAdmin.CONFLICT_MESSAGE]


class TestPriceTypeGuidIsImmutable:
    """R39: GUID вида цен 1С не меняется — иначе цены прежнего вида остались бы у другого."""

    def test_form_keeps_guid_of_existing_type(self):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        form = PriceTypeAdminForm(
            data={
                "onec_id": OCT_ID,
                "onec_name": "АКЦИЯ НОЯБРЬ-26",
                "product_field": "promo_price",
                "user_role": "",
                "is_active": "on",
                **seen_values(current),
            },
            instance=current,
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["onec_id"] == NOV_ID
        assert "onec_id" not in form.changed_data
        assert form.instance.onec_id == NOV_ID

    def test_form_can_still_create_type_with_guid(self):
        form = PriceTypeAdminForm(
            data={"onec_id": OCT_ID.upper(), "onec_name": "АКЦИЯ", "product_field": "promo_price", "user_role": ""}
        )

        assert form.is_valid(), form.errors
        assert form.cleaned_data["onec_id"] == OCT_ID

    @pytest.mark.parametrize("changed_fields", [None, ["onec_id"]])
    def test_service_refuses_to_replace_guid(self, changed_fields):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        current.onec_id = OCT_ID

        with pytest.raises(ValueError):
            promo.save_price_type(current, changed_fields=changed_fields)

        assert PriceType.objects.get(pk=current.pk).onec_id == NOV_ID
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")


# --------------------------------------------------------------------------
# Четвёртый прогон ревью: R34–R37, R40–R43 — флаг «Акция», сигналы вариантов, порядок блокировок
# --------------------------------------------------------------------------


def backend_pid() -> int:
    """PID сеанса PostgreSQL текущего потока."""
    from django.db import connection

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_backend_pid()")
        return int(cursor.fetchone()[0])


class Sessions:
    """
    PID сеансов PostgreSQL потоков теста.

    R51: «кто-то стоит на какой-то блокировке» не доказывает нужного пересечения операций. Поток
    записывает свой PID под именем, а `blocked` ждёт, что именно этот сеанс стоит на блокировке,
    которую держит именно названный другой.
    """

    def __init__(self) -> None:
        self._pids: dict[str, int] = {}
        self._changed = threading.Condition()

    def record(self, name: str) -> None:
        pid = backend_pid()
        with self._changed:
            self._pids[name] = pid
            self._changed.notify_all()

    def pid(self, name: str, timeout: float = 10.0) -> int:
        with self._changed:
            assert self._changed.wait_for(lambda: name in self._pids, timeout=timeout), f"нет сеанса {name}"
            return self._pids[name]

    def blocked(self, waiter: str, blocker: str, timeout: float = 5.0) -> bool:
        """Ждёт, пока сеанс `waiter` встанет на блокировку, которую держит сеанс `blocker`."""
        import time

        from django.db import connection

        waiter_pid, blocker_pid = self.pid(waiter), self.pid(blocker)
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with connection.cursor() as cursor:
                cursor.execute("SELECT %s = ANY(pg_blocking_pids(%s))", [blocker_pid, waiter_pid])
                if cursor.fetchone()[0]:
                    return True
            time.sleep(0.05)
        return False


class TestProductSaveKeepsDerivedFlag:
    """R34: `is_promo` выводится из акционных цен — устаревший экземпляр товара его не возвращает."""

    def test_admin_save_model_does_not_restore_stale_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        stale = Product.objects.get(pk=variant.product_id)
        assert stale.is_promo is True
        ProductVariant.objects.filter(pk=variant.pk).update(promo_price=None)  # акция закончилась
        promo.sync_promo_flags()
        assert Product.objects.get(pk=stale.pk).is_promo is False

        stale.name = "Новое имя товара"
        ProductAdmin(Product, AdminSite()).save_model(admin_request(), stale, form=None, change=True)

        saved = Product.objects.get(pk=stale.pk)
        assert saved.name == "Новое имя товара"
        assert saved.is_promo is False

    def test_plain_save_does_not_write_the_flag_in_either_direction(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        stale = Product.objects.get(pk=variant.product_id)

        stale.is_promo = False
        stale.name = "Другое имя"
        stale.save()

        saved = Product.objects.get(pk=variant.product_id)
        assert saved.name == "Другое имя"
        assert saved.is_promo is True

    def test_creation_and_explicit_update_fields_still_write_the_flag(self):
        template = make_variant().product
        product = Product.objects.create(
            name="Созданный акционный",
            slug="promo-created-product",
            brand=template.brand,
            category=template.category,
            onec_id="promo-created-product",
            is_promo=True,
        )
        assert Product.objects.get(pk=product.pk).is_promo is True

        product.is_promo = False
        product.save(update_fields=["is_promo"])

        assert Product.objects.get(pk=product.pk).is_promo is False

    def test_deferred_fields_are_left_alone(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        partial = Product.objects.only("id", "name").get(pk=variant.product_id)

        partial.name = "Только имя"
        partial.save()

        saved = Product.objects.get(pk=variant.product_id)
        assert saved.name == "Только имя"
        assert saved.is_promo is True


class TestVariantSignalsActualState:
    """R35–R37: сигналы сверяются с состоянием строки в БД перед записью, а не со снимком экземпляра."""

    @staticmethod
    def flag(product_id: int) -> bool:
        return Product.objects.get(pk=product_id).is_promo

    def test_stale_full_save_that_reenables_variant_recomputes_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        stale = ProductVariant.objects.get(pk=variant.pk)  # знает, что вариант активен
        other = ProductVariant.objects.get(pk=variant.pk)
        other.is_active = False
        other.save()
        assert self.flag(variant.product_id) is False

        stale.save()  # полное сохранение возвращает is_active=True

        assert ProductVariant.objects.get(pk=variant.pk).is_active is True
        assert self.flag(variant.product_id) is True

    def test_stale_full_save_that_moves_variant_back_recomputes_both_products(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        target = make_variant().product
        promo.sync_promo_flags()
        old_product_id = variant.product_id
        stale = ProductVariant.objects.get(pk=variant.pk)  # знает товар A
        mover = ProductVariant.objects.get(pk=variant.pk)
        mover.product_id = target.pk
        mover.save()
        assert self.flag(old_product_id) is False
        assert self.flag(target.pk) is True

        stale.save()  # возвращает вариант в A

        assert self.flag(old_product_id) is True
        assert self.flag(target.pk) is False

    def test_deleting_stale_instance_recomputes_current_owner(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        target = make_variant().product
        promo.sync_promo_flags()
        stale = ProductVariant.objects.get(pk=variant.pk)  # знает товар A
        mover = ProductVariant.objects.get(pk=variant.pk)
        mover.product_id = target.pk
        mover.save()
        assert self.flag(target.pk) is True

        stale.delete()  # строка лежит у товара B

        assert self.flag(target.pk) is False

    def test_deleting_variant_loaded_without_owner_clears_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        assert self.flag(variant.product_id) is True

        ProductVariant.objects.only("id").get(pk=variant.pk).delete()

        assert self.flag(variant.product_id) is False

    def test_deleting_variant_without_promo_price_runs_no_recompute(self, monkeypatch):
        variant = make_variant()
        calls: list[Any] = []
        monkeypatch.setattr(promo, "sync_promo_flags", lambda *args, **kwargs: calls.append((args, kwargs)))

        ProductVariant.objects.only("id").get(pk=variant.pk).delete()

        assert calls == []

    def test_saving_variant_without_promo_price_runs_no_recompute(self, monkeypatch):
        variant = make_variant()
        calls: list[Any] = []
        monkeypatch.setattr(promo, "sync_promo_flags", lambda *args, **kwargs: calls.append((args, kwargs)))

        loaded = ProductVariant.objects.get(pk=variant.pk)
        loaded.is_active = False
        loaded.save()

        assert calls == []


class TestDeleteRecomputesUnderLock:
    """R41: решение о пересчёте при удалении принимается без оглядки на флаг, который мог устареть."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_global_recompute_cannot_leave_flag_of_deleted_variant(self):
        from django.db import connection

        variant = make_variant(promo_price=Decimal("800.00"))  # цена записана, пересчёта флага ещё не было
        product_id = variant.product_id
        assert Product.objects.get(pk=product_id).is_promo is False
        outcome: dict[str, Any] = {}

        def run_global_recompute() -> None:
            try:
                outcome["changed"] = promo.sync_promo_flags()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                outcome["error"] = exc
            finally:
                connection.close()

        worker = threading.Thread(target=run_global_recompute)
        with transaction.atomic():
            ProductVariant.objects.get(pk=variant.pk).delete()  # ещё не зафиксировано: другая транзакция видит вариант
            worker.start()
            worker.join(timeout=1.0)  # пересчёт либо ждёт блокировку товара, либо успевает записать True
        join_all(worker)

        assert "error" not in outcome, outcome
        assert not ProductVariant.objects.filter(pk=variant.pk).exists()
        assert Product.objects.get(pk=product_id).is_promo is False


class TestBatchDeleteLockOrder:
    """R42: пакетное удаление берёт блокировки товаров всего набора по возрастанию `pk`."""

    @pytest.mark.django_db(transaction=True)
    def test_batch_delete_and_move_in_opposite_order_do_not_deadlock(self, monkeypatch):
        from django.db import connection

        mover_variant = make_variant(promo_price=Decimal("800.00"))  # товар A, будет перенесён в B
        other = make_variant(promo_price=Decimal("700.00"))  # товар B
        product_a, product_b = mover_variant.product, other.product
        assert product_a.pk < product_b.pk
        # Django отправляет `post_delete` по убыванию `pk`: у варианта товара B `pk` больше, поэтому
        # сначала блокируется B, потом A — обратно порядку переноса (A, затем B)
        doomed_a = ProductVariant.objects.create(
            product=product_a,
            sku="PROMO-DOOMED-A",
            onec_id=f"{product_a.onec_id}#doomed",
            retail_price=Decimal("100.00"),
            promo_price=Decimal("500.00"),
        )
        doomed_b = ProductVariant.objects.create(
            product=product_b,
            sku="PROMO-DOOMED-B",
            onec_id=f"{product_b.onec_id}#doomed",
            retail_price=Decimal("100.00"),
            promo_price=Decimal("600.00"),
        )
        promo.sync_promo_flags()

        first_signal_done = threading.Event()
        sessions = Sessions()
        original = promo.sync_promo_flags

        def synced(*args: Any, **kwargs: Any) -> int:
            result = original(*args, **kwargs)
            if threading.current_thread().name == "deleter" and not first_signal_done.is_set():
                first_signal_done.set()
                # R51: перенос должен именно встать на блокировку товара, которую держит удаление
                assert sessions.blocked("mover", "deleter")
            return result

        monkeypatch.setattr(promo, "sync_promo_flags", synced)
        errors: list[BaseException] = []

        def delete_batch() -> None:
            try:
                sessions.record("deleter")
                with transaction.atomic():
                    ProductVariant.objects.filter(pk__in=[doomed_b.pk, doomed_a.pk]).delete()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        def move() -> None:
            try:
                sessions.record("mover")
                first_signal_done.wait(timeout=10)
                with transaction.atomic():
                    variant = ProductVariant.objects.get(pk=mover_variant.pk)
                    variant.product_id = product_b.pk
                    variant.save()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=delete_batch, name="deleter"), threading.Thread(target=move, name="mover")]
        for thread in threads:
            thread.start()
        join_all(*threads)

        assert errors == []
        assert not ProductVariant.objects.filter(pk__in=[doomed_b.pk, doomed_a.pk]).exists()
        assert Product.objects.get(pk=product_a.pk).is_promo is False
        assert Product.objects.get(pk=product_b.pk).is_promo is True


class TestSwitchAgainstProductAdminSave:
    """R40: сброс цен при смене акции берёт блокировки в порядке «товар → вариант», как сохранение товара."""

    @pytest.mark.django_db(transaction=True)
    def test_product_save_with_inline_variant_and_switch_do_not_deadlock(self):
        from django.db import connection

        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        product_id = variant.product_id
        product_saved = threading.Event()
        sessions = Sessions()
        errors: list[BaseException] = []

        def save_product_with_inline() -> None:
            """Обычная админка: сначала строка товара, затем инлайн-варианты."""
            try:
                sessions.record("saver")
                with transaction.atomic():
                    product = Product.objects.get(pk=product_id)
                    product.name = "Новое имя товара"
                    product.save()
                    product_saved.set()
                    # R51: переключение должно именно встать на строку товара, которую держит сохранение
                    assert sessions.blocked("switcher", "saver")
                    inline = ProductVariant.objects.get(pk=variant.pk)
                    inline.color_name = "Красный"
                    inline.save()
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        def switch_promo() -> None:
            try:
                sessions.record("switcher")
                product_saved.wait(timeout=10)
                promo.activate(PriceType.objects.get(pk=november.pk))
            except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
                errors.append(exc)
            finally:
                connection.close()

        threads = [threading.Thread(target=save_product_with_inline), threading.Thread(target=switch_promo)]
        for thread in threads:
            thread.start()
        join_all(*threads)

        assert errors == []
        assert active_promo_ids() == [NOV_ID]
        saved = ProductVariant.objects.get(pk=variant.pk)
        assert saved.color_name == "Красный"
        assert saved.promo_price is None
        assert Product.objects.get(pk=product_id).is_promo is False


class TestSyncPromoFlagsChunks:
    """R43: пересчёт всего каталога обрабатывает каждую пачку, а не только первую."""

    def test_every_chunk_is_recomputed(self, monkeypatch):
        monkeypatch.setattr(promo, "PROMO_FLAG_CHUNK", 2)
        with_promo = [make_variant(promo_price=Decimal("800.00")) for _ in range(5)]  # флаг False → True
        without_promo = [make_variant() for _ in range(3)]
        Product.objects.filter(pk__in=[v.product_id for v in without_promo]).update(is_promo=True)  # True → False
        chunks: list[list[int]] = []
        original = promo._recompute_locked

        def spy(product_ids: list[int]) -> int:
            chunks.append(list(product_ids))
            return original(product_ids)

        monkeypatch.setattr(promo, "_recompute_locked", spy)

        changed = promo.sync_promo_flags()

        assert changed == 8
        assert [len(chunk) for chunk in chunks] == [2, 2, 2, 2]
        assert sorted(pk for chunk in chunks for pk in chunk) == sorted(
            v.product_id for v in [*with_promo, *without_promo]
        )
        assert all(Product.objects.get(pk=v.product_id).is_promo for v in with_promo)
        assert not any(Product.objects.get(pk=v.product_id).is_promo for v in without_promo)
        assert promo.sync_promo_flags() == 0


# --------------------------------------------------------------------------
# Пятый прогон ревью: R46–R52 — состояние варианта под блокировкой, порядок блокировок
# --------------------------------------------------------------------------


class Gate:
    """Точка остановки потока: поток сообщает «дошёл» и ждёт, пока основной тест не разрешит идти дальше."""

    def __init__(self) -> None:
        self.reached = threading.Event()
        self.release = threading.Event()

    def stop(self) -> None:
        self.reached.set()
        assert self.release.wait(timeout=10), "тест не отпустил поток"


def start_worker(name: str, work: Any, errors: list[BaseException]) -> threading.Thread:
    """Запускает `work` в потоке со своим соединением; исключение попадает в `errors`."""
    from django.db import connection

    def run() -> None:
        try:
            work()
        except BaseException as exc:  # noqa: BLE001 — исход проверяется в основном потоке
            errors.append(exc)
        finally:
            connection.close()

    thread = threading.Thread(target=run, name=name)
    thread.start()
    return thread


def pause_in_thread(monkeypatch: pytest.MonkeyPatch, thread_name: str, gate: Gate, target: str, *, after: bool) -> None:
    """Останавливает первый вызов `promo.<target>` в потоке `thread_name` до `gate.release`."""
    original = getattr(promo, target)

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        if threading.current_thread().name != thread_name or gate.reached.is_set():
            return original(*args, **kwargs)
        if after:
            result = original(*args, **kwargs)
            gate.stop()
            return result
        gate.stop()
        return original(*args, **kwargs)

    monkeypatch.setattr(promo, target, wrapper)


class TestStoredStateIsReadUnderLock:
    """R46: состояние варианта читается под блокировкой, в одной транзакции с записью и пересчётом."""

    @pytest.mark.django_db(transaction=True)
    def test_concurrent_disable_and_enable_leave_flag_matching_final_state(self, monkeypatch):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "disabler", gate, "sync_promo_flags", after=True)

        def disable() -> None:
            sessions.record("disabler")
            with transaction.atomic():
                loaded = ProductVariant.objects.get(pk=variant.pk)
                loaded.is_active = False
                loaded.save(update_fields=["is_active"])

        def enable() -> None:
            sessions.record("enabler")
            loaded = ProductVariant.objects.get(pk=variant.pk)  # загружен активным
            loaded.is_active = True
            loaded.save(update_fields=["is_active"])

        disabler = start_worker("disabler", disable, errors)
        assert gate.reached.wait(timeout=10)  # отключён и пересчитан, но не зафиксирован
        enabler = start_worker("enabler", enable, errors)
        assert sessions.blocked("enabler", "disabler")
        gate.release.set()
        join_all(disabler, enabler)

        assert errors == []
        assert ProductVariant.objects.get(pk=variant.pk).is_active is True
        assert Product.objects.get(pk=variant.product_id).is_promo is True

    @pytest.mark.django_db(transaction=True)
    def test_two_moves_of_one_variant_leave_no_flag_on_intermediate_owner(self, monkeypatch):
        variant = make_variant(promo_price=Decimal("800.00"))
        product_a = variant.product_id
        product_b = make_variant().product_id
        product_c = make_variant().product_id
        promo.sync_promo_flags()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "first", gate, "sync_promo_flags", after=True)

        def move(name: str, target: int) -> Any:
            def run() -> None:
                sessions.record(name)
                with transaction.atomic():
                    loaded = ProductVariant.objects.get(pk=variant.pk)  # обе загружают вариант у товара A
                    loaded.product_id = target
                    loaded.save()

            return run

        first = start_worker("first", move("first", product_b), errors)
        assert gate.reached.wait(timeout=10)
        second = start_worker("second", move("second", product_c), errors)
        assert sessions.blocked("second", "first")
        gate.release.set()
        join_all(first, second)

        assert errors == []
        assert ProductVariant.objects.get(pk=variant.pk).product_id == product_c
        assert Product.objects.get(pk=product_a).is_promo is False
        assert Product.objects.get(pk=product_b).is_promo is False
        assert Product.objects.get(pk=product_c).is_promo is True

    @pytest.mark.django_db(transaction=True)
    def test_price_written_between_state_read_and_disable_does_not_leave_flag(self):
        from django.db.models.signals import pre_save

        variant = make_variant()  # акционной цены пока нет
        gate = Gate()
        errors: list[BaseException] = []

        def pause_after_state_read(sender: Any, instance: Any, **kwargs: Any) -> None:
            if threading.current_thread().name == "disabler" and not gate.reached.is_set():
                gate.stop()

        def disable() -> None:
            loaded = ProductVariant.objects.get(pk=variant.pk)
            loaded.is_active = False
            loaded.save(update_fields=["is_active"])

        def write_price() -> None:
            ProductVariant.objects.filter(pk=variant.pk).update(promo_price=Decimal("800.00"))
            promo.sync_promo_flags()

        pre_save.connect(pause_after_state_read, sender=ProductVariant, weak=False, dispatch_uid="r46-pause")
        try:
            disabler = start_worker("disabler", disable, errors)
            assert gate.reached.wait(timeout=10)  # состояние строки прочитано, запись ещё впереди
            writer = start_worker("writer", write_price, errors)
            writer.join(timeout=1.0)  # запись цены либо ждёт строку варианта, либо успевает зафиксироваться
            gate.release.set()
            join_all(disabler, writer)
        finally:
            pre_save.disconnect(dispatch_uid="r46-pause", sender=ProductVariant)

        assert errors == []
        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.is_active is False
        assert stored.promo_price == Decimal("800.00")
        assert Product.objects.get(pk=variant.product_id).is_promo is False


class TestVariantSaveIsAtomicWithRecompute:
    """R47: изменение активности или товара и пересчёт флага — одна транзакция."""

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("change", ["deactivate", "move", "delete"])
    def test_failed_recompute_rolls_back_the_change(self, monkeypatch, change):
        variant = make_variant(promo_price=Decimal("800.00"))
        target_id = make_variant().product_id
        promo.sync_promo_flags()
        owner_id = variant.product_id

        def failing(*args: Any, **kwargs: Any) -> int:
            raise RuntimeError("пересчёт упал")

        monkeypatch.setattr(promo, "sync_promo_flags", failing)
        loaded = ProductVariant.objects.get(pk=variant.pk)

        with pytest.raises(RuntimeError):
            if change == "deactivate":
                loaded.is_active = False
                loaded.save(update_fields=["is_active"])
            elif change == "move":
                loaded.product_id = target_id
                loaded.save(update_fields=["product"])
            else:
                loaded.delete()

        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.is_active is True
        assert stored.product_id == owner_id
        assert Product.objects.get(pk=owner_id).is_promo is True
        assert Product.objects.get(pk=target_id).is_promo is False


class TestVariantWritesAgainstSwitch:
    """R48: сохранение и удаление отдельного варианта берут блокировки «товар → вариант», как сброс акции."""

    @staticmethod
    def prepare() -> tuple[ProductVariant, PriceType]:
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        return variant, november

    @pytest.mark.django_db(transaction=True)
    def test_variant_save_in_outer_transaction_and_switch_do_not_deadlock(self, monkeypatch):
        variant, november = self.prepare()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "saver", gate, "sync_promo_flags", after=False)  # строка варианта уже записана

        def save_variant() -> None:
            sessions.record("saver")
            with transaction.atomic():
                loaded = ProductVariant.objects.get(pk=variant.pk)
                loaded.is_active = False
                loaded.save(update_fields=["is_active"])

        def switch() -> None:
            sessions.record("switcher")
            promo.activate(PriceType.objects.get(pk=november.pk))

        saver = start_worker("saver", save_variant, errors)
        assert gate.reached.wait(timeout=10)
        switcher = start_worker("switcher", switch, errors)
        assert sessions.blocked("switcher", "saver")
        gate.release.set()
        join_all(saver, switcher)

        assert errors == []
        assert active_promo_ids() == [NOV_ID]
        stored = ProductVariant.objects.get(pk=variant.pk)
        assert stored.is_active is False
        assert stored.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False

    @pytest.mark.django_db(transaction=True)
    def test_variant_delete_and_switch_do_not_deadlock(self, monkeypatch):
        variant, november = self.prepare()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "deleter", gate, "sync_promo_flags", after=False)  # вариант уже удалён

        def delete_variant() -> None:
            sessions.record("deleter")
            with transaction.atomic():
                ProductVariant.objects.get(pk=variant.pk).delete()

        def switch() -> None:
            sessions.record("switcher")
            promo.activate(PriceType.objects.get(pk=november.pk))

        deleter = start_worker("deleter", delete_variant, errors)
        assert gate.reached.wait(timeout=10)
        switcher = start_worker("switcher", switch, errors)
        assert sessions.blocked("switcher", "deleter")
        gate.release.set()
        join_all(deleter, switcher)

        assert errors == []
        assert active_promo_ids() == [NOV_ID]
        assert not ProductVariant.objects.filter(pk=variant.pk).exists()
        assert Product.objects.get(pk=variant.product_id).is_promo is False


class TestBatchDeleteLocksCurrentOwners:
    """R49: пакетное удаление блокирует тех, у кого варианты лежат сейчас, а не набор, собранный до переноса."""

    @pytest.mark.django_db(transaction=True)
    def test_move_after_collecting_owners_does_not_deadlock(self, monkeypatch):
        staying = make_variant(promo_price=Decimal("800.00"))  # товар A, остаётся
        doomed = make_variant(promo_price=Decimal("600.00"))  # товар B, перед удалением переедет в A
        product_a, product_b = staying.product_id, doomed.product_id
        assert product_a < product_b
        promo.sync_promo_flags()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "deleter", gate, "lock_products", after=False)
        holding_a, go_b = threading.Event(), threading.Event()

        def delete_batch() -> None:
            sessions.record("deleter")
            with transaction.atomic():
                ProductVariant.objects.filter(pk=doomed.pk).delete()

        def recompute_a_then_b() -> None:
            """Параллельный пересчёт A и B: берёт товары по возрастанию и держит A, пока ждёт B."""
            sessions.record("holder")
            with transaction.atomic():
                promo.lock_products([product_a])
                holding_a.set()
                assert go_b.wait(timeout=10)
                promo.lock_products([product_b])

        deleter = start_worker("deleter", delete_batch, errors)
        assert gate.reached.wait(timeout=10)  # владельцы набора собраны, блокировки ещё не взяты
        ProductVariant.objects.filter(pk=doomed.pk).update(product_id=product_a)  # вариант переехал B → A
        holder = start_worker("holder", recompute_a_then_b, errors)
        assert holding_a.wait(timeout=10)
        gate.release.set()
        assert sessions.blocked("deleter", "holder")  # удалению нужен товар A
        go_b.set()
        join_all(deleter, holder)

        assert errors == []
        assert not ProductVariant.objects.filter(pk=doomed.pk).exists()
        assert Product.objects.get(pk=product_a).is_promo is True  # остался вариант staying


class TestResetCoversMovedVariants:
    """R52: сброс акции пересчитывает флаги тех, у кого очищенные варианты лежат на момент блокировок."""

    @pytest.mark.django_db(transaction=True)
    def test_variant_moved_after_collecting_owners_gets_its_flag_recomputed(self, monkeypatch):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        target_id = make_variant().product_id
        promo.sync_promo_flags()
        owner_id = variant.product_id
        gate = Gate()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "switcher", gate, "lock_products", after=False)

        def switch() -> None:
            promo.activate(PriceType.objects.get(pk=november.pk))

        switcher = start_worker("switcher", switch, errors)
        assert gate.reached.wait(timeout=10)  # владельцы акционных цен собраны, блокировок нет
        moved = ProductVariant.objects.get(pk=variant.pk)
        moved.product_id = target_id
        moved.save()  # перенос завершился до блокировок сброса
        assert Product.objects.get(pk=owner_id).is_promo is False
        assert Product.objects.get(pk=target_id).is_promo is True
        gate.release.set()
        join_all(switcher)

        assert errors == []
        assert ProductVariant.objects.get(pk=variant.pk).promo_price is None
        assert Product.objects.get(pk=owner_id).is_promo is False
        assert Product.objects.get(pk=target_id).is_promo is False


class TestLockVariantNeedsTransaction:
    """Блокировки живут до конца транзакции: вне её хелпер молча ничего бы не удержал."""

    @pytest.mark.django_db(transaction=True)
    def test_outside_transaction_raises(self):
        variant = make_variant()

        with pytest.raises(RuntimeError):
            promo.lock_variant(variant.pk)


class TestLockVariantLocksCurrentOwner:
    """R46, R49: товар, в который вариант переехал за время ожидания, блокируется до строки варианта."""

    @pytest.mark.django_db(transaction=True)
    def test_variant_moved_before_locking_is_locked_through_its_new_owner(self, monkeypatch):
        from django.db import OperationalError

        variant = make_variant(promo_price=Decimal("800.00"))
        target_id = make_variant().product_id
        gate = Gate()
        errors: list[BaseException] = []
        pause_in_thread(monkeypatch, "locker", gate, "lock_products", after=False)
        locked, done = threading.Event(), threading.Event()
        outcome: dict[str, Any] = {}

        def lock() -> None:
            with transaction.atomic():
                outcome["state"] = promo.lock_variant(variant.pk)
                locked.set()
                assert done.wait(timeout=10)

        locker = start_worker("locker", lock, errors)
        assert gate.reached.wait(timeout=10)  # владелец прочитан (товар A), блокировок ещё нет
        ProductVariant.objects.filter(pk=variant.pk).update(product_id=target_id)  # вариант переехал A → B
        gate.release.set()
        assert locked.wait(timeout=10)
        try:
            with pytest.raises(OperationalError), transaction.atomic():
                Product.objects.select_for_update(no_key=True, nowait=True).get(pk=target_id)
        finally:
            done.set()
        join_all(locker)

        assert errors == []
        assert outcome["state"].product_id == target_id


# --------------------------------------------------------------------------
# Шестой прогон ревью: R53–R60 — запись цены под блокировкой товара, пакетные удаления, сбои команды
# --------------------------------------------------------------------------


class TestUpdateFieldsIterable:
    """R57: `update_fields` может быть любым итерируемым — собственные проверки его не расходуют."""

    def test_generator_update_fields_is_saved(self):
        variant = make_variant()
        variant.stock_quantity = 77

        variant.save(update_fields=(name for name in ["stock_quantity"]))

        assert ProductVariant.objects.get(pk=variant.pk).stock_quantity == 77

    def test_generator_with_activity_still_recomputes_flag(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        assert Product.objects.get(pk=variant.product_id).is_promo is True
        variant.is_active = False

        variant.save(update_fields=(name for name in ["is_active"]))

        assert ProductVariant.objects.get(pk=variant.pk).is_active is False
        assert Product.objects.get(pk=variant.product_id).is_promo is False


class TestPriceSavedTogetherWithActivity:
    """R56: акционная цена, сохраняемая вместе с активностью, тоже повод пересчитать флаг «Акция»."""

    def test_enabling_variant_together_with_promo_price(self):
        variant = make_variant(is_active=False)
        loaded = ProductVariant.objects.get(pk=variant.pk)
        loaded.is_active = True
        loaded.promo_price = Decimal("800.00")

        loaded.save(update_fields=["is_active", "promo_price"])

        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_price_appears_while_variant_stays_active(self):
        variant = make_variant()
        loaded = ProductVariant.objects.get(pk=variant.pk)
        loaded.promo_price = Decimal("800.00")

        loaded.save(update_fields=["is_active", "promo_price"])

        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_price_removed_while_variant_stays_active(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        loaded = ProductVariant.objects.get(pk=variant.pk)
        loaded.promo_price = None

        loaded.save(update_fields=["is_active", "promo_price"])

        assert Product.objects.get(pk=variant.product_id).is_promo is False

    def test_value_change_without_presence_change_recomputes_nothing(self, monkeypatch):
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        recomputed: list[Any] = []
        original = promo.sync_promo_flags

        def counting_sync(*args: Any, **kwargs: Any) -> int:
            recomputed.append(kwargs)
            return original(*args, **kwargs)

        monkeypatch.setattr(promo, "sync_promo_flags", counting_sync)
        loaded = ProductVariant.objects.get(pk=variant.pk)
        loaded.promo_price = Decimal("900.00")

        loaded.save(update_fields=["is_active", "promo_price"])

        assert recomputed == []


class TestImportCommandPartialFailure:
    """R58: цены первого файла уже применены — ошибка второго не оставляет товары без флага «Акция»."""

    def test_flags_follow_prices_applied_before_a_later_file_fails(self, tmp_path):
        import re

        from django.core.management.base import CommandError

        variants = real_offer_variants()
        data_dir = prices_exchange_dir(tmp_path, "partial", price_lists=True)
        first = Path(data_dir) / "prices" / "prices.xml"
        broken = Path(data_dir) / "prices" / "prices_2.xml"
        broken.write_text(
            re.sub(
                "<ЦенаЗаЕдиницу>[^<]*</ЦенаЗаЕдиницу>",
                "<ЦенаЗаЕдиницу>не число</ЦенаЗаЕдиницу>",
                first.read_text(encoding="utf-8"),
                count=1,
            ),
            encoding="utf-8",
        )

        with pytest.raises(CommandError):
            run_prices_import(data_dir)

        plain = variants[OFFER_PLAIN]
        plain.refresh_from_db()
        assert plain.promo_price == Decimal("5592.00")  # цена первого файла применена
        assert Product.objects.get(pk=plain.product_id).is_promo is True


class TestImportAgainstDisableOfLastPromoVariant:
    """R53: запись акционной цены берёт блокировку товара — параллельное отключение варианта флаг не теряет."""

    @pytest.mark.django_db(transaction=True)
    def test_import_waits_for_the_product_and_flag_is_set_by_the_final_recompute(self, monkeypatch):
        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
        promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        last = make_variant(promo_price=Decimal("800.00"))  # единственный акционный вариант товара
        other = ProductVariant.objects.create(
            product=last.product,
            sku="PROMO-R53",
            onec_id=f"{last.product.onec_id}#r53",
            retail_price=Decimal("1200.00"),
            stock_quantity=5,
        )
        promo.sync_promo_flags()
        processor = new_processor()
        gate, sessions = Gate(), Sessions()
        errors: list[BaseException] = []
        imported: dict[str, Any] = {}
        pause_in_thread(monkeypatch, "disabler", gate, "sync_promo_flags", after=True)

        def disable() -> None:
            sessions.record("disabler")
            with transaction.atomic():
                loaded = ProductVariant.objects.get(pk=last.pk)
                loaded.is_active = False
                loaded.save(update_fields=["is_active"])

        def run_import() -> None:
            sessions.record("importer")
            imported["written"] = processor.update_variant_prices(
                price_data(other, **{RETAIL_ID: "1200.00", NOV_ID: "700.00"})
            )

        disabler = start_worker("disabler", disable, errors)
        assert gate.reached.wait(timeout=10)  # вариант отключён, флаг снят, но не зафиксирован
        importer = start_worker("importer", run_import, errors)
        assert sessions.blocked("importer", "disabler")  # запись цены ждёт строку товара
        gate.release.set()
        join_all(disabler, importer)

        assert errors == []
        assert imported == {"written": True}
        promo.sync_promo_flags()  # завершающий пересчёт команды импорта
        assert ProductVariant.objects.get(pk=other.pk).promo_price == Decimal("700.00")
        assert Product.objects.get(pk=last.product_id).is_promo is True

    def test_without_current_promo_import_takes_no_product_lock(self, monkeypatch, processor):
        PriceType.objects.create(onec_id=RETAIL_ID, onec_name="РРЦ", product_field="retail_price")
        variant = make_variant()
        locked: list[int] = []
        original = promo.lock_variant

        def recording_lock(pk: int, **kwargs: Any) -> promo.VariantState | None:
            locked.append(pk)
            return original(pk, **kwargs)

        monkeypatch.setattr(promo, "lock_variant", recording_lock)

        assert processor.update_variant_prices(price_data(variant, **{RETAIL_ID: "1300.00"})) is True

        assert locked == []
        assert ProductVariant.objects.get(pk=variant.pk).retail_price == Decimal("1300.00")


class TestBatchDeleteIsPinned:
    """R55: пакетное удаление не расширяет набор после блокировки владельцев."""

    def test_variant_appearing_after_locking_is_not_deleted(self, monkeypatch):
        first, second = make_variant(color_name="Удалить"), make_variant(color_name="Удалить")
        bystander = make_variant()
        late: dict[str, ProductVariant] = {}
        original = promo.lock_products_stable

        def lock_then_insert(find_ids: Any) -> list[int]:
            result = original(find_ids)
            late["variant"] = ProductVariant.objects.create(
                product=bystander.product,
                sku="PROMO-LATE",
                onec_id=f"{bystander.product.onec_id}#late",
                color_name="Удалить",
                retail_price=Decimal("100.00"),
            )
            return result

        monkeypatch.setattr(promo, "lock_products_stable", lock_then_insert)

        ProductVariant.objects.filter(color_name="Удалить").delete()

        assert not ProductVariant.objects.filter(pk__in=[first.pk, second.pk]).exists()
        assert ProductVariant.objects.filter(pk=late["variant"].pk).exists()


class TestProductBatchDeleteLockOrder:
    """R54: каскадное удаление нескольких товаров берёт блокировки товаров по возрастанию `pk`."""

    @pytest.mark.django_db(transaction=True)
    def test_cascade_delete_of_several_products_and_ordered_recompute_do_not_deadlock(self):
        early = make_variant(promo_price=Decimal("800.00"))
        product_a = early.product_id
        late_b = make_variant(promo_price=Decimal("700.00"))
        product_b = late_b.product_id
        assert product_a < product_b
        # Вариант товара B теперь младше всех: Collector шлёт `pre_delete` по `pk` вариантов,
        # то есть сначала B, затем A — обратно порядку пересчёта (A, затем B)
        ProductVariant.objects.filter(pk=early.pk).delete()
        ProductVariant.objects.create(
            product_id=product_a,
            sku="PROMO-R54",
            onec_id=f"{early.product.onec_id}#r54",
            retail_price=Decimal("1200.00"),
            promo_price=Decimal("900.00"),
        )
        sessions = Sessions()
        errors: list[BaseException] = []
        holding_a, go_b = threading.Event(), threading.Event()

        def hold_a_then_b() -> None:
            """Параллельный пересчёт: берёт товары по возрастанию и держит A, пока ждёт B."""
            sessions.record("holder")
            with transaction.atomic():
                promo.lock_products([product_a])
                holding_a.set()
                assert go_b.wait(timeout=10)
                promo.lock_products([product_b])

        def delete_products() -> None:
            sessions.record("deleter")
            with transaction.atomic():
                Product.objects.filter(pk__in=[product_a, product_b]).delete()

        holder = start_worker("holder", hold_a_then_b, errors)
        assert holding_a.wait(timeout=10)
        deleter = start_worker("deleter", delete_products, errors)
        assert sessions.blocked("deleter", "holder")  # удалению нужен товар A
        go_b.set()
        join_all(holder, deleter)

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()


class TestUnverifiedWholesaleRegularPrice:
    """R59: неверифицированный B2B видит розницу, и `regular_price` — тоже розница, а не оптовая."""

    @pytest.mark.parametrize("role", ["wholesale_level1", "wholesale_level2", "trainer", "federation_rep"])
    @pytest.mark.parametrize("promo_price", [None, Decimal("800.00")])
    def test_regular_price_is_retail_in_list_detail_and_variants(self, role, promo_price):
        variant = make_variant(
            retail_price=Decimal("1200.00"),
            opt1_price=Decimal("700.00"),
            opt2_price=Decimal("650.00"),
            trainer_price=Decimal("600.00"),
            federation_price=Decimal("550.00"),
        )
        if promo_price is not None:
            ProductVariant.objects.filter(pk=variant.pk).update(promo_price=promo_price)
        client = APIClient()
        client.force_authenticate(user=make_user(role, verified=False))

        listing = client.get(reverse("products:product-list")).json()
        item = next(row for row in listing["results"] if row["id"] == variant.product_id)
        detail = client.get(reverse("products:product-detail", kwargs={"slug": variant.product.slug})).json()

        expected_current = "800.00" if promo_price is not None else "1200.00"
        for data in (item, detail, detail["variants"][0]):
            assert data["regular_price"] == "1200.00"
            assert data["current_price"] == expected_current


class TestDeletePriceTypesRollsBack:
    """R60: сбой сброса акционных цен откатывает и удаление вида цен, и смену текущей акции."""

    model_admin = PriceTypeAdmin(PriceType, AdminSite())

    @staticmethod
    def failing_reset() -> None:
        raise RuntimeError("сбой сброса")

    def test_delete_queryset_failure_keeps_price_type_prices_and_flags(self, monkeypatch):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        monkeypatch.setattr(promo, "_reset_promo_state", self.failing_reset)

        with pytest.raises(RuntimeError, match="сбой сброса"):
            self.model_admin.delete_queryset(admin_request(), PriceType.objects.filter(pk=current.pk))

        assert PriceType.objects.filter(pk=current.pk).exists()
        assert ProductVariant.objects.get(pk=variant.pk).promo_price == Decimal("800.00")
        assert Product.objects.get(pk=variant.product_id).is_promo is True

    def test_delete_model_failure_keeps_price_type(self, monkeypatch):
        current = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=True)
        current_pk = current.pk  # `delete()` обнуляет pk у экземпляра
        make_variant(promo_price=Decimal("800.00"))
        monkeypatch.setattr(promo, "_reset_promo_state", self.failing_reset)

        with pytest.raises(RuntimeError, match="сбой сброса"):
            self.model_admin.delete_model(admin_request(), current)

        assert PriceType.objects.filter(pk=current_pk).exists()

    def test_switch_failure_keeps_previous_current_promo(self, monkeypatch):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        november = promo_type(NOV_ID, "АКЦИЯ НОЯБРЬ-26", active=False)
        variant = make_variant(promo_price=Decimal("800.00"))
        monkeypatch.setattr(promo, "_reset_promo_state", self.failing_reset)
        november.is_active = True

        with pytest.raises(RuntimeError, match="сбой сброса"):
            self.model_admin.save_model(admin_request(), november, form=None, change=True)

        assert active_promo_ids() == [OCT_ID]
        assert ProductVariant.objects.get(pk=variant.pk).promo_price == Decimal("800.00")


# --------------------------------------------------------------------------
# Восьмой прогон ревью: R65–R67 — пакетное удаление: блокировки запроса, кэш, каскад от родителей
# --------------------------------------------------------------------------


class TestBatchDeleteIgnoresInheritedRowLocks:
    """R65: `select_for_update()` исходного запроса не должен блокировать строки раньше товаров."""

    @pytest.mark.parametrize("model", [ProductVariant, Product, Brand, Category])
    def test_collecting_pks_takes_no_row_locks(self, model):
        from django.db import connection

        make_variant()
        with CaptureQueriesContext(connection) as queries:
            model.objects.select_for_update().all().delete()

        first_select = next(q["sql"] for q in queries if q["sql"].lstrip().upper().startswith("SELECT"))
        assert " FOR " not in first_select.upper()

    @pytest.mark.django_db(transaction=True)
    def test_select_for_update_delete_does_not_lock_variant_before_product(self):
        variant = make_variant(promo_price=Decimal("800.00"))
        product_pk = variant.product_id
        sessions = Sessions()
        errors: list[BaseException] = []
        holding_product, go_variant = threading.Event(), threading.Event()

        def hold_product_then_variant() -> None:
            """Другая транзакция идёт в общем порядке: сначала товар, затем строка его варианта."""
            sessions.record("holder")
            with transaction.atomic():
                promo.lock_products([product_pk])
                holding_product.set()
                assert go_variant.wait(timeout=10)
                list(ProductVariant.objects.select_for_update().filter(pk=variant.pk))

        def delete_locked() -> None:
            sessions.record("deleter")
            with transaction.atomic():
                ProductVariant.objects.select_for_update().filter(pk=variant.pk).delete()

        holder = start_worker("holder", hold_product_then_variant, errors)
        assert holding_product.wait(timeout=10)
        deleter = start_worker("deleter", delete_locked, errors)
        assert sessions.blocked("deleter", "holder")  # удалению нужен товар, который держит первая транзакция
        go_variant.set()
        join_all(holder, deleter)

        assert errors == []
        assert not ProductVariant.objects.filter(pk=variant.pk).exists()


class TestBatchDeleteClearsResultCache:
    """R66: вычисленный QuerySet после пакетного удаления не отдаёт удалённые объекты из кэша."""

    @pytest.mark.parametrize("model", [ProductVariant, Product, Brand, Category])
    def test_evaluated_queryset_is_refreshed_after_delete(self, model):
        make_variant()
        queryset = model.objects.all()
        assert len(queryset) >= 1  # результат вычислен и закэширован

        queryset.delete()

        assert list(queryset) == []


def two_products_with_reversed_variant_order() -> tuple[int, int]:
    """
    Два товара с акционными вариантами: порядок `pk` вариантов обратен порядку `pk` товаров.

    Collector шлёт `pre_delete` вариантов по их `pk`, поэтому каскад без предварительной
    блокировки берёт сначала товар B, затем A — обратно пересчёту и переносам (A, затем B).
    """
    early = make_variant(promo_price=Decimal("800.00"))
    product_a = early.product_id
    late = make_variant(promo_price=Decimal("700.00"))
    product_b = late.product_id
    assert product_a < product_b
    ProductVariant.objects.filter(pk=early.pk).delete()
    ProductVariant.objects.create(
        product_id=product_a,
        sku="PROMO-R67",
        onec_id=f"{early.product.onec_id}#r67",
        retail_price=Decimal("1200.00"),
        promo_price=Decimal("900.00"),
    )
    return product_a, product_b


def cascade_against_ordered_holder(delete: Any, product_a: int, product_b: int) -> list[BaseException]:
    """
    Запускает `delete` против транзакции, которая берёт товары по возрастанию (A, затем B).

    Та держит A, пока каскад не встанет на ожидание, и только потом идёт за B. Без блокировки
    товаров по возрастанию до каскада он держит B и ждёт A — взаимоблокировка (`40P01`).
    """
    sessions = Sessions()
    errors: list[BaseException] = []
    holding_a, go_b = threading.Event(), threading.Event()

    def hold_a_then_b() -> None:
        sessions.record("holder")
        with transaction.atomic():
            promo.lock_products([product_a])
            holding_a.set()
            assert go_b.wait(timeout=10)
            promo.lock_products([product_b])

    def cascade() -> None:
        sessions.record("deleter")
        with transaction.atomic():
            delete()

    holder = start_worker("holder", hold_a_then_b, errors)
    assert holding_a.wait(timeout=10)
    deleter = start_worker("deleter", cascade, errors)
    assert sessions.blocked("deleter", "holder")  # каскаду нужен товар A
    go_b.set()
    join_all(holder, deleter)
    return errors


class TestCascadeFromParentsLockOrder:
    """R67: удаление категории или бренда берёт блокировки товаров по возрастанию `pk` до каскада."""

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("how", ["category-instance", "category-queryset", "brand-instance", "brand-queryset"])
    def test_cascade_from_parent_and_ordered_recompute_do_not_deadlock(self, how):
        product_a, product_b = two_products_with_reversed_variant_order()
        category = Category.objects.get(slug="promo-category")
        brand = Brand.objects.get(slug="promo-brand")
        deleters = {
            "category-instance": lambda: Category.objects.get(pk=category.pk).delete(),
            "category-queryset": lambda: Category.objects.filter(pk=category.pk).delete(),
            "brand-instance": lambda: Brand.objects.get(pk=brand.pk).delete(),
            "brand-queryset": lambda: Brand.objects.filter(pk=brand.pk).delete(),
        }

        errors = cascade_against_ordered_holder(deleters[how], product_a, product_b)

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()

    @pytest.mark.django_db(transaction=True)
    def test_cascade_through_child_categories_locks_their_products(self):
        product_a, product_b = two_products_with_reversed_variant_order()
        root = Category.objects.get(slug="promo-category")
        child = Category.objects.create(name="Дочерняя категория акции", slug="promo-child-category", parent=root)
        Product.objects.filter(pk=product_b).update(category=child)

        errors = cascade_against_ordered_holder(lambda: Category.objects.get(pk=root.pk).delete(), product_a, product_b)

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()
        assert not Category.objects.filter(pk__in=[root.pk, child.pk]).exists()


# --------------------------------------------------------------------------
# Десятый прогон ревью: R69 — порядок блокировок у составной операции
# --------------------------------------------------------------------------


def product_admin_request(*variant_pks: int) -> Any:
    """POST формы товара: management-форма инлайна вариантов и скрытые `id` его строк."""
    prefix = ProductAdmin.VARIANTS_FORMSET_PREFIX
    data = {f"{prefix}-TOTAL_FORMS": str(len(variant_pks)), f"{prefix}-INITIAL_FORMS": str(len(variant_pks))}
    for index, pk in enumerate(variant_pks):
        data[f"{prefix}-{index}-id"] = str(pk)
    return admin_request(data)


def two_variants_of_ascending_products() -> tuple[ProductVariant, ProductVariant]:
    """Два акционных варианта в разных товарах: `pk` первого товара (A) меньше `pk` второго (B)."""
    first = make_variant(promo_price=Decimal("800.00"))
    second = make_variant(promo_price=Decimal("700.00"))
    assert first.product_id < second.product_id
    promo.sync_promo_flags()
    return first, second


def disable_variant(pk: int) -> None:
    variant = ProductVariant.objects.get(pk=pk)
    variant.is_active = False
    variant.save(update_fields=["is_active"])


def composite_against_recompute(edit: Any, product_a: int, product_b: int) -> list[BaseException]:
    """
    Составная операция `edit` против пересчёта флагов, который берёт товары по возрастанию (A, затем B).

    `edit(parent_locked, proceed)` открывает транзакцию, пишет сторону товара B, сообщает `parent_locked`,
    ждёт `proceed` и возвращается к стороне товара A. Пересчёт стартует после `parent_locked` и встаёт на
    блокировку операции. Если операция заняла A заранее, пересчёт ждёт её целиком; иначе он держит A и ждёт B,
    а операция ждёт A, — взаимоблокировка (`40P01`).
    """
    from django.db import connection

    sessions = Sessions()
    errors: list[BaseException] = []
    parent_locked, proceed = threading.Event(), threading.Event()

    def bounded() -> None:
        with connection.cursor() as cursor:
            cursor.execute("SET lock_timeout = '12s'")

    def run_edit() -> None:
        sessions.record("editor")
        bounded()
        edit(parent_locked, proceed)

    def recompute() -> None:
        sessions.record("recompute")
        bounded()
        promo.sync_promo_flags(product_ids=[product_a, product_b])

    editor = start_worker("editor", run_edit, errors)
    assert parent_locked.wait(timeout=10)
    recalculation = start_worker("recompute", recompute, errors)
    try:
        assert sessions.blocked("recompute", "editor")  # пересчёту нужен товар, который держит операция
    finally:
        proceed.set()
        join_all(editor, recalculation)
    return errors


class TestCompositeOperationLockOrder:
    """R69: порядок «по возрастанию pk» действует на составную операцию целиком, а не на каждое её сохранение."""

    @pytest.mark.django_db(transaction=True)
    def test_variant_saves_in_descending_order_after_prelock_do_not_deadlock(self):
        first, second = two_variants_of_ascending_products()

        def edit(parent_locked: threading.Event, proceed: threading.Event) -> None:
            with transaction.atomic():
                promo.lock_operation(variant_pks=[first.pk, second.pk])
                disable_variant(second.pk)  # товар B
                parent_locked.set()
                assert proceed.wait(timeout=10)
                disable_variant(first.pk)  # товар A

        errors = composite_against_recompute(edit, first.product_id, second.product_id)

        assert errors == []
        assert not ProductVariant.objects.filter(pk__in=[first.pk, second.pk], is_active=True).exists()
        assert not Product.objects.filter(pk__in=[first.product_id, second.product_id], is_promo=True).exists()

    @pytest.mark.django_db(transaction=True)
    def test_product_admin_save_locks_current_owners_of_posted_inline_variants(self):
        """Инлайн после загрузки формы перенесли из B в A: сохранение товара B занимает A до первой записи."""
        first, second = two_variants_of_ascending_products()
        product_a, product_b = first.product_id, second.product_id
        stale_inline = ProductVariant.objects.get(pk=second.pk)
        moved = ProductVariant.objects.get(pk=second.pk)
        moved.product_id = product_a
        moved.save(update_fields=["product"])
        request = product_admin_request(second.pk)

        def edit(parent_locked: threading.Event, proceed: threading.Event) -> None:
            with transaction.atomic():
                parent = Product.objects.get(pk=product_b)
                parent.name += " (правка)"
                ProductAdmin(Product, AdminSite()).save_model(request, parent, form=None, change=True)
                parent_locked.set()
                assert proceed.wait(timeout=10)
                # Инлайн сохраняется после товара устаревшим экземпляром: он возвращает вариант в товар B
                stale_inline.is_active = False
                stale_inline.save()

        errors = composite_against_recompute(edit, product_a, product_b)

        assert errors == []
        saved = ProductVariant.objects.get(pk=second.pk)
        assert (saved.product_id, saved.is_active) == (product_b, False)
        assert Product.objects.get(pk=product_b).name.endswith("(правка)")
        assert Product.objects.get(pk=product_a).is_promo is True  # первый вариант A активен
        assert Product.objects.get(pk=product_b).is_promo is False  # единственный вариант B отключён

    @pytest.mark.parametrize(
        "management",
        [
            {"variants-TOTAL_FORMS": "abc"},
            {"variants-TOTAL_FORMS": "2", "variants-0-id": "not-a-number", "variants-1-id": ""},
            {"variants-TOTAL_FORMS": "999999"},
            {},
        ],
    )
    def test_product_admin_save_ignores_malformed_inline_data(self, management):
        variant = make_variant(promo_price=Decimal("800.00"))
        parent = Product.objects.get(pk=variant.product_id)
        parent.name = "Правка"

        ProductAdmin(Product, AdminSite()).save_model(admin_request(management), parent, form=None, change=True)

        assert Product.objects.get(pk=parent.pk).name == "Правка"

    def test_variants_formset_prefix_matches_the_real_inline(self):
        """POST читается по этому префиксу: расхождение с настоящим formset молча отключило бы предблокировку."""
        formset = ProductVariantInline(Product, AdminSite()).get_formset(admin_request())

        assert formset.get_default_prefix() == ProductAdmin.VARIANTS_FORMSET_PREFIX

    def test_lock_operation_returns_locked_owners_in_ascending_order(self):
        first, second = two_variants_of_ascending_products()
        extra = make_variant().product_id

        locked = promo.lock_operation(product_ids=[extra], variant_pks=[second.pk, first.pk])

        assert locked == sorted({first.product_id, second.product_id, extra})
        assert promo.lock_operation() == []

    @pytest.mark.django_db(transaction=True)
    def test_lock_operation_outside_transaction_raises(self):
        """Вне транзакции блокировка снялась бы сразу и ничего не удерживала."""
        variant = make_variant()

        with pytest.raises(RuntimeError):
            promo.lock_operation(variant_pks=[variant.pk])


# --------------------------------------------------------------------------
# Десятый прогон ревью: R70 — настоящий POST добавления вида цен
# --------------------------------------------------------------------------


class TestPriceTypeAdminAddPost:
    """R70: добавление вида цен (`change=False`) идёт через сервис так же, как правка, а не мимо него."""

    @staticmethod
    def add_data(**overrides: str) -> dict[str, str]:
        return {
            "onec_id": NOV_ID,
            "onec_name": "АКЦИЯ НОЯБРЬ-26",
            "product_field": "promo_price",
            "user_role": "",
            "is_active": "on",
            **overrides,
        }

    def test_adding_active_promo_switches_current_and_resets_prices(self, client):
        october = promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        assert Product.objects.get(pk=variant.product_id).is_promo is True
        staff_login(client)

        response = client.post(reverse("admin:products_pricetype_add"), self.add_data())

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert active_promo_ids() == [NOV_ID]
        assert PriceType.objects.get(pk=october.pk).is_active is False
        variant.refresh_from_db()
        assert variant.promo_price is None
        assert Product.objects.get(pk=variant.product_id).is_promo is False
        assert PriceTypeAdmin.PROMO_RESET_MESSAGE in [str(m) for m in get_messages(response.wsgi_request)]

    def test_adding_inactive_promo_keeps_current_and_prices(self, client):
        promo_type(OCT_ID, "АКЦИЯ ОКТЯБРЬ-26", active=True)
        variant = make_variant(promo_price=Decimal("800.00"))
        promo.sync_promo_flags()
        staff_login(client)
        data = self.add_data()
        del data["is_active"]

        response = client.post(reverse("admin:products_pricetype_add"), data)

        assert response.status_code == 302, getattr(response, "context_data", None)
        assert active_promo_ids() == [OCT_ID]
        assert PriceType.objects.get(onec_id=NOV_ID).is_active is False
        variant.refresh_from_db()
        assert variant.promo_price == Decimal("800.00")
        assert Product.objects.get(pk=variant.product_id).is_promo is True
        assert PriceTypeAdmin.PROMO_RESET_MESSAGE not in [str(m) for m in get_messages(response.wsgi_request)]


# --------------------------------------------------------------------------
# Десятый прогон ревью: R71 — каскад от категории блокирует товары потомков
# --------------------------------------------------------------------------


class TestCategoryCascadeLocksDescendantProducts:
    """
    R71: в корне товаров нет, оба товара — в потомках, порядок `pk` вариантов обратен порядку `pk` товаров.

    Товар в корне маскировал потерю предварительной блокировки потомков: корень блокировал A, и встречная
    транзакция получала B без ожидания. Здесь без блокировки поддерева не заблокирован ни один товар.
    """

    @staticmethod
    def tree_with_products_only_in_descendants() -> tuple[int, int, Category]:
        product_a, product_b = two_products_with_reversed_variant_order()
        root = Category.objects.get(slug="promo-category")
        child_a = Category.objects.create(name="Потомок A", slug="promo-child-a", parent=root)
        child_b = Category.objects.create(name="Потомок B", slug="promo-child-b", parent=root)
        grandchild_b = Category.objects.create(name="Внук B", slug="promo-grandchild-b", parent=child_b)
        Product.objects.filter(pk=product_a).update(category=child_a)
        Product.objects.filter(pk=product_b).update(category=grandchild_b)
        assert not Product.objects.filter(category=root).exists()
        return product_a, product_b, root

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("how", ["instance", "queryset"])
    def test_cascade_from_root_without_products_and_ordered_recompute_do_not_deadlock(self, how):
        product_a, product_b, root = self.tree_with_products_only_in_descendants()
        deleters = {
            "instance": lambda: Category.objects.get(pk=root.pk).delete(),
            "queryset": lambda: Category.objects.filter(pk=root.pk).delete(),
        }

        errors = cascade_against_ordered_holder(deleters[how], product_a, product_b)

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()
        assert not Category.objects.filter(slug__startswith="promo-").exists()


# --------------------------------------------------------------------------
# Двенадцатый прогон ревью: R74 — предел строк инлайна вариантов
# --------------------------------------------------------------------------


def variants_formset_class() -> Any:
    """Настоящий formset инлайна вариантов: именно он решает, сколько строк POST сохранится."""
    return ProductVariantInline(Product, AdminSite()).get_formset(admin_request())


class TestPostedVariantRowsMatchTheRealFormset:
    """
    R74: инлайн без `max_num` создаёт до `absolute_max` форм (2000), а не до `DEFAULT_MAX_NUM` (1000).

    Варианты из строк 1000–1999 сохранятся, поэтому их владельцы обязаны попасть в предблокировку.
    """

    @staticmethod
    def posted(rows: dict[int, int], total: int) -> Any:
        prefix = ProductAdmin.VARIANTS_FORMSET_PREFIX
        data = {f"{prefix}-TOTAL_FORMS": str(total), f"{prefix}-INITIAL_FORMS": "0"}
        data.update({f"{prefix}-{index}-id": str(pk) for index, pk in rows.items()})
        return admin_request(data)

    def test_limit_equals_absolute_max_of_the_real_formset(self):
        assert ProductAdmin.VARIANTS_FORMSET_MAX_ROWS == variants_formset_class().absolute_max

    def test_every_row_the_real_formset_instantiates_is_read(self):
        formset_class = variants_formset_class()
        total = formset_class.absolute_max + 500
        accepted = formset_class(data=self.posted({}, total).POST, prefix=ProductAdmin.VARIANTS_FORMSET_PREFIX)
        last = accepted.total_form_count() - 1
        assert last >= 1000  # случай ревью: строки за прежней границей тоже сохраняются
        request = self.posted({0: 101, 999: 102, 1000: 103, last: 104, last + 1: 105}, total)

        pks = ProductAdmin(Product, AdminSite())._posted_variant_pks(request)

        assert pks == [101, 102, 103, 104]  # строку last + 1 formset уже не создаст

    def test_product_save_locks_the_owner_of_row_1000(self, monkeypatch):
        variant = make_variant(promo_price=Decimal("800.00"))
        parent = Product.objects.get(pk=make_variant().product_id)
        calls: list[list[int]] = []
        original = promo.lock_operation

        def spy(**kwargs: Any) -> list[int]:
            calls.append(list(kwargs["variant_pks"]))
            return original(**kwargs)

        monkeypatch.setattr(promo, "lock_operation", spy)

        ProductAdmin(Product, AdminSite()).save_model(
            self.posted({1000: variant.pk}, total=1001), parent, form=None, change=True
        )

        assert calls == [[variant.pk]]

    def test_ids_are_read_the_way_the_real_formset_binds_rows(self):
        """
        R78: formset разбирает `id` через `to_python` (`int()`), а не по `isdigit()`.

        `int()` принимает пробелы по краям, знак `+` и подчёркивания между цифрами, поэтому такие строки
        привязываются к вариантам. Если предблокировка их пропустит, владелец варианта останется без неё.
        """
        parent = make_variant().product
        bound_pks = [9_000_001, 9_000_002, 9_000_003, 9_000_030, 9_000_004]
        for pk in bound_pks:
            ProductVariant.objects.create(
                pk=pk,
                product=parent,
                sku=f"PROMO-R78-{pk}",
                onec_id=f"{parent.onec_id}#r78-{pk}",
                retail_price=Decimal("1200.00"),
            )
        raw_ids = ["9000001", " 9000002", "+9000003", "9_000_03_0", "9000004 ", "abc", ""]
        prefix = ProductAdmin.VARIANTS_FORMSET_PREFIX
        data = {f"{prefix}-TOTAL_FORMS": str(len(raw_ids)), f"{prefix}-INITIAL_FORMS": str(len(raw_ids))}
        data.update({f"{prefix}-{index}-id": raw for index, raw in enumerate(raw_ids)})
        request = admin_request(data)
        formset = variants_formset_class()(data=request.POST, instance=parent, prefix=prefix)
        bound = [form.instance.pk for form in formset.forms if form.instance.pk]
        assert bound == bound_pks  # строки с пробелами, знаком и подчёркиванием formset действительно привязывает

        pks = ProductAdmin(Product, AdminSite())._posted_variant_pks(request)

        assert pks == bound


# --------------------------------------------------------------------------
# Двенадцатый прогон ревью: R75 — владельцы перечитываются после ожидания блокировки
# --------------------------------------------------------------------------


class TestLockOperationRereadsOwnersAfterWaiting:
    """
    R75: вариант переносят другим соединением, пока `lock_operation` стоит на блокировке товара.

    Если владельцев посчитать один раз, операция удержит только прежний товар (B), а новый (A) останется
    без предблокировки: сохранение устаревшего инлайна встретится с пересчётом (A, затем B) во взаимоблокировке.
    """

    @pytest.mark.django_db(transaction=True)
    def test_variant_moved_during_the_wait_is_locked_in_its_new_product(self):
        from django.db import DatabaseError, connection

        first, second = two_variants_of_ascending_products()
        product_a, product_b = first.product_id, second.product_id
        stale_inline = ProductVariant.objects.get(pk=second.pk)
        request = product_admin_request(second.pk)
        sessions = Sessions()
        errors: list[BaseException] = []
        mover_holding, release_mover = threading.Event(), threading.Event()
        editor_locked, proceed = threading.Event(), threading.Event()

        def bounded() -> None:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '12s'")

        def move() -> None:
            sessions.record("mover")
            bounded()
            with transaction.atomic():
                promo.lock_variant(second.pk, extra_product_ids=[product_a])  # товары A и B
                mover_holding.set()
                assert release_mover.wait(timeout=10)
                moved = ProductVariant.objects.get(pk=second.pk)
                moved.product_id = product_a
                moved.save(update_fields=["product"])

        def edit() -> None:
            sessions.record("editor")
            bounded()
            with transaction.atomic():
                parent = Product.objects.get(pk=product_b)
                parent.name += " (правка)"
                # Здесь вариант ещё лежит в B, и `lock_operation` встаёт на блокировку B, которую держит перенос
                ProductAdmin(Product, AdminSite()).save_model(request, parent, form=None, change=True)
                editor_locked.set()
                assert proceed.wait(timeout=10)
                # Инлайн сохраняется устаревшим экземпляром: он возвращает вариант в товар B
                stale_inline.is_active = False
                stale_inline.save()

        def recompute() -> None:
            sessions.record("recompute")
            bounded()
            promo.sync_promo_flags(product_ids=[product_a, product_b])

        mover = start_worker("mover", move, errors)
        assert mover_holding.wait(timeout=10)
        editor = start_worker("editor", edit, errors)
        recalculation: threading.Thread | None = None
        try:
            assert sessions.blocked("editor", "mover")  # предблокировка ждёт товар B
            release_mover.set()
            assert editor_locked.wait(timeout=10)
            # Вариант теперь в A: операция обязана держать и A, и B. NOWAIT не ждёт чужую блокировку
            for held in (product_a, product_b):
                with pytest.raises(DatabaseError), transaction.atomic():
                    list(Product.objects.select_for_update(no_key=True, nowait=True).filter(pk=held))
            recalculation = start_worker("recompute", recompute, errors)
            assert sessions.blocked("recompute", "editor")  # пересчёт ждёт операцию целиком
        finally:
            release_mover.set()
            proceed.set()
            join_all(mover, editor, *([recalculation] if recalculation else []))

        assert errors == []
        saved = ProductVariant.objects.get(pk=second.pk)
        assert (saved.product_id, saved.is_active) == (product_b, False)
        assert Product.objects.get(pk=product_b).name.endswith("(правка)")
        assert Product.objects.get(pk=product_a).is_promo is True  # первый вариант A активен
        assert Product.objects.get(pk=product_b).is_promo is False  # единственный вариант B отключён


# --------------------------------------------------------------------------
# Двенадцатый прогон ревью: R76 — команда cleanup_root_categories удаляет несколько корней за раз
# --------------------------------------------------------------------------


class TestCleanupRootCategoriesLockOrder:
    """
    R76: команда удаляет якорную категорию и посторонние корни в одной транзакции.

    Каждый `Category.delete()` берёт товары только своего поддерева, поэтому без общего набора товар B
    (больший `pk`, в якорной) удерживается, а товар A (меньший `pk`, в следующем корне) берётся позже —
    против пересчёта флагов (A, затем B) это взаимоблокировка.
    """

    @pytest.mark.django_db(transaction=True)
    def test_anchor_then_other_root_and_ordered_recompute_do_not_deadlock(self):
        from io import StringIO

        from django.core.management import call_command

        product_a, product_b = two_products_with_reversed_variant_order()
        anchor = Category.objects.create(name="Якорь R76", slug="promo-anchor-r76")
        other_root = Category.objects.create(name="Посторонний корень R76", slug="promo-other-root-r76")
        Product.objects.filter(pk=product_b).update(category=anchor)  # больший pk: удаляется первым, с якорной
        Product.objects.filter(pk=product_a).update(category=other_root)  # меньший pk: удаляется позже, с корнем

        def run_command() -> None:
            call_command("cleanup_root_categories", execute=True, root_name=anchor.name, stdout=StringIO())

        errors = cascade_against_ordered_holder(run_command, product_a, product_b)

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()
        assert not Category.objects.filter(pk__in=[anchor.pk, other_root.pk]).exists()


# --------------------------------------------------------------------------
# Тринадцатый прогон ревью: R77 — каскад бренда и категории перечитывает товары после ожидания
# --------------------------------------------------------------------------


class TestCascadeRereadsProductsAfterWaiting:
    """
    R77: товар переносят в удаляемый бренд или поддерево, пока каскад стоит на блокировке другого товара.

    Если набор товаров собрать один раз (`lock_products` вместо `lock_products_stable`), каскад удержит только
    прежний товар (B), а перенесённый (A) возьмёт позже, в порядке Collector: против пересчёта (A, затем B)
    это взаимоблокировка. Тест останавливает каскад сразу после предблокировки и требует, чтобы удержаны были
    оба товара; затем пересчёт (A, затем B) встаёт на каскад и всё завершается без `40P01`.
    """

    @staticmethod
    def parent_holding_only_product_b(kind: str, product_a: int) -> tuple[Any, Any]:
        """
        Удаляемый родитель, в котором лежит только товар B, и функция, которая переносит в него товар A.

        Товар A стоит в стороннем бренде или категории. Для категории переезд идёт в дочернюю: в поддерево.
        """
        if kind == "brand":
            brand = Brand.objects.get(slug="promo-brand")
            other_brand = Brand.objects.create(name="Сторонний бренд R77", slug="promo-elsewhere-brand-r77")
            Product.objects.filter(pk=product_a).update(brand=other_brand)
            return brand, lambda: Product.objects.filter(pk=product_a).update(brand=brand)
        category = Category.objects.get(slug="promo-category")
        other_category = Category.objects.create(name="Сторонняя категория R77", slug="promo-elsewhere-category-r77")
        child = Category.objects.create(name="Потомок R77", slug="promo-child-category-r77", parent=category)
        Product.objects.filter(pk=product_a).update(category=other_category)
        return category, lambda: Product.objects.filter(pk=product_a).update(category=child)

    @pytest.mark.django_db(transaction=True)
    @pytest.mark.parametrize("kind", ["brand", "category"])
    @pytest.mark.parametrize("how", ["instance", "queryset"])
    def test_product_moved_during_the_wait_is_locked_before_the_cascade(self, monkeypatch, kind, how):
        from django.db import DatabaseError, connection

        from apps.products import models as product_models

        product_a, product_b = two_products_with_reversed_variant_order()
        parent, relocate = self.parent_holding_only_product_b(kind, product_a)
        model = type(parent)
        sessions = Sessions()
        errors: list[BaseException] = []
        mover_holding, release_mover = threading.Event(), threading.Event()
        prelocked, proceed = threading.Event(), threading.Event()

        # Каскад останавливается сразу после предблокировки: до Collector, который сам берёт товары
        lock_name = f"_lock_{kind}_products"
        original = getattr(product_models, lock_name)

        def pause_after_prelock(pks: list[int]) -> None:
            original(pks)
            prelocked.set()
            assert proceed.wait(timeout=10)

        monkeypatch.setattr(product_models, lock_name, pause_after_prelock)

        def bounded() -> None:
            with connection.cursor() as cursor:
                cursor.execute("SET lock_timeout = '12s'")

        def move() -> None:
            sessions.record("mover")
            bounded()
            with transaction.atomic():
                promo.lock_products([product_a, product_b])
                mover_holding.set()
                assert release_mover.wait(timeout=10)
                relocate()

        def cascade() -> None:
            sessions.record("deleter")
            bounded()
            with transaction.atomic():
                target = model.objects.get(pk=parent.pk) if how == "instance" else model.objects.filter(pk=parent.pk)
                target.delete()

        def recompute() -> None:
            sessions.record("recompute")
            bounded()
            promo.sync_promo_flags(product_ids=[product_a, product_b])

        mover = start_worker("mover", move, errors)
        assert mover_holding.wait(timeout=10)
        deleter = start_worker("deleter", cascade, errors)
        recalculation: threading.Thread | None = None
        try:
            assert sessions.blocked("deleter", "mover")  # предблокировка ждёт товар B: в родителе он один
            release_mover.set()
            assert prelocked.wait(timeout=10)
            # Товар A теперь в родителе: каскад обязан держать и A, и B. NOWAIT не ждёт чужую блокировку
            for held in (product_a, product_b):
                with pytest.raises(DatabaseError), transaction.atomic():
                    list(Product.objects.select_for_update(no_key=True, nowait=True).filter(pk=held))
            recalculation = start_worker("recompute", recompute, errors)
            assert sessions.blocked("recompute", "deleter")  # пересчёт ждёт каскад целиком
        finally:
            release_mover.set()
            proceed.set()
            join_all(mover, deleter, *([recalculation] if recalculation else []))

        assert errors == []
        assert not Product.objects.filter(pk__in=[product_a, product_b]).exists()
        assert not model.objects.filter(pk=parent.pk).exists()

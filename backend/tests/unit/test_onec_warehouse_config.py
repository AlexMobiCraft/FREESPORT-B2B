"""
Склады 1С в боевых настройках `ONEC_EXCHANGE`.

Тесты идут по настоящим `WAREHOUSE_NAME_BY_ID` / `WAREHOUSE_RULES`, без override:
они ловят склад, который заведён в одном словаре и забыт в другом. Такой склад
приходит в rests.xml, вариант получает его имя, но организацию и НДС сайт
определяет уже по запасным правилам (`ORGANIZATION_BY_VAT` / `DEFAULT_*`).
"""

from decimal import Decimal

import pytest
from django.conf import settings

from apps.orders.services.order_export import OrderExportService
from apps.products.services.variant_import import VariantImportProcessor

ANGAR_COSMO_ID = "7aec9712-7825-11f0-8fa2-fa163ea88911"
ANGAR_COSMO_NAME = "№1 АНГАР Cosmo"


def _processor() -> VariantImportProcessor:
    # Методы разрешения склада читают только settings — сессия импорта не нужна.
    return object.__new__(VariantImportProcessor)


@pytest.mark.unit
class TestOnecWarehouseConfig:
    def test_every_warehouse_id_has_rule(self):
        cfg = settings.ONEC_EXCHANGE
        missing = set(cfg["WAREHOUSE_NAME_BY_ID"].values()) - set(cfg["WAREHOUSE_RULES"])
        assert not missing, f"Склады без правила организации: {missing}"

    def test_every_rule_has_warehouse_id(self):
        cfg = settings.ONEC_EXCHANGE
        missing = set(cfg["WAREHOUSE_RULES"]) - set(cfg["WAREHOUSE_NAME_BY_ID"].values())
        assert not missing, f"Правила для складов без GUID из 1С: {missing}"

    def test_angar_cosmo_resolves_to_semeryuk_with_item_vat(self):
        processor = _processor()

        name = processor._resolve_warehouse_name(ANGAR_COSMO_ID)

        assert name == ANGAR_COSMO_NAME
        # Как у «1 СДВ склад»: фиксированной ставки нет, НДС берётся с товара.
        assert processor._get_vat_rate_by_warehouse_name(name) is None
        assert OrderExportService()._get_org_and_warehouse(Decimal("22"), name) == (
            "ИП Семерюк Д.В.",
            ANGAR_COSMO_NAME,
        )

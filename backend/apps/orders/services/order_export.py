"""
Сервис экспорта заказов в формате CommerceML 3.1 для интеграции с 1С.

Этот модуль реализует Service Layer паттерн для генерации XML заказов.
"""

from __future__ import annotations

import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterator, Union

from django.conf import settings
from django.db.models import QuerySet
from django.utils import timezone

from apps.orders.models import Order, OrderItem
from apps.products.models import ProductVariant
from apps.users.models import User

logger = logging.getLogger(__name__)


class OrderExportService:
    """
    Сервис генерации XML заказов в формате CommerceML 3.1 для экспорта в 1С.

    Реализует Service Layer паттерн — вся бизнес-логика генерации XML
    инкапсулирована в этом классе.
    """

    DEFAULT_SCHEMA_VERSION = "3.1"

    def __init__(self, schema_version: str | None = None):
        if schema_version:
            self._schema_version = schema_version
        else:
            exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
            self._schema_version = str(exchange_cfg.get("COMMERCEML_VERSION", self.DEFAULT_SCHEMA_VERSION))

    @property
    def SCHEMA_VERSION(self) -> str:
        """Read CommerceML version from init or settings."""
        return self._schema_version

    CURRENCY = "RUB"
    EXCHANGE_RATE = "1"
    OPERATION_TYPE = "Заказ товара"
    ROLE = "Продавец"
    DEFAULT_UNIT_CODE = "796"
    DEFAULT_UNIT_NAME_FULL = "Штука"
    DEFAULT_UNIT_NAME_INTL = "PCE"
    DEFAULT_UNIT_NAME_SHORT = "шт"

    @property
    def _unit_defaults(self) -> dict:
        """Read default unit of measurement from settings, falling back to hardcoded defaults."""
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        unit_cfg = exchange_cfg.get("DEFAULT_UNIT", {})
        return {
            "code": unit_cfg.get("CODE", self.DEFAULT_UNIT_CODE),
            "name_full": unit_cfg.get("NAME_FULL", self.DEFAULT_UNIT_NAME_FULL),
            "name_intl": unit_cfg.get("NAME_INTL", self.DEFAULT_UNIT_NAME_INTL),
            "name_short": unit_cfg.get("NAME_SHORT", self.DEFAULT_UNIT_NAME_SHORT),
        }

    def generate_xml(self, orders: "QuerySet[Order]") -> str:
        """
        Generate CommerceML 3.1 XML for orders export to 1C.

        Args:
            orders: QuerySet of **sub-orders** (is_master=False, parent_order__isnull=False)
                    with prefetch_related('items__variant', 'items__product', 'user').
                    vat_group субзаказа — авторитетный источник для организации/склада.
                    Guest orders (user=None) are supported — counterparty block is omitted.

        Returns:
            UTF-8 encoded XML string with declaration.

        Raises:
            No exceptions — проблемные заказы/товары пропускаются с warning.
        """
        xml_parts = list(self.generate_xml_streaming(orders))
        return "".join(xml_parts)

    def generate_xml_streaming(
        self,
        orders: "QuerySet[Order]",
        exported_ids: list[int] | None = None,
        skipped_ids: list[int] | None = None,
    ) -> Iterator[str]:
        """
        Generate CommerceML 3.1 XML using streaming/generator approach.

        Suitable for large datasets where memory efficiency is critical.
        Yields XML fragments that should be concatenated by the caller.

        Args:
            orders: QuerySet of **sub-orders** (is_master=False, parent_order__isnull=False)
                    with prefetch_related('items__variant', 'items__product', 'user').
                    vat_group субзаказа — авторитетный источник для организации/склада.
                    Guest orders (user=None) are supported — counterparty block is omitted.
            exported_ids: Optional list to append exported order PKs to.
                         Allows callers to know exactly which orders were included.
            skipped_ids: Optional list to append skipped order PKs to.
                        Orders that failed validation (e.g., no items) are added here.

        Yields:
            XML string fragments (declaration, root open, documents, root close).
        """
        # XML declaration
        yield '<?xml version="1.0" encoding="UTF-8"?>\n'

        # Root element open tag with attributes
        formation_date = self._format_datetime(timezone.now())
        yield f'<КоммерческаяИнформация ВерсияСхемы="{self.SCHEMA_VERSION}" '
        yield f'ДатаФормирования="{formation_date}">\n'

        # Stream each order as a Container with Document inside
        for _order in orders.iterator(chunk_size=100):
            order: Any = _order
            if order.is_master:
                logger.warning(
                    f"Order {order.order_number}: is_master=True, export skipped — "
                    f"OrderExportService expects sub-orders only"
                )
                if skipped_ids is not None:
                    skipped_ids.append(order.pk)
                continue
            if not self._validate_order(order):
                if skipped_ids is not None:
                    skipped_ids.append(order.pk)
                continue
            container = ET.Element("Контейнер")
            document = self._create_document_element(order)
            container.append(document)
            yield ET.tostring(container, encoding="unicode", method="xml")
            yield "\n"
            if exported_ids is not None:
                exported_ids.append(order.pk)

        # Root element close tag
        yield "</КоммерческаяИнформация>"

    def _validate_order(self, order: "Order") -> bool:
        """Валидация заказа перед генерацией XML."""
        # Use cached items from prefetch_related to avoid N+1 queries
        items_queryset = order.items.all()
        if not items_queryset:
            logger.warning(f"Order {order.order_number}: no items, skipping")
            return False
        return True

    def _create_document_element(self, order: "Order") -> ET.Element:
        """Создание элемента Документ для заказа."""
        document = ET.Element("Документ")

        # Основные теги документа
        self._add_text_element(document, "Ид", self._get_order_id(order))
        self._add_text_element(document, "Номер", order.order_number)
        # Convert to local time before formatting to ensure correct date
        local_created_at = timezone.localtime(order.created_at)
        self._add_text_element(document, "Дата", local_created_at.strftime("%Y-%m-%d"))
        self._add_text_element(document, "Время", local_created_at.strftime("%H:%M:%S"))
        self._add_text_element(document, "ХозОперация", self.OPERATION_TYPE)
        self._add_text_element(document, "Роль", self.ROLE)
        self._add_text_element(document, "Валюта", self.CURRENCY)
        self._add_text_element(document, "Курс", self.EXCHANGE_RATE)
        self._add_text_element(document, "Сумма", self._format_price(order.total_amount))

        # sub_order.vat_group → ORGANIZATION_BY_VAT, однородная группа НДС (AC4).
        # vat_group=None (AC8): DEFAULT_ORGANIZATION/DEFAULT_WAREHOUSE напрямую, warehouse_name не используется.
        order_vat_rate = self._get_order_vat_rate(order)
        if order.vat_group is not None:
            order_warehouse_name = self._get_order_warehouse_name_for_vat(order, order_vat_rate)
            org_name, warehouse_name = self._get_org_and_warehouse(order_vat_rate, order_warehouse_name)
        else:
            # AC8: vat_group=None → DEFAULT_* без warehouse_name routing
            logger.warning(f"Sub-order {order.order_number}: vat_group is None, using defaults")
            _exc_cfg = getattr(settings, "ONEC_EXCHANGE", {})
            org_name = _exc_cfg.get("DEFAULT_ORGANIZATION", "ИП Семерюк Д.В.")
            warehouse_name = _exc_cfg.get("DEFAULT_WAREHOUSE", "1 СДВ склад")
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        agreement_name = exchange_cfg.get("DEFAULT_AGREEMENT", "Стандартное")

        self._add_text_element(document, "Организация", org_name)
        self._add_text_element(document, "Склад", warehouse_name)

        agreement = ET.SubElement(document, "Соглашение")
        self._add_text_element(agreement, "Наименование", agreement_name)

        # 1C-БУС читает флаг "Цена включает НДС" из Документ.Налоги, а не из строк товара.
        document.append(self._create_document_taxes_element(order, order_vat_rate))

        # Блок контрагентов
        counterparties = self._create_counterparties_element(order)
        document.append(counterparties)

        # Блок товаров
        products = self._create_products_element(order)
        document.append(products)

        # Значения реквизитов документа (обязательные для УТ 11)
        doc_props = ET.Element("ЗначенияРеквизитов")

        order_defaults = self._get_order_defaults()

        # Обязательные реквизиты УТ 11
        # Организация, Склад и Соглашение берутся из динамически вычисленных значений
        self._add_requisite(doc_props, "Операция", order_defaults["OPERATION"])
        self._add_requisite(doc_props, "Статус заказа", order_defaults["STATUS"])
        self._add_requisite(doc_props, "Организация", org_name)
        self._add_requisite(doc_props, "Соглашение", agreement_name)
        self._add_requisite(doc_props, "Склад", warehouse_name)

        self._add_requisite(doc_props, "Отменен", "false")
        self._add_requisite(doc_props, "Проведен", "false")
        self._add_requisite(doc_props, "Сайт", "freesport.ru")

        document.append(doc_props)

        return document

    def _create_document_taxes_element(self, order: "Order", order_vat_rate: Decimal) -> ET.Element:
        """Создаёт блок Документ/Налоги для 1С, чтобы импорт выставил ЦенаВключаетНДС."""
        taxes = ET.Element("Налоги")
        tax = ET.SubElement(taxes, "Налог")
        self._add_text_element(tax, "Наименование", "НДС")
        self._add_text_element(tax, "УчтеноВСумме", "true")
        self._add_text_element(tax, "Ставка", str(int(order_vat_rate)))
        self._add_text_element(tax, "Сумма", self._format_price(self._get_document_vat_amount(order, order_vat_rate)))
        return taxes

    def _create_counterparties_element(self, order: "Order") -> ET.Element:
        """Создание блока Контрагенты.

        Supports both registered users and guest orders. For guest orders,
        uses order.customer_name, customer_email, customer_phone fields.
        Customer fields скопированы с мастера в Story 34-2, прямое использование безопасно.
        """
        counterparties = ET.Element("Контрагенты")
        counterparty = ET.Element("Контрагент")

        user = order.user
        if user:
            # Registered user: use User model fields
            counterparty_id = self._get_counterparty_id(user)
            if not user.onec_id:
                logger.warning(
                    f"Order {order.order_number}: User {user.id} has no onec_id, "
                    f"using fallback ID: {counterparty_id}"
                )
            self._add_text_element(counterparty, "Ид", counterparty_id)

            # Наименование: company_name для B2B или full_name для B2C
            if user.is_b2b_user and user.company_name:
                self._add_text_element(counterparty, "Наименование", str(user.company_name))
                self._add_text_element(counterparty, "ПолноеНаименование", str(user.company_name))
            else:
                name = str(user.full_name or user.email or "")
                self._add_text_element(counterparty, "Наименование", name)
                self._add_text_element(counterparty, "ПолноеНаименование", name)

            self._add_text_element(counterparty, "Роль", "Покупатель")

            # ИНН только если есть tax_id
            if user.tax_id:
                self._add_text_element(counterparty, "ИНН", str(user.tax_id))

            # Контакты
            contacts = ET.Element("Контакты")
            if user.email:
                contact_email = ET.Element("Контакт")
                self._add_text_element(contact_email, "Тип", "Почта")
                self._add_text_element(contact_email, "Значение", str(user.email))
                contacts.append(contact_email)
            if user.phone:
                contact_phone = ET.Element("Контакт")
                self._add_text_element(contact_phone, "Тип", "Телефон")
                self._add_text_element(contact_phone, "Значение", str(user.phone))
                contacts.append(contact_phone)
            if len(contacts) > 0:
                counterparty.append(contacts)
        else:
            # Guest order: use Order.customer_name/email/phone fields
            # Generate stable ID from email hash or order number
            counterparty_id = self._get_guest_counterparty_id(order)
            self._add_text_element(counterparty, "Ид", counterparty_id)

            # Наименование from customer_name or email
            name = order.customer_name or order.customer_email or f"Гость #{order.order_number}"
            self._add_text_element(counterparty, "Наименование", name)
            self._add_text_element(counterparty, "ПолноеНаименование", name)
            self._add_text_element(counterparty, "Роль", "Покупатель")

            # Контакты from order fields
            contacts = ET.Element("Контакты")
            if order.customer_email:
                contact_email = ET.Element("Контакт")
                self._add_text_element(contact_email, "Тип", "Почта")
                self._add_text_element(contact_email, "Значение", order.customer_email)
                contacts.append(contact_email)
            if order.customer_phone:
                contact_phone = ET.Element("Контакт")
                self._add_text_element(contact_phone, "Тип", "Телефон")
                self._add_text_element(contact_phone, "Значение", order.customer_phone)
                contacts.append(contact_phone)
            if len(contacts) > 0:
                counterparty.append(contacts)

            logger.info(f"Order {order.order_number}: guest order, using customer fields for counterparty")

        # Адрес регистрации (common for both user and guest orders)
        if order.delivery_address:
            address_reg = ET.Element("АдресРегистрации")
            self._add_text_element(address_reg, "Представление", str(order.delivery_address))
            counterparty.append(address_reg)

        counterparties.append(counterparty)
        return counterparties

    def _create_products_element(self, order: "Order") -> ET.Element:
        """Создание блока Товары."""
        products = ET.Element("Товары")

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        action = exchange_cfg.get("DEFAULT_ITEM_ACTION", "Резервировать")
        price_type_name = self._get_price_type(order)
        price_type_id = self._get_price_type_id(price_type_name)
        order_vat_rate = self._get_order_vat_rate(order)

        for item in order.items.all():
            # Defensive check: пропуск OrderItem с variant=None
            if item.variant is None:
                logger.warning(f"OrderItem {item.id}: variant is None (deleted?), skipping")
                continue

            # Defensive check: пропуск товара без onec_id
            if not item.variant.onec_id:
                logger.warning(f"OrderItem {item.id}: ProductVariant {item.variant.id} " f"missing onec_id, skipping")
                continue

            product = ET.Element("Товар")
            self._add_text_element(product, "Ид", item.variant.onec_id)
            self._add_text_element(product, "Наименование", item.product_name)

            # Базовая единица измерения (configurable via settings.ONEC_EXCHANGE.DEFAULT_UNIT)
            ud = self._unit_defaults
            unit = ET.Element("БазоваяЕдиница")
            unit.set("Код", ud["code"])
            unit.set("НаименованиеПолное", ud["name_full"])
            unit.set("МеждународноеСокращение", ud["name_intl"])
            unit.text = ud["name_short"]
            product.append(unit)

            self._add_text_element(product, "ЦенаЗаЕдиницу", self._format_price(item.unit_price))
            self._add_text_element(product, "Количество", str(item.quantity))
            self._add_text_element(product, "Сумма", self._format_price(item.total_price))

            # Действие строки — резервирование товара на складе
            self._add_text_element(product, "Действие", action)

            # Вид цены — зависит от категории (роли) покупателя
            vid_ceny = ET.SubElement(product, "ВидЦены")
            if price_type_id:
                self._add_text_element(vid_ceny, "Ид", price_type_id)
            self._add_text_element(vid_ceny, "Наименование", price_type_name)

            # НДС «в том числе» (включён в сумму строки).
            item_vat_rate = self._resolve_item_vat_rate_for_export(item, order_vat_rate)
            vat_amount = self._calc_vat_amount(item.total_price, item_vat_rate)

            taxes = ET.SubElement(product, "Налоги")
            tax = ET.SubElement(taxes, "Налог")
            self._add_text_element(tax, "Наименование", "НДС")
            # CommerceML/Bitrix expects the standard "included in sum" flag name.
            self._add_text_element(tax, "УчтеноВСумме", "true")
            self._add_text_element(tax, "Ставка", str(int(item_vat_rate)))
            self._add_text_element(tax, "Сумма", self._format_price(vat_amount))

            # Реквизиты товара (обязательно для загрузки в 1С УТ)
            props = ET.Element("ЗначенияРеквизитов")

            prop1 = ET.Element("ЗначениеРеквизита")
            self._add_text_element(prop1, "Наименование", "ВидНоменклатуры")
            self._add_text_element(prop1, "Значение", "Товар")
            props.append(prop1)

            prop2 = ET.Element("ЗначениеРеквизита")
            self._add_text_element(prop2, "Наименование", "ТипНоменклатуры")
            self._add_text_element(prop2, "Значение", "Товар")
            props.append(prop2)

            product.append(props)

            products.append(product)

        return products

    def _resolve_item_vat_rate_for_export(self, item: "OrderItem", order_vat_rate: Decimal) -> Decimal:
        """Возвращает ставку НДС строки для XML-экспорта заказа."""
        # Цепочка AC5: OrderItem.vat_rate (snapshot) → variant.vat_rate → product.vat_rate → order_vat_rate.
        # warehouse_name варианта НЕ используется для item-level VAT — только для order-level fallback.
        if item.vat_rate is not None:
            return Decimal(str(item.vat_rate))
        if item.variant is None:
            return order_vat_rate
        if item.variant.vat_rate is not None:
            return Decimal(str(item.variant.vat_rate))
        product_vat_rate = self._get_prefetched_product_vat_rate(item)
        return product_vat_rate if product_vat_rate is not None else order_vat_rate

    def _get_document_vat_amount(self, order: "Order", order_vat_rate: Decimal) -> Decimal:
        """Сумма НДС документа как сумма НДС строк, чтобы совпадать с товарными блоками."""
        total_vat = Decimal("0.00")
        for item in order.items.all():
            if item.variant is None:
                continue
            item_vat_rate = self._resolve_item_vat_rate_for_export(item, order_vat_rate)
            total_vat += self._calc_vat_amount(item.total_price, item_vat_rate)
        return total_vat.quantize(Decimal("0.01"))

    # -------------------------------------------------------------------------
    # Вспомогательные методы для организации/склада/цены/НДС
    # -------------------------------------------------------------------------

    def _get_order_vat_rate(self, order: "Order") -> Decimal:
        """
        Определяет ставку НДС заказа.
        Приоритет: order.vat_group (Story 34-2) → OrderItem.vat_rate (snapshot, Story 34-1)
                 → variant.vat_rate → warehouse_name → DEFAULT_VAT_RATE.
        """
        if order.vat_group is not None:
            return Decimal(str(order.vat_group))

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        default_rate = Decimal(str(exchange_cfg.get("DEFAULT_VAT_RATE", 22)))
        for item in order.items.all():
            # Приоритет snapshot (Story 34-1)
            if item.vat_rate is not None:
                return Decimal(str(item.vat_rate))
            product_vat_rate = self._get_prefetched_product_vat_rate(item)
            if product_vat_rate is not None:
                return product_vat_rate
            if not item.variant:
                continue
            if item.variant.vat_rate is not None:
                return Decimal(str(item.variant.vat_rate))
            warehouse_vat_rate = self._get_vat_rate_by_warehouse_name(item.variant.warehouse_name)
            if warehouse_vat_rate is not None:
                return warehouse_vat_rate
        return default_rate

    def _get_prefetched_product_vat_rate(self, item: "OrderItem") -> Decimal | None:
        """Возвращает Product.vat_rate без неявного SQL-запроса к item.product."""
        product = getattr(item._state, "fields_cache", {}).get("product")
        if product is None or product.vat_rate is None:
            return None
        return Decimal(str(product.vat_rate))

    def _get_order_warehouse_name(self, order: "Order") -> str | None:
        """Возвращает склад первого товара заказа, если он уже определён у варианта."""
        for item in order.items.all():
            if item.variant and item.variant.warehouse_name:
                return str(item.variant.warehouse_name)
        return None

    def _get_order_warehouse_name_for_vat(self, order: "Order", vat_rate: Decimal) -> str | None:
        """Возвращает склад субзаказа если он однозначен и совместим с vat_group.

        Склад возвращается если:
        - все позиции субзаказа имеют одинаковый склад (однозначность)
        - склад известен (есть в WAREHOUSE_RULES)
        - склад либо не имеет фиксированной ставки НДС (переменная, как 1 СДВ склад),
          либо его ставка совпадает с vat_group субзаказа.
        """
        warehouse_names = {
            str(item.variant.warehouse_name)
            for item in order.items.all()
            if item.variant and item.variant.warehouse_name
        }
        if len(warehouse_names) != 1:
            return None

        warehouse_name = next(iter(warehouse_names))
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        if warehouse_name not in warehouse_rules:
            return None

        warehouse_vat_rate = self._get_vat_rate_by_warehouse_name(warehouse_name)
        # Склад без фиксированной ставки (переменный НДС) — принимаем как есть.
        # Склад с фиксированной ставкой — принимаем только если совпадает с vat_group.
        if warehouse_vat_rate is None or warehouse_vat_rate == Decimal(str(vat_rate)):
            return warehouse_name
        return None

    def _get_org_and_warehouse(self, vat_rate: Decimal, warehouse_name: str | None = None) -> tuple[str, str]:
        """
        Возвращает (название организации, название склада).
        Приоритет: warehouse_name -> vat_rate -> DEFAULT_*.
        """
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        if warehouse_name:
            warehouse_info = warehouse_rules.get(warehouse_name)
            if warehouse_info:
                return warehouse_info["organization"], warehouse_name

        mapping = exchange_cfg.get("ORGANIZATION_BY_VAT", {})
        info = mapping.get(int(vat_rate))
        if info:
            return info["name"], info["warehouse"]
        return (
            exchange_cfg.get("DEFAULT_ORGANIZATION", "ИП Семерюк Д.В."),
            exchange_cfg.get("DEFAULT_WAREHOUSE", "1 СДВ склад"),
        )

    def _get_vat_rate_by_warehouse_name(self, warehouse_name: str | None) -> Decimal | None:
        """Возвращает ставку НДС по имени склада."""
        if not warehouse_name:
            return None

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        info = warehouse_rules.get(warehouse_name)
        if not info:
            return None

        vat_rate = info.get("vat_rate")
        if vat_rate is None:
            return None

        return Decimal(str(vat_rate))

    def _get_variant_vat_rate(self, variant: "ProductVariant", default_rate: Decimal) -> Decimal:
        """Возвращает НДС варианта: собственный vat_rate, затем ставка по складу, затем default."""
        if variant.vat_rate is not None:
            return Decimal(str(variant.vat_rate))

        warehouse_vat_rate = self._get_vat_rate_by_warehouse_name(variant.warehouse_name)
        if warehouse_vat_rate is not None:
            return warehouse_vat_rate

        return default_rate

    def _get_price_type(self, order: "Order") -> str:
        """
        Возвращает вид цены в 1С по роли пользователя.
        Маппинг настраивается через ONEC_EXCHANGE['PRICE_TYPE_BY_ROLE'].
        """
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        role_map = exchange_cfg.get("PRICE_TYPE_BY_ROLE", {})
        default_pt = str(exchange_cfg.get("DEFAULT_PRICE_TYPE", "РРЦ"))
        user = order.user
        if user:
            return str(role_map.get(user.role, default_pt))
        return default_pt

    def _get_price_type_id(self, price_type_name: str) -> str | None:
        """Возвращает GUID типа цены 1С по имени без SQL-запросов."""
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        mapping = exchange_cfg.get("PRICE_TYPE_ID_BY_NAME", {})
        price_type_id = str(mapping.get(price_type_name, "")).strip()
        return price_type_id or None

    def _calc_vat_amount(self, total_price: Decimal, vat_rate: Decimal) -> Decimal:
        """
        НДС «в том числе» (включён в цену):
            НДС = сумма × ставка / (100 + ставка)
        Пример: 2109.00 × 22 / 122 = 380.31
        """
        return (total_price * vat_rate / (Decimal("100") + vat_rate)).quantize(Decimal("0.01"))

    def _get_order_defaults(self) -> dict:
        """Read order default requisites from settings.ONEC_EXCHANGE.ORDER_DEFAULTS."""
        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        defaults = exchange_cfg.get("ORDER_DEFAULTS", {})
        return {
            "OPERATION": defaults.get("OPERATION", "Реализация"),
            "STATUS": defaults.get("STATUS", "Не согласован"),
        }

    def _add_requisite(self, parent: ET.Element, name: str, value: str) -> None:
        """Добавление элемента ЗначениеРеквизита."""
        prop = ET.Element("ЗначениеРеквизита")
        self._add_text_element(prop, "Наименование", name)
        self._add_text_element(prop, "Значение", value)
        parent.append(prop)

    # -------------------------------------------------------------------------
    # Общие вспомогательные методы
    # -------------------------------------------------------------------------

    def _add_text_element(self, parent: ET.Element, tag: str, text: str) -> ET.Element:
        """Добавление текстового элемента к родителю."""
        element = ET.SubElement(parent, tag)
        element.text = text
        return element

    def _format_datetime(self, dt: datetime) -> str:
        """Форматирование даты/времени в ISO 8601."""
        return dt.isoformat()

    def _format_price(self, value: Union[Decimal, float, int]) -> str:
        """
        Format price with exactly 2 decimal places.

        CommerceML 3.1 expects prices in format like "1500.00", not "1500".
        """
        return f"{Decimal(value):.2f}"

    def _get_order_id(self, order: "Order") -> str:
        """
        Get immutable order identifier for XML <Ид> element.

        Uses order.id (database primary key) which is immutable,
        unlike order_number which could theoretically be changed.
        Format: 'order-{id}' for clarity in 1C.
        """
        return f"order-{order.id}"

    def _get_counterparty_id(self, user: "User") -> str:
        """
        Get counterparty identifier with privacy-safe fallback.

        Priority: onec_id → SHA256(email)[:16] → user-{id}
        Uses hashed email to avoid PII leak while maintaining uniqueness.
        """
        if user.onec_id:
            return str(user.onec_id)
        if user.email:
            # Use first 16 chars of SHA256 hash for reasonable uniqueness
            email_hash = hashlib.sha256(str(user.email).encode()).hexdigest()[:16]
            return f"email-{email_hash}"
        return f"user-{user.id}"

    def _get_guest_counterparty_id(self, order: "Order") -> str:
        """
        Get counterparty identifier for guest orders.

        Priority: SHA256(customer_email)[:16] → guest-order-{id}
        Uses hashed email to avoid PII leak while maintaining uniqueness.
        """
        if order.customer_email:
            email_hash = hashlib.sha256(order.customer_email.encode()).hexdigest()[:16]
            return f"guest-{email_hash}"
        return f"guest-order-{order.id}"

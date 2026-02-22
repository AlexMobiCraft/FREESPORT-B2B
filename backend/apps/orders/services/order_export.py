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
from typing import TYPE_CHECKING, Iterator, Union

from django.conf import settings
from django.utils import timezone

if TYPE_CHECKING:
    from django.db.models import QuerySet

    from apps.orders.models import Order
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
            orders: QuerySet with prefetch_related('items__variant', 'user').
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
            orders: QuerySet with prefetch_related('items__variant', 'user').
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
        for order in orders.iterator(chunk_size=100):
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

        # Блок контрагентов
        counterparties = self._create_counterparties_element(order)
        document.append(counterparties)

        # Блок товаров
        products = self._create_products_element(order)
        document.append(products)

        # Значения реквизитов документа
        doc_props = ET.Element("ЗначенияРеквизитов")
        
        doc_prop1 = ET.Element("ЗначениеРеквизита")
        self._add_text_element(doc_prop1, "Наименование", "Статус заказа")
        self._add_text_element(doc_prop1, "Значение", "Новый")
        doc_props.append(doc_prop1)
        
        doc_prop2 = ET.Element("ЗначениеРеквизита")
        self._add_text_element(doc_prop2, "Наименование", "Отменен")
        self._add_text_element(doc_prop2, "Значение", "false")
        doc_props.append(doc_prop2)

        doc_prop3 = ET.Element("ЗначениеРеквизита")
        self._add_text_element(doc_prop3, "Наименование", "Сайт")
        self._add_text_element(doc_prop3, "Значение", "freesport.ru")
        doc_props.append(doc_prop3)

        document.append(doc_props)

        return document

    def _create_counterparties_element(self, order: "Order") -> ET.Element:
        """Создание блока Контрагенты.

        Supports both registered users and guest orders. For guest orders,
        uses order.customer_name, customer_email, customer_phone fields.
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

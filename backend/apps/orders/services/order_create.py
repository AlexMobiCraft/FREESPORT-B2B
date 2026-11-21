"""
Сервис создания заказов OPTISPORT.
Реализует разбивку заказа на мастер + субзаказы по VAT-группам (Story 34-2).
"""

import logging
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, cast

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.db.models.manager import BaseManager
from rest_framework import serializers

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order, OrderItem
from apps.orders.services.order_numbering import OrderNumberError, OrderNumberingService
from apps.products.models import PriceType, ProductVariant
from apps.products.pricing_policy import PROMO_PRICE_FIELD, PricedField, resolve_user_price
from apps.products.services.promo import current_promo_type, lock_promo_state

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceChange:
    """Позиция корзины, цена которой разошлась со снимком."""

    variant_id: int
    product_name: str
    quantity: int
    old_price: Decimal
    new_price: Decimal


@dataclass(frozen=True)
class PricesChanged:
    """
    Результат оформления «цены изменились»: заказ не создан, снимки корзины обновлены.

    `items` — только разошедшиеся позиции, `items_total` — сумма всех позиций
    корзины по новым ценам.
    """

    items: list[PriceChange]
    items_total: Decimal


class OrderCreateService:
    """Создаёт мастер-заказ и N субзаказов по VAT-группам из корзины."""

    def __init__(self, cart: Cart, user: Any, validated_data: dict[str, Any], delivery_cost: Decimal):
        self.cart = cart
        self.user = user
        self.validated_data = validated_data
        self.delivery_cost = delivery_cost
        # Поле-источник цены → (GUID, наименование) вида цен 1С; один запрос на поле за заказ
        self._price_types: dict[str, tuple[str, str]] = {}

    @transaction.atomic
    def create(self) -> Order | PricesChanged:
        """
        Создаёт заказ по ценам, пересчитанным в момент оформления.

        Возвращает `PricesChanged` (заказа нет), если цена хоть одной позиции
        разошлась со снимком корзины: снимки обновляются и фиксируются коммитом
        этой транзакции. Цена `≤ 0` у любой позиции — `ValidationError`
        `price_unavailable`, корзина не меняется.
        """
        user = self.user
        delivery_cost = self.delivery_cost
        validated_data = dict(self.validated_data)

        # Пока идёт смена или сброс текущей акции (исключительная блокировка),
        # оформление ждёт: цена позиции не должна читаться посреди переключения.
        lock_promo_state(shared=True)

        # Double-submit protection: блокируем строку корзины внутри транзакции.
        # Второй параллельный запрос будет ждать снятия блокировки; после этого
        # увидит пустую корзину (cart.clear() уже вызван) и получит ValidationError.
        cart_manager = cast(BaseManager[Cart], getattr(Cart, "objects"))
        cart = cart_manager.select_for_update().filter(pk=self.cart.pk).first()
        if not cart or not cart.items.exists():
            raise serializers.ValidationError(
                "Корзина пуста или уже используется для создания заказа. " "Обновите корзину и попробуйте снова."
            )

        # discount_amount is server-authoritative; client value ignored.
        # promo_code is a stub: accepted from client, not yet validated against DB.
        # Future: PromoCode.calculate(promo_code, cart, user) → discount_amount.
        validated_data.pop("discount_amount", None)
        validated_data.pop("promo_code", None)
        discount_amount: Decimal = Decimal("0")

        # 1. Сгруппировать позиции корзины по устойчивой ставке НДС и складу.
        # 1С требует отдельные документы не только для разных ставок НДС, но и
        # для разных складов внутри одной ставки (например 1 СДВ и Intex ОСНОВНОЙ).
        # Цена каждой позиции считается заново, вместе с полем-источником.
        groups: dict[tuple[Decimal | None, str | None], list[tuple[CartItem, PricedField]]] = defaultdict(list)
        priced_items: list[tuple[CartItem, PricedField]] = []

        for ci in cart.items.select_related("variant__product").order_by("pk"):
            variant = ci.variant
            product = variant.product if variant else None
            if not variant or not product:
                raise serializers.ValidationError("Некорректный товар в корзине. Обновите корзину и попробуйте снова.")
            priced = resolve_user_price(variant, user)
            priced_items.append((ci, priced))
            vat_key = self._resolve_item_vat_rate(variant, product)
            warehouse_key = getattr(variant, "warehouse_name", None) or None
            groups[(vat_key, warehouse_key)].append((ci, priced))

        # Проверки — до номера заказа и любых записей: (1) цены нет, (2) цена изменилась.
        for ci, priced in priced_items:
            if priced.price <= 0:
                raise serializers.ValidationError(
                    {
                        "code": "price_unavailable",
                        "detail": f"{ci.variant.product.name} сейчас недоступен для заказа",
                    }
                )

        total_items_sum = sum((priced.price * ci.quantity for ci, priced in priced_items), Decimal("0"))
        price_changes = self._sync_changed_snapshots(priced_items)
        if price_changes:
            return PricesChanged(items=price_changes, items_total=total_items_sum)

        ordered_groups = sorted(
            groups.items(),
            key=lambda entry: (
                entry[0][0] is None,
                entry[0][0] if entry[0][0] is not None else Decimal("0"),
                entry[0][1] or "",
            ),
        )
        try:
            master_number = OrderNumberingService.next_master_number(user)
        except OrderNumberError as exc:
            raise serializers.ValidationError({"order_number": str(exc)}) from exc

        # 2. Создать мастер-заказ (delivery_cost и discount_amount только здесь)
        master = Order(
            order_number=master_number.order_number,
            user=user,
            is_master=True,
            parent_order=None,
            vat_group=None,
            customer_code_snapshot=master_number.customer_code_snapshot,
            order_year=master_number.order_year,
            customer_year_sequence=master_number.customer_year_sequence,
            delivery_cost=delivery_cost,
            discount_amount=discount_amount,
            total_amount=total_items_sum + delivery_cost - discount_amount,
            **validated_data,
        )
        master.save()

        # 3. Создать субзаказы + OrderItem для каждой VAT-группы
        variant_updates: list[tuple[int, int]] = []
        order_item_manager = cast(BaseManager[OrderItem], getattr(OrderItem, "objects"))

        for suborder_sequence, ((vat_key, _warehouse_key), items) in enumerate(ordered_groups, start=1):
            group_total = sum((priced.price * ci.quantity for ci, priced in items), Decimal("0"))
            sub_number = OrderNumberingService.build_suborder_number(master, suborder_sequence)
            sub = Order(
                order_number=sub_number.order_number,
                user=user,
                is_master=False,
                parent_order=master,
                vat_group=vat_key,
                customer_code_snapshot=sub_number.customer_code_snapshot,
                order_year=sub_number.order_year,
                customer_year_sequence=sub_number.customer_year_sequence,
                suborder_sequence=sub_number.suborder_sequence,
                delivery_cost=Decimal("0"),
                total_amount=group_total,
                status="pending",
                payment_status="pending",
                customer_name=master.customer_name,
                customer_email=master.customer_email,
                customer_phone=master.customer_phone,
                delivery_address=master.delivery_address,
                delivery_method=master.delivery_method,
                delivery_date=master.delivery_date,
                payment_method=master.payment_method,
                notes=master.notes,
            )
            sub.save()

            sub_items = []
            for ci, priced in items:
                variant = ci.variant
                product = variant.product
                unit_price = priced.price
                snapshot = OrderItem.build_snapshot(product, variant)
                price_type_onec_id, price_type_name = self._price_type_for_field(priced.field, master.order_number)
                sub_items.append(
                    OrderItem(
                        order=sub,
                        product=product,
                        variant=variant,
                        quantity=ci.quantity,
                        unit_price=unit_price,
                        total_price=unit_price * ci.quantity,
                        price_source_field=priced.field,
                        price_type_onec_id=price_type_onec_id,
                        price_type_name=price_type_name,
                        **snapshot,
                    )
                )
                variant_updates.append((variant.pk, ci.quantity))

            order_item_manager.bulk_create(sub_items)

        # 4. Списать остатки через conditional update — защита от race condition
        # между параллельными checkout'ами: если stock уже забрали, update вернёт 0,
        # бросаем ValidationError, транзакция откатывается целиком.
        variant_manager = cast(BaseManager[ProductVariant], getattr(ProductVariant, "objects"))
        for variant_pk, qty in variant_updates:
            updated = variant_manager.filter(pk=variant_pk, stock_quantity__gte=qty).update(
                stock_quantity=F("stock_quantity") - qty
            )
            if updated == 0:
                out_of_stock_variant: ProductVariant | None = (
                    variant_manager.filter(pk=variant_pk).only("id", "sku").first()
                )
                sku = getattr(out_of_stock_variant, "sku", variant_pk) if out_of_stock_variant else variant_pk
                raise serializers.ValidationError(
                    f"Недостаточно товара '{sku}' на складе. "
                    f"Запрошенное количество больше не доступно — возможно, другой покупатель "
                    f"оформил заказ раньше. Обновите корзину и попробуйте снова."
                )

        # 5. Очистить корзину
        cart.clear()

        return master

    def _price_type_for_field(self, field: str, order_number: str) -> tuple[str, str]:
        """
        Вид цен 1С поля-источника цены: (GUID, наименование) или ("", ""), если вида нет.

        Только активные `PriceType`, без поиска по наименованию. Акция — текущая
        (`current_promo_type`): `create` держит общую блокировку акции с начала
        транзакции, поэтому вид читается в том же состоянии акции, что и цена.
        Несколько активных видов у поля — первый по `onec_name` и предупреждение.
        """
        if field in self._price_types:
            return self._price_types[field]

        candidates: list[PriceType]
        if field == PROMO_PRICE_FIELD:
            promo_type = current_promo_type()
            candidates = [promo_type] if promo_type else []
        else:
            price_type_manager = cast(BaseManager[PriceType], getattr(PriceType, "objects"))
            candidates = list(
                price_type_manager.filter(product_field=field, is_active=True).order_by("onec_name", "pk")[:2]
            )

        if not candidates:
            logger.warning(
                "Заказ %s: нет активного вида цен 1С для поля %s — вид цены строки в 1С не передаётся",
                order_number,
                field,
            )
            result = ("", "")
        else:
            if len(candidates) > 1:
                logger.warning(
                    "Заказ %s: у поля %s несколько активных видов цен 1С, взят первый по наименованию «%s»",
                    order_number,
                    field,
                    candidates[0].onec_name,
                )
            result = (candidates[0].onec_id, candidates[0].onec_name)

        self._price_types[field] = result
        return result

    @staticmethod
    def _sync_changed_snapshots(priced_items: list[tuple[CartItem, PricedField]]) -> list[PriceChange]:
        """
        Обновляет снимки цен разошедшихся позиций и возвращает список изменений.

        `update()`, а не `save()`: `CartItem.save` вызывает `full_clean`, а сигнал
        позиции пересчитывает `reserved_quantity` — ни то, ни другое здесь не нужно.
        """
        changes: list[PriceChange] = []
        cart_item_manager = cast(BaseManager[CartItem], getattr(CartItem, "objects"))
        for ci, priced in priced_items:
            if priced.price == ci.price_snapshot:
                continue
            cart_item_manager.filter(pk=ci.pk).update(price_snapshot=priced.price)
            changes.append(
                PriceChange(
                    variant_id=ci.variant_id,
                    product_name=ci.variant.product.name,
                    quantity=ci.quantity,
                    old_price=ci.price_snapshot,
                    new_price=priced.price,
                )
            )
        return changes

    def _resolve_item_vat_rate(self, variant: ProductVariant, product: Any) -> Decimal | None:
        """
        Возвращает ставку НДС для группировки заказа.

        Приоритет: warehouse_name → variant.vat_rate → product.vat_rate → DEFAULT_VAT_RATE.
        Склад проверяется первым: он определяет юрлицо (ИП) и применяемую ставку НДС.
        Это защищает от ситуации когда goods.xml содержит иную ставку, чем реально
        применяется для продажи со склада (например, 22% в каталоге vs 5% на складе ТЛВ).
        """
        warehouse_vat = self._get_vat_rate_by_warehouse_name(getattr(variant, "warehouse_name", None))
        if warehouse_vat is not None:
            return warehouse_vat

        raw_vat = getattr(variant, "vat_rate", None)
        if raw_vat is not None:
            return Decimal(str(raw_vat))

        product_vat = getattr(product, "vat_rate", None)
        if product_vat is not None:
            return Decimal(str(product_vat))

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        default_vat = exchange_cfg.get("DEFAULT_VAT_RATE")
        return Decimal(str(default_vat)) if default_vat is not None else None

    def _get_vat_rate_by_warehouse_name(self, warehouse_name: str | None) -> Decimal | None:
        if not warehouse_name:
            return None

        exchange_cfg = getattr(settings, "ONEC_EXCHANGE", {})
        warehouse_rules = exchange_cfg.get("WAREHOUSE_RULES", {})
        info = warehouse_rules.get(warehouse_name)
        if not info:
            return None

        vat_rate = info.get("vat_rate")
        return Decimal(str(vat_rate)) if vat_rate is not None else None

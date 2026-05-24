from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from django.core.exceptions import ObjectDoesNotExist
from django.db import IntegrityError
from django.db.models import Q
from django.utils import timezone

from apps.orders.models import CustomerOrderSequence

if TYPE_CHECKING:
    from apps.orders.models import Order

CUSTOMER_CODE_RE = re.compile(r"^\d{5}$")
MASTER_CANONICAL_RE = re.compile(r"^\d{10}$")
MASTER_UI_RE = re.compile(r"^(?P<customer>\d{4})-(?P<body>\d{5})$")
SUBORDER_UI_RE = re.compile(r"^(?P<customer>\d{5})-(?P<body>\d{5})-(?P<sequence>[1-9]\d*)$")
ALLOWED_QUERY_RE = re.compile(r"^[\d\-\s]+$")


class OrderNumberError(ValueError):
    pass


class MissingCustomerCodeError(OrderNumberError):
    pass


class OrderNumberSequenceExhausted(OrderNumberError):
    pass


class InvalidOrderNumberError(OrderNumberError):
    pass


@dataclass(frozen=True)
class MasterOrderNumberData:
    order_number: str
    customer_code_snapshot: str
    order_year: int
    customer_year_sequence: int


@dataclass(frozen=True)
class SubOrderNumberData(MasterOrderNumberData):
    suborder_sequence: int


def is_valid_customer_code(value: str | None) -> bool:
    return bool(CUSTOMER_CODE_RE.fullmatch(value or ""))


def is_canonical_master_order_number(value: str | None) -> bool:
    if not isinstance(value, str) or not MASTER_CANONICAL_RE.fullmatch(value):
        return False
    sequence = int(value[-3:])
    return 1 <= sequence <= 999


def is_canonical_sub_order_number(value: str | None) -> bool:
    if not isinstance(value, str) or not value.isdigit() or len(value) <= 10:
        return False
    if not is_canonical_master_order_number(value[:10]):
        return False
    return int(value[10:]) >= 1


def format_order_number(value: str | None) -> str:
    if not value:
        return ""
    if is_canonical_sub_order_number(value):
        return f"{value[:5]}-{value[5:10]}-{value[10:]}"
    if is_canonical_master_order_number(value):
        return f"{value[1:5]}-{value[5:10]}"
    return value


def normalize_order_number_query(raw: str) -> list[str]:
    if not isinstance(raw, str):
        return []
    compact = raw.strip().replace(" ", "")
    if not compact or not ALLOWED_QUERY_RE.fullmatch(compact):
        return []
    if is_canonical_master_order_number(compact) or is_canonical_sub_order_number(compact):
        return [compact]
    master_match = MASTER_UI_RE.fullmatch(compact)
    if master_match:
        body = master_match.group("body")
        if not 1 <= int(body[-3:]) <= 999:
            return []
        return [f"{master_match.group('customer')}{body}"]
    suborder_match = SUBORDER_UI_RE.fullmatch(compact)
    if suborder_match:
        body = suborder_match.group("body")
        if not 1 <= int(body[-3:]) <= 999:
            return []
        return [f"{suborder_match.group('customer')}{body}{suborder_match.group('sequence')}"]
    return []


def build_order_number_search_query(raw: str) -> Q | None:
    candidates = normalize_order_number_query(raw)
    if not candidates:
        return None
    query = Q()
    for candidate in candidates:
        if len(candidate) == 9:
            query.add(Q(order_number__endswith=candidate), Q.OR)
        else:
            query.add(Q(order_number=candidate), Q.OR)
    if not query.children:
        return None
    return cast(Q, query)


class OrderNumberingService:
    @classmethod
    def next_master_number(cls, user: Any) -> MasterOrderNumberData:
        user_model = type(user)
        locked_user = user_model._default_manager.select_for_update().only("pk", "customer_code").get(pk=user.pk)
        customer_code = str(getattr(locked_user, "customer_code", "") or "")
        if not is_valid_customer_code(customer_code):
            raise MissingCustomerCodeError("У пользователя отсутствует корректный customer_code.")
        year = timezone.localdate().year
        sequence = cls._next_sequence(customer_code, year)
        order_number = f"{customer_code}{str(year)[-2:]}{sequence:03d}"
        return MasterOrderNumberData(
            order_number=order_number,
            customer_code_snapshot=customer_code,
            order_year=year,
            customer_year_sequence=sequence,
        )

    @classmethod
    def build_suborder_number(cls, master: Order, suborder_sequence: int) -> SubOrderNumberData:
        if not is_canonical_master_order_number(master.order_number):
            raise InvalidOrderNumberError("Невозможно сформировать субзаказ для неканонического мастер-заказа.")
        if suborder_sequence < 1:
            raise InvalidOrderNumberError("suborder_sequence должен быть больше либо равен 1.")
        order_year = master.order_year
        customer_year_sequence = master.customer_year_sequence
        if order_year is None or customer_year_sequence is None:
            raise InvalidOrderNumberError("Мастер-заказ не содержит полных данных для формирования номера субзаказа.")
        return SubOrderNumberData(
            order_number=f"{master.order_number}{suborder_sequence}",
            customer_code_snapshot=master.customer_code_snapshot,
            order_year=order_year,
            customer_year_sequence=customer_year_sequence,
            suborder_sequence=suborder_sequence,
        )

    @classmethod
    def _next_sequence(cls, customer_code: str, year: int) -> int:
        counter = cls._get_locked_counter(customer_code, year)
        next_value = counter.last_sequence + 1
        if next_value > 999:
            raise OrderNumberSequenceExhausted(
                f"Исчерпан диапазон номеров заказов для customer_code={customer_code} и year={year}."
            )
        counter.last_sequence = next_value
        counter.save(update_fields=["last_sequence"])
        return next_value

    @classmethod
    def _get_locked_counter(cls, customer_code: str, year: int) -> CustomerOrderSequence:
        try:
            return CustomerOrderSequence.objects.select_for_update().get(customer_code=customer_code, year=year)
        except ObjectDoesNotExist:
            try:
                CustomerOrderSequence.objects.create(customer_code=customer_code, year=year, last_sequence=0)
            except IntegrityError:
                pass
            return CustomerOrderSequence.objects.select_for_update().get(customer_code=customer_code, year=year)

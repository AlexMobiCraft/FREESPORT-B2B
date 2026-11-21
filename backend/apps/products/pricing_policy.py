"""
Политика видимости цен в каталоге.

Единственный источник истины по вопросу «какие ценовые поля видит роль».
Инвариант (`project-context.md` §3): оптовые цены и B2B-инфо-цены доступны
только верифицированным пользователям с B2B-ролью; все остальные, включая
гостей, розницу и контрагентов 1С без портального аккаунта, видят розничную
цену.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Any, NamedTuple

if TYPE_CHECKING:
    from apps.products.models import ProductVariant
    from apps.users.models import User

# Сырые оптовые поля ответа каталога.
WHOLESALE_PRICE_FIELDS = ("opt1_price", "opt2_price", "opt3_price", "opt4_price")

# Инфо-цены B2B. Не участвуют в расчётах. `rrp` = розничная цена варианта
# (`retail_price`), которую и так получает любая роль: гейт сохранён намеренно
# (решение спеки spec-product-rrp-display), а показ строки «РРЦ» решает фронт
# по `isB2BRole`. `msrp` (МРЦ) закрыт от розницы по существу.
INFO_PRICE_FIELDS = ("rrp", "msrp")

# Роль → поле цены роли варианта. Роли вне карты (retail, unregistered,
# admin, аноним) считаются по retail_price.
#
# Единственный источник истины для `ProductVariant.get_price_for_user` и для
# ценовых фильтров каталога. Раньше карта была продублирована в обоих местах и
# разошлась: расчёт цены откатывался на розницу и при NULL, и при 0.00
# (`self.opt1_price or self.retail_price`), а фильтр — только при NULL. Из-за
# этого выдача по min_price/max_price не совпадала с ценой в карточке
# (находка ревью 2026-08-04). Правило одно: цена роли задана, только если она
# строго больше нуля.
ROLE_PRICE_FIELDS = {
    "wholesale_level1": "opt1_price",
    "wholesale_level2": "opt2_price",
    "wholesale_level3": "opt3_price",
    "wholesale_level4": "opt4_price",
    "trainer": "trainer_price",
    "federation_rep": "federation_price",
    "vip": "vip_price",
    "special_price": "special_price",
    "dealer": "dealer_price",
}

# Цены ролей, которые импорт 1С не только пишет, но и снимает: вид цен убрали из
# предложения — поле сбрасывается в NULL (`variant_import._resolve_role_price`).
# Этот же набор полное сохранение варианта не пишет (`ProductVariant.save`), а админка
# показывает только для чтения: источник истины — 1С, ручную правку сотрёт импорт.
RESETTABLE_ROLE_PRICE_FIELDS = ("special_price", "dealer_price")

# Вид цен 1С → роль, которую получает клиент с этим видом цен в соглашении
# (`PriceType.user_role`). GUID видов «VIP цены», «СПЕЦЦЕНА» и «Дилерская цена»
# заранее неизвестны, миграция их не засеет: роль проставляет импорт справочника цен.
#
# Один набор «ролей с ценой из 1С» намеренно (решение владельца 2026-11-16): каждая
# такая роль получает оптовые условия — оплата только банковским переводом или при
# получении, оптовые баннеры, нет саморегистрации, сырое поле цены скрыто в API.
# Поэтому `ASSIGNED_PRICE_ROLES` и `HIDDEN_ROLE_PRICE_FIELDS` выводятся отсюда. Роль с
# ценой из 1С без оптовых условий — повод развести наборы, а не исключение внутри одного.
PRICE_TYPE_ROLES = {"vip_price": "vip", "special_price": "special_price", "dealer_price": "dealer"}

# Роли с ценой из 1С: назначаются менеджером или 1С по виду цен соглашения, без
# саморегистрации; условия оплаты и баннеры — оптовые.
ASSIGNED_PRICE_ROLES = frozenset(PRICE_TYPE_ROLES.values())

# Сырые цены ролей с ценой из 1С: API их не отдаёт ни в одном ответе, клиент
# получает итог в `current_price` / `regular_price`. Сериализаторы со вложенным
# вариантом целиком (`OrderItemSerializer`, `depth = 1`) обязаны их вырезать.
HIDDEN_ROLE_PRICE_FIELDS = tuple(PRICE_TYPE_ROLES)

# Роль → запасное поле, если поле роли не задано. Дальше — розничная цена.
# Цепочка роли: поле роли → запасное поле → розница. У остальных ролей запасного
# поля нет: VIP без своей цены платит розницу, а не «Опт 1».
ROLE_PRICE_FALLBACKS = {"special_price": "opt1_price", "dealer": "opt1_price"}

# Роли, которым API отдаёт поля РРЦ/МРЦ. federation_rep исключён намеренно —
# поведение перенесено как есть из литеральных списков сериализаторов. admin поле
# получает, но строку «РРЦ» фронт ему не показывает (`isB2BRole`).
INFO_PRICE_ROLES = frozenset(
    {
        "wholesale_level1",
        "wholesale_level2",
        "wholesale_level3",
        "wholesale_level4",
        "trainer",
        "vip",
        "special_price",
        "dealer",
        "admin",
    }
)


def role_price_fields(role: str) -> tuple[str, ...]:
    """
    Поля цены роли в порядке приоритета, без розницы.

    Пустой кортеж — у роли своей цены нет (retail, unregistered, admin, аноним):
    цена такой роли — `retail_price`. Эту цепочку читают и расчёт цены, и ценовые
    фильтры каталога: добавлять ступень надо здесь, а не в одном из потребителей.
    """
    field = ROLE_PRICE_FIELDS.get(role)
    if field is None:
        return ()
    fallback = ROLE_PRICE_FALLBACKS.get(role)
    return (field, fallback) if fallback else (field,)


class PricedField(NamedTuple):
    """Цена и поле варианта, из которого она взята (`opt2_price`, `promo_price`, `retail_price`…)."""

    price: Decimal
    field: str


RETAIL_PRICE_FIELD = "retail_price"
PROMO_PRICE_FIELD = "promo_price"


def resolve_role_price(variant: "ProductVariant", role: str) -> PricedField:
    """
    Цена варианта для роли без учёта акции: первая заданная ступень цепочки, иначе розница.

    Цена задана, только если она строго больше нуля: NULL, 0.00 и отрицательное
    значение означают «цены для роли нет». Ровно то же условие применяют
    ценовые фильтры каталога (`filters.visible_price_q`).
    """
    for field in role_price_fields(role):
        value: Decimal | None = getattr(variant, field)
        if value is not None and value > 0:
            return PricedField(value, field)
    return PricedField(variant.retail_price, RETAIL_PRICE_FIELD)


def resolve_user_price(variant: "ProductVariant", user: "User | Any | None") -> PricedField:
    """
    Цена, которую платит пользователь, и поле-источник: меньшая из цены по роли и акционной.

    Акционная цена действует для всех ролей, но клиенту невыгодной не бывает:
    `min(цена по роли, акционная)` (решение владельца 2026-10-26). При равенстве
    источник — акция (решение 2026-11-12: вид цены строки для 1С). Цена роли `≤ 0`
    в сравнении не участвует: платит акцию. Нулевая цена без акции возвращается
    как есть — «цены нет» решает вызывающий (оформление заказа отказывает).
    `ProductVariant.get_price_for_user` отдаёт отсюда только `price`.
    """
    regular = resolve_role_price(variant, resolve_pricing_role(user))
    promo: Decimal | None = getattr(variant, PROMO_PRICE_FIELD)
    if promo is None or promo <= 0:
        return regular
    if regular.price <= 0 or promo <= regular.price:
        return PricedField(promo, PROMO_PRICE_FIELD)
    return regular


def resolve_pricing_role(user: "User | Any | None") -> str:
    """
    Роль, по которой считается цена для пользователя.

    B2B-роль без верификации понижается до "retail": менеджер ещё не
    подтвердил контрагента, поэтому оптовых условий у него нет.
    """
    from apps.users.models import User

    if user is None or not getattr(user, "is_authenticated", False):
        return "retail"

    role = getattr(user, "role", "retail")
    if role in User.B2B_ROLES and not getattr(user, "is_verified", False):
        return "retail"
    return role


def can_see_wholesale_prices(user: "User | Any | None") -> bool:
    """
    Видит ли пользователь сырые оптовые поля (`WHOLESALE_PRICE_FIELDS`).

    Роль без права получает `0.0` — это означает «нет права видеть оптовую
    цену», а НЕ «цена не заполнена» (пустая цена даёт тот же `0.0` в
    `get_optN_price`). Снятие этой проверки открывает всю оптовую сетку
    анонимным запросам — см. `tech-debt.md` п. 18.
    """
    from apps.users.models import User

    role = resolve_pricing_role(user)
    return role in User.B2B_ROLES or role == "admin"


def can_see_info_prices(user: "User | Any | None") -> bool:
    """Видит ли пользователь инфо-цены РРЦ/МРЦ (`INFO_PRICE_FIELDS`)."""
    return resolve_pricing_role(user) in INFO_PRICE_ROLES

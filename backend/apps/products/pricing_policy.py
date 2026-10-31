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
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.products.models import ProductVariant
    from apps.users.models import User

# Сырые оптовые поля ответа каталога.
WHOLESALE_PRICE_FIELDS = ("opt1_price", "opt2_price", "opt3_price", "opt4_price")

# Инфо-цены B2B. Не участвуют в расчётах, но так же закрыты от розницы.
INFO_PRICE_FIELDS = ("rrp", "msrp")

# Сырые цены ролей VIP и «Спец цена»: API их не отдаёт ни в одном ответе, клиент
# получает итог в `current_price` / `regular_price`. Сериализаторы со вложенным
# вариантом целиком (`OrderItemSerializer`, `depth = 1`) обязаны их вырезать.
HIDDEN_ROLE_PRICE_FIELDS = ("vip_price", "special_price")

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
}

# Поле спеццены: её, в отличие от остальных цен роли, импорт ещё и снимает.
SPECIAL_PRICE_FIELD = "special_price"

# Вид цен 1С → роль, которую получает клиент с этим видом цен в соглашении
# (`PriceType.user_role`). GUID видов «VIP цены» и «СПЕЦЦЕНА» заранее неизвестны,
# миграция их не засеет: роль проставляет импорт справочника цен.
PRICE_TYPE_ROLES = {"vip_price": "vip", "special_price": "special_price"}

# Роль → запасное поле, если поле роли не задано. Дальше — розничная цена.
# Цепочка роли: поле роли → запасное поле → розница. У остальных ролей запасного
# поля нет: VIP без своей цены платит розницу, а не «Опт 1».
ROLE_PRICE_FALLBACKS = {"special_price": "opt1_price"}

# Роли, которым видны РРЦ/МРЦ. federation_rep исключён намеренно —
# поведение перенесено как есть из литеральных списков сериализаторов.
INFO_PRICE_ROLES = frozenset(
    {
        "wholesale_level1",
        "wholesale_level2",
        "wholesale_level3",
        "wholesale_level4",
        "trainer",
        "vip",
        "special_price",
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


def resolve_role_price(variant: "ProductVariant", role: str) -> Decimal:
    """
    Цена варианта для роли без учёта акции: первая заданная ступень цепочки, иначе розница.

    Цена задана, только если она строго больше нуля: NULL, 0.00 и отрицательное
    значение означают «цены для роли нет». Ровно то же условие применяют
    ценовые фильтры каталога (`filters.visible_price_q`).
    """
    for field in role_price_fields(role):
        value: Decimal | None = getattr(variant, field)
        if value is not None and value > 0:
            return value
    return variant.retail_price


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

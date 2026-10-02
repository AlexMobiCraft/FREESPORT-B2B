"""
Политика видимости цен в каталоге.

Единственный источник истины по вопросу «какие ценовые поля видит роль».
Инвариант (`project-context.md` §3): оптовые цены и B2B-инфо-цены доступны
только верифицированным пользователям с B2B-ролью; все остальные, включая
гостей, розницу и контрагентов 1С без портального аккаунта, видят розничную
цену.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apps.users.models import User

# Сырые оптовые поля ответа каталога.
WHOLESALE_PRICE_FIELDS = ("opt1_price", "opt2_price", "opt3_price", "opt4_price")

# Инфо-цены B2B. Не участвуют в расчётах, но так же закрыты от розницы.
INFO_PRICE_FIELDS = ("rrp", "msrp")

# Роль → поле специальной цены варианта. Роли вне карты (retail, unregistered,
# admin, аноним) считаются по retail_price.
#
# Единственный источник истины для `ProductVariant.get_price_for_user` и для
# ценовых фильтров каталога. Раньше карта была продублирована в обоих местах и
# разошлась: расчёт цены откатывался на розницу и при NULL, и при 0.00
# (`self.opt1_price or self.retail_price`), а фильтр — только при NULL. Из-за
# этого выдача по min_price/max_price не совпадала с ценой в карточке
# (находка ревью 2026-08-04). Правило одно: специальная цена задана, только
# если она строго больше нуля.
ROLE_PRICE_FIELDS = {
    "wholesale_level1": "opt1_price",
    "wholesale_level2": "opt2_price",
    "wholesale_level3": "opt3_price",
    "wholesale_level4": "opt4_price",
    "trainer": "trainer_price",
    "federation_rep": "federation_price",
}

# Роли, которым видны РРЦ/МРЦ. federation_rep исключён намеренно —
# поведение перенесено как есть из литеральных списков сериализаторов.
INFO_PRICE_ROLES = frozenset(
    {"wholesale_level1", "wholesale_level2", "wholesale_level3", "wholesale_level4", "trainer", "admin"}
)


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

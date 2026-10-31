"""
Форматы телефонных номеров по стране регистрации.

Единый источник для модельного валидатора `User.phone` и сериализатора
регистрации. Модуль не импортирует модели, поэтому его безопасно брать из
`models.py`. Фронтовая копия таблицы — `frontend/src/utils/validators/phone.ts`.
"""

import re
from typing import NamedTuple


class PhoneFormat(NamedTuple):
    """Формат номера: регулярное выражение и пример для сообщения об ошибке."""

    pattern: str
    sample: str


# Россия и Казахстан делят код +7, поэтому формат у них один.
_RUSSIA_KAZAKHSTAN = PhoneFormat(pattern=r"^\+7\d{10}$", sample="+79001234567")
_BELARUS = PhoneFormat(pattern=r"^\+375\d{9}$", sample="+375291234567")

PHONE_FORMATS_BY_COUNTRY: dict[str, PhoneFormat] = {
    "Россия": _RUSSIA_KAZAKHSTAN,
    "Казахстан": _RUSSIA_KAZAKHSTAN,
    "Беларусь": _BELARUS,
}

DEFAULT_PHONE_COUNTRY = "Россия"

# Допустимо для хранения любое из форматов: страну у записи могут сменить
# отдельно от номера (админка, импорт из 1С), и модель не должна на этом падать.
ANY_PHONE_PATTERN = r"^(\+7\d{10}|\+375\d{9})$"
ANY_PHONE_MESSAGE = (
    f"Номер телефона должен быть в формате: '{_RUSSIA_KAZAKHSTAN.sample}' (Россия, Казахстан) "
    f"или '{_BELARUS.sample}' (Беларусь)"
)


def get_phone_format(country: object) -> PhoneFormat:
    """Формат номера для страны; неизвестное или не строковое значение — как Россия."""
    if isinstance(country, str):
        return PHONE_FORMATS_BY_COUNTRY.get(country, PHONE_FORMATS_BY_COUNTRY[DEFAULT_PHONE_COUNTRY])
    return PHONE_FORMATS_BY_COUNTRY[DEFAULT_PHONE_COUNTRY]


def is_known_phone_country(country: object) -> bool:
    """Есть ли страна в таблице форматов (не строка или незнакомое значение — нет)."""
    return isinstance(country, str) and country in PHONE_FORMATS_BY_COUNTRY


def is_valid_phone_for_country(phone: str, country: object) -> bool:
    """
    Соответствует ли номер формату выбранной страны.

    `re.ASCII`: без него шаблон принимает цифры любых алфавитов (арабо-индийские,
    полноширинные), а фронт и 1С работают только с `0-9`.
    """
    return re.fullmatch(get_phone_format(country).pattern, phone, flags=re.ASCII) is not None

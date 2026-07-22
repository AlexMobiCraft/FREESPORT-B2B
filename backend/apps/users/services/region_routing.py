"""
Маршрутизация email о регистрации B2B-клиента на регионального менеджера.

Ответственный менеджер определяется по стране регистрации (для зарубежных
клиентов) либо по коду субъекта РФ — первым двум цифрам ИНН. Сопоставление
хранится в редактируемой через Django Admin модели ``ManagerRoutingRule``.
"""

import logging

from apps.common.models import ManagerRoutingRule
from apps.users.models import User

logger = logging.getLogger(__name__)


def resolve_manager_recipients(country: str | None, tax_id: str | None) -> list[str]:
    """
    Вернуть список email менеджеров для уведомления о регистрации.

    Порядок разрешения:
      1. ``country`` не Россия → правило по стране (ИНН игнорируется).
      2. Иначе первые 2 цифры ``tax_id`` → правило по коду субъекта РФ.
      3. Ничего не найдено (неизвестный код, пустой/короткий ИНН, зарубеж без
         правила) → резервные адреса (``fallback``).

    Args:
        country: Страна регистрации (например, "Россия", "Беларусь").
        tax_id: ИНН клиента (10 или 12 цифр).

    Returns:
        Список уникальных email активных получателей (может быть пустым, если
        не настроено ни одного подходящего или резервного правила).
    """
    rules = ManagerRoutingRule.objects.filter(is_active=True)

    if country and country != User.COUNTRY_RUSSIA:
        matched = rules.filter(match_type=ManagerRoutingRule.MATCH_COUNTRY, match_value=country)
    else:
        region_code = (tax_id or "")[:2]
        if len(region_code) == 2 and region_code.isdigit():
            matched = rules.filter(match_type=ManagerRoutingRule.MATCH_INN_REGION, match_value=region_code)
        else:
            matched = rules.none()

    emails = list(matched.values_list("manager_email", flat=True))

    if not emails:
        logger.warning(
            "Manager region routing fell back to default recipients",
            extra={
                "country": country,
                "tax_id_prefix": (tax_id or "")[:2],
                "action": "manager_region_routing_fallback",
            },
        )
        emails = list(
            rules.filter(match_type=ManagerRoutingRule.MATCH_FALLBACK).values_list("manager_email", flat=True)
        )

    # Удаляем дубликаты, сохраняя порядок.
    return list(dict.fromkeys(emails))

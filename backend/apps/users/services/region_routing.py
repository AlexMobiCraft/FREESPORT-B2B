"""
Маршрутизация email о регистрации B2B-клиента на регионального менеджера.

Ответственный менеджер определяется по стране регистрации (для зарубежных
клиентов) либо по коду субъекта РФ — первым двум цифрам ИНН. Сопоставление
хранится в редактируемой через Django Admin модели ``ManagerRoutingRule``.
Та же таблица правил задаёт и ответственного менеджера клиента
(``apps.users.services.responsible_manager``), ключ региона общий.
"""

import logging

from django.db.models import QuerySet

from apps.common.models import ManagerRoutingRule
from apps.users.services.responsible_manager import region_key

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
    rules = ManagerRoutingRule.objects.filter(is_active=True).select_related("manager")

    key = region_key(country, tax_id)
    matched = rules.filter(match_type=key[0], match_value=key[1]) if key is not None else rules.none()

    emails = _rule_emails(matched)

    if not emails:
        logger.warning(
            "Manager region routing fell back to default recipients",
            extra={
                "country": country,
                "tax_id_prefix": (tax_id or "")[:2],
                "action": "manager_region_routing_fallback",
            },
        )
        emails = _rule_emails(rules.filter(match_type=ManagerRoutingRule.MATCH_FALLBACK))

    # Удаляем дубликаты, сохраняя порядок.
    return list(dict.fromkeys(emails))


def _rule_emails(rules: QuerySet[ManagerRoutingRule]) -> list[str]:
    """Адрес правила: email учётной записи менеджера, иначе ``manager_email``."""
    emails: list[str] = []
    for rule in rules:
        manager = rule.manager
        email = manager.email if manager is not None and manager.email else rule.manager_email
        if email:
            emails.append(str(email))
    return emails

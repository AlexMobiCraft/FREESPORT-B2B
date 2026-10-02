"""
Unit тесты маршрутизации заявок о регистрации B2B на регионального менеджера.

Покрывает:
- resolve_manager_recipients: страна, код субъекта РФ по ИНН, резерв, дедуп
- send_manager_region_email: успешная отправка, пустой список, отсутствие user
"""

from unittest.mock import patch

import pytest

from apps.common.models import ManagerRoutingRule
from apps.users.services.region_routing import resolve_manager_recipients
from apps.users.tasks import send_manager_region_email
from tests.factories import UserFactory

LOPATINA = "d.lopatina@freesportopt.ru"
GUSEV = "1managermsk@freesportopt.ru"
ISAKOVA = "manager5@freesportopt.ru"
CHERNOV = "managermsk3@freesportopt.ru"
ADMIN = "admin@freesportopt.ru"


def _rule(match_type, match_value, email, active=True):
    return ManagerRoutingRule.objects.create(
        match_type=match_type,
        match_value=match_value,
        manager_email=email,
        is_active=active,
    )


@pytest.fixture(autouse=True)
def _clear_routing_rules(db):
    """Изолируем unit-тесты от правил, засеянных data-миграцией."""
    ManagerRoutingRule.objects.all().delete()
    yield


@pytest.fixture
def fallback_rules(db):
    _rule(ManagerRoutingRule.MATCH_FALLBACK, "default", CHERNOV)
    _rule(ManagerRoutingRule.MATCH_FALLBACK, "default", ADMIN)


@pytest.mark.unit
@pytest.mark.django_db
class TestResolveManagerRecipients:
    """Тесты чистой функции разрешения получателей."""

    def test_russia_region_with_manager(self, fallback_rules):
        """РФ + код региона с менеджером → менеджер этого округа."""
        _rule(ManagerRoutingRule.MATCH_INN_REGION, "77", GUSEV)  # ЦФО (Москва)
        assert resolve_manager_recipients("Россия", "7701234567") == [GUSEV]

    def test_yufo_split_by_region(self, fallback_rules):
        """ЮФО делится по регионам: код 23 (Краснодар) → Исакова."""
        _rule(ManagerRoutingRule.MATCH_INN_REGION, "23", ISAKOVA)
        assert resolve_manager_recipients("Россия", "2312345678") == [ISAKOVA]

    def test_ufo_to_lopatina(self, fallback_rules):
        """УФО (код 66) → Лопатина (решение по конфликту в файле)."""
        _rule(ManagerRoutingRule.MATCH_INN_REGION, "66", LOPATINA)
        assert resolve_manager_recipients("Россия", "6612345678") == [LOPATINA]

    def test_foreign_country_ignores_inn(self, fallback_rules):
        """Зарубеж (Беларусь) → менеджер по стране, ИНН игнорируется."""
        _rule(ManagerRoutingRule.MATCH_COUNTRY, "Беларусь", LOPATINA)
        # ИНН выглядит как код региона 77, но страна имеет приоритет.
        assert resolve_manager_recipients("Беларусь", "7701234567") == [LOPATINA]

    def test_unknown_region_falls_back(self, fallback_rules):
        """РФ + неизвестный код региона → резервные адреса."""
        assert set(resolve_manager_recipients("Россия", "0012345678")) == {CHERNOV, ADMIN}

    def test_empty_inn_falls_back(self, fallback_rules):
        """Пустой ИНН → резерв."""
        assert set(resolve_manager_recipients("Россия", "")) == {CHERNOV, ADMIN}

    def test_short_inn_falls_back(self, fallback_rules):
        """Слишком короткий ИНН (< 2 цифр) → резерв."""
        assert set(resolve_manager_recipients("Россия", "7")) == {CHERNOV, ADMIN}

    def test_non_digit_prefix_falls_back(self, fallback_rules):
        """Нечисловой префикс ИНН → резерв."""
        assert set(resolve_manager_recipients("Россия", "AB12345678")) == {CHERNOV, ADMIN}

    def test_inactive_rule_excluded(self, fallback_rules):
        """Неактивное правило исключается → уходит в резерв."""
        _rule(ManagerRoutingRule.MATCH_INN_REGION, "77", GUSEV, active=False)
        assert set(resolve_manager_recipients("Россия", "7701234567")) == {CHERNOV, ADMIN}

    def test_recipients_deduplicated(self, db):
        """Дубли получателей удаляются, порядок сохраняется."""
        _rule(ManagerRoutingRule.MATCH_FALLBACK, "default", CHERNOV)
        _rule(ManagerRoutingRule.MATCH_FALLBACK, "default", CHERNOV)
        assert resolve_manager_recipients("Россия", "") == [CHERNOV]

    def test_no_rules_returns_empty(self, db):
        """Ни одного правила (даже резерва) → пустой список."""
        assert resolve_manager_recipients("Россия", "7701234567") == []


@pytest.mark.unit
@pytest.mark.django_db
class TestSendManagerRegionEmail:
    """Тесты Celery-таска отправки письма менеджеру."""

    @patch("apps.users.tasks.send_mail")
    def test_send_success(self, mock_send_mail, settings, fallback_rules):
        """Успешная отправка письма менеджеру региона."""
        settings.SITE_URL = "http://localhost"
        _rule(ManagerRoutingRule.MATCH_INN_REGION, "77", GUSEV)

        user = UserFactory(
            role="wholesale_level1",
            company_name="ООО Тест",
            tax_id="7701234567",
            email="b2b77@example.com",
        )

        result = send_manager_region_email(user.id)

        assert result is True
        mock_send_mail.assert_called_once()
        call_kwargs = mock_send_mail.call_args.kwargs
        assert call_kwargs["recipient_list"] == [GUSEV]
        assert "ООО Тест" in call_kwargs["subject"]
        assert call_kwargs["html_message"] is not None

    @patch("apps.users.tasks.send_mail")
    def test_no_recipients_skips(self, mock_send_mail, settings):
        """Нет ни одного правила → письмо не отправляется."""
        settings.SITE_URL = "http://localhost"
        user = UserFactory(role="trainer", company_name="Club", tax_id="0000000000")

        result = send_manager_region_email(user.id)

        assert result is False
        mock_send_mail.assert_not_called()

    def test_user_not_found(self):
        """Несуществующий пользователь → False без исключения."""
        assert send_manager_region_email(999999) is False

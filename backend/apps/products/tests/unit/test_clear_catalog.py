"""
Тесты для management command clear_catalog.

Ключевая проверка — справочник видов цен переживает чистку каталога.
Импорт priceLists восстанавливает из XML только onec_name, is_active и
product_field; user_role (маппинг «вид цен 1С → роль портала») из выгрузки
не выводится, а миграция 0054 повторно не выполняется — потеря была бы
безвозвратной и полностью бесшумной.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.products.models import Brand, Category, ImportSession, PriceType, Product

pytestmark = [pytest.mark.django_db, pytest.mark.unit]


def _suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def catalog():
    """Минимальный каталог: бренд, категория, товар, сессия импорта."""
    suffix = _suffix()
    brand = Brand.objects.create(name=f"Бренд {suffix}", slug=f"brand-{suffix}")
    category = Category.objects.create(name=f"Категория {suffix}", slug=f"category-{suffix}")
    Product.objects.create(
        name=f"Товар {suffix}",
        slug=f"product-{suffix}",
        brand=brand,
        category=category,
    )
    ImportSession.objects.create(session_key=f"session-{suffix}")


@pytest.fixture(autouse=True)
def clean_price_types(db):
    """
    Тест начинает с пустого справочника.

    Тестовая БД может строиться и с миграциями (тогда 0053 засеяла «Опт 4»,
    а 0054 проставила роли), и без них — тесты не должны зависеть от способа.
    """
    PriceType.objects.all().delete()


@pytest.fixture
def price_types(clean_price_types):
    """Справочник видов цен с ролями, как после миграции 0054."""
    PriceType.objects.create(
        onec_id="90d2c899-b3f2-11ea-81c3-00155d3cae02",
        onec_name="Опт 1 (300-600 тыс.руб в квартал)",
        product_field="opt1_price",
        user_role="wholesale_level1",
    )
    PriceType.objects.create(
        onec_id="3d1482c4-bd77-11e4-afc8-20cf3073dde3",
        onec_name="РРЦ",
        product_field="retail_price",
        user_role="",
    )


def _run_clear_catalog():
    """Прогон команды с ответом «yes» на интерактивное подтверждение."""
    with patch("builtins.input", return_value="yes"):
        call_command("clear_catalog", "--confirm")


class TestClearCatalog:
    def test_requires_confirm_flag(self):
        with pytest.raises(CommandError):
            call_command("clear_catalog")

    def test_aborts_without_interactive_yes(self, catalog):
        with patch("builtins.input", return_value="no"):
            call_command("clear_catalog", "--confirm")

        assert Product.objects.count() == 1, "отказ от подтверждения не должен ничего удалять"

    def test_clears_catalog_entities(self, catalog):
        _run_clear_catalog()

        assert Product.objects.count() == 0
        assert Brand.objects.count() == 0
        assert Category.objects.count() == 0
        assert ImportSession.objects.count() == 0

    def test_keeps_price_type_reference(self, catalog, price_types):
        """Справочник видов цен не относится к каталогу товаров и остаётся."""
        _run_clear_catalog()

        assert PriceType.objects.count() == 2

    def test_keeps_user_role_mapping(self, catalog, price_types):
        """
        Маппинг ролей переживает чистку.

        Иначе после повторного импорта роли молча перестали бы назначаться:
        резолвер отдавал бы unknown_price_type на каждого контрагента.
        """
        _run_clear_catalog()

        opt1 = PriceType.objects.get(onec_id="90d2c899-b3f2-11ea-81c3-00155d3cae02")
        rrc = PriceType.objects.get(onec_id="3d1482c4-bd77-11e4-afc8-20cf3073dde3")

        assert opt1.user_role == "wholesale_level1"
        assert opt1.product_field == "opt1_price"
        assert rrc.user_role == "", "у РРЦ роль намеренно пуста и такой остаётся"

    def test_role_map_survives_for_resolver(self, catalog, price_types):
        """Резолвер после чистки продолжает разрешать роль (сторож 40.2)."""
        from apps.users.services.price_type_role import resolve_role_from_price_types

        _run_clear_catalog()

        result = resolve_role_from_price_types(["90d2c899-b3f2-11ea-81c3-00155d3cae02"])

        assert result.role == "wholesale_level1"
        assert result.reason == "resolved"

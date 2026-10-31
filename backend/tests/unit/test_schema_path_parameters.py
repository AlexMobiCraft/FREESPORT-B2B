"""Регрессия: модель вью определяется без обращения к БД.

drf-spectacular выводит тип path-параметра из модели вью. Модель он ищет сначала в
атрибуте `queryset`, и только если его нет — вызывает `get_queryset()`, гася любое
исключение и молча оставляя параметр строкой без описания.

Из-за этого вью, чей `get_queryset()` выполняет запрос (а не строит ленивый QuerySet),
даёт разную схему в зависимости от доступности БД: локально с накатанными миграциями —
`type: integer`, в CI гейта контракта (`check_openapi_sync`, база пустая) — `type: string`.
Гейт при этом сообщает о рассинхроне контракта, хотя расходится не файл, а окружение.

Тест фиксирует контракт «модель берётся из атрибута»: `get_queryset()` при определении
модели не зовётся вовсе.
"""

from unittest import mock

import pytest
from django.db import DatabaseError
from drf_spectacular.plumbing import get_view_model

from apps.products.models import Category
from apps.products.views import CategoryTreeViewSet


class TestCategoryTreeViewSetModelResolution:
    def test_queryset_attribute_declares_model(self):
        assert CategoryTreeViewSet.queryset is not None
        assert CategoryTreeViewSet.queryset.model is Category

    def test_model_resolves_when_get_queryset_cannot_reach_database(self):
        """Ровно условие CI: таблиц нет, запрос падает — тип параметра меняться не должен."""
        with mock.patch.object(
            CategoryTreeViewSet,
            "get_queryset",
            side_effect=DatabaseError('relation "products_category" does not exist'),
        ):
            assert get_view_model(CategoryTreeViewSet(), emit_warnings=False) is Category

    @pytest.mark.parametrize("view_class", [CategoryTreeViewSet])
    def test_get_queryset_is_not_called_for_model_lookup(self, view_class):
        with mock.patch.object(view_class, "get_queryset") as get_queryset:
            get_view_model(view_class(), emit_warnings=False)
        get_queryset.assert_not_called()

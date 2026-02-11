"""
Service для генерации facets (фасетов) атрибутов товаров

Story 14.6: Filtering & Facets API
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import Count, Q, QuerySet

from ..models import Attribute, AttributeValue, Product

if TYPE_CHECKING:
    pass


class AttributeFacetService:
    """
    Сервис для генерации фасетов (facets) атрибутов товаров

    Фасет - это структура данных, содержащая доступные значения атрибута
    с количеством товаров для каждого значения в текущем результате фильтрации.

    Пример структуры facets:
    {
        "color": [
            {"value": "Красный", "slug": "krasnyj", "count": 10},
            {"value": "Синий", "slug": "sinij", "count": 5}
        ],
        "size": [
            {"value": "XL", "slug": "xl", "count": 8},
            {"value": "L", "slug": "l", "count": 12}
        ]
    }
    """

    @staticmethod
    def get_facets(queryset: QuerySet[Product]) -> dict[str, list[dict[str, Any]]]:
        """
        Генерирует facets для текущего набора товаров

        Агрегирует доступные значения атрибутов с подсчетом количества товаров
        для каждого значения в отфильтрованном queryset.

        Args:
            queryset: Отфильтрованный QuerySet товаров

        Returns:
            Словарь вида:
            {
                "attribute_slug": [
                    {
                        "value": "Значение атрибута",
                        "slug": "slug-znacheniya",
                        "count": 10
                    },
                    ...
                ],
                ...
            }

        Performance:
            - Использует единственный агрегационный запрос с GROUP BY
            - Фильтрует только активные атрибуты
            - Оптимизирован для больших наборов данных
        """
        # Получаем IDs товаров из отфильтрованного queryset
        # Используем values_list для минимизации данных
        product_ids = queryset.values_list("id", flat=True)

        # Если queryset пустой, возвращаем пустые facets
        if not product_ids:
            return {}

        # Агрегация значений атрибутов с подсчетом товаров
        # Фильтруем только по товарам из queryset и активным атрибутам
        attribute_values = (
            AttributeValue.objects.filter(
                # Только значения, связанные с товарами из queryset
                Q(products__id__in=product_ids) | Q(variants__product__id__in=product_ids),
                # Только активные атрибуты
                attribute__is_active=True,
            )
            .select_related("attribute")
            .values(
                "attribute__slug",  # Slug атрибута для группировки
                "value",  # Значение атрибута
                "slug",  # Slug значения
            )
            .annotate(
                # Подсчет уникальных товаров с этим значением
                count=Count("products__id", distinct=True)
                + Count("variants__product__id", distinct=True)
            )
            .order_by("attribute__slug", "-count")  # Сортировка по популярности
        )

        # Группируем результаты по атрибутам
        facets: dict[str, list[dict[str, Any]]] = {}

        for item in attribute_values:
            attr_slug = item["attribute__slug"]

            # Пропускаем значения без подсчета
            if item["count"] == 0:
                continue

            # Инициализируем список значений для атрибута если его еще нет
            if attr_slug not in facets:
                facets[attr_slug] = []

            # Добавляем значение в facets
            facets[attr_slug].append(
                {
                    "value": item["value"],
                    "slug": item["slug"],
                    "count": item["count"],
                }
            )

        return facets

    @staticmethod
    def get_active_attributes() -> QuerySet[Attribute]:
        """
        Получает список всех активных атрибутов для создания фильтров

        Returns:
            QuerySet активных атрибутов с предзагруженными значениями
        """
        return Attribute.objects.filter(is_active=True).prefetch_related("values").order_by("name")

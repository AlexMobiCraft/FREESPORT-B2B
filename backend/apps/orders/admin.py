"""
Django Admin конфигурация для Orders приложения.
Настройки для управления заказами через Django Admin с поддержкой B2B/B2C.
"""

from __future__ import annotations

import csv
from typing import TYPE_CHECKING, Any

from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Order, OrderItem
from .services.order_numbering import build_order_number_search_query

if TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


class OrderItemInline(admin.TabularInline):
    """Inline для отображения позиций заказа."""

    model = OrderItem
    extra = 0
    fields = ["product_name", "product_sku", "quantity", "unit_price", "total_price"]
    readonly_fields = ["total_price"]
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj: Order | None = None) -> bool:
        """Запрещаем добавление новых позиций через admin."""
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Admin конфигурация для модели Order."""

    list_display = [
        "display_order_number",
        "order_number",
        "customer_display",
        "status",
        "payment_status_display",
        "items_count",
        "total_amount",
        "is_master",
        "sent_to_1c",
        "status_1c",
        "created_at",
    ]
    list_select_related = ["user"]
    list_filter = [
        "status",
        "payment_status",
        "delivery_method",
        "is_master",
        "sent_to_1c",
        "created_at",
    ]
    search_fields = [
        "order_number",
        "user__email",
        "customer_email",
        "tracking_number",
    ]
    readonly_fields = ["display_order_number", "order_number", "created_at", "updated_at", "payment_id"]
    inlines = [OrderItemInline]
    actions = ["export_to_csv"]
    date_hierarchy = "created_at"

    fieldsets = (
        (
            "Основная информация",
            {
                "fields": (
                    "display_order_number",
                    "order_number",
                    "user",
                    "status",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "Информация о клиенте",
            {
                "fields": ("customer_name", "customer_email", "customer_phone"),
                "description": "Для гостевых заказов (если user не указан)",
            },
        ),
        (
            "Суммы",
            {"fields": ("total_amount", "discount_amount", "delivery_cost")},
        ),
        (
            "Доставка",
            {
                "fields": (
                    "delivery_address",
                    "delivery_method",
                    "delivery_date",
                    "tracking_number",
                )
            },
        ),
        (
            "Оплата",
            {"fields": ("payment_method", "payment_status", "payment_id")},
        ),
        (
            "Интеграция с 1С",
            {
                "fields": ("sent_to_1c", "sent_to_1c_at", "status_1c"),
            },
        ),
        (
            "VAT / Субзаказы",
            {
                "fields": ("parent_order", "is_master", "vat_group"),
            },
        ),
        (
            "Дополнительная информация",
            {"fields": ("notes",), "classes": ("collapse",)},
        ),
    )

    def get_queryset(self, request: HttpRequest) -> QuerySet[Order]:
        """Оптимизация queryset для предотвращения N+1 запросов."""
        qs = super().get_queryset(request)
        return qs.select_related("user").prefetch_related("items", "sub_orders__items")

    @admin.display(description="Customer", ordering="user__email")
    def customer_display(self, obj: Order) -> str:
        """Отображает email пользователя или информацию о гостевом заказе."""
        if obj.user:
            return str(obj.user.email)
        return obj.customer_email or obj.customer_name or "-"

    @admin.display(description="Display Number")
    def display_order_number(self, obj: Order) -> str:
        return obj.order_number_display

    @admin.display(description="Items Count")
    def items_count(self, obj: Order) -> int:
        """Количество позиций в заказе (для master — из субзаказов)."""
        if obj.is_master and obj.sub_orders.exists():
            return sum(sub.items.count() for sub in obj.sub_orders.all())
        return obj.items.count()

    @admin.display(description="Total Items")
    def total_items_quantity(self, obj: Order) -> int:
        """Общее количество товаров в заказе (для master — из субзаказов)."""
        if obj.is_master and obj.sub_orders.exists():
            return sum(item.quantity for sub in obj.sub_orders.all() for item in sub.items.all())
        return sum(item.quantity for item in obj.items.all())

    @admin.display(description="Payment Status")
    def payment_status_display(self, obj: Order) -> str:
        """Отображение статуса оплаты с цветной иконкой."""
        icons = {
            "paid": '<span style="color: green;">💳 {}</span>',
            "pending": '<span style="color: orange;">⏳ {}</span>',
            "failed": '<span style="color: red;">❌ {}</span>',
            "refunded": '<span style="color: blue;">🔄 {}</span>',
        }
        status_display = obj.get_payment_status_display()
        template = icons.get(obj.payment_status, "{}")
        return format_html(template, status_display)

    def get_search_results(self, request: HttpRequest, queryset: QuerySet[Order], search_term: str):
        base_queryset = queryset
        queryset, use_distinct = super().get_search_results(request, queryset, search_term)
        order_number_query = build_order_number_search_query(search_term)
        if order_number_query is None:
            return queryset, use_distinct
        normalized_queryset = base_queryset.filter(order_number_query)
        return queryset | normalized_queryset, use_distinct

    @admin.action(description="Export selected orders to CSV")
    def export_to_csv(self, request: HttpRequest, queryset: QuerySet[Order]) -> HttpResponse:
        """Экспорт выбранных заказов в CSV файл."""
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = 'attachment; filename="orders_export.csv"'

        writer = csv.writer(response)
        writer.writerow(
            [
                "Order Number",
                "Display Number",
                "Customer",
                "Status",
                "Payment Status",
                "Total Amount",
                "Delivery Method",
                "Created At",
            ]
        )

        # Оптимизация: используем select_related для предотвращения N+1
        for order in queryset.select_related("user"):
            writer.writerow(
                [
                    order.order_number,
                    order.order_number_display,
                    order.customer_display_name,
                    order.get_status_display(),
                    order.get_payment_status_display(),
                    str(order.total_amount),
                    order.get_delivery_method_display(),
                    order.created_at.strftime("%Y-%m-%d %H:%M"),
                ]
            )

        return response

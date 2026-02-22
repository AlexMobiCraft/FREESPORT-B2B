"""
Модели для управления способами доставки.
"""

from __future__ import annotations

from django.db import models


class DeliveryMethod(models.Model):
    """Способ доставки."""

    id = models.CharField(max_length=50, primary_key=True)  # courier, pickup, transport
    name = models.CharField("Название", max_length=100)
    description = models.TextField("Описание", blank=True)
    icon = models.CharField(
        "Иконка",
        max_length=50,
        blank=True,
        help_text="CSS класс иконки или emoji для UI",
    )
    is_available = models.BooleanField("Доступен", default=True)
    sort_order = models.PositiveIntegerField("Порядок сортировки", default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Способ доставки"
        verbose_name_plural = "Способы доставки"
        ordering = ["sort_order", "name"]

    def __str__(self) -> str:
        return self.name

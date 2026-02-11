from __future__ import annotations

from django import forms

from .models import Attribute, Brand


class MergeBrandsActionForm(forms.Form):
    """Форма выбора целевого бренда для объединения"""

    target_brand = forms.ModelChoiceField(
        queryset=Brand.objects.all().order_by("name"),
        label="Целевой бренд",
        help_text=("Выберите бренд, в который будут объединены выбранные бренды. " "Исходные бренды будут удалены."),
        required=True,
    )


class TransferMappingsActionForm(forms.Form):
    """Форма выбора целевого бренда для переноса маппингов"""

    target_brand = forms.ModelChoiceField(
        queryset=Brand.objects.all().order_by("name"),
        label="Целевой бренд",
        help_text="Выберите бренд, к которому будут привязаны выбранные маппинги.",
        required=True,
    )


class MergeAttributesActionForm(forms.Form):
    """Форма выбора целевого атрибута для объединения"""

    target_attribute = forms.ModelChoiceField(
        queryset=Attribute.objects.all().order_by("name"),
        label="Целевой атрибут",
        help_text="Выберите атрибут, в который будут объединены выбранные атрибуты. "
        "Маппинги 1С и значения будут перенесены. Исходные атрибуты будут удалены.",
        required=True,
    )

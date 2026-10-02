from __future__ import annotations

from django import forms

from .models import Attribute, Brand, PriceType


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


class PriceTypeAdminForm(forms.ModelForm):
    """
    Форма справочника видов цен.

    user_role ограничен списком существующих ролей: свободный текст
    позволил бы опечатку («wholesale_level_2»), которую импорт (стори
    40.4) записал бы живому аккаунту без единой ошибки.
    """

    class Meta:
        model = PriceType
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.users.models import User

        self.fields["user_role"] = forms.ChoiceField(
            choices=[("", "— роль не назначается —"), *User.ROLE_CHOICES],
            required=False,
            label="Роль пользователя",
            help_text=(
                "Роль портала, которую получит клиент на этом виде цен. "
                "У «РРЦ» и «МРЦ» поле обязано остаться пустым."
            ),
        )

    def clean_onec_id(self) -> str:
        """
        Нормализует GUID и не даёт завести регистрового двойника.

        Резолвер роли (``apps.users.services.price_type_role``) ищет по GUID
        в нижнем регистре, а уникальность ``onec_id`` в PostgreSQL
        регистрозависима: записи «GUID» и «guid» ужились бы в БД, но дали бы
        один ключ маппинга — и роль стала бы зависеть от порядка выборки.
        """
        onec_id = (self.cleaned_data["onec_id"] or "").strip().lower()

        duplicates = PriceType.objects.filter(onec_id__iexact=onec_id)
        if self.instance.pk:
            duplicates = duplicates.exclude(pk=self.instance.pk)
        if duplicates.exists():
            raise forms.ValidationError("Вид цен с таким UUID уже заведён (возможно, в другом регистре).")

        return onec_id

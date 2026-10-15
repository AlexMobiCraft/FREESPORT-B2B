"""Сериализаторы бонусной программы для личного кабинета тренера."""

from rest_framework import serializers

from apps.bonuses.models import BonusTransaction


class BonusSummarySerializer(serializers.Serializer):
    """Сводка по бонусному счёту тренера."""

    balance = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Текущий баланс")
    total_accrued = serializers.DecimalField(max_digits=12, decimal_places=2, help_text="Всего начислено")
    total_paid_out = serializers.DecimalField(
        max_digits=12, decimal_places=2, help_text="Всего выплачено и списано (положительное число)"
    )
    current_percent = serializers.DecimalField(max_digits=5, decimal_places=2, help_text="Действующий процент")
    is_active = serializers.BooleanField(help_text="Программа активна")


class BonusTransactionSerializer(serializers.ModelSerializer):
    """Операция журнала для истории в личном кабинете."""

    transaction_type_display = serializers.CharField(source="get_transaction_type_display", read_only=True)
    order_id = serializers.IntegerField(source="order.id", read_only=True, allow_null=True)
    # Номер берётся из снимка, если заказ удалён: иначе начисление в истории
    # тренера осталось бы без указания, за что оно сделано
    order_number = serializers.SerializerMethodField()

    def get_order_number(self, obj: BonusTransaction) -> str | None:
        """Номер заказа: живой заказ либо снимок на момент начисления."""
        return obj.order_display or None

    class Meta:
        model = BonusTransaction
        fields = [
            "id",
            "transaction_type",
            "transaction_type_display",
            "amount",
            "order_id",
            "order_number",
            "percent_applied",
            "base_amount",
            "comment",
            "created_at",
        ]
        read_only_fields = fields

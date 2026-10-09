"""Бизнес-логика бонусной программы.

Вынесена из сигналов и админки, чтобы начисление можно было вызвать
и протестировать независимо от источника события (импорт из 1С,
ручная смена статуса в админке).
"""

from __future__ import annotations

import logging
from decimal import ROUND_HALF_UP, Decimal
from typing import TYPE_CHECKING

from django.contrib.auth import get_user_model
from django.db import IntegrityError, connection, transaction
from django.db.models import Sum

from apps.bonuses.models import BonusProgramSettings, BonusTransaction

if TYPE_CHECKING:
    from apps.orders.models import Order
    from apps.users.models import User

logger = logging.getLogger(__name__)

TRAINER_ROLE = "trainer"
"""Роль, участвующая в бонусной программе."""

MONEY_QUANT = Decimal("0.01")


EXCLUDED_SUB_STATUSES = ("cancelled", "refunded")
"""Субзаказы в этих статусах не участвуют в базе начисления."""


def calculate_base(order: "Order") -> Decimal:
    """Сумма товаров, от которой считается бонус.

    Позиции живут в субзаказах — у мастер-заказа своих `OrderItem` нет.
    Fallback на собственные позиции нужен для legacy-мастеров без субзаказов.
    Доставка и скидка в базу не входят.

    Отменённые и возвращённые субзаказы исключаются: мастер со смешанными
    статусами агрегируется в `delivered` (у `cancelled` приоритет 0), и без
    фильтра бонус считался бы за неотгруженный товар.
    """
    from apps.orders.models import OrderItem

    sub_ids = list(order.sub_orders.exclude(status__in=EXCLUDED_SUB_STATUSES).values_list("id", flat=True))
    if sub_ids:
        target_ids = sub_ids
    elif order.sub_orders.exists():
        # Все субзаказы отменены — начислять не за что
        return Decimal("0")
    else:
        target_ids = [order.id]
    base = OrderItem.objects.filter(order_id__in=target_ids).aggregate(total=Sum("total_price"))["total"]
    return base or Decimal("0")


def get_balance(user: "User | int", exclude_pk: int | None = None) -> Decimal:
    """Текущий баланс тренера — сумма всех операций журнала.

    Args:
        user: Пользователь или его id.
        exclude_pk: Исключить операцию с этим pk (используется при
            редактировании существующей операции в админке).
    """
    user_id = user if isinstance(user, int) else user.pk
    queryset = BonusTransaction.objects.filter(user_id=user_id)
    if exclude_pk is not None:
        queryset = queryset.exclude(pk=exclude_pk)
    total = queryset.aggregate(total=Sum("amount"))["total"]
    return total or Decimal("0")


def lock_trainer_account(user_id: int | None) -> None:
    """Блокирует счёт тренера до конца текущей транзакции.

    Точка сериализации для проверки лимита выплаты: без неё две одновременные
    выплаты читают одинаковый баланс и обе проходят проверку. Блокируется
    строка пользователя — она существует всегда, в отличие от строк журнала
    (у тренера без операций блокировать было бы нечего).

    Вне транзакции `select_for_update()` невозможен, поэтому в этом случае
    блокировка пропускается: `full_clean()` вызывают и из кода без транзакции,
    и падать там нельзя. Все пути записи (админка, `create_manual_transaction`)
    транзакцию открывают.
    """
    if user_id is None:
        return
    if not connection.in_atomic_block:
        logger.warning(
            "Проверка баланса тренера %s выполняется без транзакции — блокировка счёта пропущена",
            user_id,
        )
        return
    user_model = get_user_model()
    # values_list + list() гарантируют выполнение SELECT ... FOR UPDATE:
    # exists() Django оборачивает в EXISTS и блокировку теряет
    list(user_model.objects.select_for_update().filter(pk=user_id).values_list("pk", flat=True))


def create_manual_transaction(
    *,
    user: "User | int",
    transaction_type: str,
    amount: Decimal,
    comment: str,
    created_by: "User | int | None" = None,
) -> BonusTransaction:
    """Создаёт ручную операцию (выплату или списание) с полной валидацией.

    Единственный поддерживаемый путь создания ручных операций вне админки:
    открывает транзакцию, блокирует счёт тренера и проверяет лимит выплаты
    в той же транзакции, в которой операция сохраняется.

    Raises:
        ValidationError: сумма не положительна, нет комментария или выплата
            превышает баланс.
    """
    user_id = user if isinstance(user, int) else user.pk
    created_by_id = created_by if isinstance(created_by, int) or created_by is None else created_by.pk

    with transaction.atomic():
        lock_trainer_account(user_id)
        bonus = BonusTransaction(
            user_id=user_id,
            transaction_type=transaction_type,
            amount=amount,
            comment=comment,
            created_by_id=created_by_id,
        )
        bonus.full_clean()
        bonus.save()
    return bonus


def is_eligible(order: "Order", settings: BonusProgramSettings) -> bool:
    """Проверяет, подлежит ли заказ начислению бонуса."""
    if not settings.is_active:
        return False
    if not order.is_master:
        return False
    if order.status != settings.accrual_status:
        return False

    # Отсечка по дате запуска: сигнал висит на post_save любого мастера,
    # а импорт из 1С сохраняет мастера при изменении payment_status.
    # Без отсечки первый же импорт начислил бы бонусы за все старые заказы.
    start_at = settings.program_start_at
    if start_at is not None and order.created_at is not None and order.created_at < start_at:
        return False

    user = order.user
    if user is None:
        return False
    return user.role == TRAINER_ROLE and bool(user.is_verified)


def accrue_for_order(order: "Order") -> BonusTransaction | None:
    """Начисляет бонус по мастер-заказу.

    Идемпотентно: повторный вызов по тому же заказу не создаёт новую операцию.
    Возвращает созданную операцию либо None, если начисление не положено
    или уже существует.
    """
    try:
        # Savepoint охватывает ВСЕ обращения к БД, а не только create():
        # load() — это get_or_create, exists() и агрегация базы тоже ходят в БД.
        # Сигнал срабатывает внутри транзакции импорта из 1С, поэтому любая
        # ошибка вне savepoint пометила бы транзакцию как broken, и весь батч
        # обновлений статусов умер бы с "current transaction is aborted".
        with transaction.atomic():
            settings = BonusProgramSettings.load()
            if not is_eligible(order, settings):
                return None

            # Проверка идёт по снимку номера заказа, а не по FK: после удаления
            # заказа `order` обнуляется, и проверка по FK пропустила бы
            # повторное начисление за то же экономическое событие
            already_accrued = BonusTransaction.objects.filter(
                transaction_type=BonusTransaction.ACCRUAL,
                order_number_snapshot=order.order_number,
            ).exists()
            if already_accrued:
                logger.debug("Бонус по заказу %s уже начислен, пропуск", order.pk)
                return None

            base = calculate_base(order)
            amount = (base * settings.percent / Decimal("100")).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)
            if amount <= 0:
                logger.debug("Заказ %s: база начисления %s, бонус не начисляется", order.pk, base)
                return None

            bonus = BonusTransaction.objects.create(
                user=order.user,
                transaction_type=BonusTransaction.ACCRUAL,
                amount=amount,
                order=order,
                percent_applied=settings.percent,
                base_amount=base,
                comment=f"Начисление по заказу {order.order_number_display}",
            )
    except IntegrityError:
        logger.debug("Бонус по заказу %s уже начислен (гонка), пропуск", order.pk)
        return None

    logger.info(
        "Заказ %s: начислен бонус %s ₽ (%s%% от %s ₽) тренеру %s",
        order.order_number,
        amount,
        settings.percent,
        base,
        order.user_id,
    )
    return bonus

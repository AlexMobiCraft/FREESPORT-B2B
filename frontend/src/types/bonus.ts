/**
 * Типы бонусной программы для тренеров
 *
 * Контракт: docs/api/openapi.yaml (теги Bonuses)
 */

/** Тип операции журнала бонусов */
export type BonusTransactionType = 'accrual' | 'payout' | 'writeoff';

/** Сводка по бонусному счёту тренера */
export interface BonusSummary {
  /** Текущий баланс */
  balance: string;
  /** Всего начислено */
  total_accrued: string;
  /** Всего выплачено и списано (положительное число) */
  total_paid_out: string;
  /** Действующий процент программы */
  current_percent: string;
  /** Программа активна */
  is_active: boolean;
}

/**
 * Операция журнала бонусов.
 * `amount` приходит со знаком: начисление положительное,
 * выплата и списание — отрицательные.
 */
export interface BonusTransaction {
  id: number;
  transaction_type: BonusTransactionType;
  transaction_type_display: string;
  amount: string;
  order_id: number | null;
  order_number: string | null;
  /** Снимок процента на момент начисления */
  percent_applied: string | null;
  /** Снимок стоимости товаров на момент начисления */
  base_amount: string | null;
  comment: string;
  created_at: string;
}

/** Фильтры истории операций */
export interface BonusTransactionFilters {
  page?: number;
  page_size?: number;
  type?: BonusTransactionType;
}

/** Подписи типов операций для UI */
export const BONUS_TYPE_LABELS: Record<BonusTransactionType, string> = {
  accrual: 'Начисление',
  payout: 'Выплата',
  writeoff: 'Списание',
};

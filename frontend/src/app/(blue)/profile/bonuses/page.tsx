/**
 * Bonuses Page
 * Раздел «Бонусы» личного кабинета тренера: сводка по счёту и история операций
 *
 * Терминология — docs/guides/bonus-program-trainers.md
 */

'use client';

import React, { useCallback, useEffect, useRef, useState, Suspense } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import type { AxiosError } from 'axios';
import { Button, Pagination, Spinner } from '@/components/ui';
import bonusService from '@/services/bonusService';
import { BONUS_TYPE_LABELS } from '@/types/bonus';
import type { BonusSummary, BonusTransaction, BonusTransactionType } from '@/types/bonus';

const PAGE_SIZE = 20;

/**
 * Форматирует сумму в рублях со знаком операции
 */
function formatAmount(amount: string): string {
  const value = Number(amount);
  const formatted = new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 2,
  }).format(Math.abs(value));
  return `${value < 0 ? '−' : '+'}${formatted}`;
}

/**
 * Форматирует сумму без знака (для сводки)
 */
function formatMoney(amount: string): string {
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 2,
  }).format(Number(amount));
}

/**
 * Форматирует дату операции
 */
function formatDate(value: string): string {
  return new Date(value).toLocaleDateString('ru-RU', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
  });
}

/**
 * Валидирует тип операции из URL
 */
function parseTypeFilter(value: string | null): BonusTransactionType | 'all' {
  const valid: (BonusTransactionType | 'all')[] = ['all', 'accrual', 'payout', 'writeoff'];
  return valid.includes(value as BonusTransactionType | 'all')
    ? (value as BonusTransactionType | 'all')
    : 'all';
}

/**
 * Валидирует номер страницы из URL
 */
function parsePageNumber(value: string | null): number {
  const page = parseInt(value || '1', 10);
  return isNaN(page) || page < 1 ? 1 : page;
}

/**
 * Собирает строку query-параметров на основе текущих
 */
function buildParams(
  current: ReturnType<typeof useSearchParams>,
  mutate: (params: URLSearchParams) => void
): string {
  const params = current ? new URLSearchParams(current.toString()) : new URLSearchParams();
  mutate(params);
  return params.toString();
}

/**
 * Карточка показателя в сводке
 */
const SummaryTile: React.FC<{ label: string; value: string; accent?: boolean }> = ({
  label,
  value,
  accent = false,
}) => (
  <div className="bg-canvas rounded-xl p-4">
    <p className="text-body-s text-text-secondary">{label}</p>
    <p
      className={`mt-1 font-bold ${accent ? 'text-title-l text-primary' : 'text-title-m text-text-primary'}`}
    >
      {value}
    </p>
  </div>
);

/**
 * Расчёт начисления: «5 % от 80 000 ₽»
 */
function formatCalculation(transaction: BonusTransaction): string {
  if (transaction.percent_applied === null || transaction.base_amount === null) {
    return transaction.comment || '—';
  }
  const percent = Number(transaction.percent_applied);
  return `${percent} % от ${formatMoney(transaction.base_amount)}`;
}

/**
 * Внутренний компонент страницы с useSearchParams
 */
function BonusesPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const typeFilter = parseTypeFilter(searchParams?.get('type') ?? null);
  const currentPage = parsePageNumber(searchParams?.get('page') ?? null);

  const [summary, setSummary] = useState<BonusSummary | null>(null);
  const [transactions, setTransactions] = useState<BonusTransaction[]>([]);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isForbidden, setIsForbidden] = useState(false);

  // Порядковый номер запроса: медленный ответ по прошлому фильтру
  // не должен перерисовать данные поверх актуальных
  const requestSeq = useRef(0);

  const fetchBonuses = useCallback(async () => {
    const seq = ++requestSeq.current;
    setIsLoading(true);
    setError(null);

    try {
      const [summaryData, history] = await Promise.all([
        bonusService.getSummary(),
        bonusService.getTransactions({
          page: currentPage,
          page_size: PAGE_SIZE,
          ...(typeFilter !== 'all' && { type: typeFilter }),
        }),
      ]);

      if (seq !== requestSeq.current) return;

      setSummary(summaryData);
      setTransactions(history.results);
      setTotalPages(Math.max(1, Math.ceil(history.count / PAGE_SIZE)));
    } catch (err) {
      if (seq !== requestSeq.current) return;

      const status = (err as AxiosError)?.response?.status;

      // Страница за пределом истории: DRF отдаёт 404 — молча возвращаемся на первую
      if (status === 404 && currentPage > 1) {
        router.replace(`/profile/bonuses?${buildParams(searchParams, p => p.set('page', '1'))}`, {
          scroll: false,
        });
        return;
      }

      setSummary(null);
      setTransactions([]);

      if (status === 403) {
        setIsForbidden(true);
        return;
      }

      console.error('Failed to fetch bonuses:', err);
      setError('Не удалось загрузить бонусы. Попробуйте обновить страницу.');
    } finally {
      if (seq === requestSeq.current) {
        setIsLoading(false);
      }
    }
  }, [currentPage, typeFilter, router, searchParams]);

  useEffect(() => {
    fetchBonuses();
  }, [fetchBonuses]);

  const updateParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      router.push(`/profile/bonuses?${buildParams(searchParams, mutate)}`, { scroll: false });
    },
    [router, searchParams]
  );

  const handleTypeFilterChange = useCallback(
    (type: BonusTransactionType | 'all') => {
      updateParams(params => {
        params.set('page', '1');
        if (type === 'all') {
          params.delete('type');
        } else {
          params.set('type', type);
        }
      });
    },
    [updateParams]
  );

  const handlePageChange = useCallback(
    (page: number) => {
      updateParams(params => params.set('page', page.toString()));
    },
    [updateParams]
  );

  const filterOptions: { value: BonusTransactionType | 'all'; label: string }[] = [
    { value: 'all', label: 'Все операции' },
    { value: 'accrual', label: BONUS_TYPE_LABELS.accrual },
    { value: 'payout', label: BONUS_TYPE_LABELS.payout },
    { value: 'writeoff', label: BONUS_TYPE_LABELS.writeoff },
  ];

  // Ранний выход только после всех хуков — иначе нарушаются правила хуков
  if (isForbidden) {
    return (
      <div className="w-full py-16 text-center">
        <h1 className="text-title-l font-bold text-text-primary mb-2">Раздел недоступен</h1>
        <p className="text-body-m text-text-secondary">
          Бонусная программа доступна только подтверждённым тренерам.
        </p>
      </div>
    );
  }

  return (
    <div className="w-full">
      <div className="mb-6">
        <h1 className="text-title-l font-bold text-text-primary">Бонусы</h1>
        <p className="text-body-m text-text-secondary mt-1">
          Вознаграждение за выполненные заказы и история операций
        </p>
      </div>

      {error && (
        <div className="p-4 mb-6 bg-accent-danger/10 border border-accent-danger rounded-md">
          <p className="text-body-m text-accent-danger">{error}</p>
          <Button variant="tertiary" size="small" onClick={fetchBonuses} className="mt-2">
            Попробовать снова
          </Button>
        </div>
      )}

      {summary && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-6">
            <SummaryTile label="Текущий баланс" value={formatMoney(summary.balance)} accent />
            <SummaryTile label="Всего начислено" value={formatMoney(summary.total_accrued)} />
            <SummaryTile label="Выплачено и списано" value={formatMoney(summary.total_paid_out)} />
            <SummaryTile
              label="Действующий процент"
              value={`${Number(summary.current_percent)} %`}
            />
          </div>

          {!summary.is_active && (
            <div className="p-4 mb-6 bg-canvas border border-neutral-300 rounded-md">
              <p className="text-body-m text-text-secondary">
                Программа временно приостановлена. Накопленные бонусы сохраняются.
              </p>
            </div>
          )}
        </>
      )}

      <div className="flex flex-wrap gap-2 mb-4">
        {filterOptions.map(option => (
          <button
            key={option.value}
            type="button"
            onClick={() => handleTypeFilterChange(option.value)}
            className={`px-4 py-2 rounded-lg text-body-s transition-colors duration-150 ${
              typeFilter === option.value
                ? 'bg-primary text-white'
                : 'bg-canvas text-neutral-700 hover:bg-neutral-200'
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-16">
          <Spinner size="large" />
        </div>
      ) : transactions.length === 0 ? (
        <div className="py-16 text-center">
          <p className="text-body-m text-text-secondary">
            {typeFilter === 'all'
              ? 'Операций пока нет. Бонусы начисляются после выполнения заказа.'
              : 'Операций этого типа пока нет.'}
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-neutral-300">
                  <th className="py-3 pr-4 text-body-s text-text-secondary font-normal">Дата</th>
                  <th className="py-3 pr-4 text-body-s text-text-secondary font-normal">
                    Операция
                  </th>
                  <th className="py-3 pr-4 text-body-s text-text-secondary font-normal">Заказ</th>
                  <th className="py-3 pr-4 text-body-s text-text-secondary font-normal">Расчёт</th>
                  <th className="py-3 text-body-s text-text-secondary font-normal text-right">
                    Сумма
                  </th>
                </tr>
              </thead>
              <tbody>
                {transactions.map(transaction => (
                  <tr key={transaction.id} className="border-b border-neutral-200">
                    <td className="py-3 pr-4 text-body-s text-text-secondary whitespace-nowrap">
                      {formatDate(transaction.created_at)}
                    </td>
                    <td className="py-3 pr-4 text-body-m text-text-primary whitespace-nowrap">
                      {transaction.transaction_type_display}
                    </td>
                    <td className="py-3 pr-4 text-body-m whitespace-nowrap">
                      {transaction.order_id ? (
                        <Link
                          href={`/profile/orders/${transaction.order_id}`}
                          prefetch={false}
                          className="text-primary hover:underline"
                        >
                          №{transaction.order_number}
                        </Link>
                      ) : transaction.order_number ? (
                        // Заказ удалён: ссылки уже нет, но номер сохранён снимком —
                        // без него тренер не поймёт, за что начислен бонус (§9 руководства)
                        <span className="text-text-secondary">№{transaction.order_number}</span>
                      ) : (
                        <span className="text-text-secondary">—</span>
                      )}
                    </td>
                    <td className="py-3 pr-4 text-body-s text-text-secondary">
                      {formatCalculation(transaction)}
                    </td>
                    <td
                      className={`py-3 text-body-m font-semibold text-right whitespace-nowrap ${
                        Number(transaction.amount) < 0 ? 'text-text-primary' : 'text-accent-success'
                      }`}
                    >
                      {formatAmount(transaction.amount)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {totalPages > 1 && (
            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={handlePageChange}
              className="mt-6"
            />
          )}
        </>
      )}
    </div>
  );
}

/**
 * Страница бонусов с Suspense для useSearchParams
 */
export default function BonusesPage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center py-16">
          <Spinner size="large" />
        </div>
      }
    >
      <BonusesPageContent />
    </Suspense>
  );
}

/**
 * Unit-тесты страницы «Бонусы» (/profile/bonuses)
 *
 * Проверяет:
 * - Сводку по счёту и историю операций
 * - Знак и формат сумм
 * - Ссылку на заказ у начисления
 * - Обработку 403 для не-тренера
 * - Empty state и ошибку загрузки
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import BonusesPage from '../page';
import bonusService from '@/services/bonusService';
import type { BonusSummary, BonusTransaction } from '@/types/bonus';
import type { PaginatedResponse } from '@/types/api';

const mockPush = vi.fn();
const mockReplace = vi.fn();
let mockSearchParams = new URLSearchParams();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
  useSearchParams: () => mockSearchParams,
}));

vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/services/bonusService', () => ({
  default: {
    getSummary: vi.fn(),
    getTransactions: vi.fn(),
  },
}));

const summary: BonusSummary = {
  balance: '3000.00',
  total_accrued: '5000.00',
  total_paid_out: '2000.00',
  current_percent: '5.00',
  is_active: true,
};

const accrual: BonusTransaction = {
  id: 1,
  transaction_type: 'accrual',
  transaction_type_display: 'Начисление',
  amount: '4000.00',
  order_id: 39,
  order_number: '2345-26007',
  percent_applied: '5.00',
  base_amount: '80000.00',
  comment: 'Начисление по заказу',
  created_at: '2026-03-12T10:00:00Z',
};

const payout: BonusTransaction = {
  id: 2,
  transaction_type: 'payout',
  transaction_type_display: 'Выплата',
  amount: '-2000.00',
  order_id: null,
  order_number: null,
  percent_applied: null,
  base_amount: null,
  comment: 'Перевод на карту',
  created_at: '2026-03-20T10:00:00Z',
};

// Заказ удалён: ссылки уже нет, но номер сохранён снимком (§9 руководства)
const accrualForDeletedOrder: BonusTransaction = {
  ...accrual,
  id: 3,
  order_id: null,
  order_number: '2345-26008',
};

function page(results: BonusTransaction[]): PaginatedResponse<BonusTransaction> {
  return { count: results.length, next: null, previous: null, results };
}

describe('BonusesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockSearchParams = new URLSearchParams();
  });

  it('показывает сводку по счёту', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([accrual, payout]));

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByText('Текущий баланс')).toBeInTheDocument();
    });
    expect(screen.getByText('Всего начислено')).toBeInTheDocument();
    expect(screen.getByText('5 %')).toBeInTheDocument();
  });

  it('показывает операции со знаком и расчётом начисления', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([accrual, payout]));

    render(<BonusesPage />);

    // Названия типов есть и в чипах фильтра, поэтому ищем внутри таблицы
    const table = await screen.findByRole('table');
    expect(within(table).getByText('Начисление')).toBeInTheDocument();
    expect(within(table).getByText('Выплата')).toBeInTheDocument();
    expect(within(table).getByText(/5 % от/)).toBeInTheDocument();
    expect(within(table).getByText('Перевод на карту')).toBeInTheDocument();

    // Знак суммы: начисление со знаком «+», выплата со знаком «−»
    expect(within(table).getByText(/^\+/)).toBeInTheDocument();
    expect(within(table).getByText(/^−/)).toBeInTheDocument();
  });

  it('делает номер заказа ссылкой, а у ручной операции показывает прочерк', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([accrual, payout]));

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByRole('link', { name: /2345-26007/ })).toHaveAttribute(
        'href',
        '/profile/orders/39'
      );
    });
    expect(screen.getByText('—')).toBeInTheDocument();
  });

  it('показывает номер удалённого заказа из снимка без ссылки', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([accrualForDeletedOrder]));

    render(<BonusesPage />);

    const table = await screen.findByRole('table');
    // Номер обязан остаться видимым: иначе тренер не поймёт, за что начислен бонус
    expect(within(table).getByText(/2345-26008/)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /2345-26008/ })).not.toBeInTheDocument();
  });

  it('показывает понятное сообщение при 403, а не сетевую ошибку', async () => {
    const forbidden = Object.assign(new Error('Forbidden'), { response: { status: 403 } });
    vi.mocked(bonusService.getSummary).mockRejectedValue(forbidden);
    vi.mocked(bonusService.getTransactions).mockRejectedValue(forbidden);

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByText('Раздел недоступен')).toBeInTheDocument();
    });
    expect(screen.queryByText('Попробовать снова')).not.toBeInTheDocument();
  });

  it('показывает ошибку загрузки с кнопкой повтора при 500', async () => {
    const failure = Object.assign(new Error('Server error'), { response: { status: 500 } });
    vi.mocked(bonusService.getSummary).mockRejectedValue(failure);
    vi.mocked(bonusService.getTransactions).mockRejectedValue(failure);

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Не удалось загрузить бонусы/)).toBeInTheDocument();
    });
    expect(screen.getByText('Попробовать снова')).toBeInTheDocument();
  });

  it('показывает empty state без операций', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([]));

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Операций пока нет/)).toBeInTheDocument();
    });
  });

  it('сообщает о приостановке программы', async () => {
    vi.mocked(bonusService.getSummary).mockResolvedValue({ ...summary, is_active: false });
    vi.mocked(bonusService.getTransactions).mockResolvedValue(page([accrual]));

    render(<BonusesPage />);

    await waitFor(() => {
      expect(screen.getByText(/Программа временно приостановлена/)).toBeInTheDocument();
    });
  });

  it('возвращает на первую страницу, если запрошенная за пределом истории', async () => {
    mockSearchParams = new URLSearchParams('page=5');
    const notFound = Object.assign(new Error('Not found'), { response: { status: 404 } });
    vi.mocked(bonusService.getSummary).mockResolvedValue(summary);
    vi.mocked(bonusService.getTransactions).mockRejectedValue(notFound);

    render(<BonusesPage />);

    await waitFor(() => {
      expect(mockReplace).toHaveBeenCalledWith(expect.stringContaining('page=1'), {
        scroll: false,
      });
    });
  });
});

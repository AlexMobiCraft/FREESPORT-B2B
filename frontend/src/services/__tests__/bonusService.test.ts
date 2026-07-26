/**
 * Tests for bonusService
 * Бонусная программа для тренеров
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import bonusService from '../bonusService';
import apiClient from '../api-client';
import type { BonusSummary, BonusTransaction } from '@/types/bonus';
import type { PaginatedResponse } from '@/types/api';

vi.mock('../api-client');

describe('bonusService', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('getSummary', () => {
    it('должен возвращать сводку по бонусному счёту', async () => {
      const mockSummary: BonusSummary = {
        balance: '3000.00',
        total_accrued: '5000.00',
        total_paid_out: '2000.00',
        current_percent: '5.00',
        is_active: true,
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockSummary });

      const result = await bonusService.getSummary();

      expect(apiClient.get).toHaveBeenCalledWith('/users/bonuses/');
      expect(result).toEqual(mockSummary);
    });

    it('должен пробрасывать ошибку 403 для не-тренера', async () => {
      const error = Object.assign(new Error('Forbidden'), { response: { status: 403 } });
      vi.mocked(apiClient.get).mockRejectedValueOnce(error);

      await expect(bonusService.getSummary()).rejects.toThrow('Forbidden');
    });
  });

  describe('getTransactions', () => {
    const mockPage: PaginatedResponse<BonusTransaction> = {
      count: 1,
      next: null,
      previous: null,
      results: [
        {
          id: 1,
          transaction_type: 'accrual',
          transaction_type_display: 'Начисление',
          amount: '4000.00',
          order_id: 39,
          order_number: '2345-26007',
          percent_applied: '5.00',
          base_amount: '80000.00',
          comment: 'Начисление по заказу 2345-26007',
          created_at: '2026-03-12T10:00:00Z',
        },
      ],
    };

    it('должен запрашивать историю без фильтров', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockPage });

      const result = await bonusService.getTransactions();

      expect(apiClient.get).toHaveBeenCalledWith('/users/bonuses/transactions/', {
        params: undefined,
      });
      expect(result.results).toHaveLength(1);
    });

    it('должен передавать фильтр по типу и пагинацию', async () => {
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: mockPage });

      await bonusService.getTransactions({ page: 2, page_size: 20, type: 'payout' });

      expect(apiClient.get).toHaveBeenCalledWith('/users/bonuses/transactions/', {
        params: { page: 2, page_size: 20, type: 'payout' },
      });
    });

    it('должен сохранять отрицательный знак у выплат', async () => {
      const payoutPage: PaginatedResponse<BonusTransaction> = {
        ...mockPage,
        results: [
          {
            ...mockPage.results[0],
            id: 2,
            transaction_type: 'payout',
            transaction_type_display: 'Выплата',
            amount: '-2000.00',
            order_id: null,
            order_number: null,
            percent_applied: null,
            base_amount: null,
            comment: 'Перевод на карту',
          },
        ],
      };
      vi.mocked(apiClient.get).mockResolvedValueOnce({ data: payoutPage });

      const result = await bonusService.getTransactions({ type: 'payout' });

      expect(result.results[0].amount).toBe('-2000.00');
      expect(result.results[0].order_id).toBeNull();
    });
  });
});

/**
 * Bonus Service — бонусная программа для тренеров
 *
 * HTTP только через общий apiClient (JWT interceptor + auto-refresh).
 */

import apiClient from './api-client';
import type { PaginatedResponse } from '@/types/api';
import type { BonusSummary, BonusTransaction, BonusTransactionFilters } from '@/types/bonus';

class BonusService {
  /**
   * Сводка по счёту: баланс, начислено, выплачено, действующий процент.
   */
  async getSummary(): Promise<BonusSummary> {
    const response = await apiClient.get<BonusSummary>('/users/bonuses/');
    return response.data;
  }

  /**
   * История операций с пагинацией и фильтром по типу.
   */
  async getTransactions(
    filters?: BonusTransactionFilters
  ): Promise<PaginatedResponse<BonusTransaction>> {
    const response = await apiClient.get<PaginatedResponse<BonusTransaction>>(
      '/users/bonuses/transactions/',
      { params: filters }
    );
    return response.data;
  }
}

const bonusService = new BonusService();
export default bonusService;

/**
 * Promo Service - методы для работы с промокодами
 *
 * @see Story 26.4: Promo Code Integration
 */

import apiClient from './api-client';
import type { PromoResponse } from '@/types/cart';

/**
 * Сервис для работы с промокодами
 */
class PromoService {
  /**
   * Применить промокод к корзине
   *
   * @param code - Код промокода
   * @param cartTotal - Текущая сумма корзины (для проверки минимальной суммы)
   * @returns PromoResponse с результатом применения
   * @throws Error с user-friendly сообщением при ошибке
   */
  async applyPromo(code: string, cartTotal: number): Promise<PromoResponse> {
    try {
      const response = await apiClient.post<PromoResponse>('/cart/apply-promo/', {
        code: code.toUpperCase(),
        cartTotal,
      });
      return response.data;
    } catch (error) {
      // Извлекаем user-friendly сообщение об ошибке
      if (error && typeof error === 'object' && 'response' in error) {
        const axiosError = error as { response?: { data?: { error?: string } } };
        const errorMessage = axiosError.response?.data?.error;
        if (errorMessage) {
          return { success: false, error: errorMessage };
        }
      }
      return { success: false, error: 'Не удалось применить промокод. Попробуйте позже.' };
    }
  }

  /**
   * Очистить примененный промокод
   * Выполняется локально в store, API не требуется
   */
  async clearPromo(): Promise<void> {
    // Промокод хранится только в клиентском состоянии
    // При необходимости можно добавить API вызов
    return Promise.resolve();
  }

  /**
   * Валидация формата промокода
   * @param code - Код для валидации
   * @returns true если формат валидный
   */
  validateFormat(code: string): boolean {
    // Минимум 4 символа, только буквы и цифры
    return /^[A-Z0-9]{4,}$/i.test(code);
  }
}

const promoService = new PromoService();
export default promoService;

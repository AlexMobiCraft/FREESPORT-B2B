/**
 * Delivery Service - методы для работы с доставкой
 * Story 15.3b: Frontend DeliveryOptions Component
 */

import apiClient from './api-client';
import type { DeliveryMethod } from '@/types/delivery';

export const deliveryService = {
  /**
   * Получить список доступных способов доставки
   */
  async getDeliveryMethods(): Promise<DeliveryMethod[]> {
    const response = await apiClient.get<DeliveryMethod[]>('/delivery/methods/');
    return response.data;
  },
};

export default deliveryService;

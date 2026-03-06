/**
 * Orders Service - методы для работы с заказами
 * Story 15.2: Интеграция с Orders API
 *
 * Features:
 * - Создание заказа с маппингом CheckoutFormData -> CreateOrderPayload
 * - Обработка ошибок (400, 401, 500)
 * - Retry логика встроена в apiClient (exponential backoff)
 */

import apiClient from './api-client';
import type { CheckoutFormData } from '@/schemas/checkoutSchema';
import type { CartItem } from '@/types/cart';
import type {
  Order,
  CreateOrderPayload,
  CreateOrderResponse,
  OrderValidationError,
  OrderAuthError,
} from '@/types/order';
import type { PaginatedResponse } from '@/types/api';
import { AxiosError } from 'axios';

/**
 * Фильтры для списка заказов
 * Story 16.2: Расширены для поддержки фильтрации по статусу
 */
export interface OrderFilters {
  page?: number;
  page_size?: number;
  status?: string; // pending | processing | shipped | delivered | cancelled
}

/**
 * Маппинг CheckoutFormData -> CreateOrderPayload
 * Преобразует данные формы в формат API
 */
function mapFormDataToPayload(
  formData: CheckoutFormData,
  cartItems: CartItem[]
): CreateOrderPayload {
  return {
    email: formData.email,
    phone: formData.phone,
    first_name: formData.firstName,
    last_name: formData.lastName,
    delivery_address: `${formData.postalCode}, г. ${formData.city}, ул. ${formData.street}, д. ${formData.house}${
      formData.buildingSection ? `, корп. ${formData.buildingSection}` : ''
    }${formData.apartment ? `, кв. ${formData.apartment}` : ''}`,
    delivery_method: formData.deliveryMethod,
    payment_method: formData.paymentMethod,
    items: cartItems.map(item => ({
      variant_id: item.variant_id,
      quantity: item.quantity,
    })),
    comment: formData.comment || undefined,
  };
}

/**
 * Парсинг ошибки API в читаемое сообщение
 */
function parseApiError(
  error: AxiosError<
    OrderValidationError | OrderAuthError | { error?: string; message?: string; detail?: string }
  >
): string {
  const status = error.response?.status;
  const data = error.response?.data;

  // 400 Bad Request - валидационные ошибки
  if (status === 400) {
    console.error('API Validation Error:', JSON.stringify(data, null, 2));

    if (data && 'error' in data && typeof data.error === 'string') {
      return data.error;
    }

    if (data && 'detail' in data && typeof data.detail === 'string') {
      return data.detail;
    }

    if (data && typeof data === 'object') {
      const firstErrorKey = Object.keys(data)[0];
      if (firstErrorKey) {
        const messages = (data as Record<string, unknown>)[firstErrorKey];
        if (Array.isArray(messages) && messages.length > 0 && typeof messages[0] === 'string') {
          return `${firstErrorKey}: ${messages[0]}`;
        }
        if (typeof messages === 'string') {
          return `${firstErrorKey}: ${messages}`;
        }
      }
    }

    return `Ошибка валидации: ${JSON.stringify(data)}`;
  }

  if (status === 401) {
    return 'Сессия истекла. Войдите заново.';
  }

  if (status && status >= 500) {
    return 'Ошибка сервера. Попробуйте позже.';
  }

  if (error.code === 'ECONNREFUSED' || error.code === 'ETIMEDOUT') {
    return 'Ошибка сети. Проверьте подключение к интернету.';
  }

  return 'Ошибка создания заказа. Попробуйте снова.';
}

class OrdersService {
  /**
   * Создать новый заказ
   */
  async createOrder(formData: CheckoutFormData, cartItems: CartItem[]): Promise<Order> {
    if (!cartItems || cartItems.length === 0) {
      throw new Error('Корзина пуста, невозможно оформить заказ');
    }

    const payload = mapFormDataToPayload(formData, cartItems);

    try {
      const response = await apiClient.post<CreateOrderResponse>('/orders/', payload);
      return response.data;
    } catch (error) {
      const axiosError = error as AxiosError<OrderValidationError>;
      const message = parseApiError(axiosError);
      throw new Error(message);
    }
  }

  /**
   * Получить список заказов с пагинацией
   */
  async getAll(filters?: OrderFilters): Promise<PaginatedResponse<Order>> {
    const response = await apiClient.get<PaginatedResponse<Order>>('/orders/', {
      params: filters,
    });
    return response.data;
  }

  /**
   * Получить заказ по ID
   */
  async getById(orderId: string): Promise<Order> {
    const response = await apiClient.get<Order>(`/orders/${orderId}/`);
    return response.data;
  }
}

const ordersService = new OrdersService();
export default ordersService;

export { mapFormDataToPayload, parseApiError };

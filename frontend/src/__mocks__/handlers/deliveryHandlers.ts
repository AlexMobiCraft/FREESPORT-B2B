/**
 * MSW Handlers для Delivery API
 * Story 15.3b: Frontend DeliveryOptions Component
 */

import { http, HttpResponse } from 'msw';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001/api/v1';

/**
 * Mock данные для способов доставки
 */
export const mockDeliveryMethods = [
  {
    id: 'courier',
    name: 'Курьер',
    description: 'Доставка курьером до двери. Стоимость уточняется администратором.',
    icon: 'truck',
    is_available: true,
  },
  {
    id: 'pickup',
    name: 'Самовывоз',
    description: 'Забрать заказ самостоятельно из пункта выдачи.',
    icon: 'store',
    is_available: true,
  },
  {
    id: 'transport_company',
    name: 'Транспортная компания',
    description: 'Доставка через CDEK, Boxberry и другие службы. Стоимость уточняется.',
    icon: 'package',
    is_available: true,
  },
];

/**
 * Delivery API Handlers
 */
export const deliveryHandlers = [
  // GET /delivery/methods/ - Список способов доставки
  http.get(`${API_BASE_URL}/delivery/methods/`, () => {
    return HttpResponse.json(mockDeliveryMethods);
  }),

  // Wildcard handler для совместимости
  http.get('*/delivery/methods/', () => {
    return HttpResponse.json(mockDeliveryMethods);
  }),
];

/**
 * Error handlers для тестирования error states
 */
export const deliveryErrorHandlers = {
  // 500 Server Error
  serverError500: http.get(`${API_BASE_URL}/delivery/methods/`, () => {
    return HttpResponse.json({ detail: 'Internal server error' }, { status: 500 });
  }),

  // Network error
  networkError: http.get(`${API_BASE_URL}/delivery/methods/`, () => {
    return HttpResponse.error();
  }),

  // Empty response
  emptyResponse: http.get(`${API_BASE_URL}/delivery/methods/`, () => {
    return HttpResponse.json([]);
  }),
};

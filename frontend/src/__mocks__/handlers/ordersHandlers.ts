/**
 * MSW Handlers для Orders API
 * Story 15.2: Интеграция с Orders API
 * Story 16.2: История заказов с функцией повторного заказа
 * Story 34-2: VAT-split контракт (customer_*, notes, discount_amount; items не передаются)
 */

import { http, HttpResponse } from 'msw';
import type { OrderListItem } from '@/types/order';

/**
 * Mock данные успешного заказа (контракт OrderDetailSerializer, Story 34-2)
 */
export const mockSuccessOrder = {
  id: 1,
  order_number: '0462026007',
  user: 1,
  customer_display_name: 'Тест Пользователь',
  customer_name: 'Тест Пользователь',
  customer_email: 'test@example.com',
  customer_phone: '+79001234567',
  status: 'pending' as const,
  total_amount: '15500',
  discount_amount: '0',
  delivery_cost: '500',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1, кв. 10',
  delivery_method: 'courier' as const,
  delivery_date: null,
  tracking_number: '',
  payment_method: 'card',
  payment_status: 'pending',
  payment_id: '',
  notes: '',
  created_at: '2025-01-15T10:30:00Z',
  updated_at: '2025-01-15T10:30:00Z',
  items: [
    {
      id: 1,
      product: { id: 101, name: 'Кроссовки Nike Air Max' },
      variant: {
        id: 1,
        sku: 'NIKE-AM-001',
        color_name: 'Чёрный',
        size_value: '42',
        is_active: true,
      },
      product_name: 'Кроссовки Nike Air Max',
      product_sku: 'NIKE-AM-001',
      variant_info: 'Размер: 42, Цвет: Чёрный',
      quantity: 2,
      unit_price: '5000',
      total_price: '10000',
    },
    {
      id: 2,
      product: { id: 102, name: 'Футболка Adidas' },
      variant: {
        id: 2,
        sku: 'ADIDAS-TS-002',
        color_name: 'Белый',
        size_value: 'L',
        is_active: true,
      },
      product_name: 'Футболка Adidas',
      product_sku: 'ADIDAS-TS-002',
      variant_info: 'Размер: L, Цвет: Белый',
      quantity: 1,
      unit_price: '5500',
      total_price: '5500',
    },
  ],
  subtotal: '15500',
  total_items: 3,
  calculated_total: '15500',
  can_be_cancelled: true,
  // Story 34-1/34-2: поля 1С и VAT-split (полный контракт OrderDetailSerializer)
  is_master: true,
  vat_group: null,
  sent_to_1c: false,
  sent_to_1c_at: null,
  status_1c: '',
};

/**
 * Mock данные для списка заказов (контракт OrderListSerializer, Story 34-2)
 * Узкий набор полей; соответствует OrderListItem type.
 */
export const mockOrderListItem1: OrderListItem = {
  id: 1,
  user: 1,
  order_number: '0462026007',
  customer_display_name: 'Тест Пользователь',
  status: 'pending',
  total_amount: '15500',
  delivery_method: 'courier',
  payment_method: 'card',
  payment_status: 'pending',
  is_master: true,
  vat_group: null,
  sent_to_1c: false,
  created_at: '2025-01-15T10:30:00Z',
  total_items: 3,
};

export const mockOrdersList: OrderListItem[] = [
  mockOrderListItem1,
  {
    ...mockOrderListItem1,
    id: 2,
    order_number: '0462026008',
    status: 'delivered',
    total_amount: '25000',
    payment_status: 'paid',
    created_at: '2025-01-10T14:00:00Z',
    total_items: 5,
  },
  {
    ...mockOrderListItem1,
    id: 3,
    order_number: '0462026009',
    status: 'shipped',
    total_amount: '8000',
    payment_status: 'paid',
    created_at: '2025-01-12T09:15:00Z',
    total_items: 2,
  },
];

/**
 * Orders API Handlers
 */
export const ordersHandlers = [
  // POST /orders/ - Создание заказа (контракт Story 34-2: customer_*, notes, discount_amount, promo_code)
  http.post('*/orders/', async ({ request }) => {
    const body = (await request.json()) as {
      customer_email?: string;
      customer_phone?: string;
      customer_name?: string;
      delivery_address?: string;
      delivery_method?: string;
      payment_method?: string;
      notes?: string;
      discount_amount?: string;
      promo_code?: string | null; // stub Story 34-2 [Review][Patch]
    };

    if (!body.customer_email) {
      return HttpResponse.json(
        {
          error: 'Validation failed',
          details: {
            customer_email: ['Это поле обязательно.'],
          },
        },
        { status: 400 }
      );
    }

    return HttpResponse.json(mockSuccessOrder, { status: 201 });
  }),

  // GET /orders/ - Список заказов (Story 16.2)
  http.get('*/orders/', ({ request }) => {
    const url = new URL(request.url);
    const status = url.searchParams.get('status');
    const page = parseInt(url.searchParams.get('page') || '1', 10);
    const pageSize = parseInt(url.searchParams.get('page_size') || '20', 10);

    let filteredOrders = [...mockOrdersList];
    if (status) {
      filteredOrders = filteredOrders.filter(order => order.status === status);
    }

    const start = (page - 1) * pageSize;
    const end = start + pageSize;
    const paginatedOrders = filteredOrders.slice(start, end);

    return HttpResponse.json({
      count: filteredOrders.length,
      next: end < filteredOrders.length ? `?page=${page + 1}` : null,
      previous: page > 1 ? `?page=${page - 1}` : null,
      results: paginatedOrders,
    });
  }),

  // GET /orders/:id/ - Получить заказ по ID
  http.get('*/orders/:id/', ({ params }) => {
    const { id } = params;

    if (id === 'not-found' || id === '00000000-0000-0000-0000-000000000000') {
      return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
    }

    // Backend возвращает numeric id; Number() парсит строку URL-параметра
    const numericId = Number(id);
    return HttpResponse.json({
      ...mockSuccessOrder,
      id: Number.isFinite(numericId) ? numericId : mockSuccessOrder.id,
    });
  }),
];

/**
 * Handlers для тестирования ошибок
 */
export const ordersErrorHandlers = {
  validation400: http.post('*/orders/', () => {
    return HttpResponse.json(
      {
        error: 'Validation failed',
        details: {
          items: ['Недостаточно товара на складе'],
        },
      },
      { status: 400 }
    );
  }),

  unauthorized401: http.post('*/orders/', () => {
    return HttpResponse.json(
      {
        error: 'Unauthorized',
        message: 'Token expired',
      },
      { status: 401 }
    );
  }),

  serverError500: http.post('*/orders/', () => {
    return HttpResponse.json(
      {
        error: 'Internal server error',
        message: 'Failed to create order',
      },
      { status: 500 }
    );
  }),

  networkError: http.post('*/orders/', () => {
    return HttpResponse.error();
  }),
};

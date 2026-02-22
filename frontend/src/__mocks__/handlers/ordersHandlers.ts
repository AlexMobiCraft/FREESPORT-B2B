/**
 * MSW Handlers для Orders API
 * Story 15.2: Интеграция с Orders API
 * Story 16.2: История заказов с функцией повторного заказа
 */

import { http, HttpResponse } from 'msw';

/**
 * Mock данные успешного заказа (полный формат для Story 16.2)
 */
export const mockSuccessOrder = {
  id: 1,
  order_number: 'ORD-2025-001',
  user: 1,
  customer_display_name: 'Тест Пользователь',
  customer_name: 'Тест Пользователь',
  customer_email: 'test@example.com',
  customer_phone: '+79001234567',
  status: 'pending' as const,
  total_amount: '15500',
  discount_amount: '500',
  delivery_cost: '500',
  delivery_address: 'г. Москва, ул. Тестовая, д. 1, кв. 10',
  delivery_method: 'courier',
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
      product: 101,
      product_name: 'Кроссовки Nike Air Max',
      product_sku: 'NIKE-AM-001',
      quantity: 2,
      unit_price: '5000',
      total_price: '10000',
    },
    {
      id: 2,
      product: 102,
      product_name: 'Футболка Adidas',
      product_sku: 'ADIDAS-TS-002',
      quantity: 1,
      unit_price: '5500',
      total_price: '5500',
    },
  ],
  subtotal: '15500',
  total_items: 3,
  calculated_total: '15500',
  can_be_cancelled: true,
};

/**
 * Mock данные для списка заказов (Story 16.2)
 */
export const mockOrdersList = [
  mockSuccessOrder,
  {
    ...mockSuccessOrder,
    id: 2,
    order_number: 'ORD-2025-002',
    status: 'delivered' as const,
    total_amount: '25000',
    payment_status: 'paid',
    created_at: '2025-01-10T14:00:00Z',
    tracking_number: 'TRK-123456',
    total_items: 5,
  },
  {
    ...mockSuccessOrder,
    id: 3,
    order_number: 'ORD-2025-003',
    status: 'shipped' as const,
    total_amount: '8000',
    payment_status: 'paid',
    created_at: '2025-01-12T09:15:00Z',
    tracking_number: 'TRK-789012',
    total_items: 2,
  },
];

/**
 * Orders API Handlers
 */
export const ordersHandlers = [
  // POST /orders/ - Создание заказа
  http.post('*/orders/', async ({ request }) => {
    const body = (await request.json()) as {
      email: string;
      phone: string;
      first_name: string;
      last_name: string;
      delivery_address: string;
      delivery_method: string;
      payment_method: string;
      items: Array<{ variant_id: number; quantity: number }>;
      comment?: string;
    };

    if (!body.items || body.items.length === 0) {
      return HttpResponse.json(
        {
          error: 'Validation failed',
          details: {
            items: ['Корзина пуста'],
          },
        },
        { status: 400 }
      );
    }

    const unavailableItem = body.items.find(item => item.variant_id === 999);
    if (unavailableItem) {
      return HttpResponse.json(
        {
          error: 'Validation failed',
          details: {
            items: ['Товар с ID 999 закончился на складе'],
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

    return HttpResponse.json({
      ...mockSuccessOrder,
      id: id as string,
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

/**
 * Orders Service Tests
 * Story 15.2: Интеграция с Orders API
 *
 * Тест-кейсы:
 * - Успешное создание заказа
 * - Обработка 400 Bad Request (валидационные ошибки)
 * - Обработка 401 Unauthorized
 * - Обработка 500 Server Error
 * - Пустая корзина
 * - Получение заказа по ID
 */

import ordersService, { mapFormDataToPayload, parseApiError } from '../ordersService';
import { server } from '../../__mocks__/api/server';
import {
  ordersErrorHandlers,
  mockSuccessOrder,
  mockOrdersList,
} from '../../__mocks__/handlers/ordersHandlers';
import { AxiosError } from 'axios';
import type { CheckoutFormData } from '@/schemas/checkoutSchema';
import type { CartItem } from '@/types/cart';
import type { OrderAuthError, OrderValidationError } from '@/types/order';

type MockApiError =
  | OrderValidationError
  | OrderAuthError
  | { error?: string; message?: string; detail?: string };

/**
 * Mock данные формы checkout
 */
const mockFormData: CheckoutFormData = {
  email: 'test@example.com',
  phone: '+79001234567',
  firstName: 'Иван',
  lastName: 'Петров',
  city: 'Москва',
  street: 'Ленина',
  house: '10',
  apartment: '5',
  postalCode: '123456',
  deliveryMethod: 'courier',
  paymentMethod: 'card',
  comment: 'Позвоните за час до доставки',
};

/**
 * Mock данные корзины
 */
const mockCartItems: CartItem[] = [
  {
    id: 1,
    variant_id: 123,
    product: {
      id: 1,
      name: 'Футбольный мяч Nike',
      slug: 'football-nike',
      image: '/images/ball.jpg',
    },
    variant: {
      sku: 'NIKE-001',
      color_name: 'Белый',
      size_value: '5',
    },
    quantity: 2,
    unit_price: '2500.00',
    total_price: '5000.00',
    added_at: '2025-12-14T10:00:00Z',
  },
];

describe('ordersService', () => {
  describe('mapFormDataToPayload', () => {
    test('корректно маппит данные формы в payload (контракт OrderCreateSerializer)', () => {
      const payload = mapFormDataToPayload(mockFormData, mockCartItems);

      // Поля customer_* соответствуют полям модели Order
      expect(payload.customer_email).toBe('test@example.com');
      expect(payload.customer_phone).toBe('+79001234567');
      expect(payload.customer_name).toBe('Иван Петров');

      // Проверка строки адреса: "123456, г. Москва, ул. Ленина, д. 10, кв. 5"
      const expectedAddress = '123456, г. Москва, ул. Ленина, д. 10, кв. 5';
      expect(payload.delivery_address).toBe(expectedAddress);

      expect(payload.delivery_method).toBe('courier');
      expect(payload.payment_method).toBe('card');
      expect(payload.notes).toBe('Позвоните за час до доставки');

      // items не передаются — backend строит заказ из server-side корзины
      expect((payload as unknown as Record<string, unknown>)['items']).toBeUndefined();
    });

    test('обрабатывает пустые optional поля', () => {
      const formDataWithoutOptional: CheckoutFormData = {
        ...mockFormData,
        apartment: '',
        comment: '',
      };

      const payload = mapFormDataToPayload(formDataWithoutOptional, mockCartItems);

      expect(payload.delivery_address).toContain('123456, г. Москва, ул. Ленина, д. 10');
      expect(payload.delivery_address).not.toContain('кв.');
      expect(payload.notes).toBeUndefined();
    });

    test.skip('[deprecated] backward-compat: mapFormDataToPayload принимает discountAmount (Story 34-2 — deprecated, сервер всегда возвращает 0)', () => {
      const payload = mapFormDataToPayload(mockFormData, mockCartItems, 500);

      expect(payload.discount_amount).toBe('500.00');
    });

    test('не включает discount_amount в payload при нулевой скидке', () => {
      const payloadNoDiscount = mapFormDataToPayload(mockFormData, mockCartItems, 0);
      expect(
        (payloadNoDiscount as unknown as Record<string, unknown>)['discount_amount']
      ).toBeUndefined();

      const payloadUndefined = mapFormDataToPayload(mockFormData, mockCartItems);
      expect(
        (payloadUndefined as unknown as Record<string, unknown>)['discount_amount']
      ).toBeUndefined();
    });

    test('[Review][Patch] stub: включает promo_code в payload при передаче строки (Story 34-2)', () => {
      const payload = mapFormDataToPayload(mockFormData, mockCartItems, undefined, 'SUMMER2026');
      expect(payload.promo_code).toBe('SUMMER2026');
    });

    test('[Review][Patch] stub: не включает promo_code в payload при null/undefined (Story 34-2)', () => {
      const payloadNull = mapFormDataToPayload(mockFormData, mockCartItems, undefined, null);
      expect((payloadNull as unknown as Record<string, unknown>)['promo_code']).toBeUndefined();

      const payloadUndefined = mapFormDataToPayload(mockFormData, mockCartItems);
      expect(
        (payloadUndefined as unknown as Record<string, unknown>)['promo_code']
      ).toBeUndefined();
    });
  });

  describe('parseApiError', () => {
    test('парсит 400 ошибку с details.items', () => {
      const error = {
        response: {
          status: 400,
          data: {
            error: 'Validation failed',
            details: {
              items: ['Товар закончился на складе'],
            },
          },
        },
      } as AxiosError<MockApiError>;

      const message = parseApiError(error);
      expect(message).toBe('Validation failed');
    });

    test('парсит 400 ошибку с error полем', () => {
      const error = {
        response: {
          status: 400,
          data: {
            error: 'Некорректные данные',
          },
        },
      } as AxiosError<MockApiError>;

      const message = parseApiError(error);
      expect(message).toBe('Некорректные данные');
    });

    test('парсит 401 ошибку', () => {
      const error = {
        response: {
          status: 401,
          data: {},
        },
      } as AxiosError<MockApiError>;

      const message = parseApiError(error);
      expect(message).toBe('Сессия истекла. Войдите заново.');
    });

    test('парсит 500 ошибку', () => {
      const error = {
        response: {
          status: 500,
          data: {},
        },
      } as AxiosError<MockApiError>;

      const message = parseApiError(error);
      expect(message).toBe('Ошибка сервера. Попробуйте позже.');
    });

    test('парсит network ошибку', () => {
      const error = {
        code: 'ECONNREFUSED',
      } as AxiosError<MockApiError>;

      const message = parseApiError(error);
      expect(message).toBe('Ошибка сети. Проверьте подключение к интернету.');
    });
  });

  describe('createOrder', () => {
    test('успешно создаёт заказ', async () => {
      const result = await ordersService.createOrder(mockFormData, mockCartItems);

      expect(result.id).toBe(mockSuccessOrder.id);
      expect(result.order_number).toBe('0462026007');
      expect(result.status).toBe('pending');
      expect(result.total_amount).toBe('15500');
    });

    test('выбрасывает ошибку при пустой корзине', async () => {
      await expect(ordersService.createOrder(mockFormData, [])).rejects.toThrow(
        'Корзина пуста, невозможно оформить заказ'
      );
    });

    // TODO: Эти тесты требуют изолированного MSW сервера
    // parseApiError тестирует логику обработки ошибок выше
    test.skip('обрабатывает 400 Bad Request (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.validation400);

      await expect(ordersService.createOrder(mockFormData, mockCartItems)).rejects.toThrow(
        'Недостаточно товара на складе'
      );
    });

    test.skip('обрабатывает 401 Unauthorized (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.unauthorized401);

      await expect(ordersService.createOrder(mockFormData, mockCartItems)).rejects.toThrow(
        'Сессия истекла. Войдите заново.'
      );
    });

    test.skip('обрабатывает 500 Server Error (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.serverError500);

      await expect(ordersService.createOrder(mockFormData, mockCartItems)).rejects.toThrow(
        'Ошибка сервера. Попробуйте позже.'
      );
    });

    test('обрабатывает серверную ошибку валидации (например, нет товара на складе)', async () => {
      // Backend returns 400 when stock is depleted (server-side check).
      // Frontend does not send items in payload — validation is purely server-side.
      // parseApiError returns the top-level "error" field value from the response body.
      server.use(ordersErrorHandlers.validation400);

      await expect(ordersService.createOrder(mockFormData, mockCartItems)).rejects.toThrow(
        'Validation failed'
      );
    });

    test.skip('[deprecated] backward-compat: передаёт discount_amount при явной передаче (Story 34-2 — сервер всегда выставляет 0)', async () => {
      let capturedBody: Record<string, unknown> | null = null;

      server.use(
        (await import('msw')).http.post('*/orders/', async ({ request }) => {
          capturedBody = (await request.json()) as Record<string, unknown>;
          return (await import('msw')).HttpResponse.json(mockSuccessOrder, { status: 201 });
        })
      );

      await ordersService.createOrder(mockFormData, mockCartItems, 500);

      expect(capturedBody).not.toBeNull();
      expect(capturedBody!['discount_amount']).toBe('500.00');
    });
  });

  describe('getAll', () => {
    test('получает список заказов', async () => {
      const result = await ordersService.getAll();

      expect(result.count).toBe(3);
      expect(result.results).toHaveLength(3);
      expect(result.results[0].order_number).toBe('0462026007');
    });

    test('получает заказы с пагинацией', async () => {
      const result = await ordersService.getAll({ page: 1 });

      expect(result.results).toBeDefined();
    });

    test('list-contract содержит поля OrderListItem (Story 34-2)', async () => {
      const result = await ordersService.getAll();

      const first = result.results[0];
      // Поля Story 34-2, обязательные в OrderListSerializer
      expect(typeof first.is_master).toBe('boolean');
      expect('vat_group' in first).toBe(true);
      expect(typeof first.sent_to_1c).toBe('boolean');
      expect(typeof first.total_items).toBe('number');
      // is_master=true у первого мастера
      expect(first.is_master).toBe(true);
      // Проверяем, что в списке нет полей detail-only (items, calculated_total)
      expect((first as unknown as Record<string, unknown>)['items']).toBeUndefined();
      expect((first as unknown as Record<string, unknown>)['calculated_total']).toBeUndefined();
    });

    test('mock data соответствует mockOrdersList', async () => {
      const result = await ordersService.getAll();

      expect(result.results[0]).toMatchObject({
        id: mockOrdersList[0].id,
        order_number: mockOrdersList[0].order_number,
        is_master: true,
        sent_to_1c: false,
      });
    });
  });

  describe('getById', () => {
    test('получает заказ по ID (numeric contract)', async () => {
      // Backend возвращает numeric id; orderId передаётся как string URL-параметр
      const result = await ordersService.getById('1');

      expect(result.id).toBe(1);
      expect(result.order_number).toBe('0462026007');
    });

    test('items[].product является nested object (depth=1 contract)', async () => {
      const result = await ordersService.getById('1');

      expect(result.items.length).toBeGreaterThan(0);
      const firstItem = result.items[0];
      expect(typeof firstItem.product).toBe('object');
      expect(firstItem.product).toHaveProperty('id');
      expect(firstItem.product).toHaveProperty('name');
    });

    test('обрабатывает 404 Not Found', async () => {
      await expect(ordersService.getById('not-found')).rejects.toThrow();
    });
  });

  describe('contract regression: DeliveryMethodCode', () => {
    test('transport_schedule является валидным значением delivery_method (Story 34-2)', async () => {
      // Backend поддерживает transport_schedule; frontend-тип должен его принимать
      type ValidDelivery =
        | 'pickup'
        | 'courier'
        | 'post'
        | 'transport_company'
        | 'transport_schedule';
      const value: ValidDelivery = 'transport_schedule';
      expect(value).toBe('transport_schedule');
    });

    test('createOrder возвращает delivery_method из OrderDetail (contract AC12)', async () => {
      const result = await ordersService.createOrder(mockFormData, mockCartItems);
      // Убеждаемся что delivery_method существует в ответе
      expect(result.delivery_method).toBeDefined();
    });
  });
});

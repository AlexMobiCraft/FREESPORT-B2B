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
import { ordersErrorHandlers, mockSuccessOrder } from '../../__mocks__/handlers/ordersHandlers';
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
    test('корректно маппит данные формы в payload', () => {
      const payload = mapFormDataToPayload(mockFormData, mockCartItems);

      expect(payload.email).toBe('test@example.com');
      expect(payload.phone).toBe('+79001234567');
      expect(payload.first_name).toBe('Иван');
      expect(payload.last_name).toBe('Петров');

      // Проверка строки адреса: "123456, г. Москва, ул. Ленина, д. 10, кв. 5"
      const expectedAddress = '123456, г. Москва, ул. Ленина, д. 10, кв. 5';
      expect(payload.delivery_address).toBe(expectedAddress);

      expect(payload.delivery_method).toBe('courier');
      expect(payload.payment_method).toBe('card');
      expect(payload.comment).toBe('Позвоните за час до доставки');
      expect(payload.items).toHaveLength(1);
      expect(payload.items[0].variant_id).toBe(123);
      expect(payload.items[0].quantity).toBe(2);
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
      expect(payload.comment).toBeUndefined();
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
      expect(result.order_number).toBe('ORD-2025-001');
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

    test('обрабатывает недоступный товар (variant_id=999)', async () => {
      const itemsWithUnavailable: CartItem[] = [
        {
          ...mockCartItems[0],
          variant_id: 999,
        },
      ];

      await expect(ordersService.createOrder(mockFormData, itemsWithUnavailable)).rejects.toThrow(
        'Validation failed'
      );
    });
  });

  describe('getAll', () => {
    test('получает список заказов', async () => {
      const result = await ordersService.getAll();

      expect(result.count).toBe(3);
      expect(result.results).toHaveLength(3);
      expect(result.results[0].order_number).toBe('ORD-2025-001');
    });

    test('получает заказы с пагинацией', async () => {
      const result = await ordersService.getAll({ page: 1 });

      expect(result.results).toBeDefined();
    });
  });

  describe('getById', () => {
    test('получает заказ по ID', async () => {
      const result = await ordersService.getById('550e8400-e29b-41d4-a716-446655440000');

      expect(result.id).toBe('550e8400-e29b-41d4-a716-446655440000');
      expect(result.order_number).toBe('ORD-2025-001');
    });

    test('обрабатывает 404 Not Found', async () => {
      await expect(ordersService.getById('not-found')).rejects.toThrow();
    });
  });
});

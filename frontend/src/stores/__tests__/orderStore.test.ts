/**
 * Order Store Tests
 * Story 15.2: Интеграция с Orders API
 *
 * Тест-кейсы:
 * - createOrder успешно создаёт заказ и очищает корзину
 * - createOrder сохраняет ошибку при сбое
 * - isSubmitting изменяется корректно (true → false)
 * - clearOrder сбрасывает currentOrder в null
 * - setError устанавливает ошибку
 */

import { act } from 'react';
import { http, HttpResponse } from 'msw';
import { useOrderStore } from '../orderStore';
import { useCartStore } from '../cartStore';
import { server } from '../../__mocks__/api/server';
import {
  ordersErrorHandlers,
  mockPricesChangedBody,
  mockSuccessOrder,
} from '../../__mocks__/handlers/ordersHandlers';
import type { CheckoutFormData } from '@/schemas/checkoutSchema';
import type { CartItem } from '@/types/cart';

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
  comment: 'Комментарий к заказу',
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

describe('orderStore', () => {
  // Сброс state перед каждым тестом
  beforeEach(() => {
    // Reset orderStore
    useOrderStore.setState({
      currentOrder: null,
      isSubmitting: false,
      error: null,
      priceChanges: null,
      cartRefreshFailed: false,
      cartRefreshing: false,
    });

    // Setup cartStore с mock данными
    useCartStore.setState({
      items: mockCartItems,
      totalItems: 2,
      totalPrice: 5000,
      isLoading: false,
      error: null,
      promoCode: null,
      discountType: null,
      discountValue: 0,
    });
  });

  describe('initial state', () => {
    test('имеет корректное начальное состояние', () => {
      const state = useOrderStore.getState();

      expect(state.currentOrder).toBeNull();
      expect(state.isSubmitting).toBe(false);
      expect(state.error).toBeNull();
    });
  });

  describe('createOrder', () => {
    test('успешно создаёт заказ', async () => {
      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        await createOrder(mockFormData);
      });

      const state = useOrderStore.getState();
      expect(state.currentOrder).not.toBeNull();
      expect(state.currentOrder?.id).toBe(mockSuccessOrder.id);
      expect(state.currentOrder?.order_number).toBe('0462026007');
      expect(state.currentOrder?.status).toBe('pending');
      expect(state.error).toBeNull();
    });

    test('[Review][Patch] Story 34-2: очищает корзину локально после успешного заказа без повторного API-вызова /cart/clear/', async () => {
      // [Patch 11] Устанавливаем promoCode, чтобы проверить clearPromo() после createOrder
      useCartStore.setState({ promoCode: 'TESTCODE', discountType: 'percent', discountValue: 0 });

      // Track if the /cart/clear/ API endpoint is hit (it must NOT be called)
      let cartClearApiCalled = false;
      server.use(
        http.delete('*/cart/clear/', () => {
          cartClearApiCalled = true;
          return new HttpResponse(null, { status: 204 });
        })
      );

      // Проверяем что корзина не пуста
      expect(useCartStore.getState().items).toHaveLength(1);

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        await createOrder(mockFormData);
      });

      // clearCartLocal() не вызывает API — корзина пуста сразу без мокирования cartService.clear()
      expect(useCartStore.getState().items).toHaveLength(0);
      expect(useCartStore.getState().totalPrice).toBe(0);
      expect(useCartStore.getState().totalItems).toBe(0);
      // [Story 34-2] backend already cleared cart in transaction — no redundant /cart/clear/ call
      expect(cartClearApiCalled).toBe(false);
      // [Patch 9] Сбрасываем MSW handler, чтобы не перехватывал запросы в других тестах
      server.resetHandlers();
      // [Patch 11] clearPromo() должен быть вызван через try-finally в orderStore
      expect(useCartStore.getState().promoCode).toBeNull();
    });

    test('устанавливает isSubmitting в true во время запроса', async () => {
      const { createOrder } = useOrderStore.getState();

      // Проверяем начальное состояние
      expect(useOrderStore.getState().isSubmitting).toBe(false);

      // Запускаем createOrder без await чтобы проверить промежуточное состояние
      const promise = createOrder(mockFormData);

      // isSubmitting должен быть true во время запроса
      expect(useOrderStore.getState().isSubmitting).toBe(true);

      // Ждём завершения
      await act(async () => {
        await promise;
      });

      // После завершения isSubmitting должен быть false
      expect(useOrderStore.getState().isSubmitting).toBe(false);
    });

    // TODO: Требует изолированного MSW - parseApiError тестирует логику обработки ошибок
    test.skip('сохраняет ошибку при сбое API (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.validation400);

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        try {
          await createOrder(mockFormData);
        } catch {
          // Ошибка ожидается
        }
      });

      const state = useOrderStore.getState();
      expect(state.error).toBe('Недостаточно товара на складе');
      expect(state.currentOrder).toBeNull();
      expect(state.isSubmitting).toBe(false);
    });

    test('выбрасывает ошибку при пустой корзине', async () => {
      // Очищаем корзину
      useCartStore.setState({ items: [], totalItems: 0, totalPrice: 0 });

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        try {
          await createOrder(mockFormData);
        } catch (error) {
          expect((error as Error).message).toBe('Корзина пуста, невозможно оформить заказ');
        }
      });

      const state = useOrderStore.getState();
      expect(state.error).toBe('Корзина пуста, невозможно оформить заказ');
    });

    test('передаёт promo_code из cartStore при создании заказа ([Review][Patch] Story 34-2)', async () => {
      useCartStore.setState({
        items: mockCartItems,
        totalItems: 2,
        totalPrice: 5000,
        promoCode: 'SUMMER20',
        discountType: null,
        discountValue: 0,
        isLoading: false,
        error: null,
      });

      let capturedPayload: Record<string, unknown> | null = null;

      server.use(
        http.post('*/orders/', async ({ request }) => {
          capturedPayload = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockSuccessOrder, { status: 201 });
        })
      );

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        await createOrder(mockFormData);
      });

      expect(capturedPayload).not.toBeNull();
      expect(capturedPayload!['promo_code']).toBe('SUMMER20');
    });

    test('не передаёт discount_amount даже при ненулевом getPromoDiscount() ([Review][Patch] Story 34-2 regression)', async () => {
      // promo-система не серверная: orderStore не должен вычислять и отправлять client-side discount_amount
      useCartStore.setState({
        items: mockCartItems,
        totalItems: 2,
        totalPrice: 5000,
        promoCode: 'PROMO10',
        discountType: 'fixed',
        discountValue: 500,
        isLoading: false,
        error: null,
      });

      let capturedPayload: Record<string, unknown> | null = null;

      server.use(
        http.post('*/orders/', async ({ request }) => {
          capturedPayload = (await request.json()) as Record<string, unknown>;
          return HttpResponse.json(mockSuccessOrder, { status: 201 });
        })
      );

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        await createOrder(mockFormData);
      });

      expect(capturedPayload).not.toBeNull();
      // discount_amount НЕ должен приходить от клиента — сервер всегда выставляет 0
      expect(capturedPayload!['discount_amount']).toBeUndefined();
      // promo_code передаётся как stub для будущей серверной promo-системы
      expect(capturedPayload!['promo_code']).toBe('PROMO10');
    });

    test('очищает promoCode из cartStore после успешного создания заказа ([Review][Patch] Story 34-2)', async () => {
      useCartStore.setState({
        items: mockCartItems,
        totalItems: 2,
        totalPrice: 5000,
        promoCode: 'SUMMER20',
        discountType: 'percent',
        discountValue: 10,
        isLoading: false,
        error: null,
      });

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        await createOrder(mockFormData);
      });

      const cartState = useCartStore.getState();
      expect(cartState.promoCode).toBeNull();
      expect(cartState.discountType).toBeNull();
      expect(cartState.discountValue).toBe(0);
    });

    // TODO: Требует изолированного MSW - parseApiError тестирует логику обработки ошибок
    test.skip('сохраняет ошибку 401 при истекшем токене (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.unauthorized401);

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        try {
          await createOrder(mockFormData);
        } catch {
          // Ошибка ожидается
        }
      });

      const state = useOrderStore.getState();
      expect(state.error).toBe('Сессия истекла. Войдите заново.');
    });

    // TODO: Требует изолированного MSW - parseApiError тестирует логику обработки ошибок
    test.skip('сохраняет ошибку 500 при серверной ошибке (requires isolated MSW)', async () => {
      server.use(ordersErrorHandlers.serverError500);

      const { createOrder } = useOrderStore.getState();

      await act(async () => {
        try {
          await createOrder(mockFormData);
        } catch {
          // Ошибка ожидается
        }
      });

      const state = useOrderStore.getState();
      expect(state.error).toBe('Ошибка сервера. Попробуйте позже.');
    });
  });

  describe('clearOrder', () => {
    test('сбрасывает currentOrder в null', async () => {
      // Сначала создаём заказ
      await act(async () => {
        await useOrderStore.getState().createOrder(mockFormData);
      });

      // Проверяем что заказ создан
      expect(useOrderStore.getState().currentOrder).not.toBeNull();

      // Очищаем
      act(() => {
        useOrderStore.getState().clearOrder();
      });

      const state = useOrderStore.getState();
      expect(state.currentOrder).toBeNull();
      expect(state.error).toBeNull();
    });

    test('также очищает error', () => {
      // Устанавливаем ошибку
      useOrderStore.setState({ error: 'Тестовая ошибка' });

      act(() => {
        useOrderStore.getState().clearOrder();
      });

      expect(useOrderStore.getState().error).toBeNull();
    });
  });

  describe('createOrder: 409 prices_changed', () => {
    /** Корзина на сервере после 409: снимок мяча обновлён до 2800 */
    const refreshedCart = {
      id: 1,
      items: [{ ...mockCartItems[0], unit_price: '2800.00', total_price: '5600.00' }],
      total_items: 2,
      total_amount: '5600.00',
      created_at: '2026-11-12T10:00:00Z',
      updated_at: '2026-11-12T10:00:00Z',
    };

    const submit = async () => {
      let thrown: unknown = null;
      await act(async () => {
        try {
          await useOrderStore.getState().createOrder(mockFormData);
        } catch (error) {
          thrown = error;
        }
      });
      return thrown;
    };

    test('сохраняет priceChanges, перезагружает корзину и выставляет сообщение', async () => {
      server.use(
        ordersErrorHandlers.pricesChanged409,
        http.get('*/cart/', () => HttpResponse.json(refreshedCart))
      );

      const thrown = await submit();

      expect(thrown).toBeInstanceOf(Error);
      const state = useOrderStore.getState();
      expect(state.error).toBe('Цены изменились. Проверьте сумму заказа');
      expect(state.priceChanges).toEqual({
        items: mockPricesChangedBody.items,
        items_total: '5600.00',
      });
      expect(state.currentOrder).toBeNull();
      expect(state.isSubmitting).toBe(false);
      expect(useCartStore.getState().items[0].unit_price).toBe('2800.00');
      expect(useCartStore.getState().totalPrice).toBe(5600);
      expect(state.cartRefreshFailed).toBe(false);
    });

    test('при упавшей перезагрузке корзины priceChanges из тела 409 сохранены', async () => {
      server.use(
        ordersErrorHandlers.pricesChanged409,
        // 4xx: apiClient не повторяет запрос (5xx повторил бы с паузами 1/2/4 с)
        http.get('*/cart/', () => HttpResponse.json({ detail: 'boom' }, { status: 404 }))
      );

      await submit();

      expect(useCartStore.getState().error).not.toBeNull();

      const state = useOrderStore.getState();
      expect(state.error).toBe('Цены изменились. Проверьте сумму заказа');
      expect(state.priceChanges?.items_total).toBe('5600.00');
      expect(state.priceChanges?.items).toHaveLength(1);
      expect(state.cartRefreshFailed).toBe(true);
    });

    test('пока корзина не перезагружена, оформление не отправляется', async () => {
      let orderRequests = 0;
      server.use(
        http.post('*/orders/', () => {
          orderRequests += 1;
          return HttpResponse.json(mockSuccessOrder, { status: 201 });
        })
      );
      useOrderStore.setState({ cartRefreshFailed: true });

      const thrown = await submit();

      expect(thrown).toBeInstanceOf(Error);
      expect(orderRequests).toBe(0);
      expect(useOrderStore.getState().currentOrder).toBeNull();
      expect(useOrderStore.getState().error).toMatch(/Обновите корзину/);
      expect(useCartStore.getState().items).toHaveLength(1);
    });

    test('refreshCart: успешная перезагрузка снимает флаг, повторный сбой оставляет', async () => {
      useOrderStore.setState({ cartRefreshFailed: true });
      server.use(
        http.get('*/cart/', () => HttpResponse.json({ detail: 'boom' }, { status: 404 }))
      );

      await act(async () => {
        await useOrderStore.getState().refreshCart();
      });
      expect(useOrderStore.getState().cartRefreshFailed).toBe(true);
      expect(useCartStore.getState().items[0].unit_price).toBe('2500.00');

      server.use(http.get('*/cart/', () => HttpResponse.json(refreshedCart)));
      await act(async () => {
        await useOrderStore.getState().refreshCart();
      });
      expect(useOrderStore.getState().cartRefreshFailed).toBe(false);
      expect(useCartStore.getState().totalPrice).toBe(5600);
    });

    test('clearOrder снимает флаг устаревшей корзины', () => {
      useOrderStore.setState({ cartRefreshFailed: true, cartRefreshing: true });

      act(() => {
        useOrderStore.getState().clearOrder();
      });

      expect(useOrderStore.getState().cartRefreshFailed).toBe(false);
      expect(useOrderStore.getState().cartRefreshing).toBe(false);
    });

    test('сообщение и строки видны сразу, до окончания перезагрузки корзины', async () => {
      let releaseCart: () => void = () => {};
      const cartGate = new Promise<void>(resolve => {
        releaseCart = resolve;
      });
      let cartRequested: () => void = () => {};
      const cartRequestSeen = new Promise<void>(resolve => {
        cartRequested = resolve;
      });
      server.use(
        ordersErrorHandlers.pricesChanged409,
        http.get('*/cart/', async () => {
          cartRequested();
          await cartGate;
          return HttpResponse.json(refreshedCart);
        })
      );

      let pending: Promise<unknown> = Promise.resolve();
      await act(async () => {
        pending = useOrderStore
          .getState()
          .createOrder(mockFormData)
          .catch(error => error);
        await cartRequestSeen;
      });

      // Корзина ещё грузится, а сообщение и строки уже в сторе
      expect(useOrderStore.getState().error).toBe('Цены изменились. Проверьте сумму заказа');
      expect(useOrderStore.getState().priceChanges?.items_total).toBe('5600.00');
      expect(useCartStore.getState().items[0].unit_price).toBe('2500.00');
      // Прежние цены корзины помечены как перезагружаемые, отправка ещё заблокирована
      expect(useOrderStore.getState().cartRefreshing).toBe(true);
      expect(useOrderStore.getState().isSubmitting).toBe(true);

      await act(async () => {
        releaseCart();
        await pending;
      });

      expect(useCartStore.getState().items[0].unit_price).toBe('2800.00');
      expect(useOrderStore.getState().isSubmitting).toBe(false);
      expect(useOrderStore.getState().cartRefreshing).toBe(false);
      expect(useOrderStore.getState().cartRefreshFailed).toBe(false);
    });

    test('refreshCart помечает перезагрузку на время запроса', async () => {
      useOrderStore.setState({ cartRefreshFailed: true });
      let releaseCart: () => void = () => {};
      const cartGate = new Promise<void>(resolve => {
        releaseCart = resolve;
      });
      let cartRequested: () => void = () => {};
      const cartRequestSeen = new Promise<void>(resolve => {
        cartRequested = resolve;
      });
      server.use(
        http.get('*/cart/', async () => {
          cartRequested();
          await cartGate;
          return HttpResponse.json(refreshedCart);
        })
      );

      let pending: Promise<void> = Promise.resolve();
      await act(async () => {
        pending = useOrderStore.getState().refreshCart();
        await cartRequestSeen;
      });
      expect(useOrderStore.getState().cartRefreshing).toBe(true);

      await act(async () => {
        releaseCart();
        await pending;
      });
      expect(useOrderStore.getState().cartRefreshing).toBe(false);
      expect(useOrderStore.getState().cartRefreshFailed).toBe(false);
    });

    test('следующая отправка сбрасывает priceChanges', async () => {
      useOrderStore.setState({
        priceChanges: { items: mockPricesChangedBody.items, items_total: '5600.00' },
      });

      await act(async () => {
        await useOrderStore.getState().createOrder(mockFormData);
      });

      expect(useOrderStore.getState().priceChanges).toBeNull();
      expect(useOrderStore.getState().currentOrder?.id).toBe(mockSuccessOrder.id);
    });

    test('400 price_unavailable не трогает корзину и не заполняет priceChanges', async () => {
      let cartRequests = 0;
      server.use(
        ordersErrorHandlers.priceUnavailable400,
        http.get('*/cart/', () => {
          cartRequests += 1;
          return HttpResponse.json(refreshedCart);
        })
      );

      await submit();

      expect(useOrderStore.getState().error).toBe(
        'Футбольный мяч Nike сейчас недоступен для заказа'
      );
      expect(useOrderStore.getState().priceChanges).toBeNull();
      expect(cartRequests).toBe(0);
      expect(useCartStore.getState().items[0].unit_price).toBe('2500.00');
    });
  });

  describe('setError', () => {
    test('устанавливает ошибку', () => {
      act(() => {
        useOrderStore.getState().setError('Тестовая ошибка');
      });

      expect(useOrderStore.getState().error).toBe('Тестовая ошибка');
    });

    test('очищает ошибку при передаче null', () => {
      // Устанавливаем ошибку
      useOrderStore.setState({ error: 'Тестовая ошибка' });

      act(() => {
        useOrderStore.getState().setError(null);
      });

      expect(useOrderStore.getState().error).toBeNull();
    });
  });
});

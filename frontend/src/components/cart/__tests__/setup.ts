/**
 * Cart Test Setup & Utilities
 *
 * Файл предоставляет:
 * - MSW handlers для Cart API endpoints
 * - Mock фикстуры для cart items
 * - renderWithStore utility для тестирования с Zustand
 * - Server setup для beforeAll/afterEach/afterAll hooks
 *
 * @see Story 26.5: Cart Page Unit & Integration Tests
 */

import React from 'react';
import { render, RenderOptions } from '@testing-library/react';
import { beforeAll, afterEach, afterAll } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { useCartStore } from '@/stores/cartStore';
import type { CartItem, Cart, PromoResponse } from '@/types/cart';

const API_URL = 'http://localhost:8001/api/v1';

// ==================== Mock Fixtures ====================

/**
 * Создаёт mock CartItem для тестов
 * @param overrides - переопределение полей
 */
export const mockCartItem = (overrides: Partial<CartItem> = {}): CartItem => ({
  id: 1,
  variant_id: 100,
  product: {
    id: 10,
    name: 'Кроссовки Nike Air Max',
    slug: 'nike-air-max',
    image: '/images/nike-air-max.jpg',
  },
  variant: {
    sku: 'NK-AM-001',
    color_name: 'Чёрный',
    size_value: '42',
  },
  quantity: 2,
  unit_price: '5990.00',
  total_price: '11980.00',
  added_at: '2025-12-07T12:00:00Z',
  ...overrides,
});

/**
 * Создаёт mock Cart для тестов
 */
export const mockCart = (itemOverrides: Partial<CartItem>[] = []): Cart => {
  const items =
    itemOverrides.length > 0
      ? itemOverrides.map((override, idx) => mockCartItem({ id: idx + 1, ...override }))
      : [mockCartItem()];

  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  const totalAmount = items.reduce((sum, item) => sum + parseFloat(item.total_price), 0);

  return {
    id: 1,
    items,
    total_items: totalItems,
    total_amount: totalAmount.toFixed(2),
    created_at: '2025-12-07T10:00:00Z',
    updated_at: '2025-12-07T12:00:00Z',
  };
};

/**
 * Создаёт несколько mock cart items
 */
export const mockCartItems = (): CartItem[] => [
  mockCartItem({
    id: 1,
    variant_id: 100,
    product: {
      id: 10,
      name: 'Кроссовки Nike Air Max',
      slug: 'nike-air-max',
      image: '/images/nike-air-max.jpg',
    },
    variant: { sku: 'NK-AM-001', color_name: 'Чёрный', size_value: '42' },
    quantity: 2,
    unit_price: '5990.00',
    total_price: '11980.00',
  }),
  mockCartItem({
    id: 2,
    variant_id: 101,
    product: {
      id: 11,
      name: 'Футбольный мяч Adidas',
      slug: 'adidas-ball',
      image: '/images/adidas-ball.jpg',
    },
    variant: { sku: 'AD-BALL-001', color_name: 'Белый', size_value: '5' },
    quantity: 1,
    unit_price: '2500.00',
    total_price: '2500.00',
  }),
];

// ==================== MSW Handlers ====================

/**
 * MSW handlers для Cart API endpoints
 */
export const cartHandlers = [
  // GET /api/v1/cart/ - получить корзину
  http.get(`${API_URL}/cart/`, () => {
    return HttpResponse.json(mockCart());
  }),

  // POST /api/v1/cart/items/ - добавить товар
  http.post(`${API_URL}/cart/items/`, async ({ request }) => {
    const { variant_id, quantity } = (await request.json()) as {
      variant_id: number;
      quantity: number;
    };
    return HttpResponse.json(
      mockCartItem({
        id: Date.now(),
        variant_id,
        quantity,
        total_price: String(5990 * quantity),
      })
    );
  }),

  // PATCH /api/v1/cart/items/:id/ - обновить количество
  http.patch(`${API_URL}/cart/items/:id/`, async ({ params, request }) => {
    const { id } = params;
    const { quantity } = (await request.json()) as { quantity: number };
    return HttpResponse.json(
      mockCartItem({
        id: Number(id),
        quantity,
        total_price: String(5990 * quantity),
      })
    );
  }),

  // DELETE /api/v1/cart/items/:id/ - удалить товар
  http.delete(`${API_URL}/cart/items/:id/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // DELETE /api/v1/cart/ - очистить корзину
  http.delete(`${API_URL}/cart/`, () => {
    return new HttpResponse(null, { status: 204 });
  }),

  // POST /api/v1/promo/apply/ - применить промокод
  http.post(`${API_URL}/promo/apply/`, async ({ request }) => {
    const { code } = (await request.json()) as { code: string; cartTotal: number };

    const promoResponses: Record<string, PromoResponse> = {
      SAVE10: { success: true, code: 'SAVE10', discount_type: 'percent', discount_value: 10 },
      SAVE500: { success: true, code: 'SAVE500', discount_type: 'fixed', discount_value: 500 },
      EXPIRED: { success: false, error: 'Срок действия промокода истёк' },
    };

    const response = promoResponses[code.toUpperCase()] || {
      success: false,
      error: 'Промокод недействителен',
    };
    return HttpResponse.json(response, { status: response.success ? 200 : 400 });
  }),
];

// ==================== MSW Server Setup ====================

/**
 * MSW server для тестов
 */
export const server = setupServer(...cartHandlers);

/**
 * Setup hooks для тестов
 * Вызывается в beforeAll/afterEach/afterAll
 */
export const setupMswServer = () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
};

// ==================== Zustand Store Utilities ====================

/**
 * Начальное состояние cartStore
 */
export const initialCartState = {
  items: [] as CartItem[],
  totalItems: 0,
  totalPrice: 0,
  isLoading: false,
  error: null as string | null,
  promoCode: null as string | null,
  discountType: null as 'percent' | 'fixed' | null,
  discountValue: 0,
};

/**
 * Сбрасывает cartStore в начальное состояние
 */
export const resetCartStore = () => {
  useCartStore.setState(initialCartState);
};

/**
 * Устанавливает состояние cartStore для теста
 */
export const setCartState = (state: Partial<typeof initialCartState>) => {
  useCartStore.setState({
    ...initialCartState,
    ...state,
  });
};

// ==================== Render Utilities ====================

/**
 * Custom render function с предустановленным состоянием cartStore
 *
 * @param ui - React элемент для рендеринга
 * @param initialState - начальное состояние cartStore
 * @param renderOptions - дополнительные опции @testing-library/react render
 *
 * @example
 * ```tsx
 * renderWithStore(<CartSummary />, {
 *   items: [mockCartItem()],
 *   totalPrice: 5990,
 *   totalItems: 2,
 * });
 * ```
 */
export const renderWithStore = (
  ui: React.ReactElement,
  initialState: Partial<typeof initialCartState> = {},
  renderOptions?: Omit<RenderOptions, 'wrapper'>
) => {
  // Reset and set initial state before render
  setCartState(initialState);

  return render(ui, renderOptions);
};

// ==================== Additional Utilities ====================

/**
 * Ожидает изменение состояния store
 */
export const waitForStoreUpdate = (
  predicate: (state: ReturnType<typeof useCartStore.getState>) => boolean,
  timeout = 1000
): Promise<void> => {
  return new Promise((resolve, reject) => {
    const startTime = Date.now();

    const checkState = () => {
      if (predicate(useCartStore.getState())) {
        resolve();
        return;
      }

      if (Date.now() - startTime > timeout) {
        reject(new Error('Timeout waiting for store update'));
        return;
      }

      setTimeout(checkState, 10);
    };

    checkState();
  });
};

/**
 * Создаёт mock для cartService
 */
export const mockCartService = {
  get: () => Promise.resolve(mockCart()),
  add: (variantId: number, quantity: number) =>
    Promise.resolve(mockCartItem({ variant_id: variantId, quantity })),
  update: (itemId: number, quantity: number) =>
    Promise.resolve(mockCartItem({ id: itemId, quantity })),
  remove: () => Promise.resolve(),
  clear: () => Promise.resolve(),
};

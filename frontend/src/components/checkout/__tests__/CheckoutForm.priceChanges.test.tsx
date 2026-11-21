/**
 * Чекаут при ответе 409 `prices_changed` (spec-checkout-price-recalc).
 *
 * Настоящие orderStore, cartStore и ordersService: POST /orders/ отвечает 409
 * через MSW, корзину перезагружает `cartService.get`. Проверяем, что покупатель
 * видит сообщение, строки «было → стало» и новую сумму из тела ответа, сводка
 * показывает обновлённую корзину, а введённые поля формы не потеряны.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import { CheckoutForm } from '../CheckoutForm';
import { useCartStore } from '@/stores/cartStore';
import { useOrderStore } from '@/stores/orderStore';
import cartService from '@/services/cartService';
import { server } from '@/__mocks__/api/server';
import { ordersErrorHandlers } from '@/__mocks__/handlers/ordersHandlers';
import { http, HttpResponse } from 'msw';
import type { Cart, CartItem } from '@/types/cart';

const mockPush = vi.fn();

// Сценарии написаны для включённого выбора способа доставки. Выключенный выбор —
// в `CheckoutForm.deliveryDisabled.test.tsx`.
vi.mock('@/config/checkout', () => ({
  DELIVERY_METHOD_SELECTION_ENABLED: true,
  DEFAULT_DELIVERY_METHOD: 'by_agreement',
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));
vi.mock('@/services/cartService', () => ({
  default: { get: vi.fn() },
}));
vi.mock('@/services/addressService', () => ({
  addressService: {
    getAddresses: vi.fn().mockResolvedValue([]),
    createAddress: vi.fn().mockResolvedValue({}),
    updateAddress: vi.fn(),
    deleteAddress: vi.fn(),
  },
}));
vi.mock('@/services/deliveryService', () => ({
  default: {
    getDeliveryMethods: vi.fn().mockResolvedValue([
      {
        id: 'pickup',
        name: 'Самовывоз',
        description: 'Из магазина',
        icon: '🏪',
        is_available: true,
      },
    ]),
  },
}));
vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() },
}));

/** Корзина до оформления: мяч по снимку 2500 ₽ */
const ballAt2500: CartItem = {
  id: 1,
  variant_id: 123,
  product: { id: 1, name: 'Футбольный мяч Nike', slug: 'football-nike', image: null },
  variant: { sku: 'NIKE-001', color_name: 'Белый', size_value: '5' },
  quantity: 2,
  unit_price: '2500.00',
  total_price: '5000.00',
  added_at: '2026-11-12T10:00:00Z',
};

/** Корзина после 409: сервер обновил снимок до 2800 ₽ */
const refreshedCart: Cart = {
  id: 1,
  items: [{ ...ballAt2500, unit_price: '2800.00', total_price: '5600.00' }],
  total_items: 2,
  total_amount: '5600.00',
  created_at: '2026-11-12T10:00:00Z',
  updated_at: '2026-11-12T10:05:00Z',
};

const cartGet = cartService.get as ReturnType<typeof vi.fn>;

function fillForm() {
  fireEvent.change(screen.getByLabelText('Электронная почта'), {
    target: { value: 'buyer@mail.ru' },
  });
  fireEvent.change(screen.getByLabelText('Телефон'), { target: { value: '+79001112233' } });
  fireEvent.change(screen.getByLabelText('Имя'), { target: { value: 'Алексей' } });
  fireEvent.change(screen.getByLabelText('Фамилия'), { target: { value: 'Смирнов' } });
  fireEvent.change(screen.getByLabelText('Город'), { target: { value: 'Тверь' } });
  fireEvent.change(screen.getByLabelText('Улица'), { target: { value: 'Советская' } });
  fireEvent.change(screen.getByLabelText('Дом'), { target: { value: '7' } });
  fireEvent.change(screen.getByLabelText('Почтовый индекс'), { target: { value: '170000' } });
  fireEvent.change(screen.getByLabelText('Комментарий (необязательно)'), {
    target: { value: 'Позвонить заранее' },
  });
}

async function fillAndSubmit() {
  render(<CheckoutForm user={null} />);
  fillForm();
  await waitFor(() => expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument());
  fireEvent.click(screen.getByLabelText(/Самовывоз/));

  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /оформить заказ/i }));
  });
}

/** Панель ошибки оформления с сообщением о смене цен. */
async function pricesChangedPanel(): Promise<HTMLElement> {
  const title = await screen.findByText('Ошибка оформления заказа');
  return title.closest('[role="alert"]') as HTMLElement;
}

function expectRowsFromConflictBody(panel: HTMLElement) {
  expect(within(panel).getByText('Цены изменились. Проверьте сумму заказа')).toBeInTheDocument();
  const rows = within(panel).getByRole('list', { name: 'Изменившиеся цены' });
  expect(within(rows).getAllByRole('listitem')).toHaveLength(1);
  expect(
    within(rows).getByText(/^Футбольный мяч Nike \(Белый \/ 5\): 2\s?500 ₽ → 2\s?800 ₽$/)
  ).toBeInTheDocument();
  expect(within(panel).getByText(/^Новая сумма товаров: 5\s?600 ₽$/)).toBeInTheDocument();
}

describe('CheckoutForm — 409 «Цены изменились»', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    server.use(ordersErrorHandlers.pricesChanged409);
    useOrderStore.setState({
      currentOrder: null,
      isSubmitting: false,
      error: null,
      priceChanges: null,
      cartRefreshFailed: false,
      cartRefreshing: false,
    });
    useCartStore.setState({
      items: [ballAt2500],
      totalItems: 2,
      totalPrice: 5000,
      isLoading: false,
      error: null,
      promoCode: null,
      discountType: null,
      discountValue: 0,
    });
  });

  it('показывает строки «было → стало», новую сумму и обновлённую корзину; поля формы сохранены', async () => {
    cartGet.mockResolvedValue(refreshedCart);

    await fillAndSubmit();

    expectRowsFromConflictBody(await pricesChangedPanel());
    expect(cartGet).toHaveBeenCalledTimes(1);
    await waitFor(() =>
      expect(screen.getByTestId('total-price-items')).toHaveTextContent(/^5\s?600 ₽$/)
    );
    expect(screen.getByTestId('order-summary-items')).toHaveTextContent(/2 × 2\s?800 ₽/);

    expect(screen.getByLabelText('Электронная почта')).toHaveValue('buyer@mail.ru');
    expect(screen.getByLabelText('Город')).toHaveValue('Тверь');
    expect(screen.getByLabelText('Улица')).toHaveValue('Советская');
    expect(screen.getByLabelText('Комментарий (необязательно)')).toHaveValue('Позвонить заранее');
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('при упавшей перезагрузке корзины строки и сумма из тела 409 всё равно показаны', async () => {
    cartGet.mockRejectedValue(new Error('Ошибка загрузки корзины'));

    await fillAndSubmit();

    expectRowsFromConflictBody(await pricesChangedPanel());
    expect(cartGet).toHaveBeenCalledTimes(1);
    expect(mockPush).not.toHaveBeenCalled();
  });

  it('прежняя сумма не выдаётся за актуальную, оформление заблокировано до перезагрузки корзины', async () => {
    cartGet.mockRejectedValueOnce(new Error('Ошибка загрузки корзины'));

    await fillAndSubmit();

    await screen.findByTestId('prices-outdated');
    const summary = screen.getByTestId('order-summary');
    expect(screen.queryByTestId('total-price-items')).not.toBeInTheDocument();
    expect(screen.queryByTestId('total-price')).not.toBeInTheDocument();
    expect(within(summary).queryByText(/5\s?000 ₽/)).not.toBeInTheDocument();
    expect(within(summary).queryByText(/2\s?500 ₽/)).not.toBeInTheDocument();
    expect(screen.getByTestId('checkout-submit-button')).toBeDisabled();

    cartGet.mockResolvedValueOnce(refreshedCart);
    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: 'Обновить корзину' }));
    });

    await waitFor(() =>
      expect(screen.getByTestId('total-price-items')).toHaveTextContent(/^5\s?600 ₽$/)
    );
    expect(screen.queryByTestId('prices-outdated')).not.toBeInTheDocument();
    expect(screen.getByTestId('checkout-submit-button')).toBeEnabled();
    expect(cartGet).toHaveBeenCalledTimes(2);
  });

  it('пока корзина перезагружается, прежняя сумма скрыта, а оформление заблокировано', async () => {
    let releaseCart: (cart: Cart) => void = () => {};
    cartGet.mockReturnValueOnce(
      new Promise<Cart>(resolve => {
        releaseCart = resolve;
      })
    );

    await fillAndSubmit();

    // 409 получен, GET /cart/ ещё не ответил
    expectRowsFromConflictBody(await pricesChangedPanel());
    expect(cartGet).toHaveBeenCalledTimes(1);
    const summary = screen.getByTestId('order-summary');
    expect(within(summary).getByTestId('prices-refreshing')).toHaveTextContent(
      'Загружаем актуальные цены корзины'
    );
    expect(screen.queryByTestId('prices-outdated')).not.toBeInTheDocument();
    expect(screen.queryByTestId('total-price-items')).not.toBeInTheDocument();
    expect(screen.queryByTestId('total-price')).not.toBeInTheDocument();
    expect(within(summary).queryByText(/5\s?000 ₽/)).not.toBeInTheDocument();
    expect(within(summary).queryByText(/2\s?500 ₽/)).not.toBeInTheDocument();
    expect(screen.getByTestId('checkout-submit-button')).toBeDisabled();

    await act(async () => {
      releaseCart(refreshedCart);
    });

    await waitFor(() =>
      expect(screen.getByTestId('total-price-items')).toHaveTextContent(/^5\s?600 ₽$/)
    );
    expect(screen.queryByTestId('prices-refreshing')).not.toBeInTheDocument();
    expect(screen.getByTestId('checkout-submit-button')).toBeEnabled();
  });

  it('варианты без различающихся характеристик различаются артикулом', async () => {
    const plainA: CartItem = {
      ...ballAt2500,
      variant: { sku: 'NIKE-A', color_name: null, size_value: null },
    };
    const plainB: CartItem = {
      ...ballAt2500,
      id: 2,
      variant_id: 124,
      variant: { sku: 'NIKE-B', color_name: null, size_value: null },
      quantity: 1,
      unit_price: '2400.00',
      total_price: '2400.00',
    };
    const glove: CartItem = {
      ...ballAt2500,
      id: 3,
      variant_id: 125,
      product: { id: 2, name: 'Перчатки вратарские', slug: 'gloves', image: null },
      variant: { sku: 'GLV-1', color_name: null, size_value: null },
      quantity: 1,
      unit_price: '1000.00',
      total_price: '1000.00',
    };
    useCartStore.setState({ items: [plainA, plainB, glove], totalItems: 4, totalPrice: 8400 });
    server.use(
      http.post('*/orders/', () =>
        HttpResponse.json(
          {
            code: 'prices_changed',
            detail: 'Цены изменились. Проверьте сумму заказа',
            items: [
              {
                variant_id: 123,
                product_name: 'Футбольный мяч Nike',
                quantity: 2,
                old_price: '2500.00',
                new_price: '2800.00',
              },
              {
                variant_id: 125,
                product_name: 'Перчатки вратарские',
                quantity: 1,
                old_price: '1000.00',
                new_price: '1100.00',
              },
            ],
            items_total: '9100.00',
          },
          { status: 409 }
        )
      )
    );
    cartGet.mockResolvedValue({
      ...refreshedCart,
      items: [
        { ...plainA, unit_price: '2800.00', total_price: '5600.00' },
        plainB,
        { ...glove, unit_price: '1100.00', total_price: '1100.00' },
      ],
      total_items: 4,
      total_amount: '9100.00',
    });

    await fillAndSubmit();

    const rows = within(await pricesChangedPanel()).getByRole('list', {
      name: 'Изменившиеся цены',
    });
    const texts = within(rows)
      .getAllByRole('listitem')
      .map(row => row.textContent?.replace(/\s/g, ' '));
    // Мячей в корзине два и без характеристик — нужен артикул; перчатки однозначны
    expect(texts).toEqual([
      'Футбольный мяч Nike (арт. NIKE-A): 2 500 ₽ → 2 800 ₽',
      'Перчатки вратарские: 1 000 ₽ → 1 100 ₽',
    ]);
  });

  it('варианты одного товара различаются характеристиками из корзины', async () => {
    const size4: CartItem = {
      ...ballAt2500,
      id: 2,
      variant_id: 124,
      variant: { sku: 'NIKE-004', color_name: 'Белый', size_value: '4' },
      quantity: 1,
      unit_price: '2400.00',
      total_price: '2400.00',
    };
    useCartStore.setState({ items: [ballAt2500, size4], totalItems: 3, totalPrice: 7400 });
    server.use(
      http.post('*/orders/', () =>
        HttpResponse.json(
          {
            code: 'prices_changed',
            detail: 'Цены изменились. Проверьте сумму заказа',
            items: [
              {
                variant_id: 123,
                product_name: 'Футбольный мяч Nike',
                quantity: 2,
                old_price: '2500.00',
                new_price: '2800.00',
              },
              {
                variant_id: 124,
                product_name: 'Футбольный мяч Nike',
                quantity: 1,
                old_price: '2400.00',
                new_price: '2600.00',
              },
            ],
            items_total: '8200.00',
          },
          { status: 409 }
        )
      )
    );
    cartGet.mockResolvedValue({
      ...refreshedCart,
      items: [
        { ...ballAt2500, unit_price: '2800.00', total_price: '5600.00' },
        { ...size4, unit_price: '2600.00', total_price: '2600.00' },
      ],
      total_items: 3,
      total_amount: '8200.00',
    });

    await fillAndSubmit();

    const rows = within(await pricesChangedPanel()).getByRole('list', {
      name: 'Изменившиеся цены',
    });
    const texts = within(rows)
      .getAllByRole('listitem')
      .map(row => row.textContent?.replace(/\s/g, ' '));
    expect(texts).toEqual([
      'Футбольный мяч Nike (Белый / 5): 2 500 ₽ → 2 800 ₽',
      'Футбольный мяч Nike (Белый / 4): 2 400 ₽ → 2 600 ₽',
    ]);
  });
});

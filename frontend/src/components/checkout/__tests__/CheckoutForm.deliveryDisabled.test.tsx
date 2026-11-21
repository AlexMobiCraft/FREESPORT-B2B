/**
 * Выбор способа доставки отключён флагом `DELIVERY_METHOD_SELECTION_ENABLED`
 * (spec-disable-checkout-delivery-choice).
 *
 * Пока флаг выключен, вместо радиокнопок — плашка, `/delivery/methods/` не
 * запрашивается, заказ уходит с `delivery_method: 'by_agreement'`, что бы ни
 * лежало в черновике. После включения флага `by_agreement` из черновика
 * сбрасывается, и покупатель выбирает способ сам.
 *
 * Настоящие orderStore и ordersService: тело POST /orders/ снимается с MSW.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { CheckoutForm } from '../CheckoutForm';
import { useCartStore } from '@/stores/cartStore';
import { useOrderStore } from '@/stores/orderStore';
import deliveryService from '@/services/deliveryService';
import { server } from '@/__mocks__/api/server';
import { mockSuccessOrder } from '@/__mocks__/handlers/ordersHandlers';
import { defaultCheckoutFormValues } from '@/schemas/checkoutSchema';
import { clearCheckoutDraft, saveCheckoutDraft } from '@/utils/checkout/checkoutDraft';
import type { CartItem } from '@/types/cart';

const config = vi.hoisted(() => ({ enabled: false }));
const mockPush = vi.hoisted(() => vi.fn());

vi.mock('@/config/checkout', () => ({
  get DELIVERY_METHOD_SELECTION_ENABLED() {
    return config.enabled;
  },
  DEFAULT_DELIVERY_METHOD: 'by_agreement',
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
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

const ball: CartItem = {
  id: 1,
  variant_id: 123,
  product: { id: 1, name: 'Футбольный мяч Nike', slug: 'football-nike', image: null },
  variant: { sku: 'NIKE-001', color_name: 'Белый', size_value: '5' },
  quantity: 2,
  unit_price: '2500.00',
  total_price: '5000.00',
  added_at: '2026-11-16T10:00:00Z',
};

/** Тела POST /orders/, дошедшие до сервера. */
let orderPayloads: Array<Record<string, unknown>>;

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
}

/** Черновик анонима с заполненными полями и заданным способом доставки. */
function saveDraftWithDelivery(deliveryMethod: string) {
  saveCheckoutDraft({
    userId: null,
    values: {
      ...defaultCheckoutFormValues,
      email: 'buyer@mail.ru',
      phone: '+79001112233',
      firstName: 'Алексей',
      lastName: 'Смирнов',
      city: 'Тверь',
      street: 'Советская',
      house: '7',
      postalCode: '170000',
      deliveryMethod,
    },
    selectedAddressId: null,
    saveAddress: false,
  });
}

async function submit() {
  await act(async () => {
    fireEvent.click(screen.getByRole('button', { name: /оформить заказ/i }));
  });
}

describe('CheckoutForm — выбор способа доставки отключён', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    config.enabled = false;
    clearCheckoutDraft();
    orderPayloads = [];
    server.use(
      http.post('*/orders/', async ({ request }) => {
        orderPayloads.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(mockSuccessOrder, { status: 201 });
      })
    );
    useOrderStore.setState({
      currentOrder: null,
      isSubmitting: false,
      error: null,
      priceChanges: null,
      cartRefreshFailed: false,
      cartRefreshing: false,
    });
    useCartStore.setState({
      items: [ball],
      totalItems: 2,
      totalPrice: 5000,
      isLoading: false,
      error: null,
      promoCode: null,
      discountType: null,
      discountValue: 0,
    });
  });

  afterEach(() => {
    clearCheckoutDraft();
  });

  it('показывает плашку вместо радиокнопок и не запрашивает способы доставки', async () => {
    const requested: string[] = [];
    const onRequest = ({ request }: { request: Request }) => {
      requested.push(new URL(request.url).pathname);
    };
    server.events.on('request:start', onRequest);

    try {
      render(<CheckoutForm user={null} />);

      expect(screen.getByText('Способ доставки')).toBeInTheDocument();
      expect(screen.getByTestId('delivery-by-agreement-notice')).toHaveTextContent(
        'Способ и стоимость доставки согласует персональный специалист после оформления заказа.'
      );
      expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument();
      expect(screen.queryByRole('radio')).not.toBeInTheDocument();

      // Даём эффектам отработать: запрос способов не должен появиться и позже.
      await act(async () => {
        await new Promise(resolve => setTimeout(resolve, 0));
      });
      expect(deliveryService.getDeliveryMethods).not.toHaveBeenCalled();
      expect(requested.some(path => path.includes('/delivery/methods'))).toBe(false);
    } finally {
      server.events.removeListener('request:start', onRequest);
    }
  });

  it('заказ уходит с delivery_method by_agreement без выбора способа', async () => {
    render(<CheckoutForm user={null} />);
    fillForm();

    await submit();

    await waitFor(() => expect(orderPayloads).toHaveLength(1));
    expect(orderPayloads[0].delivery_method).toBe('by_agreement');
    await waitFor(() => expect(mockPush).toHaveBeenCalledWith(`/checkout/success/${mockSuccessOrder.id}`));
    expect(screen.queryByText('Выберите способ доставки')).not.toBeInTheDocument();
  });

  it('способ из черновика (courier) заменяется на by_agreement', async () => {
    saveDraftWithDelivery('courier');

    render(<CheckoutForm user={null} />);
    expect(screen.getByLabelText('Город')).toHaveValue('Тверь');

    await submit();

    await waitFor(() => expect(orderPayloads).toHaveLength(1));
    expect(orderPayloads[0].delivery_method).toBe('by_agreement');
  });
});

describe('CheckoutForm — выбор способа доставки возвращён', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    config.enabled = true;
    clearCheckoutDraft();
    orderPayloads = [];
    server.use(
      http.post('*/orders/', async ({ request }) => {
        orderPayloads.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(mockSuccessOrder, { status: 201 });
      })
    );
    useOrderStore.setState({
      currentOrder: null,
      isSubmitting: false,
      error: null,
      priceChanges: null,
      cartRefreshFailed: false,
      cartRefreshing: false,
    });
    useCartStore.setState({
      items: [ball],
      totalItems: 2,
      totalPrice: 5000,
      isLoading: false,
      error: null,
      promoCode: null,
      discountType: null,
      discountValue: 0,
    });
  });

  afterEach(() => {
    config.enabled = false;
    clearCheckoutDraft();
  });

  it('показывает радиокнопки, а плашки нет', async () => {
    render(<CheckoutForm user={null} />);

    await waitFor(() => expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument());
    expect(deliveryService.getDeliveryMethods).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId('delivery-by-agreement-notice')).not.toBeInTheDocument();
  });

  it('обычный способ из черновика восстанавливается', async () => {
    saveDraftWithDelivery('pickup');

    render(<CheckoutForm user={null} />);
    await waitFor(() => expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument());
    expect(screen.getByLabelText(/Самовывоз/)).toBeChecked();

    await submit();

    await waitFor(() => expect(orderPayloads).toHaveLength(1));
    expect(orderPayloads[0].delivery_method).toBe('pickup');
  });

  it('by_agreement из черновика сбрасывается: без выбора заказ не уходит', async () => {
    saveDraftWithDelivery('by_agreement');

    render(<CheckoutForm user={null} />);
    await waitFor(() => expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument());
    expect(screen.getByLabelText(/Самовывоз/)).not.toBeChecked();

    await submit();

    expect(await screen.findByText('Выберите способ доставки')).toBeInTheDocument();
    expect(orderPayloads).toHaveLength(0);

    fireEvent.click(screen.getByLabelText(/Самовывоз/));
    await submit();

    await waitFor(() => expect(orderPayloads).toHaveLength(1));
    expect(orderPayloads[0].delivery_method).toBe('pickup');
  });
});

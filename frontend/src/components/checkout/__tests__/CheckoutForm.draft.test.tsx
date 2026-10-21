/**
 * Регрессия механизма черновика формы оформления заказа (Story 41.4).
 *
 * Ссылка «Условия возврата и рекламаций» уводит пользователя со страницы
 * оформления в текущей вкладке. Без черновика возврат по Back означал бы
 * потерю всего заполненного. Тесты закрепляют три свойства механизма:
 * сохранение перед переходом, восстановление после возврата и одноразовость —
 * черновик не должен всплывать при следующем независимом заходе в оформление.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { CheckoutForm } from '../CheckoutForm';
import { useCartStore } from '@/stores/cartStore';
import { addressService } from '@/services/addressService';
import { clearCheckoutDraft, readCheckoutDraft } from '@/utils/checkout/checkoutDraft';
import type { User } from '@/types/api';
import type { Address } from '@/types/address';

vi.mock('@/stores/cartStore');
vi.mock('@/stores/orderStore', () => ({
  useOrderStore: Object.assign(
    vi.fn(() => ({
      createOrder: vi.fn(),
      isSubmitting: false,
      error: null,
      clearOrder: vi.fn(),
    })),
    {
      getState: vi.fn(() => ({
        currentOrder: null,
        setError: vi.fn(),
      })),
    }
  ),
}));
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
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

const mockUser: User = {
  id: 1,
  email: 'test@mail.ru',
  first_name: 'Иван',
  last_name: 'Петров',
  phone: '+79001234567',
  role: 'retail',
};

const mockCartItems = [
  {
    id: 1,
    variant_id: 1,
    product: { id: 1, name: 'Test Product', slug: 'test-product', image: null },
    variant: { sku: 'TEST-001', color_name: 'Red', size_value: 'M' },
    quantity: 2,
    unit_price: '100.00',
    total_price: '200.00',
    added_at: new Date().toISOString(),
  },
];

function makeAddress(overrides: Partial<Address> = {}): Address {
  return {
    id: 1,
    address_type: 'shipping',
    full_name: 'Иван Иванов',
    phone: '+79001234567',
    city: 'Москва',
    street: 'Ленина',
    building: '10',
    building_section: '',
    apartment: '5',
    postal_code: '123456',
    is_default: false,
    full_address: '123456, Москва, Ленина, 10, кв. 5',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

/** Заполняет контактные и адресные поля различимыми значениями. */
function fillForm() {
  fireEvent.change(screen.getByLabelText('Электронная почта'), {
    target: { value: 'draft@mail.ru' },
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

/** Ссылка на условия возврата внутри сводки заказа. */
function returnsLink(): HTMLAnchorElement {
  return screen.getByRole('link', { name: 'Условия возврата и рекламаций' }) as HTMLAnchorElement;
}

/** Проверяет, что поля формы содержат заполненные fillForm значения. */
function expectFormRestored() {
  expect(screen.getByLabelText('Электронная почта')).toHaveValue('draft@mail.ru');
  expect(screen.getByLabelText('Телефон')).toHaveValue('+79001112233');
  expect(screen.getByLabelText('Имя')).toHaveValue('Алексей');
  expect(screen.getByLabelText('Фамилия')).toHaveValue('Смирнов');
  expect(screen.getByLabelText('Город')).toHaveValue('Тверь');
  expect(screen.getByLabelText('Улица')).toHaveValue('Советская');
  expect(screen.getByLabelText('Дом')).toHaveValue('7');
  expect(screen.getByLabelText('Почтовый индекс')).toHaveValue('170000');
  expect(screen.getByLabelText('Комментарий (необязательно)')).toHaveValue('Позвонить заранее');
}

describe('CheckoutForm — черновик при переходе к условиям возврата', () => {
  beforeEach(() => {
    clearCheckoutDraft();
    (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      items: mockCartItems,
      totalPrice: 200,
      totalItems: 2,
      fetchCart: vi.fn(),
      getPromoDiscount: vi.fn().mockReturnValue(0),
    });
    (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValue([]);
  });

  it('ссылка на условия ведёт на /partners#returns и живёт внутри формы', () => {
    render(<CheckoutForm user={null} />);

    const link = returnsLink();
    expect(link).toHaveAttribute('href', '/partners#returns');
    expect(link.closest('form')).not.toBeNull();
  });

  it('клик по ссылке сохраняет незавершённый ввод анонима', () => {
    render(<CheckoutForm user={null} />);
    fillForm();

    fireEvent.click(returnsLink());

    const draft = readCheckoutDraft(null);
    expect(draft).not.toBeNull();
    expect(draft?.values.email).toBe('draft@mail.ru');
    expect(draft?.values.city).toBe('Тверь');
    expect(draft?.values.comment).toBe('Позвонить заранее');
  });

  it('после возврата поля восстанавливаются целиком', () => {
    const first = render(<CheckoutForm user={null} />);
    fillForm();
    fireEvent.click(returnsLink());
    first.unmount();

    render(<CheckoutForm user={null} />);

    expectFormRestored();
  });

  it('черновик одноразовый: следующий независимый заход показывает чистую форму', () => {
    const first = render(<CheckoutForm user={null} />);
    fillForm();
    fireEvent.click(returnsLink());
    first.unmount();

    const second = render(<CheckoutForm user={null} />);
    expectFormRestored();
    second.unmount();

    render(<CheckoutForm user={null} />);

    expect(screen.getByLabelText('Электронная почта')).toHaveValue('');
    expect(screen.getByLabelText('Город')).toHaveValue('');
  });

  it('Ctrl-клик и клик средней кнопкой черновик не пишут: форма остаётся на месте', () => {
    render(<CheckoutForm user={null} />);
    fillForm();

    fireEvent.click(returnsLink(), { ctrlKey: true });
    expect(readCheckoutDraft(null)).toBeNull();

    fireEvent.click(returnsLink(), { button: 1 });
    expect(readCheckoutDraft(null)).toBeNull();
  });

  it('клик по другой ссылке сводки черновик не пишет', () => {
    render(<CheckoutForm user={null} />);
    fillForm();

    fireEvent.click(screen.getByRole('link', { name: /Политикой обработки персональных данных/ }));

    expect(readCheckoutDraft(null)).toBeNull();
  });

  it('сохраняет и восстанавливает выбранный адрес и флаг «запомнить адрес»', async () => {
    (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValue([
      makeAddress({ id: 1, is_default: true }),
      makeAddress({ id: 2, city: 'Казань', street: 'Баумана', full_address: 'Казань, Баумана' }),
    ]);

    const first = render(<CheckoutForm user={mockUser} />);
    await waitFor(() => expect(screen.getByTestId('address-selector')).toBeInTheDocument());

    const cards = screen.getAllByTestId('address-card-option');
    fireEvent.click(cards[1]);
    await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Казань'));

    // Ручная правка делает адрес «грязным» — появляется чекбокс «запомнить».
    fireEvent.change(screen.getByLabelText('Дом'), { target: { value: '99' } });
    await waitFor(() =>
      expect(screen.getByTestId('save-address-checkbox-wrapper')).toBeInTheDocument()
    );
    fireEvent.click(screen.getByLabelText('Запомнить этот адрес в профиле'));

    fireEvent.click(returnsLink());

    const draft = readCheckoutDraft(mockUser.id);
    expect(draft?.selectedAddressId).toBe(2);
    expect(draft?.saveAddress).toBe(true);
    expect(draft?.values.house).toBe('99');

    first.unmount();
    render(<CheckoutForm user={mockUser} />);

    await waitFor(() => expect(screen.getByTestId('address-selector')).toBeInTheDocument());
    expect(screen.getByLabelText('Дом')).toHaveValue('99');
    expect(screen.getAllByTestId('address-card-option')[1]).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByLabelText('Запомнить этот адрес в профиле')).toBeChecked();
  });

  it('восстановленный ввод не затирается автозаполнением default-адреса', async () => {
    (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValue([
      makeAddress({ id: 1, is_default: true, city: 'Москва' }),
    ]);

    const first = render(<CheckoutForm user={mockUser} />);
    await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Москва'));

    fireEvent.change(screen.getByLabelText('Город'), { target: { value: 'Тверь' } });
    fireEvent.click(returnsLink());
    first.unmount();

    render(<CheckoutForm user={mockUser} />);

    await waitFor(() => expect(addressService.getAddresses).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.getByLabelText('Город')).toHaveValue('Тверь'));
  });

  it('черновик анонима не попадает в форму авторизованного пользователя', () => {
    const first = render(<CheckoutForm user={null} />);
    fillForm();
    fireEvent.click(returnsLink());
    first.unmount();

    render(<CheckoutForm user={mockUser} />);

    expect(screen.getByLabelText('Электронная почта')).toHaveValue('test@mail.ru');
    expect(screen.getByLabelText('Город')).toHaveValue('');
  });

  it('успешное оформление заказа стирает черновик', async () => {
    const { useOrderStore } = await import('@/stores/orderStore');
    const createOrder = vi.fn().mockResolvedValue(undefined);
    (useOrderStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      createOrder,
      isSubmitting: false,
      error: null,
      clearOrder: vi.fn(),
    });
    (useOrderStore as unknown as { getState: ReturnType<typeof vi.fn> }).getState.mockReturnValue({
      currentOrder: { id: 999 },
      setError: vi.fn(),
    });

    render(<CheckoutForm user={null} />);
    fillForm();
    await waitFor(() => expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument());
    fireEvent.click(screen.getByLabelText(/Самовывоз/));

    fireEvent.click(returnsLink());
    expect(readCheckoutDraft(null)).not.toBeNull();

    await act(async () => {
      fireEvent.click(screen.getByRole('button', { name: /оформить заказ/i }));
    });

    await waitFor(() => expect(createOrder).toHaveBeenCalled());
    expect(readCheckoutDraft(null)).toBeNull();
  });
});

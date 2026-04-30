import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { CheckoutForm } from '../CheckoutForm';
import { useCartStore } from '@/stores/cartStore';
import { addressService } from '@/services/addressService';
import type { User } from '@/types/api';
import type { Address } from '@/types/address';

// Mock зависимостей
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
  useRouter: () => ({
    push: vi.fn(),
  }),
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
  toast: {
    error: vi.fn(),
    success: vi.fn(),
  },
}));

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

describe('CheckoutForm', () => {
  const mockUser: User = {
    id: 1,
    email: 'test@example.com',
    first_name: 'Иван',
    last_name: 'Петров',
    phone: '+79001234567',
    role: 'retail',
  };

  /**
   * Mock структуры CartItem согласно типу из @/types/cart.ts
   * Исправлено по результатам QA review: добавлен product объект,
   * структура variant обновлена с color_name и size_value
   */
  const mockCartItems = [
    {
      id: 1,
      variant_id: 1,
      product: {
        id: 1,
        name: 'Test Product',
        slug: 'test-product',
        image: null,
      },
      variant: {
        sku: 'TEST-001',
        color_name: 'Red',
        size_value: 'M',
      },
      quantity: 2,
      unit_price: '100.00',
      total_price: '200.00',
      added_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      items: mockCartItems,
      totalPrice: 200,
      totalItems: 2,
      fetchCart: vi.fn(),
      getPromoDiscount: vi.fn().mockReturnValue(0),
    });
  });

  describe('Rendering', () => {
    it('должен отображать все секции формы', () => {
      render(<CheckoutForm user={null} />);

      expect(screen.getByText('Контактные данные')).toBeInTheDocument();
      expect(screen.getByText('Адрес доставки')).toBeInTheDocument();
      expect(screen.getByText('Способ доставки')).toBeInTheDocument();
      expect(screen.getByText('Комментарий к заказу')).toBeInTheDocument();
      expect(screen.getByText('Ваш заказ')).toBeInTheDocument();
    });

    it('должен отображать кнопку "Оформить заказ"', () => {
      render(<CheckoutForm user={null} />);

      const submitButton = screen.getByRole('button', {
        name: /оформить заказ/i,
      });
      expect(submitButton).toBeInTheDocument();
      expect(submitButton).not.toBeDisabled();
    });
  });

  describe('Автозаполнение для авторизованных пользователей', () => {
    it('должен автозаполнять контактные данные из user', () => {
      render(<CheckoutForm user={mockUser} />);

      expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('+79001234567')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Иван')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Петров')).toBeInTheDocument();
    });

    it('должен отображать пустые поля для неавторизованных пользователей', () => {
      render(<CheckoutForm user={null} />);

      const emailInput = screen.getByLabelText('Электронная почта') as HTMLInputElement;
      const phoneInput = screen.getByLabelText('Телефон') as HTMLInputElement;

      expect(emailInput.value).toBe('');
      expect(phoneInput.value).toBe('');
    });
  });

  describe('Валидация формы', () => {
    it('должен показывать ошибки при отправке пустой формы', async () => {
      render(<CheckoutForm user={null} />);

      const submitButton = screen.getByRole('button', {
        name: /оформить заказ/i,
      });

      fireEvent.click(submitButton);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only)
        const errors = screen.getAllByText('Email обязателен');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен показывать ошибку при некорректном формате email', async () => {
      render(<CheckoutForm user={null} />);

      const emailInput = screen.getByLabelText('Электронная почта');
      fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
      fireEvent.blur(emailInput);

      await waitFor(() => {
        // Input компонент рендерит ошибку в двух местах (visible + sr-only)
        const errors = screen.getAllByText('Некорректный формат email');
        expect(errors.length).toBeGreaterThan(0);
      });
    });

    it('должен показывать ошибку при некорректном формате телефона', async () => {
      render(<CheckoutForm user={null} />);

      const phoneInput = screen.getByLabelText('Телефон');
      fireEvent.change(phoneInput, { target: { value: '1234567890' } });
      fireEvent.blur(phoneInput);

      await waitFor(() => {
        expect(screen.getByText(/Формат: \+7XXXXXXXXXX/)).toBeInTheDocument();
      });
    });
  });

  describe('Отправка формы', () => {
    it('должен блокировать кнопку во время отправки', async () => {
      // Mock orderStore с isSubmitting = true для проверки disabled состояния
      const { useOrderStore } = await import('@/stores/orderStore');
      (useOrderStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        createOrder: vi.fn(),
        isSubmitting: true,
        error: null,
        clearOrder: vi.fn(),
      });

      render(<CheckoutForm user={mockUser} />);

      // Проверяем, что кнопка disabled при isSubmitting = true
      const submitButton = screen.getByRole('button', {
        name: /оформление/i,
      });

      expect(submitButton).toBeDisabled();
    });
  });

  describe('OrderSummary интеграция', () => {
    it('должен отображать товары из корзины', () => {
      render(<CheckoutForm user={null} />);

      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('2 × 100 ₽')).toBeInTheDocument();
      // Цена отображается в нескольких местах (item total, cart total, итого)
      const prices = screen.getAllByText(/200\s*₽/);
      expect(prices.length).toBeGreaterThan(0);
    });

    it('должен показывать сообщение о пустой корзине', () => {
      (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        items: [],
        totalPrice: 0,
        totalItems: 0,
        fetchCart: vi.fn(),
        getPromoDiscount: vi.fn().mockReturnValue(0),
      });

      render(<CheckoutForm user={null} />);

      // Message may appear multiple times in different components
      expect(screen.getAllByText('Корзина пуста').length).toBeGreaterThan(0);
    });
  });

  describe('Discount UI (Story 34-2 regression)', () => {
    it('не показывает строку скидки при нулевом промокоде', () => {
      render(<CheckoutForm user={null} />);

      expect(screen.queryByTestId('promo-discount-row')).not.toBeInTheDocument();
    });

    it('не показывает строку скидки даже при promoDiscount > 0 (promo-система не серверная)', () => {
      // [Review][Patch] Story 34-2: checkout не должен обещать скидку, которую order API не сохраняет
      (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        items: mockCartItems,
        totalPrice: 200,
        totalItems: 2,
        fetchCart: vi.fn(),
        getPromoDiscount: vi.fn().mockReturnValue(50),
      });

      render(<CheckoutForm user={null} />);

      expect(screen.queryByTestId('promo-discount-row')).not.toBeInTheDocument();
    });

    it('итого равно полной цене без вычета скидки (сервер всегда выставляет discount_amount=0)', () => {
      (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        items: mockCartItems,
        totalPrice: 200,
        totalItems: 2,
        fetchCart: vi.fn(),
        getPromoDiscount: vi.fn().mockReturnValue(50),
      });

      render(<CheckoutForm user={null} />);

      // Итого = totalPrice (200), скидка не вычитается в checkout
      expect(screen.getByTestId('total-price')).toHaveTextContent('200');
    });

    it('не показывает метку "До скидки" (discount не применяется в checkout)', () => {
      (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        items: mockCartItems,
        totalPrice: 200,
        totalItems: 2,
        fetchCart: vi.fn(),
        getPromoDiscount: vi.fn().mockReturnValue(50),
      });

      render(<CheckoutForm user={null} />);

      expect(screen.queryByTestId('price-before-discount')).not.toBeInTheDocument();
    });
  });

  describe('Address loading и автозаполнение из API (spec checkout-address-ux)', () => {
    it('гость — addressService.getAddresses не вызывается, селектора нет', async () => {
      render(<CheckoutForm user={null} />);
      await waitFor(() => {
        expect(addressService.getAddresses).not.toHaveBeenCalled();
      });
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
      expect(screen.queryByTestId('save-address-checkbox-wrapper')).not.toBeInTheDocument();
    });

    it('авторизован, 0 адресов — селектор не рендерится, форма пустая', async () => {
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);
      render(<CheckoutForm user={mockUser} />);
      await waitFor(() => {
        expect(addressService.getAddresses).toHaveBeenCalledTimes(1);
      });
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
      const cityInput = screen.getByLabelText('Город') as HTMLInputElement;
      expect(cityInput.value).toBe('');
    });

    it('авторизован, 1 default-адрес — поля автозаполнены, селектор скрыт', async () => {
      const addr = makeAddress({ id: 11, is_default: true, city: 'Казань' });
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce([addr]);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        const cityInput = screen.getByLabelText('Город') as HTMLInputElement;
        expect(cityInput.value).toBe('Казань');
      });
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
    });

    it('авторизован, 3 адреса с default — селектор показан, дефолт автозаполнен', async () => {
      const list = [
        makeAddress({ id: 1, city: 'Москва' }),
        makeAddress({ id: 2, is_default: true, city: 'СПб', street: 'Невский', building: '1', postal_code: '190000' }),
        makeAddress({ id: 3, city: 'Сочи' }),
      ];
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce(list);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        const cityInput = screen.getByLabelText('Город') as HTMLInputElement;
        expect(cityInput.value).toBe('СПб');
      });

      const cards = screen.getAllByTestId('address-card-option');
      expect(cards).toHaveLength(3);
      // Дефолт выделен
      const selectedCard = cards.find(c => c.getAttribute('data-selected') === 'true');
      expect(selectedCard).toBeDefined();
    });

    it('фильтрует адреса по address_type=shipping', async () => {
      const list = [
        makeAddress({ id: 1, address_type: 'shipping', is_default: true, city: 'Москва' }),
        makeAddress({ id: 2, address_type: 'legal', city: 'Юр-адрес' }),
      ];
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce(list);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        const cityInput = screen.getByLabelText('Город') as HTMLInputElement;
        expect(cityInput.value).toBe('Москва');
      });
      // Селектор не появляется — после фильтра остался один shipping
      expect(screen.queryByTestId('address-selector')).not.toBeInTheDocument();
    });

    it('выбор другого адреса в селекторе перезаписывает поля формы', async () => {
      const list = [
        makeAddress({ id: 1, is_default: true, city: 'Москва', street: 'Ленина', building: '10' }),
        makeAddress({ id: 2, city: 'Сочи', street: 'Морская', building: '5', postal_code: '354000' }),
      ];
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce(list);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect((screen.getByLabelText('Город') as HTMLInputElement).value).toBe('Москва');
      });

      const cards = screen.getAllByTestId('address-card-option');
      // Карточки рендерятся в порядке массива addresses; вторая — Сочи
      fireEvent.click(cards[1]);

      await waitFor(() => {
        expect((screen.getByLabelText('Город') as HTMLInputElement).value).toBe('Сочи');
        expect((screen.getByLabelText('Дом') as HTMLInputElement).value).toBe('5');
      });
    });

    it('ручное редактирование показывает чекбокс «Запомнить»', async () => {
      const addr = makeAddress({ id: 1, is_default: true, city: 'Москва' });
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce([addr]);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect((screen.getByLabelText('Город') as HTMLInputElement).value).toBe('Москва');
      });
      expect(screen.queryByTestId('save-address-checkbox-wrapper')).not.toBeInTheDocument();

      const cityInput = screen.getByLabelText('Город');
      fireEvent.change(cityInput, { target: { value: 'Тверь' } });

      await waitFor(() => {
        expect(screen.getByTestId('save-address-checkbox-wrapper')).toBeInTheDocument();
      });
    });

    it('ошибка getAddresses показывает toast, форма остаётся пустой', async () => {
      const { toast } = await import('sonner');
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockRejectedValueOnce(
        new Error('500')
      );

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect(toast.error).toHaveBeenCalled();
      });
      const cityInput = screen.getByLabelText('Город') as HTMLInputElement;
      expect(cityInput.value).toBe('');
    });
  });

  describe('Address save после оформления заказа (spec checkout-address-ux)', () => {
    async function fillFormAndSubmit({
      withCheckbox,
    }: {
      withCheckbox: boolean;
    }): Promise<void> {
      // Заполняем все обязательные поля
      fireEvent.change(screen.getByLabelText('Электронная почта'), {
        target: { value: 'buyer@example.com' },
      });
      fireEvent.change(screen.getByLabelText('Телефон'), {
        target: { value: '+79001112233' },
      });
      fireEvent.change(screen.getByLabelText('Имя'), { target: { value: 'Алексей' } });
      fireEvent.change(screen.getByLabelText('Фамилия'), { target: { value: 'Смирнов' } });
      fireEvent.change(screen.getByLabelText('Город'), { target: { value: 'Тверь' } });
      fireEvent.change(screen.getByLabelText('Улица'), { target: { value: 'Советская' } });
      fireEvent.change(screen.getByLabelText('Дом'), { target: { value: '7' } });
      fireEvent.change(screen.getByLabelText('Почтовый индекс'), {
        target: { value: '170000' },
      });

      // Способ доставки (radio)
      await waitFor(() => {
        expect(screen.getByLabelText(/Самовывоз/)).toBeInTheDocument();
      });
      fireEvent.click(screen.getByLabelText(/Самовывоз/));

      if (withCheckbox) {
        await waitFor(() => {
          expect(screen.getByTestId('save-address-checkbox-wrapper')).toBeInTheDocument();
        });
        fireEvent.click(screen.getByLabelText(/Запомнить этот адрес в профиле/));
      }

      const submitButton = screen.getByRole('button', { name: /оформить заказ/i });
      await act(async () => {
        fireEvent.click(submitButton);
      });
    }

    it('первый адрес у юзера — POST createAddress с is_default=true после успеха заказа', async () => {
      const { useOrderStore } = await import('@/stores/orderStore');
      const createOrder = vi.fn().mockResolvedValue(undefined);
      (useOrderStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        createOrder,
        isSubmitting: false,
        error: null,
        clearOrder: vi.fn(),
      });
      (
        useOrderStore as unknown as { getState: ReturnType<typeof vi.fn> }
      ).getState.mockReturnValue({
        currentOrder: { id: 999 },
        setError: vi.fn(),
      });
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);
      (addressService.createAddress as ReturnType<typeof vi.fn>).mockResolvedValueOnce(
        makeAddress({ id: 50 })
      );

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect(addressService.getAddresses).toHaveBeenCalled();
      });

      await fillFormAndSubmit({ withCheckbox: true });

      await waitFor(() => {
        expect(createOrder).toHaveBeenCalled();
      });
      await waitFor(() => {
        expect(addressService.createAddress).toHaveBeenCalledWith(
          expect.objectContaining({
            address_type: 'shipping',
            full_name: 'Алексей Смирнов',
            phone: '+79001112233',
            city: 'Тверь',
            street: 'Советская',
            building: '7',
            postal_code: '170000',
            is_default: true,
          })
        );
      });
    });

    it('submit без чекбокса — createAddress не вызывается даже при ручном вводе', async () => {
      const { useOrderStore } = await import('@/stores/orderStore');
      const createOrder = vi.fn().mockResolvedValue(undefined);
      (useOrderStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        createOrder,
        isSubmitting: false,
        error: null,
        clearOrder: vi.fn(),
      });
      (
        useOrderStore as unknown as { getState: ReturnType<typeof vi.fn> }
      ).getState.mockReturnValue({
        currentOrder: { id: 1000 },
        setError: vi.fn(),
      });
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce([]);

      render(<CheckoutForm user={mockUser} />);
      await waitFor(() => {
        expect(addressService.getAddresses).toHaveBeenCalled();
      });

      await fillFormAndSubmit({ withCheckbox: false });

      await waitFor(() => {
        expect(createOrder).toHaveBeenCalled();
      });
      expect(addressService.createAddress).not.toHaveBeenCalled();
    });

    it('гость — submit не вызывает createAddress даже при включённом чекбоксе (чекбокса нет)', async () => {
      render(<CheckoutForm user={null} />);
      // Чекбокс не должен существовать вообще
      expect(screen.queryByTestId('save-address-checkbox-wrapper')).not.toBeInTheDocument();
      expect(addressService.createAddress).not.toHaveBeenCalled();
    });

    it('адрес из селектора без правки — чекбокс «Запомнить» не показывается', async () => {
      const list = [
        makeAddress({ id: 1, is_default: true }),
        makeAddress({ id: 2, full_name: 'Петя Петров' }),
      ];
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce(list);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect(screen.getAllByTestId('address-card-option')).toHaveLength(2);
      });

      // Кликаем по второй карточке — поля заполняются, но юзер ничего не правил
      fireEvent.click(screen.getAllByTestId('address-card-option')[1]);

      // Чекбокса быть не должно (поля совпадают с выбранным адресом)
      await waitFor(() => {
        expect(
          screen.queryByTestId('save-address-checkbox-wrapper')
        ).not.toBeInTheDocument();
      });
    });

    it('2+ адресов без is_default — автозаполнен первый из массива', async () => {
      const list = [
        makeAddress({ id: 10, is_default: false, city: 'Сочи' }),
        makeAddress({ id: 11, is_default: false, city: 'Казань' }),
      ];
      (addressService.getAddresses as ReturnType<typeof vi.fn>).mockResolvedValueOnce(list);

      render(<CheckoutForm user={mockUser} />);

      await waitFor(() => {
        expect((screen.getByLabelText('Город') as HTMLInputElement).value).toBe('Сочи');
      });
      // Селектор должен быть виден (2 адреса)
      expect(screen.getByTestId('address-selector')).toBeInTheDocument();
    });
  });
});

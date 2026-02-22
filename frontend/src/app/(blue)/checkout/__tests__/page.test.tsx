import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { CheckoutPageClient } from '../CheckoutPageClient';
import { useAuthStore } from '@/stores/authStore';
import { useCartStore } from '@/stores/cartStore';
import type { User } from '@/types/api';

// Mock зависимостей
vi.mock('@/stores/authStore');
vi.mock('@/stores/cartStore');
vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: vi.fn(),
  }),
}));

describe('CheckoutPage', () => {
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
      quantity: 1,
      unit_price: '100.00',
      total_price: '100.00',
      added_at: new Date().toISOString(),
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      items: mockCartItems,
      totalPrice: 100,
      totalItems: 1,
    });
  });

  describe('Авторизованный пользователь', () => {
    it('должен отображать приветствие с именем пользователя', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
      });

      render(<CheckoutPageClient />);

      expect(screen.getByText('Здравствуйте, Иван Петров')).toBeInTheDocument();
    });

    it('должен отображать форму checkout', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
      });

      render(<CheckoutPageClient />);

      expect(screen.getByText('Оформление заказа')).toBeInTheDocument();
      expect(screen.getByText('Контактные данные')).toBeInTheDocument();
      expect(screen.getByText('Адрес доставки')).toBeInTheDocument();
    });

    it('должен автозаполнить данные пользователя', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
      });

      render(<CheckoutPageClient />);

      expect(screen.getByDisplayValue('test@example.com')).toBeInTheDocument();
      expect(screen.getByDisplayValue('+79001234567')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Иван')).toBeInTheDocument();
      expect(screen.getByDisplayValue('Петров')).toBeInTheDocument();
    });
  });

  describe('Неавторизованный пользователь', () => {
    it('должен отображать форму checkout без приветствия', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
      });

      render(<CheckoutPageClient />);

      expect(screen.getByText('Оформление заказа')).toBeInTheDocument();
      expect(screen.queryByText(/Здравствуйте/)).not.toBeInTheDocument();
    });

    it('должен отображать пустую форму', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
      });

      render(<CheckoutPageClient />);

      const emailInput = screen.getByLabelText('Email') as HTMLInputElement;
      const phoneInput = screen.getByLabelText('Телефон') as HTMLInputElement;

      expect(emailInput.value).toBe('');
      expect(phoneInput.value).toBe('');
    });
  });

  describe('Заголовок страницы', () => {
    it('должен отображать заголовок "Оформление заказа"', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
      });

      render(<CheckoutPageClient />);

      const heading = screen.getByRole('heading', {
        name: /оформление заказа/i,
        level: 1,
      });
      expect(heading).toBeInTheDocument();
    });
  });

  describe('Отображение корзины', () => {
    it('должен отображать товары из корзины в OrderSummary', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
      });

      render(<CheckoutPageClient />);

      expect(screen.getByText('Test Product')).toBeInTheDocument();
      expect(screen.getByText('Ваш заказ')).toBeInTheDocument();
    });

    it('должен показывать сообщение о пустой корзине', () => {
      (useAuthStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        user: null,
        isAuthenticated: false,
      });

      (useCartStore as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        items: [],
        totalPrice: 0,
        totalItems: 0,
      });

      render(<CheckoutPageClient />);

      // Message may appear multiple times in different components
      expect(screen.getAllByText('Корзина пуста').length).toBeGreaterThan(0);
    });
  });
});

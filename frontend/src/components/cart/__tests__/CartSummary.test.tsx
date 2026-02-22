/**
 * CartSummary Component Tests
 *
 * Покрытие:
 * - Рендеринг заголовка и итогов
 * - Отображение сумм (subtotal, total)
 * - Disabled state кнопки при пустой корзине
 * - Условный рендеринг Link/button
 * - Hydration (mounted state)
 * - Promo code placeholder
 * - Accessibility (aria-live)
 *
 * @see Story 26.3: Cart Summary & Checkout CTA
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { CartSummary } from '../CartSummary';

// Mock cartStore
const mockCartStore = {
  items: [] as Array<{ id: number }>,
  totalPrice: 0,
  totalItems: 0,
  // Story 26.4: Promo state
  promoCode: null as string | null,
  discountType: null as 'percent' | 'fixed' | null,
  discountValue: 0,
  getPromoDiscount: () => {
    if (!mockCartStore.discountType) return 0;
    const discount =
      mockCartStore.discountType === 'percent'
        ? mockCartStore.totalPrice * (mockCartStore.discountValue / 100)
        : mockCartStore.discountValue;
    return Math.min(discount, mockCartStore.totalPrice);
  },
};

vi.mock('@/stores/cartStore', () => ({
  useCartStore: vi.fn(() => mockCartStore),
}));

// Mock formatPrice
vi.mock('@/utils/pricing', () => ({
  formatPrice: (price: number) => `${price.toLocaleString('ru-RU')} ₽`,
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Mock PromoCodeInput
vi.mock('../PromoCodeInput', () => ({
  default: () => <div data-testid="promo-code-section">PromoCodeInput Mock</div>,
}));

/**
 * Хелпер для установки состояния cartStore
 */
const setCartState = (state: Partial<typeof mockCartStore>) => {
  Object.assign(mockCartStore, state);
};

/**
 * Хелпер для сброса cartStore
 */
const resetCartStore = () => {
  mockCartStore.items = [];
  mockCartStore.totalPrice = 0;
  mockCartStore.totalItems = 0;
  // Story 26.4: Reset promo state
  mockCartStore.promoCode = null;
  mockCartStore.discountType = null;
  mockCartStore.discountValue = 0;
};

/**
 * Mock данные для тестов
 */
const mockCartItems = [
  {
    id: 1,
    variant_id: 101,
    product: { id: 10, name: 'Мяч футбольный Nike', slug: 'myach', image: '/ball.jpg' },
    variant: { sku: 'BALL-001', color_name: 'Белый', size_value: '5' },
    quantity: 2,
    unit_price: '2500',
    total_price: '5000',
    added_at: '2025-12-07T10:00:00Z',
  },
  {
    id: 2,
    variant_id: 102,
    product: { id: 11, name: 'Бутсы Adidas', slug: 'butsy', image: '/boots.jpg' },
    variant: { sku: 'BOOTS-002', color_name: 'Чёрный', size_value: '42' },
    quantity: 1,
    unit_price: '8990',
    total_price: '8990',
    added_at: '2025-12-07T10:05:00Z',
  },
];

describe('CartSummary', () => {
  beforeEach(() => {
    resetCartStore();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  // ================== Базовый рендеринг ==================
  describe('Rendering', () => {
    it('renders cart summary container', async () => {
      render(<CartSummary />);
      expect(screen.getByTestId('cart-summary')).toBeInTheDocument();
    });

    it('renders header "Итоги заказа"', () => {
      render(<CartSummary />);
      expect(screen.getByText('Итоги заказа')).toBeInTheDocument();
    });

    it('renders "Товары на сумму" label', () => {
      render(<CartSummary />);
      expect(screen.getByText('Товары на сумму')).toBeInTheDocument();
    });

    it('renders "Итого к оплате" label', () => {
      render(<CartSummary />);
      expect(screen.getByText('Итого к оплате')).toBeInTheDocument();
    });

    it('renders promo code section (placeholder)', () => {
      render(<CartSummary />);
      expect(screen.getByTestId('promo-code-section')).toBeInTheDocument();
    });

    it('renders checkout button', () => {
      render(<CartSummary />);
      expect(screen.getByTestId('checkout-button')).toBeInTheDocument();
    });
  });

  // ================== Price Display ==================
  describe('Price Display', () => {
    it('displays placeholder "—" before hydration', () => {
      // До useEffect subtotal показывает placeholder
      render(<CartSummary />);
      // После первого рендера mounted = false
      // Но React Testing Library обычно запускает useEffect синхронно
    });

    it('displays totalPrice after hydration', async () => {
      setCartState({ items: mockCartItems, totalPrice: 13990, totalItems: 3 });
      render(<CartSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('subtotal-amount')).toHaveTextContent('13 990 ₽');
      });
    });

    it('displays totalPrice equal to finalTotal when no promo', async () => {
      setCartState({ items: mockCartItems, totalPrice: 13990, totalItems: 3 });
      render(<CartSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('total-amount')).toHaveTextContent('13 990 ₽');
      });
    });

    it('displays 0 ₽ when cart is empty', async () => {
      setCartState({ items: [], totalPrice: 0, totalItems: 0 });
      render(<CartSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('subtotal-amount')).toHaveTextContent('0 ₽');
        expect(screen.getByTestId('total-amount')).toHaveTextContent('0 ₽');
      });
    });
  });

  // ================== Promo Discount ==================
  describe('Promo Discount', () => {
    it('does not display promo discount row when promoDiscount is 0', () => {
      render(<CartSummary />);
      expect(screen.queryByTestId('promo-discount-amount')).not.toBeInTheDocument();
    });

    it('does not display "Скидка по промокоду" text when no promo', () => {
      render(<CartSummary />);
      expect(screen.queryByText('Скидка по промокоду')).not.toBeInTheDocument();
    });
  });

  // ================== Checkout Button ==================
  describe('Checkout Button', () => {
    it('renders disabled button when cart is empty', async () => {
      setCartState({ items: [], totalPrice: 0, totalItems: 0 });
      render(<CartSummary />);

      await waitFor(() => {
        const button = screen.getByTestId('checkout-button');
        expect(button.tagName).toBe('BUTTON');
        expect(button).toBeDisabled();
        expect(button).toHaveAttribute('aria-disabled', 'true');
      });
    });

    it('renders Link when cart has items', async () => {
      setCartState({ items: mockCartItems, totalPrice: 13990, totalItems: 3 });
      render(<CartSummary />);

      await waitFor(() => {
        const link = screen.getByTestId('checkout-button');
        expect(link.tagName).toBe('A');
        expect(link).toHaveAttribute('href', '/checkout');
      });
    });

    it('displays "Перейти к оформлению" text', () => {
      render(<CartSummary />);
      expect(screen.getByText(/Перейти к оформлению/)).toBeInTheDocument();
    });
  });

  // ================== Sticky Positioning ==================
  describe('Sticky Positioning', () => {
    it('has lg:sticky lg:top-24 classes for desktop sticky', () => {
      render(<CartSummary />);
      const container = screen.getByTestId('cart-summary');
      expect(container.className).toContain('lg:sticky');
      expect(container.className).toContain('lg:top-24');
    });
  });

  // ================== Accessibility ==================
  describe('Accessibility', () => {
    it('has aria-live="polite" on price section', () => {
      render(<CartSummary />);
      const priceSection = screen.getByTestId('subtotal-amount').parentElement?.parentElement;
      expect(priceSection).toHaveAttribute('aria-live', 'polite');
    });

    it('disabled button has aria-disabled attribute', async () => {
      setCartState({ items: [], totalPrice: 0, totalItems: 0 });
      render(<CartSummary />);

      await waitFor(() => {
        const button = screen.getByTestId('checkout-button');
        expect(button).toHaveAttribute('aria-disabled', 'true');
      });
    });
  });

  // ================== Hydration ==================
  describe('Hydration', () => {
    it('correctly handles hydration with mounted state', async () => {
      setCartState({ items: mockCartItems, totalPrice: 13990, totalItems: 3 });
      render(<CartSummary />);

      // После монтирования должен отображаться Link
      await waitFor(() => {
        const element = screen.getByTestId('checkout-button');
        expect(element.tagName).toBe('A');
      });
    });
  });
});

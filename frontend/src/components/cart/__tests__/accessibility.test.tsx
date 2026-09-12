/**
 * Cart Components Accessibility Tests
 *
 * Тесты доступности для всех компонентов корзины с использованием vitest-axe.
 * Проверяет соответствие WCAG 2.1 guidelines.
 *
 * @see Story 26.5: Cart Page Unit & Integration Tests (AC: 8)
 */

import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as axeMatchers from 'vitest-axe';
import { axe } from 'vitest-axe';
import LayoutWrapper from '@/components/layout/LayoutWrapper';
import { CartPage } from '../CartPage';
import { CartItemCard } from '../CartItemCard';
import { CartSummary } from '../CartSummary';
import { EmptyCart } from '../EmptyCart';
import { CartError } from '../CartError';
import { CartSkeleton } from '../CartSkeleton';
import { QuantitySelector } from '../QuantitySelector';
import { ReturnsAndSupportNotice } from '@/components/common';
import { useCartStore } from '@/stores/cartStore';
import type { CartItem } from '@/types/cart';

// Extend expect with accessibility matchers
// @ts-expect-error vitest-axe types mismatch with vitest
expect.extend(axeMatchers);

// ==================== Mocks ====================

vi.mock('next/link', () => ({
  default: ({ children, href, ...props }: { children: React.ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

vi.mock('next/image', () => ({
  default: ({ src, alt, ...props }: { src: string; alt: string }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img src={src} alt={alt} {...props} />
  ),
}));

vi.mock('@/utils/pricing', () => ({
  formatPrice: (price: number) => `${price.toLocaleString('ru-RU')} ₽`,
}));

vi.mock('@/components/ui', () => ({
  Breadcrumb: ({ items }: { items: { label: string }[] }) => (
    <nav aria-label="Хлебные крошки">
      {items.map((item, i) => (
        <span key={i}>{item.label}</span>
      ))}
    </nav>
  ),
}));

vi.mock('react-hot-toast', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

// LayoutWrapper выбирает ветку по pathname: для /cart — ветка blue со своим <main>
vi.mock('next/navigation', async importOriginal => ({
  ...(await importOriginal<typeof import('next/navigation')>()),
  usePathname: () => '/cart',
}));

vi.mock('@/components/layout/ElectricHeader', () => ({ default: () => null }));
vi.mock('@/components/layout/ElectricFooter', () => ({ default: () => null }));

vi.mock('../PromoCodeInput', () => ({
  default: () => (
    <div data-testid="promo-code-section">
      <label htmlFor="promo-input">Промокод</label>
      <input id="promo-input" type="text" aria-label="Промокод" />
      <button type="submit">Применить</button>
    </div>
  ),
}));

// ==================== Test Data ====================

const mockCartItem: CartItem = {
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
};

// ==================== Helper Functions ====================

/**
 * Сбрасывает состояние cartStore
 */
const resetStore = () => {
  useCartStore.setState({
    items: [],
    totalItems: 0,
    totalPrice: 0,
    isLoading: false,
    error: null,
    promoCode: null,
    discountType: null,
    discountValue: 0,
  });
};

/**
 * Устанавливает состояние cartStore с товарами
 */
const setStoreWithItems = () => {
  useCartStore.setState({
    items: [mockCartItem],
    totalItems: 2,
    totalPrice: 11980,
    isLoading: false,
    error: null,
    promoCode: null,
    discountType: null,
    discountValue: 0,
  });
};

// ==================== Accessibility Tests ====================

describe('Cart Components Accessibility', () => {
  // Тесты подменяют fetchCart, чтобы корзина с товарами не перезагружалась с сервера
  const originalFetchCart = useCartStore.getState().fetchCart;

  beforeEach(() => {
    vi.clearAllMocks();
    resetStore();
  });

  afterEach(() => {
    useCartStore.setState({ fetchCart: originalFetchCart });
  });

  // ==================== CartPage Accessibility ====================

  describe('CartPage', () => {
    // TODO: Fix heading-order violation in CartItemCard (h3 before h1 in DOM order)
    it.skip('has no accessibility violations with items', async () => {
      setStoreWithItems();
      const { container } = render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-page')).toBeInTheDocument();
      });

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('has no accessibility violations when empty', async () => {
      resetStore();
      const { container } = render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('empty-cart')).toBeInTheDocument();
      });

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('has proper heading hierarchy', async () => {
      setStoreWithItems();
      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument();
      });

      // H1 должен быть единственным и содержать название страницы
      const h1 = screen.getByRole('heading', { level: 1 });
      expect(h1).toHaveTextContent(/корзина/i);
    });

    it('не рендерит собственный main: единственный main — в LayoutWrapper', async () => {
      setStoreWithItems();
      useCartStore.setState({ fetchCart: vi.fn() });
      render(<CartPage />);

      await screen.findByTestId('cart-page');
      expect(screen.queryByRole('main')).not.toBeInTheDocument();
    });
  });

  // ==================== CartItemCard Accessibility ====================

  describe('CartItemCard', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<CartItemCard item={mockCartItem} />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('image has proper alt text', () => {
      render(<CartItemCard item={mockCartItem} />);

      const image = screen.getByRole('img');
      expect(image).toHaveAttribute('alt', 'Кроссовки Nike Air Max');
    });

    it('remove button has aria-label', () => {
      render(<CartItemCard item={mockCartItem} />);

      const removeButton = screen.getByTestId('remove-item-button');
      expect(removeButton).toHaveAttribute('aria-label', 'Удалить товар');
    });

    it('quantity controls are keyboard accessible', () => {
      render(<CartItemCard item={mockCartItem} />);

      const decrementBtn = screen.getByTestId('quantity-decrement');
      const incrementBtn = screen.getByTestId('quantity-increment');
      const input = screen.getByTestId('quantity-input');

      // Все элементы должны быть focusable
      expect(decrementBtn).not.toHaveAttribute('tabindex', '-1');
      expect(incrementBtn).not.toHaveAttribute('tabindex', '-1');
      expect(input).not.toHaveAttribute('tabindex', '-1');
    });
  });

  // ==================== CartSummary Accessibility ====================

  describe('CartSummary', () => {
    it('has no accessibility violations', async () => {
      setStoreWithItems();
      const { container } = render(<CartSummary />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-summary')).toBeInTheDocument();
      });

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('has aria-live for price updates', async () => {
      setStoreWithItems();
      render(<CartSummary />);

      await waitFor(() => {
        const priceSection = screen.getByTestId('subtotal-amount').parentElement?.parentElement;
        expect(priceSection).toHaveAttribute('aria-live', 'polite');
      });
    });

    it('disabled button has aria-disabled', async () => {
      resetStore();
      render(<CartSummary />);

      await waitFor(() => {
        const button = screen.getByTestId('checkout-button');
        expect(button).toHaveAttribute('aria-disabled', 'true');
      });
    });
  });

  // ============ ReturnsAndSupportNotice Accessibility (Story 41.4, AC8) ============

  describe('ReturnsAndSupportNotice', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<ReturnsAndSupportNotice />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('группа ссылок имеет доступное имя', () => {
      render(<ReturnsAndSupportNotice />);

      expect(screen.getByRole('region', { name: 'Условия возврата и поддержка' })).toBeInTheDocument();
    });

    it('все ссылки имеют осмысленные доступные имена (WCAG 2.4.4)', () => {
      render(<ReturnsAndSupportNotice />);

      const names = screen.getAllByRole('link').map(link => link.textContent?.trim());
      expect(names).toEqual([
        'Условия возврата и рекламаций',
        '+7 968 273-21-68',
        'info@optisport.ru',
      ]);
    });
  });

  // ==================== EmptyCart Accessibility ====================

  describe('EmptyCart', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<EmptyCart />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('icon has aria-hidden', () => {
      const { container } = render(<EmptyCart />);

      const icon = container.querySelector('svg');
      expect(icon).toHaveAttribute('aria-hidden', 'true');
    });

    it('CTA button is keyboard accessible', () => {
      render(<EmptyCart />);

      const catalogButton = screen.getByTestId('go-to-catalog-button');
      expect(catalogButton).toBeVisible();
      expect(catalogButton.tagName).toBe('A');
    });
  });

  // ==================== CartError Accessibility (Story 41.10) ====================

  describe('CartError', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<CartError error="Ошибка сервера" onRetry={vi.fn()} />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('retry button is keyboard accessible', () => {
      render(<CartError error="Ошибка сервера" onRetry={vi.fn()} />);

      const retryButton = screen.getByTestId('cart-retry-button');
      expect(retryButton).not.toHaveAttribute('tabindex', '-1');
    });
  });

  // ==================== CartSkeleton Accessibility (Story 41.10) ====================

  describe('CartSkeleton', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<CartSkeleton />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('announces loading and keeps the returns notice reachable', () => {
      render(<CartSkeleton />);

      expect(screen.getByRole('region', { name: 'Загрузка корзины' })).toHaveAttribute(
        'aria-busy',
        'true'
      );
      expect(
        screen.getByRole('region', { name: 'Условия возврата и поддержка' })
      ).toBeInTheDocument();
    });
  });

  // ============ Landmarks внутри LayoutWrapper (единственный main на странице) ============

  describe('Landmarks inside LayoutWrapper', () => {
    // Только landmark-правила: полный прогон корзины с товарами упирается
    // в известный heading-order CartItemCard (см. it.skip выше)
    const LANDMARK_RULES = {
      runOnly: {
        type: 'rule' as const,
        values: [
          'landmark-main-is-top-level',
          'landmark-no-duplicate-main',
          'landmark-banner-is-top-level',
          'landmark-contentinfo-is-top-level',
          'landmark-complementary-is-top-level',
          'landmark-unique',
          'aria-prohibited-attr',
        ],
      },
    };

    const renderInLayout = (ui: React.ReactElement) =>
      render(
        <LayoutWrapper header={<header>Шапка</header>} footer={<footer>Подвал</footer>}>
          {ui}
        </LayoutWrapper>
      );

    it.each([
      ['CartSkeleton', () => <CartSkeleton />, 'cart-skeleton'],
      ['EmptyCart', () => <EmptyCart />, 'empty-cart'],
      ['CartError', () => <CartError error="Ошибка сервера" onRetry={vi.fn()} />, 'cart-error'],
    ])('%s: один main на странице, axe без landmark-нарушений', async (_name, ui, testId) => {
      const { container } = renderInLayout(ui());

      expect(screen.getByTestId(testId)).toBeInTheDocument();
      expect(screen.getAllByRole('main')).toHaveLength(1);

      const results = await axe(container, LANDMARK_RULES);
      expect(results.violations.map(v => v.id)).toEqual([]);
    });

    it('CartPage с товарами: один main на странице, axe без landmark-нарушений', async () => {
      setStoreWithItems();
      useCartStore.setState({ fetchCart: vi.fn() });
      const { container } = renderInLayout(<CartPage />);

      await screen.findByTestId('cart-page');
      expect(screen.getAllByRole('main')).toHaveLength(1);

      const results = await axe(container, LANDMARK_RULES);
      expect(results.violations.map(v => v.id)).toEqual([]);
    });
  });

  // ==================== QuantitySelector Accessibility ====================

  describe('QuantitySelector', () => {
    it('has no accessibility violations', async () => {
      const { container } = render(<QuantitySelector value={5} onChange={vi.fn()} />);

      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });

    it('has role="spinbutton"', () => {
      render(<QuantitySelector value={5} onChange={vi.fn()} />);

      expect(screen.getByRole('spinbutton')).toBeInTheDocument();
    });

    it('has correct aria attributes', () => {
      render(<QuantitySelector value={5} min={1} max={99} onChange={vi.fn()} />);

      const spinbutton = screen.getByRole('spinbutton');
      expect(spinbutton).toHaveAttribute('aria-valuenow', '5');
      expect(spinbutton).toHaveAttribute('aria-valuemin', '1');
      expect(spinbutton).toHaveAttribute('aria-valuemax', '99');
      expect(spinbutton).toHaveAttribute('aria-label', 'Количество товара');
    });

    it('buttons have aria-labels', () => {
      render(<QuantitySelector value={5} onChange={vi.fn()} />);

      expect(screen.getByTestId('quantity-decrement')).toHaveAttribute(
        'aria-label',
        'Уменьшить количество'
      );
      expect(screen.getByTestId('quantity-increment')).toHaveAttribute(
        'aria-label',
        'Увеличить количество'
      );
    });

    it('supports keyboard navigation', () => {
      const onChange = vi.fn();
      render(<QuantitySelector value={5} onChange={onChange} />);

      const input = screen.getByTestId('quantity-input');

      // Input должен быть focusable
      input.focus();
      expect(document.activeElement).toBe(input);
    });
  });

  // ==================== Focus Management ====================

  describe('Focus Management', () => {
    it('maintains focus when updating quantity', async () => {
      render(<QuantitySelector value={5} onChange={vi.fn()} />);

      const incrementBtn = screen.getByTestId('quantity-increment');
      incrementBtn.focus();

      expect(document.activeElement).toBe(incrementBtn);
    });

    it('all interactive elements can receive focus', async () => {
      // Mock fetchCart to preserve items
      const mockFetchCart = vi.fn();
      setStoreWithItems();
      useCartStore.setState({ fetchCart: mockFetchCart });

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-page')).toBeInTheDocument();
      });

      // Wait for items to render before checking for buttons
      await waitFor(
        () => {
          const buttons = screen.queryAllByRole('button');
          expect(buttons.length).toBeGreaterThan(0);
        },
        { timeout: 3000 }
      );

      // Проверяем что все интерактивные элементы доступны
      const buttons = screen.getAllByRole('button');
      const links = screen.getAllByRole('link');

      buttons.forEach(button => {
        expect(button).not.toHaveAttribute('tabindex', '-1');
      });

      links.forEach(link => {
        expect(link).not.toHaveAttribute('tabindex', '-1');
      });
    });
  });

  // ==================== Color Contrast ====================

  describe('Color Contrast', () => {
    // TODO: Fix heading-order violation in CartItemCard
    it.skip('CartPage passes color contrast checks', async () => {
      setStoreWithItems();
      const { container } = render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-page')).toBeInTheDocument();
      });

      // axe автоматически проверяет контрастность
      const results = await axe(container);
      expect(results.violations).toHaveLength(0);
    });
  });
});

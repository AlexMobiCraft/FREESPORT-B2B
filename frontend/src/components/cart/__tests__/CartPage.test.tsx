/**
 * CartPage Component Tests
 *
 * Покрытие:
 * - Рендеринг страницы с товарами
 * - Пустая корзина (EmptyCart)
 * - Loading state (CartSkeleton)
 * - Error state с retry
 * - Hydration паттерн
 * - Responsive layout
 */

import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach } from 'vitest';
import { CartPage } from '../CartPage';
import { useCartStore } from '@/stores/cartStore';
import type { CartItem } from '@/types/cart';

// Mock cartStore
vi.mock('@/stores/cartStore', () => ({
  useCartStore: vi.fn(),
}));

// Mock next/link
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

// Mock Breadcrumb
vi.mock('@/components/ui', () => ({
  Breadcrumb: ({
    items,
    className,
  }: {
    items: { label: string; href?: string }[];
    className?: string;
  }) => (
    <nav aria-label="Breadcrumb" className={className} data-testid="cart-breadcrumb">
      {items.map((item, i) => (
        <span key={i}>{item.label}</span>
      ))}
    </nav>
  ),
}));

// Mock Skeleton
vi.mock('@/components/ui/Skeleton', () => ({
  Skeleton: ({ className }: { className?: string }) => (
    <div className={className} data-testid="skeleton" />
  ),
}));

const mockCartItem: CartItem = {
  id: 1,
  variant_id: 101,
  product: {
    id: 10,
    name: 'Test Product',
    slug: 'test-product',
    image: '/test-image.jpg',
  },
  variant: {
    sku: 'SKU-001',
    color_name: 'Черный',
    size_value: 'XL',
  },
  quantity: 2,
  unit_price: '1500.00',
  total_price: '3000.00',
  added_at: '2024-01-01T00:00:00Z',
};

const mockEmptyStore = {
  items: [],
  isLoading: false,
  error: null,
  fetchCart: vi.fn(),
  totalPrice: 0,
  totalItems: 0,
  updateQuantity: vi.fn().mockResolvedValue({ success: true }),
  removeItem: vi.fn().mockResolvedValue({ success: true }),
  promoCode: null,
  discountType: null,
  discountValue: 0,
  getPromoDiscount: vi.fn().mockReturnValue(0),
};

const mockStoreWithItems = {
  items: [mockCartItem],
  isLoading: false,
  error: null,
  fetchCart: vi.fn(),
  totalPrice: 3000,
  totalItems: 2,
  updateQuantity: vi.fn().mockResolvedValue({ success: true }),
  removeItem: vi.fn().mockResolvedValue({ success: true }),
  promoCode: null,
  discountType: null,
  discountValue: 0,
  getPromoDiscount: vi.fn().mockReturnValue(0),
};

const mockLoadingStore = {
  items: [],
  isLoading: true,
  error: null,
  fetchCart: vi.fn(),
  totalPrice: 0,
  totalItems: 0,
  updateQuantity: vi.fn().mockResolvedValue({ success: true }),
  removeItem: vi.fn().mockResolvedValue({ success: true }),
  promoCode: null,
  discountType: null,
  discountValue: 0,
  getPromoDiscount: vi.fn().mockReturnValue(0),
};

const mockErrorStore = {
  items: [],
  isLoading: false,
  error: 'Ошибка сервера',
  fetchCart: vi.fn(),
  totalPrice: 0,
  totalItems: 0,
  updateQuantity: vi.fn().mockResolvedValue({ success: true }),
  removeItem: vi.fn().mockResolvedValue({ success: true }),
  promoCode: null,
  discountType: null,
  discountValue: 0,
  getPromoDiscount: vi.fn().mockReturnValue(0),
};

describe('CartPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // Пустая корзина
  describe('Empty Cart', () => {
    it('renders EmptyCart when cart is empty', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockEmptyStore);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('empty-cart')).toBeInTheDocument();
      });
    });

    it('shows "Ваша корзина пуста" message', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockEmptyStore);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByText('Ваша корзина пуста')).toBeInTheDocument();
      });
    });

    it('shows "В каталог" button', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockEmptyStore);

      render(<CartPage />);

      await waitFor(() => {
        const catalogLink = screen.getByRole('link', { name: /в каталог/i });
        expect(catalogLink).toBeInTheDocument();
        expect(catalogLink).toHaveAttribute('href', '/catalog');
      });
    });
  });

  // Корзина с товарами
  describe('Cart with Items', () => {
    it('renders cart page with items', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-page')).toBeInTheDocument();
      });
    });

    it('displays product name', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByText('Test Product')).toBeInTheDocument();
      });
    });

    it('displays product variant info', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        // CartItemCard форматирует как "Арт: SKU | Цвет: X | Размер: Y"
        const skuElement = screen.getByTestId('cart-item-sku');
        expect(skuElement).toHaveTextContent('Арт: SKU-001');
        expect(skuElement).toHaveTextContent('Цвет: Черный');
        expect(skuElement).toHaveTextContent('Размер: XL');
      });
    });

    it('displays total price', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        // Total price in summary
        expect(screen.getByTestId('cart-summary')).toBeInTheDocument();
      });
    });

    it('renders cart items list', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-items-list')).toBeInTheDocument();
      });
    });
  });

  // Loading state
  describe('Loading State', () => {
    it('renders CartSkeleton when loading and empty', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockLoadingStore);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-skeleton')).toBeInTheDocument();
      });
    });

    it('shows loading skeleton before hydration', () => {
      vi.mocked(useCartStore).mockReturnValue(mockLoadingStore);

      // On initial render before useEffect runs
      const { container } = render(<CartPage />);

      // Should have skeleton (before mounted state)
      expect(container.querySelector('[data-testid="cart-skeleton"]')).toBeInTheDocument();
    });
  });

  // Error state
  describe('Error State', () => {
    it('renders CartError when error occurs', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockErrorStore);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-error')).toBeInTheDocument();
      });
    });

    it('displays error message', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockErrorStore);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByText('Ошибка сервера')).toBeInTheDocument();
      });
    });

    it('calls fetchCart on retry button click', async () => {
      const mockFetchCart = vi.fn();
      vi.mocked(useCartStore).mockReturnValue({
        ...mockErrorStore,
        fetchCart: mockFetchCart,
      });

      render(<CartPage />);

      await waitFor(() => {
        const retryButton = screen.getByTestId('cart-retry-button');
        fireEvent.click(retryButton);
        expect(mockFetchCart).toHaveBeenCalled();
      });
    });
  });

  // Breadcrumb
  describe('Breadcrumb', () => {
    it('renders breadcrumb with correct items', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByTestId('cart-breadcrumb')).toBeInTheDocument();
        expect(screen.getByText('Главная')).toBeInTheDocument();
        expect(screen.getByText('Корзина')).toBeInTheDocument();
      });
    });
  });

  // Заголовок страницы
  describe('Page Title', () => {
    it('renders page title "Ваша корзина"', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent('Ваша корзина');
      });
    });
  });

  // Accessibility
  describe('Accessibility', () => {
    it('has main landmark with role="main"', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        expect(screen.getByRole('main')).toBeInTheDocument();
      });
    });

    it('has proper section aria-labels', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        const itemsSection = screen.getByLabelText('Товары в корзине');
        expect(itemsSection).toBeInTheDocument();
      });
    });

    it('cart summary has aria-live for dynamic updates', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        // aria-live на внутреннем элементе с ценами
        const priceSection = screen.getByTestId('subtotal-amount').parentElement?.parentElement;
        expect(priceSection).toHaveAttribute('aria-live', 'polite');
      });
    });
  });

  // Responsive Layout
  describe('Responsive Layout', () => {
    it('has correct grid classes for responsive layout', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      const { container } = render(<CartPage />);

      await waitFor(() => {
        const grid = container.querySelector('.grid');
        expect(grid).toHaveClass('grid-cols-1');
        expect(grid).toHaveClass('lg:grid-cols-3');
      });
    });

    it('items section spans 2 columns on desktop', async () => {
      vi.mocked(useCartStore).mockReturnValue(mockStoreWithItems);

      render(<CartPage />);

      await waitFor(() => {
        const itemsSection = screen.getByTestId('cart-items-list');
        expect(itemsSection).toHaveClass('lg:col-span-2');
      });
    });
  });

  // Data loading
  describe('Data Loading', () => {
    it('calls fetchCart on mount when items empty', async () => {
      const mockFetchCart = vi.fn();
      vi.mocked(useCartStore).mockReturnValue({
        ...mockEmptyStore,
        fetchCart: mockFetchCart,
      });

      render(<CartPage />);

      await waitFor(() => {
        expect(mockFetchCart).toHaveBeenCalled();
      });
    });

    it('calls fetchCart even when items exist to sync with server', async () => {
      const mockFetchCart = vi.fn();
      vi.mocked(useCartStore).mockReturnValue({
        ...mockStoreWithItems,
        fetchCart: mockFetchCart,
      });

      render(<CartPage />);

      await waitFor(() => {
        // Always calls fetchCart to sync with server, even if items exist
        // This is intentional - see CartPage.tsx line 33-35 comment
        expect(mockFetchCart).toHaveBeenCalled();
      });
    });
  });
});

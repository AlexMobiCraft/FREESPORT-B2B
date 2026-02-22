/**
 * Tests for Header Component
 * Comprehensive testing of all states, variants, and user interactions
 * Covers: authenticated/unauthenticated states, B2B/B2C UI, mobile menu, cart badge
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { axe } from 'vitest-axe';
import Header from '../Header';
import { useCartStore } from '@/stores/cartStore';
import { authSelectors } from '@/stores/authStore';
import type { CartItem } from '@/types/cart';

// Mock Next.js router
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  usePathname: vi.fn(() => '/'),
  useRouter: vi.fn(() => ({ push: mockPush })),
}));

// Mock authStore
const mockLogout = vi.fn().mockResolvedValue(undefined);
vi.mock('@/stores/authStore', () => ({
  authSelectors: {
    useIsAuthenticated: vi.fn(() => false),
    useUser: vi.fn(() => null),
    useIsB2BUser: vi.fn(() => false),
  },
  useAuthStore: vi.fn(selector =>
    selector({
      logout: mockLogout,
      accessToken: null,
      user: null,
      isAuthenticated: false,
      setTokens: vi.fn(),
      setUser: vi.fn(),
      getRefreshToken: vi.fn(),
    })
  ),
}));

// Mock cartStore
vi.mock('@/stores/cartStore', () => ({
  useCartStore: vi.fn(selector =>
    selector({
      items: [],
      totalItems: 0,
      totalPrice: 0,
      isLoading: false,
      error: null,
      promoCode: null,
      discountType: null,
      discountValue: 0,
      addItem: vi.fn(),
      removeItem: vi.fn(),
      updateQuantity: vi.fn(),
      clearCart: vi.fn(),
      fetchCart: vi.fn(),
      applyPromo: vi.fn(),
      clearPromo: vi.fn(),
      getPromoDiscount: vi.fn(() => 0),
      getTotalItems: vi.fn(() => 0),
      setItems: vi.fn(),
      setError: vi.fn(),
      setLoading: vi.fn(),
    })
  ),
}));

// Helper для создания валидных CartItem моков (Epic 26 types)
function createMockCartItem(overrides: Partial<CartItem> = {}): CartItem {
  return {
    id: 1,
    variant_id: 1,
    product: {
      id: 1,
      name: 'Product',
      slug: 'product',
      image: null,
    },
    variant: {
      sku: 'TEST-SKU',
      color_name: null,
      size_value: null,
    },
    quantity: 1,
    unit_price: '100.00',
    total_price: '100.00',
    added_at: '2024-01-01T00:00:00Z',
    ...overrides,
  };
}

// Helper для создания CartStore mock с items
function createMockCartStore(
  items: CartItem[] = [],
  overrides: Partial<ReturnType<typeof useCartStore.getState>> = {}
) {
  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  return {
    items,
    totalItems,
    totalPrice: 0,
    isLoading: false,
    error: null,
    promoCode: null,
    discountType: null,
    discountValue: 0,
    addItem: vi.fn(),
    removeItem: vi.fn(),
    updateQuantity: vi.fn(),
    clearCart: vi.fn(),
    fetchCart: vi.fn(),
    applyPromo: vi.fn(),
    clearPromo: vi.fn(),
    getPromoDiscount: vi.fn(() => 0),
    getTotalItems: vi.fn(() => totalItems),
    setItems: vi.fn(),
    setError: vi.fn(),
    setLoading: vi.fn(),
    ...overrides,
  };
}

describe('Header', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockPush.mockClear();
    mockLogout.mockClear();
  });

  describe('Rendering - Unauthenticated State', () => {
    beforeEach(() => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(false);
      vi.mocked(authSelectors.useUser).mockReturnValue(null);
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);
    });

    it('should render logo', () => {
      render(<Header />);
      expect(screen.getByAltText('FREESPORT')).toBeInTheDocument();
    });

    it('should render navigation items', () => {
      render(<Header />);

      expect(screen.getByRole('link', { name: 'Главная' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Каталог' })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'Новости' })).toBeInTheDocument();
      const blogLink = screen.getByRole('link', { name: 'Блог' });
      expect(blogLink).toBeInTheDocument();
      expect(blogLink).toHaveAttribute('href', '/blog');
      expect(screen.getByRole('link', { name: 'Партнёрам' })).toBeInTheDocument();
    });

    it('should render action icons (search, favorites, cart)', () => {
      render(<Header />);

      expect(screen.getByRole('link', { name: /Поиск/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Избранное/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Корзина/i })).toBeInTheDocument();
    });

    it('should render login and register buttons', () => {
      render(<Header />);

      const loginButtons = screen.getAllByRole('link', { name: 'Войти' });
      const registerButtons = screen.getAllByRole('link', { name: 'Регистрация' });

      // Desktop + Mobile
      expect(loginButtons.length).toBeGreaterThan(0);
      expect(registerButtons.length).toBeGreaterThan(0);
    });

    it('should NOT render B2B badge when user is not B2B', () => {
      render(<Header />);
      expect(screen.queryByText('B2B')).not.toBeInTheDocument();
    });

    it('should NOT render B2B navigation items', () => {
      render(<Header />);

      expect(screen.queryByRole('link', { name: 'Оптовые цены' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Заказы' })).not.toBeInTheDocument();
    });
  });

  describe('Authentication Links', () => {
    beforeEach(() => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(false);
      vi.mocked(authSelectors.useUser).mockReturnValue(null);
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);
    });

    it('should have correct href for login button (desktop)', () => {
      render(<Header />);

      const loginButtons = screen.getAllByRole('link', { name: 'Войти' });
      const desktopLoginButton = loginButtons[0]; // First one is desktop

      expect(desktopLoginButton).toHaveAttribute('href', '/login');
    });

    it('should have correct href for register button (desktop)', () => {
      render(<Header />);

      const registerButtons = screen.getAllByRole('link', { name: 'Регистрация' });
      const desktopRegisterButton = registerButtons[0]; // First one is desktop

      expect(desktopRegisterButton).toHaveAttribute('href', '/register');
    });

    it('should have correct href for login button (mobile)', async () => {
      const user = userEvent.setup();
      render(<Header />);

      // Open mobile menu
      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      await user.click(menuButton);

      const loginButtons = screen.getAllByRole('link', { name: 'Войти' });
      const mobileLoginButton = loginButtons[1]; // Second one is mobile

      expect(mobileLoginButton).toHaveAttribute('href', '/login');
    });

    it('should have correct href for register button (mobile)', async () => {
      const user = userEvent.setup();
      render(<Header />);

      // Open mobile menu
      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      await user.click(menuButton);

      const registerButtons = screen.getAllByRole('link', { name: 'Регистрация' });
      const mobileRegisterButton = registerButtons[1]; // Second one is mobile

      expect(mobileRegisterButton).toHaveAttribute('href', '/register');
    });
  });

  describe('Rendering - Authenticated State (B2C User)', () => {
    beforeEach(() => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(true);
      vi.mocked(authSelectors.useUser).mockReturnValue({
        id: 1,
        email: 'user@example.com',
        first_name: 'Иван',
        last_name: 'Иванов',
        phone: '+79001234567',
        role: 'retail',
      });
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);
    });

    it('should render user greeting with first name', () => {
      render(<Header />);

      const greetings = screen.getAllByText(/Привет, Иван!/i);
      expect(greetings.length).toBeGreaterThan(0);
    });

    it('should render profile button instead of login/register', () => {
      render(<Header />);

      const profileButtons = screen.getAllByRole('link', { name: 'Профиль' });
      expect(profileButtons.length).toBeGreaterThan(0);

      expect(screen.queryByRole('link', { name: 'Войти' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Регистрация' })).not.toBeInTheDocument();
    });

    it('should NOT render B2B badge for B2C user', () => {
      render(<Header />);
      expect(screen.queryByText('B2B')).not.toBeInTheDocument();
    });

    it('should NOT render B2B navigation items for B2C user', () => {
      render(<Header />);

      expect(screen.queryByRole('link', { name: 'Оптовые цены' })).not.toBeInTheDocument();
      expect(screen.queryByRole('link', { name: 'Заказы' })).not.toBeInTheDocument();
    });
  });

  describe('Rendering - Authenticated State (B2B User)', () => {
    beforeEach(() => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(true);
      vi.mocked(authSelectors.useUser).mockReturnValue({
        id: 2,
        email: 'b2b@example.com',
        first_name: 'Петр',
        last_name: 'Петров',
        phone: '+79007654321',
        role: 'wholesale_level1',
        company_name: 'ООО "Спорт"',
        tax_id: '1234567890',
        is_verified: true,
      });
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(true);
    });

    it('should render B2B badge next to logo', () => {
      render(<Header />);
      expect(screen.getByText('B2B')).toBeInTheDocument();
    });
  });

  describe('Cart Badge', () => {
    it('should NOT display cart badge when cart is empty', () => {
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore()));

      render(<Header />);

      const cartLinks = screen.getAllByRole('link', { name: /Корзина/i });
      cartLinks.forEach(link => {
        expect(link.querySelector('span')).not.toBeInTheDocument();
      });
    });

    it('should display cart badge with correct count when cart has items', () => {
      const items = [
        createMockCartItem({
          id: 1,
          product: { id: 1, name: 'Product 1', slug: 'product-1', image: null },
          quantity: 1,
        }),
        createMockCartItem({
          id: 2,
          product: { id: 2, name: 'Product 2', slug: 'product-2', image: null },
          quantity: 2,
        }),
        createMockCartItem({
          id: 3,
          product: { id: 3, name: 'Product 3', slug: 'product-3', image: null },
          quantity: 1,
        }),
      ];
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      render(<Header />);

      const badges = screen.getAllByText('4');
      expect(badges.length).toBeGreaterThan(0);
    });

    it('should display "99+" when cart has more than 99 items', () => {
      const items = Array.from({ length: 100 }, (_, i) =>
        createMockCartItem({
          id: i + 1,
          product: { id: i + 1, name: `Product ${i + 1}`, slug: `product-${i + 1}`, image: null },
          quantity: 1,
        })
      );
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      render(<Header />);

      const badges = screen.getAllByText('99+');
      expect(badges.length).toBeGreaterThan(0);
    });

    it('should have correct aria-label with item count', () => {
      const items = [
        createMockCartItem({
          id: 1,
          product: { id: 1, name: 'Product 1', slug: 'product-1', image: null },
          quantity: 1,
        }),
        createMockCartItem({
          id: 2,
          product: { id: 2, name: 'Product 2', slug: 'product-2', image: null },
          quantity: 2,
        }),
      ];
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      render(<Header />);

      const desktopCartLink = screen.getByRole('link', { name: 'Корзина (3 товаров)' });
      expect(desktopCartLink).toBeInTheDocument();
    });
  });

  describe('Mobile Menu', () => {
    it('should render mobile menu toggle button', () => {
      render(<Header />);

      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      expect(menuButton).toBeInTheDocument();
    });

    it('should NOT show mobile navigation by default', () => {
      render(<Header />);

      // Мобильная навигация не видна изначально
      const mobileNavItems = screen.queryAllByRole('link', { name: 'Главная' });
      // Desktop navigation + NO mobile navigation initially
      expect(mobileNavItems.length).toBe(1);
    });

    it('should toggle mobile menu when button is clicked', async () => {
      const user = userEvent.setup();
      render(<Header />);

      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      await user.click(menuButton);

      // После клика меню должно открыться
      expect(screen.getByRole('button', { name: 'Закрыть меню' })).toBeInTheDocument();

      // Проверяем наличие мобильной навигации
      const mobileNavItems = screen.getAllByRole('link', { name: 'Главная' });
      expect(mobileNavItems.length).toBe(2); // Desktop + Mobile
    });

    it('should close mobile menu when close button is clicked', async () => {
      const user = userEvent.setup();
      render(<Header />);

      // Открываем меню
      const openButton = screen.getByRole('button', { name: 'Открыть меню' });
      await user.click(openButton);

      // Закрываем меню
      const closeButton = screen.getByRole('button', { name: 'Закрыть меню' });
      await user.click(closeButton);

      // Проверяем что кнопка снова "Открыть меню"
      expect(screen.getByRole('button', { name: 'Открыть меню' })).toBeInTheDocument();
    });

    it('should have correct aria-expanded attribute', async () => {
      const user = userEvent.setup();
      render(<Header />);

      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      expect(menuButton).toHaveAttribute('aria-expanded', 'false');

      await user.click(menuButton);
      expect(screen.getByRole('button', { name: 'Закрыть меню' })).toHaveAttribute(
        'aria-expanded',
        'true'
      );
    });
  });

  describe('Accessibility', () => {
    it('should have proper ARIA labels for action links', () => {
      render(<Header />);

      expect(screen.getByRole('link', { name: /Поиск/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Избранное/i })).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Корзина/i })).toBeInTheDocument();
    });

    it('should have focus styles on interactive elements', () => {
      render(<Header />);

      const searchLink = screen.getByRole('link', { name: /Поиск/i });
      expect(searchLink).toHaveClass('focus:ring-2', 'focus:ring-primary');
    });

    it('should use semantic HTML nav elements', () => {
      render(<Header />);

      const navElements = screen.getAllByRole('navigation');
      expect(navElements.length).toBeGreaterThan(0);
    });

    it('should render Partners link', () => {
      render(<Header />);
      const partnersLink = screen.getByRole('link', { name: 'Партнёрам' });
      expect(partnersLink).toBeInTheDocument();
      expect(partnersLink).toHaveAttribute('href', '/partners');
    });

    it('should apply relative positioning for active state styles', () => {
      render(<Header />);
      const partnersLink = screen.getByRole('link', { name: 'Партнёрам' });

      // Should have relative class for positioning the active state underline
      expect(partnersLink).toHaveClass('relative');
    });
  });

  describe('Styling', () => {
    it('should have correct header height (60px)', () => {
      render(<Header />);

      const header = screen.getByRole('banner');
      const innerDiv = header.querySelector('div > div');
      expect(innerDiv).toHaveClass('h-[60px]');
    });

    it('should have correct shadow styling', () => {
      render(<Header />);

      const header = screen.getByRole('banner');
      expect(header).toHaveClass('shadow-[0_6px_16px_rgba(31,42,68,0.05)]');
    });

    it('should have sticky positioning', () => {
      render(<Header />);

      const header = screen.getByRole('banner');
      expect(header).toHaveClass('sticky', 'top-0', 'z-50');
    });

    it('should apply correct Cart Badge colors', () => {
      const items = [createMockCartItem({ quantity: 1 })];
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      render(<Header />);

      const badge = screen.getAllByText('1')[0];
      expect(badge).toHaveClass('bg-accent-danger-bg', 'text-accent-danger');
    });

    it('should apply correct B2B badge colors', () => {
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(true);
      render(<Header />);

      const b2bBadge = screen.getByText('B2B');
      expect(b2bBadge).toHaveClass('bg-accent-danger-bg', 'text-accent-danger');
    });
  });

  describe('Logout Button', () => {
    describe('Authenticated User', () => {
      beforeEach(() => {
        vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(true);
        vi.mocked(authSelectors.useUser).mockReturnValue({
          id: 1,
          email: 'user@example.com',
          first_name: 'Иван',
          last_name: 'Иванов',
          phone: '+79001234567',
          role: 'retail',
        });
        vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);
      });

      it('should display logout button for authenticated users (desktop)', () => {
        render(<Header />);

        const logoutButton = screen.getByTestId('logout-button');
        expect(logoutButton).toBeInTheDocument();
        expect(logoutButton).toHaveAttribute('aria-label', 'Выйти из аккаунта');
      });

      it('should display logout button for authenticated users (mobile)', async () => {
        const user = userEvent.setup();
        render(<Header />);

        // Open mobile menu
        const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
        await user.click(menuButton);

        const logoutButtonMobile = screen.getByTestId('logout-button-mobile');
        expect(logoutButtonMobile).toBeInTheDocument();
        expect(logoutButtonMobile).toHaveAttribute('aria-label', 'Выйти из аккаунта');
      });

      it('should call authStore.logout() on desktop button click', async () => {
        const user = userEvent.setup();
        render(<Header />);

        const logoutButton = screen.getByTestId('logout-button');
        await user.click(logoutButton);

        expect(mockLogout).toHaveBeenCalled();
      });

      it('should redirect to home page after logout (desktop)', async () => {
        const user = userEvent.setup();
        render(<Header />);

        const logoutButton = screen.getByTestId('logout-button');
        await user.click(logoutButton);

        expect(mockPush).toHaveBeenCalledWith('/');
      });

      it('should call authStore.logout() and redirect on mobile button click', async () => {
        const user = userEvent.setup();
        render(<Header />);

        // Open mobile menu
        const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
        await user.click(menuButton);

        // Click logout button in mobile menu
        const logoutButtonMobile = screen.getByTestId('logout-button-mobile');
        await user.click(logoutButtonMobile);

        // Check that logout was called
        expect(mockLogout).toHaveBeenCalled();
        expect(mockPush).toHaveBeenCalledWith('/');
      });

      it('should close mobile menu after logout', async () => {
        const user = userEvent.setup();
        render(<Header />);

        // Open mobile menu
        const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
        await user.click(menuButton);

        // Click logout button in mobile menu
        const logoutButtonMobile = screen.getByTestId('logout-button-mobile');
        await user.click(logoutButtonMobile);

        // Check that mobile menu is closed (logout button no longer visible)
        expect(screen.queryByTestId('logout-button-mobile')).not.toBeInTheDocument();
      });
    });

    describe('Unauthenticated User', () => {
      beforeEach(() => {
        vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(false);
        vi.mocked(authSelectors.useUser).mockReturnValue(null);
        vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);
      });

      it('should NOT display logout button for unauthenticated users', () => {
        render(<Header />);

        expect(screen.queryByTestId('logout-button')).not.toBeInTheDocument();
        expect(screen.queryByTestId('logout-button-mobile')).not.toBeInTheDocument();
      });
    });
  });

  describe('Automated Accessibility (axe-core)', () => {
    it('should have no accessibility violations (unauthenticated)', async () => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(false);
      vi.mocked(authSelectors.useUser).mockReturnValue(null);
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);

      const { container } = render(<Header />);
      const results = await axe(container);

      expect(results.violations).toEqual([]);
    });

    it('should have no accessibility violations (authenticated B2C)', async () => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(true);
      vi.mocked(authSelectors.useUser).mockReturnValue({
        id: 1,
        email: 'user@example.com',
        first_name: 'Иван',
        last_name: 'Иванов',
        phone: '+79001234567',
        role: 'retail',
      });
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(false);

      const { container } = render(<Header />);
      const results = await axe(container);

      expect(results.violations).toEqual([]);
    });

    it('should have no accessibility violations (authenticated B2B)', async () => {
      vi.mocked(authSelectors.useIsAuthenticated).mockReturnValue(true);
      vi.mocked(authSelectors.useUser).mockReturnValue({
        id: 2,
        email: 'b2b@example.com',
        first_name: 'Петр',
        last_name: 'Петров',
        phone: '+79007654321',
        role: 'wholesale_level1',
        company_name: 'ООО "Спорт"',
        tax_id: '1234567890',
        is_verified: true,
      });
      vi.mocked(authSelectors.useIsB2BUser).mockReturnValue(true);

      const { container } = render(<Header />);
      const results = await axe(container);

      expect(results.violations).toEqual([]);
    });

    it('should have no accessibility violations with cart items', async () => {
      const items = [
        createMockCartItem({
          id: 1,
          product: { id: 1, name: 'Product 1', slug: 'product-1', image: null },
          quantity: 1,
        }),
        createMockCartItem({
          id: 2,
          product: { id: 2, name: 'Product 2', slug: 'product-2', image: null },
          quantity: 2,
        }),
      ];
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      const { container } = render(<Header />);
      const results = await axe(container);

      expect(results.violations).toEqual([]);
    });

    it('should have no accessibility violations with mobile menu open', async () => {
      const user = userEvent.setup();
      const { container } = render(<Header />);

      const menuButton = screen.getByRole('button', { name: 'Открыть меню' });
      await user.click(menuButton);

      const results = await axe(container);
      expect(results.violations).toEqual([]);
    });

    it('should verify color contrast for Cart Badge (#A63232 on #F9E1E1)', async () => {
      const items = [createMockCartItem({ quantity: 1 })];
      vi.mocked(useCartStore).mockImplementation(selector => selector(createMockCartStore(items)));

      const { container } = render(<Header />);
      const results = await axe(container, {
        rules: {
          'color-contrast': { enabled: true },
        },
      });

      expect(results.violations).toEqual([]);
    });
  });
});

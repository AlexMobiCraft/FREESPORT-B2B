/**
 * Интеграционные тесты для главной страницы (/)
 *
 * Проверяет:
 * - Корректный рендеринг страницы на роуте /
 * - Наличие SEO метатегов
 * - Интеграцию с HeroSection
 * - SSR-загрузку featured brands
 * - Адаптивность на разных viewport размерах
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import BlueHomePage, { metadata, revalidate } from '../page';
import { ToastProvider } from '@/components/ui/Toast/ToastProvider';

// Mock authStore state (mutable)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let mockAuthState: any = {
  user: null,
  isAuthenticated: false,
  accessToken: null,
  refreshToken: null,
  setTokens: vi.fn(),
  setUser: vi.fn(),
  logout: vi.fn(),
  getRefreshToken: vi.fn().mockReturnValue(null),
};

// Mock Zustand store with getState method
vi.mock('@/stores/authStore', () => ({
  useAuthStore: Object.assign(
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    vi.fn((selector: any) => {
      return selector ? selector(mockAuthState) : mockAuthState;
    }),
    {
      getState: () => mockAuthState,
    }
  ),
  authSelectors: {
    useUser: () => mockAuthState.user,
    useIsAuthenticated: () => mockAuthState.isAuthenticated,
  },
}));

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

vi.mock('@/services/categoriesService', () => ({
  default: {
    getCategories: vi.fn().mockResolvedValue([
      { id: 1, name: 'Обувь', slug: 'shoes', icon: '👟', products_count: 10 },
      { id: 2, name: 'Одежда', slug: 'clothing', icon: '👕', products_count: 5 },
    ]),
    getCategoryBySlug: vi.fn(),
  },
}));

const mockGetFeatured = vi.fn().mockResolvedValue([
  { id: 1, name: 'Nike', slug: 'nike', image: '/media/brands/nike.png', is_featured: true },
  { id: 2, name: 'Adidas', slug: 'adidas', image: '/media/brands/adidas.png', is_featured: true },
]);

vi.mock('@/services/brandsService', () => ({
  default: {
    getFeatured: (...args: unknown[]) => mockGetFeatured(...args),
  },
}));

/**
 * Helper: await async server component and render the returned JSX
 */
async function renderAsyncPage() {
  const jsx = await BlueHomePage();
  return render(<ToastProvider>{jsx}</ToastProvider>);
}

describe('Главная страница (/)', () => {
  beforeEach(() => {
    // Reset mock state before each test
    mockAuthState = {
      user: null,
      isAuthenticated: false,
      accessToken: null,
      refreshToken: null,
      setTokens: vi.fn(),
      setUser: vi.fn(),
      logout: vi.fn(),
      getRefreshToken: vi.fn().mockReturnValue(null),
    };
    mockGetFeatured.mockClear();
  });

  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', async () => {
      const { container } = await renderAsyncPage();
      expect(container).toBeInTheDocument();
    });

    it('должна содержать HeroSection компонент', async () => {
      await renderAsyncPage();

      // Проверка наличия hero секции по заголовку (ждём загрузку)
      expect(
        await screen.findByText(/Спортивные товары для профессионалов и любителей/i)
      ).toBeInTheDocument();
    });

    it('должна содержать секцию с популярными категориями', async () => {
      await renderAsyncPage();

      expect(await screen.findByText(/Популярные категории/i)).toBeInTheDocument();
    });
  });

  describe('SSR data fetching', () => {
    it('AC1: вызывает brandsService.getFeatured() на сервере', async () => {
      await renderAsyncPage();

      expect(mockGetFeatured).toHaveBeenCalledTimes(1);
    });

    it('AC1: передаёт featured brands в HomePage', async () => {
      await renderAsyncPage();

      // BrandsBlock рендерится с данными брендов
      expect(screen.getByLabelText('Популярные бренды')).toBeInTheDocument();
    });

    it('рендерит страницу без ошибок при сбое API и логирует ошибку', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      mockGetFeatured.mockRejectedValueOnce(new Error('API Error'));

      const { container } = await renderAsyncPage();

      expect(container).toBeInTheDocument();
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        '[BlueHomePage] Failed to fetch featured brands:',
        expect.any(Error)
      );
      consoleErrorSpy.mockRestore();
    });
  });

  describe('SEO Metadata', () => {
    it('должна содержать правильный title', () => {
      expect(metadata.title).toBe('Спортивные товары оптом и в розницу');
    });

    it('должна содержать правильный description', () => {
      expect(metadata.description).toContain('Платформа для оптовых и розничных продаж');
      expect(metadata.description).toContain('спортивных товаров');
    });

    it('должна содержать keywords', () => {
      expect(metadata.keywords).toBeDefined();
      expect(metadata.keywords).toContain('спортивные товары оптом');
    });

    it('должна содержать OpenGraph метатеги', () => {
      expect(metadata.openGraph).toBeDefined();
      expect(metadata.openGraph?.title).toBe('Спортивные товары оптом и в розницу');
      expect(metadata.openGraph?.description).toContain('Платформа для оптовых и розничных продаж');
    });

    it('должна содержать OpenGraph изображение', () => {
      expect(metadata.openGraph?.images).toBeDefined();
      expect(Array.isArray(metadata.openGraph?.images)).toBe(true);
      expect(metadata.openGraph?.images).toContain('/og-image.jpg');
    });

    it('должна содержать Twitter метатеги', () => {
      expect(metadata.twitter).toBeDefined();
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      expect((metadata.twitter as any)?.card).toBe('summary_large_image');
      expect(metadata.twitter?.title).toBe('Спортивные товары оптом и в розницу');
    });
  });

  describe('SSG/ISR конфигурация', () => {
    it('должна иметь правильное значение revalidate для ISR', () => {
      expect(revalidate).toBe(3600); // 1 час в секундах
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнер', async () => {
      const { container } = await renderAsyncPage();

      // Проверка наличия контейнеров с max-width
      const containers = container.querySelectorAll('.max-w-7xl, .mx-auto');
      expect(containers.length).toBeGreaterThan(0);
    });

    it('должна содержать адаптивные padding классы', async () => {
      const { container } = await renderAsyncPage();

      // Проверка responsive padding (sm:px-6, lg:px-8)
      const responsiveContainers = container.querySelectorAll('[class*="px-"]');
      expect(responsiveContainers.length).toBeGreaterThan(0);
    });
  });

  describe('Интеграция с authStore', () => {
    it('должна корректно работать с авторизованным B2B пользователем', async () => {
      mockAuthState.user = {
        id: 1,
        email: 'b2b@test.com',
        first_name: 'Test',
        last_name: 'B2B',
        phone: '+79001234567',
        role: 'wholesale_level1',
        is_verified: true,
      };
      mockAuthState.isAuthenticated = true;
      mockAuthState.accessToken = 'mock-token';

      await renderAsyncPage();

      // HeroSection должен показывать баннер (может быть любой текст из баннера)
      await waitFor(() => {
        expect(
          screen.getByText(/Спортивные товары для профессионалов и любителей/i)
        ).toBeInTheDocument();
      });
    });

    it('должна корректно работать с авторизованным B2C пользователем', async () => {
      mockAuthState.user = {
        id: 2,
        email: 'retail@test.com',
        first_name: 'Test',
        last_name: 'Retail',
        phone: '+79001234567',
        role: 'retail',
        is_verified: true,
      };
      mockAuthState.isAuthenticated = true;
      mockAuthState.accessToken = 'mock-token';

      await renderAsyncPage();

      // HeroSection должен показывать баннер (может быть любой текст из баннера)
      await waitFor(() => {
        expect(
          screen.getByText(/Спортивные товары для профессионалов и любителей/i)
        ).toBeInTheDocument();
      });
    });
  });
});

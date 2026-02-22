/**
 * Unit тесты для HeroSection компонента
 *
 * Проверяет:
 * - Загрузку баннеров из API
 * - Skeleton loading state
 * - Fallback на статические баннеры при ошибке или пустом ответе
 * - Карусель для нескольких баннеров
 * - Рендеринг правильного баннера для разных ролей пользователей
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import HeroSection from '../HeroSection';
import { useAuthStore } from '@/stores/authStore';
import bannersService from '@/services/bannersService';
import type { User } from '@/types/api';

// Mock Zustand store
vi.mock('@/stores/authStore');

// Mock bannersService
vi.mock('@/services/bannersService');

// Mock Next.js Link component
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
  ),
}));

describe('HeroSection Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Loading State', () => {
    it('должен показывать skeleton loader во время загрузки', () => {
      // Mock never-resolving promise для имитации загрузки
      vi.mocked(bannersService.getActive).mockReturnValue(new Promise(() => {}));

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      expect(screen.getByTestId('hero-skeleton')).toBeInTheDocument();
      expect(screen.getByLabelText('Hero section loading')).toBeInTheDocument();
    });
  });

  describe('Загрузка баннеров из API', () => {
    it('должен отображать баннер из API после успешной загрузки', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([
        {
          id: 1,
          type: 'hero',
          title: 'API Banner Title',
          subtitle: 'API Banner Subtitle',
          image_url: '/media/banners/test.jpg',
          image_alt: 'Test banner',
          cta_text: 'Shop now',
          cta_link: '/catalog',
        },
      ]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText('API Banner Title')).toBeInTheDocument();
        expect(screen.getByText('API Banner Subtitle')).toBeInTheDocument();
        expect(screen.getByText('Shop now')).toBeInTheDocument();
      });
    });

    it('должен отображать несколько баннеров с индикаторами карусели', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([
        {
          id: 1,
          type: 'hero',
          title: 'First Banner',
          subtitle: 'First Subtitle',
          image_url: '/media/banners/first.jpg',
          image_alt: 'First banner',
          cta_text: 'Click here',
          cta_link: '/first',
        },
        {
          id: 2,
          type: 'hero',
          title: 'Second Banner',
          subtitle: 'Second Subtitle',
          image_url: '/media/banners/second.jpg',
          image_alt: 'Second banner',
          cta_text: 'Click there',
          cta_link: '/second',
        },
      ]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText('First Banner')).toBeInTheDocument();
      });

      // Проверяем наличие индикаторов карусели
      const indicators = screen.getAllByLabelText(/Go to banner/i);
      expect(indicators).toHaveLength(2);
    });
  });

  describe('Fallback на статические баннеры', () => {
    it('должен отображать статический баннер при ошибке API', async () => {
      vi.mocked(bannersService.getActive).mockRejectedValue(new Error('API Error'));

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(
          screen.getByText(/FREESPORT - Спортивные товары для профессионалов и любителей/i)
        ).toBeInTheDocument();
      });
    });

    it('должен отображать статический баннер при пустом ответе API', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(
          screen.getByText(/FREESPORT - Спортивные товары для профессионалов и любителей/i)
        ).toBeInTheDocument();
      });
    });

    it('должен отображать B2B статический баннер для wholesale пользователя при ошибке API', async () => {
      vi.mocked(bannersService.getActive).mockRejectedValue(new Error('API Error'));

      const mockUser: User = {
        id: 1,
        email: 'b2b@test.com',
        first_name: 'Test',
        last_name: 'B2B',
        phone: '+79001234567',
        role: 'wholesale_level1',
      };

      vi.mocked(useAuthStore).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        accessToken: 'mock-token',
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText(/Оптовые поставки спортивных товаров/i)).toBeInTheDocument();
      });
    });

    it('должен отображать B2C статический баннер для retail пользователя при ошибке API', async () => {
      vi.mocked(bannersService.getActive).mockRejectedValue(new Error('API Error'));

      const mockUser: User = {
        id: 4,
        email: 'retail@test.com',
        first_name: 'Test',
        last_name: 'Retail',
        phone: '+79001234567',
        role: 'retail',
      };

      vi.mocked(useAuthStore).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        accessToken: 'mock-token',
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText(/Новая коллекция 2025/i)).toBeInTheDocument();
      });
    });
  });

  describe('Рендеринг баннеров для разных ролей (статические)', () => {
    beforeEach(() => {
      // Mock пустой ответ API для использования fallback
      vi.mocked(bannersService.getActive).mockResolvedValue([]);
    });

    it('должен отображать B2B баннер для wholesale_level1 пользователя', async () => {
      const mockUser: User = {
        id: 1,
        email: 'b2b@test.com',
        first_name: 'Test',
        last_name: 'B2B',
        phone: '+79001234567',
        role: 'wholesale_level1',
      };

      vi.mocked(useAuthStore).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        accessToken: 'mock-token',
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText(/Оптовые поставки спортивных товаров/i)).toBeInTheDocument();
        expect(
          screen.getByText(/Специальные цены для бизнеса. Персональный менеджер и гибкие условия./i)
        ).toBeInTheDocument();
        expect(screen.getByText(/Узнать оптовые условия/i)).toBeInTheDocument();
      });
    });

    it('должен отображать B2C баннер для retail пользователя', async () => {
      const mockUser: User = {
        id: 4,
        email: 'retail@test.com',
        first_name: 'Test',
        last_name: 'Retail',
        phone: '+79001234567',
        role: 'retail',
      };

      vi.mocked(useAuthStore).mockReturnValue({
        user: mockUser,
        isAuthenticated: true,
        accessToken: 'mock-token',
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(screen.getByText(/Новая коллекция 2025/i)).toBeInTheDocument();
        expect(
          screen.getByText(
            /Стиль и качество для вашего спорта. Эксклюзивные новинки уже в продаже./i
          )
        ).toBeInTheDocument();
        expect(screen.getByText(/Перейти в каталог/i)).toBeInTheDocument();
      });
    });

    it('должен отображать универсальный баннер для неавторизованного пользователя', async () => {
      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        expect(
          screen.getByText(/FREESPORT - Спортивные товары для профессионалов и любителей/i)
        ).toBeInTheDocument();
        expect(
          screen.getByText(/5 брендов. 1000\+ товаров. Доставка по всей России./i)
        ).toBeInTheDocument();
        expect(screen.getByText(/Начать покупки/i)).toBeInTheDocument();
      });
    });
  });

  describe('Проверка CTA кнопок', () => {
    it('API баннер должен содержать правильную ссылку', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([
        {
          id: 1,
          type: 'hero',
          title: 'Test Banner',
          subtitle: 'Test Subtitle',
          image_url: '/media/banners/test.jpg',
          image_alt: 'Test banner',
          cta_text: 'Click here',
          cta_link: '/custom-link',
        },
      ]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        const link = screen.getByRole('link');
        expect(link).toHaveAttribute('href', '/custom-link');
      });
    });
  });

  describe('Accessibility', () => {
    it('должен иметь accessibility атрибуты', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      const { container } = render(<HeroSection />);

      await waitFor(() => {
        const section = container.querySelector('section');
        expect(section).toHaveAttribute('aria-label', 'Hero section');
      });
    });

    it('должен иметь правильный alt текст для изображения из API', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([
        {
          id: 1,
          type: 'hero',
          title: 'Test Banner',
          subtitle: 'Test Subtitle',
          image_url: '/media/banners/test.jpg',
          image_alt: 'Test banner alt text',
          cta_text: 'Click here',
          cta_link: '/test',
        },
      ]);

      vi.mocked(useAuthStore).mockReturnValue({
        user: null,
        isAuthenticated: false,
        accessToken: null,
        setTokens: vi.fn(),
        setUser: vi.fn(),
        logout: vi.fn(),
        getRefreshToken: vi.fn(),
      });

      render(<HeroSection />);

      await waitFor(() => {
        const img = screen.getByAltText('Test banner alt text');
        expect(img).toBeInTheDocument();
      });
    });
  });
});

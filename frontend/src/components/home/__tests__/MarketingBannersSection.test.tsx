/**
 * Unit тесты для MarketingBannersSection
 *
 * Покрывает AC1–AC6:
 * - AC1: секция рендерится на странице
 * - AC2: пустое состояние (null)
 * - AC3: skeleton loader
 * - AC4: обработка ошибки загрузки изображения
 * - AC5: ErrorBoundary перехватывает ошибку рендера
 * - AC6: навигация по cta_link
 * - Security: cta_link validation guard
 * - Reliability: image_url pre-check
 */

import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import {
  MarketingBannersSection,
  MarketingBannerErrorBoundary,
} from '../MarketingBannersSection';
import bannersService from '@/services/bannersService';
import type { Banner } from '@/types/banners';

// Mock bannersService
vi.mock('@/services/bannersService');

// Mock Next.js Link
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    ...props
  }: {
    children: React.ReactNode;
    href: string;
    [key: string]: unknown;
  }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
}));

// Mock Next.js Image — render img with onError support
vi.mock('next/image', () => ({
  default: (props: {
    src: string;
    alt: string;
    onError?: () => void;
    fill?: boolean;
    sizes?: string;
    loading?: string;
    className?: string;
  }) => (
    // eslint-disable-next-line @next/next/no-img-element
    <img
      src={props.src}
      alt={props.alt}
      onError={props.onError}
      data-sizes={props.sizes}
      data-loading={props.loading}
      className={props.className}
    />
  ),
}));

// Mock useBannerCarousel
const mockOnDotButtonClick = vi.fn();
vi.mock('@/hooks/useBannerCarousel', () => ({
  useBannerCarousel: vi.fn(() => ({
    emblaRef: vi.fn(),
    selectedIndex: 0,
    scrollSnaps: [0],
    canScrollPrev: false,
    canScrollNext: false,
    scrollNext: vi.fn(),
    scrollPrev: vi.fn(),
    onDotButtonClick: mockOnDotButtonClick,
    scrollTo: vi.fn(),
  })),
}));

// Re-import for dynamic mock control
import { useBannerCarousel } from '@/hooks/useBannerCarousel';

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const mockMarketingBanners: Banner[] = [
  {
    id: 10,
    type: 'marketing',
    title: 'Летняя распродажа',
    subtitle: 'Скидки до 50%',
    image_url: '/media/banners/summer-sale.jpg',
    image_alt: 'Летняя распродажа баннер',
    cta_text: 'Купить со скидкой',
    cta_link: '/catalog?sale=summer',
  },
  {
    id: 11,
    type: 'marketing',
    title: 'Новая коллекция кроссовок',
    subtitle: 'Бренды Nike, Adidas, Puma',
    image_url: '/media/banners/sneakers.jpg',
    image_alt: 'Коллекция кроссовок',
    cta_text: 'Смотреть коллекцию',
    cta_link: '/catalog/sneakers',
  },
];

const threeBanners: Banner[] = [
  ...mockMarketingBanners,
  {
    id: 12,
    type: 'marketing',
    title: 'Зимний сезон',
    subtitle: 'Куртки и термобелье',
    image_url: '/media/banners/winter.jpg',
    image_alt: 'Зимний сезон баннер',
    cta_text: 'Смотреть',
    cta_link: '/catalog/winter',
  },
];

const singleBanner: Banner[] = [mockMarketingBanners[0]];

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('MarketingBannersSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: multi-banner carousel mock
    vi.mocked(useBannerCarousel).mockReturnValue({
      emblaRef: vi.fn(),
      selectedIndex: 0,
      scrollSnaps: [0, 1],
      canScrollPrev: false,
      canScrollNext: true,
      scrollNext: vi.fn(),
      scrollPrev: vi.fn(),
      onDotButtonClick: mockOnDotButtonClick,
      scrollTo: vi.fn(),
    });
  });

  // -------------------------------------------------------------------------
  // AC3: Skeleton loading state
  // -------------------------------------------------------------------------
  describe('AC3: Состояние загрузки', () => {
    it('должен показывать skeleton loader во время загрузки', () => {
      vi.mocked(bannersService.getActive).mockReturnValue(new Promise(() => {}));

      render(<MarketingBannersSection />);

      expect(screen.getByTestId('marketing-banners-skeleton')).toBeInTheDocument();
      expect(
        screen.getByLabelText('Маркетинговые баннеры загружаются')
      ).toBeInTheDocument();
    });

    it('skeleton должен содержать контейнер с фиксированным aspect-ratio', () => {
      vi.mocked(bannersService.getActive).mockReturnValue(new Promise(() => {}));

      const { container } = render(<MarketingBannersSection />);

      const skeleton = container.querySelector('[class*="aspect-"]');
      expect(skeleton).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // AC2: Пустое состояние
  // -------------------------------------------------------------------------
  describe('AC2: Пустое состояние', () => {
    it('должен рендерить null при пустом ответе API', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue([]);

      const { container } = render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.queryByTestId('marketing-banners-skeleton')
        ).not.toBeInTheDocument();
      });

      expect(
        screen.queryByTestId('marketing-banners-section')
      ).not.toBeInTheDocument();
      expect(container.innerHTML).toBe('');
    });

    it('должен рендерить null при ошибке API', async () => {
      vi.mocked(bannersService.getActive).mockRejectedValue(
        new Error('Network Error')
      );

      const { container } = render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.queryByTestId('marketing-banners-skeleton')
        ).not.toBeInTheDocument();
      });

      expect(container.innerHTML).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // AC1: Рендеринг секции
  // -------------------------------------------------------------------------
  describe('AC1: Рендеринг секции', () => {
    it('должен рендерить секцию с баннерами после успешной загрузки', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.getByTestId('marketing-banners-section')
        ).toBeInTheDocument();
      });

      expect(
        screen.getByLabelText('Маркетинговые предложения')
      ).toBeInTheDocument();
    });

    it('должен вызывать bannersService.getActive с типом marketing', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(bannersService.getActive).toHaveBeenCalledWith('marketing', expect.any(AbortSignal));
      });
    });

    it('должен рендерить изображения с корректными alt и sizes', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const img = screen.getByAltText('Летняя распродажа баннер');
        expect(img).toBeInTheDocument();
        expect(img).toHaveAttribute(
          'data-sizes',
          '(max-width: 768px) 100vw, 1280px'
        );
      });
    });
  });

  // -------------------------------------------------------------------------
  // AC6: Навигация по cta_link
  // -------------------------------------------------------------------------
  describe('AC6: Навигация по cta_link', () => {
    it('должен оборачивать баннер в ссылку с cta_link', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const link = screen.getByRole('link', { name: 'Летняя распродажа' });
        expect(link).toHaveAttribute('href', '/catalog?sale=summer');
      });
    });

    it('должен рендерить ссылки для всех баннеров', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const links = screen.getAllByRole('link');
        expect(links).toHaveLength(2);
        expect(links[0]).toHaveAttribute('href', '/catalog?sale=summer');
        expect(links[1]).toHaveAttribute('href', '/catalog/sneakers');
      });
    });
  });

  // -------------------------------------------------------------------------
  // Security: cta_link validation guard
  // -------------------------------------------------------------------------
  describe('Security: cta_link guard', () => {
    it('не должен рендерить ссылку для javascript: протокола', async () => {
      const maliciousBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: 'javascript:alert(1)',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(maliciousBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('не должен рендерить ссылку для data: протокола', async () => {
      const maliciousBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: 'data:text/html,<script>alert(1)</script>',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(maliciousBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('не должен рендерить ссылку для внешних URL', async () => {
      const externalBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: 'https://evil.com/phishing',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(externalBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('не должен рендерить ссылку для vbscript: протокола', async () => {
      const vbsBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: 'vbscript:MsgBox("xss")',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(vbsBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('не должен рендерить ссылку для protocol-relative URL (//evil.com)', async () => {
      const prBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: '//evil.com/phishing',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(prBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('не должен рендерить ссылку для cta_link с backslash', async () => {
      const backslashBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: '/catalog\\..\\admin',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(backslashBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('link')).not.toBeInTheDocument();
    });

    it('должен использовать trimmed href для ссылки с пробелами', async () => {
      const spacedBanner: Banner[] = [{
        ...mockMarketingBanners[0],
        cta_link: '  /catalog?sale=summer  ',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(spacedBanner);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const link = screen.getByRole('link', { name: 'Летняя распродажа' });
        expect(link).toHaveAttribute('href', '/catalog?sale=summer');
      });
    });

    it('должен рендерить ссылку для безопасных относительных путей', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const link = screen.getByRole('link', { name: 'Летняя распродажа' });
        expect(link).toHaveAttribute('href', '/catalog?sale=summer');
      });
    });
  });

  // -------------------------------------------------------------------------
  // Reliability: image_url pre-check
  // -------------------------------------------------------------------------
  describe('Reliability: image_url pre-check', () => {
    it('должен фильтровать баннеры с пустым image_url', async () => {
      const bannersWithEmpty: Banner[] = [
        mockMarketingBanners[0],
        { ...mockMarketingBanners[1], image_url: '' },
      ];
      vi.mocked(bannersService.getActive).mockResolvedValue(bannersWithEmpty);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.getByAltText('Летняя распродажа баннер')).toBeInTheDocument();
      expect(screen.queryByAltText('Коллекция кроссовок')).not.toBeInTheDocument();
    });

    it('должен рендерить null если все баннеры имеют пустой image_url', async () => {
      const allEmpty: Banner[] = [
        { ...mockMarketingBanners[0], image_url: '' },
        { ...mockMarketingBanners[1], image_url: '   ' },
      ];
      vi.mocked(bannersService.getActive).mockResolvedValue(allEmpty);

      const { container } = render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.queryByTestId('marketing-banners-skeleton')).not.toBeInTheDocument();
      });

      expect(container.innerHTML).toBe('');
    });
  });

  // -------------------------------------------------------------------------
  // Dots / carousel controls
  // -------------------------------------------------------------------------
  describe('Навигация карусели', () => {
    it('должен показывать dots при banners.length > 1', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const dots = screen.getAllByRole('button', { name: /Баннер \d+/ });
        expect(dots).toHaveLength(2);
      });
    });

    it('не должен показывать dots при одном баннере', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      expect(screen.queryByRole('button', { name: /Баннер \d+/ })).not.toBeInTheDocument();
    });

    it('должен вызывать onDotButtonClick при клике по точке', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const dots = screen.getAllByRole('button', { name: /Баннер \d+/ });
        fireEvent.click(dots[1]);
        expect(mockOnDotButtonClick).toHaveBeenCalledWith(1);
      });
    });
  });

  // -------------------------------------------------------------------------
  // Performance: autoplay/loop disabled for single banner
  // -------------------------------------------------------------------------
  describe('Performance: autoplay/loop при одном баннере', () => {
    it('должен вызывать useBannerCarousel с loop=false, autoplay=false при 1 баннере', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      // After banners load with 1 banner, hook should be called with loop=false, autoplay=false
      const lastCall = vi.mocked(useBannerCarousel).mock.calls.at(-1);
      expect(lastCall?.[0]).toMatchObject({
        loop: false,
        autoplay: false,
      });
    });

    it('должен вызывать useBannerCarousel с loop=true, autoplay=true при 2+ баннерах', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      const lastCall = vi.mocked(useBannerCarousel).mock.calls.at(-1);
      expect(lastCall?.[0]).toMatchObject({
        loop: true,
        autoplay: true,
      });
    });

    it('должен передавать autoplay профиль с stopOnInteraction=false и stopOnMouseEnter=true', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByTestId('marketing-banners-section')).toBeInTheDocument();
      });

      const lastCall = vi.mocked(useBannerCarousel).mock.calls.at(-1);
      expect(lastCall?.[0]).toMatchObject({
        loop: true,
        autoplay: true,
        autoplayDelay: 3000,
        stopOnInteraction: false,
        stopOnMouseEnter: true,
      });
    });
  });

  // -------------------------------------------------------------------------
  // AC4: Обработка ошибки загрузки изображения
  // -------------------------------------------------------------------------
  describe('AC4: Обработка ошибки загрузки изображения', () => {
    it('должен скрывать слайд при ошибке загрузки изображения', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.getByAltText('Летняя распродажа баннер')
        ).toBeInTheDocument();
      });

      // Trigger image error on first banner
      const img = screen.getByAltText('Летняя распродажа баннер');
      fireEvent.error(img);

      await waitFor(() => {
        expect(
          screen.queryByAltText('Летняя распродажа баннер')
        ).not.toBeInTheDocument();
      });

      // Second banner should still be visible
      expect(screen.getByAltText('Коллекция кроссовок')).toBeInTheDocument();
    });

    it('должен скрывать всю секцию если все изображения не загрузились', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(singleBanner);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      const { container } = render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.getByAltText('Летняя распродажа баннер')
        ).toBeInTheDocument();
      });

      const img = screen.getByAltText('Летняя распродажа баннер');
      fireEvent.error(img);

      await waitFor(() => {
        expect(container.innerHTML).toBe('');
      });
    });

    it('должен корректно работать с 3+ баннерами при ошибке одного изображения', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(threeBanners);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0, 1, 2],
        canScrollPrev: false,
        canScrollNext: true,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByAltText('Летняя распродажа баннер')).toBeInTheDocument();
        expect(screen.getByAltText('Коллекция кроссовок')).toBeInTheDocument();
        expect(screen.getByAltText('Зимний сезон баннер')).toBeInTheDocument();
      });

      // Fail first banner image
      const img = screen.getByAltText('Летняя распродажа баннер');
      fireEvent.error(img);

      await waitFor(() => {
        expect(screen.queryByAltText('Летняя распродажа баннер')).not.toBeInTheDocument();
      });

      // Other 2 banners remain visible
      expect(screen.getByAltText('Коллекция кроссовок')).toBeInTheDocument();
      expect(screen.getByAltText('Зимний сезон баннер')).toBeInTheDocument();
    });

    it('dots должны синхронизироваться с visible banners после image error', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(threeBanners);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0, 1, 2],
        canScrollPrev: false,
        canScrollNext: true,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      // Initially 3 dots
      await waitFor(() => {
        const dots = screen.getAllByRole('button', { name: /Баннер \d+/ });
        expect(dots).toHaveLength(3);
      });

      // Fail first banner image
      const img = screen.getByAltText('Летняя распродажа баннер');
      fireEvent.error(img);

      // After image error, dots should be 2 (matching visible banners)
      await waitFor(() => {
        const dots = screen.getAllByRole('button', { name: /Баннер \d+/ });
        expect(dots).toHaveLength(2);
      });
    });
  });

  // -------------------------------------------------------------------------
  // AC5: ErrorBoundary
  // -------------------------------------------------------------------------
  describe('AC5: ErrorBoundary', () => {
    it('должен перехватывать ошибку рендера и скрывать секцию', () => {
      const ThrowingComponent = () => {
        throw new Error('Render crash');
      };

      // Suppress console.error for expected error boundary trigger
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {});

      const { container } = render(
        <MarketingBannerErrorBoundary>
          <ThrowingComponent />
        </MarketingBannerErrorBoundary>
      );

      expect(container.innerHTML).toBe('');
      consoleSpy.mockRestore();
    });

    it('должен рендерить children при отсутствии ошибок', () => {
      render(
        <MarketingBannerErrorBoundary>
          <div data-testid="child-content">Content</div>
        </MarketingBannerErrorBoundary>
      );

      expect(screen.getByTestId('child-content')).toBeInTheDocument();
    });
  });

  // -------------------------------------------------------------------------
  // Accessibility
  // -------------------------------------------------------------------------
  describe('Accessibility', () => {
    it('должен иметь aria-label на секции', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.getByLabelText('Маркетинговые предложения')
        ).toBeInTheDocument();
      });
    });

    it('должен иметь alt текст для каждого изображения', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(
          screen.getByAltText('Летняя распродажа баннер')
        ).toBeInTheDocument();
        expect(
          screen.getByAltText('Коллекция кроссовок')
        ).toBeInTheDocument();
      });
    });

    it('должен использовать title как fallback для пустого image_alt', async () => {
      const bannerNoAlt: Banner[] = [{
        ...mockMarketingBanners[0],
        image_alt: '',
      }];
      vi.mocked(bannersService.getActive).mockResolvedValue(bannerNoAlt);
      vi.mocked(useBannerCarousel).mockReturnValue({
        emblaRef: vi.fn(),
        selectedIndex: 0,
        scrollSnaps: [0],
        canScrollPrev: false,
        canScrollNext: false,
        scrollNext: vi.fn(),
        scrollPrev: vi.fn(),
        onDotButtonClick: mockOnDotButtonClick,
        scrollTo: vi.fn(),
      });

      render(<MarketingBannersSection />);

      await waitFor(() => {
        // Fallback: image_alt пустой → используется banner.title
        const img = screen.getByAltText('Летняя распродажа');
        expect(img).toBeInTheDocument();
      });
    });

    it('dots должны иметь aria-label и aria-current', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        const dots = screen.getAllByRole('button', { name: /Баннер \d+/ });
        expect(dots[0]).toHaveAttribute('aria-label', 'Баннер 1');
        expect(dots[1]).toHaveAttribute('aria-label', 'Баннер 2');
        expect(dots[0]).toHaveAttribute('aria-current', 'true');
        expect(dots[1]).not.toHaveAttribute('aria-current');
      });
    });

    it('dots контейнер должен иметь role=group', async () => {
      vi.mocked(bannersService.getActive).mockResolvedValue(mockMarketingBanners);

      render(<MarketingBannersSection />);

      await waitFor(() => {
        expect(screen.getByRole('group', { name: 'Навигация по баннерам' })).toBeInTheDocument();
      });
    });
  });

  // -------------------------------------------------------------------------
  // displayName
  // -------------------------------------------------------------------------
  it('должен иметь displayName', () => {
    expect(MarketingBannersSection.displayName).toBe('MarketingBannersSection');
  });
});

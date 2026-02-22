/**
 * Unit-тесты для страницы списка новостей (/news)
 * Story 20.2 - AC 11
 *
 * Проверяет:
 * - Рендеринг списка новостей
 * - Breadcrumb навигацию
 * - Пагинацию
 * - Empty state
 * - SEO metadata
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import NewsPage, { metadata } from '../page';
import { newsService } from '@/services/newsService';
import type { NewsList } from '@/types/api';

// Mock Next.js components
vi.mock('next/link', () => ({
  default: ({
    children,
    href,
    className,
  }: {
    children: React.ReactNode;
    href: string;
    className?: string;
  }) => (
    <a href={href} className={className}>
      {children}
    </a>
  ),
}));

// eslint-disable-next-line @next/next/no-img-element
const MockImage = ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />;

vi.mock('next/image', () => ({
  default: MockImage,
}));

// Mock newsService
vi.mock('@/services/newsService', () => ({
  newsService: {
    getNewsList: vi.fn(),
  },
}));

// Mock NewsCard component
vi.mock('@/components/home/NewsCard', () => ({
  NewsCard: ({ title, excerpt, slug }: { title: string; excerpt: string; slug: string }) => (
    <a href={`/news/${slug}`}>
      <article data-testid="news-card">
        <h3>{title}</h3>
        <p>{excerpt}</p>
      </article>
    </a>
  ),
}));

const mockNewsData: NewsList = {
  count: 25,
  next: 'http://api.example.com/news?page=2',
  previous: null,
  results: [
    {
      id: 1,
      title: 'Новость 1',
      slug: 'news-1',
      excerpt: 'Краткое описание новости 1',
      content: 'Полное содержание новости 1',
      image: 'http://example.com/image1.jpg',
      published_at: '2025-12-26T10:00:00Z',
      created_at: '2025-12-25T10:00:00Z',
      updated_at: '2025-12-25T10:00:00Z',
      author: 'Автор 1',
    },
    {
      id: 2,
      title: 'Новость 2',
      slug: 'news-2',
      excerpt: 'Краткое описание новости 2',
      image: null,
      published_at: '2025-12-25T10:00:00Z',
      created_at: '2025-12-24T10:00:00Z',
      updated_at: '2025-12-24T10:00:00Z',
    },
  ],
};

describe('NewsPage (/news)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(container).toBeInTheDocument();
    });

    it('должна отображать заголовок h1', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Новости');
    });

    it('должна отображать описание секции', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(
        screen.getByText(/Актуальные новости, акции и события компании FREESPORT/i)
      ).toBeInTheDocument();
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const nav = container.querySelector('nav[aria-label="Breadcrumb"]');
      expect(nav).toBeInTheDocument();
      expect(screen.getByText('Главная')).toBeInTheDocument();
    });

    it('должна иметь ссылку на главную', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });

  describe('Список новостей', () => {
    it('должна рендерить карточки новостей', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const cards = screen.getAllByTestId('news-card');
      expect(cards).toHaveLength(2);
    });

    it('должна передавать правильные props в NewsCard', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('Новость 1')).toBeInTheDocument();
      expect(screen.getByText('Краткое описание новости 1')).toBeInTheDocument();
    });

    it('должна иметь ссылки на детальные страницы новостей', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const links = container.querySelectorAll('a[href^="/news/"]');
      expect(links.length).toBeGreaterThanOrEqual(2);
    });

    it('должна использовать grid layout для карточек', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const grid = container.querySelector('[class*="grid-cols"]');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Пагинация', () => {
    it('должна отображать кнопки пагинации когда страниц > 1', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('← Назад')).toBeInTheDocument();
      expect(screen.getByText('Вперёд →')).toBeInTheDocument();
    });

    it('должна отображать номера страниц', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('должна выделять текущую страницу', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({ page: '1' }) }));
      const currentPageLink = screen.getByText('1').closest('a');
      expect(currentPageLink).toHaveClass('bg-primary');
    });

    it('не должна отображать пагинацию когда 1 страница', async () => {
      const singlePageData = {
        ...mockNewsData,
        count: 5, // Меньше 12
      };
      vi.mocked(newsService.getNewsList).mockResolvedValue(singlePageData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.queryByText('← Назад')).not.toBeInTheDocument();
    });

    it('должна запрашивать правильную страницу из searchParams', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      render(await NewsPage({ searchParams: Promise.resolve({ page: '2' }) }));
      expect(newsService.getNewsList).toHaveBeenCalledWith({ page: 2 });
    });
  });

  describe('Empty State', () => {
    it('должна отображать empty state когда нет новостей', async () => {
      const emptyData: NewsList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(newsService.getNewsList).mockResolvedValue(emptyData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('Новостей пока нет')).toBeInTheDocument();
      expect(
        screen.getByText(/Скоро здесь появятся новости о наших акциях и событиях/i)
      ).toBeInTheDocument();
    });

    it('должна отображать иконку в empty state', async () => {
      const emptyData: NewsList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(newsService.getNewsList).mockResolvedValue(emptyData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const icon = container.querySelector('[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });

    it('не должна отображать grid когда нет новостей', async () => {
      const emptyData: NewsList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(newsService.getNewsList).mockResolvedValue(emptyData);
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(screen.queryByTestId('news-card')).not.toBeInTheDocument();
    });
  });

  describe('SEO Metadata', () => {
    it('должна содержать правильный title', () => {
      expect(metadata.title).toBe('Новости | FREESPORT');
    });

    it('должна содержать правильный description', () => {
      expect(metadata.description).toContain('Новости компании FREESPORT');
      expect(metadata.description).toContain('Акции');
      expect(metadata.description).toContain('события');
    });

    it('должна содержать OpenGraph метатеги', () => {
      expect(metadata.openGraph).toBeDefined();
      expect(metadata.openGraph?.title).toBe('Новости | FREESPORT');
      expect(metadata.openGraph?.description).toBe('Новости компании FREESPORT');
    });
  });

  describe('Обработка ошибок', () => {
    it('должна корректно обрабатывать ошибку загрузки данных', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(newsService.getNewsList).mockRejectedValue(new Error('API Error'));
      render(await NewsPage({ searchParams: Promise.resolve({}) }));
      expect(consoleErrorSpy).toHaveBeenCalled();
      expect(screen.getByText('Новостей пока нет')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнеры', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const containers = container.querySelectorAll('.max-w-7xl');
      expect(containers.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive grid для карточек', async () => {
      vi.mocked(newsService.getNewsList).mockResolvedValue(mockNewsData);
      const { container } = render(await NewsPage({ searchParams: Promise.resolve({}) }));
      const grid = container.querySelector('[class*="md:grid-cols-2"]');
      expect(grid).toBeInTheDocument();
    });
  });
});

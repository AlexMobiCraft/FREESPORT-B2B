/**
 * Unit-тесты для страницы списка блога (/blog)
 * Story 21.3 - AC 8
 *
 * Проверяет:
 * - Рендеринг списка статей
 * - Breadcrumb навигацию
 * - Пагинацию
 * - Empty state
 * - SEO metadata
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import BlogPage, { metadata } from '../page';
import { blogService } from '@/services/blogService';
import type { BlogList } from '@/types/api';

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

// Mock Next.js Image component
vi.mock('next/image', () => ({
  // eslint-disable-next-line @next/next/no-img-element
  default: ({ src, alt }: { src: string; alt: string }) => <img src={src} alt={alt} />,
}));

// Mock blogService
vi.mock('@/services/blogService', () => ({
  blogService: {
    getBlogPosts: vi.fn(),
  },
}));

// Mock BlogPostCard component
vi.mock('@/components/home/BlogPostCard', () => ({
  BlogPostCard: ({ title, excerpt, slug }: { title: string; excerpt: string; slug: string }) => (
    <article data-testid="blog-card">
      <a href={`/blog/${slug}`}>
        <h3>{title}</h3>
        <p>{excerpt}</p>
      </a>
    </article>
  ),
}));

const mockBlogData: BlogList = {
  count: 25,
  next: 'http://api.example.com/blog?page=2',
  previous: null,
  results: [
    {
      id: 1,
      title: 'Статья блога 1',
      slug: 'blog-post-1',
      excerpt: 'Краткое описание статьи 1',
      content: 'Полное содержание статьи 1',
      image: 'http://example.com/blog1.jpg',
      published_at: '2025-12-26T10:00:00Z',
      created_at: '2025-12-25T10:00:00Z',
      updated_at: '2025-12-25T10:00:00Z',
      author: 'Автор 1',
      category: 'Тренировки',
      subtitle: 'Подзаголовок 1',
    },
    {
      id: 2,
      title: 'Статья блога 2',
      slug: 'blog-post-2',
      excerpt: 'Краткое описание статьи 2',
      image: null,
      published_at: '2025-12-25T10:00:00Z',
      created_at: '2025-12-24T10:00:00Z',
      updated_at: '2025-12-24T10:00:00Z',
    },
  ],
};

describe('BlogPage (/blog)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(container).toBeInTheDocument();
    });

    it('должна отображать заголовок h1', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Блог');
    });

    it('должна отображать описание секции', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(
        screen.getByText(
          /Полезные статьи о спорте, тренировках и экипировке от экспертов FREESPORT/i
        )
      ).toBeInTheDocument();
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const nav = container.querySelector('nav[aria-label="Breadcrumb"]');
      expect(nav).toBeInTheDocument();
      expect(screen.getByText('Главная')).toBeInTheDocument();
    });

    it('должна иметь ссылку на главную', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
    });
  });

  describe('Список статей блога', () => {
    it('должна рендерить карточки статей', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const cards = screen.getAllByTestId('blog-card');
      expect(cards).toHaveLength(2);
    });

    it('должна передавать правильные props в NewsCard', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('Статья блога 1')).toBeInTheDocument();
      expect(screen.getByText('Краткое описание статьи 1')).toBeInTheDocument();
    });

    it('должна иметь ссылки на детальные страницы статей', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const links = container.querySelectorAll('a[href^="/blog/"]');
      expect(links.length).toBeGreaterThanOrEqual(2);
    });

    it('должна использовать grid layout для карточек', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const grid = container.querySelector('[class*="grid-cols"]');
      expect(grid).toBeInTheDocument();
    });
  });

  describe('Пагинация', () => {
    it('должна отображать кнопки пагинации когда страниц > 1', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('← Назад')).toBeInTheDocument();
      expect(screen.getByText('Вперёд →')).toBeInTheDocument();
    });

    it('должна отображать номера страниц', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('1')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });

    it('должна выделять текущую страницу', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({ page: '1' }) }));
      const currentPageLink = screen.getByText('1').closest('a');
      expect(currentPageLink).toHaveClass('bg-primary');
    });

    it('не должна отображать пагинацию когда 1 страница', async () => {
      const singlePageData = {
        ...mockBlogData,
        count: 5, // Меньше 12
      };
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(singlePageData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.queryByText('← Назад')).not.toBeInTheDocument();
    });

    it('должна запрашивать правильную страницу из searchParams', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      render(await BlogPage({ searchParams: Promise.resolve({ page: '2' }) }));
      expect(blogService.getBlogPosts).toHaveBeenCalledWith({ page: 2 });
    });
  });

  describe('Empty State', () => {
    it('должна отображать empty state когда нет статей', async () => {
      const emptyData: BlogList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(emptyData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.getByText('Статей пока нет')).toBeInTheDocument();
      expect(
        screen.getByText(/Скоро здесь появятся полезные статьи о спорте и тренировках/i)
      ).toBeInTheDocument();
    });

    it('должна отображать иконку в empty state', async () => {
      const emptyData: BlogList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(emptyData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const icon = container.querySelector('[aria-hidden="true"]');
      expect(icon).toBeInTheDocument();
    });

    it('не должна отображать grid когда нет статей', async () => {
      const emptyData: BlogList = {
        count: 0,
        next: null,
        previous: null,
        results: [],
      };
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(emptyData);
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(screen.queryByTestId('blog-card')).not.toBeInTheDocument();
    });
  });

  describe('SEO Metadata', () => {
    it('должна содержать правильный title', () => {
      expect(metadata.title).toBe('Блог | FREESPORT');
    });

    it('должна содержать правильный description', () => {
      expect(metadata.description).toContain('Полезные статьи о спорте');
      expect(metadata.description).toContain('тренировках');
      expect(metadata.description).toContain('экипировке');
    });

    it('должна содержать OpenGraph метатеги', () => {
      expect(metadata.openGraph).toBeDefined();
      expect(metadata.openGraph?.title).toBe('Блог | FREESPORT');
      expect(metadata.openGraph?.description).toContain('Полезные статьи о спорте');
    });
  });

  describe('Обработка ошибок', () => {
    it('должна корректно обрабатывать ошибку загрузки данных', async () => {
      const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
      vi.mocked(blogService.getBlogPosts).mockRejectedValue(new Error('API Error'));
      render(await BlogPage({ searchParams: Promise.resolve({}) }));
      expect(consoleErrorSpy).toHaveBeenCalled();
      expect(screen.getByText('Статей пока нет')).toBeInTheDocument();
      consoleErrorSpy.mockRestore();
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнеры', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const containers = container.querySelectorAll('.max-w-7xl');
      expect(containers.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive grid для карточек', async () => {
      vi.mocked(blogService.getBlogPosts).mockResolvedValue(mockBlogData);
      const { container } = render(await BlogPage({ searchParams: Promise.resolve({}) }));
      const grid = container.querySelector('[class*="md:grid-cols-2"]');
      expect(grid).toBeInTheDocument();
    });
  });
});

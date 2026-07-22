/**
 * Unit-тесты для детальной страницы блога (/blog/[slug])
 * Story 21.3 - AC 8
 *
 * Проверяет:
 * - Рендеринг детальной страницы
 * - Breadcrumb навигацию с заголовком статьи
 * - Отображение контента и дополнительных полей (subtitle, category)
 * - generateMetadata для SEO (meta_title, meta_description)
 * - Обработку notFound()
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import BlogDetailPage, { generateMetadata } from '../page';
import { blogService } from '@/services/blogService';
import type { BlogItem } from '@/types/api';

// Mock Next.js navigation
// Mock Next.js navigation
const { mockNotFound } = vi.hoisted(() => ({
  mockNotFound: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  notFound: mockNotFound,
}));

// Mock Next.js components
vi.mock('next/link', () => ({
  default: ({ children, href }: { children: React.ReactNode; href: string }) => (
    <a href={href}>{children}</a>
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
    getBlogPostBySlug: vi.fn(),
  },
}));

const mockBlogPost: BlogItem = {
  id: 1,
  title: 'Тестовая статья блога',
  slug: 'test-blog-post',
  subtitle: 'Подзаголовок тестовой статьи',
  excerpt: 'Краткое описание тестовой статьи блога',
  content: '<p>Полное содержание статьи с <strong>HTML</strong> форматированием.</p>',
  image: 'http://example.com/blog-image.jpg',
  published_at: '2025-12-26T10:00:00Z',
  created_at: '2025-12-25T10:00:00Z',
  updated_at: '2025-12-25T10:00:00Z',
  author: 'Редакция FREESPORT',
  category: 'Тренировки',
  meta_title: 'SEO заголовок статьи',
  meta_description: 'SEO описание статьи для поисковых систем',
};

describe('BlogDetailPage (/blog/[slug])', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      expect(container).toBeInTheDocument();
    });

    it('должна отображать заголовок статьи', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Тестовая статья блога');
    });

    it('должна использовать семантический тег article', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const article = container.querySelector('article');
      expect(article).toBeInTheDocument();
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb с заголовком статьи', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.getByText('Главная')).toBeInTheDocument();
      expect(screen.getByText('Блог')).toBeInTheDocument();
      expect(screen.getAllByText('Тестовая статья блога').length).toBeGreaterThanOrEqual(1);
    });

    it('должна иметь ссылки на главную и блог', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
      const blogLinks = screen.getAllByText('Блог');
      const blogLink = blogLinks.find(el => el.closest('a'))?.closest('a');
      expect(blogLink).toHaveAttribute('href', '/blog');
    });
  });

  describe('Контент статьи', () => {
    it('должна отображать изображение статьи', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const image = screen.getByAltText('Тестовая статья блога');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', mockBlogPost.image);
    });

    it('должна отображать дату публикации', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const timeElement = screen.getByText(/26 декабря 2025/i);
      expect(timeElement).toBeInTheDocument();
    });

    it('должна отображать автора', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.getByText('Редакция FREESPORT')).toBeInTheDocument();
    });

    it('должна отображать категорию', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.getByText('Тренировки')).toBeInTheDocument();
    });

    it('должна отображать подзаголовок (subtitle)', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.getByText('Подзаголовок тестовой статьи')).toBeInTheDocument();
    });

    it('должна отображать HTML контент', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const contentDiv = container.querySelector('[class*="prose"]');
      expect(contentDiv).toBeInTheDocument();
      expect(contentDiv?.innerHTML).toContain('<strong>HTML</strong>');
    });

    it('должна рендериться без изображения', async () => {
      const postWithoutImage = { ...mockBlogPost, image: null };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutImage);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      expect(container.querySelector('img')).not.toBeInTheDocument();
    });

    it('должна рендериться без автора', async () => {
      const postWithoutAuthor = { ...mockBlogPost, author: undefined };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutAuthor);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.queryByText('Редакция FREESPORT')).not.toBeInTheDocument();
    });

    it('должна рендериться без категории', async () => {
      const postWithoutCategory = { ...mockBlogPost, category: undefined };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutCategory);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.queryByText('Тренировки')).not.toBeInTheDocument();
    });

    it('должна рендериться без подзаголовка', async () => {
      const postWithoutSubtitle = { ...mockBlogPost, subtitle: undefined };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutSubtitle);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.queryByText('Подзаголовок тестовой статьи')).not.toBeInTheDocument();
    });
  });

  describe('Кнопка "Назад к блогу"', () => {
    it('должна отображать кнопку "Назад к блогу"', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      expect(screen.getByText('Назад к блогу')).toBeInTheDocument();
    });

    it('должна иметь ссылку на /blog', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const backLink = screen.getByText('Назад к блогу').closest('a');
      expect(backLink).toHaveAttribute('href', '/blog');
    });

    it('должна иметь иконку стрелки', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const backLink = screen.getByText('Назад к блогу').closest('a');
      expect(backLink?.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('Обработка ошибок', () => {
    it('должна вызвать notFound() если статья не найдена', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockRejectedValue(new Error('Blog post not found'));

      await BlogDetailPage({ params: Promise.resolve({ slug: 'non-existent' }) });

      expect(mockNotFound).toHaveBeenCalled();
    });

    it('должна запросить правильный slug', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) });
      expect(blogService.getBlogPostBySlug).toHaveBeenCalledWith('test-blog-post');
    });
  });

  describe('generateMetadata', () => {
    it('должна использовать meta_title если он есть', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.title).toBe('SEO заголовок статьи | Блог FREESPORT');
    });

    it('должна использовать title если meta_title отсутствует', async () => {
      const postWithoutMetaTitle = { ...mockBlogPost, meta_title: undefined };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutMetaTitle);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.title).toBe('Тестовая статья блога | Блог FREESPORT');
    });

    it('должна использовать meta_description если он есть', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.description).toBe('SEO описание статьи для поисковых систем');
    });

    it('должна использовать excerpt если meta_description отсутствует', async () => {
      const postWithoutMetaDesc = { ...mockBlogPost, meta_description: undefined };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutMetaDesc);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.description).toBe('Краткое описание тестовой статьи блога');
    });

    it('должна возвращать OpenGraph с изображением', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.openGraph?.title).toBe('SEO заголовок статьи');
      expect(metadata.openGraph?.description).toBe('SEO описание статьи для поисковых систем');
      expect(metadata.openGraph?.images).toEqual(['http://example.com/blog-image.jpg']);
    });

    it('должна возвращать OpenGraph без изображения', async () => {
      const postWithoutImage = { ...mockBlogPost, image: null };
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(postWithoutImage);
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.openGraph?.images).toEqual([]);
    });

    it('должна обрабатывать ошибку при генерации метаданных', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockRejectedValue(new Error('Blog post not found'));
      const metadata = await generateMetadata({
        params: Promise.resolve({ slug: 'test-blog-post' }),
      });
      expect(metadata.title).toBe('Статья не найдена | FREESPORT');
      expect(metadata.description).toBe('Запрашиваемая статья не найдена');
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнеры', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const responsiveContainers = container.querySelectorAll('.max-w-4xl, .max-w-7xl');
      expect(responsiveContainers.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive padding', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const responsivePadding = container.querySelectorAll('[class*="sm:px-"]');
      expect(responsivePadding.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive размеры текста', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const headings = container.querySelectorAll('[class*="sm:text-"]');
      expect(headings.length).toBeGreaterThan(0);
    });
  });

  describe('Доступность', () => {
    it('должна иметь time элемент с dateTime атрибутом', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      const { container } = render(
        await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) })
      );
      const timeElement = container.querySelector('time');
      expect(timeElement).toHaveAttribute('dateTime', mockBlogPost.published_at);
    });

    it('должна иметь один h1 заголовок', async () => {
      vi.mocked(blogService.getBlogPostBySlug).mockResolvedValue(mockBlogPost);
      render(await BlogDetailPage({ params: Promise.resolve({ slug: 'test-blog-post' }) }));
      const h1 = screen.getAllByRole('heading', { level: 1 });
      expect(h1.length).toBe(1);
    });
  });
});

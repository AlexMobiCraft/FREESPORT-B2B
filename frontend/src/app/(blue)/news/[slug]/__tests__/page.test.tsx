/**
 * Unit-тесты для детальной страницы новости (/news/[slug])
 * Story 20.2 - AC 11
 *
 * Проверяет:
 * - Рендеринг детальной страницы
 * - Breadcrumb навигацию с заголовком новости
 * - Отображение контента
 * - generateMetadata для SEO
 * - Обработку notFound()
 */

import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import NewsDetailPage, { generateMetadata } from '../page';
import { newsService } from '@/services/newsService';
import type { NewsItem } from '@/types/api';

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

// Mock newsService
vi.mock('@/services/newsService', () => ({
  newsService: {
    getNewsBySlug: vi.fn(),
  },
}));

const mockNewsItem: NewsItem = {
  id: 1,
  title: 'Тестовая новость',
  slug: 'test-news',
  excerpt: 'Краткое описание тестовой новости',
  content: '<p>Полное содержание новости с <strong>HTML</strong> форматированием.</p>',
  image: 'http://example.com/news-image.jpg',
  published_at: '2025-12-26T10:00:00Z',
  created_at: '2025-12-25T10:00:00Z',
  updated_at: '2025-12-25T10:00:00Z',
  author: 'Редакция FREESPORT',
  category: 'Анонсы',
};

describe('NewsDetailPage (/news/[slug])', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('Рендеринг страницы', () => {
    it('должна рендериться без ошибок', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      expect(container).toBeInTheDocument();
    });

    it('должна отображать заголовок новости', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const heading = screen.getByRole('heading', { level: 1 });
      expect(heading).toHaveTextContent('Тестовая новость');
    });

    it('должна использовать семантический тег article', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const article = container.querySelector('article');
      expect(article).toBeInTheDocument();
    });
  });

  describe('Breadcrumb навигация', () => {
    it('должна отображать breadcrumb с заголовком новости', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      expect(screen.getByText('Главная')).toBeInTheDocument();
      expect(screen.getByText('Новости')).toBeInTheDocument();
      expect(screen.getAllByText('Тестовая новость').length).toBeGreaterThanOrEqual(1);
    });

    it('должна иметь ссылки на главную и новости', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const homeLink = screen.getByText('Главная').closest('a');
      expect(homeLink).toHaveAttribute('href', '/');
      const newsLinks = screen.getAllByText('Новости');
      const newsLink = newsLinks.find(el => el.closest('a'))?.closest('a');
      expect(newsLink).toHaveAttribute('href', '/news');
    });
  });

  describe('Контент новости', () => {
    it('должна отображать изображение новости', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const image = screen.getByAltText('Тестовая новость');
      expect(image).toBeInTheDocument();
      expect(image).toHaveAttribute('src', mockNewsItem.image);
    });

    it('должна отображать дату публикации', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const timeElement = screen.getByText(/26 декабря 2025/i);
      expect(timeElement).toBeInTheDocument();
    });

    it('должна отображать автора', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      expect(screen.getByText('Редакция FREESPORT')).toBeInTheDocument();
    });

    it('должна отображать HTML контент', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const contentDiv = container.querySelector('[class*="prose"]');
      expect(contentDiv).toBeInTheDocument();
      expect(contentDiv?.innerHTML).toContain('<strong>HTML</strong>');
    });

    it('должна рендериться без изображения', async () => {
      const newsWithoutImage = { ...mockNewsItem, image: null };
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(newsWithoutImage);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      expect(container.querySelector('img')).not.toBeInTheDocument();
    });

    it('должна рендериться без автора', async () => {
      const newsWithoutAuthor = { ...mockNewsItem, author: undefined };
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(newsWithoutAuthor);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      expect(screen.queryByText('Редакция FREESPORT')).not.toBeInTheDocument();
    });
  });

  describe('Кнопка "Назад к новостям"', () => {
    it('должна отображать кнопку "Назад к новостям"', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      expect(screen.getByText('Назад к новостям')).toBeInTheDocument();
    });

    it('должна иметь ссылку на /news', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const backLink = screen.getByText('Назад к новостям').closest('a');
      expect(backLink).toHaveAttribute('href', '/news');
    });

    it('должна иметь иконку стрелки', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const backLink = screen.getByText('Назад к новостям').closest('a');
      expect(backLink?.querySelector('svg')).toBeInTheDocument();
    });
  });

  describe('Обработка ошибок', () => {
    it('должна вызвать notFound() если новость не найдена', async () => {
      vi.mocked(newsService.getNewsBySlug).mockRejectedValue(new Error('News not found'));

      await NewsDetailPage({ params: Promise.resolve({ slug: 'non-existent' }) });

      expect(mockNotFound).toHaveBeenCalled();
    });

    it('должна запросить правильный slug', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(newsService.getNewsBySlug).toHaveBeenCalledWith('test-news');
    });
  });

  describe('generateMetadata', () => {
    it('должна возвращать правильный title', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(metadata.title).toBe('Тестовая новость | Новости FREESPORT');
    });

    it('должна возвращать excerpt как description', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(metadata.description).toBe('Краткое описание тестовой новости');
    });

    it('должна возвращать OpenGraph с изображением', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(metadata.openGraph?.title).toBe('Тестовая новость');
      expect(metadata.openGraph?.description).toBe('Краткое описание тестовой новости');
      expect(metadata.openGraph?.images).toEqual(['http://example.com/news-image.jpg']);
    });

    it('должна возвращать OpenGraph без изображения', async () => {
      const newsWithoutImage = { ...mockNewsItem, image: null };
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(newsWithoutImage);
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(metadata.openGraph?.images).toEqual([]);
    });

    it('должна обрабатывать ошибку при генерации метаданных', async () => {
      vi.mocked(newsService.getNewsBySlug).mockRejectedValue(new Error('News not found'));
      const metadata = await generateMetadata({ params: Promise.resolve({ slug: 'test-news' }) });
      expect(metadata.title).toBe('Новость не найдена | FREESPORT');
      expect(metadata.description).toBe('Запрашиваемая новость не найдена');
    });
  });

  describe('Адаптивность', () => {
    it('должна иметь responsive контейнеры', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const responsiveContainers = container.querySelectorAll('.max-w-4xl, .max-w-7xl');
      expect(responsiveContainers.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive padding', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const responsivePadding = container.querySelectorAll('[class*="sm:px-"]');
      expect(responsivePadding.length).toBeGreaterThan(0);
    });

    it('должна иметь responsive размеры текста', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const headings = container.querySelectorAll('[class*="sm:text-"]');
      expect(headings.length).toBeGreaterThan(0);
    });
  });

  describe('Доступность', () => {
    it('должна иметь time элемент с dateTime атрибутом', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      const { container } = render(
        await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) })
      );
      const timeElement = container.querySelector('time');
      expect(timeElement).toHaveAttribute('dateTime', mockNewsItem.published_at);
    });

    it('должна иметь один h1 заголовок', async () => {
      vi.mocked(newsService.getNewsBySlug).mockResolvedValue(mockNewsItem);
      render(await NewsDetailPage({ params: Promise.resolve({ slug: 'test-news' }) }));
      const h1 = screen.getAllByRole('heading', { level: 1 });
      expect(h1.length).toBe(1);
    });
  });
});

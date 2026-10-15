/**
 * Unit tests for NewsSection component
 * Story 20.3 - Task 4
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { NewsSection } from '../NewsSection';

// Mock newsService
vi.mock('@/services/newsService', () => ({
  newsService: {
    getNews: vi.fn(),
  },
}));

import { newsService } from '@/services/newsService';

const mockNewsItems = [
  {
    id: 1,
    title: 'Новая коллекция 2025',
    slug: 'new-collection-2025',
    excerpt: 'Представляем новую коллекцию спортивной одежды',
    image: '/images/news/collection.jpg',
    published_at: '2025-01-15T10:00:00Z',
    created_at: '2025-01-15T10:00:00Z',
    updated_at: '2025-01-15T10:00:00Z',
  },
  {
    id: 2,
    title: 'Скидки на зимнюю экипировку',
    slug: 'winter-sale',
    excerpt: 'До конца месяца скидки до 30%',
    image: '/images/news/sale.jpg',
    published_at: '2025-01-14T10:00:00Z',
    created_at: '2025-01-14T10:00:00Z',
    updated_at: '2025-01-14T10:00:00Z',
  },
  {
    id: 3,
    title: 'Открытие нового склада',
    slug: 'new-warehouse',
    excerpt: 'Мы рады сообщить об открытии нового склада',
    image: null,
    published_at: '2025-01-13T10:00:00Z',
    created_at: '2025-01-13T10:00:00Z',
    updated_at: '2025-01-13T10:00:00Z',
  },
];

describe('NewsSection', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('shows skeleton loader while loading', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    let resolvePromise: (value: typeof mockNewsItems) => void;
    mockGetNews.mockImplementationOnce(
      () =>
        new Promise(resolve => {
          resolvePromise = resolve;
        })
    );

    render(<NewsSection />);

    // Should show skeleton loaders
    expect(screen.getAllByLabelText('Загрузка новости')).toHaveLength(3);

    // Resolve the promise
    resolvePromise!(mockNewsItems);

    await waitFor(() => {
      expect(screen.queryByLabelText('Загрузка новости')).not.toBeInTheDocument();
    });
  });

  it('loads and displays 3 news items', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      expect(screen.getByText('Новая коллекция 2025')).toBeInTheDocument();
      expect(screen.getByText('Скидки на зимнюю экипировку')).toBeInTheDocument();
      expect(screen.getByText('Открытие нового склада')).toBeInTheDocument();
    });

    expect(screen.getByText('Новости')).toBeInTheDocument();
  });

  it('displays news excerpts', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      expect(
        screen.getByText('Представляем новую коллекцию спортивной одежды')
      ).toBeInTheDocument();
      expect(screen.getByText('До конца месяца скидки до 30%')).toBeInTheDocument();
    });
  });

  it('shows static news items when API returns error', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockRejectedValueOnce(new Error('Network error'));

    render(<NewsSection />);

    await waitFor(() => {
      // При ошибке API должны отобразиться статические новости
      const newsCards = screen.getAllByRole('article');
      expect(newsCards.length).toBeGreaterThan(0);
    });

    // Проверяем что отображается статическая новость (используем getAllBy)
    await waitFor(() => {
      const staticNewsElements = screen.getAllByText(/поступление|фитнес|шоурум/i);
      expect(staticNewsElements.length).toBeGreaterThan(0);
    });
  });

  it('shows static news items when no news available', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce([]);

    render(<NewsSection />);

    await waitFor(() => {
      // Когда API возвращает пустой массив, показываются статические новости
      const newsCards = screen.getAllByRole('article');
      expect(newsCards.length).toBeGreaterThan(0);
    });

    // Проверяем что отображается статическая новость (используем getAllBy)
    await waitFor(() => {
      const staticNewsElements = screen.getAllByText(/поступление|фитнес|шоурум/i);
      expect(staticNewsElements.length).toBeGreaterThan(0);
    });
  });

  it('handles news item without image using fallback', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      expect(screen.getByText('Открытие нового склада')).toBeInTheDocument();
    });

    // Все 3 новости должны иметь изображения (item 3 с image:null использует fallback)
    const images = screen.getAllByRole('img');
    expect(images).toHaveLength(3);
  });

  it('formats dates in Russian locale', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      // Dates should be formatted in Russian locale
      const timeElements = screen.getAllByRole('time');
      expect(timeElements).toHaveLength(3);
    });
  });

  // Story 20.3 - New tests for "Все новости" link
  it('renders "Все новости" button', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      const link = screen.getByRole('link', { name: /все новости/i });
      expect(link).toBeInTheDocument();
    });
  });

  it('button links to /news', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      // Находим link который содержит кнопку "Все новости"
      const link = screen.getByRole('link', { name: /все новости/i });
      expect(link).toBeInTheDocument();
      expect(link).toHaveAttribute('href', '/news');
    });
  });

  it('passes slug prop to NewsCard components', async () => {
    const mockGetNews = vi.mocked(newsService.getNews);
    mockGetNews.mockResolvedValueOnce(mockNewsItems);

    render(<NewsSection />);

    await waitFor(() => {
      // Проверяем что ссылки на детальные страницы созданы правильно
      const newsLink1 = screen.getByRole('link', {
        name: /читать новость: новая коллекция 2025/i,
      });
      expect(newsLink1).toHaveAttribute('href', '/news/new-collection-2025');

      const newsLink2 = screen.getByRole('link', {
        name: /читать новость: скидки на зимнюю экипировку/i,
      });
      expect(newsLink2).toHaveAttribute('href', '/news/winter-sale');

      const newsLink3 = screen.getByRole('link', {
        name: /читать новость: открытие нового склада/i,
      });
      expect(newsLink3).toHaveAttribute('href', '/news/new-warehouse');
    });
  });
});

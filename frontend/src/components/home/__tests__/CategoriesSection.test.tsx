/**
 * CategoriesSection Component Tests
 * Story: home-categories-refactor — AC 3, 4, 5
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '../../../__mocks__/api/server';
import { CategoriesSection } from '../CategoriesSection';

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('CategoriesSection', () => {
  it('loads and displays root categories in carousel', async () => {
    render(<CategoriesSection />);

    // Loading state
    expect(screen.getByLabelText(/Загрузка категорий/i)).toBeInTheDocument();

    // Success state
    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
      expect(screen.getByText('Бег')).toBeInTheDocument();
      expect(screen.getByText('Теннис')).toBeInTheDocument();
      expect(screen.getByText('Велоспорт')).toBeInTheDocument();
      expect(screen.getByText('Outdoor')).toBeInTheDocument();
      expect(screen.getByText('Баскетбол')).toBeInTheDocument();
    });

    expect(screen.getByText('Популярные категории')).toBeInTheDocument();
  });

  it('renders images with cover fit and placeholder fallback', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId('category-card');
    expect(cards.length).toBe(6);

    // Категории с image отображают их
    const footballImg = screen.getByAltText('Футбол') as HTMLImageElement;
    expect(footballImg.src).toBeTruthy();
    // next/image might use a different URL format but it should eventually point to our media
    expect(decodeURIComponent(footballImg.src)).toContain('/media/categories/football.jpg');
    expect(footballImg.className).toContain('object-cover');

    // Категории без image (Теннис, image: null) получают placeholder
    const tennisImg = screen.getByAltText('Теннис') as HTMLImageElement;
    expect(decodeURIComponent(tennisImg.src)).toContain('category-placeholder.png');
  });

  it('displays product counts', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    expect(screen.getByText('150 товаров')).toBeInTheDocument();
    expect(screen.getByText('230 товаров')).toBeInTheDocument();
    expect(screen.getByText('95 товаров')).toBeInTheDocument();
  });

  it('category links navigate to correct catalog URLs', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId('category-card');
    expect(cards[0]).toHaveAttribute('href', '/catalog?category=football');
    expect(cards[1]).toHaveAttribute('href', '/catalog?category=running');
  });

  it('shows error state on API failure and allows retry', { timeout: 20000 }, async () => {
    server.use(
      http.get('*/categories/', () => {
        return new HttpResponse(JSON.stringify({ detail: 'Internal Server Error' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      })
    );

    const user = userEvent.setup();
    render(<CategoriesSection />);

    await waitFor(
      () => {
        expect(screen.getByText(/Не удалось загрузить категории/i)).toBeInTheDocument();
      },
      { timeout: 15000 }
    );

    const retryButton = screen.getByRole('button', { name: /Повторить попытку/i });
    expect(retryButton).toBeInTheDocument();

    // Reset handler и retry
    server.resetHandlers();
    await user.click(retryButton);

    await waitFor(
      () => {
        expect(screen.getByText('Футбол')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('uses is_homepage=true and ordering=sort_order in API call', async () => {
    const requestSpy = vi.fn();

    server.use(
      http.get('*/categories/', ({ request }) => {
        requestSpy(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      })
    );

    render(<CategoriesSection />);

    await waitFor(() => {
      expect(requestSpy).toHaveBeenCalled();
    });

    const calledUrl = requestSpy.mock.calls[0][0];
    expect(calledUrl).toContain('is_homepage=true');
    expect(calledUrl).toContain('ordering=sort_order');
    expect(calledUrl).toContain('page_size=50');
  });

  it('does not render when no categories are returned', async () => {
    server.use(
      http.get('*/categories/', () => {
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      })
    );

    const { container } = render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.queryByLabelText(/Загрузка категорий/i)).not.toBeInTheDocument();
    });

    expect(container.firstChild).toBeNull();
  });

  it('uses carousel layout instead of grid', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    const carousel = screen.getByRole('list', { name: /Карусель категорий/i });
    expect(carousel).toBeInTheDocument();
    expect(carousel.className).toContain('flex');
    expect(carousel.className).toContain('overflow-x-auto');
    expect(carousel.className).not.toContain('grid');
  });

  it('renders all categories without limit of 6', async () => {
    // 10 категорий
    const manyCategories = Array.from({ length: 10 }, (_, i) => ({
      id: i + 1,
      name: `Категория ${i + 1}`,
      slug: `category-${i + 1}`,
      parent_id: null,
      level: 1,
      icon: null,
      image: null,
      products_count: (i + 1) * 10,
    }));

    server.use(
      http.get('*/categories/', () => {
        return HttpResponse.json({
          count: manyCategories.length,
          next: null,
          previous: null,
          results: manyCategories,
        });
      })
    );

    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Категория 1')).toBeInTheDocument();
    });

    const cards = screen.getAllByTestId('category-card');
    expect(cards.length).toBe(10);
  });
});

/**
 * CategoriesSection Component Tests
 * Story 11.2 - AC 3, 5
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
  it('loads and displays 6 root categories', async () => {
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

    // Проверяем заголовок
    expect(screen.getByText('Популярные категории')).toBeInTheDocument();
  });

  it('displays category icons and product counts', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    // Проверяем отображение количества товаров с правильным склонением
    expect(screen.getByText('150 товаров')).toBeInTheDocument(); // Футбол
    expect(screen.getByText('230 товаров')).toBeInTheDocument(); // Бег
    expect(screen.getByText('95 товаров')).toBeInTheDocument(); // Теннис

    // Проверяем наличие emoji иконок (они рендерятся как text content)
    const categoryCards = screen.getAllByRole('listitem');
    expect(categoryCards.length).toBe(6);
  });

  it('category links navigate to correct catalog URLs', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    // Проверяем что ссылки ведут на правильные URL (listitem содержат href)
    const allLinks = screen.getAllByRole('listitem');
    expect(allLinks[0]).toHaveAttribute('href', '/catalog/football');
    expect(allLinks[1]).toHaveAttribute('href', '/catalog/running');
  });

  it('shows error state on API failure and allows retry', { timeout: 20000 }, async () => {
    // Устанавливаем error handler ДО render
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

    // Проверяем error state (дожидаемся, что загрузка завершится ошибкой)
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

  it('uses correct API endpoint with parent_id__isnull filter', async () => {
    const requestSpy = vi.fn();

    server.use(
      http.get('*/categories/', ({ request }) => {
        requestSpy(request.url);
        return HttpResponse.json([]);
      })
    );

    render(<CategoriesSection />);

    await waitFor(() => {
      expect(requestSpy).toHaveBeenCalled();
    });

    const calledUrl = requestSpy.mock.calls[0][0];
    expect(calledUrl).toContain('parent_id__isnull=true');
    expect(calledUrl).toContain('limit=6');
  });

  it('does not render when no categories are returned', async () => {
    server.use(
      http.get('*/categories/', () => {
        return HttpResponse.json([]);
      })
    );

    const { container } = render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.queryByLabelText(/Загрузка категорий/i)).not.toBeInTheDocument();
    });

    expect(container.firstChild).toBeNull();
  });

  it('uses responsive grid layout', async () => {
    render(<CategoriesSection />);

    await waitFor(() => {
      expect(screen.getByText('Футбол')).toBeInTheDocument();
    });

    // Проверяем что grid container имеет правильные классы
    const gridContainer = screen.getByRole('list');
    expect(gridContainer).toHaveClass('grid');
    expect(gridContainer).toHaveClass('grid-cols-1');
    expect(gridContainer).toHaveClass('sm:grid-cols-2');
    expect(gridContainer).toHaveClass('lg:grid-cols-3');
  });
});

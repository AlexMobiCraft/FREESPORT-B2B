/**
 * NewArrivalsSection Component Tests
 * Story 11.2 - AC 2, 4, 5
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import { NewArrivalsSection } from '../NewArrivalsSection';

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('NewArrivalsSection', () => {
  it('loads and displays 8 new products with "new" badge priority', async () => {
    render(<NewArrivalsSection />);

    // Loading state
    expect(screen.getByLabelText(/Загрузка новинок/i)).toBeInTheDocument();

    // Success state
    await waitFor(() => {
      expect(screen.getByText('Новая модель ракетки Wilson Blade')).toBeInTheDocument();
      expect(screen.getByText('Новые кроссовки Nike Air Zoom')).toBeInTheDocument();
    });

    // Проверяем приоритет бейджей для блока "Новинки"
    // Товар с is_promo=true (приоритет 2) должен показать "Акция" вместо "Новинка"
    expect(screen.getByText('Акция')).toBeInTheDocument();

    // Товар только с is_new=true должен показать "Новинка"
    // Используем getAllByText т.к. несколько товаров могут иметь бейдж "Новинка"
    const novinkaBadges = screen.getAllByText('Новинка');
    expect(novinkaBadges.length).toBeGreaterThan(0);

    // Проверяем заголовок
    expect(screen.getByText('Новинки')).toBeInTheDocument();
  });

  it('shows skeleton loaders during loading', () => {
    render(<NewArrivalsSection />);

    expect(screen.getByLabelText(/Загрузка новинок/i)).toBeInTheDocument();
    expect(screen.getAllByRole('status')).toHaveLength(1);
  });

  it('shows error state on API failure and allows retry', { timeout: 20000 }, async () => {
    // Устанавливаем error handler ДО render
    server.use(
      http.get('*/products/', () => {
        return new HttpResponse(JSON.stringify({ detail: 'Internal Server Error' }), {
          status: 500,
          headers: { 'Content-Type': 'application/json' },
        });
      })
    );

    const user = userEvent.setup();
    render(<NewArrivalsSection />);

    // Проверяем error state (дожидаемся, что загрузка завершится ошибкой)
    await waitFor(
      () => {
        expect(screen.getByText(/Не удалось загрузить новинки/i)).toBeInTheDocument();
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
        expect(screen.getByText('Новая модель ракетки Wilson Blade')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('uses correct API endpoint with is_new filter', async () => {
    const requestSpy = vi.fn();

    server.use(
      http.get('*/products/', ({ request }) => {
        requestSpy(request.url);
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      })
    );

    render(<NewArrivalsSection />);

    await waitFor(() => {
      expect(requestSpy).toHaveBeenCalled();
    });

    const calledUrl = requestSpy.mock.calls[0][0];
    expect(calledUrl).toContain('is_new=true');
    expect(calledUrl).toContain('ordering=-created_at');
    expect(calledUrl).toContain('page_size=8');
  });

  it('does not render when no products are returned', async () => {
    server.use(
      http.get('*/products/', () => {
        return HttpResponse.json({
          count: 0,
          next: null,
          previous: null,
          results: [],
        });
      })
    );

    const { container } = render(<NewArrivalsSection />);

    await waitFor(() => {
      expect(screen.queryByLabelText(/Загрузка новинок/i)).not.toBeInTheDocument();
    });

    expect(container.firstChild).toBeNull();
  });
});

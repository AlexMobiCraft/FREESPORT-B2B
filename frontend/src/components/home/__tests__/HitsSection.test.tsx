/**
 * HitsSection Component Tests
 * Story 11.2 - AC 1, 4, 5
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import { HitsSection } from '../HitsSection';
import { ToastProvider } from '@/components/ui/Toast/ToastProvider';
import { useAuthStore } from '@/stores/authStore';
import type { User } from '@/types/api';

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('HitsSection', () => {
  it('loads and displays 8 hit products with badges', async () => {
    render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    // Loading state - проверяем skeleton loaders
    expect(screen.getAllByRole('status')).toHaveLength(1);
    expect(screen.getByLabelText(/Загрузка лидеров продаж/i)).toBeInTheDocument();

    // Success state - проверяем загрузку товаров
    await waitFor(
      () => {
        expect(screen.getByText('Футбольный мяч Nike Strike')).toBeInTheDocument();
        expect(screen.getByText('Кроссовки Adidas Ultraboost')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );

    // Проверяем приоритет бейджей (Story 11.0)
    // Товар 1: is_sale=true (приоритет 1) - должен показать "20% скидка"
    expect(screen.getByText('20% скидка')).toBeInTheDocument();

    // Товар 2: только is_hit=true (приоритет 4) - должен показать "Лидер продаж"
    // Используем getAllByText т.к. несколько товаров могут иметь бейдж "Лидер продаж"
    const hitBadges = screen.getAllByText('Лидер продаж');
    expect(hitBadges.length).toBeGreaterThan(0);

    // Проверяем что заголовок отображается
    expect(screen.getByText('Лидеры продаж')).toBeInTheDocument();
  });

  it('shows skeleton loaders during loading', () => {
    render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    // Проверяем наличие skeleton loader
    const skeletons = screen.getAllByRole('status');
    expect(skeletons.length).toBeGreaterThan(0);
    expect(screen.getByLabelText(/Загрузка лидеров продаж/i)).toBeInTheDocument();
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
    render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    // Проверяем error state (дожидаемся, что загрузка завершится ошибкой)
    await waitFor(
      () => {
        expect(screen.getByText(/Не удалось загрузить лидеров продаж/i)).toBeInTheDocument();
      },
      { timeout: 15000 }
    );

    // Проверяем кнопку retry
    const retryButton = screen.getByRole('button', { name: /Повторить попытку/i });
    expect(retryButton).toBeInTheDocument();

    // Сбрасываем handler для успешного retry
    server.resetHandlers();

    // Клик на retry
    await user.click(retryButton);

    // Проверяем что данные загрузились после retry
    await waitFor(
      () => {
        expect(screen.getByText('Футбольный мяч Nike Strike')).toBeInTheDocument();
      },
      { timeout: 3000 }
    );
  });

  it('uses correct API endpoint with is_hit filter', async () => {
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

    render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    await waitFor(() => {
      expect(requestSpy).toHaveBeenCalled();
    });

    const calledUrl = requestSpy.mock.calls[0][0];
    expect(calledUrl).toContain('is_hit=true');
    expect(calledUrl).toContain('ordering=-created_at');
    expect(calledUrl).toContain('page_size=8');
  });

  it('does not render when no products are returned (graceful degradation)', async () => {
    // Устанавливаем пустой response
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

    const { container } = render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    // Ждём завершения загрузки
    await waitFor(() => {
      expect(screen.queryByLabelText(/Загрузка лидеров продаж/i)).not.toBeInTheDocument();
    });

    // Проверяем что компонент не отрисовал секцию (RecommendationsRow возвращает null)
    expect(container.firstChild).toBeNull();
  });

  it('displays correct badge variants based on priority', async () => {
    render(
      <ToastProvider>
        <HitsSection />
      </ToastProvider>
    );

    // Ждем загрузки всех товаров, включая велосипед Trek с premium бейджем
    await waitFor(() => {
      expect(screen.getByText('Футбольный мяч Nike Strike')).toBeInTheDocument();
      expect(screen.getByText('Велосипед Trek Marlin 7')).toBeInTheDocument();
    });

    // Проверяем различные варианты бейджей
    // Товары с более высоким приоритетом показывают свой бейдж вместо "Лидер продаж"
    expect(screen.getByText('20% скидка')).toBeInTheDocument(); // sale (приоритет 1) - товар #1
    expect(screen.getByText('Акция')).toBeInTheDocument(); // promo (приоритет 2) - товар #3

    // Товары только с is_hit показывают "Лидер продаж"
    const hitBadges = screen.getAllByText('Лидер продаж');
    expect(hitBadges.length).toBeGreaterThan(0); // Несколько товаров с только is_hit=true
  });

  // РРЦ = розничная цена из 1С; в electric-варианте строку выводит ElectricProductCard
  describe('строка «РРЦ» в electric-варианте', () => {
    const hitWithRrp = {
      id: 77,
      name: 'Мяч BGS322',
      slug: 'bgs322',
      description: '',
      retail_price: 2530,
      rrp: 2530,
      is_in_stock: true,
      category: { id: 1, name: 'Футбол', slug: 'football' },
      images: [],
      is_hit: true,
      is_new: false,
      is_sale: false,
      is_promo: false,
      is_premium: false,
    };
    const loginAs = (role: User['role']) =>
      useAuthStore.setState({
        user: {
          id: 1,
          email: `${role}@example.com`,
          first_name: '',
          last_name: '',
          phone: '',
          role,
          is_verified: true,
        },
      });

    afterEach(() => {
      useAuthStore.setState({ user: null });
    });

    const renderHits = async () => {
      server.use(
        http.get('*/products/', () =>
          HttpResponse.json({ count: 1, next: null, previous: null, results: [hitWithRrp] })
        )
      );
      render(
        <ToastProvider>
          <HitsSection variant="electric" />
        </ToastProvider>
      );
      await waitFor(() => expect(screen.getByText('Мяч BGS322')).toBeInTheDocument());
    };

    it('администратор не видит РРЦ, хотя API её отдал', async () => {
      loginAs('admin');
      await renderHits();

      expect(screen.queryByText(/РРЦ/)).not.toBeInTheDocument();
    });

    it('оптовик 1 видит РРЦ', async () => {
      loginAs('wholesale_level1');
      await renderHits();

      expect(screen.getByText(/РРЦ:\s*2\s530/)).toBeInTheDocument();
    });
  });
});

/**
 * PromoSection Component Tests
 * Карусель «Акция» на главной показывает все акционные товары в наличии
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import { PromoSection } from '../PromoSection';

// Setup MSW
beforeAll(() => server.listen());
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

/** n товаров в наличии с заданным маркетинговым флагом: «Товар 1» … «Товар n» */
const makeFlaggedProducts = (
  n: number,
  flags: Partial<Record<'is_hit' | 'is_new' | 'is_promo', boolean>>
) =>
  Array.from({ length: n }, (_, i) => ({
    id: 1000 + i,
    name: `Товар ${i + 1}`,
    slug: `product-${i + 1}`,
    description: '',
    retail_price: 1000,
    is_in_stock: true,
    category: { id: 1, name: 'Футбол', slug: 'football' },
    images: [],
    is_hit: false,
    is_new: false,
    is_sale: false,
    is_promo: false,
    is_premium: false,
    ...flags,
  }));

/** Общий дефолт MSW для /products/ ветки is_promo не имеет — отдаём акционные товары явно */
const servePromo = (n: number, onRequest?: (url: string) => void) =>
  server.use(
    http.get('*/products/', ({ request }) => {
      onRequest?.(request.url);
      return HttpResponse.json({
        count: n,
        next: null,
        previous: null,
        results: makeFlaggedProducts(n, { is_promo: true }),
      });
    })
  );

describe('PromoSection', () => {
  it('показывает все акционные товары из выдачи (12 → 12 карточек)', async () => {
    servePromo(12);

    render(<PromoSection />);

    expect(screen.getByLabelText(/Загрузка акционных товаров/i)).toBeInTheDocument();

    await waitFor(() => expect(screen.getByText('Товар 12')).toBeInTheDocument());
    expect(screen.getAllByRole('listitem')).toHaveLength(12);
    expect(screen.getByRole('heading', { name: 'Акция' })).toBeInTheDocument();
  });

  it('запрашивает акционные товары в наличии страницами по 100', async () => {
    const requestSpy = vi.fn();
    servePromo(0, requestSpy);

    render(<PromoSection />);

    await waitFor(() => expect(requestSpy).toHaveBeenCalled());

    const params = new URL(requestSpy.mock.calls[0][0]).searchParams;
    expect(params.get('is_promo')).toBe('true');
    expect(params.get('ordering')).toBe('category_tree');
    expect(params.get('in_stock')).toBe('true');
    expect(params.get('page_size')).toBe('100');
    expect(params.get('page')).toBe('1');
  });

  it('не рендерится, когда акционных товаров нет', async () => {
    servePromo(0);

    const { container } = render(<PromoSection />);

    await waitFor(() => {
      expect(screen.queryByLabelText(/Загрузка акционных товаров/i)).not.toBeInTheDocument();
    });
    expect(container.firstChild).toBeNull();
  });

  it('при сбое показывает ошибку и даёт повторить', { timeout: 20000 }, async () => {
    server.use(
      http.get('*/products/', () =>
        HttpResponse.json({ detail: 'Internal Server Error' }, { status: 500 })
      )
    );

    const user = userEvent.setup();
    render(<PromoSection />);

    await waitFor(
      () => expect(screen.getByText(/Не удалось загрузить акционные товары/i)).toBeInTheDocument(),
      { timeout: 15000 }
    );

    servePromo(3);
    await user.click(screen.getByRole('button', { name: /Повторить попытку/i }));

    await waitFor(() => expect(screen.getByText('Товар 3')).toBeInTheDocument());
  });
});

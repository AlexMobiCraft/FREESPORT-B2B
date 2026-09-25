/**
 * MSW Request Handlers
 * ⚠️ IMPORTANT: Use only mock tokens/credentials, never production data
 */
import { http, HttpResponse } from 'msw';

const API_URL = 'http://localhost:8001/api/v1';

export const handlers = [
  http.post(`${API_URL}/auth/login/`, async ({ request }) => {
    const body = (await request.json()) as { email: string; password: string };
    if (body.email === 'test@example.com' && body.password === 'password123') {
      return HttpResponse.json({
        access: 'mock-access-token',
        refresh: 'mock-refresh-token',
        user: {
          id: 1,
          email: 'test@example.com',
          first_name: 'Test',
          last_name: 'User',
          phone: '+79001234567',
          role: 'retail',
        },
      });
    }
    return HttpResponse.json({ detail: 'Invalid credentials' }, { status: 401 });
  }),

  http.post(`${API_URL}/auth/refresh/`, async ({ request }) => {
    const body = (await request.json()) as { refresh: string };
    if (body.refresh === 'mock-refresh-token') {
      return HttpResponse.json({ access: 'new-mock-access-token' });
    }
    return HttpResponse.json({ detail: 'Token is invalid or expired' }, { status: 401 });
  }),

  http.get(`${API_URL}/products/`, () => {
    return HttpResponse.json({
      count: 100,
      next: null,
      previous: null,
      results: [
        {
          id: 1,
          name: 'Test Product',
          slug: 'test-product',
          description: 'Test',
          retail_price: 2500,
          is_in_stock: true,
          category: { id: 1, name: 'Category', slug: 'category' },
          images: [],
        },
      ],
    });
  }),

  http.get(`${API_URL}/cart/`, () => {
    return HttpResponse.json({ id: 1, items: [], total_amount: 0 });
  }),

  http.get(`${API_URL}/orders/`, ({ request }) => {
    const url = new URL(request.url);
    const page = parseInt(url.searchParams.get('page') || '1', 10);
    const limit = parseInt(url.searchParams.get('limit') || '10', 10);

    return HttpResponse.json({
      count: 25,
      next: page * limit < 25 ? `${API_URL}/orders/?page=${page + 1}&limit=${limit}` : null,
      previous: page > 1 ? `${API_URL}/orders/?page=${page - 1}&limit=${limit}` : null,
      results: [
        {
          id: 1,
          order_number: 'ORD-001',
          status: 'delivered',
          items: [],
          total_amount: 2500,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        },
      ],
    });
  }),
];

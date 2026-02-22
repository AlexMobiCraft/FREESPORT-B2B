/**
 * Cart Service Tests
 * Обновлено для работы с variant_id (Story 12.3)
 */
import cartService from '../cartService';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

describe('cartService', () => {
  describe('get', () => {
    test('fetches cart successfully', async () => {
      const result = await cartService.get();

      expect(result.id).toBe(1);
      expect(result.items).toEqual([]);
      expect(result.total_amount).toBe(0);
    });

    test('handles network error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/cart/', () => {
          return HttpResponse.error();
        })
      );

      await expect(cartService.get()).rejects.toThrow();
    });
  });

  describe('add', () => {
    test('adds item to cart successfully with variant_id', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/cart/items/', async ({ request }) => {
          const body = (await request.json()) as { variant_id: number; quantity: number };

          // Валидация: должен быть variant_id, а не product_id
          expect(body).toHaveProperty('variant_id');
          expect(body).not.toHaveProperty('product_id');

          return HttpResponse.json(
            {
              id: Date.now(),
              variant_id: body.variant_id,
              product: {
                id: 1,
                name: 'Test Product',
                slug: 'test-product',
                image: '/test.jpg',
              },
              variant: {
                sku: 'TEST-SKU-001',
                color_name: 'Красный',
                size_value: 'L',
              },
              quantity: body.quantity,
              unit_price: '2500.00',
              total_price: (2500 * body.quantity).toFixed(2),
              added_at: new Date().toISOString(),
            },
            { status: 201 }
          );
        })
      );

      const result = await cartService.add(101, 2);

      expect(result.variant_id).toBe(101);
      expect(result.quantity).toBe(2);
      expect(result.unit_price).toBe('2500.00');
      expect(result.total_price).toBe('5000.00');
    });

    test('handles out of stock error', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/cart/items/', () => {
          return HttpResponse.json({ detail: 'Product variant out of stock' }, { status: 400 });
        })
      );

      await expect(cartService.add(101, 1)).rejects.toThrow();
    });

    test('handles invalid variant_id', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/cart/items/', () => {
          return HttpResponse.json({ detail: 'Variant not found' }, { status: 404 });
        })
      );

      await expect(cartService.add(999, 1)).rejects.toThrow();
    });
  });

  describe('update', () => {
    test('updates item quantity successfully', async () => {
      server.use(
        http.patch('http://localhost:8001/api/v1/cart/items/:id/', async ({ params, request }) => {
          const body = (await request.json()) as { quantity: number };
          return HttpResponse.json({
            id: Number(params.id),
            variant_id: 101,
            product: {
              id: 1,
              name: 'Test Product',
              slug: 'test-product',
              image: '/test.jpg',
            },
            variant: {
              sku: 'TEST-SKU-001',
              color_name: 'Красный',
              size_value: 'L',
            },
            quantity: body.quantity,
            unit_price: '2500.00',
            total_price: (2500 * body.quantity).toFixed(2),
            added_at: new Date().toISOString(),
          });
        })
      );

      const result = await cartService.update(1, 5);

      expect(result.quantity).toBe(5);
      expect(result.total_price).toBe('12500.00');
    });
  });

  describe('remove', () => {
    test('removes item from cart successfully', async () => {
      server.use(
        http.delete('http://localhost:8001/api/v1/cart/items/:id/', () => {
          return new HttpResponse(null, { status: 204 });
        })
      );

      await expect(cartService.remove(1)).resolves.toBeUndefined();
    });
  });

  describe('applyPromo', () => {
    test('applies promo code successfully', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/cart/apply-promo/', () => {
          return HttpResponse.json({
            id: 1,
            items: [],
            total_amount: 0,
            promo_code: 'DISCOUNT10',
            discount_amount: 100,
          });
        })
      );

      const result = await cartService.applyPromo('DISCOUNT10');

      expect(result.promo_code).toBe('DISCOUNT10');
      expect(result.discount_amount).toBe(100);
    });

    test('handles invalid promo code', async () => {
      server.use(
        http.post('http://localhost:8001/api/v1/cart/apply-promo/', () => {
          return HttpResponse.json({ detail: 'Invalid promo code' }, { status: 400 });
        })
      );

      await expect(cartService.applyPromo('INVALID')).rejects.toThrow();
    });
  });
});

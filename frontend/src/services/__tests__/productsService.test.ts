/**
 * Products Service Tests
 * @vitest-environment node
 */
import productsService from '../productsService';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

describe('productsService', () => {
  describe('getAll', () => {
    test('fetches products list successfully', async () => {
      const result = await productsService.getAll();

      expect(result.count).toBe(100);
      expect(result.results).toHaveLength(1);
      expect(result.results[0].name).toBe('Test Product');
    });

    test('fetches products with filters', async () => {
      const result = await productsService.getAll({
        page: 1,
        limit: 20,
        category: 'category',
      });

      expect(result.results).toBeDefined();
    });

    test('handles network error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/', () => {
          return HttpResponse.error();
        })
      );

      await expect(productsService.getAll()).rejects.toThrow();
    });
  });

  describe('getById', () => {
    test('fetches single product successfully', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:id/', ({ params }) => {
          return HttpResponse.json({
            id: Number(params.id),
            name: 'Test Product',
            slug: 'test-product',
            description: 'Test',
            retail_price: 2500,
            is_in_stock: true,
            category: { id: 1, name: 'Category', slug: 'category' },
            images: [],
          });
        })
      );

      const result = await productsService.getById(1);

      expect(result.id).toBe(1);
      expect(result.name).toBe('Test Product');
    });

    test('handles 404 error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/:id/', () => {
          return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
        })
      );

      await expect(productsService.getById(999)).rejects.toThrow();
    });
  });

  describe('search', () => {
    test('searches products successfully', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/products/search/', () => {
          return HttpResponse.json({
            results: [
              {
                id: 1,
                name: 'Search Result',
                slug: 'search-result',
                description: 'Test',
                retail_price: 2500,
                is_in_stock: true,
                category: { id: 1, name: 'Category', slug: 'category' },
                images: [],
              },
            ],
          });
        })
      );

      const result = await productsService.search('test query');

      expect(result.results).toHaveLength(1);
      expect(result.results[0].name).toBe('Search Result');
    });
  });

  describe('filter', () => {
    test('filters products successfully', async () => {
      const result = await productsService.filter({
        category: 'category',
        min_price: 1000,
        max_price: 5000,
      });

      expect(result.results).toBeDefined();
    });
  });

  describe('getProductBySlug', () => {
    test('fetches product detail by slug with custom headers', async () => {
      let capturedHeaders: Headers | undefined;

      server.use(
        http.get('http://localhost:8001/api/v1/products/:slug/', ({ request }) => {
          capturedHeaders = request.headers;
          return HttpResponse.json({
            id: 1,
            name: 'Test Product',
            slug: 'test-product',
            retail_price: 2500,
            stock_quantity: 10,
            is_in_stock: true,
            can_be_ordered: true,
            category: { id: 1, name: 'Category', slug: 'category', breadcrumbs: [] },
            images: [],
            variants: [
              {
                id: 1,
                sku: 'SKU1',
                current_price: '2500.00',
                stock_quantity: 10,
                is_in_stock: true,
                available_quantity: 10,
                rrp: '3000.00',
                msrp: '3500.00',
              },
            ],
          });
        })
      );

      const headers = { Cookie: 'sessionid=123' };
      const result = await productsService.getProductBySlug('test-product', headers);

      expect(result.slug).toBe('test-product');
      // Check if headers were passed
      expect(capturedHeaders?.get('cookie')).toBe('sessionid=123');
      // Check if RRP/MSRP mapped correctly
      expect(result.variants?.[0].rrp).toBe('3000.00');
      expect(result.variants?.[0].msrp).toBe('3500.00');
    });
  });
});

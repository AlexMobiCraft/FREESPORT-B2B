/**
 * Categories Service Tests
 */
import categoriesService from '../categoriesService';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

describe('categoriesService', () => {
  describe('getAll', () => {
    test('fetches categories list successfully', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', () => {
          return HttpResponse.json({
            count: 2,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                name: 'Футбол',
                slug: 'futbol',
                description: 'Футбольная экипировка',
              },
              {
                id: 2,
                name: 'Баскетбол',
                slug: 'basketbol',
                description: 'Баскетбольная экипировка',
              },
            ],
          });
        })
      );

      const result = await categoriesService.getAll();

      expect(result).toHaveLength(2);
      expect(result[0].name).toBe('Футбол');
      expect(result[1].name).toBe('Баскетбол');
    });

    test('handles empty categories list', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', () => {
          return HttpResponse.json({
            count: 0,
            next: null,
            previous: null,
            results: [],
          });
        })
      );

      const result = await categoriesService.getAll();

      expect(result).toHaveLength(0);
    });

    test('handles network error', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', () => {
          return HttpResponse.error();
        })
      );

      await expect(categoriesService.getAll()).rejects.toThrow();
    });
  });

  describe('getTree', () => {
    test('fetches category tree successfully', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/categories-tree/', () => {
          return HttpResponse.json([
            {
              id: 1,
              name: 'Футбол',
              slug: 'futbol',
              children: [
                {
                  id: 3,
                  name: 'Мячи',
                  slug: 'myachi',
                  children: [],
                },
              ],
            },
            {
              id: 2,
              name: 'Баскетбол',
              slug: 'basketbol',
              children: [],
            },
          ]);
        })
      );

      const result = await categoriesService.getTree();

      expect(result).toHaveLength(2);
      expect(result[0].children).toHaveLength(1);
      expect(result[0].children?.[0]?.name).toBe('Мячи');
    });

    test('handles empty tree', async () => {
      server.use(
        http.get('http://localhost:8001/api/v1/categories-tree/', () => {
          return HttpResponse.json([]);
        })
      );

      const result = await categoriesService.getTree();

      expect(result).toHaveLength(0);
    });
  });

  describe('getCategories', () => {
    test('passes ordering parameter to API', async () => {
      let capturedUrl = '';
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [{ id: 1, name: 'Бег', slug: 'beg' }],
          });
        })
      );

      await categoriesService.getCategories({
        ordering: 'sort_order',
      });

      expect(capturedUrl).toContain('ordering=sort_order');
    });

    test('passes limit=0 to fetch all categories', async () => {
      let capturedUrl = '';
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json({
            count: 0,
            next: null,
            previous: null,
            results: [],
          });
        })
      );

      await categoriesService.getCategories({
        limit: 0,
        parent_id__isnull: true,
        ordering: 'sort_order',
      });

      expect(capturedUrl).not.toContain('limit=0');
      expect(capturedUrl).toContain('page_size=1000');
      expect(capturedUrl).toContain('ordering=sort_order');
      expect(capturedUrl).toContain('parent_id__isnull=true');
    });

    test('maps generic limit to page_size', async () => {
      let capturedUrl = '';
      server.use(
        http.get('http://localhost:8001/api/v1/categories/', ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json({ results: [] });
        })
      );

      await categoriesService.getCategories({ limit: 10 });
      expect(capturedUrl).not.toContain('limit=10');
      expect(capturedUrl).toContain('page_size=10');
    });
  });
});

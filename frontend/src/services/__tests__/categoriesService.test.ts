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
});

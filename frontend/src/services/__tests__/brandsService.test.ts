/**
 * Brands Service Tests
 */
import brandsService from '../brandsService';
import { API_URL_PUBLIC } from '../api-client';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

const API_BASE_URL = API_URL_PUBLIC;

const mockBrands = [
  {
    id: 1,
    name: 'Nike',
    slug: 'nike',
    image: '/media/brands/nike.png',
    description: null,
    website: null,
    is_featured: true,
  },
  {
    id: 2,
    name: 'Adidas',
    slug: 'adidas',
    image: '/media/brands/adidas.png',
    description: null,
    website: null,
    is_featured: true,
  },
];

describe('brandsService', () => {
  describe('getFeatured', () => {
    test('fetches featured brands from dedicated endpoint', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json([
            {
              id: 1,
              name: 'Nike',
              slug: 'nike',
              image: '/media/brands/nike.png',
              website: null,
            },
          ]);
        })
      );

      const result = await brandsService.getFeatured();

      expect(result).toHaveLength(1);
      expect(result[0].name).toBe('Nike');
      expect(result[0].is_featured).toBe(true);
    });

    test('normalizes internal media URLs for featured brands', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json([
            {
              id: 1,
              name: 'Nike',
              slug: 'nike',
              image: 'http://backend:8000/media/brands/nike.png',
              website: null,
            },
          ]);
        })
      );

      const result = await brandsService.getFeatured();

      expect(result[0].image).toBe('/media/brands/nike.png');
    });

    test('supports paginated payload from featured endpoint', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json({
            count: 2,
            next: null,
            previous: null,
            results: [
              {
                id: 1,
                name: 'Nike',
                slug: 'nike',
                image: '/media/brands/nike.png',
                website: null,
              },
              {
                id: 2,
                name: 'Adidas',
                slug: 'adidas',
                image: '/media/brands/adidas.png',
                website: null,
              },
            ],
          });
        })
      );

      const result = await brandsService.getFeatured();

      expect(result).toHaveLength(2);
      expect(result[1].name).toBe('Adidas');
    });

    test('fallbacks to legacy /brands/ endpoint on 404 for /brands/featured/', async () => {
      let capturedLegacyUrl = '';

      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json({ detail: 'Not found' }, { status: 404 });
        }),
        http.get(`${API_BASE_URL}/brands/`, ({ request }) => {
          capturedLegacyUrl = request.url;
          return HttpResponse.json({
            count: 2,
            next: null,
            previous: null,
            results: mockBrands,
          });
        })
      );

      const result = await brandsService.getFeatured();

      expect(result).toHaveLength(2);

      const url = new URL(capturedLegacyUrl);
      expect(url.searchParams.get('is_featured')).toBe('true');
      expect(url.searchParams.get('page_size')).toBe('20');
    });

    test('returns empty array when no featured brands', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json([]);
        })
      );

      const result = await brandsService.getFeatured();

      expect(result).toHaveLength(0);
      expect(result).toEqual([]);
    });

    test('handles network error', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.error();
        })
      );

      await expect(brandsService.getFeatured()).rejects.toThrow();
    });

    test('does not fallback to legacy endpoint on non-404 response', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/featured/`, () => {
          return HttpResponse.json({ detail: 'Bad request' }, { status: 400 });
        })
      );

      await expect(brandsService.getFeatured()).rejects.toThrow();
    });
  });

  describe('getAll', () => {
    test('fetches all brands', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/`, () => {
          return HttpResponse.json({
            count: 2,
            next: null,
            previous: null,
            results: mockBrands,
          });
        })
      );

      const result = await brandsService.getAll();

      expect(result).toHaveLength(2);
    });
  });
});

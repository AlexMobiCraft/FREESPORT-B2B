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
    test('fetches featured brands with is_featured=true param', async () => {
      let capturedUrl = '';
      server.use(
        http.get(`${API_BASE_URL}/brands/`, ({ request }) => {
          capturedUrl = request.url;
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
      expect(result[0].name).toBe('Nike');
      expect(result[1].name).toBe('Adidas');

      const url = new URL(capturedUrl);
      expect(url.searchParams.get('is_featured')).toBe('true');
      expect(url.searchParams.get('page_size')).toBe('20');
    });

    test('returns empty array when no featured brands', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/`, () => {
          return HttpResponse.json({
            count: 0,
            next: null,
            previous: null,
            results: [],
          });
        })
      );

      const result = await brandsService.getFeatured();

      expect(result).toHaveLength(0);
      expect(result).toEqual([]);
    });

    test('handles network error', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/`, () => {
          return HttpResponse.error();
        })
      );

      await expect(brandsService.getFeatured()).rejects.toThrow();
    });

    test('returns Brand[] type', async () => {
      server.use(
        http.get(`${API_BASE_URL}/brands/`, () => {
          return HttpResponse.json({
            count: 1,
            next: null,
            previous: null,
            results: [mockBrands[0]],
          });
        })
      );

      const result = await brandsService.getFeatured();

      expect(result[0]).toHaveProperty('id');
      expect(result[0]).toHaveProperty('name');
      expect(result[0]).toHaveProperty('slug');
      expect(result[0]).toHaveProperty('image');
      expect(result[0]).toHaveProperty('is_featured');
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

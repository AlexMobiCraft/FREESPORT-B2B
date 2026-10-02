/**
 * Banners Service Tests
 */
import bannersService from '../bannersService';
import { API_URL_PUBLIC } from '../api-client';
import { server } from '../../__mocks__/api/server';
import { http, HttpResponse } from 'msw';

const API_BASE_URL = API_URL_PUBLIC;

describe('bannersService', () => {
  describe('getActive', () => {
    test('fetches active banners successfully', async () => {
      // Переопределяем хендлер для этого теста
      server.use(
        http.get(`${API_BASE_URL}/banners/`, () => {
          return HttpResponse.json([
            {
              id: 1,
              title: 'Test Banner',
              subtitle: 'Test subtitle',
              image_url: '/media/banners/test.jpg',
              image_alt: 'Test banner',
              cta_text: 'Click here',
              cta_link: '/test',
            },
          ]);
        })
      );

      const result = await bannersService.getActive();

      expect(result).toHaveLength(1);
      expect(result[0].title).toBe('Test Banner');
      expect(result[0].image_url).toBe('/media/banners/test.jpg');
      expect(result[0].image_alt).toBe('Test banner');
      expect(result[0].cta_text).toBe('Click here');
      expect(result[0].cta_link).toBe('/test');
    });

    test('handles empty banners list', async () => {
      server.use(
        http.get(`${API_BASE_URL}/banners/`, () => {
          return HttpResponse.json([]);
        })
      );

      const result = await bannersService.getActive();

      expect(result).toHaveLength(0);
    });

    test('handles network error', async () => {
      server.use(
        http.get(`${API_BASE_URL}/banners/`, () => {
          return HttpResponse.error();
        })
      );

      await expect(bannersService.getActive()).rejects.toThrow();
    });

    test('handles API error response', async () => {
      server.use(
        http.get(`${API_BASE_URL}/banners/`, () => {
          return HttpResponse.json({ detail: 'Internal server error' }, { status: 400 });
        })
      );

      await expect(bannersService.getActive()).rejects.toThrow();
    });

    test('sends type=marketing query param when called with marketing', async () => {
      let capturedUrl = '';
      server.use(
        http.get(`${API_BASE_URL}/banners/`, ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json([
            {
              id: 1,
              type: 'marketing',
              title: 'Marketing Banner',
              subtitle: 'Sub',
              image_url: '/media/banners/m.jpg',
              image_alt: 'Marketing',
              cta_text: 'Click',
              cta_link: '/promo',
            },
          ]);
        })
      );

      const result = await bannersService.getActive('marketing');

      expect(result).toHaveLength(1);
      expect(result[0].type).toBe('marketing');
      const url = new URL(capturedUrl);
      expect(url.searchParams.get('type')).toBe('marketing');
    });

    test('does not send type param when called without arguments', async () => {
      let capturedUrl = '';
      server.use(
        http.get(`${API_BASE_URL}/banners/`, ({ request }) => {
          capturedUrl = request.url;
          return HttpResponse.json([]);
        })
      );

      await bannersService.getActive();

      const url = new URL(capturedUrl);
      expect(url.searchParams.has('type')).toBe(false);
    });

    test('validates banner structure', async () => {
      const result = await bannersService.getActive();

      expect(result[0]).toHaveProperty('id');
      expect(result[0]).toHaveProperty('title');
      expect(result[0]).toHaveProperty('subtitle');
      expect(result[0]).toHaveProperty('image_url');
      expect(result[0]).toHaveProperty('image_alt');
      expect(result[0]).toHaveProperty('cta_text');
      expect(result[0]).toHaveProperty('cta_link');
    });

    test('passes AbortSignal to HTTP request for cancellation support', async () => {
      const controller = new AbortController();
      controller.abort();

      server.use(
        http.get(`${API_BASE_URL}/banners/`, () => {
          return HttpResponse.json([]);
        })
      );

      await expect(bannersService.getActive('marketing', controller.signal)).rejects.toThrow();
    });
  });
});

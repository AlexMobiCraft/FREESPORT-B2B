/**
 * Favorite Service Tests
 * Story 16.3: Управление избранными товарами (AC: 8)
 */

import { describe, it, expect } from 'vitest';
import { http, HttpResponse } from 'msw';
import { server } from '@/__mocks__/api/server';
import {
  getFavorites,
  addFavorite,
  removeFavorite,
  FavoriteValidationError,
} from '../favoriteService';
import type { Favorite } from '@/types/favorite';

// Mock API URL
const API_URL = 'http://localhost:8001/api/v1';

// Mock data
const mockFavorites: Favorite[] = [
  {
    id: 1,
    product: 10,
    product_name: 'Мяч футбольный Nike',
    product_price: '2500.00',
    product_image: '/images/ball.jpg',
    product_slug: 'myach-futbolny-nike',
    product_sku: 'BALL-001',
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    product: 11,
    product_name: 'Бутсы Adidas',
    product_price: '8990.00',
    product_image: '/images/boots.jpg',
    product_slug: 'butsy-adidas',
    product_sku: 'BOOTS-002',
    created_at: '2025-01-02T00:00:00Z',
  },
];

describe('favoriteService', () => {
  describe('getFavorites', () => {
    it('returns list of favorites on success', async () => {
      // ARRANGE
      server.use(
        http.get(`${API_URL}/users/favorites/`, () => {
          return HttpResponse.json(mockFavorites);
        })
      );

      // ACT
      const result = await getFavorites();

      // ASSERT
      expect(result).toEqual(mockFavorites);
      expect(result).toHaveLength(2);
    });

    it('throws error on 401 unauthorized', async () => {
      // ARRANGE
      server.use(
        http.get(`${API_URL}/users/favorites/`, () => {
          return HttpResponse.json(
            { detail: 'Authentication credentials were not provided.' },
            { status: 401 }
          );
        })
      );

      // ACT & ASSERT
      await expect(getFavorites()).rejects.toThrow('Требуется авторизация');
    });
  });

  describe('addFavorite', () => {
    it('adds product to favorites on success', async () => {
      // ARRANGE
      const newFavorite: Favorite = {
        id: 3,
        product: 12,
        product_name: 'Футболка Nike',
        product_price: '3500.00',
        product_image: '/images/tshirt.jpg',
        product_slug: 'futbolka-nike',
        product_sku: 'SHIRT-003',
        created_at: '2025-01-03T00:00:00Z',
      };

      server.use(
        http.post(`${API_URL}/users/favorites/`, () => {
          return HttpResponse.json(newFavorite, { status: 201 });
        })
      );

      // ACT
      const result = await addFavorite(12);

      // ASSERT
      expect(result.id).toBe(3);
      expect(result.product).toBe(12);
    });

    it('throws error when product already in favorites', async () => {
      // ARRANGE
      server.use(
        http.post(`${API_URL}/users/favorites/`, () => {
          return HttpResponse.json(
            { non_field_errors: ['The fields user, product must make a unique set.'] },
            { status: 400 }
          );
        })
      );

      // ACT & ASSERT
      await expect(addFavorite(10)).rejects.toThrow('Товар уже в избранном');
    });

    it('throws FavoriteValidationError on other 400 errors', async () => {
      // ARRANGE
      server.use(
        http.post(`${API_URL}/users/favorites/`, () => {
          return HttpResponse.json(
            { product: ['Товар неактивен или не существует'] },
            { status: 400 }
          );
        })
      );

      // ACT & ASSERT
      await expect(addFavorite(999)).rejects.toThrow(FavoriteValidationError);
    });
  });

  describe('removeFavorite', () => {
    it('removes favorite on success', async () => {
      // ARRANGE
      server.use(
        http.delete(`${API_URL}/users/favorites/1/`, () => {
          return new HttpResponse(null, { status: 204 });
        })
      );

      // ACT & ASSERT
      await expect(removeFavorite(1)).resolves.toBeUndefined();
    });

    it('throws error on 404 not found', async () => {
      // ARRANGE
      server.use(
        http.delete(`${API_URL}/users/favorites/999/`, () => {
          return HttpResponse.json({ detail: 'Not found.' }, { status: 404 });
        })
      );

      // ACT & ASSERT
      await expect(removeFavorite(999)).rejects.toThrow('Избранное не найдено');
    });

    it('throws error on 401 unauthorized', async () => {
      // ARRANGE
      server.use(
        http.delete(`${API_URL}/users/favorites/1/`, () => {
          return HttpResponse.json(
            { detail: 'Authentication credentials were not provided.' },
            { status: 401 }
          );
        })
      );

      // ACT & ASSERT
      await expect(removeFavorite(1)).rejects.toThrow('Требуется авторизация');
    });
  });
});

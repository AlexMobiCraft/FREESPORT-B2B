/**
 * Favorite Service - API сервис для управления избранными товарами
 * Story 16.3: Управление избранными товарами
 *
 * Endpoints:
 * - GET /api/v1/users/favorites/ - получить все избранные товары пользователя
 * - POST /api/v1/users/favorites/ - добавить товар в избранное
 * - DELETE /api/v1/users/favorites/{id}/ - удалить из избранного
 */

import apiClient from './api-client';
import type { Favorite, AddFavoriteData, FavoriteValidationErrors } from '@/types/favorite';
import { AxiosError } from 'axios';

/**
 * Класс ошибки валидации избранного
 */
export class FavoriteValidationError extends Error {
  errors: FavoriteValidationErrors;

  constructor(errors: FavoriteValidationErrors) {
    super('Ошибка валидации избранного');
    this.name = 'FavoriteValidationError';
    this.errors = errors;
  }
}

/**
 * Интерфейс пагинированного ответа от DRF
 */
interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

/**
 * Получить все избранные товары текущего пользователя
 */
export async function getFavorites(): Promise<Favorite[]> {
  try {
    const response = await apiClient.get<PaginatedResponse<Favorite> | Favorite[]>(
      '/users/favorites/'
    );
    // Поддержка как пагинированного, так и простого ответа
    const data = response.data;
    if (Array.isArray(data)) {
      return data;
    }
    // Пагинированный ответ - извлекаем results
    return data.results || [];
  } catch (error) {
    if (error instanceof AxiosError) {
      if (error.response?.status === 401) {
        throw new Error('Требуется авторизация');
      }
    }
    throw new Error('Не удалось загрузить избранное. Попробуйте снова.');
  }
}

/**
 * Добавить товар в избранное
 */
export async function addFavorite(productId: number): Promise<Favorite> {
  try {
    const data: AddFavoriteData = { product: productId };
    const response = await apiClient.post<Favorite>('/users/favorites/', data);
    return response.data;
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      if (error.response.status === 400) {
        const errorData = error.response.data as FavoriteValidationErrors;
        // Проверяем на дубликат
        if (errorData.non_field_errors?.some(e => e.includes('unique'))) {
          throw new Error('Товар уже в избранном');
        }
        throw new FavoriteValidationError(errorData);
      }
      if (error.response.status === 401) {
        throw new Error('Требуется авторизация');
      }
    }
    throw new Error('Не удалось добавить в избранное. Попробуйте снова.');
  }
}

/**
 * Удалить товар из избранного
 */
export async function removeFavorite(id: number): Promise<void> {
  try {
    await apiClient.delete(`/users/favorites/${id}/`);
  } catch (error) {
    if (error instanceof AxiosError && error.response) {
      if (error.response.status === 401) {
        throw new Error('Требуется авторизация');
      }
      if (error.response.status === 404) {
        throw new Error('Избранное не найдено');
      }
    }
    throw new Error('Не удалось удалить из избранного. Попробуйте снова.');
  }
}

/**
 * Объект сервиса для удобного импорта
 */
export const favoriteService = {
  getFavorites,
  addFavorite,
  removeFavorite,
};

export default favoriteService;

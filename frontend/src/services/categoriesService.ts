/**
 * Categories Service - методы для работы с категориями
 */

import apiClient from './api-client';
import type { Category, CategoryTree } from '@/types/api';

interface GetCategoriesParams {
  parent_id?: number | null;
  parent_id__isnull?: boolean;
  level?: number;
  limit?: number;
}

interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

class CategoriesService {
  /**
   * Получить список всех категорий
   */
  async getAll(): Promise<Category[]> {
    const response = await apiClient.get<PaginatedResponse<Category>>('/categories/');
    return response.data.results;
  }

  /**
   * Получить иерархию категорий (дерево)
   */
  async getTree(): Promise<CategoryTree[]> {
    const response = await apiClient.get<CategoryTree[] | PaginatedResponse<CategoryTree>>(
      '/categories-tree/'
    );

    if (Array.isArray(response.data)) {
      return response.data;
    }

    return response.data?.results ?? [];
  }

  /**
   * Получить корневые категории для главной страницы (Story 11.2)
   * GET /categories?parent_id__isnull=true&limit=6
   */
  async getCategories(params?: GetCategoriesParams): Promise<Category[]> {
    const response = await apiClient.get<Category[] | PaginatedResponse<Category>>('/categories/', {
      params: {
        parent_id__isnull: true, // Django filter: только корневые категории
        limit: 6, // AC 3: до 6 категорий
        ...params,
      },
    });
    // Handle both array and paginated response formats (for E2E mocks compatibility)
    if (Array.isArray(response.data)) {
      return response.data;
    }
    return response.data?.results ?? [];
  }
}

const categoriesService = new CategoriesService();
export default categoriesService;

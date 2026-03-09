/**
 * Categories Service - методы для работы с категориями
 */

import apiClient from './api-client';
import type { Category, CategoryTree } from '@/types/api';

interface GetCategoriesParams {
  parent_id?: number | null;
  parent_id__isnull?: boolean;
  parent__slug?: string;
  level?: number;
  limit?: number;
  ordering?: string;
  is_homepage?: boolean;
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
   * Получить категории с гибкими фильтрами
   * По умолчанию возвращает корневые (parent_id__isnull=true, limit=6)
   * Если передан parent_id, фильтр parent_id__isnull не применяется
   */
  async getCategories(params?: GetCategoriesParams): Promise<Category[]> {
    const defaults: Record<string, unknown> = { page_size: 6 };
    // parent_id__isnull только если родитель не задан явно и это не для главной страницы
    if (!params?.parent_id && !params?.parent__slug && !params?.is_homepage) {
      defaults.parent_id__isnull = true;
    }

    const apiParams: Record<string, unknown> = { ...defaults, ...params };

    // Map 'limit' to 'page_size' for Django REST Framework compatibility
    if (params?.limit !== undefined) {
      // 0 means "all" (or reasonably large amount like 1000)
      apiParams.page_size = params.limit === 0 ? 1000 : params.limit;
      delete apiParams.limit;
    }

    const response = await apiClient.get<Category[] | PaginatedResponse<Category>>('/categories/', {
      params: apiParams,
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

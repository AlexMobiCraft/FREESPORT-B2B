/**
 * Blog Service
 * API клиент для получения статей блога
 */

import apiClient from './api-client';
import type { BlogList, BlogItem } from '@/types/api';

interface GetBlogParams {
  page_size?: number;
  page?: number;
}

export const blogService = {
  /**
   * Получить список статей блога с пагинацией
   */
  async getBlogPosts(params?: GetBlogParams): Promise<BlogList> {
    const { data } = await apiClient.get<BlogList>('/blog', {
      params: {
        page_size: 12,
        ...params,
      },
    });
    return data;
  },

  /**
   * Получить детальную статью блога по slug
   * @throws Error если статья не найдена (404)
   */
  async getBlogPostBySlug(slug: string): Promise<BlogItem> {
    try {
      const { data } = await apiClient.get<BlogItem>(`/blog/${slug}/`);
      return data;
    } catch (error: unknown) {
      if (
        typeof error === 'object' &&
        error !== null &&
        'response' in error &&
        typeof error.response === 'object' &&
        error.response !== null &&
        'status' in error.response &&
        error.response.status === 404
      ) {
        throw new Error('Blog post not found');
      }
      throw error;
    }
  },
};

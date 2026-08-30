/**
 * News Service
 * API клиент для получения новостей
 */

import apiClient from './api-client';
import type { NewsList, NewsItem } from '@/types/api';

interface GetNewsParams {
  page_size?: number;
  page?: number;
}

export const newsService = {
  /**
   * Получить список новостей (для главной страницы)
   */
  async getNews(params?: GetNewsParams): Promise<NewsItem[]> {
    const { data } = await apiClient.get<NewsList>('/news', {
      params: {
        page_size: 3,
        ...params,
      },
    });
    return data.results;
  },

  /**
   * Получить список новостей с пагинацией (для страницы /news)
   */
  async getNewsList(params?: GetNewsParams): Promise<NewsList> {
    const { data } = await apiClient.get<NewsList>('/news', {
      params: {
        page_size: 12,
        ...params,
      },
    });
    return data;
  },

  /**
   * Получить детальную новость по slug
   * @throws Error если новость не найдена (404)
   */
  async getNewsBySlug(slug: string): Promise<NewsItem> {
    try {
      const { data } = await apiClient.get<NewsItem>(`/news/${slug}/`);
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
        throw new Error('News not found');
      }
      throw error;
    }
  },
};

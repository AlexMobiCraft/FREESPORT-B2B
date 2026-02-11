/**
 * Banners Service - методы для работы с баннерами
 */

import apiClient from './api-client';
import type { Banner } from '@/types/banners';

class BannersService {
  /**
   * Получить активные баннеры для текущего пользователя
   * API автоматически фильтрует по роли из JWT токена
   * @returns Массив активных баннеров
   */
  async getActive(): Promise<Banner[]> {
    const response = await apiClient.get<Banner[]>('/banners/');
    return response.data;
  }
}

const bannersService = new BannersService();
export default bannersService;

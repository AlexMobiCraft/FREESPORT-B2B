/**
 * Brands Service - методы для работы с брендами
 */

import apiClient from './api-client';
import type { Brand, PaginatedResponse } from '@/types/api';

const DEFAULT_PAGE_SIZE = 100;
const FEATURED_PAGE_SIZE = 20;

class BrandsService {
  /**
   * Нормализует URL изображения бренда.
   * Если URL содержит внутренний адрес Docker (backend:8000) или localhost:8001,
   * заменяет его на относительный путь для обработки через Next.js proxy.
   */
  private normalizeBrand(brand: Brand): Brand {
    if (brand.image) {
      // Заменяем внутренние Docker URL и localhost URL на относительные пути
      const normalizedImage = brand.image
        .replace(/^http:\/\/backend:8000\/media\//, '/media/')
        .replace(/^http:\/\/localhost:8001\/media\//, '/media/');

      return { ...brand, image: normalizedImage };
    }
    return brand;
  }

  async getAll(): Promise<Brand[]> {
    const response = await apiClient.get<PaginatedResponse<Brand>>('/brands/', {
      params: {
        page_size: DEFAULT_PAGE_SIZE,
      },
    });
    return response.data.results.map(this.normalizeBrand);
  }

  async getFeatured(): Promise<Brand[]> {
    const response = await apiClient.get<PaginatedResponse<Brand>>('/brands/', {
      params: {
        is_featured: true,
        page_size: FEATURED_PAGE_SIZE,
      },
    });
    return response.data.results.map(this.normalizeBrand);
  }
}

const brandsService = new BrandsService();
export default brandsService;

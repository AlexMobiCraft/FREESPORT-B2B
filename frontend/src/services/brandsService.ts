/**
 * Brands Service - методы для работы с брендами
 */

import { isAxiosError } from 'axios';
import apiClient from './api-client';
import type { Brand, PaginatedResponse } from '@/types/api';
import type { ProductFilters } from './productsService';
import { normalizeImageUrl } from '@/utils/media';

const DEFAULT_PAGE_SIZE = 100;
const FEATURED_PAGE_SIZE = 20;

type FeaturedBrandPayload = Omit<Brand, 'is_featured'> & { is_featured?: boolean };
type FeaturedBrandsResponse = FeaturedBrandPayload[] | PaginatedResponse<FeaturedBrandPayload>;

class BrandsService {
  /**
   * Нормализует URL изображения бренда для корректной работы в браузере.
   */
  private normalizeBrand<T extends { image?: string | null }>(brand: T): T {
    if (brand.image) {
      return {
        ...brand,
        image: normalizeImageUrl(brand.image),
      };
    }

    return brand;
  }

  private normalizeFeaturedBrands(data: FeaturedBrandsResponse): Brand[] {
    const brands = Array.isArray(data) ? data : data.results;

    return brands.map(brand => {
      const normalized = this.normalizeBrand(brand);

      return {
        ...normalized,
        description: normalized.description ?? null,
        website: normalized.website ?? null,
        is_featured: normalized.is_featured ?? true,
      };
    });
  }

  async getAll(opts?: { has_stock?: boolean }): Promise<Brand[]> {
    const params: Record<string, unknown> = { page_size: DEFAULT_PAGE_SIZE };
    if (opts?.has_stock === true) {
      params.has_stock = true;
    }

    const response = await apiClient.get<PaginatedResponse<Brand>>('/brands/', {
      params,
    });
    return response.data.results.map(this.normalizeBrand);
  }

  async getFeatured(): Promise<Brand[]> {
    try {
      const response = await apiClient.get<FeaturedBrandsResponse>('/brands/featured/');
      return this.normalizeFeaturedBrands(response.data);
    } catch (error) {
      // Backward compatibility: старые backend-сборки могли не иметь /brands/featured/
      if (!isAxiosError(error) || error.response?.status !== 404) {
        throw error;
      }

      const fallbackResponse = await apiClient.get<PaginatedResponse<FeaturedBrandPayload>>(
        '/brands/',
        {
          params: {
            is_featured: true,
            page_size: FEATURED_PAGE_SIZE,
          },
        }
      );

      return this.normalizeFeaturedBrands(fallbackResponse.data);
    }
  }

  async getVisibleBrands(filters: Partial<ProductFilters>): Promise<number[]> {
    const filtersWithoutBrand = { ...filters };
    delete filtersWithoutBrand.brand;
    const response = await apiClient.get<{ brand_ids: number[] }>('/products/visible-brands/', {
      params: filtersWithoutBrand,
    });
    return Array.isArray(response.data.brand_ids) ? response.data.brand_ids : [];
  }
}

const brandsService = new BrandsService();
export default brandsService;

/**
 * Products Service - методы для работы с товарами
 */

import apiClient from './api-client';
import type {
  Product,
  PaginatedResponse,
  ProductDetail,
  ProductImage,
  CategoryBreadcrumb,
} from '@/types/api';
import { normalizeImageUrl } from '@/utils/media';

/**
 * Интерфейс ответа API для детальной информации о товаре
 * Backend возвращает данные в этом формате
 */
interface ApiProductDetailResponse {
  id: number;
  name: string;
  slug: string;
  brand: { id: number; name: string; slug: string } | null;
  category: { id: number; name: string; slug: string } | null;
  sku?: string;
  description: string;
  full_description?: string;
  short_description?: string;
  specifications?: Record<string, string>;
  base_images?: string[];
  is_featured?: boolean;
  is_hit?: boolean;
  is_new?: boolean;
  is_sale?: boolean;
  is_promo?: boolean;
  is_premium?: boolean;
  discount_percent?: number | null;
  created_at?: string;
  // Вычисляемые поля из вариантов
  retail_price: number;
  opt1_price?: number;
  opt2_price?: number;
  opt3_price?: number;
  trainer_price?: number;
  federation_price?: number;
  stock_quantity: number;
  is_in_stock: boolean;
  main_image?: string | null;
  can_be_ordered: boolean;
  // Детальные поля
  images?: Array<{ id?: number; url: string; alt_text: string; is_main: boolean }>;
  related_products?: unknown[];
  category_breadcrumbs?: Array<{ id: number; name: string; slug: string }>;
  seo_title?: string;
  seo_description?: string;
  rating?: number;
  reviews_count?: number;
  variants?: Array<{
    id: number;
    sku: string;
    color_name?: string | null;
    size_value?: string | null;
    current_price: string;
    color_hex?: string | null;
    stock_quantity: number;
    is_in_stock: boolean;
    available_quantity: number;
    rrp?: string;
    msrp?: string;
    main_image?: string | null;
    gallery_images?: string[];
  }>;
}

/**
 * Адаптирует данные из API в формат ProductDetail для компонентов
 * Backend возвращает данные в формате ApiProductDetailResponse
 */
function adaptProductToDetail(apiProduct: ApiProductDetailResponse): ProductDetail {
  // Адаптируем изображения из формата API [{id, url, alt_text, is_main}]
  // в формат компонентов [{id, image, alt_text, is_primary}]
  // Нормализуем URL для корректной работы в Docker
  const images: ProductImage[] = (apiProduct.images || []).map(img => ({
    id: img.id,
    image: normalizeImageUrl(img.url),
    alt_text: img.alt_text || apiProduct.name,
    is_primary: img.is_main,
  }));

  // Если нет изображений, но есть main_image или base_images
  if (images.length === 0) {
    if (apiProduct.main_image) {
      images.push({
        image: normalizeImageUrl(apiProduct.main_image),
        alt_text: apiProduct.name,
        is_primary: true,
      });
    } else if (apiProduct.base_images && apiProduct.base_images.length > 0) {
      apiProduct.base_images.forEach((url, idx) => {
        images.push({
          image: normalizeImageUrl(url),
          alt_text: `${apiProduct.name} - изображение ${idx + 1}`,
          is_primary: idx === 0,
        });
      });
    }
  }

  // Извлекаем breadcrumbs из category_breadcrumbs (сохраняем полную структуру для ссылок)
  const breadcrumbs: CategoryBreadcrumb[] = apiProduct.category_breadcrumbs || [];

  return {
    id: apiProduct.id,
    slug: apiProduct.slug,
    name: apiProduct.name,
    sku: apiProduct.sku || apiProduct.variants?.[0]?.sku || `SKU-${apiProduct.id}`,
    brand: apiProduct.brand?.name || '',
    description: apiProduct.description || '',
    full_description: apiProduct.full_description || apiProduct.description || '',
    price: {
      retail: apiProduct.retail_price || 0,
      wholesale: {
        level1: apiProduct.opt1_price,
        level2: apiProduct.opt2_price,
        level3: apiProduct.opt3_price,
      },
      trainer: apiProduct.trainer_price,
      federation: apiProduct.federation_price,
      currency: 'RUB',
    },
    stock_quantity: apiProduct.stock_quantity || 0,
    images,
    rating: apiProduct.rating,
    reviews_count: apiProduct.reviews_count,
    specifications: apiProduct.specifications,
    category: {
      id: apiProduct.category?.id || 0,
      name: apiProduct.category?.name || '',
      slug: apiProduct.category?.slug || '',
      breadcrumbs: breadcrumbs.length > 0 ? breadcrumbs : [],
    },
    is_in_stock: apiProduct.is_in_stock,
    can_be_ordered: apiProduct.can_be_ordered,
    variants: (apiProduct.variants || []).map(v => ({
      ...v,
      rrp: v.rrp,
      msrp: v.msrp,
    })),
  };
}

export interface ProductFilters {
  page?: number;
  page_size?: number;
  limit?: number;
  category?: string;
  category_id?: number;
  brand?: string;
  min_price?: number;
  max_price?: number;
  ordering?: string;
  in_stock?: boolean;
  is_hit?: boolean;
  is_new?: boolean;
  is_sale?: boolean;
  is_promo?: boolean;
  is_premium?: boolean;
  search?: string;
}

class ProductsService {
  /**
   * Получить список товаров с пагинацией и фильтрами
   */
  async getAll(filters?: ProductFilters): Promise<PaginatedResponse<Product>> {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
      params: filters,
    });
    return response.data;
  }

  /**
   * Получить товар по ID
   */
  async getById(id: number): Promise<Product> {
    const response = await apiClient.get<Product>(`/products/${id}/`);
    return response.data;
  }

  /**
   * Поиск товаров
   */
  async search(query: string): Promise<{ results: Product[] }> {
    const response = await apiClient.get<{ results: Product[] }>('/products/search/', {
      params: { q: query },
    });
    return response.data;
  }

  /**
   * Фильтрация товаров
   */
  async filter(filters: ProductFilters): Promise<PaginatedResponse<Product>> {
    return this.getAll(filters);
  }

  /**
   * Получить хиты продаж (Story 11.2)
   * GET /products?is_hit=true&ordering=-created_at&page_size=8
   */
  async getHits(params?: Partial<ProductFilters>): Promise<Product[]> {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
      params: {
        is_hit: true,
        ordering: '-created_at',
        page_size: 8,
        in_stock: true,
        ...params,
      },
    });
    return response.data.results;
  }

  /**
   * Получить новинки (Story 11.2)
   * GET /products?is_new=true&ordering=-created_at&page_size=8
   */
  async getNew(params?: Partial<ProductFilters>): Promise<Product[]> {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
      params: {
        is_new: true,
        ordering: '-created_at',
        page_size: 8,
        in_stock: true,
        ...params,
      },
    });
    return response.data.results;
  }

  /**
   * Получить товары на распродаже
   * GET /products?is_sale=true&ordering=-created_at&page_size=8
   */
  async getSale(params?: Partial<ProductFilters>): Promise<Product[]> {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
      params: {
        is_sale: true,
        ordering: '-created_at',
        page_size: 8,
        in_stock: true,
        ...params,
      },
    });
    return response.data.results;
  }

  /**
   * Получить акционные товары
   * GET /products?is_promo=true&ordering=-created_at&page_size=8
   */
  async getPromo(params?: Partial<ProductFilters>): Promise<Product[]> {
    const response = await apiClient.get<PaginatedResponse<Product>>('/products/', {
      params: {
        is_promo: true,
        ordering: '-created_at',
        page_size: 8,
        in_stock: true,
        ...params,
      },
    });
    return response.data.results;
  }

  /**
   * Получить детальную информацию о товаре по slug (Story 12.1)
   * GET /products/{slug}/
   * Адаптирует данные из формата API в формат ProductDetail
   */
  async getProductBySlug(slug: string, headers?: Record<string, string>): Promise<ProductDetail> {
    const response = await apiClient.get<ApiProductDetailResponse>(`/products/${slug}/`, {
      headers,
    });
    return adaptProductToDetail(response.data);
  }
}

const productsService = new ProductsService();
export default productsService;

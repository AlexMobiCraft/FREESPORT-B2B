/**
 * Типы для работы с избранными товарами
 * Story 16.3: Управление избранными товарами
 */

/**
 * Интерфейс избранного товара (API Response)
 */
export interface Favorite {
  id: number;
  product: number;
  product_name: string;
  product_price: string; // Decimal как string
  product_image: string | null;
  product_slug: string;
  product_sku: string;
  created_at: string;
}

/**
 * Данные для добавления товара в избранное
 */
export interface AddFavoriteData {
  product: number;
}

/**
 * Расширенный тип Favorite с информацией о доступности варианта
 */
export interface FavoriteWithAvailability extends Favorite {
  isAvailable: boolean;
  variantId?: number;
  stockQuantity?: number;
}

/**
 * Ошибки валидации избранного от API
 */
export interface FavoriteValidationErrors {
  product?: string[];
  non_field_errors?: string[];
}

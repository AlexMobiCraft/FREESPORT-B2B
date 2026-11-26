/**
 * TypeScript типы для корзины покупок
 * Соответствуют API schema из backend
 */

/**
 * Элемент корзины
 */
export interface CartItem {
  id: number;
  variant_id: number;
  product: {
    id: number;
    name: string;
    slug: string;
    image: string | null;
  };
  variant: {
    sku: string;
    color_name: string | null;
    size_value: string | null;
  };
  quantity: number;
  unit_price: string; // Decimal as string
  total_price: string; // Decimal as string
  added_at: string; // ISO datetime
}

/**
 * Состояние корзины
 */
export interface CartState {
  items: CartItem[];
  totalItems: number;
  totalPrice: number;
  isLoading: boolean;
  error: string | null;
}

/**
 * Запрос на добавление в корзину
 */
export interface AddToCartRequest {
  variant_id: number;
  quantity: number;
}

/**
 * Ответ API при добавлении в корзину
 */
export type AddToCartResponse = CartItem;

/**
 * Запрос на обновление количества
 */
export interface UpdateCartItemRequest {
  quantity: number;
}

/**
 * Полная корзина с метаданными
 */
export interface Cart {
  id: number;
  items: CartItem[];
  total_items: number;
  total_amount: string; // Decimal as string
  promo_code?: string;
  discount_amount?: number;
  created_at: string;
  updated_at: string;
}

/**
 * Ответ API при применении промокода
 * @see Story 26.4: Promo Code Integration
 */
export interface PromoResponse {
  success: boolean;
  code?: string;
  discount_type?: 'percent' | 'fixed';
  discount_value?: number;
  error?: string;
}

/**
 * Запрос на применение промокода
 */
export interface ApplyPromoRequest {
  code: string;
  cartTotal: number;
}

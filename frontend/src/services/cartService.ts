/**
 * Cart Service - методы для работы с корзиной
 * Обновлено для работы с ProductVariant (variant_id вместо product_id)
 */

import apiClient from './api-client';
import type { Cart, CartItem } from '@/types/cart';

class CartService {
  /**
   * Получить текущую корзину
   */
  async get(): Promise<Cart> {
    const response = await apiClient.get<Cart>('/cart/');
    return response.data;
  }

  /**
   * Добавить вариант товара в корзину
   * @param variantId - ID варианта товара (ProductVariant)
   * @param quantity - Количество
   */
  async add(variantId: number, quantity: number): Promise<CartItem> {
    const response = await apiClient.post<CartItem>('/cart/items/', {
      variant_id: variantId,
      quantity,
    });
    return response.data;
  }

  /**
   * Обновить количество товара в корзине
   */
  async update(itemId: number, quantity: number): Promise<CartItem> {
    const response = await apiClient.patch<CartItem>(`/cart/items/${itemId}/`, {
      quantity,
    });
    return response.data;
  }

  /**
   * Удалить товар из корзины
   */
  async remove(itemId: number): Promise<void> {
    await apiClient.delete(`/cart/items/${itemId}/`);
  }

  /**
   * Очистить корзину
   */
  async clear(): Promise<void> {
    await apiClient.delete('/cart/clear/');
  }

  /**
   * Применить промокод
   */
  async applyPromo(code: string): Promise<Cart> {
    const response = await apiClient.post<Cart>('/cart/apply-promo/', { code });
    return response.data;
  }
}

const cartService = new CartService();
export default cartService;

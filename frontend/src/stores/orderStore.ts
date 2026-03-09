/**
 * Order Store - управление состоянием создания заказа
 * Story 15.2: Интеграция с Orders API
 *
 * Features:
 * - Создание заказа через ordersService
 * - Интеграция с cartStore (очистка после успешного заказа)
 * - Обработка состояний загрузки и ошибок
 */

import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import ordersService from '@/services/ordersService';
import { useCartStore } from '@/stores/cartStore';
import type { CheckoutFormData } from '@/schemas/checkoutSchema';
import type { Order } from '@/types/order';

/**
 * Состояние orderStore
 */
interface OrderState {
  // State
  currentOrder: Order | null;
  isSubmitting: boolean;
  error: string | null;

  // Actions
  createOrder: (data: CheckoutFormData) => Promise<void>;
  clearOrder: () => void;
  setError: (error: string | null) => void;
}

export const useOrderStore = create<OrderState>()(
  devtools(
    set => ({
      // Initial state
      currentOrder: null,
      isSubmitting: false,
      error: null,

      /**
       * Создание заказа
       *
       * 1. Получает товары из cartStore
       * 2. Вызывает ordersService.createOrder()
       * 3. При успехе: сохраняет заказ, очищает корзину
       * 4. При ошибке: сохраняет ошибку
       */
      createOrder: async (data: CheckoutFormData) => {
        set({ isSubmitting: true, error: null });

        try {
          // Получаем товары из корзины
          const cartItems = useCartStore.getState().items;

          // Проверка на пустую корзину
          if (!cartItems || cartItems.length === 0) {
            throw new Error('Корзина пуста, невозможно оформить заказ');
          }

          // Создаём заказ через API
          const order = await ordersService.createOrder(data, cartItems);

          // Сохраняем созданный заказ
          set({ currentOrder: order, error: null });

          // Очищаем корзину после успешного создания заказа
          await useCartStore.getState().clearCart();
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Ошибка создания заказа';
          set({ error: errorMessage });
          throw error; // Re-throw для обработки в компоненте
        } finally {
          set({ isSubmitting: false });
        }
      },

      /**
       * Очистка текущего заказа и ошибки
       * Используется при возврате на checkout или новом заказе
       */
      clearOrder: () => {
        set({ currentOrder: null, error: null });
      },

      /**
       * Установка ошибки вручную
       * Используется для edge cases (пустая корзина и т.д.)
       */
      setError: (error: string | null) => {
        set({ error });
      },
    }),
    { name: 'OrderStore' }
  )
);

/**
 * Cart Store - управление корзиной покупок
 *
 * Features:
 * - Optimistic Updates для мгновенного отклика UI
 * - Rollback при ошибках API
 * - Работа с ProductVariant (variant_id)
 * - Автоматический расчет total
 */

import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';
import cartService from '@/services/cartService';
import type { CartItem, CartState as CartStateType } from '@/types/cart';

interface CartStore extends CartStateType {
  // Promo state (Story 26.4)
  promoCode: string | null;
  discountType: 'percent' | 'fixed' | null;
  discountValue: number;

  // Actions
  addItem: (variantId: number, quantity: number) => Promise<{ success: boolean; error?: string }>;
  removeItem: (itemId: number) => Promise<{ success: boolean; error?: string }>;
  updateQuantity: (
    itemId: number,
    quantity: number
  ) => Promise<{ success: boolean; error?: string }>;
  clearCart: () => Promise<void>;
  fetchCart: () => Promise<void>;

  // Promo actions (Story 26.4)
  applyPromo: (code: string, discountType: 'percent' | 'fixed', discountValue: number) => void;
  clearPromo: () => void;
  getPromoDiscount: () => number;

  // Getters
  getTotalItems: () => number;
  setItems: (items: CartItem[]) => void;
  setError: (error: string | null) => void;
  setLoading: (loading: boolean) => void;
}

/**
 * Расчет totalItems и totalPrice
 */
const calculateTotals = (items: CartItem[]) => {
  const totalItems = items.reduce((sum, item) => sum + item.quantity, 0);
  const totalPrice = items.reduce((sum, item) => sum + parseFloat(item.total_price), 0);
  return { totalItems, totalPrice };
};

export const useCartStore = create<CartStore>()(
  devtools(
    persist(
      (set, get) => ({
        items: [],
        totalItems: 0,
        totalPrice: 0,
        isLoading: false,
        error: null,

        // Promo state (Story 26.4)
        promoCode: null,
        discountType: null,
        discountValue: 0,

        // Setters
        setItems: (items: CartItem[]) => {
          const { totalItems, totalPrice } = calculateTotals(items);
          set({ items, totalItems, totalPrice });
        },

        setError: (error: string | null) => set({ error }),

        setLoading: (isLoading: boolean) => set({ isLoading }),

        // Getters
        getTotalItems: () => get().totalItems,

        /**
         * Динамический расчёт скидки по промокоду
         * Пересчитывается при каждом изменении корзины
         */
        getPromoDiscount: () => {
          const { totalPrice, discountType, discountValue } = get();
          if (!discountType) return 0;
          const discount =
            discountType === 'percent' ? totalPrice * (discountValue / 100) : discountValue;
          // Скидка не может превышать сумму корзины
          return Math.min(discount, totalPrice);
        },

        /**
         * Применить промокод
         */
        applyPromo: (code: string, discountType: 'percent' | 'fixed', discountValue: number) => {
          set({ promoCode: code, discountType, discountValue });
        },

        /**
         * Очистить промокод
         */
        clearPromo: () => {
          set({ promoCode: null, discountType: null, discountValue: 0 });
        },

        // Загрузить корзину с backend
        fetchCart: async () => {
          set({ isLoading: true, error: null });
          try {
            const cart = await cartService.get();
            get().setItems(cart.items);
          } catch (error) {
            const errorMsg = error instanceof Error ? error.message : 'Ошибка загрузки корзины';
            set({ error: errorMsg });
          } finally {
            set({ isLoading: false });
          }
        },

        // Добавить товар в корзину (Optimistic Update)
        addItem: async (variantId: number, quantity: number) => {
          // Сохраняем предыдущее состояние для rollback
          const previousState = { ...get() };

          set({ isLoading: true, error: null });

          try {
            // Optimistic update - мгновенно обновляем UI
            const tempItem: CartItem = {
              id: Date.now(), // Временный ID
              variant_id: variantId,
              product: {
                id: 0,
                name: 'Загрузка...',
                slug: '',
                image: null,
              },
              variant: {
                sku: '',
                color_name: null,
                size_value: null,
              },
              quantity,
              unit_price: '0',
              total_price: '0',
              added_at: new Date().toISOString(),
            };

            set(state => {
              const { totalItems, totalPrice } = calculateTotals([...state.items, tempItem]);
              return {
                items: [...state.items, tempItem],
                totalItems,
                totalPrice,
              };
            });

            // Отправляем запрос на backend
            const realItem = await cartService.add(variantId, quantity);

            // Заменяем временный item на реальный
            // ВАЖНО: backend объединяет товары с одинаковым variant_id,
            // поэтому realItem может иметь id отличный от tempItem.id
            set(state => {
              // 1. Удаляем временный item
              const items = state.items.filter(item => item.id !== tempItem.id);

              // 2. Проверяем, есть ли уже item с таким id (backend вернул существующий)
              const existingIndex = items.findIndex(item => item.id === realItem.id);
              if (existingIndex >= 0) {
                // Заменяем существующий item на обновлённый
                items[existingIndex] = realItem;
              } else {
                // Добавляем новый item
                items.push(realItem);
              }

              const { totalItems, totalPrice } = calculateTotals(items);
              return { items, totalItems, totalPrice, isLoading: false };
            });

            return { success: true };
          } catch (error) {
            // ROLLBACK: восстанавливаем предыдущее состояние
            set(previousState);

            const errorMsg = error instanceof Error ? error.message : 'Ошибка добавления в корзину';
            set({ error: errorMsg, isLoading: false });

            return { success: false, error: errorMsg };
          }
        },

        // Удалить товар из корзины (Optimistic Update)
        removeItem: async (itemId: number) => {
          const previousState = { ...get() };

          set({ isLoading: true, error: null });

          try {
            // Optimistic update
            const items = get().items.filter(item => item.id !== itemId);
            get().setItems(items);

            // Отправляем запрос на backend
            await cartService.remove(itemId);

            set({ isLoading: false });
            return { success: true };
          } catch (error) {
            // ROLLBACK
            set(previousState);

            const errorMsg = error instanceof Error ? error.message : 'Ошибка удаления из корзины';
            set({ error: errorMsg, isLoading: false });

            return { success: false, error: errorMsg };
          }
        },

        // Обновить количество (Optimistic Update)
        updateQuantity: async (itemId: number, quantity: number) => {
          const previousState = { ...get() };

          set({ isLoading: true, error: null });

          try {
            // Optimistic update
            const items = get().items.map(item =>
              item.id === itemId ? { ...item, quantity } : item
            );
            get().setItems(items);

            // Отправляем запрос на backend
            const updatedItem = await cartService.update(itemId, quantity);

            // Обновляем реальными данными
            const finalItems = get().items.map(item => (item.id === itemId ? updatedItem : item));
            get().setItems(finalItems);

            set({ isLoading: false });
            return { success: true };
          } catch (error) {
            // ROLLBACK
            set(previousState);

            const errorMsg =
              error instanceof Error ? error.message : 'Ошибка обновления количества';
            set({ error: errorMsg, isLoading: false });

            return { success: false, error: errorMsg };
          }
        },

        // Очистить корзину
        clearCart: async () => {
          const previousState = { ...get() };

          set({ isLoading: true, error: null });

          try {
            // Optimistic update
            set({ items: [], totalItems: 0, totalPrice: 0 });

            // Отправляем запрос на backend
            await cartService.clear();

            set({ isLoading: false });
          } catch (error) {
            // ROLLBACK
            set(previousState);

            const errorMsg = error instanceof Error ? error.message : 'Ошибка очистки корзины';
            set({ error: errorMsg, isLoading: false });
          }
        },
      }),
      {
        name: 'cart-storage-v3', // v3: убрали items из localStorage, загружаем только с сервера
        partialize: state => ({
          // Сохраняем только promo state (Story 26.4)
          // ВАЖНО: items НЕ сохраняем в localStorage, т.к. они загружаются с сервера
          // Это предотвращает дублирование и рассинхронизацию с backend
          promoCode: state.promoCode,
          discountType: state.discountType,
          discountValue: state.discountValue,
        }),
      }
    ),
    { name: 'CartStore' }
  )
);

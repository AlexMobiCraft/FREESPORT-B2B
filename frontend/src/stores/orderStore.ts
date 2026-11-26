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
import { devtoolsInDev } from './devtoolsInDev';
import ordersService, { OrderApiError, type OrderPriceChanges } from '@/services/ordersService';
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
  /** Изменившиеся цены из ответа 409 `prices_changed`; сбрасывается при следующей отправке */
  priceChanges: OrderPriceChanges | null;
  /**
   * После 409 корзину не удалось перезагрузить: сводка показывает прежние цены.
   * Пока флаг стоит, сумма не выводится как актуальная и оформление запрещено.
   */
  cartRefreshFailed: boolean;
  /**
   * Идёт перезагрузка корзины после 409 или по кнопке «Обновить корзину».
   * Сводка в это время показывает прежние цены, поэтому сумма не выводится.
   */
  cartRefreshing: boolean;

  // Actions
  createOrder: (data: CheckoutFormData) => Promise<void>;
  /** Повторная перезагрузка корзины после неудачной; снимает `cartRefreshFailed` при успехе */
  refreshCart: () => Promise<void>;
  clearOrder: () => void;
  setError: (error: string | null) => void;
}

/** Перезагружает корзину; `fetchCart` ошибки глотает, исход — по `error` стора корзины. */
async function reloadCart(): Promise<boolean> {
  await useCartStore.getState().fetchCart();
  return useCartStore.getState().error === null;
}

type OrderStoreSet = (partial: Partial<OrderState>) => void;

/**
 * Перезагрузка корзины с пометкой `cartRefreshing` на время запроса:
 * пока она идёт, сводка не выдаёт прежнюю сумму за актуальную.
 */
async function refreshCartPrices(set: OrderStoreSet): Promise<void> {
  set({ cartRefreshing: true });
  try {
    set({ cartRefreshFailed: !(await reloadCart()) });
  } finally {
    set({ cartRefreshing: false });
  }
}

const STALE_CART_MESSAGE =
  'Не удалось загрузить актуальные цены корзины. Обновите корзину, чтобы продолжить оформление';

export const useOrderStore = create<OrderState>()(
  devtoolsInDev(
    (set, get) => ({
      // Initial state
      currentOrder: null,
      isSubmitting: false,
      error: null,
      priceChanges: null,
      cartRefreshFailed: false,
      cartRefreshing: false,

      /**
       * Создание заказа
       *
       * 1. Получает товары из cartStore
       * 2. Вызывает ordersService.createOrder()
       * 3. При успехе: сохраняет заказ, очищает корзину
       * 4. При ошибке: сохраняет ошибку
       */
      createOrder: async (data: CheckoutFormData) => {
        // Сводка с прежними ценами не основание для заказа: кнопка в этом
        // состоянии заблокирована, а здесь — защита от отправки в обход неё.
        if (get().cartRefreshFailed) {
          set({ error: STALE_CART_MESSAGE });
          throw new Error(STALE_CART_MESSAGE);
        }

        set({ isSubmitting: true, error: null, priceChanges: null });

        try {
          // Получаем товары из корзины
          const cartState = useCartStore.getState();
          const cartItems = cartState.items;

          // Проверка на пустую корзину
          if (!cartItems || cartItems.length === 0) {
            throw new Error('Корзина пуста, невозможно оформить заказ');
          }

          // promo_code — stub (Story 34-2 [Review][Patch]): передаём для будущей серверной promo-системы.
          // discount_amount НЕ передаётся клиентом: сервер всегда выставляет 0 (promo-система в разработке).
          const promoCode = cartState.promoCode;

          // Создаём заказ через API
          const order = await ordersService.createOrder(data, cartItems, undefined, promoCode);

          // Сохраняем созданный заказ
          set({ currentOrder: order, error: null });

          // Очищаем корзину и promo-state после успешного создания заказа.
          // Backend уже очистил cart в той же транзакции — вызываем только
          // локальный clear без повторного API-запроса, чтобы избежать
          // rollback-эффекта при сбое избыточного /cart/clear/.
          // try-finally гарантирует, что clearPromo() выполнится даже если
          // clearCartLocal() бросит исключение (защита от stale promoCode в localStorage).
          try {
            useCartStore.getState().clearCartLocal();
          } finally {
            useCartStore.getState().clearPromo();
          }
        } catch (error: unknown) {
          const errorMessage = error instanceof Error ? error.message : 'Ошибка создания заказа';
          if (error instanceof OrderApiError && error.code === 'prices_changed') {
            // Заказа нет, сервер уже обновил снимки корзины. Сообщение и строки
            // «было → стало» из тела 409 показываются сразу: перезагрузка корзины
            // при 5xx идёт с повторами (до ~7 с) и может упасть совсем.
            set({ error: errorMessage, priceChanges: error.priceChanges ?? null });
            await refreshCartPrices(set);
          } else {
            set({ error: errorMessage });
          }
          throw error; // Re-throw для обработки в компоненте
        } finally {
          set({ isSubmitting: false });
        }
      },

      refreshCart: async () => {
        await refreshCartPrices(set);
      },

      /**
       * Очистка текущего заказа и ошибки
       * Используется при возврате на checkout или новом заказе
       */
      clearOrder: () => {
        set({
          currentOrder: null,
          error: null,
          priceChanges: null,
          cartRefreshFailed: false,
          cartRefreshing: false,
        });
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

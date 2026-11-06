'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useAuth } from '@/providers/AuthProvider';
import { useAuthStore } from '@/stores/authStore';
import { useCartStore } from '@/stores/cartStore';
import { useOrderStore } from '@/stores/orderStore';
import { CheckoutForm } from '@/components/checkout/CheckoutForm';
import { CheckoutStateView } from '@/components/checkout/CheckoutStateView';
import { resolveCheckoutView, type CartLoadStatus } from '@/utils/checkout/checkoutView';

/**
 * Клиентский компонент страницы checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 * Story 41.10: Гейт состояний для анонима, загрузки, ошибки, пустой корзины
 * и редиректа после оформления заказа (FR-41-25) — форма монтируется только
 * когда сессия восстановлена, пользователь авторизован, корзина загружена
 * и в ней есть товары. Состояния: loading, anonymous, error, redirecting,
 * empty, form — см. `resolveCheckoutView`.
 *
 * Отвечает за:
 * - Получение данных пользователя из authStore
 * - Рендеринг формы CheckoutForm с автозаполнением
 * - Обработку успешного создания заказа (переадресация в Story 15.2)
 */
export function CheckoutPageClient() {
  const { isInitialized } = useAuth();
  const { user, isAuthenticated } = useAuthStore();
  const { items, fetchCart } = useCartStore();
  const { currentOrder, clearOrder } = useOrderStore();

  const [cartLoad, setCartLoad] = useState<CartLoadStatus>('pending');
  const attemptRef = useRef(0);

  // Устаревший заказ прошлого визита не должен блокировать новую форму (AC6).
  useEffect(() => {
    clearOrder();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadCart = useCallback(async () => {
    const attempt = ++attemptRef.current;
    setCartLoad('pending');
    await fetchCart();
    if (attemptRef.current !== attempt) return;
    setCartLoad(useCartStore.getState().error ? 'error' : 'ready');
  }, [fetchCart]);

  useEffect(() => {
    if (!isInitialized || !isAuthenticated) {
      return;
    }
    loadCart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isInitialized, isAuthenticated, user?.id, fetchCart]);

  const view = resolveCheckoutView({
    isAuthInitialized: isInitialized,
    isAuthenticated,
    cartLoad,
    hasItems: items.length > 0,
    isRedirecting: currentOrder?.id != null,
  });

  return (
    <div className="container mx-auto px-4 py-8 sm:px-6 lg:px-8">
      {/* Заголовок страницы */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 sm:text-3xl">Оформление заказа</h1>
        {isAuthenticated && user && (
          <p className="mt-2 text-sm text-gray-600">
            Здравствуйте, {user.first_name} {user.last_name}
          </p>
        )}
      </div>

      {view === 'form' ? (
        <CheckoutForm user={user} />
      ) : (
        <CheckoutStateView view={view} onRetry={loadCart} />
      )}
    </div>
  );
}

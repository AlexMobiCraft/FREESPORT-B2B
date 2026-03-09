'use client';

import { useEffect } from 'react';
import { useAuthStore } from '@/stores/authStore';
import { useCartStore } from '@/stores/cartStore';
import { CheckoutForm } from '@/components/checkout/CheckoutForm';

/**
 * Клиентский компонент страницы checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 *
 * Отвечает за:
 * - Получение данных пользователя из authStore
 * - Рендеринг формы CheckoutForm с автозаполнением
 * - Обработку успешного создания заказа (переадресация в Story 15.2)
 */
export function CheckoutPageClient() {
  const { user, isAuthenticated } = useAuthStore();
  const { fetchCart, items } = useCartStore();

  // Загружаем корзину при монтировании, если она еще не загружена
  useEffect(() => {
    fetchCart();
  }, [fetchCart]);

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

      {/* Основная форма checkout */}
      <CheckoutForm user={user} />
    </div>
  );
}

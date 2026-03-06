'use client';

import { useCartStore } from '@/stores/cartStore';
import { Button } from '@/components/ui';
import { cn } from '@/utils/cn';

export interface OrderSummaryProps {
  /** Флаг состояния отправки формы */
  isSubmitting: boolean;
  /** Текст ошибки отправки (если есть) */
  submitError?: string | null;
  /** Флаг пустой корзины (передаётся из CheckoutForm) */
  isCartEmpty?: boolean;
}

/**
 * Компонент сводки заказа для checkout
 *
 * Story 15.1: Checkout страница и упрощённая форма
 * Story 15.2: Интеграция с Orders API
 *
 * Отображает:
 * - Список товаров из корзины (название, количество, цена)
 * - Итоговую сумму заказа
 * - Стоимость доставки (placeholder "Уточняется")
 * - Кнопку "Оформить заказ" (submit формы)
 *
 * Адаптивная вёрстка:
 * - Mobile: под формой
 * - Desktop: sticky sidebar справа
 */
export function OrderSummary({ isSubmitting, submitError, isCartEmpty }: OrderSummaryProps) {
  const { items, totalPrice } = useCartStore();

  // Проверка на пустую корзину
  // Если в сторе есть товары, значит корзина НЕ пуста, даже если пропс говорит обратное (защита от гидратации)
  const isEmpty = items.length > 0 ? false : (isCartEmpty ?? true);

  return (
    <div
      className={cn('rounded-lg bg-white p-6 shadow-sm', !isEmpty && 'lg:sticky lg:top-4')}
      data-testid="order-summary"
    >
      <h2 className="mb-4 text-lg font-semibold text-gray-900">Ваш заказ</h2>

      {isEmpty ? (
        <p className="text-sm text-gray-600" data-testid="empty-cart-message">
          Корзина пуста
        </p>
      ) : (
        <>
          {/* Список товаров */}
          <div className="mb-4 space-y-3" data-testid="order-summary-items">
            {items.map(item => (
              <div key={item.id} className="flex justify-between text-sm" data-testid="cart-item">
                <div className="flex-1">
                  <p className="font-medium text-gray-900">{item.product.name}</p>
                  {(item.variant.color_name || item.variant.size_value) && (
                    <p className="text-xs text-gray-500">
                      {[item.variant.color_name, item.variant.size_value]
                        .filter(Boolean)
                        .join(' / ')}
                    </p>
                  )}
                  <p className="text-gray-600">
                    {item.quantity} × {parseFloat(item.unit_price).toLocaleString('ru-RU')} ₽
                  </p>
                </div>
                <p className="font-medium text-gray-900">
                  {parseFloat(item.total_price).toLocaleString('ru-RU')} ₽
                </p>
              </div>
            ))}
          </div>

          <div className="border-t border-gray-200 pt-4">
            {/* Итого за товары */}
            <div className="mb-2 flex justify-between text-sm">
              <span className="text-gray-600">Итого за товары:</span>
              <span className="font-medium text-gray-900" data-testid="total-price-items">
                {totalPrice.toLocaleString('ru-RU')} ₽
              </span>
            </div>

            {/* Доставка (placeholder) */}
            <div className="mb-4 flex justify-between text-sm">
              <span className="text-gray-600">Доставка:</span>
              <span className="text-gray-600">Уточняется</span>
            </div>

            {/* Общая сумма */}
            <div className="border-t border-gray-200 pt-4">
              <div className="flex justify-between">
                <span className="text-lg font-semibold text-gray-900">Итого:</span>
                <span className="text-lg font-semibold text-gray-900" data-testid="total-price">
                  {totalPrice.toLocaleString('ru-RU')} ₽
                </span>
              </div>
              <p className="mt-1 text-xs text-gray-500">
                Финальная стоимость с учётом доставки будет рассчитана после оформления
              </p>
            </div>
          </div>
        </>
      )}

      {/* Ошибка отправки - ВСЕГДА В DOM */}
      {submitError && (
        <div
          className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-800"
          role="alert"
          aria-live="polite"
          data-testid="submit-error"
        >
          {submitError}
        </div>
      )}

      {/* Кнопка оформления заказа - отображается только если корзина не пуста */}
      {!isEmpty && (
        <>
          <Button
            type="submit"
            variant="primary"
            size="large"
            className="mt-6 w-full text-white"
            loading={isSubmitting}
            disabled={isSubmitting}
            aria-busy={isSubmitting}
            data-testid="checkout-submit-button"
          >
            {isSubmitting ? 'Оформление...' : 'Оформить заказ'}
          </Button>

          {/* Дополнительная информация */}
          <p className="mt-4 text-center text-xs text-gray-500">
            Нажимая кнопку, вы соглашаетесь с условиями обработки персональных данных
          </p>
        </>
      )}
    </div>
  );
}
